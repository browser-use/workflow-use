"""
XPath optimizer for generating robust, maintainable XPath selectors.

This module takes absolute XPaths (captured during recording) and optimizes them
to be more resilient to page structure changes while maintaining accuracy.
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def escape_xpath_string(value: str) -> str:
	"""
	Escape a string value for safe use in XPath expressions.

	XPath 1.0 doesn't have a native escape mechanism for quotes, so we use concat()
	when the string contains single quotes.

	Args:
	    value: The string value to escape

	Returns:
	    Escaped string safe for XPath, or concat() expression if needed

	Examples:
	    >>> escape_xpath_string('hello')
	    "'hello'"
	    >>> escape_xpath_string("it's")
	    'concat("it", "\'", "s")'
	    >>> escape_xpath_string('say "hello"')
	    '\'say "hello"\''
	"""
	if not value:
		return "''"

	# If no single quotes, use single quotes (simple case)
	if "'" not in value:
		return f"'{value}'"

	# If no double quotes, use double quotes
	if '"' not in value:
		return f'"{value}"'

	# Contains both single and double quotes - use concat()
	# Split by single quote and build concat expression
	parts = value.split("'")
	concat_parts = []
	for i, part in enumerate(parts):
		if part:
			# Use double quotes for parts that don't contain quotes
			concat_parts.append(f'"{part}"')
		if i < len(parts) - 1:
			# Add the single quote separator
			concat_parts.append('"\'"')

	return f'concat({", ".join(concat_parts)})'


class XPathOptimizer:
	"""
	Optimize XPath selectors for robustness and maintainability.

	Converts brittle absolute XPaths into smart relative XPaths that:
	1. Use stable attributes (id, name, data-*, aria-*, role)
	2. Leverage semantic structure (tables, forms, lists)
	3. Minimize depth dependency
	4. Include fallback strategies
	"""

	def optimize_xpath(self, absolute_xpath: str, element_info: Optional[Dict] = None, max_alternatives: int = 2) -> List[str]:
		"""
		Generate optimized XPath alternatives from an absolute XPath.

		Args:
		    absolute_xpath: Full XPath like /html/body/div[1]/div[2]/table/tbody/tr[3]/td[2]/a
		    element_info: Optional dict with element details (tag, text, attributes, etc.)
		    max_alternatives: Maximum number of alternatives to return (default: 2)
		        - If max_alternatives <= 1: Returns ONLY the absolute xpath (no optimized alternatives)
		        - If max_alternatives >= 2: Returns best N-1 optimized alternatives + absolute xpath fallback

		Returns:
		    List of XPath alternatives (exactly max_alternatives), ordered from most to least robust

		Examples:
		    >>> optimizer = XPathOptimizer()

		    >>> # max_alternatives=1 returns only absolute xpath
		    >>> xpaths = optimizer.optimize_xpath(xpath, element_info, max_alternatives=1)
		    >>> # Returns: [original_xpath]

		    >>> # max_alternatives=2 returns 1 optimized + 1 absolute
		    >>> xpaths = optimizer.optimize_xpath(
		    ...     '/html/body/form/div[3]/table/tbody/tr[2]/td[3]/a',
		    ...     {'tag': 'a', 'text': '12345', 'attributes': {'class': 'license-link'}},
		    ...     max_alternatives=2,
		    ... )
		    >>> # Returns: [
		    ...     '//table//tr[2]/td[3]/a',  # Best optimized
		    ...     original_xpath              # Absolute fallback
		    ... ]

		    >>> # max_alternatives=3 returns 2 optimized + 1 absolute
		    >>> xpaths = optimizer.optimize_xpath(xpath, element_info, max_alternatives=3)
		    >>> # Returns: [optimized_1, optimized_2, original_xpath]
		"""
		alternatives = []

		# Parse the absolute XPath
		parts = self._parse_xpath(absolute_xpath)

		# Strategy 1: Use element attributes (highest priority)
		if element_info:
			attr_xpaths = self._generate_attribute_based_xpaths(element_info, parts)
			alternatives.extend(attr_xpaths)

		# Strategy 2: Anchor to stable parent structures
		anchored_xpaths = self._generate_anchored_xpaths(parts, element_info)
		alternatives.extend(anchored_xpaths)

		# Strategy 3: Use position within stable containers
		positional_xpaths = self._generate_positional_xpaths(parts, element_info)
		alternatives.extend(positional_xpaths)

		# Strategy 4: Shortened absolute path (remove volatile parents)
		shortened_xpath = self._shorten_absolute_xpath(parts)
		if shortened_xpath and shortened_xpath != absolute_xpath:
			alternatives.append(shortened_xpath)

		# Remove duplicates while preserving order
		seen = set()
		unique_alternatives = []
		for xpath in alternatives:
			if xpath not in seen and xpath != absolute_xpath:
				seen.add(xpath)
				unique_alternatives.append(xpath)

		logger.debug(
			f'XPath optimizer: Generated {len(unique_alternatives)} unique alternatives before limiting (max_alternatives={max_alternatives})'
		)

		# Limit alternatives based on max_alternatives setting
		if max_alternatives <= 1:
			# If max is 1 or less, return ONLY the absolute xpath (no optimized alternatives)
			unique_alternatives = [absolute_xpath]
		else:
			# Otherwise, keep best N-1 optimized alternatives and add absolute xpath as fallback
			unique_alternatives = unique_alternatives[: max_alternatives - 1]
			unique_alternatives.append(absolute_xpath)

		logger.debug(f'XPath optimizer: Returning {len(unique_alternatives)} alternatives (limit={max_alternatives})')

		return unique_alternatives

	def _parse_xpath(self, xpath: str) -> List[Dict]:
		"""
		Parse XPath into structured parts.

		Args:
		    xpath: XPath string like /html/body/div[3]/table/tbody/tr[2]/td[1]/a

		Returns:
		    List of dicts: [
		        {'tag': 'html', 'index': None},
		        {'tag': 'body', 'index': None},
		        {'tag': 'div', 'index': 3},
		        ...
		    ]
		"""
		parts = []

		# Remove leading slash
		xpath = xpath.lstrip('/')

		# Split by /
		segments = xpath.split('/')

		for segment in segments:
			# Extract tag and index
			match = re.match(r'^([a-zA-Z0-9_-]+)(?:\[(\d+)\])?$', segment)
			if match:
				tag = match.group(1)
				index = int(match.group(2)) if match.group(2) else None
				parts.append({'tag': tag, 'index': index, 'original': segment})

		return parts

	def _generate_attribute_based_xpaths(self, element_info: Dict, parts: List[Dict]) -> List[str]:
		"""
		Generate XPaths using element attributes.

		Priority order:
		1. id (most stable)
		2. name (stable for forms)
		3. data-* attributes (very stable)
		4. aria-* attributes (semantic, stable)
		5. unique class combinations
		6. text content
		"""
		xpaths = []
		tag = element_info.get('tag', '*').lower()
		attrs = element_info.get('attributes', {})
		text = element_info.get('text', '').strip()

		# 1. ID selector (highest priority)
		if attrs.get('id'):
			escaped_id = escape_xpath_string(attrs['id'])
			xpaths.append(f'//{tag}[@id={escaped_id}]')

		# 2. Name attribute (good for forms)
		if attrs.get('name'):
			escaped_name = escape_xpath_string(attrs['name'])
			xpaths.append(f'//{tag}[@name={escaped_name}]')

		# 3. Data attributes (very stable, often unique)
		for attr_name, attr_value in attrs.items():
			if attr_name.startswith('data-') and attr_value:
				escaped_value = escape_xpath_string(attr_value)
				xpaths.append(f'//{tag}[@{attr_name}={escaped_value}]')

		# 4. ARIA attributes (semantic, stable)
		if attrs.get('aria-label'):
			escaped_label = escape_xpath_string(attrs['aria-label'])
			xpaths.append(f'//{tag}[@aria-label={escaped_label}]')
		if attrs.get('aria-labelledby'):
			escaped_labelledby = escape_xpath_string(attrs['aria-labelledby'])
			xpaths.append(f'//{tag}[@aria-labelledby={escaped_labelledby}]')

		# 5. Role attribute
		if attrs.get('role'):
			escaped_role = escape_xpath_string(attrs['role'])
			if text:
				escaped_text = escape_xpath_string(text)
				xpaths.append(f'//{tag}[@role={escaped_role} and contains(text(), {escaped_text})]')
			else:
				xpaths.append(f'//{tag}[@role={escaped_role}]')

		# 6. Unique class combinations
		if attrs.get('class'):
			classes = attrs['class'].split()
			# Try single unique class first
			for cls in classes:
				if cls and not cls.startswith('css-'):  # Skip dynamic classes
					escaped_class = escape_xpath_string(cls)
					xpaths.append(f'//{tag}[contains(@class, {escaped_class})]')
					break  # Only try first non-dynamic class

		# 7. Text content
		if text:
			escaped_text = escape_xpath_string(text)
			# Exact text
			xpaths.append(f'//{tag}[text()={escaped_text}]')
			# Contains text (more flexible)
			if len(text) > 3:
				xpaths.append(f'//{tag}[contains(text(), {escaped_text})]')

		return xpaths

	def _generate_anchored_xpaths(self, parts: List[Dict], element_info: Optional[Dict]) -> List[str]:
		"""
		Generate XPaths anchored to stable parent structures.

		Stable structures include:
		- Tables (//table//tr[2]/td[3]/a)
		- Forms (//form[@name='search']//input)
		- Nav (//nav//a[text()='Home'])
		- Sections with IDs
		"""
		xpaths = []

		# Find stable anchor points in the path
		anchor_tags = {'table', 'form', 'nav', 'header', 'footer', 'section', 'article', 'aside', 'main'}

		for i, part in enumerate(parts):
			if part['tag'] in anchor_tags:
				# Build path from this anchor point
				target_tag = parts[-1]['tag'] if parts else '*'
				relative_path = self._build_relative_path(parts[i:])

				# Simple anchor
				xpaths.append(f'//{part["tag"]}{relative_path}')

				# If we have element info, add context
				if element_info and element_info.get('text'):
					text = element_info['text']
					escaped_text = escape_xpath_string(text)
					xpaths.append(f'//{part["tag"]}//{target_tag}[contains(text(), {escaped_text})]')

		# Special case: Table cell targeting
		if len(parts) >= 3:
			# Check if path contains table -> tr -> td pattern
			for i in range(len(parts) - 2):
				if (
					parts[i]['tag'] == 'table'
					and any(p['tag'] == 'tr' for p in parts[i:])
					and any(p['tag'] == 'td' for p in parts[i:])
				):
					# Find tr and td indices
					tr_idx = next((p['index'] for p in parts[i:] if p['tag'] == 'tr' and p['index']), None)
					td_idx = next((p['index'] for p in parts[i:] if p['tag'] == 'td' and p['index']), None)

					if tr_idx and td_idx:
						target_tag = parts[-1]['tag']
						xpaths.append(f'//table//tr[{tr_idx}]/td[{td_idx}]//{target_tag}')
						xpaths.append(f'//table//tr[{tr_idx}]/td[{td_idx}]/{target_tag}')

		return xpaths

	def _generate_positional_xpaths(self, parts: List[Dict], element_info: Optional[Dict]) -> List[str]:
		"""
		Generate XPaths using position within containers.

		Examples:
		- (//table//a)[2] - Second link in any table
		- //form//button[last()] - Last button in form
		"""
		xpaths = []

		if not parts:
			return xpaths

		target_tag = parts[-1]['tag']

		# Find if target is in a table
		has_table = any(p['tag'] == 'table' for p in parts)
		if has_table and element_info:
			# Position within table
			xpaths.append(f'(//table//{target_tag})[1]')  # First occurrence

		return xpaths

	def _build_relative_path(self, parts: List[Dict]) -> str:
		"""
		Build relative path from parsed parts.

		Args:
		    parts: List of path segments

		Returns:
		    Relative XPath string like //tr[2]/td[3]/a
		"""
		path_segments = []

		for part in parts[1:]:  # Skip first part (already used as anchor)
			segment = f'//{part["tag"]}' if not path_segments else f'/{part["tag"]}'
			if part['index']:
				segment += f'[{part["index"]}]'
			path_segments.append(segment)

		return ''.join(path_segments)

	def _shorten_absolute_xpath(self, parts: List[Dict]) -> Optional[str]:
		"""
		Shorten absolute XPath by removing volatile parent elements.

		Strategy:
		1. Keep stable anchors (table, form, main, section with clear purpose)
		2. Remove middle divs/spans (most volatile)
		3. Keep last 2-3 levels for specificity

		Args:
		    parts: Parsed XPath parts

		Returns:
		    Shortened XPath or None
		"""
		if len(parts) <= 4:
			return None  # Already short enough

		# Find last stable anchor
		stable_tags = {'html', 'body', 'table', 'form', 'nav', 'header', 'footer', 'main'}
		last_stable_idx = 0

		for i, part in enumerate(parts):
			if part['tag'] in stable_tags:
				last_stable_idx = i

		# Keep last stable anchor + last 3 elements
		if last_stable_idx < len(parts) - 3:
			keep_from = max(last_stable_idx, len(parts) - 3)
			shortened_parts = parts[keep_from:]

			# Build shortened path
			path = '/' + '/'.join(p['original'] for p in shortened_parts)
			return path

		return None
