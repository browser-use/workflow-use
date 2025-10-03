from __future__ import annotations

import asyncio
import json
import json as _json
import logging
from pathlib import Path
from typing import Any, Dict, List, TypeVar
from typing import cast as _cast

from browser_use import Agent, Browser
from browser_use.agent.views import ActionResult, AgentHistoryList
from browser_use.llm.base import BaseChatModel
from browser_use.llm import SystemMessage, UserMessage
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
	) -> None:
		"""Initialize a new Workflow instance from a schema object.

		Args:
			workflow_schema: The parsed workflow definition schema.
			controller: Optional WorkflowController instance to handle action execution
			browser: Optional Browser instance to use for browser automation
			llm: Optional language model for fallback agent functionality
			fallback_to_agent: Whether to fall back to agent-based execution on step failure
			use_cloud: Whether to use browser-use cloud browser service instead of local browser

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
	) -> Workflow:
		"""Load a workflow from a file."""
		with open(file_path, 'r', encoding='utf-8') as f:
			data = _json.load(f)
		workflow_schema = WorkflowDefinitionSchema(**data)
		return Workflow(
			workflow_schema=workflow_schema,
			controller=controller,
			browser=browser,
			llm=llm,
			page_extraction_llm=page_extraction_llm,
			use_cloud=use_cloud,
		)

	# --- Runners ---
	async def _run_deterministic_step(self, step: DeterministicWorkflowStep, step_index: int) -> ActionResult:
		"""Execute a deterministic (controller) action based on step dictionary."""
		# Assumes WorkflowStep for deterministic type has 'action' and 'params' keys
		action_name: str = step.type  # Expect 'action' key for deterministic steps
		params: Dict[str, Any] = step.model_dump()  # Use params if present

		ActionModel = self.controller.registry.create_action_model(include_actions=[action_name])
		# Pass the params dictionary directly
		action_model = ActionModel(**{action_name: params})

		try:
			result = await self.controller.act(action_model, self.browser, page_extraction_llm=self.page_extraction_llm)
		except Exception as e:
			raise RuntimeError(f"Deterministic action '{action_name}' failed: {str(e)}")

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
			update_dict = {}
			model_changed = False
			for field_name in data.model_fields:  # Iterate using model_fields keys
				original_value = getattr(data, field_name)
				resolved_value = self._resolve_placeholders(original_value)
				if resolved_value is not original_value:
					model_changed = True
				update_dict[field_name] = resolved_value

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

			try:
				# Use action key from step dictionary
				action_name = step_resolved.type or '[No action specified]'
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

		await self.browser.start()
		try:
			for step_index, step_dict in enumerate(self.schema.steps):  # self.steps now holds dictionaries
				await asyncio.sleep(0.1)

				# Check if cancellation was requested
				if cancel_event and cancel_event.is_set():
					logger.info('Cancellation requested - stopping workflow execution')
					break

				# Use description from the step dictionary
				step_description = step_dict.description or 'No description provided'
				logger.info(f'--- Running Step {step_index + 1}/{len(self.schema.steps)} -- {step_description} ---')
				# Resolve placeholders using the current context (works on the dictionary)
				step_resolved = self._resolve_placeholders(step_dict)

				# Execute step using the unified _execute_step method
				result = await self._execute_step(step_index, step_resolved)

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
			raise ValueError("LLM is required for run_as_tool to parse inputs from prompt")

		# Parse inputs from prompt using LLM
		input_model = self._build_input_model()

		system_prompt = f"""You are a helpful assistant that extracts workflow input parameters from user prompts.
The workflow requires the following inputs:
{json.dumps(input_model.model_json_schema(), indent=2)}

Extract the values from the user's prompt and return them in the required format."""

		messages = [
			SystemMessage(content=system_prompt),
			UserMessage(content=prompt)
		]

		response = await self.llm.ainvoke(messages, output_format=input_model)
		inputs = response.completion.model_dump()

		# Run the workflow with parsed inputs
		result = await self.run(inputs=inputs, close_browser_at_end=True)

		# Return results as JSON
		output = {
			"success": True,
			"steps_executed": len(result.step_results),
			"inputs_used": inputs,
			"context": self.context
		}

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
				await asyncio.sleep(0.1)

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
					raise Exception(f"Agent steps are not supported in run_with_no_ai mode. Step {step_index + 1} is an agent step.")

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
