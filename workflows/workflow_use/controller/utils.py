import logging
import re

from workflow_use.compat import cdp

logger = logging.getLogger(__name__)


def truncate_selector(selector: str, max_length: int = 35) -> str:
	"""Truncate a CSS selector to a maximum length, adding ellipsis if truncated."""
	return selector if len(selector) <= max_length else f'{selector[:max_length]}...'


async def _find_by_tag_and_text(page, tag: str, text: str, timeout_ms: float):
	"""Text-based fallback: match a *tag* element by its recorded text.

	Delegates to the compat finder: one page-side pass over ALL candidates
	(rendered innerText plus aria-label/title/placeholder/value), polled until
	*timeout_ms* so late-rendering elements are still found. (Replaces the
	Playwright-only text pseudo-class, which is not valid CSS.)
	"""
	if not text.strip():
		return None
	return await cdp.find_element_by_text(page, tag, text, timeout_ms=timeout_ms)


async def get_best_element_handle(page, selector, params=None, timeout_ms=100):
	"""Find an element using stability-ranked selector strategies.

	Returns ``(element, selector_used)`` where *element* is a browser-use actor
	``Element``. Raises when every strategy fails.
	"""
	original_selector = selector

	# Generate stability-ranked fallback selectors
	fallbacks = generate_stable_selectors(selector, params)

	selectors_to_try = [original_selector] + fallbacks

	for try_selector in selectors_to_try:
		logger.info(f'Trying selector: {truncate_selector(try_selector)}')
		element = await cdp.wait_for_element(page, try_selector, timeout_ms=timeout_ms)
		if element is not None:
			logger.info(f'Found element with selector: {truncate_selector(try_selector)}')
			return element, try_selector
		logger.debug(f'Selector failed: {truncate_selector(try_selector)}')

	# Text-based fallback (tag + recorded element text)
	element_tag = params.elementTag if params and getattr(params, 'elementTag', None) else None
	element_text = params.elementText if params and getattr(params, 'elementText', None) else None
	if element_tag and element_text and element_text.strip():
		logger.info(f'Trying text fallback: <{element_tag}> containing "{element_text.strip()[:35]}"')
		element = await _find_by_tag_and_text(page, element_tag.lower(), element_text, timeout_ms)
		if element is not None:
			return element, f'{element_tag.lower()}:text({element_text.strip()[:35]})'

	# Try XPath as last resort
	if params and getattr(params, 'xpath', None):
		xpath_alternatives = [params.xpath] + generate_stable_xpaths(params.xpath, params)
		for try_xpath in xpath_alternatives:
			xpath_selector = f'xpath={try_xpath}'
			logger.info(f'Trying XPath: {truncate_selector(xpath_selector)}')
			element = await cdp.get_element_by_xpath(page, try_xpath, timeout_ms=timeout_ms)
			if element is not None:
				return element, xpath_selector
			logger.debug(f'XPath failed: {truncate_selector(xpath_selector)}')

	raise Exception(f'Failed to find element. Original: {original_selector}')


def generate_stable_selectors(selector, params=None):
	"""Generate selectors from most to least stable based on selector patterns."""
	fallbacks = []

	# 1. Extract attribute-based selectors (most stable)
	attributes_to_check = [
		'placeholder',
		'aria-label',
		'name',
		'title',
		'role',
		'data-testid',
	]
	for attr in attributes_to_check:
		attr_pattern = rf'\[{attr}\*?=[\'"]([^\'"]*)[\'"]'
		attr_match = re.search(attr_pattern, selector)
		if attr_match:
			attr_value = attr_match.group(1)
			element_tag = extract_element_tag(selector, params)
			if element_tag:
				fallbacks.append(f'{element_tag}[{attr}*="{attr_value}"]')

	# 2. Combine tag + class + one attribute (good stability)
	element_tag = extract_element_tag(selector, params)
	classes = extract_stable_classes(selector)
	for attr in attributes_to_check:
		attr_pattern = rf'\[{attr}\*?=[\'"]([^\'"]*)[\'"]'
		attr_match = re.search(attr_pattern, selector)
		if attr_match and classes and element_tag:
			attr_value = attr_match.group(1)
			class_selector = '.'.join(classes)
			fallbacks.append(f'{element_tag}.{class_selector}[{attr}*="{attr_value}"]')

	# 3. Tag + class combination (less stable but often works)
	if element_tag and classes:
		class_selector = '.'.join(classes)
		fallbacks.append(f'{element_tag}.{class_selector}')

	# 4. Remove dynamic parts (IDs, state classes)
	if '[id=' in selector:
		fallbacks.append(re.sub(r'\[id=[\'"].*?[\'"]\]', '', selector))

	for state in ['.focus-visible', '.hover', '.active', '.focus', ':focus']:
		if state in selector:
			fallbacks.append(selector.replace(state, ''))

	# NOTE: text-based fallback lives in get_best_element_handle/_find_by_tag_and_text;
	# Playwright's :has-text() pseudo-class is not valid CSS on the CDP surface.

	return list(dict.fromkeys(fallbacks))  # Remove duplicates while preserving order


def extract_element_tag(selector, params=None):
	"""Extract element tag from selector or params."""
	# Try to get from selector first
	tag_match = re.match(r'^([a-zA-Z][a-zA-Z0-9]*)', selector)
	if tag_match:
		return tag_match.group(1).lower()

	# Fall back to params
	if params and getattr(params, 'elementTag', None):
		return params.elementTag.lower()

	return ''


def extract_stable_classes(selector):
	"""Extract classes that appear to be stable (not state-related)."""
	class_pattern = r'\.([a-zA-Z0-9_-]+)'
	classes = re.findall(class_pattern, selector)

	# Filter out likely state classes
	stable_classes = [
		cls
		for cls in classes
		if not any(state in cls.lower() for state in ['focus', 'hover', 'active', 'selected', 'checked', 'disabled'])
	]

	return stable_classes


def generate_stable_xpaths(xpath, params=None):
	"""Generate stable XPath alternatives."""
	alternatives = []

	# Handle "id()" XPath pattern which is brittle
	if 'id(' in xpath:
		element_tag = getattr(params, 'elementTag', '').lower()
		if element_tag:
			# Create XPaths based on attributes from params
			if params and getattr(params, 'cssSelector', None):
				for attr in ['placeholder', 'aria-label', 'title', 'name']:
					attr_pattern = rf'\[{attr}\*?=[\'"]([^\'"]*)[\'"]'
					attr_match = re.search(attr_pattern, params.cssSelector)
					if attr_match:
						attr_value = attr_match.group(1)
						alternatives.append(f"//{element_tag}[contains(@{attr}, '{attr_value}')]")

	return alternatives
