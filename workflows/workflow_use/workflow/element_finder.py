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
		self, strategies: List[Dict[str, Any]], browser_session: Any
	) -> Tuple[Optional[tuple[int, Dict[str, Any]]], List[StrategyAttempt]]:
		"""
		Try strategies to find element index in browser-use's DOM state.

		This method tries semantic strategies first by searching browser-use's DOM state,
		then falls back to XPath execution via Playwright if semantic strategies fail.

		Args:
		    strategies: List of strategy dictionaries with 'type', 'value', 'priority', 'metadata'
		    browser_session: Browser-use BrowserSession object

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

		# Get current DOM state from browser-use
		try:
			state = await browser_session.get_state()
			if not state or not state.selector_map:
				logger.warning('      ⚠️  No DOM state available')
				return None, strategy_attempts
		except Exception as e:
			logger.warning(f'      ⚠️  Failed to get DOM state: {e}')
			return None, strategy_attempts

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

				# Handle XPath strategies separately (requires Playwright)
				if strategy_type == 'xpath':
					result = await self._find_with_xpath(strategy_value, state, browser_session)
					if result:
						index, _ = result
						logger.info(f'         ✅ Found with XPath at index {index}')
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
						return (index, strategy), strategy_attempts
					else:
						error_msg = 'XPath query returned no results'
						logger.debug(f'         ⏭️  {error_msg}')

				else:
					# Search through browser-use's selector_map using semantic matching
					for index, node in state.selector_map.items():
						if await self._matches_strategy(node, strategy_type, strategy_value, metadata):
							logger.info(f'         ✅ Found with {strategy_type} at index {index}')
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
							return (index, strategy), strategy_attempts

					error_msg = 'No matching element found in DOM'
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

	async def _matches_strategy(self, node: Any, strategy_type: str, value: str, metadata: Dict[str, Any]) -> bool:
		"""
		Check if a DOM node matches a semantic strategy.

		Args:
		    node: EnhancedDOMTreeNode from browser-use
		    strategy_type: Type of strategy (text_exact, role_text, etc.)
		    value: Value to match
		    metadata: Additional matching metadata

		Returns:
		    True if node matches the strategy
		"""
		try:
			# Semantic Strategy 1: Exact text match
			if strategy_type == 'text_exact':
				node_text = getattr(node, 'text', '') or ''
				return node_text.strip() == value

			# Semantic Strategy 2: Role + text
			elif strategy_type == 'role_text':
				expected_role = metadata.get('role', '').lower()
				node_role = getattr(node, 'role', '') or getattr(node, 'tag_name', '')
				node_role = node_role.lower()
				node_text = getattr(node, 'text', '') or ''

				return node_role == expected_role and node_text.strip() == value

			# Semantic Strategy 3: ARIA label
			elif strategy_type == 'aria_label':
				aria_label = getattr(node, 'aria_label', '') or ''
				return aria_label.strip() == value

			# Semantic Strategy 4: Placeholder
			elif strategy_type == 'placeholder':
				placeholder = getattr(node, 'placeholder', '') or ''
				return placeholder.strip() == value

			# Semantic Strategy 5: Title attribute
			elif strategy_type == 'title':
				title = getattr(node, 'title', '') or ''
				return title.strip() == value

			# Semantic Strategy 6: Alt text (images)
			elif strategy_type == 'alt_text':
				alt = getattr(node, 'alt', '') or ''
				return alt.strip() == value

			# Semantic Strategy 7: Fuzzy text match
			elif strategy_type == 'text_fuzzy':
				threshold = metadata.get('threshold', 0.8)
				node_text = getattr(node, 'text', '') or ''
				return self._fuzzy_match(value, node_text.strip(), threshold)

			# Note: XPath and CSS strategies are handled separately in find_element_with_strategies
			# They cannot be matched against browser-use's node representation

		except Exception as e:
			logger.debug(f'Error matching strategy: {e}')
			return False

		return False

	async def _find_with_xpath(self, xpath: str, state: Any, browser_session: Any) -> Optional[tuple[int, Any]]:
		"""
		Find element using XPath and map it to browser-use's index.

		Args:
		    xpath: XPath selector
		    state: Current browser-use DOM state
		    browser_session: Browser-use session object

		Returns:
		    Tuple of (element_index, node) if found, None otherwise
		"""
		try:
			# Get the Playwright page from browser_session
			page = await browser_session.get_current_page()
			if not page:
				logger.debug('No Playwright page available for XPath execution')
				return None

			# Execute XPath query to find element
			element = await page.query_selector(f'xpath={xpath}')
			if not element:
				logger.debug(f'XPath query returned no results: {xpath}')
				return None

			# Get element properties to match against browser-use's nodes
			try:
				# Get text content, tag name, and attributes
				element_data = await page.evaluate(
					"""(el) => {
						return {
							text: el.textContent?.trim() || '',
							tagName: el.tagName?.toLowerCase() || '',
							id: el.id || '',
							className: el.className || '',
							ariaLabel: el.getAttribute('aria-label') || '',
							placeholder: el.getAttribute('placeholder') || '',
							name: el.getAttribute('name') || '',
							boundingBox: el.getBoundingClientRect ? {
								x: el.getBoundingClientRect().x,
								y: el.getBoundingClientRect().y,
								width: el.getBoundingClientRect().width,
								height: el.getBoundingClientRect().height
							} : null
						};
					}""",
					element,
				)

				# Try to find matching node in browser-use's selector_map
				for index, node in state.selector_map.items():
					if self._xpath_node_matches(node, element_data):
						logger.debug(f'Matched XPath element to index {index}')
						return (index, node)

				logger.debug('XPath found element but could not match to browser-use index')

			except Exception as e:
				logger.debug(f'Error extracting element data: {e}')

		except Exception as e:
			logger.debug(f'Error executing XPath: {e}')

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
