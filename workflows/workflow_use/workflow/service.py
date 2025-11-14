from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, TypeVar
from typing import cast as _cast

import yaml
from browser_use import Agent, Browser
from browser_use.agent.views import ActionResult, AgentHistoryList
from browser_use.llm import SystemMessage, UserMessage
from browser_use.llm.base import BaseChatModel
from browser_use.tools.views import NoParamsAction
from pydantic import BaseModel, Field, create_model

from workflow_use.controller.service import WorkflowController
from workflow_use.controller.utils import get_best_element_handle
from workflow_use.schema.views import (
	AgenticWorkflowStep,
	DeterministicWorkflowStep,
	WorkflowDefinitionSchema,
	WorkflowInputSchemaDefinition,
	WorkflowStep,
)
from workflow_use.workflow.element_finder import ElementFinder
from workflow_use.workflow.prompts import AGENT_STEP_SYSTEM_PROMPT, STRUCTURED_OUTPUT_PROMPT
from workflow_use.workflow.step_agent.controller import WorkflowStepAgentController
from workflow_use.workflow.views import WorkflowRunOutput

logger = logging.getLogger(__name__)

WAIT_FOR_ELEMENT_TIMEOUT = 2500

T = TypeVar('T', bound=BaseModel)


class Workflow:
	"""Simple orchestrator that executes a list of workflow *steps* defined in a WorkflowDefinitionSchema."""

	def __init__(
		self,
		workflow_schema: WorkflowDefinitionSchema,
		llm: BaseChatModel,
		*,
		controller: WorkflowController | None = None,
		browser: Browser | None = None,
		page_extraction_llm: BaseChatModel | None = None,
		fallback_to_agent: bool = True,
		use_cloud: bool = False,
		debug: bool = False,
		debug_log_folder: str | Path | None = None,
		step_wait_time: float | None = None,
	) -> None:
		"""Initialize a new Workflow instance from a schema object.

		Args:
			workflow_schema: The parsed workflow definition schema.
			controller: Optional WorkflowController instance to handle action execution
			browser: Optional Browser instance to use for browser automation
			llm: Optional language model for fallback agent functionality
			fallback_to_agent: Whether to fall back to agent-based execution on step failure
			use_cloud: Whether to use browser-use cloud browser service instead of local browser
			debug: Whether to enable debug mode (captures screenshots for each step)
			debug_log_folder: Custom folder path for debug logs and screenshots (default: ./logs/workflow_debug)
			step_wait_time: Time to wait between steps in seconds (default: uses workflow's default_wait_time or 0.1)

		Raises:
			ValueError: If the workflow schema is invalid (though Pydantic handles most).
		"""
		self.schema = workflow_schema  # Store the schema object

		self.controller = controller or WorkflowController()

		self.browser = browser or Browser(use_cloud=use_cloud)

		# Hack to not close it after agent kicks in
		self.browser.browser_profile.keep_alive = True

		self.llm = llm
		self.page_extraction_llm = page_extraction_llm

		self.fallback_to_agent = fallback_to_agent

		# Debug mode settings
		self.debug = debug
		self.debug_log_folder = Path(debug_log_folder) if debug_log_folder else Path('./logs/workflow_debug')

		# Step execution settings - use workflow's default_wait_time if not explicitly provided
		# Check for None explicitly to allow default_wait_time=0 to disable waits
		if step_wait_time is not None:
			self.step_wait_time = step_wait_time
		elif workflow_schema.default_wait_time is not None:
			self.step_wait_time = workflow_schema.default_wait_time
		else:
			self.step_wait_time = 0.1

		# Initialize multi-strategy element finder
		self.element_finder = ElementFinder()

		self.context: dict[str, Any] = {}

		self.inputs_def: List[WorkflowInputSchemaDefinition] = self.schema.input_schema
		self._input_model: type[BaseModel] = self._build_input_model()

	# --- Loaders ---
	@classmethod
	def load_from_file(
		cls,
		file_path: str | Path,
		llm: BaseChatModel,
		*,
		controller: WorkflowController | None = None,
		browser: Browser | None = None,
		page_extraction_llm: BaseChatModel | None = None,
		use_cloud: bool = False,
		debug: bool = False,
		debug_log_folder: str | Path | None = None,
		step_wait_time: float = 0.1,
	) -> Workflow:
		"""Load a workflow from a file."""
		with open(file_path, 'r', encoding='utf-8') as f:
			data = yaml.safe_load(f)
		workflow_schema = WorkflowDefinitionSchema(**data)
		return Workflow(
			workflow_schema=workflow_schema,
			controller=controller,
			browser=browser,
			llm=llm,
			page_extraction_llm=page_extraction_llm,
			use_cloud=use_cloud,
			debug=debug,
			debug_log_folder=debug_log_folder,
			step_wait_time=step_wait_time,
		)

	# --- Runners ---
	async def _run_deterministic_step(self, step: DeterministicWorkflowStep, step_index: int) -> ActionResult:
		"""Execute a deterministic (controller) action based on step dictionary."""
		# Assumes WorkflowStep for deterministic type has 'action' and 'params' keys
		action_name: str = step.type  # Expect 'action' key for deterministic steps
		all_params: Dict[str, Any] = step.model_dump(exclude_none=True)  # Exclude None values to prevent validation errors

		# Filter out workflow metadata fields that shouldn't be passed to browser-use ActionModel
		# Note: 'type' is NOT filtered here because some actions (like navigation) need it in their params
		workflow_metadata_fields = {
			'description',
			'output',
			'agent_reasoning',
			'page_context_url',
			'page_context_title',
			'cssSelector',
			'xpath',
			'elementTag',
			'elementHash',  # These are workflow-specific selector fields
			'selectorStrategies',  # Multi-strategy selectors
			'target_text',
			'container_hint',
			'position_hint',
			'interaction_type',  # Semantic workflow fields
		}

		# Keep only action-specific parameters
		params = {k: v for k, v in all_params.items() if k not in workflow_metadata_fields}

		# Try multi-strategy element finding for click and input actions
		if action_name in ['click', 'input'] and all_params.get('selectorStrategies'):
			try:
				strategies = all_params['selectorStrategies']
				target_text = all_params.get('target_text')  # Get target_text for validation

				logger.info(f'   🎯 Attempting semantic multi-strategy finding ({len(strategies)} strategies)')
				if target_text:
					logger.info(f'   🎯 Validating target text: "{target_text}"')

				result, strategy_attempts = await self.element_finder.find_element_with_strategies(
					strategies, self.browser, target_text
				)

				# Store strategy attempts for error reporting
				self._current_strategy_attempts = strategy_attempts

				if result:
					element_index_or_xpath, strategy_used = result
					strategy_type = strategy_used.get('type')
					logger.info(f'   ✅ Element found using strategy: {strategy_type}')

					# XPath strategies return a string, not an index
					# They should be handled by semantic_executor, not here
					if strategy_type == 'xpath':
						logger.info('   ⚠️  XPath strategy found - this should be handled by semantic_executor, not service.py')
						logger.info('   ⚠️  Falling back to full controller')
					else:
						# Semantic strategies return element index
						element_index = element_index_or_xpath
						logger.info(f'   ✅ Element found at index {element_index}')

						# Use the found index to execute the action through browser-use's controller
						# This ensures we use browser-use's native semantic action system
						if action_name == 'click':
							# Override the index param with our found index
							params['index'] = element_index
							logger.info(f'   ✅ Will click element at index {element_index} (semantic-only)')

						elif action_name == 'input':
							# Override the index param with our found index
							params['index'] = element_index
							logger.info(f'   ✅ Will input to element at index {element_index} (semantic-only)')

						# Continue to controller execution below with updated index
						# This way we leverage browser-use's robust action handling

				else:
					logger.warning('   ⚠️  Multi-strategy finding failed, falling back to full controller')
					# If target_text was provided and we couldn't find it, raise an error
					if target_text:
						raise RuntimeError(
							f'Element with target text "{target_text}" not found on the page. '
							f'Tried {len(strategies)} strategies but none matched a visible element with this text.'
						)

			except Exception as e:
				logger.warning(f'   ⚠️  Error in multi-strategy finding: {e}, falling back to full controller')
				# Re-raise if it's our validation error
				if 'target text' in str(e).lower():
					raise

		# Special handling for actions that don't accept any parameters
		# These actions use NoParamsAction, so we pass an empty instance instead of {}
		empty_actions = {'go_back', 'go_forward'}
		if action_name in empty_actions:
			params = NoParamsAction()  # type: ignore

		ActionModel = self.controller.registry.create_action_model(include_actions=[action_name])
		# Pass the params dictionary directly
		# For empty actions, ActionModel itself IS the action (EmptyActionModel), so don't wrap in dict
		if action_name in empty_actions:
			action_model = ActionModel()
		else:
			action_model = ActionModel(**{action_name: params})

		try:
			result = await self.controller.act(action_model, self.browser, page_extraction_llm=self.page_extraction_llm)
		except Exception as e:
			raise RuntimeError(f"Deterministic action '{action_name}' failed: {str(e)}")

		# Wait for page to stabilize after certain actions
		actions_requiring_wait = {'navigation', 'click', 'go_back', 'go_forward'}
		if action_name in actions_requiring_wait:
			try:
				page = await self.browser.get_current_page()
				# Wait for network to be idle (no more than 2 connections for at least 500ms)
				await page.wait_for_load_state('networkidle', timeout=10000)
				logger.info(f'Page stabilized after {action_name} action')
			except Exception as e:
				# Don't fail if wait times out, just log and continue
				logger.warning(f'Timeout waiting for page to stabilize after {action_name}: {e}')

		# Helper function to truncate long selectors in logs
		def truncate_selector(selector: str) -> str:
			return selector if len(selector) <= 45 else f'{selector[:45]}...'

		# Determine if this is not the last step, and extract next step's cssSelector if available
		current_index = step_index
		if current_index < len(self.schema.steps) - 1:
			next_step = self.schema.steps[current_index + 1]
			next_step_resolved = self._resolve_placeholders(next_step)
			css_selector = getattr(next_step_resolved, 'cssSelector', None)
			if css_selector:
				try:
					page = await self.browser.get_current_page()

					logger.info(f'Waiting for element with selector: {truncate_selector(css_selector)}')
					locator, selector_used = await get_best_element_handle(
						page, css_selector, next_step_resolved, timeout_ms=WAIT_FOR_ELEMENT_TIMEOUT
					)
					logger.info(f'Element with selector found: {truncate_selector(selector_used)}')
				except Exception as e:
					logger.error(f'Failed to wait for element with selector: {truncate_selector(css_selector)}. Error: {e}')
					raise Exception(f'Failed to wait for element. Selector: {css_selector}') from e

		return result

	def _format_agent_step_context(self, current_step: AgenticWorkflowStep, step_index: int) -> str:
		"""Format the workflow step context for the agent with extended context (last 2, current, next 2 steps)."""

		def format_step_info(step: WorkflowStep, step_num: int) -> str:
			"""Format step information consistently."""
			info = [f'Step {step_num}: Type: {step.type}']
			if step.description:
				info.append(f'Description: {step.description}')
			# For agent steps, show the task
			if isinstance(step, AgenticWorkflowStep):
				info.append(f'Task: {step.task}')
			return '\n'.join(info)

		sections = []
		total_steps = len(self.schema.steps)

		# Add previous steps context (last 2 steps)
		prev_steps = []
		for i in range(max(0, step_index - 2), step_index):
			prev_step = self.schema.steps[i]
			prev_steps.append(format_step_info(prev_step, i + 1))

		if prev_steps:
			sections.extend(['=== PREVIOUS STEPS (FOR CONTEXT ONLY) ===', '\n\n'.join(prev_steps), ''])

		# Add current step context
		sections.extend(['=== CURRENT STEP (YOUR TASK) ===', format_step_info(current_step, step_index + 1), ''])

		# Add next steps context (next 2 steps)
		next_steps = []
		for i in range(step_index + 1, min(total_steps, step_index + 3)):
			next_step = self.schema.steps[i]
			next_steps.append(format_step_info(next_step, i + 1))

		if next_steps:
			sections.extend(
				[
					'=== NEXT STEPS (FOR CONTEXT ONLY) ===',
					'\n\n'.join(next_steps),
				]
			)

		return '\n'.join(sections)

	async def _run_agent_step(self, step: AgenticWorkflowStep, step_index: int) -> AgentHistoryList:
		"""Spin-up an Agent based on step dictionary."""
		# Create contextual task with extended context (last 2, current, next 2 steps)
		contextual_task = self._format_agent_step_context(step, step_index)

		# logger.info(f'Contextual task: {contextual_task}')

		# 		task = """
		# {step.task}

		# Please do not make up any fake data.
		# """

		agent = Agent(
			task=step.task,  # Only the current step task goes into ultimate task
			message_context=contextual_task,  # Extended context with surrounding steps
			llm=self.llm,
			browser_session=self.browser,
			controller=WorkflowStepAgentController(),
			# use_vision=True,  # Consider making this configurable via WorkflowStep schema
			override_system_message=AGENT_STEP_SYSTEM_PROMPT,
		)

		return await agent.run()

	async def _run_extraction_step(self, step, step_index: int) -> ActionResult:
		"""
		Lightweight extraction that uses LLM directly without spinning up an agent.
		Much faster and cheaper than using a full agent for simple page content extraction.
		"""
		from browser_use.agent.views import ActionResult

		# Get extraction goal
		extraction_goal = ''
		if hasattr(step, 'goal'):
			extraction_goal = step.goal
		elif hasattr(step, 'extractionGoal'):
			extraction_goal = step.extractionGoal
		else:
			extraction_goal = 'Extract information from the page'

		# Get current page content using markdown extraction
		page = await self.browser.get_current_page()
		page_text, _ = await page._extract_clean_markdown()
		page_url = await page.get_url()

		# Use page_extraction_llm if available, otherwise fall back to main llm
		extraction_llm = self.page_extraction_llm or self.llm

		# Build extraction prompt
		# Limit page text to avoid token limits
		truncated_page_text = page_text[:10000] if page_text else ''

		extraction_prompt = f"""You are extracting information from a web page.

Page URL: {page_url}

Extraction Goal:
{extraction_goal}

Page Content:
{truncated_page_text}

Instructions:
- Extract the requested information accurately
- Return ONLY the extracted data, no explanations
- If the information is not found, return an empty string or appropriate null value
- Format the output as requested in the extraction goal

Extracted Information:"""

		# Call LLM directly
		messages = [UserMessage(content=extraction_prompt)]
		response = await extraction_llm.ainvoke(messages)

		# Extract the text content from response
		# ainvoke returns ChatInvokeCompletion with a 'completion' attribute
		extracted_content = ''
		if hasattr(response, 'completion'):
			extracted_content = response.completion
		elif isinstance(response, str):
			extracted_content = response

		logger.info(f'Extracted content: {extracted_content[:200]}...')

		# Return as ActionResult
		return ActionResult(
			is_done=False,
			extracted_content=extracted_content,
			include_in_memory=True,
		)

	# async def _fallback_to_agent(
	# 	self,
	# 	step_resolved: WorkflowStep,
	# 	step_index: int,
	# 	error: Exception | str | None = None,
	# ) -> AgentHistoryList:
	# 	"""Handle step failure by delegating to an agent."""

	# 	# print('Workflow steps:', step_resolved)
	# 	# Extract details from the failed step dictionary
	# 	failed_action_name = step_resolved.type
	# 	failed_params = step_resolved.model_dump()
	# 	step_description = step_resolved.description or 'No description provided'
	# 	error_msg = str(error) if error else 'Unknown error'
	# 	total_steps = len(self.steps)
	# 	fail_details = (
	# 		f"step={step_index + 1}/{total_steps}, action='{failed_action_name}', "
	# 		f"description='{step_description}', params={str(failed_params)}, error='{error_msg}'"
	# 	)

	# 	# Determine the failed_value based on step type and attributes
	# 	failed_value = None
	# 	description_prefix = f'Purpose: {step_description}. ' if step_description else ''

	# 	if isinstance(step_resolved, NavigationStep):
	# 		failed_value = f'{description_prefix}Navigate to URL: {step_resolved.url}'
	# 	elif isinstance(step_resolved, ClickStep):
	# 		# element_info = step_resolved.elementText or step_resolved.cssSelector
	# 		# failed_value = f"{description_prefix}Click element: {element_info}"
	# 		failed_value = f'Find and click element with description: {step_resolved.description}'
	# 	elif isinstance(step_resolved, InputStep):
	# 		failed_value = f"{description_prefix}Input text: '{step_resolved.value}' into element."
	# 	elif isinstance(step_resolved, SelectChangeStep):
	# 		failed_value = f"{description_prefix}Select option: '{step_resolved.selectedText}' in dropdown."
	# 	elif isinstance(step_resolved, KeyPressStep):
	# 		failed_value = f"{description_prefix}Press key: '{step_resolved.key}'"
	# 	elif isinstance(step_resolved, ScrollStep):
	# 		failed_value = f'{description_prefix}Scroll to position: (x={step_resolved.scrollX}, y={step_resolved.scrollY})'
	# 	else:
	# 		failed_value = f"{description_prefix}No specific target value available for action '{failed_action_name}'"

	# 	# Build workflow overview using the stored dictionaries
	# 	workflow_overview_lines: list[str] = []
	# 	for idx, step in enumerate(self.steps):
	# 		desc = step.description or ''
	# 		step_type_info = step.type
	# 		details = step.model_dump()
	# 		workflow_overview_lines.append(f'  {idx + 1}. ({step_type_info}) {desc} - {details}')
	# 	workflow_overview = '\n'.join(workflow_overview_lines)
	# 	# print(workflow_overview)

	# 	# Build the fallback task with the failed_value
	# 	fallback_task = WORKFLOW_FALLBACK_PROMPT_TEMPLATE.format(
	# 		step_index=step_index + 1,
	# 		total_steps=len(self.steps),
	# 		workflow_details=workflow_overview,
	# 		action_type=failed_action_name,
	# 		fail_details=fail_details,
	# 		failed_value=failed_value,
	# 		step_description=step_description,
	# 	)
	# 	logger.info(f'Agent fallback task: {fallback_task}')

	# 	# Prepare agent step config based on the failed step, adding task
	# 	agent_step_config = AgenticWorkflowStep(
	# 		type='agent',
	# 		task=fallback_task,
	# 		max_steps=5,
	# 		output=None,
	# 		description='Fallback agent to handle step failure',
	# 	)

	# 	return await self._run_agent_step(agent_step_config)

	def _validate_inputs(self, inputs: dict[str, Any]) -> None:
		"""Validate provided inputs against the workflow's input schema definition."""
		# If no inputs are defined in the schema, no validation needed
		if not self.inputs_def:
			return

		try:
			# Let Pydantic perform the heavy lifting – this covers both presence and
			# type validation based on the JSON schema model.
			self._input_model(**inputs)
		except Exception as e:
			raise ValueError(f'Invalid workflow inputs: {e}') from e

	def _resolve_placeholders(self, data: Any) -> Any:
		"""Recursively replace placeholders in *data* using current context variables.

		String placeholders are written using Python format syntax, e.g. "{index}".
		"""
		if isinstance(data, str):
			try:
				# Only attempt to format if placeholder syntax is likely present
				if '{' in data and '}' in data:
					formatted_data = data.format(**self.context)
					return formatted_data
				return data  # No placeholders, return as is
			except KeyError:
				# A key in the placeholder was not found in the context.
				# Return the original string as per previous behavior.
				return data

		# TODO: This next things are not really supported atm, we'll need to to do it in the future.
		elif isinstance(data, list):
			new_list = []
			changed = False
			for item in data:
				resolved_item = self._resolve_placeholders(item)
				if resolved_item is not item:
					changed = True
				new_list.append(resolved_item)
			return new_list if changed else data
		elif isinstance(data, dict):
			new_dict = {}
			changed = False
			for key, value in data.items():
				resolved_value = self._resolve_placeholders(value)
				if resolved_value is not value:
					changed = True
				new_dict[key] = resolved_value
			return new_dict if changed else data
		elif isinstance(data, BaseModel):  # Handle Pydantic models
			from workflow_use.schema.views import InputStep

			update_dict = {}
			model_changed = False
			for field_name in data.model_fields:  # Iterate using model_fields keys
				original_value = getattr(data, field_name)
				resolved_value = self._resolve_placeholders(original_value)
				if resolved_value is not original_value:
					model_changed = True
				update_dict[field_name] = resolved_value

			# Special handling for InputStep: use default_value if value is empty or unresolved
			if isinstance(data, InputStep):
				value = update_dict.get('value', getattr(data, 'value'))
				default_value = update_dict.get('default_value', getattr(data, 'default_value', None))

				if default_value:
					should_use_default = False

					# Case 1: Value is empty or whitespace-only
					if not value or not value.strip():
						should_use_default = True
					# Case 2: Value contains unresolved placeholders
					elif '{' in value and '}' in value:
						original_value_str = getattr(data, 'value')
						# Check if placeholder wasn't resolved (value unchanged and still has placeholders)
						if value == original_value_str:
							should_use_default = True

					if should_use_default:
						update_dict['value'] = default_value
						model_changed = True

			if model_changed:
				return data.model_copy(update=update_dict)
			else:
				return data  # Return original instance if no field's value changed
		else:
			# For any other types (int, float, bool, None, etc.), return as is
			return data

	def _store_output(self, step_cfg: WorkflowStep, result: Any) -> None:
		"""Store output into context based on 'output' key in step dictionary."""
		# Assumes WorkflowStep schema includes an optional 'output' field (string)
		output_key = step_cfg.output
		if not output_key:
			return

		# Helper to extract raw content we want to store

		value: Any = None

		if isinstance(result, ActionResult):
			# Prefer JSON in extracted_content if available
			content = result.extracted_content
			if content is None:
				value = {
					'success': result.success,
					'is_done': result.is_done,
				}
			else:
				try:
					value = json.loads(content)
				except Exception:
					value = content
		elif isinstance(result, AgentHistoryList):
			# Try to pull last ActionResult with extracted_content
			try:
				last_item = result.history[-1]
				last_action_result = next(
					(r for r in reversed(last_item.result) if r.extracted_content is not None),
					None,
				)
				if last_action_result and last_action_result.extracted_content:
					try:
						value = json.loads(last_action_result.extracted_content)
					except Exception:
						value = last_action_result.extracted_content
			except Exception:
				value = None
		else:
			value = str(result)

		self.context[output_key] = value

	async def _execute_step(self, step_index: int, step_resolved: WorkflowStep) -> ActionResult | AgentHistoryList:
		"""Execute the resolved step dictionary, handling type branching and fallback."""
		# Use 'type' field from the WorkflowStep dictionary
		result: ActionResult | AgentHistoryList

		if isinstance(step_resolved, DeterministicWorkflowStep):
			from browser_use.agent.views import ActionResult  # Local import ok

			action_name = step_resolved.type or '[No action specified]'

			# Extraction steps use lightweight LLM extraction (no agent needed)
			is_extraction_step = action_name in ['extract', 'extract_page_content']
			if is_extraction_step:
				logger.info(f'Step {step_index + 1}: Extraction step detected - using lightweight LLM extraction')
				result = await self._run_extraction_step(step_resolved, step_index)

			# Check if this is a selector step without cssSelector - use semantic execution
			elif action_name in ['click', 'input', 'key_press', 'select_change']:
				requires_selector = True
				has_css_selector = hasattr(step_resolved, 'cssSelector') and step_resolved.cssSelector
				has_target_text = hasattr(step_resolved, 'target_text') and step_resolved.target_text

				if not has_css_selector and has_target_text:
					# Use semantic execution as fallback
					logger.info(f'Step {step_index + 1}: cssSelector missing but target_text present - using semantic execution')
					from workflow_use.workflow.semantic_executor import SemanticWorkflowExecutor

					if not hasattr(self, '_semantic_executor'):
						self._semantic_executor = SemanticWorkflowExecutor(
							self.browser, page_extraction_llm=self.page_extraction_llm
						)
					result = await self._semantic_executor.execute_step(step_resolved)
				else:
					# Use deterministic controller execution
					try:
						logger.info(f'Attempting deterministic action: {action_name}')
						result = await self._run_deterministic_step(step_resolved, step_index)
						if isinstance(result, ActionResult) and result.error:
							logger.warning(f'Deterministic action reported error: {result.error}')
							raise ValueError(f'Deterministic action {action_name} failed: {result.error}')
					except Exception as e:
						action_name = step_resolved.type or '[Unknown Action]'
						logger.warning(
							f'Deterministic step {step_index + 1} ({action_name}) failed: {e}. Attempting fallback with agent.'
						)
						raise ValueError(f'Deterministic step {step_index + 1} ({action_name}) failed: {e}')
			else:
				# Use deterministic controller execution for all other actions
				try:
					logger.info(f'Attempting deterministic action: {action_name}')
					result = await self._run_deterministic_step(step_resolved, step_index)
					if isinstance(result, ActionResult) and result.error:
						logger.warning(f'Deterministic action reported error: {result.error}')
						raise ValueError(f'Deterministic action {action_name} failed: {result.error}')
				except Exception as e:
					action_name = step_resolved.type or '[Unknown Action]'
					logger.warning(
						f'Deterministic step {step_index + 1} ({action_name}) failed: {e}. Attempting fallback with agent.'
					)
					raise ValueError(f'Deterministic step {step_index + 1} ({action_name}) failed: {e}')

				# if self.fallback_to_agent:
				# 	result = await self._fallback_to_agent(step_resolved, step_index, e)
				# 	if not result.is_successful():
				# 		raise ValueError(f'Deterministic step {step_index + 1} ({action_name}) failed even after fallback')
				# else:
				# 	raise ValueError(f'Deterministic step {step_index + 1} ({action_name}) failed: {e}')

		elif isinstance(step_resolved, AgenticWorkflowStep):
			# Use task key from step dictionary
			task_description = step_resolved.task
			logger.info(f'Running agent task: {task_description}')
			try:
				result = await self._run_agent_step(step_resolved, step_index)
				if not result.is_successful():
					logger.warning(f'Agent step {step_index + 1} failed evaluation.')
					raise ValueError(f'Agent step {step_index + 1} failed evaluation.')

			except Exception as e:
				raise ValueError(f'Agent step {step_index + 1} failed: {e}. (Agent fallback is disabled)')

				if self.fallback_to_agent:
					logger.warning(f'Agent step {step_index + 1} failed: {e}. Attempting fallback with agent.')

					# result = await self._fallback_to_agent(step_resolved, step_index, e)
					# if not result.is_successful():
					# 	raise ValueError(f'Agent step {step_index + 1} failed even after fallback')
				else:
					raise ValueError(f'Agent step {step_index + 1} failed: {e}')

		return result

	# --- Convert all extracted stuff to final output model ---
	async def _convert_results_to_output_model(
		self,
		results: List[ActionResult | AgentHistoryList],
		output_model: type[T],
	) -> T:
		"""Convert workflow results to a specified output model.

		Filters ActionResults with extracted_content, then uses LLM to parse
		all extracted texts into the structured output model.

		Args:
			results: List of workflow step results
			output_model: Target Pydantic model class to convert to

		Returns:
			An instance of the specified output model
		"""
		if not results:
			raise ValueError('No results to convert')

		# Extract all content from ActionResults
		extracted_contents = []

		for result in results:
			if isinstance(result, ActionResult) and result.extracted_content:
				extracted_contents.append(result.extracted_content)
			# TODO: this might be incorrect; but it helps A LOT if extract fucks up and only the agent is able to solve it
			elif isinstance(result, AgentHistoryList):
				# Check the agent history for any extracted content
				for item in result.history:
					for action_result in item.result:
						if action_result.extracted_content:
							extracted_contents.append(action_result.extracted_content)

		if not extracted_contents:
			raise ValueError('No extracted content found in workflow results')

		# Combine all extracted contents
		combined_text = '\n\n'.join(extracted_contents)

		messages = [
			SystemMessage(content=STRUCTURED_OUTPUT_PROMPT),
			UserMessage(content=combined_text),
		]

		response = await self.llm.ainvoke(messages, output_format=output_model)
		return response.completion

	async def run_step(self, step_index: int, inputs: dict[str, Any] | None = None):
		"""Run a *single* workflow step asynchronously and return its result.

		Parameters
		----------
		step_index:
				Zero-based index of the step to execute.
		inputs:
				Optional workflow-level inputs.  If provided on the first call they
				are validated and injected into :pyattr:`context`.  Subsequent
				calls can omit *inputs* as :pyattr:`context` is already populated.
		"""
		if not (0 <= step_index < len(self.schema.steps)):
			raise IndexError(f'step_index {step_index} is out of range for workflow with {len(self.schema.steps)} steps')

		# Initialise/augment context once with the provided inputs
		if inputs is not None or not self.context:
			runtime_inputs = inputs or {}
			self._validate_inputs(runtime_inputs)
			# If context is empty we assume this is the first invocation – start fresh;
			# otherwise merge new inputs on top (explicitly overriding duplicates)
			if not self.context:
				self.context = runtime_inputs.copy()
			else:
				self.context.update(runtime_inputs)

		async with self.browser:
			raw_step_cfg = self.schema.steps[step_index]
			step_resolved = self._resolve_placeholders(raw_step_cfg)
			result = await self._execute_step(step_index, step_resolved)
			# Persist outputs (if declared) for future steps
			self._store_output(step_resolved, result)
			await asyncio.sleep(5)  # Keep browser open for 5 seconds
		# Each invocation opens a new browser context – we close the browser to
		# release resources right away.  This keeps the single-step API
		# self-contained.
		# await self.browser.close() # <-- Commented out for testing
		return result

	async def _capture_debug_screenshot(self, step_index: int, step_description: str, prefix: str = '') -> None:
		"""Capture a screenshot for debugging purposes.

		Args:
			step_index: The index of the current step
			step_description: Description of the step for the filename
			prefix: Optional prefix for the filename (e.g., 'before', 'after', 'error')
		"""
		if not self.debug:
			return

		try:
			# Create debug log folder if it doesn't exist
			self.debug_log_folder.mkdir(parents=True, exist_ok=True)

			# Clean step description for filename (remove special characters)
			import re

			clean_description = re.sub(r'[^\w\s-]', '', step_description)
			clean_description = re.sub(r'[-\s]+', '_', clean_description)
			clean_description = clean_description[:50]  # Limit length

			# Create timestamp for uniqueness
			from datetime import datetime

			timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

			# Build filename
			prefix_str = f'{prefix}_' if prefix else ''
			filename = f'step_{step_index + 1:02d}_{prefix_str}{clean_description}_{timestamp}.png'
			screenshot_path = self.debug_log_folder / filename

			# Capture screenshot
			page = await self.browser.get_current_page()
			await page.screenshot(path=str(screenshot_path), full_page=True)

			logger.info(f'📸 Debug screenshot saved: {screenshot_path}')

		except Exception as e:
			logger.warning(f'Failed to capture debug screenshot: {e}')

	async def run(
		self,
		inputs: dict[str, Any] | None = None,
		close_browser_at_end: bool = True,
		cancel_event: asyncio.Event | None = None,
		output_model: type[T] | None = None,
	) -> WorkflowRunOutput[T]:
		"""Execute the workflow asynchronously using step dictionaries.

		@dev This is the main entry point for the workflow.

		Args:
			inputs: Optional dictionary of workflow inputs
			close_browser_at_end: Whether to close the browser when done
			cancel_event: Optional event to signal cancellation
			output_model: Optional Pydantic model class to convert results to

		Returns:
			Either WorkflowRunOutput containing all step results or an instance of output_model if provided
		"""
		runtime_inputs = inputs or {}
		# 1. Validate inputs against definition
		self._validate_inputs(runtime_inputs)
		# 2. Initialize context with validated inputs
		self.context = runtime_inputs.copy()  # Start with a fresh context

		results: List[ActionResult | AgentHistoryList] = []

		# Log debug mode status
		if self.debug:
			logger.info(f'🐛 Debug mode enabled - screenshots will be saved to: {self.debug_log_folder}')
			# Create debug folder at the start
			self.debug_log_folder.mkdir(parents=True, exist_ok=True)

		# Log step wait time if configured
		if self.step_wait_time > 0.1:  # Only log if it's been changed from default
			logger.info(f'⏱️  Step wait time configured: {self.step_wait_time}s between steps')

		await self.browser.start()
		try:
			for step_index, step_dict in enumerate(self.schema.steps):  # self.steps now holds dictionaries
				# Wait between steps (configurable)
				if step_index > 0:  # Don't wait before the first step
					# Get wait time from previous step's wait_time or use default
					# Use 'is not None' to allow wait_time=0 to skip the delay intentionally
					previous_step = self.schema.steps[step_index - 1]
					step_wait_time_value = getattr(previous_step, 'wait_time', None)
					wait_time = step_wait_time_value if step_wait_time_value is not None else self.step_wait_time
					await asyncio.sleep(wait_time)
					if wait_time > 0:
						logger.debug(f'Waited {wait_time}s between steps')

				# Check if cancellation was requested
				if cancel_event and cancel_event.is_set():
					logger.info('Cancellation requested - stopping workflow execution')
					break

				# Use description from the step dictionary
				step_description = step_dict.description or 'No description provided'
				logger.info(f'--- Running Step {step_index + 1}/{len(self.schema.steps)} -- {step_description} ---')

				# Capture screenshot before step execution (if debug enabled)
				await self._capture_debug_screenshot(step_index, step_description, prefix='before')

				# Resolve placeholders using the current context (works on the dictionary)
				step_resolved = self._resolve_placeholders(step_dict)

				# Execute step using the unified _execute_step method
				try:
					result = await self._execute_step(step_index, step_resolved)

					# Capture screenshot after successful step execution (if debug enabled)
					await self._capture_debug_screenshot(step_index, step_description, prefix='after')
				except Exception as e:
					# Capture screenshot on error (if debug enabled)
					await self._capture_debug_screenshot(step_index, step_description, prefix='error')
					raise  # Re-raise the exception after capturing screenshot

				results.append(result)
				# Persist outputs using the resolved step dictionary
				self._store_output(step_resolved, result)
				logger.info(f'--- Finished Step {step_index + 1} ---\n')

			# Convert results to output model if requested
			output_model_result: T | None = None
			if output_model:
				output_model_result = await self._convert_results_to_output_model(results, output_model)

		finally:
			# Clean-up browser after finishing workflow
			if close_browser_at_end:
				self.browser.browser_profile.keep_alive = False
				await self.browser.stop()

		return WorkflowRunOutput(step_results=results, output_model=output_model_result)

	# ------------------------------------------------------------------
	# LLM tool wrapper
	# ------------------------------------------------------------------

	def _build_input_model(self) -> type[BaseModel]:
		"""Return a *pydantic* model matching the workflow's ``input_schema`` section.

		This creates a dynamic Pydantic model that includes format information in field
		descriptions, making format requirements visible to LLMs when workflows are used as tools.
		"""

		if not self.inputs_def:
			# No declared inputs -> generate an empty model
			# Use schema name for uniqueness, fallback if needed
			model_name = f'{(self.schema.name or "Workflow").replace(" ", "_")}_NoInputs'
			return create_model(model_name)

		# Map workflow input types to Python types
		type_mapping = {
			'string': str,
			'number': float,
			'bool': bool,
		}

		# Build fields dictionary for create_model()
		fields: Dict[str, tuple[type, Any]] = {}

		for input_def in self.inputs_def:
			name = input_def.name
			type_str = input_def.type
			py_type = type_mapping.get(type_str)

			if py_type is None:
				raise ValueError(f'Unsupported input type: {type_str!r} for field {name!r}')

			# Create field description with format information if available
			# This helps LLMs understand expected input formats when workflow is used as a tool
			field_description = None
			if hasattr(input_def, 'format') and input_def.format:
				field_description = f'Format: {input_def.format}'

			# Build field tuple: (type, default_or_field_info)
			# Pydantic's create_model uses ... (Ellipsis) to mark required fields
			if input_def.required:
				if field_description:
					# Required field with format description
					fields[name] = (py_type, Field(..., description=field_description))
				else:
					# Required field without format description
					fields[name] = (py_type, ...)
			else:
				if field_description:
					# Optional field with format description
					fields[name] = (py_type, Field(None, description=field_description))
				else:
					# Optional field without format description
					fields[name] = (py_type, None)

		# The raw ``create_model`` helper from Pydantic deliberately uses *dynamic*
		# signatures, which the static type checker cannot easily verify.  We cast
		# the **fields** mapping to **Any** to silence these warnings.
		return create_model(  # type: ignore[arg-type]
			f'{(self.schema.name or "Workflow").replace(" ", "_")}_Inputs',
			**_cast(Dict[str, Any], fields),
		)

	async def run_as_tool(self, prompt: str) -> str:
		"""Run the workflow with inputs parsed from a natural language prompt.

		Args:
			prompt: Natural language description of the task and inputs

		Returns:
			JSON string with workflow results
		"""
		if self.llm is None:
			raise ValueError('LLM is required for run_as_tool to parse inputs from prompt')

		# Parse inputs from prompt using LLM
		input_model = self._build_input_model()

		system_prompt = f"""You are a helpful assistant that extracts workflow input parameters from user prompts.
The workflow requires the following inputs:
{json.dumps(input_model.model_json_schema(), indent=2)}

Extract the values from the user's prompt and return them in the required format."""

		messages = [SystemMessage(content=system_prompt), UserMessage(content=prompt)]

		response = await self.llm.ainvoke(messages, output_format=input_model)
		inputs = response.completion.model_dump()

		# Run the workflow with parsed inputs
		result = await self.run(inputs=inputs, close_browser_at_end=True)

		# Return results as JSON
		output = {'success': True, 'steps_executed': len(result.step_results), 'inputs_used': inputs, 'context': self.context}

		return json.dumps(output, indent=2)

	async def run_with_no_ai(
		self,
		inputs: dict[str, Any] | None = None,
		close_browser_at_end: bool = True,
		cancel_event: asyncio.Event | None = None,
		output_model: type[T] | None = None,
	) -> WorkflowRunOutput[T]:
		"""Execute the workflow using semantic abstraction without any AI/LLM involvement.

		This method uses semantic mapping to convert visible text to deterministic selectors,
		avoiding expensive LLM calls and fragile CSS selectors.

		Args:
			inputs: Optional dictionary of workflow inputs
			close_browser_at_end: Whether to close the browser when done
			cancel_event: Optional event to signal cancellation
			output_model: Optional Pydantic model class to convert results to

		Returns:
			WorkflowRunOutput containing all step results
		"""
		from workflow_use.workflow.semantic_executor import SemanticWorkflowExecutor

		runtime_inputs = inputs or {}
		# 1. Validate inputs against definition
		self._validate_inputs(runtime_inputs)
		# 2. Initialize context with validated inputs
		self.context = runtime_inputs.copy()  # Start with a fresh context

		results: List[ActionResult | AgentHistoryList] = []

		await self.browser.start()
		semantic_executor = SemanticWorkflowExecutor(self.browser, page_extraction_llm=self.page_extraction_llm)

		try:
			for step_index, step_dict in enumerate(self.schema.steps):
				# Wait between steps (configurable) - same logic as run() method
				if step_index > 0:  # Don't wait before the first step
					# Get wait time from previous step's wait_time or use default
					# Use 'is not None' to allow wait_time=0 to skip the delay intentionally
					previous_step = self.schema.steps[step_index - 1]
					step_wait_time_value = getattr(previous_step, 'wait_time', None)
					wait_time = step_wait_time_value if step_wait_time_value is not None else self.step_wait_time
					await asyncio.sleep(wait_time)
					if wait_time > 0:
						logger.debug(f'Waited {wait_time}s between steps')

				# Check if cancellation was requested
				if cancel_event and cancel_event.is_set():
					logger.info('Cancellation requested - stopping workflow execution')
					break

				# Use description from the step dictionary
				step_description = step_dict.description or 'No description provided'
				logger.info(f'--- Running Step {step_index + 1}/{len(self.schema.steps)} -- {step_description} ---')

				# Resolve placeholders using the current context (works on the dictionary)
				step_resolved = self._resolve_placeholders(step_dict)

				# Only process deterministic steps (no agent steps)
				if step_resolved.type == 'agent':
					raise Exception(
						f'Agent steps are not supported in run_with_no_ai mode. Step {step_index + 1} is an agent step.'
					)

				# Execute step using semantic executor
				result = await semantic_executor.execute_step(step_resolved)

				results.append(result)
				# Persist outputs using the resolved step dictionary
				self._store_output(step_resolved, result)
				logger.info(f'--- Finished Step {step_index + 1} ---\n')

			# Convert results to output model if requested
			output_model_result: T | None = None
			if output_model:
				output_model_result = await self._convert_results_to_output_model(results, output_model)

		finally:
			# Clean-up browser after finishing workflow
			if close_browser_at_end:
				self.browser.browser_profile.keep_alive = False
				await self.browser.stop()

		return WorkflowRunOutput(step_results=results, output_model=output_model_result)
