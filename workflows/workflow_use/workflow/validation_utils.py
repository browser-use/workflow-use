"""
Shared utilities for detecting validation errors on web pages.

This module provides common functionality for identifying form validation errors
and other error messages displayed on web pages.
"""

from typing import List, Optional, Tuple

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


async def detect_validation_errors(page) -> Tuple[bool, Optional[str]]:
	"""
	Detect validation errors on the page using common error selectors.

	This function checks for visible error messages using standard CSS selectors
	that are commonly used across different web frameworks (Bootstrap, Tailwind, etc.).

	Args:
	    page: Playwright Page object

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
		for selector in VALIDATION_ERROR_SELECTORS:
			try:
				elements = await page.query_selector_all(selector)
				if elements:
					# Check if any are visible
					for elem in elements:
						is_visible = await elem.is_visible()
						if is_visible:
							text = await elem.text_content()
							if text and text.strip():
								# Filter out browser internal scripts and technical content
								clean_text = text.strip()

								# Skip if it looks like browser internal code
								if any(
									pattern in clean_text
									for pattern in [
										'document.getElementById',
										'function addPageBinding',
										'serializeAsCallArgument',
										'__next_f',
										'globalThis',
										'self.__next_f',
									]
								):
									continue

								# Skip very long messages (likely technical content, not user-facing errors)
								if len(clean_text) > 200:
									continue

								return True, clean_text
			except Exception:
				# Ignore errors for individual selectors, try next one
				continue

		return False, None

	except Exception as e:
		# If we can't check for errors, assume no errors to avoid blocking
		return False, None


async def get_all_validation_errors(page) -> List[str]:
	"""
	Get all validation error messages visible on the page.

	Args:
	    page: Playwright Page object

	Returns:
	    List of error message strings (may be empty if no errors found)

	Example:
	    errors = await get_all_validation_errors(page)
	    for error in errors:
	        print(f"Error: {error}")
	"""
	errors = []

	try:
		for selector in VALIDATION_ERROR_SELECTORS:
			try:
				elements = await page.query_selector_all(selector)
				if elements:
					for elem in elements:
						is_visible = await elem.is_visible()
						if is_visible:
							text = await elem.text_content()
							if text and text.strip():
								clean_text = text.strip()

								# Skip browser internal code
								if any(
									pattern in clean_text
									for pattern in [
										'document.getElementById',
										'function addPageBinding',
										'serializeAsCallArgument',
										'__next_f',
										'globalThis',
										'self.__next_f',
									]
								):
									continue

								# Skip very long messages
								if len(clean_text) > 200:
									continue

								if clean_text not in errors:  # Avoid duplicates
									errors.append(clean_text)
			except Exception:
				continue
	except Exception:
		pass

	return errors
