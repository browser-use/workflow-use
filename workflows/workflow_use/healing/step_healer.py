"""Step-level self-healing for workflow execution.

When a deterministic step fails (element not found, action error), this module:
1. Captures a screenshot of the current page state
2. Sends the screenshot + step context to the LLM
3. Asks the LLM to identify the correct element or corrective action
4. Returns a corrected step that can be retried
5. Optionally persists the fix back to the workflow file
"""

import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from browser_use.llm.base import BaseChatModel

logger = logging.getLogger(__name__)

HEALING_SYSTEM_PROMPT = """You are a browser automation self-healing agent. A workflow step has failed during execution. You will be shown:

1. A screenshot of the current page state
2. The step that failed (type, target_text, selectors)
3. The error message

Your job is to analyze the screenshot and determine WHY the step failed, then provide a corrected step.

Common failure reasons:
- The element's text changed (e.g., "Log In" became "Sign In")
- The element moved to a different location on the page
- The page hasn't finished loading yet
- A popup/modal is blocking the element
- The element is inside an iframe
- The page layout changed after an update

Respond with a JSON object containing:
{
  "diagnosis": "Brief explanation of why the step failed",
  "corrected_target_text": "The correct visible text for the element (null if unchanged)",
  "corrected_css_selector": "A CSS selector for the element (null if not applicable)",
  "corrected_xpath": "An XPath for the element (null if not applicable)",
  "action_override": "If the action type should change (null if unchanged)",
  "wait_before_retry": 0,
  "confidence": 0.8,
  "page_state_issue": "none|loading|popup|iframe|navigation_needed"
}

IMPORTANT:
- Look at the ACTUAL screenshot carefully — what elements are visible on the page?
- Prefer target_text corrections (most resilient to future changes)
- Only suggest CSS/XPath if the element has no visible text
- Set confidence to how sure you are (0.0-1.0)
- If a popup/modal is blocking, set page_state_issue accordingly"""


class StepHealer:
	"""Heals failed workflow steps using LLM vision analysis."""

	def __init__(
		self,
		llm: BaseChatModel,
		max_healing_attempts: int = 2,
		min_confidence: float = 0.5,
		persist_fixes: bool = True,
	):
		self.llm = llm
		self.max_healing_attempts = max_healing_attempts
		self.min_confidence = min_confidence
		self.persist_fixes = persist_fixes
		self._healing_log: list[Dict[str, Any]] = []

	async def heal_step(
		self,
		step: Any,
		step_index: int,
		error: Exception,
		browser: Any,
		workflow_path: Optional[str] = None,
	) -> Optional[Dict[str, Any]]:
		"""Attempt to heal a failed step using LLM vision analysis.

		Args:
			step: The WorkflowStep that failed
			step_index: Index of the step in the workflow
			error: The exception that was raised
			browser: Browser instance for screenshot capture
			workflow_path: Path to workflow file for persisting fixes

		Returns:
			Dict with corrected step fields, or None if healing failed.
		"""
		logger.info(f'🩺 Self-healing step {step_index + 1}: {error}')

		# Capture screenshot
		screenshot_b64 = await self._capture_screenshot(browser)
		if not screenshot_b64:
			logger.warning('Could not capture screenshot for healing')
			return None

		# Build step context
		step_context = self._build_step_context(step, step_index, error)

		# Ask LLM to diagnose and fix
		correction = await self._ask_llm_for_correction(screenshot_b64, step_context)
		if not correction:
			return None

		# Check confidence threshold
		confidence = correction.get('confidence', 0)
		if confidence < self.min_confidence:
			logger.info(f'🩺 Healing confidence too low ({confidence:.0%} < {self.min_confidence:.0%}), skipping')
			return None

		logger.info(f'🩺 Healing diagnosis: {correction.get("diagnosis", "unknown")}')
		logger.info(f'🩺 Confidence: {confidence:.0%}')

		# Build corrected fields
		corrected_fields = self._build_corrected_fields(step, correction)

		if not corrected_fields:
			logger.info('🩺 No corrections suggested by LLM')
			return None

		# Log the healing
		healing_entry = {
			'step_index': step_index,
			'original_error': str(error),
			'diagnosis': correction.get('diagnosis'),
			'corrections': corrected_fields,
			'confidence': confidence,
		}
		self._healing_log.append(healing_entry)

		# Persist fixes to workflow file
		if self.persist_fixes and workflow_path and corrected_fields:
			await self._persist_fix(workflow_path, step_index, corrected_fields)

		return corrected_fields

	async def _capture_screenshot(self, browser: Any) -> Optional[str]:
		"""Capture a screenshot and return as base64 string."""
		try:
			page = await browser.get_current_page()
			screenshot_bytes = await page.screenshot(full_page=False)
			return base64.b64encode(screenshot_bytes).decode('utf-8')
		except Exception as e:
			logger.warning(f'Screenshot capture failed: {e}')
			return None

	def _build_step_context(self, step: Any, step_index: int, error: Exception) -> str:
		"""Build a text description of the failed step for the LLM."""
		step_dict = step.model_dump(exclude_none=True) if hasattr(step, 'model_dump') else {}
		return json.dumps(
			{
				'step_index': step_index,
				'step_type': step_dict.get('type', 'unknown'),
				'target_text': step_dict.get('target_text'),
				'css_selector': step_dict.get('cssSelector'),
				'xpath': step_dict.get('xpath'),
				'value': step_dict.get('value'),
				'description': step_dict.get('description'),
				'error_message': str(error),
			},
			indent=2,
		)

	async def _ask_llm_for_correction(self, screenshot_b64: str, step_context: str) -> Optional[Dict[str, Any]]:
		"""Send screenshot + context to LLM and parse the correction response."""
		try:
			messages = [
				{'role': 'system', 'content': HEALING_SYSTEM_PROMPT},
				{
					'role': 'user',
					'content': [
						{
							'type': 'text',
							'text': f'This workflow step failed. Please analyze the screenshot and suggest a correction.\n\nFailed step:\n{step_context}',
						},
						{
							'type': 'image_url',
							'image_url': {'url': f'data:image/png;base64,{screenshot_b64}'},
						},
					],
				},
			]

			response = await self.llm.ainvoke(messages)
			content = response.content if hasattr(response, 'content') else str(response)

			# Parse JSON from response (handle markdown code blocks)
			json_str = content
			if '```json' in json_str:
				json_str = json_str.split('```json')[1].split('```')[0]
			elif '```' in json_str:
				json_str = json_str.split('```')[1].split('```')[0]

			return json.loads(json_str.strip())

		except Exception as e:
			logger.warning(f'LLM healing request failed: {e}')
			return None

	def _build_corrected_fields(self, step: Any, correction: Dict[str, Any]) -> Dict[str, Any]:
		"""Build a dict of corrected fields from the LLM's response."""
		fields = {}

		if correction.get('corrected_target_text'):
			fields['target_text'] = correction['corrected_target_text']

		if correction.get('corrected_css_selector'):
			fields['cssSelector'] = correction['corrected_css_selector']

		if correction.get('corrected_xpath'):
			fields['xpath'] = correction['corrected_xpath']

		if correction.get('action_override'):
			fields['type'] = correction['action_override']

		if correction.get('wait_before_retry', 0) > 0:
			fields['wait_before_retry'] = correction['wait_before_retry']

		if correction.get('page_state_issue') and correction['page_state_issue'] != 'none':
			fields['page_state_issue'] = correction['page_state_issue']

		return fields

	async def _persist_fix(self, workflow_path: str, step_index: int, corrected_fields: Dict[str, Any]) -> None:
		"""Write corrected selectors back to the workflow YAML/JSON file."""
		try:
			path = Path(workflow_path)
			if not path.exists():
				logger.warning(f'Cannot persist fix: workflow file not found at {path}')
				return

			# Load the workflow
			with open(path, 'r') as f:
				if path.suffix in ['.yaml', '.yml']:
					workflow_data = yaml.safe_load(f)
				else:
					workflow_data = json.load(f)

			steps = workflow_data.get('steps', [])
			if step_index >= len(steps):
				logger.warning(f'Cannot persist fix: step index {step_index} out of range')
				return

			# Apply corrections (only persistent fields, not transient ones)
			persistent_fields = {'target_text', 'cssSelector', 'xpath', 'type'}
			applied = []
			for key, value in corrected_fields.items():
				if key in persistent_fields:
					old_value = steps[step_index].get(key)
					steps[step_index][key] = value
					applied.append(f'{key}: {old_value!r} → {value!r}')

			if not applied:
				return

			# Write back
			with open(path, 'w') as f:
				if path.suffix in ['.yaml', '.yml']:
					yaml.dump(workflow_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
				else:
					json.dump(workflow_data, f, indent=2)

			logger.info(f'🩺 Persisted healing fix to {path.name}:')
			for change in applied:
				logger.info(f'   Step {step_index + 1}: {change}')

		except Exception as e:
			logger.warning(f'Failed to persist healing fix: {e}')

	def get_healing_log(self) -> list[Dict[str, Any]]:
		"""Return the log of all healing attempts in this session."""
		return self._healing_log.copy()
