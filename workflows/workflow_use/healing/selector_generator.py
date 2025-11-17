"""
Multi-strategy selector generator for robust element finding.

This module generates multiple fallback strategies to find elements on a page,
reducing dependence on AI and making workflows more deterministic.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from workflow_use.healing.xpath_optimizer import XPathOptimizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SelectorStrategy:
	"""A single selector strategy with priority and metadata."""

	type: str  # Strategy type: 'id', 'css_attr', 'text_exact', 'aria', etc.
	value: str  # The selector value or matching text
	priority: int  # Lower = try first (1 is highest priority)
	metadata: Dict[str, Any] = field(default_factory=dict)  # Extra info for matching

	def to_dict(self) -> Dict[str, Any]:
		"""Convert to dictionary for JSON serialization."""
		return {
			'type': self.type,
			'value': self.value,
			'priority': self.priority,
			'metadata': self.metadata,
		}

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> 'SelectorStrategy':
		"""Create from dictionary."""
		return cls(
			type=data['type'],
			value=data['value'],
			priority=data['priority'],
			metadata=data.get('metadata', {}),
		)


class SelectorGenerator:
	"""
	Generate multiple robust selector strategies from element data.

	This class takes element data captured during workflow recording and generates
	a prioritized list of strategies to find that element during execution.

	The strategies are ordered by reliability:
	1. ID selectors (most stable)
	2. Data attributes (very stable)
	3. Name attributes (stable for forms)
	4. Exact text match (good for links/buttons)
	5. ARIA labels (accessibility-based)
	6. Role + text (semantic HTML)
	7. Placeholder (for inputs)
	8. Class + text combination
	9. Fuzzy text match (resilient to small changes)
	10. Direct CSS/xpath (fallback)
	"""

	def __init__(self, enable_xpath_optimization: bool = True, max_xpath_alternatives: int = 2, max_total_strategies: int = 2):
		"""
		Initialize the SelectorGenerator.

		Args:
		    enable_xpath_optimization: If True, use XPathOptimizer to generate multiple
		        robust XPath alternatives instead of a single XPath fallback
		    max_xpath_alternatives: Maximum number of XPath alternatives to generate (default: 2)
		        Includes the absolute xpath fallback, so 2 means 1 optimized + 1 absolute
		    max_total_strategies: Maximum total number of strategies to return (default: 2)
		        Limits the total number of strategies across all types (semantic + xpath)
		"""
		self.enable_xpath_optimization = enable_xpath_optimization
		self.max_xpath_alternatives = max_xpath_alternatives
		self.max_total_strategies = max_total_strategies
		self.xpath_optimizer = XPathOptimizer() if enable_xpath_optimization else None

	def generate_strategies(self, element_data: Dict[str, Any], include_xpath_fallback: bool = True) -> List[SelectorStrategy]:
		"""
		Generate selector strategies from captured element data.

		Generates semantic strategies first, then optionally adds XPath/CSS fallbacks.

		Args:
		    element_data: Dictionary containing:
		        - tag_name: str (e.g., 'a', 'button', 'input')
		        - text: str (visible text content)
		        - attributes: Dict[str, str] (element attributes)
		        - xpath: str (optional, pre-computed XPath)
		        - css_selector: str (optional, pre-computed CSS selector)
		    include_xpath_fallback: If True, include XPath and CSS selectors as fallbacks

		Returns:
		    List of SelectorStrategy objects, ordered by priority

		Example:
		    >>> generator = SelectorGenerator()
		    >>> strategies = generator.generate_strategies(
		    ...     {
		    ...         'tag_name': 'button',
		    ...         'text': 'Submit',
		    ...         'attributes': {'aria-label': 'Submit form'},
		    ...     }
		    ... )
		    >>> # Returns: text_exact, role_text, aria_label, text_fuzzy, xpath
		"""
		strategies = []
		tag = element_data.get('tag_name', '').lower()
		text = element_data.get('text', '').strip()
		attrs = element_data.get('attributes', {})

		# Strategy 1: Exact text match (highest priority - most reliable)
		if text:
			strategies.append(
				SelectorStrategy(
					type='text_exact',
					value=text,
					priority=1,
					metadata={'tag': tag},
				)
			)

		# Strategy 2: Role + text (semantic HTML)
		role = self._infer_role(tag, attrs)
		if role and text:
			strategies.append(
				SelectorStrategy(
					type='role_text',
					value=text,
					priority=2,
					metadata={'role': role, 'tag': tag},
				)
			)

		# Strategy 3: ARIA label (accessibility-based)
		if 'aria-label' in attrs and attrs['aria-label']:
			strategies.append(
				SelectorStrategy(
					type='aria_label',
					value=attrs['aria-label'],
					priority=3,
					metadata={'tag': tag},
				)
			)

		# Strategy 4: Placeholder (for input fields)
		if 'placeholder' in attrs and attrs['placeholder']:
			strategies.append(
				SelectorStrategy(
					type='placeholder',
					value=attrs['placeholder'],
					priority=4,
					metadata={'tag': tag},
				)
			)

		# Strategy 5: Title attribute (tooltip text)
		if 'title' in attrs and attrs['title']:
			strategies.append(
				SelectorStrategy(
					type='title',
					value=attrs['title'],
					priority=5,
					metadata={'tag': tag},
				)
			)

		# Strategy 6: Alt text (for images)
		if 'alt' in attrs and attrs['alt']:
			strategies.append(
				SelectorStrategy(
					type='alt_text',
					value=attrs['alt'],
					priority=6,
					metadata={'tag': tag},
				)
			)

		# Strategy 7: Fuzzy text match (fallback - handles typos/variations)
		if text and len(text) > 3:  # Only for meaningful text
			strategies.append(
				SelectorStrategy(
					type='text_fuzzy',
					value=text,
					priority=7,
					metadata={'threshold': 0.8, 'tag': tag},
				)
			)

		# Strategy 8: XPath fallback (lowest priority but most powerful)
		if include_xpath_fallback:
			if self.enable_xpath_optimization and self.xpath_optimizer:
				# NEW: Use XPathOptimizer to generate multiple robust XPath alternatives
				absolute_xpath = element_data.get('xpath', '')

				if absolute_xpath:
					# Prepare element info for optimizer
					element_info = {
						'tag': tag,
						'text': text,
						'attributes': attrs,
					}

					# Generate optimized XPath alternatives (limited to max_xpath_alternatives)
					try:
						optimized_xpaths = self.xpath_optimizer.optimize_xpath(
							absolute_xpath, element_info, max_alternatives=self.max_xpath_alternatives
						)

						# Add each optimized XPath with appropriate priority
						# Priority starts at 3 for most robust, increases for less robust
						base_priority = 3
						for i, opt_xpath in enumerate(optimized_xpaths):
							# Skip if this is the absolute xpath (we'll add it last)
							if opt_xpath == absolute_xpath and i < len(optimized_xpaths) - 1:
								continue

							# Determine priority based on XPath characteristics
							priority = self._calculate_xpath_priority(opt_xpath, is_absolute=(opt_xpath == absolute_xpath))

							# Determine strategy type
							strategy_name = self._determine_xpath_strategy(opt_xpath)

							strategies.append(
								SelectorStrategy(
									type='xpath',
									value=opt_xpath,
									priority=priority,
									metadata={
										'tag': tag,
										'strategy': strategy_name,
										'optimized': True,
										'index': i,
									},
								)
							)
					except Exception as e:
						logger.debug(f'XPath optimization failed, using fallback: {e}')
						# Fall back to simple XPath generation
						xpath = self._generate_xpath(tag, text, attrs)
						if xpath:
							strategies.append(
								SelectorStrategy(
									type='xpath',
									value=xpath,
									priority=8,
									metadata={'tag': tag, 'fallback': True},
								)
							)
				else:
					# No absolute xpath available, generate one
					xpath = self._generate_xpath(tag, text, attrs)
					if xpath:
						strategies.append(
							SelectorStrategy(
								type='xpath',
								value=xpath,
								priority=8,
								metadata={'tag': tag, 'fallback': True},
							)
						)
			else:
				# XPath optimization disabled, use original behavior
				xpath = element_data.get('xpath') or self._generate_xpath(tag, text, attrs)

				if xpath:
					strategies.append(
						SelectorStrategy(
							type='xpath',
							value=xpath,
							priority=8,
							metadata={'tag': tag, 'fallback': True},
						)
					)

		# Sort by priority (lower number = higher priority)
		strategies.sort(key=lambda s: s.priority)

		# Limit total number of strategies if configured
		if self.max_total_strategies and len(strategies) > self.max_total_strategies:
			logger.debug(f'Limiting strategies from {len(strategies)} to {self.max_total_strategies} (keeping highest priority)')
			strategies = strategies[: self.max_total_strategies]

		return strategies

	def _infer_role(self, tag: str, attrs: Dict[str, Any]) -> Optional[str]:
		"""
		Infer semantic role from HTML tag and attributes.

		Args:
		    tag: HTML tag name (e.g., 'button', 'a', 'input')
		    attrs: Element attributes

		Returns:
		    Semantic role string or None
		"""
		# Explicit role attribute takes precedence
		if 'role' in attrs:
			return attrs['role']

		# Infer from HTML tag
		role_map = {
			'button': 'button',
			'a': 'link',
			'input': 'textbox',
			'textarea': 'textbox',
			'select': 'combobox',
			'h1': 'heading',
			'h2': 'heading',
			'h3': 'heading',
			'h4': 'heading',
			'h5': 'heading',
			'h6': 'heading',
			'img': 'img',
			'table': 'table',
			'ul': 'list',
			'ol': 'list',
			'nav': 'navigation',
		}

		# Special case for input types
		if tag == 'input' and 'type' in attrs:
			input_type = attrs['type'].lower()
			if input_type == 'checkbox':
				return 'checkbox'
			elif input_type == 'radio':
				return 'radio'
			elif input_type == 'submit':
				return 'button'

		return role_map.get(tag)

	def _generate_xpath(self, tag: str, text: str, attrs: Dict[str, Any]) -> Optional[str]:
		"""
		Generate a robust XPath selector from element data.

		Args:
		    tag: HTML tag name
		    text: Element text content
		    attrs: Element attributes

		Returns:
		    XPath string or None
		"""
		try:
			xpath_parts = []

			# Start with tag
			if tag:
				xpath_parts.append(f'//{tag}')
			else:
				xpath_parts.append('//*')

			# Add attribute-based conditions (most reliable)
			conditions = []

			# ID is most stable
			if 'id' in attrs and attrs['id']:
				conditions.append(f'@id={self._escape_xpath_value(attrs["id"])}')

			# Name attribute (common for forms)
			elif 'name' in attrs and attrs['name']:
				conditions.append(f'@name={self._escape_xpath_value(attrs["name"])}')

			# Data attributes (very stable)
			elif any(k.startswith('data-') for k in attrs.keys()):
				for k, v in attrs.items():
					if k.startswith('data-') and v:
						conditions.append(f'@{k}={self._escape_xpath_value(v)}')
						break

			# ARIA label
			elif 'aria-label' in attrs and attrs['aria-label']:
				conditions.append(f'@aria-label={self._escape_xpath_value(attrs["aria-label"])}')

			# Placeholder
			elif 'placeholder' in attrs and attrs['placeholder']:
				conditions.append(f'@placeholder={self._escape_xpath_value(attrs["placeholder"])}')

			# Text content (fallback)
			elif text:
				# Use contains for more robustness
				conditions.append(f'contains(text(), {self._escape_xpath_value(text)})')

			# Combine conditions
			if conditions:
				xpath_parts.append('[' + ' and '.join(conditions) + ']')

			return ''.join(xpath_parts) if len(xpath_parts) > 1 else None

		except Exception as e:
			logger.debug(f'Failed to generate XPath: {e}')
			return None

	def _generate_css_selector(self, tag: str, text: str, attrs: Dict[str, Any]) -> Optional[str]:
		"""
		Generate a robust CSS selector from element data.

		Args:
		    tag: HTML tag name
		    text: Element text content
		    attrs: Element attributes

		Returns:
		    CSS selector string or None
		"""
		try:
			parts = []

			# Start with tag
			if tag:
				parts.append(tag)

			# Add ID (most specific)
			if 'id' in attrs and attrs['id']:
				# CSS escaping for IDs with special characters
				id_val = attrs['id'].replace(':', '\\:').replace('.', '\\.')
				parts.append(f'#{id_val}')
				return ''.join(parts)

			# Add name attribute
			if 'name' in attrs and attrs['name']:
				parts.append(f'[name="{self._escape_quotes(attrs["name"])}"]')
				return ''.join(parts)

			# Add data attributes (very stable)
			for k, v in attrs.items():
				if k.startswith('data-') and v:
					parts.append(f'[{k}="{self._escape_quotes(v)}"]')
					return ''.join(parts)

			# Add aria-label
			if 'aria-label' in attrs and attrs['aria-label']:
				parts.append(f'[aria-label="{self._escape_quotes(attrs["aria-label"])}"]')
				return ''.join(parts)

			# Add placeholder
			if 'placeholder' in attrs and attrs['placeholder']:
				parts.append(f'[placeholder="{self._escape_quotes(attrs["placeholder"])}"]')
				return ''.join(parts)

			# If we only have tag and no good attributes, return None
			# (CSS can't select by text content reliably)
			return ''.join(parts) if len(parts) > 1 else None

		except Exception as e:
			logger.debug(f'Failed to generate CSS selector: {e}')
			return None

	def _escape_xpath_value(self, value: str) -> str:
		"""
		Escape quotes in XPath values.

		Args:
		    value: String to escape

		Returns:
		    Escaped string suitable for XPath
		"""
		# If value contains single quotes, use double quotes
		if "'" in value:
			if '"' in value:
				# Both types of quotes - use concat
				parts = value.split("'")
				return "concat('" + "', \"'\", '".join(parts) + "')"
			else:
				return f'"{value}"'
		else:
			return f"'{value}'"

	def _escape_quotes(self, value: str) -> str:
		"""Escape quotes in CSS selector values."""
		return value.replace("'", "\\'").replace('"', '\\"')

	def _calculate_xpath_priority(self, xpath: str, is_absolute: bool = False) -> int:
		"""
		Calculate priority score based on XPath characteristics.

		Lower priority number = higher priority (tried first)

		Args:
		    xpath: The XPath string to evaluate
		    is_absolute: Whether this is an absolute XPath

		Returns:
		    Priority score (1-10, lower is better)
		"""
		# Absolute XPath = lowest priority (fallback only)
		if is_absolute or xpath.startswith('/html/body'):
			return 10

		# ID-based XPath = highest priority
		if '@id=' in xpath or '@id =' in xpath:
			return 2

		# Name attribute-based = very high priority
		if '@name=' in xpath or '@name =' in xpath:
			return 2

		# Data attributes = very high priority
		if '@data-' in xpath:
			return 2

		# ARIA attributes = high priority
		if '@aria-label=' in xpath or '@aria-labelledby=' in xpath or '@role=' in xpath:
			return 3

		# Table-anchored XPath = medium-high priority
		if '//table//' in xpath and ('tr[' in xpath or 'td[' in xpath):
			return 4

		# Form-anchored XPath = medium-high priority
		if '//form//' in xpath:
			return 4

		# Text-based in stable container = medium priority
		if ('//table//' in xpath or '//form//' in xpath or '//nav//' in xpath) and 'text()' in xpath:
			return 5

		# Class-based = medium-low priority (classes can be dynamic)
		if '@class=' in xpath or 'contains(@class' in xpath:
			return 6

		# Text-based without stable container = low priority
		if 'text()' in xpath or 'contains(text()' in xpath:
			return 7

		# Positional selectors = very low priority
		if '[' in xpath and ']' in xpath and xpath.count('[') > 1:
			return 8

		# Default: medium priority
		return 5

	def _determine_xpath_strategy(self, xpath: str) -> str:
		"""
		Determine the strategy type/name based on XPath characteristics.

		Args:
		    xpath: The XPath string to evaluate

		Returns:
		    Strategy name (e.g., 'id-based', 'table-anchored', 'text-based')
		"""
		if xpath.startswith('/html/body'):
			return 'absolute-fallback'

		if '@id=' in xpath or '@id =' in xpath:
			return 'id-based'

		if '@name=' in xpath or '@name =' in xpath:
			return 'name-based'

		if '@data-' in xpath:
			return 'data-attribute'

		if '@aria-label=' in xpath or '@aria-labelledby=' in xpath:
			return 'aria-based'

		if '@role=' in xpath:
			return 'role-based'

		if '//table//' in xpath and ('tr[' in xpath or 'td[' in xpath):
			return 'table-anchored'

		if '//form//' in xpath:
			return 'form-anchored'

		if '//nav//' in xpath:
			return 'nav-anchored'

		if 'text()=' in xpath:
			return 'text-exact'

		if 'contains(text()' in xpath:
			return 'text-contains'

		if '@class=' in xpath or 'contains(@class' in xpath:
			return 'class-based'

		if '[' in xpath and ']' in xpath:
			return 'positional'

		return 'relative-xpath'

	def generate_strategies_dict(self, element_data: Dict[str, Any]) -> List[Dict[str, Any]]:
		"""
		Generate strategies and return as list of dictionaries for JSON serialization.

		Args:
		    element_data: Element data dictionary

		Returns:
		    List of strategy dictionaries
		"""
		strategies = self.generate_strategies(element_data)
		return [s.to_dict() for s in strategies]

	def get_summary(self, strategies: List[SelectorStrategy]) -> str:
		"""
		Get a human-readable summary of strategies.

		Args:
		    strategies: List of selector strategies

		Returns:
		    Summary string

		Example:
		    >>> generator = SelectorGenerator()
		    >>> strategies = generator.generate_strategies({...})
		    >>> print(generator.get_summary(strategies))
		    Generated 5 selector strategies:
		      1. [priority 1] id: #submit-btn
		      2. [priority 4] text_exact: "Submit"
		      ...
		"""
		lines = [f'Generated {len(strategies)} selector strategies:']
		for i, s in enumerate(strategies[:5], 1):  # Show first 5
			value_preview = s.value[:50] + '...' if len(s.value) > 50 else s.value
			lines.append(f'  {i}. [priority {s.priority}] {s.type}: {value_preview}')
		if len(strategies) > 5:
			lines.append(f'  ... and {len(strategies) - 5} more')
		return '\n'.join(lines)
