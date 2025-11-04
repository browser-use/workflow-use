"""
Enhanced error reporting for workflow execution.

This module provides structured error messages with actionable context,
debugging information, and next steps for resolving failures.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
	"""Categories of workflow errors."""

	ELEMENT_NOT_FOUND = 'element_not_found'
	EXECUTION_FAILED = 'execution_failed'
	VERIFICATION_FAILED = 'verification_failed'
	VALIDATION_ERROR = 'validation_error'
	TIMEOUT = 'timeout'
	SYSTEMATIC_FAILURE = 'systematic_failure'
	UNKNOWN = 'unknown'


@dataclass
class StrategyAttempt:
	"""Record of a single strategy attempt."""

	strategy_type: str
	strategy_value: str
	priority: int
	success: bool
	error_message: Optional[str] = None
	metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorContext:
	"""Comprehensive error context for debugging."""

	# Step information
	step_type: str
	step_description: str
	step_index: Optional[int] = None

	# Error details
	error_category: ErrorCategory = ErrorCategory.UNKNOWN
	error_message: str = ''
	original_exception: Optional[Exception] = None

	# Strategy attempts
	strategies_attempted: List[StrategyAttempt] = field(default_factory=list)

	# Failure metrics
	global_failure_count: int = 0
	consecutive_failures: int = 0
	consecutive_verification_failures: int = 0
	retry_attempts: int = 0

	# Additional context
	target_text: Optional[str] = None
	input_value: Optional[str] = None
	last_successful_step: Optional[str] = None
	timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

	# Page state
	current_url: Optional[str] = None
	page_title: Optional[str] = None

	# Debugging aids
	screenshot_path: Optional[str] = None
	suggestions: List[str] = field(default_factory=list)


class ErrorReporter:
	"""
	Generate comprehensive error reports for workflow failures.

	Provides structured error messages with:
	- Clear explanation of what failed
	- List of all strategies attempted
	- Specific failure reasons
	- Actionable next steps
	- Debugging information
	"""

	def __init__(self):
		self.error_history: List[ErrorContext] = []

	def report_error(self, context: ErrorContext) -> str:
		"""
		Generate a comprehensive error report.

		Args:
		    context: Error context with all relevant information

		Returns:
		    Formatted error report string
		"""
		self.error_history.append(context)

		# Build the error report
		lines = []
		lines.append('\n' + '=' * 80)
		lines.append('❌ WORKFLOW STEP FAILED')
		lines.append('=' * 80)

		# Step information
		lines.append('\n📍 Step Information:')
		if context.step_index is not None:
			lines.append(f'   Step #{context.step_index}: {context.step_type}')
		else:
			lines.append(f'   Step Type: {context.step_type}')
		lines.append(f'   Description: {context.step_description}')

		if context.target_text:
			lines.append(f'   Target: {context.target_text}')
		if context.input_value:
			lines.append(f'   Input Value: {context.input_value}')

		# Error details
		lines.append(f'\n🔴 Error Category: {context.error_category.value.replace("_", " ").title()}')
		if context.error_message:
			lines.append(f'   Message: {context.error_message}')

		# Page context
		if context.current_url or context.page_title:
			lines.append('\n📄 Page Context:')
			if context.current_url:
				lines.append(f'   URL: {context.current_url}')
			if context.page_title:
				lines.append(f'   Title: {context.page_title}')

		# Strategies attempted
		if context.strategies_attempted:
			lines.append(f'\n🔍 Strategies Attempted ({len(context.strategies_attempted)} total):')
			for i, attempt in enumerate(context.strategies_attempted, 1):
				status = '✅' if attempt.success else '❌'
				lines.append(
					f'   {i}. [{attempt.priority}] {attempt.strategy_type}: {self._truncate(attempt.strategy_value, 60)} {status}'
				)
				if attempt.error_message:
					lines.append(f'      Error: {attempt.error_message}')

		# Failure metrics
		lines.append('\n📊 Failure Metrics:')
		lines.append(f'   Retry Attempts: {context.retry_attempts}')
		lines.append(f'   Global Failures: {context.global_failure_count}')
		lines.append(f'   Consecutive Failures: {context.consecutive_failures}')
		if context.consecutive_verification_failures > 0:
			lines.append(f'   Consecutive Verification Failures: {context.consecutive_verification_failures}')

		if context.last_successful_step:
			lines.append(f'\n✅ Last Successful Step: {context.last_successful_step}')

		# Debugging information
		if context.screenshot_path:
			lines.append(f'\n📸 Screenshot: {context.screenshot_path}')

		# Suggestions for resolution
		suggestions = context.suggestions or self._generate_suggestions(context)
		if suggestions:
			lines.append('\n💡 Suggested Next Steps:')
			for i, suggestion in enumerate(suggestions, 1):
				lines.append(f'   {i}. {suggestion}')

		# Root cause analysis
		root_cause = self._analyze_root_cause(context)
		if root_cause:
			lines.append('\n🔎 Likely Root Cause:')
			lines.append(f'   {root_cause}')

		lines.append('\n' + '=' * 80 + '\n')

		error_report = '\n'.join(lines)
		logger.error(error_report)
		return error_report

	def _generate_suggestions(self, context: ErrorContext) -> List[str]:
		"""
		Generate actionable suggestions based on error context.

		Args:
		    context: Error context

		Returns:
		    List of suggestions
		"""
		suggestions = []

		if context.error_category == ErrorCategory.ELEMENT_NOT_FOUND:
			suggestions.append('Verify the element exists on the current page (check screenshot)')
			suggestions.append('Check if the page structure has changed since workflow creation')
			suggestions.append('Ensure the page has fully loaded before this step executes')
			if context.target_text:
				suggestions.append(f"Look for elements with text similar to '{context.target_text}' on the page")
			suggestions.append('Consider adding a wait/delay before this step if content loads dynamically')

		elif context.error_category == ErrorCategory.VERIFICATION_FAILED:
			suggestions.append('Check if the action completed but verification criteria are too strict')
			suggestions.append('Verify that the expected outcome is still correct for the current page')
			suggestions.append('Increase wait times if the page needs more time to respond to actions')
			suggestions.append('Review the verification logic - it may need to be updated')

		elif context.error_category == ErrorCategory.VALIDATION_ERROR:
			suggestions.append('Review the input data - it may not meet form validation requirements')
			suggestions.append('Check if form validation rules have changed')
			suggestions.append('Look for specific validation error messages on the page (check screenshot)')
			if context.input_value:
				suggestions.append(f"Verify that '{context.input_value}' is a valid value for this field")

		elif context.error_category == ErrorCategory.TIMEOUT:
			suggestions.append('Increase timeout values for this step')
			suggestions.append('Check if the page is experiencing performance issues')
			suggestions.append('Verify network connectivity and page load times')

		elif context.error_category == ErrorCategory.SYSTEMATIC_FAILURE:
			suggestions.append('Review the entire workflow - there may be fundamental issues')
			suggestions.append('Check if the target website has made major changes')
			suggestions.append('Verify input data is valid and complete')
			suggestions.append('Consider regenerating the workflow if structure has significantly changed')

		# Add strategy-specific suggestions
		if context.strategies_attempted:
			xpath_attempted = any(s.strategy_type == 'xpath' for s in context.strategies_attempted)
			if not xpath_attempted:
				suggestions.append('Try adding an XPath selector as a fallback strategy')

		# Add context-specific suggestions
		if context.consecutive_failures > 2:
			suggestions.append('Consider stopping the workflow and reviewing from the last successful step')

		return suggestions

	def _analyze_root_cause(self, context: ErrorContext) -> Optional[str]:
		"""
		Analyze error context to determine likely root cause.

		Args:
		    context: Error context

		Returns:
		    Root cause description or None
		"""
		# Pattern 1: All semantic strategies failed, but XPath might work
		if context.strategies_attempted:
			semantic_failed = all(
				not s.success and s.strategy_type in ['text_exact', 'role_text', 'aria_label', 'placeholder']
				for s in context.strategies_attempted
			)
			if semantic_failed and len(context.strategies_attempted) >= 3:
				return 'All semantic strategies failed - element may have changed structure but still exists. XPath fallback may succeed.'

		# Pattern 2: High verification failures
		if context.consecutive_verification_failures >= 2:
			return 'Actions are executing but not achieving expected results. Page behavior may have changed.'

		# Pattern 3: Validation errors
		if context.error_category == ErrorCategory.VALIDATION_ERROR:
			return 'Form validation is rejecting the input. Check validation rules and input data format.'

		# Pattern 4: Systematic failures
		if context.consecutive_failures >= 3:
			return 'Multiple consecutive failures indicate systematic issues. Workflow may need regeneration.'

		# Pattern 5: Element not found after multiple retries
		if context.error_category == ErrorCategory.ELEMENT_NOT_FOUND and context.retry_attempts > 1:
			return 'Element not found after multiple retries. Page structure likely changed or element is not visible.'

		return None

	def _truncate(self, text: str, max_len: int) -> str:
		"""Truncate text to max length with ellipsis."""
		if len(text) <= max_len:
			return text
		return text[: max_len - 3] + '...'

	def get_error_summary(self) -> Dict[str, Any]:
		"""
		Get summary statistics of all errors.

		Returns:
		    Dictionary with error statistics
		"""
		if not self.error_history:
			return {'total_errors': 0}

		return {
			'total_errors': len(self.error_history),
			'errors_by_category': {
				category.value: sum(1 for e in self.error_history if e.error_category == category) for category in ErrorCategory
			},
			'errors_by_step_type': {
				step_type: sum(1 for e in self.error_history if e.step_type == step_type)
				for step_type in set(e.step_type for e in self.error_history)
			},
			'most_recent_error': self.error_history[-1].error_message if self.error_history else None,
		}
