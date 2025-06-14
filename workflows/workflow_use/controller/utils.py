import logging
import re

logger = logging.getLogger(__name__)


def truncate_selector(selector: str, max_length: int = 35) -> str:
	"""Truncate a CSS selector to a maximum length, adding ellipsis if truncated."""
	return selector if len(selector) <= max_length else f'{selector[:max_length]}...'


async def get_best_element_handle(page, selector, params=None, timeout_ms=100):
	"""Find element using stability-ranked selector strategies."""
	original_selector = selector

	# Generate stability-ranked fallback selectors
	fallbacks = generate_stable_selectors(selector, params)

	# Try all selectors with exponential backoff for timeouts
	selectors_to_try = [original_selector] + fallbacks

	for try_selector in selectors_to_try:
		try:
			logger.info(f'Trying selector: {truncate_selector(try_selector)}')
			locator = page.locator(try_selector)
			await locator.wait_for(state='visible', timeout=timeout_ms)
			logger.info(f'Found element with selector: {truncate_selector(try_selector)}')
			return locator, try_selector
		except Exception as e:
			logger.error(f'Selector failed: {truncate_selector(try_selector)} with error: {e}')

	# Try XPath as last resort
	if params and getattr(params, 'xpath', None):
		xpath = params.xpath
		try:
			# Generate stable XPath alternatives
			xpath_alternatives = [xpath] + generate_stable_xpaths(xpath, params)

			for try_xpath in xpath_alternatives:
				xpath_selector = f'xpath={try_xpath}'
				logger.info(f'Trying XPath: {truncate_selector(xpath_selector)}')
				locator = page.locator(xpath_selector)
				await locator.wait_for(state='visible', timeout=timeout_ms)
				return locator, xpath_selector
		except Exception as e:
			logger.error(f'All XPaths failed with error: {e}')

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

	# 5. Use text-based selector if we have element tag and text
	if params and getattr(params, 'elementTag', None) and getattr(params, 'elementText', None) and params.elementText.strip():
		fallbacks.append(f"{params.elementTag}:has-text('{params.elementText}')")

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
