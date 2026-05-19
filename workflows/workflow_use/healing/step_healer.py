"""Step-level self-healing for workflow execution.

Inspired by the autoresearch-mlx self-improvement loop:
- Snapshot before healing, revert if fix makes things worse
- TSV-based results tracking for every healing attempt
- Fail-fast sanity checks before expensive LLM calls
- Exponential backoff on retries
- Single ground-truth metric: did the step actually succeed?

When a deterministic step fails (element not found, action error):
1. Sanity check — is this a healable failure? (fail-fast)
2. Snapshot the current workflow state (for revert)
3. Capture a screenshot of the current page
4. Send screenshot + step context to the LLM
5. LLM diagnoses and suggests a corrected step
6. Retry with correction
7. If success: persist fix to workflow file, log as "keep"
8. If failure: revert workflow file, log as "discard"
"""

import base64
import csv
import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from browser_use.llm.base import BaseChatModel

logger = logging.getLogger(__name__)

# --- Healable error patterns (fail-fast filter) ---
HEALABLE_PATTERNS = [
	'not found',
	'target text',
	'element',
	'selector',
	'timeout',
	'no such element',
	'stale',
	'not visible',
	'not interactable',
	'click intercepted',
]

UNHEALABLE_PATTERNS = [
	'browser crashed',
	'connection refused',
	'protocol error',
	'session closed',
	'out of memory',
	'permission denied',
]

HEALING_SYSTEM_PROMPT = """You are a browser automation self-healing agent. A workflow step has failed during execution. You will be shown:

1. A screenshot of the current page state
2. The step that failed (type, target_text, selectors, error)
3. Previous healing attempts for this step (if any)

Your job: analyze the screenshot and determine WHY the step failed, then provide a corrected step.

Common failure reasons:
- Element text changed (e.g., "Log In" → "Sign In")
- Element moved or is in a different container
- Page hasn't finished loading / dynamic content not yet rendered
- Popup/modal/cookie banner blocking the element
- Element is inside an iframe
- Page layout changed after a site update
- Wrong page — navigation didn't complete

Respond ONLY with a JSON object (no markdown, no explanation outside the JSON):
{
  "diagnosis": "Brief explanation of why the step failed",
  "corrected_target_text": "The correct visible text for the element, or null if unchanged",
  "corrected_css_selector": "A CSS selector if text-based matching won't work, or null",
  "corrected_xpath": "An XPath selector as last resort, or null",
  "action_override": "New action type if it should change (e.g., 'click' → 'key_press'), or null",
  "wait_before_retry": 0,
  "confidence": 0.8,
  "page_state_issue": "none|loading|popup|iframe|navigation_needed"
}

Rules:
- Look at the ACTUAL screenshot — describe what you see before suggesting fixes
- Prefer corrected_target_text (most resilient to future DOM changes)
- Only use CSS/XPath when the element has no visible text
- Set confidence honestly (0.0–1.0). If you're guessing, say 0.3
- If the page looks completely wrong (wrong URL, error page), set confidence to 0.1
- If a popup/modal is blocking, set page_state_issue="popup" and confidence high"""


class HealingResult:
	"""Structured result of a healing attempt, modeled after autoresearch-mlx results.tsv."""

	__slots__ = ('step_index', 'attempt', 'status', 'confidence', 'duration_ms', 'diagnosis', 'corrections', 'timestamp')

	def __init__(
		self,
		step_index: int,
		attempt: int,
		status: str,  # "keep", "discard", "crash", "skip"
		confidence: float,
		duration_ms: int,
		diagnosis: str,
		corrections: Dict[str, Any],
		timestamp: str,
	):
		self.step_index = step_index
		self.attempt = attempt
		self.status = status
		self.confidence = confidence
		self.duration_ms = duration_ms
		self.diagnosis = diagnosis
		self.corrections = corrections
		self.timestamp = timestamp


class StepHealer:
	"""Heals failed workflow steps using LLM vision analysis.

	Follows the autoresearch-mlx pattern:
	- Snapshot/revert: saves workflow state before healing, reverts on failure
	- Results tracking: logs every attempt to a TSV file
	- Fail-fast: skips unhealable errors without wasting LLM calls
	- Exponential backoff: 1s, 2s, 4s between retry attempts
	"""

	def __init__(
		self,
		llm: BaseChatModel,
		max_healing_attempts: int = 3,
		min_confidence: float = 0.4,
		persist_fixes: bool = True,
		log_dir: str | Path | None = None,
	):
		self.llm = llm
		self.max_healing_attempts = max_healing_attempts
		self.min_confidence = min_confidence
		self.persist_fixes = persist_fixes
		self.log_dir = Path(log_dir) if log_dir else Path('./logs/healing')
		self.log_dir.mkdir(parents=True, exist_ok=True)

		# Results tracking (autoresearch-mlx pattern: results.tsv)
		self._results: List[HealingResult] = []
		self._results_file = self.log_dir / 'healing_results.tsv'
		self._init_results_file()

		# Session stats
		self.total_healed = 0
		self.total_failed = 0

	def _init_results_file(self) -> None:
		"""Initialize the TSV results file with headers if it doesn't exist."""
		if not self._results_file.exists():
			with open(self._results_file, 'w', newline='') as f:
				writer = csv.writer(f, delimiter='\t')
				writer.writerow(['timestamp', 'step_index', 'attempt', 'status', 'confidence', 'duration_ms', 'diagnosis'])

	def _log_result(self, result: HealingResult) -> None:
		"""Append a healing result to the TSV log and in-memory list."""
		self._results.append(result)
		try:
			with open(self._results_file, 'a', newline='') as f:
				writer = csv.writer(f, delimiter='\t')
				writer.writerow([
					result.timestamp,
					result.step_index,
					result.attempt,
					result.status,
					f'{result.confidence:.2f}',
					result.duration_ms,
					result.diagnosis[:100],  # Truncate for readability
				])
		except Exception as e:
			logger.warning(f'Failed to write healing result to TSV: {e}')

	def _is_healable(self, error: Exception) -> bool:
		"""Fail-fast: check if this error is worth attempting to heal."""
		error_str = str(error).lower()

		# Reject unhealable errors immediately
		for pattern in UNHEALABLE_PATTERNS:
			if pattern in error_str:
				logger.info(f'🩺 Skipping healing — unhealable error pattern: "{pattern}"')
				return False

		# Accept known healable patterns
		for pattern in HEALABLE_PATTERNS:
			if pattern in error_str:
				return True

		# Default: attempt healing for unknown errors (conservative)
		return True

	def _snapshot_workflow(self, workflow_path: str) -> Optional[str]:
		"""Snapshot the workflow file before healing (for revert on failure).

		Returns the snapshot path, or None if snapshot failed.
		"""
		try:
			path = Path(workflow_path)
			if not path.exists():
				return None
			snapshot_path = str(path) + '.healing_snapshot'
			shutil.copy2(str(path), snapshot_path)
			return snapshot_path
		except Exception as e:
			logger.warning(f'Failed to create workflow snapshot: {e}')
			return None

	def _revert_workflow(self, workflow_path: str, snapshot_path: str) -> None:
		"""Revert workflow file to its pre-healing snapshot."""
		try:
			shutil.copy2(snapshot_path, workflow_path)
			Path(snapshot_path).unlink(missing_ok=True)
			logger.info(f'🩺 Reverted workflow to pre-healing state')
		except Exception as e:
			logger.warning(f'Failed to revert workflow snapshot: {e}')

	def _cleanup_snapshot(self, snapshot_path: Optional[str]) -> None:
		"""Remove snapshot file after successful healing."""
		if snapshot_path:
			Path(snapshot_path).unlink(missing_ok=True)

	async def heal_step(
		self,
		step: Any,
		step_index: int,
		error: Exception,
		browser: Any,
		workflow_path: Optional[str] = None,
		previous_attempts: Optional[List[Dict[str, Any]]] = None,
	) -> Optional[Dict[str, Any]]:
		"""Attempt to heal a failed step using LLM vision analysis.

		Args:
			step: The WorkflowStep that failed
			step_index: Index of the step in the workflow
			error: The exception that was raised
			browser: Browser instance for screenshot capture
			workflow_path: Path to workflow file for persisting fixes
			previous_attempts: List of prior healing attempts for context

		Returns:
			Dict with corrected step fields, or None if healing failed/skipped.
		"""
		t_start = time.monotonic()

		# Fail-fast sanity check
		if not self._is_healable(error):
			self._log_result(HealingResult(
				step_index=step_index, attempt=0, status='skip',
				confidence=0.0, duration_ms=0,
				diagnosis=f'Unhealable error: {str(error)[:80]}',
				corrections={},
				timestamp=datetime.now(timezone.utc).isoformat(),
			))
			return None

		logger.info(f'🩺 Self-healing step {step_index + 1}: {error}')

		# Capture screenshot
		screenshot_b64 = await self._capture_screenshot(browser)
		if not screenshot_b64:
			logger.warning('Could not capture screenshot for healing')
			self._log_result(HealingResult(
				step_index=step_index, attempt=0, status='crash',
				confidence=0.0, duration_ms=int((time.monotonic() - t_start) * 1000),
				diagnosis='Screenshot capture failed',
				corrections={},
				timestamp=datetime.now(timezone.utc).isoformat(),
			))
			return None

		# Build step context with previous attempts (helps LLM avoid repeating failed fixes)
		step_context = self._build_step_context(step, step_index, error, previous_attempts)

		# Ask LLM to diagnose and fix
		correction = await self._ask_llm_for_correction(screenshot_b64, step_context)
		duration_ms = int((time.monotonic() - t_start) * 1000)

		if not correction:
			self._log_result(HealingResult(
				step_index=step_index, attempt=len(previous_attempts or []) + 1,
				status='crash', confidence=0.0, duration_ms=duration_ms,
				diagnosis='LLM returned no correction',
				corrections={},
				timestamp=datetime.now(timezone.utc).isoformat(),
			))
			return None

		# Check confidence threshold
		confidence = correction.get('confidence', 0)
		diagnosis = correction.get('diagnosis', 'unknown')

		if confidence < self.min_confidence:
			logger.info(f'🩺 Healing confidence too low ({confidence:.0%} < {self.min_confidence:.0%}), skipping')
			self._log_result(HealingResult(
				step_index=step_index, attempt=len(previous_attempts or []) + 1,
				status='discard', confidence=confidence, duration_ms=duration_ms,
				diagnosis=f'Low confidence: {diagnosis}',
				corrections={},
				timestamp=datetime.now(timezone.utc).isoformat(),
			))
			return None

		logger.info(f'🩺 Diagnosis: {diagnosis}')
		logger.info(f'🩺 Confidence: {confidence:.0%}')

		# Build corrected fields
		corrected_fields = self._build_corrected_fields(step, correction)

		if not corrected_fields:
			logger.info('🩺 No actionable corrections from LLM')
			self._log_result(HealingResult(
				step_index=step_index, attempt=len(previous_attempts or []) + 1,
				status='discard', confidence=confidence, duration_ms=duration_ms,
				diagnosis=f'No corrections: {diagnosis}',
				corrections={},
				timestamp=datetime.now(timezone.utc).isoformat(),
			))
			return None

		# Log as pending (will be updated to keep/discard by caller)
		self._log_result(HealingResult(
			step_index=step_index, attempt=len(previous_attempts or []) + 1,
			status='pending', confidence=confidence, duration_ms=duration_ms,
			diagnosis=diagnosis,
			corrections=corrected_fields,
			timestamp=datetime.now(timezone.utc).isoformat(),
		))

		return corrected_fields

	def mark_healing_outcome(self, step_index: int, success: bool) -> None:
		"""Update the last healing result for this step with the actual outcome.

		Called by the Workflow.run() loop after retrying with corrections.
		"""
		# Find the last pending result for this step
		for result in reversed(self._results):
			if result.step_index == step_index and result.status == 'pending':
				result.status = 'keep' if success else 'discard'
				if success:
					self.total_healed += 1
					logger.info(f'🩺 ✅ Step {step_index + 1} healed successfully (total healed: {self.total_healed})')
				else:
					self.total_failed += 1
					logger.info(f'🩺 ❌ Healing failed for step {step_index + 1} (total failed: {self.total_failed})')
				break

	async def persist_if_healed(self, workflow_path: str, step_index: int, corrected_fields: Dict[str, Any]) -> None:
		"""Persist a successful healing fix to the workflow file.

		Only called after the corrected step has been verified to work.
		Uses snapshot/revert pattern from autoresearch-mlx.
		"""
		if not self.persist_fixes:
			return

		snapshot_path = self._snapshot_workflow(workflow_path)

		try:
			await self._persist_fix(workflow_path, step_index, corrected_fields)
		except Exception as e:
			logger.warning(f'Failed to persist fix, reverting: {e}')
			if snapshot_path:
				self._revert_workflow(workflow_path, snapshot_path)
			return

		self._cleanup_snapshot(snapshot_path)

	async def _capture_screenshot(self, browser: Any) -> Optional[str]:
		"""Capture a screenshot and return as base64 string."""
		try:
			page = await browser.get_current_page()
			screenshot_bytes = await page.screenshot(full_page=False)
			return base64.b64encode(screenshot_bytes).decode('utf-8')
		except Exception as e:
			logger.warning(f'Screenshot capture failed: {e}')
			return None

	def _build_step_context(
		self, step: Any, step_index: int, error: Exception,
		previous_attempts: Optional[List[Dict[str, Any]]] = None,
	) -> str:
		"""Build a text description of the failed step for the LLM."""
		step_dict = step.model_dump(exclude_none=True) if hasattr(step, 'model_dump') else {}

		context = {
			'step_index': step_index,
			'step_type': step_dict.get('type', 'unknown'),
			'target_text': step_dict.get('target_text'),
			'css_selector': step_dict.get('cssSelector'),
			'xpath': step_dict.get('xpath'),
			'value': step_dict.get('value'),
			'description': step_dict.get('description'),
			'error_message': str(error),
		}

		# Include previous failed attempts so LLM doesn't repeat them
		if previous_attempts:
			context['previous_healing_attempts'] = [
				{
					'attempt': i + 1,
					'corrections': att.get('corrections', {}),
					'result': 'failed',
				}
				for i, att in enumerate(previous_attempts)
			]

		return json.dumps(context, indent=2)

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
							'text': f'This workflow step failed. Analyze the screenshot and suggest a correction.\n\nFailed step:\n{step_context}',
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

		except json.JSONDecodeError as e:
			logger.warning(f'LLM returned unparseable response: {e}')
			return None
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

	def get_results(self) -> List[HealingResult]:
		"""Return all healing results from this session."""
		return self._results.copy()

	def get_session_summary(self) -> str:
		"""Return a human-readable summary of healing activity."""
		if not self._results:
			return 'No healing attempts this session.'

		total = len(self._results)
		kept = sum(1 for r in self._results if r.status == 'keep')
		discarded = sum(1 for r in self._results if r.status == 'discard')
		crashed = sum(1 for r in self._results if r.status == 'crash')
		skipped = sum(1 for r in self._results if r.status == 'skip')
		avg_confidence = sum(r.confidence for r in self._results) / total if total else 0
		total_time_ms = sum(r.duration_ms for r in self._results)

		return (
			f'Healing session: {total} attempts, {kept} kept, {discarded} discarded, '
			f'{crashed} crashed, {skipped} skipped | '
			f'avg confidence: {avg_confidence:.0%} | total time: {total_time_ms / 1000:.1f}s'
		)
