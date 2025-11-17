"""
Unit tests for XPath optimization in SelectorGenerator.

Tests that SelectorGenerator with xpath optimization enabled generates
multiple robust XPath alternatives instead of a single brittle absolute XPath.
"""

from workflow_use.healing.selector_generator import SelectorGenerator
from workflow_use.healing.xpath_optimizer import XPathOptimizer


class TestXPathOptimization:
	"""Test XPath optimization in SelectorGenerator"""

	def setup_method(self):
		"""Setup test fixture"""
		# NOTE: max_total_strategies=None means no global limit (for testing XPath optimization specifically)
		self.generator_with_optimization = SelectorGenerator(enable_xpath_optimization=True, max_total_strategies=None)
		self.generator_without_optimization = SelectorGenerator(enable_xpath_optimization=False, max_total_strategies=None)
		self.optimizer = XPathOptimizer()

	# ============================================================================
	# Test 1: XPath Optimization Enabled - Limited XPath Strategies
	# ============================================================================
	def test_xpath_optimization_generates_limited_strategies(self):
		"""Test that XPath optimization generates limited XPath strategies (max 2)"""
		# Absolute XPath for a table link (brittle)
		absolute_xpath = '/html/body/form/div[3]/div/div/table/tbody/tr[2]/td[3]/a'

		element_data = {
			'tag_name': 'a',
			'text': 'License 12345',
			'attributes': {'class': 'license-link', 'href': '/license/12345'},
			'xpath': absolute_xpath,
		}

		strategies = self.generator_with_optimization.generate_strategies(element_data)

		# Filter to XPath strategies only
		xpath_strategies = [s for s in strategies if s.type == 'xpath']

		# Should generate exactly 2 XPath alternatives (1 optimized + 1 absolute)
		assert len(xpath_strategies) == 2, f'Expected exactly 2 XPath strategies, got {len(xpath_strategies)}'

		# Should include at least one optimized strategy
		optimized_strategies = [s for s in xpath_strategies if s.metadata.get('optimized')]
		assert len(optimized_strategies) > 0, 'Should have at least one optimized XPath strategy'

		# Last one should be the absolute xpath
		assert xpath_strategies[-1].value == absolute_xpath, 'Last XPath should be absolute fallback'

	# ============================================================================
	# Test 2: XPath Optimization Disabled - Single XPath Strategy
	# ============================================================================
	def test_xpath_optimization_disabled_generates_single_strategy(self):
		"""Test that without optimization, only one XPath strategy is generated"""
		absolute_xpath = '/html/body/form/div[3]/div/div/table/tbody/tr[2]/td[3]/a'

		element_data = {
			'tag_name': 'a',
			'text': 'License 12345',
			'attributes': {'class': 'license-link'},
			'xpath': absolute_xpath,
		}

		strategies = self.generator_without_optimization.generate_strategies(element_data)

		# Filter to XPath strategies only
		xpath_strategies = [s for s in strategies if s.type == 'xpath']

		# Should generate only one XPath strategy (fallback only)
		assert len(xpath_strategies) == 1, f'Expected 1 XPath strategy, got {len(xpath_strategies)}'

	# ============================================================================
	# Test 3: Priority Calculation - ID-based XPath
	# ============================================================================
	def test_priority_calculation_id_based(self):
		"""Test that ID-based XPath gets high priority (low number)"""
		xpath = "//button[@id='submit-btn']"
		priority = self.generator_with_optimization._calculate_xpath_priority(xpath)

		assert priority <= 2, f'ID-based XPath should have priority <= 2, got {priority}'

	# ============================================================================
	# Test 4: Priority Calculation - Table-anchored XPath
	# ============================================================================
	def test_priority_calculation_table_anchored(self):
		"""Test that table-anchored XPath gets medium-high priority"""
		xpath = '//table//tr[2]/td[3]/a'
		priority = self.generator_with_optimization._calculate_xpath_priority(xpath)

		assert priority == 4, f'Table-anchored XPath should have priority 4, got {priority}'

	# ============================================================================
	# Test 5: Priority Calculation - Absolute XPath
	# ============================================================================
	def test_priority_calculation_absolute_xpath(self):
		"""Test that absolute XPath gets lowest priority (highest number)"""
		xpath = '/html/body/form/div[3]/div/div/table/tbody/tr[2]/td[3]/a'
		priority = self.generator_with_optimization._calculate_xpath_priority(xpath, is_absolute=True)

		assert priority >= 8, f'Absolute XPath should have priority >= 8, got {priority}'

	# ============================================================================
	# Test 6: Strategy Determination - Table-anchored
	# ============================================================================
	def test_strategy_determination_table_anchored(self):
		"""Test that table-anchored XPath is correctly identified"""
		xpath = '//table//tr[2]/td[3]/a'
		strategy = self.generator_with_optimization._determine_xpath_strategy(xpath)

		assert strategy == 'table-anchored', f"Expected 'table-anchored', got '{strategy}'"

	# ============================================================================
	# Test 7: Strategy Determination - ID-based
	# ============================================================================
	def test_strategy_determination_id_based(self):
		"""Test that ID-based XPath is correctly identified"""
		xpath = "//button[@id='submit']"
		strategy = self.generator_with_optimization._determine_xpath_strategy(xpath)

		assert strategy == 'id-based', f"Expected 'id-based', got '{strategy}'"

	# ============================================================================
	# Test 8: Strategy Determination - Absolute Fallback
	# ============================================================================
	def test_strategy_determination_absolute_fallback(self):
		"""Test that absolute XPath is correctly identified"""
		xpath = '/html/body/div/form/button'
		strategy = self.generator_with_optimization._determine_xpath_strategy(xpath)

		assert strategy == 'absolute-fallback', f"Expected 'absolute-fallback', got '{strategy}'"

	# ============================================================================
	# Test 9: Strategy Determination - Text-based
	# ============================================================================
	def test_strategy_determination_text_contains(self):
		"""Test that text-based XPath is correctly identified"""
		xpath = "//a[contains(text(), 'Click here')]"
		strategy = self.generator_with_optimization._determine_xpath_strategy(xpath)

		assert strategy == 'text-contains', f"Expected 'text-contains', got '{strategy}'"

	# ============================================================================
	# Test 10: Integration - Full Element with Table Context
	# ============================================================================
	def test_integration_table_element_optimization(self):
		"""Test full integration: table element with optimization (limited to 2 XPaths)"""
		absolute_xpath = '/html/body/div[1]/div[2]/table/tbody/tr[2]/td[3]/a'

		element_data = {
			'tag_name': 'a',
			'text': 'License 12345',
			'attributes': {'class': 'license-link', 'href': '/license/12345'},
			'xpath': absolute_xpath,
		}

		strategies = self.generator_with_optimization.generate_strategies(element_data)

		# Should have strategies including:
		# - Semantic strategies (text_exact, role_text, etc.)
		# - Limited XPath strategies (2 max)

		strategy_types = [s.type for s in strategies]

		# Should have semantic strategies
		assert 'text_exact' in strategy_types, 'Should have text_exact strategy'

		# Should have exactly 2 XPath strategies
		xpath_strategies = [s for s in strategies if s.type == 'xpath']
		assert len(xpath_strategies) == 2, f'Should have exactly 2 XPath strategies, got {len(xpath_strategies)}'

		# First should be optimized (table-anchored or similar)
		first_xpath = xpath_strategies[0]
		assert first_xpath.metadata.get('optimized'), 'First XPath should be optimized'

		# Last should be absolute fallback
		last_xpath = xpath_strategies[-1]
		assert last_xpath.value == absolute_xpath, 'Last XPath should be absolute fallback'
		assert last_xpath.priority >= first_xpath.priority, 'Absolute should have lower priority (higher number)'

	# ============================================================================
	# Test 11: Integration - Form Input Element
	# ============================================================================
	def test_integration_form_input_optimization(self):
		"""Test full integration: form input element with optimization (limited to 2 XPaths)"""
		absolute_xpath = '/html/body/div[5]/form/div[3]/div[1]/input'

		element_data = {
			'tag_name': 'input',
			'text': '',
			'attributes': {'name': 'email', 'type': 'email', 'placeholder': 'Enter your email'},
			'xpath': absolute_xpath,
		}

		strategies = self.generator_with_optimization.generate_strategies(element_data)

		# Should have placeholder and XPath strategies
		strategy_types = [s.type for s in strategies]
		assert 'placeholder' in strategy_types, 'Should have placeholder strategy'

		# Should have exactly 2 XPath strategies
		xpath_strategies = [s for s in strategies if s.type == 'xpath']
		assert len(xpath_strategies) == 2, f'Should have exactly 2 XPath strategies, got {len(xpath_strategies)}'

		# At least one should be optimized
		optimized = [s for s in xpath_strategies if s.metadata.get('optimized')]
		assert len(optimized) > 0, 'Should have optimized XPath strategies'

	# ============================================================================
	# Test 12: XPath Optimization with Data Attributes
	# ============================================================================
	def test_xpath_optimization_data_attributes(self):
		"""Test that data attributes are prioritized in optimized XPaths (limited to 2)"""
		absolute_xpath = '/html/body/div[1]/div[2]/div[3]/button'

		element_data = {
			'tag_name': 'button',
			'text': 'Submit',
			'attributes': {'data-testid': 'submit-button', 'class': 'btn btn-primary'},
			'xpath': absolute_xpath,
		}

		strategies = self.generator_with_optimization.generate_strategies(element_data)

		# Should have exactly 2 XPath strategies
		xpath_strategies = [s for s in strategies if s.type == 'xpath']
		assert len(xpath_strategies) == 2, f'Should have exactly 2 XPath strategies, got {len(xpath_strategies)}'

		# First should be optimized (likely data-attribute based)
		first_xpath = xpath_strategies[0]
		assert first_xpath.metadata.get('optimized'), 'First XPath should be optimized'

		# Data attribute XPath should have high priority
		assert first_xpath.priority <= 3, f'First XPath should have high priority, got {first_xpath.priority}'

	# ============================================================================
	# Test 13: XPath Optimization without Absolute XPath
	# ============================================================================
	def test_xpath_optimization_without_absolute_xpath(self):
		"""Test that optimization falls back gracefully when no absolute XPath is provided"""
		element_data = {
			'tag_name': 'button',
			'text': 'Submit',
			'attributes': {'class': 'btn'},
			# No xpath provided
		}

		strategies = self.generator_with_optimization.generate_strategies(element_data)

		# Should still generate strategies (semantic + fallback XPath)
		assert len(strategies) > 0, 'Should generate strategies even without absolute XPath'

		# Should have at least text-based strategies
		strategy_types = [s.type for s in strategies]
		assert 'text_exact' in strategy_types, 'Should have text_exact strategy'

	# ============================================================================
	# Test 14: XPath Strategy Metadata
	# ============================================================================
	def test_xpath_strategy_metadata(self):
		"""Test that XPath strategies include proper metadata"""
		absolute_xpath = '/html/body/table/tbody/tr[2]/td[3]/a'

		element_data = {
			'tag_name': 'a',
			'text': 'Link',
			'attributes': {'href': '/page'},
			'xpath': absolute_xpath,
		}

		strategies = self.generator_with_optimization.generate_strategies(element_data)

		xpath_strategies = [s for s in strategies if s.type == 'xpath']

		for xpath_strategy in xpath_strategies:
			# Should have metadata
			assert xpath_strategy.metadata is not None, 'XPath strategy should have metadata'

			# Should have tag
			assert 'tag' in xpath_strategy.metadata, 'XPath metadata should include tag'

			# Optimized strategies should have strategy name
			if xpath_strategy.metadata.get('optimized'):
				assert 'strategy' in xpath_strategy.metadata, 'Optimized XPath should have strategy name'

	# ============================================================================
	# Test 15: Priority Calculation - ARIA Attributes
	# ============================================================================
	def test_priority_calculation_aria_attributes(self):
		"""Test that ARIA attribute-based XPath gets high priority"""
		xpath = "//button[@aria-label='Submit form']"
		priority = self.generator_with_optimization._calculate_xpath_priority(xpath)

		assert priority <= 3, f'ARIA-based XPath should have priority <= 3, got {priority}'

	# ============================================================================
	# Test 16: XPath Optimizer Integration
	# ============================================================================
	def test_xpath_optimizer_called_correctly(self):
		"""Test that XPathOptimizer is called with correct parameters"""
		absolute_xpath = '/html/body/div[1]/form/button'

		element_data = {
			'tag_name': 'button',
			'text': 'Submit',
			'attributes': {'id': 'submit-btn'},
			'xpath': absolute_xpath,
		}

		# Generate strategies (this should call XPathOptimizer internally)
		strategies = self.generator_with_optimization.generate_strategies(element_data)

		# Verify that we got optimized XPath strategies
		xpath_strategies = [s for s in strategies if s.type == 'xpath']
		optimized_strategies = [s for s in xpath_strategies if s.metadata.get('optimized')]

		assert len(optimized_strategies) > 0, 'Should have optimized XPath strategies from optimizer'

	# ============================================================================
	# Test 17: Comparison - With vs Without Optimization
	# ============================================================================
	def test_comparison_with_without_optimization(self):
		"""Compare strategy generation with and without optimization (limited to 2)"""
		absolute_xpath = '/html/body/div[1]/table/tbody/tr[2]/td[3]/a'

		element_data = {
			'tag_name': 'a',
			'text': 'Link',
			'attributes': {'class': 'link'},
			'xpath': absolute_xpath,
		}

		strategies_with = self.generator_with_optimization.generate_strategies(element_data)
		strategies_without = self.generator_without_optimization.generate_strategies(element_data)

		xpath_with = [s for s in strategies_with if s.type == 'xpath']
		xpath_without = [s for s in strategies_without if s.type == 'xpath']

		# With optimization should have 2 XPath strategies
		assert len(xpath_with) == 2, f'With optimization should have 2 XPaths, got {len(xpath_with)}'

		# Without optimization should have only 1 XPath (the fallback)
		assert len(xpath_without) == 1, f'Without optimization should have 1 XPath, got {len(xpath_without)}'

	# ============================================================================
	# Test 18: No Duplicate XPath Strategies
	# ============================================================================
	def test_no_duplicate_xpath_strategies(self):
		"""Test that no duplicate XPath strategies are generated"""
		absolute_xpath = '/html/body/div/a'

		element_data = {
			'tag_name': 'a',
			'text': 'Link',
			'attributes': {},
			'xpath': absolute_xpath,
		}

		strategies = self.generator_with_optimization.generate_strategies(element_data)

		xpath_strategies = [s for s in strategies if s.type == 'xpath']
		xpath_values = [s.value for s in xpath_strategies]

		# Check for duplicates
		unique_values = set(xpath_values)
		assert len(xpath_values) == len(unique_values), f'Found duplicate XPath strategies: {xpath_values}'

	# ============================================================================
	# Test 19: Max Alternatives = 1 (Only Absolute XPath)
	# ============================================================================
	def test_max_alternatives_one(self):
		"""Test that max_alternatives=1 returns only the absolute xpath (no optimized alternatives)"""
		absolute_xpath = '/html/body/form/div[3]/table/tbody/tr[2]/td[3]/a'

		element_info = {
			'tag': 'a',
			'text': 'License 12345',
			'attributes': {'class': 'license-link', 'href': '/license/12345'},
		}

		# Request only 1 alternative
		result = self.optimizer.optimize_xpath(absolute_xpath, element_info, max_alternatives=1)

		# Should return exactly 1 XPath (the absolute one only)
		assert len(result) == 1, f'Expected exactly 1 XPath with max_alternatives=1, got {len(result)}'

		# Should be the absolute xpath
		assert result[0] == absolute_xpath, f'Expected absolute xpath, got {result[0]}'

	# ============================================================================
	# Test 20: Total Strategy Limit
	# ============================================================================
	def test_total_strategy_limit(self):
		"""Test that total strategies are limited to max_total_strategies"""
		generator_limited = SelectorGenerator(enable_xpath_optimization=True, max_xpath_alternatives=2, max_total_strategies=2)

		absolute_xpath = '/html/body/form/div[3]/div/div/table/tbody/tr[2]/td[3]/a'

		element_data = {
			'tag_name': 'a',
			'text': 'License 12345',
			'attributes': {'class': 'license-link', 'href': '/license/12345'},
			'xpath': absolute_xpath,
		}

		strategies = generator_limited.generate_strategies(element_data)

		# Should have exactly 2 total strategies (not just 2 XPath)
		assert len(strategies) == 2, f'Expected exactly 2 total strategies, got {len(strategies)}'

		# Should prioritize highest priority strategies
		priorities = [s.priority for s in strategies]
		assert priorities[0] <= priorities[1], 'Strategies should be sorted by priority'


if __name__ == '__main__':
	# Run all tests
	test = TestXPathOptimization()
	test_methods = [m for m in dir(test) if m.startswith('test_')]

	print(f'\n{"=" * 80}')
	print(f'Running {len(test_methods)} tests for XPath Optimization')
	print(f'{"=" * 80}\n')

	passed = 0
	failed = 0

	for method_name in test_methods:
		test.setup_method()  # Setup for each test
		method = getattr(test, method_name)
		try:
			method()
			print(f'✅ PASS: {method_name}')
			passed += 1
		except AssertionError as e:
			print(f'❌ FAIL: {method_name}')
			print(f'   {str(e)}')
			failed += 1
		except Exception as e:
			print(f'❌ ERROR: {method_name}')
			print(f'   {type(e).__name__}: {str(e)}')
			failed += 1

	print(f'\n{"=" * 80}')
	print(f'Test Results: {passed} passed, {failed} failed')
	print(f'{"=" * 80}\n')

	exit(0 if failed == 0 else 1)
