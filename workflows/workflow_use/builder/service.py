import base64
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import aiofiles
from browser_use.llm import UserMessage
from browser_use.llm.base import BaseChatModel
from pydantic import ValidationError

from workflow_use.builder.prompts import WORKFLOW_BUILDER_PROMPT_TEMPLATE
from workflow_use.controller.service import WorkflowController
from workflow_use.schema.views import WorkflowDefinitionSchema

logger = logging.getLogger(__name__)


class BuilderService:
	"""
	Service responsible for building executable workflow JSON definitions
	from recorded browser session events using an LLM.
	"""

	def __init__(self, llm: BaseChatModel):
		"""
		Initializes the BuilderService.

		Args:
		    llm: A LangChain BaseChatModel instance configured for use.
		         It should ideally support vision capabilities if screenshots are used.
		"""
		if llm is None:
			raise ValueError('A BaseChatModel instance must be provided.')

		# Store the LLM - will use browser-use's output_format parameter
		self.llm = llm
		self.prompt_template_str = WORKFLOW_BUILDER_PROMPT_TEMPLATE
		self.actions_markdown = self._get_available_actions_markdown()
		logger.info('BuilderService initialized.')

	@staticmethod
	def _get_available_actions_markdown() -> str:
		"""Return a markdown list of available actions and their schema."""
		controller = WorkflowController()
		lines: List[str] = []
		for action in controller.registry.registry.actions.values():
			# Only include deterministic actions relevant for building from recordings
			# Exclude agent-specific or meta-actions if necessary
			# Based on schema/views.py, the recorder types seem to map directly
			# to controller action *names*, but the prompt uses the event `type` field.
			# Let's assume the prompt template correctly lists the *event types* expected.
			# This function provides the detailed schema for the LLM.
			schema_info = action.param_model.model_json_schema()
			# Simplify schema representation for the prompt if too verbose
			param_details = []
			props = schema_info.get('properties', {})
			required = schema_info.get('required', [])
			for name, details in props.items():
				req_star = '*' if name in required else ''
				param_details.append(f'`{name}`{req_star} ({details.get("type", "any")})')

			lines.append(f'- **`{action.name}`**: {action.description}')  # Using action name from controller
			if param_details:
				lines.append(f'  - Parameters: {", ".join(param_details)}')

		# Add descriptions for agent/extract_content types manually if not in controller
		if 'agent' not in [a.name for a in controller.registry.registry.actions.values()]:
			lines.append('- **`agent`**: Executes a task using an autonomous agent.')
			lines.append('  - Parameters: `task`* (string), `description` (string), `max_steps` (integer)')
		# if "extract_content" not in [
		#     a.name for a in controller.registry.registry.actions.values()
		# ]:
		#     lines.append(
		#         "- **`extract_content`**: Uses an LLM to extract specific information from the current page."
		#     )
		#     lines.append(
		#         "  - Parameters: `goal`* (string), `description` (string), `should_strip_link_urls` (boolean)"
		#     )

		logger.debug(f'Generated actions markdown:\n{lines}')
		return '\n'.join(lines)

	@staticmethod
	def _find_first_user_interaction_url(events: List[Dict[str, Any]]) -> Optional[str]:
		"""Finds the URL of the first recorded user interaction."""
		return next(
			(
				evt.get('frameUrl')
				for evt in events
				if evt.get('type')
				in [
					'input',
					'click',
					'scroll',
					'select_change',
					'key_press',
				]  # Added more types
			),
			None,
		)

	def _parse_llm_output_to_workflow(self, llm_content: str) -> WorkflowDefinitionSchema:
		"""Attempts to parse the LLM string output into a WorkflowDefinitionSchema."""
		logger.debug(f'Raw LLM Output:\n{llm_content}')
		content_to_parse = llm_content

		# Heuristic cleanup: Extract JSON from markdown code blocks
		if '```json' in content_to_parse:
			match = re.search(r'```json\s*([\s\S]*?)\s*```', content_to_parse, re.DOTALL)
			if match:
				content_to_parse = match.group(1).strip()
				logger.debug('Extracted JSON from ```json block.')
		elif content_to_parse.strip().startswith('{') and content_to_parse.strip().endswith('}'):
			# Assume it's already JSON if it looks like it
			content_to_parse = content_to_parse.strip()
			logger.debug('Assuming raw output is JSON.')
		else:
			logger.warning('Could not reliably extract JSON from LLM output, attempting parse anyway.')

		try:
			# Try parsing directly first (might work with structured output)
			workflow_data = WorkflowDefinitionSchema.model_validate_json(content_to_parse)
			logger.info('Successfully parsed LLM output into WorkflowDefinitionSchema.')
			return workflow_data
		except (json.JSONDecodeError, ValidationError) as e:
			logger.error(f'Failed to parse LLM output into WorkflowDefinitionSchema: {e}')
			logger.debug(f'Content attempted parsing:\n{content_to_parse}')
			raise ValueError(f'LLM output could not be parsed into a valid Workflow schema. Error: {e}') from e

	async def build_workflow(
		self,
		input_workflow: WorkflowDefinitionSchema,
		user_goal: str,
		use_screenshots: bool = False,
		max_images: int = 20,
	) -> WorkflowDefinitionSchema:
		"""
		Generates an enhanced Workflow definition from an input workflow object using an LLM.

		Args:
		    input_workflow: The initial WorkflowDefinitionSchema object containing steps to process.
		    user_goal: Optional high-level description of the workflow's purpose.
		               If None, the user might be prompted interactively.
		    use_screenshots: Whether to include screenshots as visual context for the LLM (if available in steps).
		    max_images: Maximum number of screenshots to include (to manage cost/tokens).

		Returns:
		    A new WorkflowDefinitionSchema object generated by the LLM.

		Raises:
		    ValueError: If the input workflow is invalid or the LLM output cannot be parsed.
		    Exception: For other LLM or processing errors.
		"""
		# Validate input slightly
		if not input_workflow or not isinstance(input_workflow.steps, list):
			raise ValueError('Invalid input_workflow object provided.')

		# Handle user goal
		goal = user_goal
		if goal is None:
			try:
				goal = input('Please describe the high-level task for the workflow (optional, press Enter to skip): ').strip()
			except EOFError:  # Handle non-interactive environments
				goal = ''
		goal = goal or 'Automate the recorded browser actions.'  # Default goal if empty

		# Format the main instruction prompt
		prompt_str = self.prompt_template_str.format(
			actions=self.actions_markdown,
			goal=goal,
		)

		# Prepare the vision messages list
		vision_messages: List[Dict[str, Any]] = [{'type': 'text', 'text': prompt_str}]

		# Integrate message preparation logic here
		images_used = 0
		for step in input_workflow.steps:
			step_messages: List[Dict[str, Any]] = []  # Messages for this specific step

			# 1. Text representation (JSON dump)
			step_dict = step.model_dump(mode='json', exclude_none=True)
			screenshot_data = step_dict.pop('screenshot', None)  # Pop potential screenshot
			step_messages.append({'type': 'text', 'text': json.dumps(step_dict, indent=2)})

			# 2. Optional screenshot
			attach_image = use_screenshots and images_used < max_images
			step_type = getattr(step, 'type', step_dict.get('type'))

			if attach_image and step_type != 'input':  # Don't attach for inputs
				# Re-retrieve screenshot data if it wasn't popped (e.g., nested under 'data')
				# This assumes screenshot might still be in the original step model or dict
				# A bit redundant, ideally screenshot handling is consistent
				screenshot = screenshot_data or getattr(step, 'screenshot', None) or step_dict.get('data', {}).get('screenshot')

				if screenshot:
					if isinstance(screenshot, str) and screenshot.startswith('data:'):
						screenshot = screenshot.split(',', 1)[-1]

					# Validate base64 payload
					try:
						base64.b64decode(cast(str, screenshot), validate=True)
						meta = f"<Screenshot for event type '{step_type}'>"
						step_messages.append({'type': 'text', 'text': meta})
						step_messages.append(
							{
								'type': 'image_url',
								'image_url': {'url': f'data:image/png;base64,{screenshot}'},
							}
						)
						images_used += 1  # Increment image count *only* if successfully added
					except (TypeError, ValueError, Exception) as e:
						logger.warning(
							f"Invalid or missing screenshot for step type '{step_type}' "
							f'@ {step_dict.get("timestamp", "")}. Error: {e}'
						)
						# Don't add image messages if invalid

			# Add the messages for this step to the main list
			vision_messages.extend(step_messages)

		logger.info(f'Prepared {len(vision_messages)} total message parts, including {images_used} images.')

		# Invoke the LLM with structured output
		try:
			llm_response = await self.llm.ainvoke(
				[UserMessage(content=cast(Any, vision_messages))], output_format=WorkflowDefinitionSchema
			)
			workflow_data = llm_response.completion
		except Exception as e:
			logger.exception(f'An error occurred during LLM invocation or processing: {e}')
			raise

		# Return the workflow data object directly
		return workflow_data

	# path handlers
	async def build_workflow_from_path(self, path: Path, user_goal: str) -> WorkflowDefinitionSchema:
		"""Build a workflow from a JSON file path."""
		async with aiofiles.open(path, 'r') as f:
			content = await f.read()
			workflow_data = json.loads(content)

		workflow_data_schema = WorkflowDefinitionSchema.model_validate(workflow_data)
		return await self.build_workflow(workflow_data_schema, user_goal)

	async def save_workflow_to_path(self, workflow: WorkflowDefinitionSchema, path: Path):
		"""Save a workflow to a JSON file path."""
		async with aiofiles.open(path, 'w') as f:
			await f.write(json.dumps(workflow.model_dump(mode='json'), indent=2))
