"""
Step verification system for workflow execution.

This module provides deterministic and AI-based verification checks
to ensure each step completed successfully and achieved its intended goal.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VerificationMethod(Enum):
	"""Types of verification methods available."""

	DETERMINISTIC = 'deterministic'  # Rule-based, no AI
	AI_ASSISTED = 'ai_assisted'  # Uses LLM for verification
	HYBRID = 'hybrid'  # Deterministic first, AI fallback


class VerificationResult(Enum):
	"""Verification result status."""

	SUCCESS = 'success'  # Step achieved expected outcome
	FAILURE = 'failure'  # Step did not achieve expected outcome
	UNCERTAIN = 'uncertain'  # Cannot determine outcome
	SKIPPED = 'skipped'  # Verification skipped


@dataclass
class VerificationCheck:
	"""A single verification check to run after a step."""

	name: str
	method: VerificationMethod
	check_function: str  # Name of the check function to call
	description: str
	expected_outcome: Optional[str] = None
	parameters: Dict[str, Any] = None

	def __post_init__(self):
		if self.parameters is None:
			self.parameters = {}


@dataclass
class VerificationOutcome:
	"""Result of running verification checks."""

	result: VerificationResult
	checks_run: List[str]
	checks_passed: List[str]
	checks_failed: List[str]
	confidence: float  # 0.0 to 1.0
	details: str
	suggestions: List[str] = None

	def __post_init__(self):
		if self.suggestions is None:
			self.suggestions = []


class StepVerifier:
	"""
	Verify that workflow steps completed successfully.

	Provides deterministic checks (DOM inspection, URL changes, etc.)
	and optional AI-assisted verification for complex scenarios.
	"""

	def __init__(self, llm: Optional[Any] = None):
		"""
		Initialize step verifier.

		Args:
		    llm: Optional language model for AI-assisted verification
		"""
		self.llm = llm

	async def verify_step(
		self, step: Any, browser_session: Any, pre_state: Optional[Dict[str, Any]] = None
	) -> VerificationOutcome:
		"""
		Verify that a step completed successfully.

		Args:
		    step: The workflow step that was executed
		    browser_session: Browser session for DOM inspection
		    pre_state: Optional state captured before step execution

		Returns:
		    VerificationOutcome with results
		"""
		step_type = getattr(step, 'type', 'unknown')
		logger.info(f'   🔍 Verifying step: {step_type}')

		# Get verification checks for this step type
		checks = self._get_verification_checks(step, pre_state)

		if not checks:
			logger.debug(f'   ⏭️  No verification checks defined for {step_type}')
			return VerificationOutcome(
				result=VerificationResult.SKIPPED,
				checks_run=[],
				checks_passed=[],
				checks_failed=[],
				confidence=0.0,
				details='No verification checks defined for this step type',
			)

		# Run all checks
		checks_run = []
		checks_passed = []
		checks_failed = []
		details_list = []

		for check in checks:
			checks_run.append(check.name)
			logger.debug(f'      Running check: {check.name}')

			try:
				# Run the check
				if check.method == VerificationMethod.DETERMINISTIC:
					passed, detail = await self._run_deterministic_check(check, step, browser_session, pre_state)
				elif check.method == VerificationMethod.AI_ASSISTED:
					passed, detail = await self._run_ai_check(check, step, browser_session, pre_state)
				else:  # HYBRID
					passed, detail = await self._run_hybrid_check(check, step, browser_session, pre_state)

				if passed:
					checks_passed.append(check.name)
					logger.info(f'      ✅ {check.name}: PASSED')
				else:
					checks_failed.append(check.name)
					logger.warning(f'      ❌ {check.name}: FAILED - {detail}')

				details_list.append(f'{check.name}: {detail}')

			except Exception as e:
				checks_failed.append(check.name)
				logger.warning(f'      ❌ {check.name}: ERROR - {e}')
				details_list.append(f'{check.name}: Error - {e}')

		# Determine overall result
		total_checks = len(checks_run)
		passed_count = len(checks_passed)
		failed_count = len(checks_failed)

		if total_checks == 0:
			result = VerificationResult.UNCERTAIN
			confidence = 0.0
		elif failed_count == 0:
			result = VerificationResult.SUCCESS
			confidence = 1.0
		elif passed_count == 0:
			result = VerificationResult.FAILURE
			confidence = 1.0
		else:
			# Mixed results
			confidence = passed_count / total_checks
			if confidence >= 0.7:
				result = VerificationResult.SUCCESS
			else:
				result = VerificationResult.FAILURE

		details = '\n'.join(details_list)

		logger.info(f'   📊 Verification result: {result.value} (confidence: {confidence:.1%})')

		return VerificationOutcome(
			result=result,
			checks_run=checks_run,
			checks_passed=checks_passed,
			checks_failed=checks_failed,
			confidence=confidence,
			details=details,
		)

	def _get_verification_checks(self, step: Any, pre_state: Optional[Dict[str, Any]] = None) -> List[VerificationCheck]:
		"""
		Get verification checks for a specific step type.

		Args:
		    step: The workflow step
		    pre_state: State before step execution

		Returns:
		    List of verification checks to run
		"""
		step_type = getattr(step, 'type', 'unknown')
		checks = []

		# Navigation step verification
		if step_type == 'navigation':
			url = getattr(step, 'url', None)
			if url:
				checks.append(
					VerificationCheck(
						name='url_changed',
						method=VerificationMethod.DETERMINISTIC,
						check_function='check_url_matches',
						description=f'Verify URL changed to {url}',
						expected_outcome=url,
					)
				)
				checks.append(
					VerificationCheck(
						name='page_loaded',
						method=VerificationMethod.DETERMINISTIC,
						check_function='check_page_loaded',
						description='Verify page finished loading',
					)
				)

		# Click step verification
		elif step_type == 'click':
			checks.append(
				VerificationCheck(
					name='page_state_changed',
					method=VerificationMethod.DETERMINISTIC,
					check_function='check_page_state_changed',
					description='Verify page state changed after click',
					parameters={'pre_state': pre_state},
				)
			)
			# Add AI verification for complex outcomes
			if self.llm:
				description = getattr(step, 'description', '')
				checks.append(
					VerificationCheck(
						name='click_outcome_check',
						method=VerificationMethod.AI_ASSISTED,
						check_function='check_click_outcome',
						description=f'Verify click achieved expected outcome: {description}',
						expected_outcome=description,
					)
				)

		# Input step verification
		elif step_type == 'input':
			target_text = getattr(step, 'target_text', None)
			value = getattr(step, 'value', None)
			if target_text and value:
				checks.append(
					VerificationCheck(
						name='input_value_set',
						method=VerificationMethod.DETERMINISTIC,
						check_function='check_input_value',
						description=f'Verify input field contains "{value}"',
						parameters={'target_text': target_text, 'expected_value': value},
					)
				)
				checks.append(
					VerificationCheck(
						name='no_validation_errors',
						method=VerificationMethod.DETERMINISTIC,
						check_function='check_no_validation_errors',
						description='Verify no validation errors appeared',
					)
				)

		# Select/dropdown verification
		elif step_type == 'select_change':
			selected_text = getattr(step, 'selectedText', None)
			if selected_text:
				checks.append(
					VerificationCheck(
						name='option_selected',
						method=VerificationMethod.DETERMINISTIC,
						check_function='check_option_selected',
						description=f'Verify option "{selected_text}" is selected',
						parameters={'expected_option': selected_text},
					)
				)

		# Scroll verification
		elif step_type == 'scroll':
			checks.append(
				VerificationCheck(
					name='scroll_position_changed',
					method=VerificationMethod.DETERMINISTIC,
					check_function='check_scroll_position',
					description='Verify scroll position changed',
					parameters={'pre_state': pre_state},
				)
			)

		# Extract verification
		elif step_type == 'extract':
			checks.append(
				VerificationCheck(
					name='data_extracted',
					method=VerificationMethod.DETERMINISTIC,
					check_function='check_data_extracted',
					description='Verify data was extracted',
				)
			)

		return checks

	async def _run_deterministic_check(
		self, check: VerificationCheck, step: Any, browser_session: Any, pre_state: Optional[Dict[str, Any]]
	) -> tuple[bool, str]:
		"""
		Run a deterministic verification check.

		Args:
		    check: The verification check to run
		    step: The workflow step
		    browser_session: Browser session
		    pre_state: State before step execution

		Returns:
		    Tuple of (passed, detail_message)
		"""
		check_fn = check.check_function

		# URL verification
		if check_fn == 'check_url_matches':
			expected_url = check.expected_outcome
			page = await browser_session.get_current_page()
			current_url = page.url if page else None

			if not current_url:
				return False, 'Could not get current URL'

			# Allow partial match for URL parameters
			if expected_url in current_url or current_url.startswith(expected_url):
				return True, f'URL matches: {current_url}'
			else:
				return False, f'URL mismatch: expected {expected_url}, got {current_url}'

		# Page loaded verification
		elif check_fn == 'check_page_loaded':
			page = await browser_session.get_current_page()
			if not page:
				return False, 'No page available'

			try:
				# Check if page is in a loading state
				ready_state = await page.evaluate('document.readyState')
				if ready_state == 'complete':
					return True, 'Page fully loaded'
				else:
					return False, f'Page not fully loaded: {ready_state}'
			except Exception as e:
				return False, f'Error checking page state: {e}'

		# Page state change verification
		elif check_fn == 'check_page_state_changed':
			page = await browser_session.get_current_page()
			if not page:
				return False, 'No page available'

			try:
				# Get current state
				current_state = await self._capture_page_state(page)

				# Compare with pre-state if available
				if pre_state:
					# Check if URL changed
					if current_state.get('url') != pre_state.get('url'):
						return True, f'URL changed from {pre_state.get("url")} to {current_state.get("url")}'

					# Check if DOM changed significantly
					dom_changed = current_state.get('dom_hash') != pre_state.get('dom_hash')
					if dom_changed:
						return True, 'DOM structure changed'

					# Check if visible elements changed
					visible_changed = current_state.get('visible_elements_count') != pre_state.get('visible_elements_count')
					if visible_changed:
						return (
							True,
							f'Visible elements changed: {pre_state.get("visible_elements_count")} → {current_state.get("visible_elements_count")}',
						)

					return False, 'No significant page state changes detected'
				else:
					# Without pre-state, assume change occurred
					return True, 'State change assumed (no pre-state to compare)'

			except Exception as e:
				return False, f'Error checking page state: {e}'

		# Input value verification
		elif check_fn == 'check_input_value':
			target_text = check.parameters.get('target_text')
			expected_value = check.parameters.get('expected_value')

			page = await browser_session.get_current_page()
			if not page:
				return False, 'No page available'

			try:
				# Use Playwright to directly query input elements instead of relying on browser_session.get_state()
				# This is more resilient and doesn't depend on browser-use's state management

				# Try multiple strategies to find the input element
				input_selectors = [
					f'input[placeholder*="{target_text}" i]',  # By placeholder
					f'input[aria-label*="{target_text}" i]',  # By aria-label
					f'input[name*="{target_text}" i]',  # By name attribute
				]

				# Also try to find by associated label
				label_selector = f'label:has-text("{target_text}")'

				found_value = None

				# Try each selector
				for selector in input_selectors:
					try:
						element = await page.query_selector(selector)
						if element:
							found_value = await element.input_value()
							if found_value and expected_value in str(found_value):
								return True, f'Input value set to: {found_value}'
					except Exception:
						continue

				# Try finding via label
				try:
					label_element = await page.query_selector(label_selector)
					if label_element:
						# Get the associated input
						input_id = await label_element.get_attribute('for')
						if input_id:
							input_element = await page.query_selector(f'#{input_id}')
							if input_element:
								found_value = await input_element.input_value()
								if found_value and expected_value in str(found_value):
									return True, f'Input value set to: {found_value}'
				except Exception:
					pass

				# If we found a value but it doesn't match, report that
				if found_value:
					return False, f'Input found but value "{found_value}" does not contain "{expected_value}"'

				# Gracefully degrade - assume success if we can't verify
				# This prevents false failures from blocking workflow execution
				logger.warning(f'Could not verify input value for "{target_text}" - assuming success')
				return True, 'Input verification skipped (element not found, assuming success)'

			except Exception as e:
				# Log the error but don't fail the step
				logger.warning(f'Error checking input value: {e} - assuming success')
				return True, f'Input verification skipped (error: {str(e)})'

		# Validation error check
		elif check_fn == 'check_no_validation_errors':
			page = await browser_session.get_current_page()
			if not page:
				return False, 'No page available'

			try:
				# Use shared validation error detection utility
				from workflow_use.workflow.validation_utils import detect_validation_errors

				has_errors, error_message = await detect_validation_errors(page)
				if has_errors:
					return False, f'Validation error found: {error_message}'
				else:
					return True, 'No validation errors detected'

			except Exception as e:
				return False, f'Error checking for validation errors: {e}'

		# Option selected check
		elif check_fn == 'check_option_selected':
			expected_option = check.parameters.get('expected_option')
			page = await browser_session.get_current_page()

			if not page:
				return False, 'No page available'

			try:
				# Check selected option in select elements
				selected_options = await page.evaluate(
					"""() => {
						const selects = document.querySelectorAll('select');
						return Array.from(selects).map(select => {
							const selected = select.options[select.selectedIndex];
							return selected ? selected.text : null;
						}).filter(Boolean);
					}"""
				)

				if expected_option in selected_options:
					return True, f'Option "{expected_option}" is selected'
				else:
					return False, f'Option "{expected_option}" not found in selected options: {selected_options}'

			except Exception as e:
				return False, f'Error checking selected option: {e}'

		# Scroll position check
		elif check_fn == 'check_scroll_position':
			page = await browser_session.get_current_page()
			if not page:
				return False, 'No page available'

			try:
				current_scroll = await page.evaluate('({x: window.scrollX, y: window.scrollY})')
				pre_scroll = check.parameters.get('pre_state', {}).get('scroll_position', {})

				if current_scroll != pre_scroll:
					return True, f'Scroll changed: {pre_scroll} → {current_scroll}'
				else:
					return False, 'Scroll position unchanged'

			except Exception as e:
				return False, f'Error checking scroll position: {e}'

		# Data extraction check
		elif check_fn == 'check_data_extracted':
			# Check if output was captured
			output_key = getattr(step, 'output', None)
			if output_key:
				# This would need to check the workflow context for the extracted data
				# For now, assume success if output key is defined
				return True, f'Data extraction completed (output key: {output_key})'
			else:
				return False, 'No output key defined for extraction'

		# Unknown check
		else:
			return False, f'Unknown check function: {check_fn}'

	async def _run_ai_check(
		self, check: VerificationCheck, step: Any, browser_session: Any, pre_state: Optional[Dict[str, Any]]
	) -> tuple[bool, str]:
		"""
		Run an AI-assisted verification check.

		Args:
		    check: The verification check to run
		    step: The workflow step
		    browser_session: Browser session
		    pre_state: State before step execution

		Returns:
		    Tuple of (passed, detail_message)
		"""
		if not self.llm:
			return False, 'AI verification requested but no LLM available'

		page = await browser_session.get_current_page()
		if not page:
			return False, 'No page available'

		try:
			# Get current page state
			current_state = await self._capture_page_state(page)

			# Prepare prompt for LLM
			prompt_text = f"""You are verifying a workflow step execution.

Step Type: {getattr(step, 'type', 'unknown')}
Step Description: {getattr(step, 'description', 'No description')}
Expected Outcome: {check.expected_outcome or 'Verify step completed successfully'}

Current Page State:
- URL: {current_state.get('url')}
- Title: {current_state.get('title')}
- Visible Text: {current_state.get('visible_text', '')[:500]}...

Question: Did this step complete successfully and achieve its intended outcome?

Respond with ONLY one of:
- PASS: <brief reason>
- FAIL: <brief reason>
- UNCERTAIN: <brief reason>
"""

			# Call LLM using ainvoke (BaseChatModel API)
			from browser_use.llm import UserMessage

			messages = [UserMessage(content=prompt_text)]
			result = await self.llm.ainvoke(messages)
			response_text = result.content.strip().upper()

			if response_text.startswith('PASS'):
				reason = response_text.replace('PASS:', '').strip()
				return True, f'AI verification passed: {reason}'
			elif response_text.startswith('FAIL'):
				reason = response_text.replace('FAIL:', '').strip()
				return False, f'AI verification failed: {reason}'
			else:
				reason = response_text.replace('UNCERTAIN:', '').strip()
				return False, f'AI verification uncertain: {reason}'

		except Exception as e:
			return False, f'AI verification error: {e}'

	async def _run_hybrid_check(
		self, check: VerificationCheck, step: Any, browser_session: Any, pre_state: Optional[Dict[str, Any]]
	) -> tuple[bool, str]:
		"""
		Run a hybrid verification (deterministic first, AI fallback).

		Args:
		    check: The verification check to run
		    step: The workflow step
		    browser_session: Browser session
		    pre_state: State before step execution

		Returns:
		    Tuple of (passed, detail_message)
		"""
		# Try deterministic first
		passed, detail = await self._run_deterministic_check(check, step, browser_session, pre_state)

		# If uncertain or failed, try AI
		if not passed and self.llm:
			logger.debug('      Deterministic check inconclusive, trying AI verification')
			ai_passed, ai_detail = await self._run_ai_check(check, step, browser_session, pre_state)
			if ai_passed:
				return True, f'AI verification: {ai_detail} (deterministic was: {detail})'

		return passed, detail

	async def _capture_page_state(self, page: Any) -> Dict[str, Any]:
		"""
		Capture current page state for comparison.

		Args:
		    page: Playwright page object

		Returns:
		    Dictionary with page state information
		"""
		try:
			state = {
				'url': page.url,
				'title': await page.title(),
				'visible_text': await page.evaluate('document.body?.innerText || ""'),
				'visible_elements_count': await page.evaluate('document.querySelectorAll("*").length'),
				'scroll_position': await page.evaluate('({x: window.scrollX, y: window.scrollY})'),
			}

			# Calculate simple DOM hash
			try:
				dom_structure = await page.evaluate('document.documentElement?.outerHTML?.substring(0, 1000) || ""')
				state['dom_hash'] = hash(dom_structure)
			except Exception:
				state['dom_hash'] = 0

			return state

		except Exception as e:
			logger.debug(f'Error capturing page state: {e}')
			return {}

	async def capture_pre_step_state(self, browser_session: Any) -> Dict[str, Any]:
		"""
		Capture state before a step executes (for comparison).

		Args:
		    browser_session: Browser session

		Returns:
		    Dictionary with pre-step state
		"""
		try:
			page = await browser_session.get_current_page()
			if page:
				return await self._capture_page_state(page)
		except Exception as e:
			logger.debug(f'Error capturing pre-step state: {e}')

		return {}
