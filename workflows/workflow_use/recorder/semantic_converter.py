import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SemanticWorkflowConverter:
	"""Converts recorded workflows to use semantic targeting instead of CSS selectors."""

	def __init__(self, enable_variable_identification: bool = True, variable_config: Optional[Dict[str, Any]] = None):
		"""
		Initialize the semantic workflow converter.

		Args:
			enable_variable_identification: Whether to automatically identify and parameterize variables
			variable_config: Optional configuration for variable identification (min_confidence, etc.)
		"""
		self.enable_variable_identification = enable_variable_identification
		self.variable_config = variable_config or {}

	def convert_workflow_to_semantic(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
		"""Convert a recorded workflow to use semantic targeting."""

		# Deep copy the workflow data to avoid modifying the original
		semantic_workflow = workflow_data.copy()

		# Update metadata
		semantic_workflow['workflow_analysis'] = (
			'Semantic version of recorded workflow. Uses visible text to identify elements instead of CSS selectors for improved reliability.'
		)
		if 'name' in semantic_workflow:
			semantic_workflow['name'] = f'{semantic_workflow["name"]} (Semantic)'

		# Convert steps to use semantic targeting
		if 'steps' in semantic_workflow:
			semantic_workflow['steps'] = self._convert_steps_to_semantic(semantic_workflow['steps'])

		# Identify and parameterize variables
		if self.enable_variable_identification:
			semantic_workflow = self._identify_and_parameterize_variables(semantic_workflow)

		return semantic_workflow

	def _convert_steps_to_semantic(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""Convert workflow steps to use semantic targeting."""
		semantic_steps = []

		for step in steps:
			semantic_step = self._convert_step_to_semantic(step)
			semantic_steps.append(semantic_step)

		return semantic_steps

	def _convert_step_to_semantic(self, step: Dict[str, Any]) -> Dict[str, Any]:
		"""Convert a single step to use semantic targeting."""
		# Make a copy of the step
		semantic_step = step.copy()

		step_type = step.get('type')

		if step_type in ['click', 'input', 'select_change', 'key_press']:
			# For interactive steps, prioritize target_text over cssSelector
			target_text = self._extract_semantic_target_text(step)

			if target_text:
				semantic_step['target_text'] = target_text

				# Extract text-based context hints (no CSS selectors stored)
				semantic_info = step.get('semanticInfo', {})
				if semantic_info:
					# Extract container context as text hint
					container_context = semantic_info.get('container_context', {})
					if container_context:
						container_text = container_context.get('text', '').strip()
						container_id = container_context.get('id', '').strip()

						if container_text and len(container_text) < 50:
							semantic_step['container_hint'] = container_text
						elif container_id:
							formatted_id = container_id.replace('-', ' ').replace('_', ' ').title()
							semantic_step['container_hint'] = formatted_id

					# Extract position context as text hint
					sibling_context = semantic_info.get('sibling_context', {})
					if sibling_context:
						position = sibling_context.get('position')
						total = sibling_context.get('total')
						if position is not None and total is not None and total > 1:
							semantic_step['position_hint'] = f'item {position + 1} of {total}'

					# Extract interaction type hint
					interaction_hints = semantic_info.get('interaction_hints', [])
					if interaction_hints and isinstance(interaction_hints, list) and len(interaction_hints) > 0:
						semantic_step['interaction_type'] = interaction_hints[0]  # Use first hint

				# Add a description that mentions the semantic targeting
				if not semantic_step.get('description'):
					action = {'click': 'Click', 'input': 'Input', 'select_change': 'Select', 'key_press': 'Press key on'}.get(
						step_type, 'Interact with'
					)
					semantic_step['description'] = f'{action} element'

				logger.info(f"Converted {step_type} step to use semantic targeting: '{target_text}'")
			else:
				# If no semantic text available, keep the CSS selector as fallback
				logger.warning(f'No semantic text found for {step_type} step, keeping CSS selector')

		elif step_type == 'navigation':
			# Navigation steps don't need semantic conversion
			pass

		elif step_type == 'scroll':
			# Scroll steps don't need semantic conversion
			pass

		return semantic_step

	def _extract_semantic_target_text(self, step: Dict[str, Any]) -> Optional[str]:
		"""Extract the best semantic target text from a step."""

		# Priority order for semantic targeting:
		# 1. targetText (if already captured by extension)
		# 2. hierarchical target_text with context
		# 3. elementText (visible text content)
		# 4. Extract from semanticInfo if available
		# 5. Extract meaningful text from element attributes

		# Check if we already have targetText from the updated extension
		if step.get('targetText'):
			return step['targetText'].strip()

		# Check for hierarchical context to create contextual target text
		semantic_info = step.get('semanticInfo', {})
		if semantic_info:
			base_text = None
			container_context = semantic_info.get('container_context', {})

			# Get base text
			for field in ['labelText', 'textContent', 'name', 'id']:
				value = semantic_info.get(field, '').strip()
				if value and len(value) < 100:
					base_text = value
					break

			# Add hierarchical context if available
			if base_text and container_context:
				container_text = container_context.get('text', '').strip()
				container_id = container_context.get('id', '').strip()

				# Create contextual target text
				if container_text and len(container_text) < 50:
					return f'{base_text} (in {container_text})'
				elif container_id and len(container_id) < 30:
					formatted_id = container_id.replace('-', ' ').replace('_', ' ').title()
					return f'{base_text} (in {formatted_id})'

			# Fallback to base text
			if base_text:
				return base_text

			# Priority: placeholder > ariaLabel > other fields
			for field in ['placeholder', 'ariaLabel']:
				value = semantic_info.get(field, '').strip()
				if value and len(value) < 100:  # Reasonable length for targeting
					return value

		# Fallback to elementText
		element_text = step.get('elementText', '').strip()
		if element_text and len(element_text) < 100:
			return element_text

		# Try to extract from CSS selector or XPath as last resort
		css_selector = step.get('cssSelector', '')
		if css_selector:
			# Extract ID using regex - more robust approach

			# Look for id attribute in selector
			id_match = re.search(r'\[id=["\']([^"\']+)["\']\]', css_selector)
			if id_match:
				extracted_id = id_match.group(1)
				if extracted_id and len(extracted_id) < 50:  # Reasonable length
					logger.info(f"Extracted ID from CSS selector: '{extracted_id}'")
					return extracted_id

			# Also try the # selector format
			if '#' in css_selector:
				# Extract ID
				id_part = css_selector.split('#')[1].split('.')[0].split('[')[0].split(':')[0]
				if id_part and id_part.replace('_', '').replace('-', '').isalnum():
					logger.info(f"Extracted ID from # selector: '{id_part}'")
					return id_part

			# Extract name attribute from CSS selector using regex
			name_match = re.search(r'\[name=["\']([^"\']+)["\']\]', css_selector)
			if name_match:
				extracted_name = name_match.group(1)
				if extracted_name and len(extracted_name) < 50:
					logger.info(f"Extracted name from CSS selector: '{extracted_name}'")
					return extracted_name

			# Look for value attribute for radio buttons
			value_match = re.search(r'\[value=["\']([^"\']+)["\']\]', css_selector)
			if value_match and ('radio' in css_selector or 'checkbox' in css_selector):
				extracted_value = value_match.group(1)
				if extracted_value and len(extracted_value) < 50:
					logger.info(f"Extracted value from CSS selector: '{extracted_value}'")
					return extracted_value

			# For buttons, try to extract meaningful text from complex selectors
			if 'button' in css_selector:
				# Look for text content patterns or simple IDs
				if '[id=' in css_selector:
					# Already handled above
					pass
				elif css_selector.count('.') < 10:  # Not too complex
					# Try to find a meaningful class name
					classes = re.findall(r'\.([a-zA-Z][a-zA-Z0-9_-]*)', css_selector)
					for class_name in classes:
						if (
							len(class_name) > 2
							and len(class_name) < 20
							and not any(
								x in class_name.lower()
								for x in [
									'btn',
									'button',
									'flex',
									'inline',
									'items',
									'justify',
									'gap',
									'rounded',
									'text',
									'font',
									'ring',
									'transition',
									'colors',
									'bg',
									'primary',
									'foreground',
								]
							)
						):
							logger.info(f"Extracted meaningful class name: '{class_name}'")
							return class_name

		return None

	def _identify_and_parameterize_variables(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		Identify and parameterize variables in the workflow.

		This method imports and uses the VariableIdentifier to automatically detect
		input values that should be parameterized as variables.
		"""
		try:
			from workflow_use.workflow.variable_identifier import identify_variables_in_workflow

			min_confidence = self.variable_config.get('min_confidence', 0.6)
			use_llm = self.variable_config.get('use_llm', False)

			logger.info('Identifying variables in workflow...')
			workflow_with_vars = identify_variables_in_workflow(workflow_data, min_confidence, use_llm)

			if workflow_with_vars.get('metadata', {}).get('identified_variable_count', 0) > 0:
				logger.info(f'Successfully identified {workflow_with_vars["metadata"]["identified_variable_count"]} variables')
			else:
				logger.info('No variables identified in workflow')

			return workflow_with_vars

		except ImportError as e:
			logger.warning(f'Variable identification not available: {e}')
			return workflow_data
		except Exception as e:
			logger.error(f'Error during variable identification: {e}', exc_info=True)
			return workflow_data


def convert_recorded_workflow_to_semantic(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
	"""Convenience function to convert a recorded workflow to semantic targeting."""
	converter = SemanticWorkflowConverter()
	return converter.convert_workflow_to_semantic(workflow_data)


def convert_workflow_file_to_semantic(input_file_path: str, output_file_path: str = None) -> str:
	"""Convert a workflow file to semantic and save it."""
	import json

	# Read the original workflow
	with open(input_file_path, 'r') as f:
		workflow_data = json.load(f)

	# Convert to semantic
	semantic_workflow = convert_recorded_workflow_to_semantic(workflow_data)

	# Determine output path
	if output_file_path is None:
		if input_file_path.endswith('.json'):
			output_file_path = input_file_path.replace('.json', '.semantic.json')
		else:
			output_file_path = f'{input_file_path}.semantic.json'

	# Save the converted workflow
	with open(output_file_path, 'w') as f:
		json.dump(semantic_workflow, f, indent=2)

	logger.info(f'Converted workflow saved to: {output_file_path}')
	return output_file_path
