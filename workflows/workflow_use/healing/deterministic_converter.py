"""
Deterministic converter that transforms browser-use agent history into semantic workflow steps
without relying on LLM for step creation. LLM is only used for variable identification.
"""

from typing import Any, Dict, List, Optional

from browser_use.agent.views import AgentHistoryList


class DeterministicWorkflowConverter:
	"""
	Converts browser-use agent actions to semantic workflow steps deterministically.

	This approach analyzes recorded browser actions directly and creates semantic steps
	programmatically, without relying on LLM for step creation. Only uses LLM for
	variable identification.
	"""

	def __init__(self):
		self.element_text_map: Dict[str, str] = {}  # Maps element hashes to visible text
		self.element_hash_map: Dict[int, str] = {}  # Maps element index to hash for selector population
		self.captured_element_text_map: Dict[int, Any] = {}  # Captured during agent execution

	def convert_history_to_steps(self, history_list: AgentHistoryList) -> List[Dict[str, Any]]:
		"""
		Convert browser-use agent history to semantic workflow steps deterministically.

		Args:
		    history_list: The recorded browser interactions from browser-use agent

		Returns:
		    List of workflow step dictionaries ready for WorkflowDefinitionSchema
		"""
		steps = []

		for history in history_list.history:
			if history.model_output is None:
				continue

			# Capture semantic context from the agent's reasoning
			# current_state is an AgentBrain object, extract the text from it
			current_state = getattr(history.model_output, 'current_state', None)
			reasoning_text = None
			if current_state:
				# AgentBrain has various fields, extract the most relevant one
				# Try memory first, then thought, then convert to string
				if hasattr(current_state, 'memory') and current_state.memory:
					reasoning_text = str(current_state.memory)
				elif hasattr(current_state, 'thought') and current_state.thought:
					reasoning_text = str(current_state.thought)
				elif hasattr(current_state, 'evaluation_previous_goal') and current_state.evaluation_previous_goal:
					reasoning_text = str(current_state.evaluation_previous_goal)
				else:
					reasoning_text = str(current_state)

			agent_context = {
				'reasoning': reasoning_text,
				'page_url': getattr(history.state, 'url', None),
				'page_title': getattr(history.state, 'title', None),
			}

			# Process each action in this history item
			for action in history.model_output.action:
				action_dict = action.model_dump()

				# Browser-use action format: {action_type: {params}}
				# Extract action type from dictionary keys (excluding 'type' if present)
				action_type = None
				action_params = {}

				for key, value in action_dict.items():
					if key != 'type' and isinstance(value, dict):
						action_type = key
						action_params = value
						break

				if not action_type:
					# Fallback to old format if present
					action_type = action_dict.get('type', '')
					action_params = action_dict

				# Debug: Log the action type and params
				print(f'🔍 Processing action type: "{action_type}"')
				print(f'   Action params: {action_params}')
				reasoning = agent_context.get('reasoning')
				if reasoning:
					# Truncate long reasoning text
					reasoning_preview = reasoning[:150] + '...' if len(reasoning) > 150 else reasoning
					print(f'   🧠 Agent reasoning: {reasoning_preview}')

				# Get interacted element data if available
				element_data = self._get_element_data(history, action_params)

				# Convert action to semantic step with context
				step = self._convert_action_to_step(action_type, action_params, element_data, agent_context)

				if step:
					print(f'   ✅ Converted to step: {step.get("type")}')
					steps.append(step)
				else:
					print('   ❌ Skipped (no step generated)')

		print(f'\n📊 Total steps generated: {len(steps)}')
		return steps

	def _get_element_data(self, history, action_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
		"""
		Extract element data from the DOM using the box overlay index.

		Browser-use creates overlay boxes on top of elements. The index refers to the box,
		not the actual element. We need to look at the DOM state to find the visible text.
		"""
		index = action_dict.get('index')
		if index is None:
			return None

		# Debug: Print available data in history.state
		print(f'   🔍 Looking for element with index {index}')

		# First, try to get from captured element map (captured during agent execution)
		if index in self.captured_element_text_map:
			element_info = self.captured_element_text_map[index]
			print(f'      ✅ Found element {index} in captured map!')
			print(f'         Element info: {element_info}')
			# Normalize and return
			normalized = self._normalize_element_data(element_info)
			if normalized:
				self.element_hash_map[index] = normalized['element_hash']
				return normalized

		# Print the full state dict to see what browser-use provides
		try:
			state_dict = history.state.to_dict()
			print(f'      State dict keys: {state_dict.keys()}')

			# Check if tabs have element information
			if 'tabs' in state_dict and state_dict['tabs']:
				first_tab = state_dict['tabs'][0]
				print(f'      First tab keys: {first_tab.keys()}')

				# Look for selector map or interactive elements
				if 'selector_map' in first_tab:
					print(f'      Found selector_map with {len(first_tab["selector_map"])} entries')
					# Check if our index is in the selector map
					if str(index) in first_tab['selector_map']:
						element_info = first_tab['selector_map'][str(index)]
						print(f'      ✅ Found element {index} in selector_map!')
						print(f'         Element info: {element_info}')
						# Normalize and return
						normalized = self._normalize_element_data(element_info)
						if normalized:
							self.element_hash_map[index] = normalized['element_hash']
							return normalized

				# Check for interactive_elements field
				if 'interactive_elements' in first_tab:
					elements = first_tab['interactive_elements']
					print(f'      Found interactive_elements with {len(elements)} entries')
					# Find element by index
					for elem in elements:
						if elem.get('index') == index or elem.get('highlight_index') == index:
							print(f'      ✅ Found element {index} in interactive_elements!')
							print(f'         Element: {elem}')
							# Normalize and return
							normalized = self._normalize_element_data(elem)
							if normalized:
								self.element_hash_map[index] = normalized['element_hash']
								return normalized
		except Exception as e:
			print(f'      Error accessing state dict: {e}')

		# Fallback to old method
		interacted_elements = history.state.interacted_element
		print(f'      Number of interacted elements: {len(interacted_elements)}')

		# Try to find by highlight_index (the box number)
		matching_element = None
		for i, element in enumerate(interacted_elements):
			if element:
				if hasattr(element, 'highlight_index') and element.highlight_index == index:
					matching_element = element
					print('      ✓ Found by highlight_index match')
					break

		if matching_element is None:
			print(f'   ⚠️  Could not find element with index {index} - returning None')
			return None

		# Normalize the element data
		normalized = self._normalize_element_data(matching_element)
		if normalized:
			self.element_hash_map[index] = normalized['element_hash']
			print(
				f'   📍 Found element: tag={normalized.get("node_name")}, '
				f'value="{normalized.get("node_value")[:50] if normalized.get("node_value") else ""}"'
			)
			print(f'      Attributes: {list(normalized.get("attributes", {}).keys())}')
			print(f'      Hash: {normalized["element_hash"]}')

		return normalized

	def _create_semantic_description(
		self, action_type: str, base_description: str, agent_context: Dict[str, Any], target_text: Optional[str] = None
	) -> str:
		"""
		Create a semantically rich description using agent reasoning and context.

		Args:
		    action_type: The type of action
		    base_description: The basic description
		    agent_context: Context from agent reasoning
		    target_text: Optional target text for the action

		Returns:
		    Enhanced description with semantic context
		"""
		reasoning = agent_context.get('reasoning') or ''
		page_title = agent_context.get('page_title') or ''

		# If we have agent reasoning, try to extract intent
		if reasoning and isinstance(reasoning, str):
			# Simple heuristic: extract action intent from reasoning
			reasoning_lower = reasoning.lower()

			# Look for intent keywords
			intent_map = {
				'click': ['click', 'select', 'choose', 'open'],
				'navigation': ['navigate', 'go to', 'visit', 'open'],
				'input': ['enter', 'type', 'input', 'fill'],
				'scroll': ['scroll', 'view more', 'see more'],
				'extract': ['extract', 'get', 'find', 'collect'],
			}

			# Find matching intent
			for intent_type, keywords in intent_map.items():
				if action_type in ['click', 'click_element'] and intent_type == 'click':
					for keyword in keywords:
						if keyword in reasoning_lower and target_text:
							# Try to find what they're clicking on
							if 'section' in reasoning_lower:
								return f"Click on '{target_text}' to access section"
							elif 'filing' in reasoning_lower or 'sec' in reasoning_lower:
								return f"Click on '{target_text}' (Filings section)"
							elif 'news' in reasoning_lower or 'press' in reasoning_lower:
								return f"Click on '{target_text}' (News/Press Releases)"
							elif 'event' in reasoning_lower or 'webcast' in reasoning_lower:
								return f"Click on '{target_text}' (Events/Webcasts)"
							elif 'presentation' in reasoning_lower:
								return f"Click on '{target_text}' (Presentations)"

		# Fallback to base description with page context
		if page_title and action_type in ['click', 'input']:
			return f'{base_description} (on {page_title})'

		return base_description

	def _normalize_element_data(self, raw_data: Any) -> Dict[str, Any]:
		"""
		Normalize element data from various browser-use formats to a consistent structure.
		"""
		import hashlib

		# If it's already a dict from selector_map or interactive_elements
		if isinstance(raw_data, dict):
			# Extract common fields with fallbacks
			result = {
				'node_name': raw_data.get('tag_name') or raw_data.get('node_name') or '',
				'node_value': raw_data.get('text') or raw_data.get('node_value') or '',
				'attributes': raw_data.get('attributes', {}),
				'xpath': raw_data.get('xpath') or raw_data.get('x_path') or '',
			}

			# Compute element hash if we have the data
			tag_name = result['node_name'].lower()
			# Use xpath or a combination of attributes as hash source
			hash_source = result['xpath'] or str(result['attributes'])
			element_hash = hashlib.sha256(f'{tag_name}_{hash_source}'.encode()).hexdigest()[:10]

			result['element_hash'] = element_hash
			result['element_object'] = raw_data  # Store raw for reference

			return result

		# If it's a DOM element object (fallback)
		if hasattr(raw_data, 'node_name'):
			tag_name = raw_data.node_name.lower() if hasattr(raw_data, 'node_name') else ''
			element_browser_hash = getattr(raw_data, 'element_hash', '')
			element_hash = hashlib.sha256(f'{tag_name}_{element_browser_hash}'.encode()).hexdigest()[:10]

			return {
				'node_name': getattr(raw_data, 'node_name', ''),
				'node_value': getattr(raw_data, 'node_value', ''),
				'attributes': getattr(raw_data, 'attributes', {}),
				'xpath': getattr(raw_data, 'x_path', ''),
				'element_hash': element_hash,
				'element_object': raw_data,
			}

		return None

	def _extract_target_text(self, element_data: Optional[Dict[str, Any]], action_dict: Dict[str, Any]) -> str:
		"""
		Extract the best target_text for semantic targeting from element data.

		Priority:
		1. Visible text content (node_value)
		2. aria-label attribute
		3. title attribute
		4. placeholder attribute
		5. alt attribute (for images)
		6. value attribute
		7. name attribute
		8. id attribute (last resort)
		9. href attribute (for anchor tags) - extract meaningful part
		10. Input text being entered (for input actions)
		11. Node name + xpath hint (absolute fallback)
		"""
		if not element_data:
			# For input actions, use the text being entered as fallback
			if action_dict.get('text'):
				return action_dict['text']
			return 'element'

		# Priority 1: Visible text content
		node_value = element_data.get('node_value', '').strip()
		if node_value:
			print(f'      ✓ Using node_value as target_text: "{node_value}"')
			return node_value

		# Priority 2-8: Check attributes in order
		attributes = element_data.get('attributes', {})
		for attr in ['aria-label', 'title', 'placeholder', 'alt', 'value', 'name', 'id']:
			if attr in attributes and attributes[attr]:
				text = str(attributes[attr]).strip()
				if text:
					print(f'      ✓ Using {attr} attribute as target_text: "{text}"')
					return text

		# Priority 9: For anchor tags, extract meaningful text from href
		node_name = element_data.get('node_name', '')
		if node_name == 'a' and 'href' in attributes:
			href = attributes['href']
			if isinstance(href, str):
				# Remove query params and anchors
				href = href.split('?')[0].split('#')[0]
				# Get the last path segment
				path_parts = href.rstrip('/').split('/')
				if path_parts:
					last_part = path_parts[-1]
					# Convert URL-friendly text to readable text
					# E.g., "sec-filings" -> "SEC Filings"
					# Skip generic terms
					skip_terms = ['www.edison.com', 'edison.com', 'investors', 'www', 'com', 'http:', 'https:']
					if last_part and last_part not in skip_terms:
						text = last_part.replace('-', ' ').replace('_', ' ').title()
						print(f'      ✓ Extracted from href as target_text: "{text}"')
						return text

		# Priority 10: For input actions, use the text being entered
		if action_dict.get('text'):
			text = action_dict['text']
			print(f'      ✓ Using input text as target_text: "{text}"')
			return text

		# Priority 11: Fallback - use node name as hint
		if node_name:
			print(f'      ⚠️  No good target text found, using node name: "{node_name}"')
			return f'{node_name} element'

		print('      ⚠️  No target text found at all')
		return 'element'

	def _convert_action_to_step(
		self,
		action_type: str,
		action_dict: Dict[str, Any],
		element_data: Optional[Dict[str, Any]],
		agent_context: Optional[Dict[str, Any]] = None,
	) -> Optional[Dict[str, Any]]:
		"""
		Convert a single browser-use action to a semantic workflow step with context.

		Args:
		    action_type: The type of action (e.g., 'click', 'navigate')
		    action_dict: The action parameters
		    element_data: Element data extracted from the DOM
		    agent_context: Semantic context from the agent's reasoning

		Mapping (browser-use action names):
		- navigate → navigation step
		- input_text → input step with target_text
		- click → click step with target_text
		- send_keys → keypress step
		- extract_content → extract_page_content step
		- scroll → scroll step
		"""
		agent_context = agent_context or {}

		# Navigation actions
		if action_type in ['navigate', 'go_to_url']:
			url = action_dict.get('url', '')
			step = {
				'type': 'navigation',
				'url': url,
				'description': f'Navigate to {url}',
			}

			# Add semantic metadata for navigation
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']

			return step

		# Input text actions
		elif action_type == 'input_text':
			target_text = self._extract_target_text(element_data, action_dict)
			# Ensure target_text is never empty
			if not target_text:
				target_text = 'input field'

			step = {
				'type': 'input',
				'target_text': target_text,
				'value': action_dict.get('text', ''),
				'description': f'Enter text into {target_text}',
			}

			# Add element hash for selector population
			if element_data and element_data.get('element_hash'):
				step['elementHash'] = element_data['element_hash']

			# Add semantic metadata
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']
			if agent_context.get('page_url'):
				step['page_context_url'] = agent_context['page_url']

			return step

		# Click actions (browser-use uses 'click', not 'click_element')
		elif action_type in ['click', 'click_element']:
			target_text = self._extract_target_text(element_data, action_dict)
			# Ensure target_text is never empty
			if not target_text:
				target_text = 'element'

			# Create semantic description
			base_description = f'Click on {target_text}'
			description = self._create_semantic_description(action_type, base_description, agent_context, target_text)

			step = {
				'type': 'click',
				'target_text': target_text,
				'description': description,
			}

			# Add element hash for selector population
			if element_data and element_data.get('element_hash'):
				step['elementHash'] = element_data['element_hash']

			# Add semantic metadata (optional fields that provide context)
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']
			if agent_context.get('page_url'):
				step['page_context_url'] = agent_context['page_url']
			if agent_context.get('page_title'):
				step['page_context_title'] = agent_context['page_title']

			return step

		# Keyboard actions
		elif action_type == 'send_keys':
			# For send_keys, we might not have a specific element
			# If it's a simple key like "Enter", create a keypress step
			keys = action_dict.get('keys', '')

			# Try to get target from last interacted element if available
			target_text = self._extract_target_text(element_data, action_dict)
			# Ensure target_text is never empty
			if not target_text:
				target_text = 'page'

			step = {
				'type': 'key_press',
				'key': keys,
				'target_text': target_text,
				'description': f'Press {keys} key',
			}

			# Add element hash for selector population
			if element_data and element_data.get('element_hash'):
				step['elementHash'] = element_data['element_hash']

			return step

		# Extract content actions
		elif action_type in ['extract_page_content', 'extract_content']:
			# Browser-use may use different field names for extraction goal
			goal = action_dict.get('value') or action_dict.get('goal') or action_dict.get('content') or 'page content'
			return {
				'type': 'extract_page_content',
				'goal': goal,
				'description': f'Extract: {goal}',
			}

		# Scroll actions
		elif action_type == 'scroll':
			# Convert browser-use scroll (down: bool, pages: float) to workflow scroll (scrollX, scrollY: int)
			# Estimate 800 pixels per page
			down = action_dict.get('down', True)
			pages = action_dict.get('pages', 1.0)
			pixels = int(pages * 800)

			step = {
				'type': 'scroll',
				'scrollX': 0,
				'scrollY': pixels if down else -pixels,
				'description': f'Scroll {"down" if down else "up"} {pages} pages',
			}

			# Add semantic metadata
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']
			if agent_context.get('page_url'):
				step['page_context_url'] = agent_context['page_url']

			return step

		# Dropdown actions - convert to click for now
		elif action_type == 'select_dropdown_option':
			target_text = action_dict.get('text', '')
			return {
				'type': 'click',
				'target_text': target_text,
				'description': f'Select dropdown option: {target_text}',
			}

		# Navigation actions
		elif action_type == 'go_back':
			step = {
				'type': 'go_back',
				'description': 'Navigate back to previous page',
			}

			# Add semantic metadata
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']
			if agent_context.get('page_url'):
				step['page_context_url'] = agent_context['page_url']

			return step

		elif action_type == 'go_forward':
			step = {
				'type': 'go_forward',
				'description': 'Navigate forward to next page',
			}

			# Add semantic metadata
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']
			if agent_context.get('page_url'):
				step['page_context_url'] = agent_context['page_url']

			return step

		# Actions we skip or handle differently
		elif action_type in ['done', 'switch_tab', 'close_tab', 'write_file', 'replace_file', 'read_file', 'search_google']:
			return None  # These don't translate to workflow steps

		else:
			# Unknown action type - log a warning (only if not empty)
			if action_type:
				print(f'⚠️  Unknown action type: {action_type} - skipping')
			return None

	def create_workflow_definition(
		self,
		name: str,
		description: str,
		steps: List[Dict[str, Any]],
		input_schema: Optional[List[Dict[str, Any]]] = None,
		version: str = '1.0.0',
	) -> Dict[str, Any]:
		"""
		Create a complete workflow definition from converted steps.

		Args:
		    name: Workflow name
		    description: Workflow description
		    steps: List of converted step dictionaries
		    input_schema: Optional list of input variable definitions
		    version: Workflow version (default: '1.0.0')

		Returns:
		    Complete workflow definition dictionary
		"""
		return {
			'name': name,
			'description': description,
			'version': version,
			'input_schema': input_schema or [],
			'steps': steps,
		}
