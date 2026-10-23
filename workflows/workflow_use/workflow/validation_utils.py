"""
Shared utilities for detecting validation errors on web pages.

This module provides common functionality for identifying form validation errors
and other error messages displayed on web pages.
"""

import logging
from typing import List, Optional, Tuple

from workflow_use.compat import cdp

logger = logging.getLogger(__name__)

# Common CSS selectors for error messages across different frameworks and patterns
VALIDATION_ERROR_SELECTORS = [
	'.error',
	'.error-message',
	'.validation-error',
	'.field-error',
	'[role="alert"]',
	'.alert-danger',
	'.text-red',
	'.text-error',
	'.invalid-feedback',
	'.form-error',
	'.help-block.error',
]

# Strings that indicate framework/browser internals rather than user-facing errors
_INTERNAL_PATTERNS = [
	'document.getElementById',
	'function addPageBinding',
	'serializeAsCallArgument',
	'__next_f',
	'globalThis',
	'self.__next_f',
]

# One page round-trip: collect the visible text of every matching error element.
_COLLECT_ERRORS_JS = """(selectors) => {
	const out = [];
	for (const selector of selectors) {
		let nodes = [];
		try { nodes = document.querySelectorAll(selector); } catch (e) { continue; }
		for (const node of nodes) {
			const rect = node.getBoundingClientRect();
			const style = getComputedStyle(node);
			const visible = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
			if (!visible) continue;
			const text = (node.textContent || '').trim();
			if (text) out.push(text);
		}
	}
	return out;
}"""


def _clean_error_texts(raw_texts: List[str]) -> List[str]:
	"""Filter out framework internals / oversized blobs, dedupe preserving order."""
	errors: List[str] = []
	for text in raw_texts:
		clean_text = text.strip()
		if not clean_text:
			continue
		# Skip if it looks like browser internal code
		if any(pattern in clean_text for pattern in _INTERNAL_PATTERNS):
			continue
		# Skip very long messages (likely technical content, not user-facing errors)
		if len(clean_text) > 200:
			continue
		if clean_text not in errors:
			errors.append(clean_text)
	return errors


async def _collect_visible_error_texts(page) -> List[str]:
	result = await cdp.evaluate(page, _COLLECT_ERRORS_JS, VALIDATION_ERROR_SELECTORS)
	if not isinstance(result, list):
		return []
	return _clean_error_texts([str(item) for item in result])


async def detect_validation_errors(page) -> Tuple[bool, Optional[str]]:
	"""
	Detect validation errors on the page using common error selectors.

	This function checks for visible error messages using standard CSS selectors
	that are commonly used across different web frameworks (Bootstrap, Tailwind, etc.).

	Args:
	    page: browser-use actor Page object

	Returns:
	    Tuple of (has_errors: bool, error_message: Optional[str])
	    - has_errors: True if validation errors were found
	    - error_message: Text of the first error found, or None if no errors

	Example:
	    has_errors, error_text = await detect_validation_errors(page)
	    if has_errors:
	        print(f"Validation error: {error_text}")
	"""
	try:
		errors = await _collect_visible_error_texts(page)
		if errors:
			return True, errors[0]
		return False, None
	except Exception as e:
		# If we can't check for errors, assume no errors to avoid blocking
		logger.debug(f'Validation-error detection failed: {e}')
		return False, None


async def get_all_validation_errors(page) -> List[str]:
	"""
	Get all validation error messages visible on the page.

	Args:
	    page: browser-use actor Page object

	Returns:
	    List of error message strings (may be empty if no errors found)

	Example:
	    errors = await get_all_validation_errors(page)
	    for error in errors:
	        print(f"Error: {error}")
	"""
	try:
		return await _collect_visible_error_texts(page)
	except Exception as e:
		logger.debug(f'Validation-error collection failed: {e}')
		return []
