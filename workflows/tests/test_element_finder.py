"""
Unit tests for ElementFinder - Semantic matching against DOM state.

Tests that ElementFinder correctly searches browser-use's DOM state using semantic strategies
and returns element indices (not Playwright element handles).
"""

from unittest.mock import AsyncMock, Mock

from workflow_use.workflow.element_finder import ElementFinder


class TestElementFinder:
	"""Test ElementFinder semantic matching"""

	def setup_method(self):
		"""Setup test fixture"""
		self.finder = ElementFinder()

	# Test 1: Find element by text_exact strategy
	async def test_find_by_text_exact(self):
		"""Test finding element using text_exact strategy"""
		# Mock browser session with DOM state
		mock_session = Mock()
		mock_state = Mock()

		# Create mock DOM nodes
		mock_nodes = {
			1: Mock(text='Cancel', tag_name='button'),
			2: Mock(text='Submit', tag_name='button'),  # Should match
			3: Mock(text='Back', tag_name='a'),
		}
		mock_state.selector_map = mock_nodes
		mock_session.get_state = AsyncMock(return_value=mock_state)

		# Strategy to find "Submit"
		strategies = [{'type': 'text_exact', 'value': 'Submit', 'priority': 1, 'metadata': {}}]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is not None, 'Should find element'
		index, strategy_used = result
		assert index == 2, f'Expected index 2, got {index}'
		assert strategy_used['type'] == 'text_exact', 'Should use text_exact strategy'

	# Test 2: Find element by role_text strategy
	async def test_find_by_role_text(self):
		"""Test finding element using role + text strategy"""
		mock_session = Mock()
		mock_state = Mock()

		# Create mock DOM nodes
		mock_nodes = {
			1: Mock(text='Submit', tag_name='button', role='button'),  # Should match
			2: Mock(text='Submit', tag_name='a', role='link'),  # Wrong role
		}
		mock_state.selector_map = mock_nodes
		mock_session.get_state = AsyncMock(return_value=mock_state)

		# Strategy to find button with text "Submit"
		strategies = [{'type': 'role_text', 'value': 'Submit', 'priority': 2, 'metadata': {'role': 'button'}}]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is not None, 'Should find element'
		index, strategy_used = result
		assert index == 1, f'Expected index 1, got {index}'

	# Test 3: Find element by aria_label strategy
	async def test_find_by_aria_label(self):
		"""Test finding element using aria-label strategy"""
		mock_session = Mock()
		mock_state = Mock()

		mock_nodes = {
			1: Mock(aria_label='Close dialog', tag_name='button'),  # Should match
			2: Mock(aria_label='Open menu', tag_name='button'),
		}
		mock_state.selector_map = mock_nodes
		mock_session.get_state = AsyncMock(return_value=mock_state)

		strategies = [{'type': 'aria_label', 'value': 'Close dialog', 'priority': 3, 'metadata': {}}]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is not None, 'Should find element'
		index, _ = result
		assert index == 1, f'Expected index 1, got {index}'

	# Test 4: Find element by placeholder strategy
	async def test_find_by_placeholder(self):
		"""Test finding element using placeholder strategy"""
		mock_session = Mock()
		mock_state = Mock()

		mock_nodes = {
			1: Mock(placeholder='Enter your name', tag_name='input'),
			2: Mock(placeholder='Enter your email', tag_name='input'),  # Should match
		}
		mock_state.selector_map = mock_nodes
		mock_session.get_state = AsyncMock(return_value=mock_state)

		strategies = [{'type': 'placeholder', 'value': 'Enter your email', 'priority': 4, 'metadata': {}}]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is not None, 'Should find element'
		index, _ = result
		assert index == 2, f'Expected index 2, got {index}'

	# Test 5: Find element by title strategy
	async def test_find_by_title(self):
		"""Test finding element using title attribute strategy"""
		mock_session = Mock()
		mock_state = Mock()

		mock_nodes = {
			1: Mock(title='Click to close', tag_name='button'),  # Should match
			2: Mock(title='Click to submit', tag_name='button'),
		}
		mock_state.selector_map = mock_nodes
		mock_session.get_state = AsyncMock(return_value=mock_state)

		strategies = [{'type': 'title', 'value': 'Click to close', 'priority': 5, 'metadata': {}}]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is not None, 'Should find element'
		index, _ = result
		assert index == 1, f'Expected index 1, got {index}'

	# Test 6: Find element by alt_text strategy
	async def test_find_by_alt_text(self):
		"""Test finding element using alt text strategy (for images)"""
		mock_session = Mock()
		mock_state = Mock()

		mock_nodes = {
			1: Mock(alt='Company logo', tag_name='img'),  # Should match
			2: Mock(alt='User avatar', tag_name='img'),
		}
		mock_state.selector_map = mock_nodes
		mock_session.get_state = AsyncMock(return_value=mock_state)

		strategies = [{'type': 'alt_text', 'value': 'Company logo', 'priority': 6, 'metadata': {}}]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is not None, 'Should find element'
		index, _ = result
		assert index == 1, f'Expected index 1, got {index}'

	# Test 7: Fuzzy text matching
	async def test_find_by_fuzzy_text(self):
		"""Test finding element using fuzzy text matching"""
		mock_session = Mock()
		mock_state = Mock()

		# "Submit" vs "Submit Form" has ratio 0.70, so use lower threshold or closer match
		mock_nodes = {
			1: Mock(text='Submitt', tag_name='button'),  # Typo - ratio ~0.92, should match with threshold 0.8
		}
		mock_state.selector_map = mock_nodes
		mock_session.get_state = AsyncMock(return_value=mock_state)

		strategies = [{'type': 'text_fuzzy', 'value': 'Submit', 'priority': 7, 'metadata': {'threshold': 0.8}}]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is not None, 'Should find element with fuzzy matching'
		index, _ = result
		assert index == 1, f'Expected index 1, got {index}'

	# Test 8: Multiple strategies fallback (priority order)
	async def test_multiple_strategies_fallback(self):
		"""Test that strategies are tried in priority order (lower priority = try first)"""
		mock_session = Mock()
		mock_state = Mock()

		mock_nodes = {
			1: Mock(text='Not this one', tag_name='button', aria_label='Close'),
			2: Mock(text='Submit', tag_name='button', aria_label='Submit'),  # Should match on text_exact (priority 1)
		}
		mock_state.selector_map = mock_nodes
		mock_session.get_state = AsyncMock(return_value=mock_state)

		# Strategies in reverse order (should still try priority 1 first)
		strategies = [
			{'type': 'aria_label', 'value': 'Close', 'priority': 3, 'metadata': {}},  # Would match index 1
			{'type': 'text_exact', 'value': 'Submit', 'priority': 1, 'metadata': {}},  # Should match index 2 first
		]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is not None, 'Should find element'
		index, strategy_used = result
		# Should use text_exact (priority 1) and find index 2
		assert index == 2, f'Expected index 2 (priority 1 strategy), got {index}'
		assert strategy_used['type'] == 'text_exact', 'Should use highest priority strategy'

	# Test 9: No match returns None
	async def test_no_match_returns_none(self):
		"""Test that None is returned when no strategy matches"""
		mock_session = Mock()
		mock_state = Mock()

		mock_nodes = {
			1: Mock(text='Cancel', tag_name='button'),
			2: Mock(text='Back', tag_name='a'),
		}
		mock_state.selector_map = mock_nodes
		mock_session.get_state = AsyncMock(return_value=mock_state)

		# Strategy looking for non-existent text
		strategies = [{'type': 'text_exact', 'value': 'Submit', 'priority': 1, 'metadata': {}}]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is None, 'Should return None when no match found'

	# Test 10: Empty strategies list returns None
	async def test_empty_strategies_returns_none(self):
		"""Test that None is returned when strategies list is empty"""
		mock_session = Mock()

		result = await self.finder.find_element_with_strategies([], mock_session)

		assert result is None, 'Should return None for empty strategies'

	# Test 11: No DOM state returns None
	async def test_no_dom_state_returns_none(self):
		"""Test that None is returned when DOM state is not available"""
		mock_session = Mock()
		mock_session.get_state = AsyncMock(return_value=None)

		strategies = [{'type': 'text_exact', 'value': 'Submit', 'priority': 1, 'metadata': {}}]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is None, 'Should return None when DOM state is not available'

	# Test 12: Empty selector_map returns None
	async def test_empty_selector_map_returns_none(self):
		"""Test that None is returned when selector_map is empty"""
		mock_session = Mock()
		mock_state = Mock()
		mock_state.selector_map = {}  # Empty
		mock_session.get_state = AsyncMock(return_value=mock_state)

		strategies = [{'type': 'text_exact', 'value': 'Submit', 'priority': 1, 'metadata': {}}]

		result = await self.finder.find_element_with_strategies(strategies, mock_session)

		assert result is None, 'Should return None when selector_map is empty'

	# Test 13: Fuzzy matching threshold
	async def test_fuzzy_matching_threshold(self):
		"""Test that fuzzy matching respects threshold"""
		# Test _fuzzy_match directly
		# "Submit" vs "Submit" = 1.0 (exact)
		assert self.finder._fuzzy_match('Submit', 'Submit', 0.8), 'Exact match should pass'

		# "Submit" vs "Submitt" = ~0.92 (typo)
		assert self.finder._fuzzy_match('Submit', 'Submitt', 0.8), 'Close match with typo should pass'

		# "Submit" vs "Submit Form" = ~0.70 (extra words - below 0.8)
		# This should fail with threshold 0.8, or pass with lower threshold
		assert self.finder._fuzzy_match('Submit', 'Submit Form', 0.7), 'Partial match should pass with lower threshold'
		assert not self.finder._fuzzy_match('Submit', 'Submit Form', 0.8), 'Partial match should fail with threshold 0.8'

		# Very different text
		assert not self.finder._fuzzy_match('Submit', 'Completely Different', 0.8), 'Very different should fail'

	# Test 14: Case insensitivity in fuzzy matching
	async def test_fuzzy_matching_case_insensitive(self):
		"""Test that fuzzy matching is case insensitive"""
		assert self.finder._fuzzy_match('Submit', 'SUBMIT', 0.9), 'Should be case insensitive'
		assert self.finder._fuzzy_match('Submit', 'submit', 0.9), 'Should be case insensitive'


# Helper to run async tests
import asyncio


def run_async_test(test_method):
	"""Helper to run async test methods"""
	return asyncio.run(test_method())


if __name__ == '__main__':
	# Run all tests
	test = TestElementFinder()
	test_methods = [m for m in dir(test) if m.startswith('test_')]

	print(f'\n{"=" * 80}')
	print(f'Running {len(test_methods)} tests for ElementFinder')
	print(f'{"=" * 80}\n')

	passed = 0
	failed = 0

	for method_name in test_methods:
		test.setup_method()  # Setup for each test
		method = getattr(test, method_name)
		try:
			# Run async or sync test
			if asyncio.iscoroutinefunction(method):
				run_async_test(method)
			else:
				method()

			print(f'✅ PASS: {method_name}')
			passed += 1
		except AssertionError as e:
			print(f'❌ FAIL: {method_name}')
			print(f'   {str(e)}')
			failed += 1
		except Exception as e:
			print(f'❌ ERROR: {method_name}')
			print(f'   {str(e)}')
			import traceback

			traceback.print_exc()
			failed += 1

	print(f'\n{"=" * 80}')
	print(f'Test Results: {passed} passed, {failed} failed')
	print(f'{"=" * 80}\n')

	exit(0 if failed == 0 else 1)
