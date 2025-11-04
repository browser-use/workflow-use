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

	def __init__(self, llm=None):
		self.llm = llm
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

			# Capture step duration if available
			step_duration = None
			if history.metadata and hasattr(history.metadata, 'duration_seconds'):
				step_duration = history.metadata.duration_seconds

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

				# Convert action to semantic step with context and duration
				step = self._convert_action_to_step(action_type, action_params, element_data, agent_context, step_duration)

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
			# Extract tag name first
			tag_name = raw_data.get('tag_name') or raw_data.get('node_name') or ''

			# Extract text value from multiple possible fields, filtering out browser-use bugs
			text_value = ''
			for text_field in ['text', 'inner_text', 'textContent', 'innerText', 'node_value']:
				potential_text = raw_data.get(text_field, '').strip()
				if potential_text:
					# IMPORTANT: browser-use sometimes provides JavaScript href as 'text' for anchor tags
					# Skip this and try other fields (case-insensitive check)
					if tag_name == 'a' and potential_text.lower().startswith('javascript:'):
						continue
					text_value = potential_text
					break

			# Extract common fields with fallbacks
			result = {
				'node_name': tag_name,
				'node_value': text_value,
				'attributes': raw_data.get('attributes', {}),
				'xpath': raw_data.get('xpath') or raw_data.get('x_path') or '',
			}

			# IMPORTANT: Preserve selector_strategies for semantic/deterministic element finding
			if 'selector_strategies' in raw_data:
				result['selector_strategies'] = raw_data['selector_strategies']

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

	def _extract_target_text(
		self, element_data: Optional[Dict[str, Any]], action_dict: Dict[str, Any], agent_context: Optional[Dict[str, Any]] = None
	) -> str:
		"""
		Extract the best target_text for semantic targeting from element data.

		Priority:
		1. Visible text content (node_value)
		2. aria-label attribute
		3. placeholder attribute (for input fields)
		4. title attribute
		5. alt attribute (for images)
		6. name attribute (if human-readable, not technical ID)
		7. id attribute (only if human-readable, not technical ID)
		8. href attribute (for anchor tags) - extract meaningful part
		9. Input text being entered (for input actions)
		10. Node name + xpath hint (absolute fallback)
		"""
		if not element_data:
			# For input actions, use the text being entered as fallback
			if action_dict.get('text'):
				return action_dict['text']
			return 'element'

		# Priority 1: Visible text content (but NOT for input fields - they don't have meaningful text content)
		node_name = element_data.get('node_name', '').lower()
		node_value = element_data.get('node_value', '').strip()

		# Skip node_value for input fields (they don't have text content, only values)
		if node_value and node_name not in ['input', 'textarea', 'select']:
			print(f'      ✓ Using node_value as target_text: "{node_value}"')
			return node_value

		# Priority 2-5: Check high-value attributes in order
		attributes = element_data.get('attributes', {})
		for attr in ['aria-label', 'placeholder', 'title', 'alt']:
			if attr in attributes and attributes[attr]:
				text = str(attributes[attr]).strip()
				if text:
					print(f'      ✓ Using {attr} attribute as target_text: "{text}"')
					return text

		# Priority 6: Extract from agent reasoning using structured [ELEMENT: "text"] format
		# The agent is instructed to use this format: [ELEMENT: "First Name"], [ELEMENT: "Search"], etc.
		if agent_context and agent_context.get('reasoning'):
			reasoning = agent_context['reasoning']
			import re

			# Debug: print the reasoning to see what we're working with
			print(f'      📝 Agent reasoning: {reasoning[:200]}...')

			# Primary Pattern: Extract from structured [ELEMENT: "text"] tag
			# This is the most reliable since we explicitly ask the agent to use this format

			# Find ALL [ELEMENT] tags and use the LAST one (closest to the action)
			matches = list(re.finditer(r'\[ELEMENT:\s*["\']([^"\']+)["\']\]', reasoning))
			if matches:
				element_text = matches[-1].group(1).strip()  # Use last match
				print(f'      ✓ Extracted from [ELEMENT] tag (last occurrence): "{element_text}"')
				print(f'         (Found {len(matches)} [ELEMENT] tags total, using the last one)')
				return element_text

			# Try without quotes as fallback: [ELEMENT: Search]
			matches = list(re.finditer(r'\[ELEMENT:\s*([^\]]+)\]', reasoning))
			if matches:
				element_text = matches[-1].group(1).strip()  # Use last match
				print(f'      ✓ Extracted from [ELEMENT] tag (no quotes, last occurrence): "{element_text}"')
				return element_text

			# Fallback patterns for when agent doesn't follow the structured format:

			# For input/click actions, try to find context-specific field mentions
			# E.g., "input 'Jasmine' into the First Name" or "'Paxton' into the Last Name"
			action_value = action_dict.get('text') or action_dict.get('value')

			if action_value:
				# Pattern: Look for the value followed by field name mention
				# E.g., "'Jasmine' into the First Name field" or "input 'Paxton'... Last Name"
				escaped_value = re.escape(str(action_value))
				# Match: value (with quotes or not) + optional words + "into/in/for" + field name + "field/input"
				match = re.search(
					rf'["\']?{escaped_value}["\']?[^.]*?(?:into|in|for|to)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:field|input|box)',
					reasoning,
					re.IGNORECASE,
				)
				if match:
					label_text = match.group(1).strip()
					print(f'      ✓ Extracted from agent reasoning (context: "{action_value}"): "{label_text}"')
					return label_text

			# Fallback: Pattern 1: "into the First Name field" (first occurrence)
			match = re.search(r'(?:into|in|for)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:field|input|box)', reasoning)
			if match:
				label_text = match.group(1).strip()
				print(f'      ✓ Extracted from agent reasoning: "{label_text}"')
				return label_text

			# Fallback: Pattern 2: "First Name field" or "Last Name input"
			match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:field|input|box)', reasoning)
			if match:
				label_text = match.group(1).strip()
				print(f'      ✓ Extracted from agent reasoning: "{label_text}"')
				return label_text

			# Fallback: Pattern 3: "click the Search button" or "click on Search" (for button/link clicks)
			match = re.search(
				r'(?:click|tap|press)\s+(?:on\s+)?(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:button|link)',
				reasoning,
				re.IGNORECASE,
			)
			if match:
				button_text = match.group(1).strip()
				print(f'      ✓ Extracted button text from agent reasoning: "{button_text}"')
				return button_text

		# Priority 7-8: Check name/id attributes, but skip or convert technical/generated IDs
		def is_human_readable(text: str) -> bool:
			"""Check if text is human-readable, not a technical ID."""
			text_lower = text.lower()
			# Skip if contains common technical patterns
			technical_patterns = ['$', 'ctl', 'ctr', 'dnn', 'aspnet', 'viewstate', '__', 'guid']
			if any(pattern in text_lower for pattern in technical_patterns):
				return False
			# Skip if mostly uppercase/numbers (like GUID fragments)
			if len([c for c in text if c.isupper() or c.isdigit()]) > len(text) * 0.7:
				return False
			return True

		def extract_semantic_part(technical_id: str) -> str | None:
			"""Try to extract semantic meaning from technical IDs like 'dnn$ctr434$SQLViewPro$FirstName$txtParameter'."""
			# Split by common separators
			parts = technical_id.replace('$', '.').replace('_', '.').split('.')

			# Look for parts that might be semantic (e.g., "FirstName", "LastName", "Search")
			for part in reversed(parts):  # Check from end first (more specific)
				# Skip common technical suffixes
				if part.lower() in ['txt', 'txtparameter', 'parameter', 'ctrl', 'control', 'btn', 'button', 'lbl', 'label']:
					continue
				# Skip very short parts (likely not semantic)
				if len(part) < 3:
					continue
				# Skip numeric parts
				if part.isdigit():
					continue
				# Skip parts that look like prefixes (all caps)
				if part.isupper() and len(part) < 5:
					continue

				# Found a potentially semantic part - convert camelCase to readable text
				# E.g., "FirstName" -> "First Name"
				import re

				# Insert space before capital letters
				readable = re.sub(r'([a-z])([A-Z])', r'\1 \2', part)
				print(f'      ✓ Extracted semantic text from {technical_id}: "{readable}"')
				return readable

			return None

		for attr in ['name', 'id']:
			if attr in attributes and attributes[attr]:
				text = str(attributes[attr]).strip()
				if text and is_human_readable(text):
					print(f'      ✓ Using {attr} attribute as target_text: "{text}"')
					return text
				elif text:
					# Try to extract semantic meaning from technical IDs
					semantic_text = extract_semantic_part(text)
					if semantic_text:
						return semantic_text
					print(f'      ⚠️  Skipping technical {attr} attribute: "{text}"')

		# Priority 8: For anchor tags, extract meaningful text from href
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

		# Priority 9: Fallback - use descriptive element type
		# NEVER use action_dict.get('text') - that's the input VALUE, not a semantic identifier!
		if node_name:
			print(f'      ⚠️  No good target text found, using node name: "{node_name}"')
			return f'{node_name} element'

		print('      ⚠️  No target text found at all')
		return 'element'

	def _add_wait_time_to_step(self, step: Dict[str, Any], step_duration: Optional[float]) -> Dict[str, Any]:
		"""Add wait_time to step based on execution duration (0.75x multiplier)."""
		if step_duration is not None and step_duration > 0:
			wait_time = round(step_duration * 0.75, 2)
			step['wait_time'] = wait_time
			print(f'   ⏱️  Set wait_time={wait_time}s (based on {step_duration}s execution)')
		return step

	def _convert_action_to_step(
		self,
		action_type: str,
		action_dict: Dict[str, Any],
		element_data: Optional[Dict[str, Any]],
		agent_context: Optional[Dict[str, Any]] = None,
		step_duration: Optional[float] = None,
	) -> Optional[Dict[str, Any]]:
		"""
		Convert a single browser-use action to a semantic workflow step with context.

		Args:
		    action_type: The type of action (e.g., 'click', 'navigate')
		    action_dict: The action parameters
		    element_data: Element data extracted from the DOM
		    agent_context: Semantic context from the agent's reasoning
		    step_duration: Duration of the step execution in seconds

		Mapping (browser-use action names):
		- navigate → navigation step
		- input, input_text → input step with target_text
		- click, click_element → click step with target_text
		- send_keys → keypress step
		- extract, extract_content, extract_page_content → extract_page_content step
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
				'expected_outcome': f'Successfully navigated to {url} and page loaded',
				# Deterministic verification checks
				'verification_checks': [
					{
						'name': 'url_changed',
						'method': 'deterministic',
						'check_function': 'check_url_matches',
						'description': f'Verify URL changed to {url}',
						'parameters': {'expected_url': url},
					},
					{
						'name': 'page_loaded',
						'method': 'deterministic',
						'check_function': 'check_page_loaded',
						'description': 'Verify page finished loading',
					},
				],
			}

			# Add semantic metadata for navigation
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']

			return self._add_wait_time_to_step(step, step_duration)

		# Input text actions (browser-use can use either 'input' or 'input_text')
		elif action_type in ['input', 'input_text']:
			target_text = self._extract_target_text(element_data, action_dict, agent_context)
			# Ensure target_text is never empty
			if not target_text:
				target_text = 'input field'

			input_value = action_dict.get('text', '')
			step = {
				'type': 'input',
				'target_text': target_text,
				'value': input_value,
				'description': f'Enter text into {target_text}',
				'expected_outcome': f'Input field "{target_text}" populated with value and no validation errors',
				# Deterministic verification checks
				'verification_checks': [
					{
						'name': 'input_value_set',
						'method': 'deterministic',
						'check_function': 'check_input_value',
						'description': 'Verify input field contains the entered value',
						'parameters': {'target_text': target_text, 'expected_value': input_value},
					},
					{
						'name': 'no_validation_errors',
						'method': 'deterministic',
						'check_function': 'check_no_validation_errors',
						'description': 'Verify no validation errors appeared',
					},
				],
			}

			# Add element hash for selector population
			if element_data and element_data.get('element_hash'):
				step['elementHash'] = element_data['element_hash']

			# Add multi-strategy selectors for robust element finding
			if element_data and element_data.get('selector_strategies'):
				step['selectorStrategies'] = element_data['selector_strategies']

			# Add semantic metadata
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']
			if agent_context.get('page_url'):
				step['page_context_url'] = agent_context['page_url']

			return self._add_wait_time_to_step(step, step_duration)

		# Click actions (browser-use uses 'click', not 'click_element')
		elif action_type in ['click', 'click_element']:
			target_text = self._extract_target_text(element_data, action_dict, agent_context)
			# Ensure target_text is never empty
			if not target_text:
				target_text = 'element'

			# Check if this looks like a dynamic identifier (ID, code, number, etc.) that should be made generic
			import re

			position_hint = None
			container_hint = None

			# Define common dynamic identifier patterns
			# Require at least one digit to avoid matching regular words
			alphanumeric_id = re.match(r'^[A-Z]{2,}\d{3,}$', target_text)  # e.g., AP00945776, ABC123
			numeric_id = re.match(r'^\d{3,}$', target_text)  # e.g., 123456, 00945776
			code_with_separator = re.match(
				r'^[A-Z0-9]+[-_][A-Z0-9]*\d+[A-Z0-9]*$', target_text, re.IGNORECASE
			)  # e.g., ORD-12345, user_456, TKT-9876

			if alphanumeric_id or numeric_id or code_with_separator:
				print(f'      🔍 Detected dynamic identifier pattern: "{target_text}"')

				# Check agent reasoning for context to determine the semantic meaning
				reasoning = agent_context.get('reasoning', '') if agent_context else ''
				reasoning_lower = reasoning.lower()

				original_target = target_text

				# Map reasoning keywords to generic identifiers
				# This makes workflows reusable across different records
				semantic_mapping = {
					'license': 'license number link',
					'provider': 'provider id link',
					'order': 'order id link',
					'invoice': 'invoice number link',
					'ticket': 'ticket number link',
					'case': 'case number link',
					'patient': 'patient id link',
					'user': 'user id link',
					'customer': 'customer id link',
					'product': 'product code link',
					'transaction': 'transaction id link',
					'record': 'record id link',
				}

				# Try to find semantic meaning from reasoning
				converted = False
				for keyword, generic_name in semantic_mapping.items():
					if keyword in reasoning_lower:
						target_text = generic_name
						position_hint = 'first'  # Usually click the first result
						container_hint = 'search results'
						print(f'      ✅ Converted to generic: "{target_text}" (detected: {keyword})')
						print(f'         Position: {position_hint}, Container: {container_hint}')
						print(f'         Original value "{original_target}" will match via pattern')
						converted = True
						break

				# If no semantic meaning found, use generic "id link"
				if not converted:
					target_text = 'id link'
					position_hint = 'first'
					container_hint = 'search results'
					print(f'      ✅ Converted to generic: "{target_text}" (no specific context detected)')
					print(f'         Position: {position_hint}, Container: {container_hint}')
					print(f'         Original value "{original_target}" will match via pattern')

			# Create semantic description
			base_description = f'Click on {target_text}'
			description = self._create_semantic_description(action_type, base_description, agent_context, target_text)

			step = {
				'type': 'click',
				'target_text': target_text,
				'description': description,
				'expected_outcome': f'Successfully clicked "{target_text}" and page/state updated',
				# Deterministic verification check - verify page state changed
				'verification_checks': [
					{
						'name': 'page_state_changed',
						'method': 'deterministic',
						'check_function': 'check_page_state_changed',
						'description': 'Verify page or DOM state changed after click',
					}
				],
			}

			# Add position and container hints if detected
			if position_hint:
				step['position_hint'] = position_hint
			if container_hint:
				step['container_hint'] = container_hint

			# Add element hash for selector population
			if element_data and element_data.get('element_hash'):
				step['elementHash'] = element_data['element_hash']

			# Add multi-strategy selectors for robust element finding
			if element_data and element_data.get('selector_strategies'):
				step['selectorStrategies'] = element_data['selector_strategies']

			# Add semantic metadata (optional fields that provide context)
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']
			if agent_context.get('page_url'):
				step['page_context_url'] = agent_context['page_url']
			if agent_context.get('page_title'):
				step['page_context_title'] = agent_context['page_title']

			return self._add_wait_time_to_step(step, step_duration)

		# Keyboard actions
		elif action_type == 'send_keys':
			# For send_keys, we might not have a specific element
			# If it's a simple key like "Enter", create a keypress step
			keys = action_dict.get('keys', '')

			# Try to get target from last interacted element if available
			target_text = self._extract_target_text(element_data, action_dict, agent_context)
			# Ensure target_text is never empty
			if not target_text:
				target_text = 'page'

			step = {
				'type': 'key_press',
				'key': keys,
				'target_text': target_text,
				'description': f'Press {keys} key',
				'expected_outcome': f'Key "{keys}" pressed successfully',
			}

			# Add element hash for selector population
			if element_data and element_data.get('element_hash'):
				step['elementHash'] = element_data['element_hash']

			return self._add_wait_time_to_step(step, step_duration)

		# Extract content actions (browser-use can use 'extract', 'extract_content', or 'extract_page_content')
		elif action_type in ['extract', 'extract_page_content', 'extract_content']:
			# Browser-use may use different field names for extraction goal
			goal = (
				action_dict.get('value')
				or action_dict.get('goal')
				or action_dict.get('content')
				or action_dict.get('query')
				or 'page content'
			)
			step = {
				'type': 'extract_page_content',
				'goal': goal,
				'description': f'Extract: {goal}',
				'expected_outcome': f'Successfully extracted: {goal}',
			}
			return self._add_wait_time_to_step(step, step_duration)

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
				'expected_outcome': f'Page scrolled {"down" if down else "up"} by {pixels} pixels',
				# Deterministic verification check
				'verification_checks': [
					{
						'name': 'scroll_position_changed',
						'method': 'deterministic',
						'check_function': 'check_scroll_position',
						'description': 'Verify scroll position changed',
					}
				],
			}

			# Add semantic metadata
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']
			if agent_context.get('page_url'):
				step['page_context_url'] = agent_context['page_url']

			return self._add_wait_time_to_step(step, step_duration)

		# Dropdown actions - convert to click for now
		elif action_type == 'select_dropdown_option':
			target_text = action_dict.get('text', '')
			step = {
				'type': 'click',
				'target_text': target_text,
				'description': f'Select dropdown option: {target_text}',
				'expected_outcome': f'Dropdown option "{target_text}" selected',
			}
			return self._add_wait_time_to_step(step, step_duration)

		# Navigation actions
		elif action_type == 'go_back':
			step = {
				'type': 'go_back',
				'description': 'Navigate back to previous page',
				'expected_outcome': 'Successfully navigated back to previous page',
			}

			# Add semantic metadata
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']
			if agent_context.get('page_url'):
				step['page_context_url'] = agent_context['page_url']

			return self._add_wait_time_to_step(step, step_duration)

		elif action_type == 'go_forward':
			step = {
				'type': 'go_forward',
				'description': 'Navigate forward to next page',
				'expected_outcome': 'Successfully navigated forward to next page',
			}

			# Add semantic metadata
			if agent_context.get('reasoning'):
				step['agent_reasoning'] = agent_context['reasoning']
			if agent_context.get('page_url'):
				step['page_context_url'] = agent_context['page_url']

			return self._add_wait_time_to_step(step, step_duration)

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
