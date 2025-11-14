"""
Multi-strategy element finder for robust workflow execution.

This module provides fallback strategies to find elements on a page,
reducing failures when page structure changes.

Uses semantic strategies with XPath fallback.
Leverages browser-use's existing semantic finding through the controller.
"""

import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from workflow_use.workflow.error_reporter import StrategyAttempt

logger = logging.getLogger(__name__)


class ElementFinder:
	"""
	Find elements using multiple semantic fallback strategies.

	This class works WITH browser-use's controller, not instead of it.
	The controller already does excellent semantic element finding - we just
	provide a faster path when we have semantic hints from workflow recording.
	"""

	async def find_element_with_strategies(
		self, strategies: List[Dict[str, Any]], browser_session: Any, target_text: Optional[str] = None
	) -> Tuple[Optional[tuple[int, Dict[str, Any]]], List[StrategyAttempt]]:
		"""
		Try strategies to find element index in browser-use's DOM state.

		This method tries semantic strategies first by searching browser-use's DOM state,
		then falls back to XPath execution via Playwright if semantic strategies fail.

		Args:
		    strategies: List of strategy dictionaries with 'type', 'value', 'priority', 'metadata'
		    browser_session: Browser-use BrowserSession object
		    target_text: Optional target text to validate element existence

		Returns:
		    Tuple of:
		        - (element_index, strategy_used) if found, None if all strategies fail
		        - List of StrategyAttempt records for error reporting

		Example:
		    >>> finder = ElementFinder()
		    >>> result, attempts = await finder.find_element_with_strategies(strategies, browser_session)
		"""
		strategy_attempts: List[StrategyAttempt] = []

		if not strategies:
			return None, strategy_attempts

		# Get current page from browser-use
		try:
			page = await browser_session.get_current_page()
			if not page:
				logger.warning('      ⚠️  No page available')
				return None, strategy_attempts
		except Exception as e:
			logger.warning(f'      ⚠️  Failed to get current page: {e}')
			return None, strategy_attempts

		# Get selector map for semantic strategies
		selector_map = None
		try:
			selector_map = await browser_session.get_selector_map()
			if selector_map:
				logger.debug(f'      📋 Retrieved selector map with {len(selector_map)} elements')
		except Exception as e:
			logger.debug(f'      ⚠️  Could not get selector map: {e}')

		# Sort by priority (should already be sorted, but ensure it)
		sorted_strategies = sorted(strategies, key=lambda s: s.get('priority', 999))

		for i, strategy in enumerate(sorted_strategies, 1):
			strategy_type = strategy.get('type')
			strategy_value = strategy.get('value', '')
			priority = strategy.get('priority', 999)
			metadata = strategy.get('metadata', {})
			error_msg = None

			try:
				logger.info(f'      🔍 Strategy {i}/{len(sorted_strategies)}: {strategy_type}')

				# Try XPath strategies via Playwright
				if strategy_type == 'xpath':
					result = await self._find_with_xpath(strategy_value, page, browser_session, target_text)
					if result:
						xpath_string, xpath_used = result
						logger.info('         ✅ Found element with XPath')
						# Record successful attempt
						strategy_attempts.append(
							StrategyAttempt(
								strategy_type=strategy_type,
								strategy_value=strategy_value,
								priority=priority,
								success=True,
								metadata=metadata,
							)
						)
						# Return XPath string for semantic_executor.py to use in JavaScript click
						# Note: This differs from semantic strategies which return element_index for service.py
						return (xpath_string, strategy), strategy_attempts
					else:
						error_msg = 'XPath query returned no results'
						logger.debug(f'         ⏭️  {error_msg}')

				# Try semantic strategies using selector map
				elif selector_map and strategy_type in [
					'text_exact',
					'role_text',
					'aria_label',
					'placeholder',
					'title',
					'alt_text',
					'text_fuzzy',
				]:
					result = await self._find_with_semantic_strategy(
						strategy_type, strategy_value, metadata, selector_map, target_text
					)
					if result:
						element_index, matched_element = result
						logger.info(f'         ✅ Found element with {strategy_type}')
						# Record successful attempt
						strategy_attempts.append(
							StrategyAttempt(
								strategy_type=strategy_type,
								strategy_value=strategy_value,
								priority=priority,
								success=True,
								metadata=metadata,
							)
						)
						return (element_index, strategy), strategy_attempts
					else:
						error_msg = 'No matching element found in DOM'
						logger.debug(f'         ⏭️  {error_msg}')

				else:
					# Strategy type not supported or no selector map available
					if not selector_map:
						error_msg = 'Selector map not available for semantic strategy'
					else:
						error_msg = f'Strategy type "{strategy_type}" not supported'
					logger.debug(f'         ⏭️  {error_msg}')

			except Exception as e:
				error_msg = str(e)
				logger.debug(f'         ❌ Error with {strategy_type}: {e}')

			# Record failed attempt
			strategy_attempts.append(
				StrategyAttempt(
					strategy_type=strategy_type,
					strategy_value=strategy_value,
					priority=priority,
					success=False,
					error_message=error_msg,
					metadata=metadata,
				)
			)

		# All strategies failed
		logger.warning(f'      ❌ All {len(sorted_strategies)} strategies failed')
		return None, strategy_attempts

	async def _find_with_semantic_strategy(
		self,
		strategy_type: str,
		strategy_value: str,
		metadata: Dict[str, Any],
		selector_map: Dict[str, Any],
		target_text: Optional[str] = None,
	) -> Optional[tuple[int, Dict[str, Any]]]:
		"""
		Find element using semantic strategy in browser-use's selector map.

		Args:
		    strategy_type: Type of semantic strategy (text_exact, role_text, etc.)
		    strategy_value: Value to match
		    metadata: Additional matching metadata
		    selector_map: Browser-use's selector map (dict of index -> element)
		    target_text: Optional target text for validation

		Returns:
		    Tuple of (element_index, element_data) if found, None otherwise
		"""
		try:
			# Iterate through selector map to find matching element
			for index, element in selector_map.items():
				# Handle both dict and object formats
				if isinstance(element, dict):
					node = element
				else:
					# Convert object to dict-like access
					node = element

				# Check if element matches the strategy
				if await self._matches_strategy(node, strategy_type, strategy_value, metadata):
					# Validate element exists and is visible
					if await self._validate_element_in_map(index, node, target_text):
						return (int(index), node)

			return None

		except Exception as e:
			logger.debug(f'Error finding element with semantic strategy: {e}')
			return None

	async def _validate_element_in_map(self, index: int, node: Any, target_text: Optional[str] = None) -> bool:
		"""
		Validate that element in selector map is visible and optionally matches target_text.

		Args:
		    index: Element index in browser-use's selector map
		    node: Browser-use DOM element (dict or object)
		    target_text: Optional text to validate

		Returns:
		    True if element is valid and visible
		"""
		try:
			# Helper to get attribute from dict or object
			def get_attr(obj, attr, default=''):
				if isinstance(obj, dict):
					return obj.get(attr, default)
				return getattr(obj, attr, default)

			# Check if node is visible - this is a hard requirement
			is_visible = get_attr(node, 'is_visible', True)
			if not is_visible:
				logger.debug(f'Element at index {index} is not visible')
				return False

			# If target_text is provided, validate it (advisory only)
			if target_text:
				target_lower = target_text.lower().strip()

				# Collect all text sources from the element
				text_sources = []

				# Get element's visible text
				node_text = get_attr(node, 'text', '') or ''
				if node_text:
					text_sources.append(node_text.lower().strip())

				# Get aria-label
				aria_label = get_attr(node, 'aria_label', '') or ''
				if aria_label:
					text_sources.append(aria_label.lower().strip())

				# Get placeholder
				placeholder = get_attr(node, 'placeholder', '') or ''
				if placeholder:
					text_sources.append(placeholder.lower().strip())

				# Get title
				title = get_attr(node, 'title', '') or ''
				if title:
					text_sources.append(title.lower().strip())

				# Get alt text
				alt = get_attr(node, 'alt', '') or ''
				if alt:
					text_sources.append(alt.lower().strip())

				# Get name attribute
				attrs = get_attr(node, 'attributes', {}) or {}
				if isinstance(attrs, dict) and 'name' in attrs:
					text_sources.append(attrs['name'].lower().strip())

				# Check if target_text matches any text source
				found_match = any(target_lower in source or source in target_lower for source in text_sources if source)

				if not found_match:
					logger.debug(
						f'⚠️ Target text "{target_text}" not found in element at index {index}, but proceeding with selector.'
					)
				else:
					logger.debug(f'✓ Target text "{target_text}" validated in element at index {index}')

			return True

		except Exception as e:
			logger.debug(f'Error validating element at index {index}: {e}')
			return False

	async def _matches_strategy(self, node: Any, strategy_type: str, value: str, metadata: Dict[str, Any]) -> bool:
		"""
		Check if a DOM node matches a semantic strategy.

		Args:
		    node: EnhancedDOMTreeNode from browser-use (dict or object)
		    strategy_type: Type of strategy (text_exact, role_text, etc.)
		    value: Value to match
		    metadata: Additional matching metadata

		Returns:
		    True if node matches the strategy
		"""
		try:
			# Helper to get attribute from dict or object
			def get_attr(obj, attr, default=''):
				if isinstance(obj, dict):
					return obj.get(attr, default)
				return getattr(obj, attr, default)

			# Semantic Strategy 1: Exact text match
			if strategy_type == 'text_exact':
				node_text = get_attr(node, 'text', '') or ''
				return node_text.strip() == value

			# Semantic Strategy 2: Role + text
			elif strategy_type == 'role_text':
				expected_role = metadata.get('role', '').lower()
				node_role = get_attr(node, 'role', '') or get_attr(node, 'tag_name', '')
				node_role = node_role.lower() if node_role else ''
				node_text = get_attr(node, 'text', '') or ''

				return node_role == expected_role and node_text.strip() == value

			# Semantic Strategy 3: ARIA label
			elif strategy_type == 'aria_label':
				aria_label = get_attr(node, 'aria_label', '') or ''
				return aria_label.strip() == value

			# Semantic Strategy 4: Placeholder
			elif strategy_type == 'placeholder':
				placeholder = get_attr(node, 'placeholder', '') or ''
				return placeholder.strip() == value

			# Semantic Strategy 5: Title attribute
			elif strategy_type == 'title':
				title = get_attr(node, 'title', '') or ''
				return title.strip() == value

			# Semantic Strategy 6: Alt text (images)
			elif strategy_type == 'alt_text':
				alt = get_attr(node, 'alt', '') or ''
				return alt.strip() == value

			# Semantic Strategy 7: Fuzzy text match
			elif strategy_type == 'text_fuzzy':
				threshold = metadata.get('threshold', 0.8)
				node_text = get_attr(node, 'text', '') or ''
				return self._fuzzy_match(value, node_text.strip(), threshold)

			# Note: XPath and CSS strategies are handled separately in find_element_with_strategies
			# They cannot be matched against browser-use's node representation

		except Exception as e:
			logger.debug(f'Error matching strategy: {e}')
			return False

		return False

	async def _validate_element_exists(
		self, index: int, node: Any, browser_session: Any, target_text: Optional[str] = None
	) -> bool:
		"""
		Validate that element exists, is visible, and optionally matches target_text.

		Args:
		    index: Element index in browser-use's selector map
		    node: Browser-use DOM node
		    browser_session: Browser-use session object
		    target_text: Optional text to validate against element's text/label/aria-label/placeholder
		                 If provided, we log a warning if text doesn't match but still allow the element

		Returns:
		    True if element is valid and visible (text matching is advisory only)
		"""
		try:
			# Check if node is visible - this is a hard requirement
			is_visible = getattr(node, 'is_visible', True)
			if not is_visible:
				logger.debug(f'Element at index {index} is not visible')
				return False

			# If target_text is provided, validate it exists in the element's text sources
			# BUT: This is advisory only - we log a warning but don't fail validation
			# The target_text might be a descriptive label, not actual visible text
			if target_text:
				target_lower = target_text.lower().strip()

				# Collect all text sources from the element
				text_sources = []

				# Get element's visible text
				node_text = getattr(node, 'text', '') or ''
				if node_text:
					text_sources.append(node_text.lower().strip())

				# Get aria-label
				aria_label = getattr(node, 'aria_label', '') or ''
				if aria_label:
					text_sources.append(aria_label.lower().strip())

				# Get placeholder
				placeholder = getattr(node, 'placeholder', '') or ''
				if placeholder:
					text_sources.append(placeholder.lower().strip())

				# Get title
				title = getattr(node, 'title', '') or ''
				if title:
					text_sources.append(title.lower().strip())

				# Get alt text
				alt = getattr(node, 'alt', '') or ''
				if alt:
					text_sources.append(alt.lower().strip())

				# Get name attribute
				attrs = getattr(node, 'attributes', {}) or {}
				if 'name' in attrs:
					text_sources.append(attrs['name'].lower().strip())

				# Check if target_text matches any text source
				found_match = any(target_lower in source or source in target_lower for source in text_sources if source)

				if not found_match:
					# Don't fail - just log a warning
					# The XPath/CSS selector is more authoritative than target_text hint
					logger.debug(
						f'⚠️ Target text "{target_text}" not found in element at index {index}, but proceeding with selector. '
						f'Available text sources: {text_sources}'
					)
				else:
					logger.debug(f'✓ Target text "{target_text}" validated in element at index {index}')

			return True

		except Exception as e:
			logger.debug(f'Error validating element at index {index}: {e}')
			return False

	async def _find_with_xpath(
		self, xpath: str, page: Any, browser_session: Any, target_text: Optional[str] = None
	) -> Optional[tuple[Any, str]]:
		"""
		Find element using XPath via JavaScript evaluation.

		Args:
		    xpath: XPath selector
		    page: Browser-use Page object
		    browser_session: Browser-use session object
		    target_text: Optional target text for validation

		Returns:
		    Tuple of (xpath, xpath_used) if found, None otherwise
		    Note: Returns xpath string, not element object, since we'll click via JS
		"""
		try:
			# Normalize XPath: ensure it starts with / for absolute paths
			normalized_xpath = xpath
			if xpath and not xpath.startswith('/') and not xpath.startswith('('):
				normalized_xpath = '/' + xpath
				logger.info(f'         🔧 Normalized XPath to: {normalized_xpath}')

			logger.info(f'         🔎 Executing XPath: {normalized_xpath}')

			# Execute XPath query via JavaScript to find element
			# Escape the XPath for safe JavaScript string usage
			escaped_xpath = normalized_xpath.replace("'", "\\'")
			js_code = f"""() => {{
	try {{
		const result = document.evaluate(
			'{escaped_xpath}',
			document,
			null,
			XPathResult.FIRST_ORDERED_NODE_TYPE,
			null
		);

		const element = result.singleNodeValue;
		if (!element) {{
			return null;
		}}

		// Check if element is visible
		const rect = element.getBoundingClientRect();
		const style = window.getComputedStyle(element);
		const isVisible = rect.width > 0 && rect.height > 0 &&
		                  style.visibility !== 'hidden' &&
		                  style.display !== 'none';

		return {{
			found: true,
			visible: isVisible,
			tag: element.tagName,
			text: element.textContent?.trim() || '',
			xpath: '{escaped_xpath}'
		}};
	}} catch (error) {{
		return {{ error: error.message }};
	}}
}}"""

			result = await page.evaluate(js_code)

			if not result:
				logger.info('         ⚠️  XPath evaluation returned null')
				return None

			if isinstance(result, dict) and result.get('error'):
				logger.warning(f'         ❌ XPath evaluation error: {result["error"]}')
				return None

			if not isinstance(result, dict) or not result.get('found'):
				logger.info('         ⚠️  XPath returned no results')
				return None

			if not result.get('visible'):
				logger.info('         ⚠️  Element found but not visible')
				return None

			logger.info(f'         ✅ Found visible element: <{result["tag"]}>')
			# Return the xpath itself since we'll execute click via JavaScript
			return (normalized_xpath, normalized_xpath)

		except Exception as e:
			logger.warning(f'         ❌ Error executing XPath: {e}')
			return None

	def _xpath_node_matches(self, node: Any, element_data: Dict[str, Any]) -> bool:
		"""
		Check if a browser-use node matches element data from XPath query.

		Args:
		    node: Browser-use EnhancedDOMTreeNode
		    element_data: Element data from Playwright evaluation

		Returns:
		    True if they match
		"""
		try:
			# Match by multiple properties for higher confidence
			matches = 0
			checks = 0

			# Check tag name
			node_tag = getattr(node, 'tag_name', '').lower()
			if node_tag and element_data.get('tagName'):
				checks += 1
				if node_tag == element_data['tagName']:
					matches += 1

			# Check text content (allow partial match for robustness)
			node_text = (getattr(node, 'text', '') or '').strip()
			element_text = element_data.get('text', '').strip()
			if node_text and element_text:
				checks += 1
				if node_text == element_text or element_text in node_text or node_text in element_text:
					matches += 1

			# Check ID
			node_id = getattr(node, 'element_id', '') or ''
			if node_id and element_data.get('id'):
				checks += 1
				if node_id == element_data['id']:
					matches += 2  # ID is a strong indicator

			# Check aria-label
			node_aria = getattr(node, 'aria_label', '') or ''
			if node_aria and element_data.get('ariaLabel'):
				checks += 1
				if node_aria == element_data['ariaLabel']:
					matches += 1

			# Check placeholder
			node_placeholder = getattr(node, 'placeholder', '') or ''
			if node_placeholder and element_data.get('placeholder'):
				checks += 1
				if node_placeholder == element_data['placeholder']:
					matches += 1

			# Check name attribute
			node_attrs = getattr(node, 'attributes', {}) or {}
			if 'name' in node_attrs and element_data.get('name'):
				checks += 1
				if node_attrs['name'] == element_data['name']:
					matches += 1

			# Require at least 2 matches or 1 strong match (ID)
			return matches >= 2 or (matches > 0 and checks > 0 and matches / checks >= 0.7)

		except Exception as e:
			logger.debug(f'Error matching xpath node: {e}')
			return False

	def _fuzzy_match(self, target: str, candidate: str, threshold: float = 0.8) -> bool:
		"""
		Check if two strings match with fuzzy matching.

		Args:
		    target: The target string to match
		    candidate: The candidate string to check
		    threshold: Similarity threshold (0-1), default 0.8

		Returns:
		    True if similarity >= threshold
		"""
		ratio = SequenceMatcher(None, target.lower(), candidate.lower()).ratio()
		return ratio >= threshold
