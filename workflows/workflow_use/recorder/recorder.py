# Enhanced recorder with comprehensive event types and intelligent merging
import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from workflow_use.recorder.service import RecordingService  # Adjust import path if necessary


@dataclass
class BaseEvent:
	"""Base class for all recorded events."""

	timestamp: int
	url: str
	description: str
	type: str = ''


@dataclass
class NavigationEvent(BaseEvent):
	"""Navigation to a new page."""

	type: str = 'navigation'


@dataclass
class ClickEvent(BaseEvent):
	"""Click on an element."""

	type: str = 'click'
	target_text: str = ''  # Primary text-based identifier (e.g., "Submit (in Personal Information)")
	# Optional context hints for disambiguation (text-based, not selectors)
	container_hint: str = ''  # e.g., "Personal Information", "Billing Section"
	position_hint: str = ''  # e.g., "item 2 of 3", "first", "last"
	interaction_type: str = ''  # e.g., "form_submit", "table_action", "navigation"
	# Legacy fields for backward compatibility - discouraged in new workflows
	element_tag: str = ''
	css_selector: str = ''
	xpath: str = ''


@dataclass
class InputEvent(BaseEvent):
	"""Input into a text field."""

	type: str = 'input'
	target_text: str = ''  # Primary text-based identifier
	value: str = ''
	input_type: str = 'text'  # text, password, email, number, etc.
	# Optional context hints for disambiguation
	container_hint: str = ''
	position_hint: str = ''
	interaction_type: str = ''
	# Legacy fields for backward compatibility
	element_tag: str = ''
	css_selector: str = ''
	xpath: str = ''


@dataclass
class RadioEvent(BaseEvent):
	"""Radio button selection."""

	type: str = 'radio'
	field_name: str = ''  # The group name (e.g., "Gender")
	selected_option: str = ''  # The selected value (e.g., "Male")
	options: List[str] = None  # All available options in the group
	target_text: str = ''  # Primary text-based identifier
	# Optional context hints for disambiguation
	container_hint: str = ''
	position_hint: str = ''
	interaction_type: str = ''
	# Legacy fields for backward compatibility
	css_selector: str = ''
	xpath: str = ''

	def __post_init__(self):
		if self.options is None:
			self.options = []


@dataclass
class SelectEvent(BaseEvent):
	"""Select dropdown selection."""

	type: str = 'select'
	field_name: str = ''  # The select field name/label
	selected_option: str = ''  # The selected text
	selected_value: str = ''  # The selected value
	options: List[Dict[str, str]] = None  # All options [{"text": "...", "value": "..."}]
	target_text: str = ''  # Primary text-based identifier
	# Optional context hints for disambiguation
	container_hint: str = ''
	position_hint: str = ''
	interaction_type: str = ''
	# Legacy fields for backward compatibility
	css_selector: str = ''
	xpath: str = ''

	def __post_init__(self):
		if self.options is None:
			self.options = []


@dataclass
class CheckboxEvent(BaseEvent):
	"""Checkbox toggle."""

	type: str = 'checkbox'
	field_name: str = ''
	checked: bool = False
	target_text: str = ''  # Primary text-based identifier
	# Optional context hints for disambiguation
	container_hint: str = ''
	position_hint: str = ''
	interaction_type: str = ''
	# Legacy fields for backward compatibility
	css_selector: str = ''
	xpath: str = ''


@dataclass
class ButtonEvent(BaseEvent):
	"""Button click event."""

	type: str = 'button'
	button_text: str = ''  # The visible text on the button
	button_type: str = ''  # submit, button, reset, etc.
	target_text: str = ''  # Primary text-based identifier
	# Optional context hints for disambiguation
	container_hint: str = ''
	position_hint: str = ''
	interaction_type: str = ''
	# Legacy fields for backward compatibility
	css_selector: str = ''
	xpath: str = ''


class EnhancedRecordingService(RecordingService):
	"""Enhanced recording service with better event type detection and merging."""

	def __init__(self):
		super().__init__()
		self.pending_events: List[BaseEvent] = []
		self.last_click_timestamp = 0
		self.label_click_window_ms = 1000  # Time window to merge label clicks with input focus

	async def process_raw_event(self, raw_event: Dict) -> Optional[BaseEvent]:
		"""Process a raw event from the browser extension into a typed event."""
		event_type = raw_event.get('type', '')

		if event_type == 'CUSTOM_CLICK_EVENT':
			return await self._process_click_event(raw_event['payload'])
		elif event_type == 'CUSTOM_INPUT_EVENT':
			return await self._process_input_event(raw_event['payload'])
		elif event_type == 'CUSTOM_SELECT_EVENT':
			return await self._process_select_event(raw_event['payload'])
		elif event_type == 'navigation':
			return await self._process_navigation_event(raw_event['payload'])
		else:
			# Handle other event types as needed
			return None

	def _extract_text_context_hints(self, payload: Dict) -> Dict:
		"""Extract text-based context hints from payload (no CSS selectors)."""
		semantic_info = payload.get('semanticInfo', {})

		# Extract container context as text hint
		container_hint = ''
		container_context = semantic_info.get('container_context', {})
		if container_context:
			container_text = container_context.get('text', '').strip()
			container_id = container_context.get('id', '').strip()

			if container_text and len(container_text) < 50:
				container_hint = container_text
			elif container_id:
				container_hint = container_id.replace('-', ' ').replace('_', ' ').title()

		# Extract position context as text hint
		position_hint = ''
		sibling_context = semantic_info.get('sibling_context', {})
		if sibling_context:
			position = sibling_context.get('position')
			total = sibling_context.get('total')
			if position is not None and total is not None and total > 1:
				position_hint = f'item {position + 1} of {total}'

		# Extract interaction type hint
		interaction_type = ''
		interaction_hints = semantic_info.get('interaction_hints', [])
		if interaction_hints and isinstance(interaction_hints, list) and len(interaction_hints) > 0:
			interaction_type = interaction_hints[0]  # Use first hint

		return {'container_hint': container_hint, 'position_hint': position_hint, 'interaction_type': interaction_type}

	def _create_contextual_target_text(self, base_text: str, context_hints: Dict) -> str:
		"""Create contextual target text using context hints."""
		if not base_text:
			return base_text

		result_text = base_text

		# Add container context if available
		container_hint = context_hints.get('container_hint', '').strip()
		if container_hint and container_hint.lower() not in result_text.lower():
			result_text = f'{result_text} (in {container_hint})'

		# Add position context if available
		position_hint = context_hints.get('position_hint', '').strip()
		if position_hint and position_hint not in result_text:
			result_text = f'{result_text} ({position_hint})'

		return result_text

	async def _process_click_event(self, payload: Dict) -> Optional[BaseEvent]:
		"""Process click events with smart type detection."""
		element_tag = payload.get('elementTag', '').lower()
		element_type = payload.get('elementType', '').lower()
		semantic_info = payload.get('semanticInfo', {})
		radio_info = payload.get('radioButtonInfo', {})

		# Determine if this is a special input type click
		if element_tag == 'input':
			if element_type == 'radio':
				return await self._create_radio_event(payload, radio_info, semantic_info)
			elif element_type == 'checkbox':
				return await self._create_checkbox_event(payload, semantic_info)
			elif element_type in ['submit', 'button']:
				return await self._create_button_event(payload, semantic_info)
			else:
				# Regular input field click - might merge with subsequent input
				return await self._create_input_focus_event(payload, semantic_info)

		elif element_tag == 'button':
			if payload.get('role') == 'radio':
				return await self._create_radio_event(payload, radio_info, semantic_info)
			else:
				return await self._create_button_event(payload, semantic_info)

		elif element_tag == 'label':
			# Label click - try to merge with associated input
			return await self._handle_label_click(payload, semantic_info)

		else:
			# Check if this might be a button-like element (div with button role, etc.)
			if self._is_button_like_element(payload, semantic_info):
				return await self._create_button_event(payload, semantic_info)
			else:
				# Regular click event
				return await self._create_click_event(payload, semantic_info)

	async def _process_input_event(self, payload: Dict) -> Optional[InputEvent]:
		"""Process input events."""
		context_hints = self._extract_text_context_hints(payload)

		# Create contextual target text
		base_text = payload.get('targetText', '')
		target_text = self._create_contextual_target_text(base_text, context_hints)

		return InputEvent(
			type='input',
			timestamp=payload.get('timestamp', 0),
			url=payload.get('url', ''),
			target_text=target_text,
			value=payload.get('value', ''),
			input_type=payload.get('inputType', 'text'),
			element_tag=payload.get('elementTag', ''),
			css_selector=payload.get('cssSelector', ''),
			xpath=payload.get('xpath', ''),
			description=f"Enter '{payload.get('value', '')}' into {target_text or 'input field'}",
			**context_hints,
		)

	async def _process_select_event(self, payload: Dict) -> Optional[SelectEvent]:
		"""Process select dropdown events."""
		# Extract options from the select element if available
		options = []
		select_options = payload.get('allOptions', [])
		for opt in select_options:
			if isinstance(opt, dict):
				options.append(opt)
			else:
				# Convert string options to dict format
				options.append({'text': str(opt), 'value': str(opt)})

		context_hints = self._extract_text_context_hints(payload)

		# Create contextual target text
		base_text = payload.get('targetText', '')
		target_text = self._create_contextual_target_text(base_text, context_hints)

		return SelectEvent(
			type='select',
			timestamp=payload.get('timestamp', 0),
			url=payload.get('url', ''),
			field_name=payload.get('fieldName', ''),
			selected_option=payload.get('selectedText', ''),
			selected_value=payload.get('selectedValue', ''),
			options=options,
			target_text=target_text,
			css_selector=payload.get('cssSelector', ''),
			xpath=payload.get('xpath', ''),
			description=f"Select '{payload.get('selectedText', '')}' from {target_text or payload.get('fieldName', 'dropdown')}",
			**context_hints,
		)

	async def _create_radio_event(self, payload: Dict, radio_info: Dict, semantic_info: Dict) -> RadioEvent:
		"""Create a radio button event."""
		field_name = radio_info.get('fieldName', semantic_info.get('fieldName', ''))
		selected_option = radio_info.get('optionValue', semantic_info.get('optionValue', ''))
		all_options = radio_info.get('allOptions', semantic_info.get('allOptions', []))

		context_hints = self._extract_text_context_hints(payload)

		# Create contextual target text
		base_text = payload.get('targetText', selected_option)
		target_text = self._create_contextual_target_text(base_text, context_hints)

		return RadioEvent(
			type='radio',
			timestamp=payload.get('timestamp', 0),
			url=payload.get('url', ''),
			field_name=field_name,
			selected_option=selected_option,
			options=all_options,
			target_text=target_text,
			css_selector=payload.get('cssSelector', ''),
			xpath=payload.get('xpath', ''),
			description=f"Select '{selected_option}' for {field_name}",
			**context_hints,
		)

	async def _create_checkbox_event(self, payload: Dict, semantic_info: Dict) -> CheckboxEvent:
		"""Create a checkbox event."""
		field_name = semantic_info.get('fieldName', semantic_info.get('labelText', ''))
		checked = payload.get('checked', False)

		context_hints = self._extract_text_context_hints(payload)

		# Create contextual target text
		base_text = payload.get('targetText', field_name)
		target_text = self._create_contextual_target_text(base_text, context_hints)

		return CheckboxEvent(
			type='checkbox',
			timestamp=payload.get('timestamp', 0),
			url=payload.get('url', ''),
			field_name=field_name,
			checked=checked,
			target_text=target_text,
			css_selector=payload.get('cssSelector', ''),
			xpath=payload.get('xpath', ''),
			description=f'{"Check" if checked else "Uncheck"} {field_name}',
			**context_hints,
		)

	async def _create_button_event(self, payload: Dict, semantic_info: Dict) -> ButtonEvent:
		"""Create a button click event."""
		base_text = payload.get('targetText') or semantic_info.get('labelText', '')
		button_text = base_text or semantic_info.get('textContent', '')
		button_type = payload.get('elementType', 'button')

		context_hints = self._extract_text_context_hints(payload)

		# Create contextual target text
		target_text = self._create_contextual_target_text(base_text, context_hints)

		return ButtonEvent(
			type='button',
			timestamp=payload.get('timestamp', 0),
			url=payload.get('url', ''),
			button_text=button_text,
			button_type=button_type,
			target_text=target_text,
			css_selector=payload.get('cssSelector', ''),
			xpath=payload.get('xpath', ''),
			description=f"Click button '{button_text}'",
			**context_hints,
		)

	async def _create_click_event(self, payload: Dict, semantic_info: Dict) -> ClickEvent:
		"""Create a regular click event."""
		base_text = payload.get('targetText') or semantic_info.get('labelText', '')

		context_hints = self._extract_text_context_hints(payload)

		# Create contextual target text
		target_text = self._create_contextual_target_text(base_text, context_hints)

		return ClickEvent(
			type='click',
			timestamp=payload.get('timestamp', 0),
			url=payload.get('url', ''),
			target_text=target_text,
			element_tag=payload.get('elementTag', ''),
			css_selector=payload.get('cssSelector', ''),
			xpath=payload.get('xpath', ''),
			description=f'Click {target_text or "element"}',
			**context_hints,
		)

	async def _create_input_focus_event(self, payload: Dict, semantic_info: Dict) -> Optional[BaseEvent]:
		"""Handle input field focus - might be merged with label click."""
		# Check if there was a recent label click that should be merged
		current_time = payload.get('timestamp', 0)

		# Look for recent label clicks to merge
		for i, event in enumerate(self.pending_events):
			if (
				isinstance(event, ClickEvent)
				and current_time - event.timestamp <= self.label_click_window_ms
				and self._events_should_merge(event, payload)
			):
				# Remove the label click and create a merged input focus
				self.pending_events.pop(i)
				return await self._create_merged_input_event(event, payload, semantic_info)

		# No merge needed, just record focus if relevant
		return None  # Focus events without subsequent input are usually not interesting

	async def _handle_label_click(self, payload: Dict, semantic_info: Dict) -> Optional[ClickEvent]:
		"""Handle label click - may be merged later with input focus."""
		base_text = payload.get('targetText') or semantic_info.get('labelText', '')

		context_hints = self._extract_text_context_hints(payload)

		# Create contextual target text
		target_text = self._create_contextual_target_text(base_text, context_hints)

		event = ClickEvent(
			type='click',
			timestamp=payload.get('timestamp', 0),
			url=payload.get('url', ''),
			target_text=target_text,
			element_tag='label',
			css_selector=payload.get('cssSelector', ''),
			xpath=payload.get('xpath', ''),
			description=f'Click label: {target_text}',
			**context_hints,
		)

		# Add to pending events for potential merging
		self.pending_events.append(event)
		self.last_click_timestamp = event.timestamp

		# Return None initially - will be finalized later if not merged
		return None

	def _events_should_merge(self, label_click: ClickEvent, input_payload: Dict) -> bool:
		"""Determine if a label click and input focus should be merged."""
		# Check if the label is associated with the input field
		label_for = self._extract_label_for_attribute(label_click.css_selector)
		input_id = self._extract_input_id(input_payload.get('cssSelector', ''))

		if label_for and input_id and label_for == input_id:
			return True

		# Check proximity and context
		# This is a simplified check - in practice you might want more sophisticated logic
		return (
			input_payload.get('url') == label_click.url
			and abs(input_payload.get('timestamp', 0) - label_click.timestamp) <= self.label_click_window_ms
		)

	async def _create_merged_input_event(self, label_click: ClickEvent, input_payload: Dict, semantic_info: Dict) -> InputEvent:
		"""Create a merged input event from label click + input focus."""
		context_hints = self._extract_text_context_hints(input_payload)

		return InputEvent(
			type='input',
			timestamp=input_payload.get('timestamp', 0),
			url=input_payload.get('url', ''),
			target_text=label_click.target_text or input_payload.get('targetText', ''),
			value='',  # Will be filled when actual input happens
			input_type=input_payload.get('inputType', 'text'),
			element_tag=input_payload.get('elementTag', ''),
			css_selector=input_payload.get('cssSelector', ''),
			xpath=input_payload.get('xpath', ''),
			description=f'Click and focus on {label_click.target_text or "input field"}',
			**context_hints,
		)

	async def _process_navigation_event(self, payload: Dict) -> NavigationEvent:
		"""Process navigation events."""
		return NavigationEvent(
			type='navigation',
			timestamp=payload.get('timestamp', 0),
			url=payload.get('url', ''),
			description=f'Navigate to {payload.get("url", "")}',
		)

	def _extract_label_for_attribute(self, css_selector: str) -> Optional[str]:
		"""Extract the 'for' attribute value from a label's CSS selector."""
		import re

		match = re.search(r'\[for=["\']([^"\']+)["\']\]', css_selector)
		return match.group(1) if match else None

	def _extract_input_id(self, css_selector: str) -> Optional[str]:
		"""Extract the ID from an input's CSS selector."""
		import re

		# Try [id="..."] format first
		match = re.search(r'\[id=["\']([^"\']+)["\']\]', css_selector)
		if match:
			return match.group(1)

		# Try #id format
		match = re.search(r'#([a-zA-Z][a-zA-Z0-9_-]*)', css_selector)
		return match.group(1) if match else None

	def _is_button_like_element(self, payload: Dict, semantic_info: Dict) -> bool:
		"""Determine if an element behaves like a button."""
		element_tag = payload.get('elementTag', '').lower()
		css_selector = payload.get('cssSelector', '')

		# Check for explicit button role
		if 'role="button"' in css_selector:
			return True

		# Check for clickable elements that might be styled as buttons
		button_like_tags = ['a', 'span', 'div']
		if element_tag in button_like_tags:
			# Check if element has button-like characteristics
			target_text = payload.get('targetText', '').lower()
			button_keywords = ['submit', 'save', 'send', 'continue', 'next', 'confirm', 'cancel', 'close', 'ok', 'apply']

			if any(keyword in target_text for keyword in button_keywords):
				return True

			# Check for button-like CSS classes
			if any(cls in css_selector.lower() for cls in ['btn', 'button', 'submit']):
				return True

		return False

	async def finalize_pending_events(self) -> List[BaseEvent]:
		"""Finalize any pending events that weren't merged."""
		finalized = self.pending_events.copy()
		self.pending_events.clear()
		return finalized

	def export_events_to_workflow(self, events: List[BaseEvent]) -> Dict:
		"""Export the processed events to workflow format."""
		workflow_steps = []

		for event in events:
			step = asdict(event)
			# Clean up the step format for workflow compatibility
			if hasattr(event, 'options') and event.options:
				# Keep options for radio and select events
				step['options'] = event.options

			workflow_steps.append(step)

		return {
			'workflow_analysis': 'Enhanced recorded workflow with comprehensive event types and intelligent merging',
			'name': 'Enhanced Recorded Workflow',
			'description': 'Workflow with input, radio, select, checkbox and other enhanced event types',
			'version': '2.0',
			'steps': workflow_steps,
			'input_schema': [],
		}


async def run_enhanced_recording():
	"""Run the enhanced recording service."""
	service = EnhancedRecordingService()
	print('Starting enhanced recording session...')

	# This would integrate with the existing capture_workflow method
	# For now, showing the structure
	workflow_schema = await service.capture_workflow()

	if workflow_schema:
		print('\n--- ENHANCED RECORDED WORKFLOW ---')
		try:
			print(workflow_schema.model_dump_json(indent=2))
		except AttributeError:
			# Fallback if model_dump_json isn't available
			print(json.dumps(workflow_schema, indent=2, default=str))
		print('------------------------------------')
	else:
		print('No workflow was captured.')


if __name__ == '__main__':
	try:
		asyncio.run(run_enhanced_recording())
	except KeyboardInterrupt:
		print('Enhanced recording script interrupted.')
	except Exception as e:
		print(f'An error occurred in the enhanced recording script: {e}')
