import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Union

import aiofiles
from browser_use import Agent, AgentHistoryList, Browser
from browser_use.dom.views import DOMInteractedElement
from browser_use.llm import SystemMessage, UserMessage
from browser_use.llm.base import BaseChatModel, BaseMessage

from workflow_use.builder.service import BuilderService
from workflow_use.healing.deterministic_converter import DeterministicWorkflowConverter
from workflow_use.healing.selector_generator import SelectorGenerator
from workflow_use.healing.validator import WorkflowValidator
from workflow_use.healing.variable_extractor import VariableExtractor
from workflow_use.healing.views import ParsedAgentStep, SimpleDomElement, SimpleResult
from workflow_use.schema.views import WorkflowDefinitionSchema

# Get the absolute path to the prompts directory
_PROMPTS_DIR = Path(__file__).parent / 'prompts'


class HealingService:
	def __init__(
		self,
		llm: BaseChatModel,
		enable_variable_extraction: bool = True,
		use_deterministic_conversion: bool = False,
		enable_ai_validation: bool = False,
	):
		self.llm = llm
		self.enable_variable_extraction = enable_variable_extraction
		self.use_deterministic_conversion = use_deterministic_conversion
		self.enable_ai_validation = enable_ai_validation
		self.variable_extractor = VariableExtractor(llm=llm) if enable_variable_extraction else None
		self.deterministic_converter = DeterministicWorkflowConverter(llm=llm) if use_deterministic_conversion else None
		self.selector_generator = SelectorGenerator()  # Initialize multi-strategy selector generator
		# Note: validator will be initialized with extraction_llm in generate_workflow_from_prompt
		self.validator = None

		self.interacted_elements_hash_map: dict[str, DOMInteractedElement] = {}

	def _remove_none_fields_from_dict(self, d: dict) -> dict:
		return {k: v for k, v in d.items() if v is not None}

	def _history_to_workflow_definition(self, history_list: AgentHistoryList) -> list[UserMessage]:
		# history

		messages: list[UserMessage] = []

		for history in history_list.history:
			if history.model_output is None:
				continue

			interacted_elements: list[SimpleDomElement] = []
			for element in history.state.interacted_element:
				if element is None:
					continue

				# Get tag_name from node_name (lowercased)
				tag_name = element.node_name.lower() if hasattr(element, 'node_name') else ''

				# hash element by hashing the node_name + element_hash
				element_hash = hashlib.sha256(f'{tag_name}_{element.element_hash}'.encode()).hexdigest()[:10]

				if element_hash not in self.interacted_elements_hash_map:
					self.interacted_elements_hash_map[element_hash] = element

				interacted_elements.append(
					SimpleDomElement(
						tag_name=tag_name,
						highlight_index=getattr(element, 'highlight_index', 0),
						shadow_root=getattr(element, 'shadow_root', False),
						element_hash=element_hash,
					)
				)

			screenshot = history.state.get_screenshot() if hasattr(history.state, 'get_screenshot') else None

			# Capture step duration if available
			duration_seconds = None
			if history.metadata and hasattr(history.metadata, 'duration_seconds'):
				duration_seconds = history.metadata.duration_seconds

			parsed_step = ParsedAgentStep(
				url=history.state.url,
				title=history.state.title,
				agent_brain=history.model_output.current_state,
				actions=[self._remove_none_fields_from_dict(action.model_dump()) for action in history.model_output.action],
				results=[
					SimpleResult(
						success=result.success or False,
						extracted_content=result.extracted_content,
					)
					for result in history.result
				],
				interacted_elements=interacted_elements,
				duration_seconds=duration_seconds,
			)

			parsed_step_json = json.dumps(parsed_step.model_dump(exclude_none=True))
			content_blocks: List[Union[str, Dict[str, Any]]] = []

			text_block: Dict[str, Any] = {'type': 'text', 'text': parsed_step_json}
			content_blocks.append(text_block)

			if screenshot:
				# Assuming screenshot is a base64 encoded string.
				# Adjust mime type if necessary (e.g., image/png)
				image_block: Dict[str, Any] = {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{screenshot}'}}
				content_blocks.append(image_block)

			messages.append(UserMessage(content=content_blocks))

		return messages

	def _validate_workflow_quality(self, workflow_definition: WorkflowDefinitionSchema) -> None:
		"""Validate the generated workflow and warn about quality issues."""
		agent_steps = []
		for i, step in enumerate(workflow_definition.steps):
			if hasattr(step, 'type') and step.type == 'agent':
				agent_steps.append((i, step))

		if agent_steps:
			print(f'\n⚠️  WARNING: Generated workflow contains {len(agent_steps)} agent step(s)!')
			print('   Agent steps are 10-30x slower and cost money per execution.')
			print('   Consider these alternatives:\n')
			for i, step in agent_steps:
				task = getattr(step, 'task', 'Unknown task')
				print(f'   Step {i + 1}: {task}')

				# Suggest semantic alternatives
				if 'search' in task.lower() or 'input' in task.lower():
					print("     → Suggestion: Use 'input' + 'keypress' steps instead")
				elif 'click' in task.lower():
					print("     → Suggestion: Use 'click' step with 'target_text' instead")
				print()

	def _populate_selector_fields(self, workflow_definition: WorkflowDefinitionSchema) -> WorkflowDefinitionSchema:
		"""
		DISABLED: We no longer populate xpath/cssSelector fields to rely purely on semantic matching.
		This method is kept for backward compatibility but doesn't modify the workflow.
		"""
		print('\n🔧 Skipping selector field population - using pure semantic matching')
		print(f'   Available element hashes in map: {len(self.interacted_elements_hash_map)}')

		# Just return the workflow as-is without populating xpath/cssSelector
		# The semantic executor will use target_text for element matching
		return workflow_definition

	async def create_workflow_definition(
		self, task: str, history_list: AgentHistoryList, extract_variables: bool = True
	) -> WorkflowDefinitionSchema:
		# Load prompt using absolute path
		prompt_file = _PROMPTS_DIR / 'workflow_creation_prompt.md'
		async with aiofiles.open(prompt_file, mode='r') as f:
			prompt_content = await f.read()

		prompt_content = prompt_content.format(goal=task, actions=BuilderService._get_available_actions_markdown())

		system_message = SystemMessage(content=prompt_content)
		human_messages = self._history_to_workflow_definition(history_list)

		all_messages: Sequence[BaseMessage] = [system_message] + human_messages

		# Use browser-use's output_format parameter for structured output
		try:
			response = await self.llm.ainvoke(all_messages, output_format=WorkflowDefinitionSchema)
			workflow_definition: WorkflowDefinitionSchema = response.completion  # type: ignore
		except Exception as e:
			print('ERROR: Failed to generate structured workflow definition')
			print(f'Error details: {e}')
			# Try to get the raw response
			try:
				raw_response = await self.llm.ainvoke(all_messages)
				print('\nRaw LLM response:')
				print(raw_response)
			except Exception:
				pass
			raise

		workflow_definition = self._populate_selector_fields(workflow_definition)

		# Validate workflow quality - warn about agent steps
		self._validate_workflow_quality(workflow_definition)

		# Post-process to extract additional variables if enabled
		if extract_variables and self.variable_extractor:
			# The LLM already identified variables in the initial generation
			# But we can optionally run a second pass for validation/enhancement
			try:
				print('\nAnalyzing workflow for additional variable opportunities...')
				result = await self.variable_extractor.suggest_variables(workflow_definition)
				if result.suggestions:
					print(f'Found {len(result.suggestions)} variable suggestions:')
					for suggestion in result.suggestions:
						print(f'  - {suggestion.name} ({suggestion.type}): {suggestion.reasoning}')
					# Note: We don't auto-apply these suggestions, just log them
					# The initial LLM generation should have already identified the main variables
			except Exception as e:
				print(f'Warning: Variable extraction analysis failed: {e}')
				# Continue with the original workflow

		return workflow_definition

	async def _create_workflow_deterministically(
		self, task: str, history_list: AgentHistoryList, extract_variables: bool = True
	) -> WorkflowDefinitionSchema:
		"""
		Create workflow definition using deterministic conversion (no LLM for step creation).

		This method converts browser actions directly to semantic steps without LLM inference,
		resulting in faster generation and guaranteed semantic steps (no agent steps).
		"""
		if not self.deterministic_converter:
			raise ValueError('Deterministic converter not initialized. Set use_deterministic_conversion=True in constructor.')

		print('🔧 Using deterministic workflow conversion (no LLM for step creation)')

		# Convert history to steps deterministically
		steps = self.deterministic_converter.convert_history_to_steps(history_list)

		# Transfer element objects from deterministic converter to healing service's map
		# This allows _populate_selector_fields to populate cssSelector
		# Use the captured element map from the CapturingController instead of history
		captured_map = getattr(self, 'captured_element_text_map', {})

		for history in history_list.history:
			if history.model_output is None:
				continue
			for action in history.model_output.action:
				action_dict = action.model_dump()
				# Extract index from browser-use action format
				for key, value in action_dict.items():
					if isinstance(value, dict) and 'index' in value:
						index = value['index']
						if index in self.deterministic_converter.element_hash_map:
							element_hash = self.deterministic_converter.element_hash_map[index]

							# First try: Use captured element data (more reliable)
							if index in captured_map:
								# Create a mock DOMInteractedElement from captured data
								captured_data = captured_map[index]

								# Create a simple object with the needed attributes
								class MockElement:
									def __init__(self, data):
										self.node_name = data.get('tag_name', '').upper()
										self.css_selector = data.get('css_selector', '')
										self.x_path = data.get('xpath', '')
										self.xpath = data.get('xpath', '')  # Support both attribute names

								mock_element = MockElement(captured_data)
								self.interacted_elements_hash_map[element_hash] = mock_element
								print(f'   📍 Populated selector for hash {element_hash} from captured data (index {index})')
								print(f'      CSS: {mock_element.css_selector}')
								print(f'      XPath: {mock_element.x_path}')
								continue

							# Fallback: Use history.state.interacted_element
							for element in history.state.interacted_element:
								if element and hasattr(element, 'highlight_index') and element.highlight_index == index:
									self.interacted_elements_hash_map[element_hash] = element
									print(f'   📍 Populated selector for hash {element_hash} from history (index {index})')
									break

		# Create workflow definition dict
		workflow_dict = self.deterministic_converter.create_workflow_definition(
			name=task, description=f'Workflow for: {task}', steps=steps, input_schema=[]
		)

		# Convert to WorkflowDefinitionSchema
		workflow_definition = WorkflowDefinitionSchema(**workflow_dict)

		workflow_definition = self._populate_selector_fields(workflow_definition)

		# Validate workflow quality - should have zero agent steps
		self._validate_workflow_quality(workflow_definition)

		# Post-process to extract variables if enabled
		if extract_variables and self.variable_extractor:
			try:
				print('\nAnalyzing workflow for variable opportunities...')
				result = await self.variable_extractor.suggest_variables(workflow_definition)
				if result.suggestions:
					print(f'Found {len(result.suggestions)} variable suggestions:')
					for suggestion in result.suggestions:
						print(f'  - {suggestion.name} ({suggestion.type}): {suggestion.reasoning}')
			except Exception as e:
				print(f'Warning: Variable extraction analysis failed: {e}')

		return workflow_definition

	# Generate workflow from prompt
	async def generate_workflow_from_prompt(
		self, prompt: str, agent_llm: BaseChatModel, extraction_llm: BaseChatModel, use_cloud: bool = False
	) -> WorkflowDefinitionSchema:
		"""
		Generate a workflow definition from a prompt by:
		1. Running a browser agent to explore and complete the task
		2. Converting the agent history into a workflow definition
		"""

		browser = Browser(use_cloud=use_cloud)

		# Create a shared map to capture element text during agent execution
		element_text_map = {}  # Maps index -> {'text': str, 'tag': str, 'xpath': str, etc.}

		# Create a custom controller that captures element mappings
		from browser_use import Controller

		class CapturingController(Controller):
			"""Controller that captures element text mapping during execution"""

			def __init__(self, selector_generator: SelectorGenerator):
				super().__init__()
				self.selector_generator = selector_generator

			async def act(self, action, browser_session, *args, **kwargs):
				# Get the selector map before action
				try:
					selector_map = await browser_session.get_selector_map()

					if selector_map:
						print(f'📋 Captured {len(selector_map)} elements from selector_map')
						# selector_map is a dict: {index: DOMInteractedElement}
						# We need to extract text/attributes from each element
						debug_count = 0
						for index, dom_element in selector_map.items():
							# DEBUG: Print all fields for first 3 elements to see what's available
							if debug_count < 3:
								print(f'\n🔍 DEBUG - Element {index}:')
								print(f'   Type: {type(dom_element)}')
								if isinstance(dom_element, dict):
									print(f'   Dict keys: {list(dom_element.keys())}')
									print(f'   Content: {dom_element}')
								elif hasattr(dom_element, '__dict__'):
									print(f'   Available fields: {list(dom_element.__dict__.keys())}')
									print(f'   Values: {dom_element.__dict__}')
								else:
									attrs = [attr for attr in dir(dom_element) if not attr.startswith('_')]
									print(f'   Dir (non-private): {attrs}')
									# Print values of key attributes
									for attr in ['text', 'inner_text', 'node_value', 'node_name', 'attributes']:
										if hasattr(dom_element, attr):
											val = getattr(dom_element, attr, None)
											print(f'   {attr}: {val}')
								debug_count += 1

							# Handle dict format (from selector_map)
							if isinstance(dom_element, dict):
								text = dom_element.get('text', '')
								tag_name = dom_element.get('tag_name', '')
								attrs = dom_element.get('attributes', {})
							else:
								# Extract tag name first
								tag_name = (
									getattr(dom_element, 'node_name', '').lower() if hasattr(dom_element, 'node_name') else ''
								)
								attrs = getattr(dom_element, 'attributes', {})

								# Extract text by trying multiple field names
								text = ''
								for text_field in ['text', 'inner_text', 'node_value', 'textContent', 'innerText']:
									if hasattr(dom_element, text_field):
										potential_text = getattr(dom_element, text_field, '')
										if potential_text and potential_text.strip():
											# IMPORTANT: Skip JavaScript href text (same filter as in deterministic_converter.py)
											# browser-use sometimes provides JavaScript href as 'text' for anchor tags
											if tag_name == 'a' and potential_text.lower().startswith('javascript:'):
												continue
											text = potential_text
											break

							# Normalize text (strip whitespace)
							text = text.strip() if text else ''

							# For interactive elements (links, buttons), prioritize semantic attributes
							# over potentially meaningless text content
							if tag_name in ['a', 'button'] and isinstance(attrs, dict):
								# Check if current text is very short or looks like an ID/hash
								is_poor_text = (
									not text
									or len(text) <= 2  # Single char or very short
									or text.lower() in ['link', 'button', 'click', 'here']  # Generic text
									or (len(text) == 8 and text.isalnum())  # Looks like an ID (e.g., "nboo9eyy")
								)

								if is_poor_text:
									# Try semantic attributes first for better context
									semantic_text = (
										attrs.get('aria-label')
										or attrs.get('title')
										or attrs.get('alt')
										or attrs.get('placeholder')
										or attrs.get('value')
										or ''
									)

									if semantic_text:
										text = semantic_text
										print(f'   📎 Using semantic attribute for better text: "{text}"')
									# For anchor tags, try ID/class-based inference for common button patterns
									elif tag_name == 'a':
										element_id = attrs.get('id', '')
										element_class = attrs.get('class', '')

										# Check for common button patterns in ID/class
										id_lower = element_id.lower() if element_id else ''
										class_lower = element_class.lower() if element_class else ''

										# Common search/submit button patterns
										if 'search' in id_lower or 'search' in class_lower:
											text = 'Search'
											print(f'   📎 Inferred "Search" from ID/class: {element_id or element_class}')
										elif 'submit' in id_lower or 'submit' in class_lower:
											text = 'Submit'
											print(f'   📎 Inferred "Submit" from ID/class: {element_id or element_class}')
										elif 'action' in id_lower or 'action' in class_lower:
											# cmdAction, btnAction, etc. in forms usually means Submit/Search
											if 'sqlviewpro' in id_lower or 'parameter' in id_lower:
												text = 'Search'
												print(f'   📎 Inferred "Search" from form action button: {element_id}')
											else:
												text = 'Submit'
												print(f'   📎 Inferred "Submit" from action button: {element_id}')
										# If still no text after ID/class inference, try href extraction
										elif 'href' in attrs:
											href = attrs['href']
											# Skip JavaScript hrefs - they don't have meaningful text to extract
											if isinstance(href, str) and not href.lower().startswith('javascript:'):
												# Extract the last meaningful part of the URL path
												# E.g., "https://newsroom.edison.com/releases" -> "releases"
												# Remove query params and anchors
												href = href.split('?')[0].split('#')[0]
												# Get the last path segment
												path_parts = href.rstrip('/').split('/')
												if path_parts:
													last_part = path_parts[-1]
													# Only use if it looks like readable text
													# Avoid random IDs like "nboo9eyy" (all lowercase alphanumeric with no separators)
													if last_part and last_part not in [
														'www.edison.com',
														'edison.com',
														'investors',
													]:
														# Check if it has word separators (hyphens, underscores)
														if '-' in last_part or '_' in last_part:
															text = last_part.replace('-', ' ').replace('_', ' ').title()
															print(f'   📎 Extracted from href: "{text}"')
														# Fallback: use clean slugs without separators (e.g., "login", "dashboard")
														# Only if they're reasonable length and look like words (not random IDs)
														elif len(last_part) >= 3 and len(last_part) <= 20 and last_part.isalpha():
															text = last_part.title()
															print(f'   📎 Extracted clean slug from href: "{text}"')

							# Final fallback for any element (not anchor/button): if still no text, try attributes
							elif not text:
								if isinstance(attrs, dict):
									# Try common text attributes
									text = (
										attrs.get('aria-label')
										or attrs.get('title')
										or attrs.get('alt')
										or attrs.get('placeholder')
										or attrs.get('value')
										or ''
									)
									# Note: ID/class inference for anchor tags is now handled above in the anchor/button block

							# Create a simplified dict with the data we need
							# Handle both dict and object formats
							if isinstance(dom_element, dict):
								element_data = {
									'index': index,
									'tag_name': tag_name or dom_element.get('tag_name', ''),
									'text': text,
									'xpath': dom_element.get('xpath', '') or dom_element.get('x_path', ''),
									'css_selector': dom_element.get('css_selector', ''),
									'attributes': attrs,
								}
							else:
								element_data = {
									'index': index,
									'tag_name': tag_name,
									'text': text,
									'xpath': getattr(dom_element, 'x_path', '') or getattr(dom_element, 'xpath', ''),
									'css_selector': getattr(dom_element, 'css_selector', ''),
									'attributes': attrs,
								}

							# Generate multiple selector strategies for robust element finding
							try:
								strategies = self.selector_generator.generate_strategies_dict(element_data)
								element_data['selector_strategies'] = strategies
							except Exception as e:
								print(f'   ⚠️  Warning: Failed to generate selector strategies: {e}')
								element_data['selector_strategies'] = []

							# Store in the shared map
							element_text_map[index] = element_data

							# Show first few captures for debugging
							if len(element_text_map) <= 5:
								text_preview = element_data['text'][:50] if element_data['text'] else '(no text)'
								print(f'   Element {index} ({element_data["tag_name"]}): {text_preview}')

				except Exception as e:
					print(f'⚠️  Warning: Failed to capture elements before action: {e}')

				# Execute the actual action
				result = await super().act(action, browser_session, *args, **kwargs)
				return result

		# Enhance the prompt to ensure agent mentions visible text of elements in a structured format
		enhanced_prompt = f"""{prompt}

CRITICAL WORKFLOW GENERATION REQUIREMENTS:
For EVERY action you take, you MUST include this structured tag in your reasoning:

Format: [ELEMENT: "exact visible text"]

Examples:
- "I will input 'John' [ELEMENT: "First Name"] into the form"
- "I will input 'Doe' [ELEMENT: "Last Name"] into the form"
- "I will click [ELEMENT: "Search"] to submit the form"
- "I will click [ELEMENT: "License Number"] to view details"
- "I will select [ELEMENT: "Country"] from the dropdown"

The [ELEMENT: "..."] tag must contain the EXACT visible text of the button, label, link, or field you're interacting with.
This structured format is critical for generating a reusable workflow."""

		agent = Agent(
			task=enhanced_prompt,
			browser_session=browser,
			llm=agent_llm,
			page_extraction_llm=extraction_llm,
			controller=CapturingController(self.selector_generator),  # Pass selector_generator to controller
			enable_memory=False,
			use_vision=True,
			max_failures=10,
		)

		# Store the element map for later use
		self.captured_element_text_map = element_text_map

		# Run the agent to get history
		print('🎬 Starting agent with element capture enabled...')
		history = await agent.run()
		print(f'✅ Agent completed. Captured {len(element_text_map)} element mappings total.')

		# Store the history so it can be accessed externally (for result caching)
		self._agent_history = history

		# Create workflow definition from the history
		# Route to deterministic or LLM-based conversion based on flag
		if self.use_deterministic_conversion:
			# Pass the captured element map to the deterministic converter
			self.deterministic_converter.captured_element_text_map = element_text_map
			workflow_definition = await self._create_workflow_deterministically(
				prompt, history, extract_variables=self.enable_variable_extraction
			)
		else:
			workflow_definition = await self.create_workflow_definition(
				prompt, history, extract_variables=self.enable_variable_extraction
			)

		# Apply AI validation and correction if enabled
		if self.enable_ai_validation:
			# Initialize validator with extraction_llm (same as used for page extraction)
			# This is more reliable than the main agent LLM
			if not self.validator:
				self.validator = WorkflowValidator(llm=extraction_llm)

			print('\n🔍 Running AI validation on generated workflow...')
			try:
				validation_result = await self.validator.validate_workflow(workflow=workflow_definition, original_task=prompt)

				# Print validation report
				self.validator.print_validation_report(validation_result)

				# Apply corrections if found
				if validation_result.corrected_workflow:
					print('\n✨ Applying AI corrections to workflow...')
					workflow_definition = validation_result.corrected_workflow
					print('✅ Workflow has been corrected!')
				elif validation_result.issues:
					print('\n⚠️  Issues found but no corrections were applied')
				else:
					print('\n✅ Validation passed - no issues found!')
			except Exception as e:
				print(f'\n⚠️  Validation failed: {e}')
				print('Continuing with original workflow...')

		return workflow_definition
