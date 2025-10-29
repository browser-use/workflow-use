"""
Multi-strategy element finder for robust workflow execution.

This module provides fallback strategies to find elements on a page,
reducing failures when page structure changes.

Uses SEMANTIC-ONLY strategies - no CSS selectors, no xpaths.
Leverages browser-use's existing semantic finding through the controller.
"""

import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

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
	) -> Optional[tuple[int, Dict[str, Any]]]:
		"""
		Try SEMANTIC-ONLY strategies to find element index in browser-use's DOM state.

		This method uses the semantic strategies to search through browser-use's
		already-indexed DOM state, then returns the index that the controller expects.

		Args:
		    strategies: List of strategy dictionaries with 'type', 'value', 'priority', 'metadata'
		    browser_session: Browser-use BrowserSession object

		Returns:
		    Tuple of (element_index, strategy_used) if found, None if all strategies fail

		Example:
		    >>> finder = ElementFinder()
		    >>> index, strategy = await finder.find_element_with_strategies(strategies, browser_session)
		"""
		if not strategies:
			return None

		# Get current DOM state from browser-use
		try:
			state = await browser_session.get_state()
			if not state or not state.selector_map:
				logger.warning('      ⚠️  No DOM state available')
				return None
		except Exception as e:
			logger.warning(f'      ⚠️  Failed to get DOM state: {e}')
			return None

		# Sort by priority (should already be sorted, but ensure it)
		sorted_strategies = sorted(strategies, key=lambda s: s.get('priority', 999))

		for i, strategy in enumerate(sorted_strategies, 1):
			try:
				strategy_type = strategy.get('type')
				strategy_value = strategy.get('value')
				metadata = strategy.get('metadata', {})

				logger.info(f'      🔍 Strategy {i}/{len(sorted_strategies)}: {strategy_type}')

				# Search through browser-use's selector_map using semantic matching
				for index, node in state.selector_map.items():
					if await self._matches_strategy(node, strategy_type, strategy_value, metadata):
						logger.info(f'         ✅ Found with {strategy_type} at index {index}')
						return (index, strategy)

				logger.debug(f'         ⏭️  No match with {strategy_type}')

			except Exception as e:
				logger.debug(f'         ❌ Error with {strategy_type}: {e}')
				continue

		# All strategies failed
		logger.warning(f'      ❌ All {len(sorted_strategies)} strategies failed')
		return None

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

		except Exception as e:
			logger.debug(f'Error matching strategy: {e}')
			return False

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
