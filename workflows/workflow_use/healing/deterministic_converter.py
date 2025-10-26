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

			# Process each action in this history item
			for action in history.model_output.action:
				action_dict = action.model_dump()
				action_type = action_dict.get('type', '')

				# Get interacted element data if available
				element_data = self._get_element_data(history, action_dict)

				# Convert action to semantic step
				step = self._convert_action_to_step(action_type, action_dict, element_data)

				if step:
					steps.append(step)

		return steps

	def _get_element_data(self, history, action_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
		"""
		Extract element data from interacted elements using the action's index.

		Returns element data including visible text, attributes, node_name, etc.
		"""
		index = action_dict.get('index')
		if index is None:
			return None

		# Browser-use uses 1-based indexing
		element_index = index - 1 if index > 0 else 0

		interacted_elements = history.state.interacted_element
		if element_index < len(interacted_elements):
			element = interacted_elements[element_index]
			if element is None:
				return None

			return {
				'node_name': getattr(element, 'node_name', ''),
				'node_value': getattr(element, 'node_value', ''),
				'attributes': getattr(element, 'attributes', {}),
				'xpath': getattr(element, 'x_path', ''),
			}

		return None

	def _extract_target_text(self, element_data: Optional[Dict[str, Any]], action_dict: Dict[str, Any]) -> str:
		"""
		Extract the best target_text for semantic targeting from element data.

		Priority:
		1. Visible text content (node_value)
		2. Placeholder attribute
		3. aria-label attribute
		4. title attribute
		5. Value attribute
		6. Input text being entered (for input actions)
		"""
		if not element_data:
			# For input actions, use the text being entered as fallback
			if action_dict.get('text'):
				return action_dict['text']
			return ''

		# Priority 1: Visible text content
		node_value = element_data.get('node_value', '').strip()
		if node_value:
			return node_value

		# Priority 2-5: Check attributes
		attributes = element_data.get('attributes', {})
		for attr in ['placeholder', 'aria-label', 'title', 'value']:
			if attr in attributes and attributes[attr]:
				return attributes[attr]

		# For input actions, use the text being entered
		if action_dict.get('text'):
			return action_dict['text']

		return ''

	def _convert_action_to_step(
		self, action_type: str, action_dict: Dict[str, Any], element_data: Optional[Dict[str, Any]]
	) -> Optional[Dict[str, Any]]:
		"""
		Convert a single browser-use action to a semantic workflow step.

		Mapping:
		- navigate/go_to_url → navigation step
		- input_text → input step with target_text
		- click_element → click step with target_text
		- send_keys → keypress step
		- extract_page_content → extract_page_content step
		- scroll → scroll step
		"""

		# Navigation actions
		if action_type in ['navigate', 'go_to_url']:
			return {
				'type': 'navigation',
				'url': action_dict.get('url', ''),
				'description': f'Navigate to {action_dict.get("url", "")}',
			}

		# Input text actions
		elif action_type == 'input_text':
			target_text = self._extract_target_text(element_data, action_dict)
			return {
				'type': 'input',
				'target_text': target_text,
				'value': action_dict.get('text', ''),
				'description': f'Enter text into {target_text or "input field"}',
			}

		# Click actions
		elif action_type == 'click_element':
			target_text = self._extract_target_text(element_data, action_dict)
			return {
				'type': 'click',
				'target_text': target_text,
				'description': f'Click on {target_text or "element"}',
			}

		# Keyboard actions
		elif action_type == 'send_keys':
			# For send_keys, we might not have a specific element
			# If it's a simple key like "Enter", create a keypress step
			keys = action_dict.get('keys', '')

			# Try to get target from last interacted element if available
			target_text = self._extract_target_text(element_data, action_dict)

			return {
				'type': 'keypress',
				'key': keys,
				'target_text': target_text,
				'description': f'Press {keys} key',
			}

		# Extract content actions
		elif action_type == 'extract_page_content':
			return {
				'type': 'extract_page_content',
				'goal': action_dict.get('value', ''),
				'description': f'Extract: {action_dict.get("value", "")}',
			}

		# Scroll actions
		elif action_type == 'scroll':
			direction = 'down' if action_dict.get('down', True) else 'up'
			pages = action_dict.get('pages', 1.0)
			return {
				'type': 'scroll',
				'direction': direction,
				'amount': pages,
				'description': f'Scroll {direction} {pages} pages',
			}

		# Dropdown actions - convert to click for now
		elif action_type == 'select_dropdown_option':
			target_text = action_dict.get('text', '')
			return {
				'type': 'click',
				'target_text': target_text,
				'description': f'Select dropdown option: {target_text}',
			}

		# Actions we skip or handle differently
		elif action_type in ['done', 'switch_tab', 'close_tab']:
			return None  # These don't translate to workflow steps

		else:
			# Unknown action type - log a warning
			print(f'⚠️  Unknown action type: {action_type} - skipping')
			return None

	def create_workflow_definition(
		self,
		name: str,
		description: str,
		steps: List[Dict[str, Any]],
		input_schema: Optional[List[Dict[str, Any]]] = None,
	) -> Dict[str, Any]:
		"""
		Create a complete workflow definition from converted steps.

		Args:
		    name: Workflow name
		    description: Workflow description
		    steps: List of converted step dictionaries
		    input_schema: Optional list of input variable definitions

		Returns:
		    Complete workflow definition dictionary
		"""
		return {
			'name': name,
			'description': description,
			'input_schema': input_schema or [],
			'steps': steps,
		}
