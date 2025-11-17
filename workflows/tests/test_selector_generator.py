"""
Unit tests for SelectorGenerator - Semantic-only strategy generation.

Tests that SelectorGenerator creates ONLY semantic strategies (no CSS/xpath/id).
"""

from workflow_use.healing.selector_generator import SelectorGenerator, SelectorStrategy


class TestSelectorGenerator:
	"""Test SelectorGenerator semantic-only strategy generation"""

	def setup_method(self):
		"""Setup test fixture"""
		self.generator = SelectorGenerator()

	# Test 1: Basic semantic strategies for button with text
	def test_button_with_text_generates_semantic_strategies(self):
		"""Test that button with text generates text_exact, role_text, and text_fuzzy strategies"""
		element_data = {'tag_name': 'button', 'text': 'Submit', 'attributes': {}}

		strategies = self.generator.generate_strategies(element_data)

		# Should generate at least 3 strategies: text_exact, role_text, text_fuzzy
		assert len(strategies) >= 3, f'Expected at least 3 strategies, got {len(strategies)}'

		# Check that we have the expected strategy types
		strategy_types = [s.type for s in strategies]
		assert 'text_exact' in strategy_types, 'Missing text_exact strategy'
		assert 'role_text' in strategy_types, 'Missing role_text strategy'
		assert 'text_fuzzy' in strategy_types, 'Missing text_fuzzy strategy'

		# Verify text_exact strategy
		text_exact = next(s for s in strategies if s.type == 'text_exact')
		assert text_exact.value == 'Submit', f"Expected 'Submit', got {text_exact.value}"
		assert text_exact.priority == 1, 'text_exact should have priority 1'

		# Verify role_text strategy
		role_text = next(s for s in strategies if s.type == 'role_text')
		assert role_text.value == 'Submit', f"Expected 'Submit', got {role_text.value}"
		assert role_text.metadata.get('role') == 'button', f"Expected role 'button', got {role_text.metadata.get('role')}"
		assert role_text.priority == 2, 'role_text should have priority 2'

	# Test 2: No CSS/id strategies (but xpath is allowed as fallback)
	def test_no_css_id_strategies(self):
		"""Test that NO CSS or id strategies are generated (semantic-first with xpath fallback)"""
		element_data = {
			'tag_name': 'button',
			'text': 'Click Me',
			'attributes': {
				'id': 'submit-btn',  # Has ID but should NOT generate id strategy
				'class': 'btn btn-primary',  # Has class but should NOT generate CSS strategy
				'data-testid': 'submit',  # Has data attr but should NOT generate CSS strategy
			},
		}

		strategies = self.generator.generate_strategies(element_data)

		# Verify NO CSS/id strategies (semantic-first approach)
		strategy_types = [s.type for s in strategies]
		assert 'id' not in strategy_types, 'Should NOT generate id strategy (semantic-first)'
		assert 'css' not in strategy_types, 'Should NOT generate CSS strategy (semantic-first)'
		assert 'css_selector' not in strategy_types, 'Should NOT generate css_selector strategy (semantic-first)'
		assert 'css_attr' not in strategy_types, 'Should NOT generate css_attr strategy (semantic-first)'

		# XPath is allowed as a fallback strategy (this is the improvement!)
		# It should be low priority (tested in test_xpath_optimization.py)

	# Test 3: ARIA label strategy
	def test_aria_label_strategy(self):
		"""Test that aria-label generates aria_label strategy"""
		element_data = {'tag_name': 'button', 'text': 'Submit', 'attributes': {'aria-label': 'Submit form'}}

		strategies = self.generator.generate_strategies(element_data)
		strategy_types = [s.type for s in strategies]

		assert 'aria_label' in strategy_types, 'Missing aria_label strategy'

		aria_label = next(s for s in strategies if s.type == 'aria_label')
		assert aria_label.value == 'Submit form', f"Expected 'Submit form', got {aria_label.value}"
		assert aria_label.priority == 3, 'aria_label should have priority 3'

	# Test 4: Placeholder strategy for inputs
	def test_placeholder_strategy(self):
		"""Test that input with placeholder generates placeholder strategy"""
		element_data = {'tag_name': 'input', 'text': '', 'attributes': {'placeholder': 'Enter your email'}}

		strategies = self.generator.generate_strategies(element_data)
		strategy_types = [s.type for s in strategies]

		assert 'placeholder' in strategy_types, 'Missing placeholder strategy'

		placeholder = next(s for s in strategies if s.type == 'placeholder')
		assert placeholder.value == 'Enter your email', f"Expected 'Enter your email', got {placeholder.value}"
		assert placeholder.priority == 4, 'placeholder should have priority 4'

	# Test 5: Title attribute strategy
	def test_title_strategy(self):
		"""Test that title attribute generates title strategy"""
		element_data = {'tag_name': 'button', 'text': 'X', 'attributes': {'title': 'Close dialog'}}

		strategies = self.generator.generate_strategies(element_data)
		strategy_types = [s.type for s in strategies]

		assert 'title' in strategy_types, 'Missing title strategy'

		title_strategy = next(s for s in strategies if s.type == 'title')
		assert title_strategy.value == 'Close dialog', f"Expected 'Close dialog', got {title_strategy.value}"
		assert title_strategy.priority == 5, 'title should have priority 5'

	# Test 6: Alt text for images
	def test_alt_text_strategy(self):
		"""Test that img with alt text generates alt_text strategy"""
		element_data = {'tag_name': 'img', 'text': '', 'attributes': {'alt': 'Company logo'}}

		strategies = self.generator.generate_strategies(element_data)
		strategy_types = [s.type for s in strategies]

		assert 'alt_text' in strategy_types, 'Missing alt_text strategy'

		alt_text = next(s for s in strategies if s.type == 'alt_text')
		assert alt_text.value == 'Company logo', f"Expected 'Company logo', got {alt_text.value}"
		assert alt_text.priority == 6, 'alt_text should have priority 6'

	# Test 7: Role inference for common tags
	def test_role_inference(self):
		"""Test that _infer_role correctly maps tags to semantic roles"""
		test_cases = [
			('button', {}, 'button'),
			('a', {}, 'link'),
			('input', {}, 'textbox'),
			('textarea', {}, 'textbox'),
			('select', {}, 'combobox'),
			('h1', {}, 'heading'),
			('h2', {}, 'heading'),
			('img', {}, 'img'),
			('input', {'type': 'checkbox'}, 'checkbox'),
			('input', {'type': 'radio'}, 'radio'),
			('input', {'type': 'submit'}, 'button'),
		]

		for tag, attrs, expected_role in test_cases:
			role = self.generator._infer_role(tag, attrs)
			assert role == expected_role, f"Expected role '{expected_role}' for tag '{tag}' with attrs {attrs}, got '{role}'"

	# Test 8: Explicit role attribute takes precedence
	def test_explicit_role_takes_precedence(self):
		"""Test that explicit role attribute overrides inferred role"""
		role = self.generator._infer_role('div', {'role': 'button'})
		assert role == 'button', f"Expected explicit role 'button', got '{role}'"

	# Test 9: Strategy priority ordering
	def test_strategy_priority_ordering(self):
		"""Test that strategies are sorted by priority (lower = higher priority)"""
		element_data = {
			'tag_name': 'button',
			'text': 'Submit Form',
			'attributes': {'aria-label': 'Submit the form', 'title': 'Click to submit'},
		}

		strategies = self.generator.generate_strategies(element_data)

		# Verify strategies are sorted by priority
		priorities = [s.priority for s in strategies]
		assert priorities == sorted(priorities), f'Strategies not sorted by priority: {priorities}'

		# Verify priority 1 is text_exact
		assert strategies[0].type == 'text_exact', f'First strategy should be text_exact, got {strategies[0].type}'
		assert strategies[0].priority == 1, 'First strategy should have priority 1'

	# Test 10: No strategies for element without semantic data
	def test_element_with_no_semantic_data(self):
		"""Test element with no text or semantic attributes"""
		element_data = {'tag_name': 'div', 'text': '', 'attributes': {}}

		strategies = self.generator.generate_strategies(element_data)

		# Should generate minimal or no strategies
		# (No text, no ARIA, no role text possible)
		assert len(strategies) == 0, f'Expected 0 strategies for element with no semantic data, got {len(strategies)}'

	# Test 11: generate_strategies_dict returns serializable dicts
	def test_generate_strategies_dict(self):
		"""Test that generate_strategies_dict returns JSON-serializable dictionaries"""
		element_data = {'tag_name': 'button', 'text': 'Click Me', 'attributes': {'aria-label': 'Click button'}}

		strategies_dict = self.generator.generate_strategies_dict(element_data)

		# Should be a list of dicts
		assert isinstance(strategies_dict, list), 'Should return a list'
		assert all(isinstance(s, dict) for s in strategies_dict), 'All strategies should be dicts'

		# Each dict should have required keys
		for strategy in strategies_dict:
			assert 'type' in strategy, "Strategy missing 'type' key"
			assert 'value' in strategy, "Strategy missing 'value' key"
			assert 'priority' in strategy, "Strategy missing 'priority' key"
			assert 'metadata' in strategy, "Strategy missing 'metadata' key"

	# Test 12: Fuzzy text match only for meaningful text
	def test_fuzzy_text_only_for_meaningful_text(self):
		"""Test that text_fuzzy is only generated for text > 3 characters"""
		# Short text (3 chars or less) - should NOT generate fuzzy
		short_text_data = {
			'tag_name': 'button',
			'text': 'OK',  # 2 chars
			'attributes': {},
		}

		short_strategies = self.generator.generate_strategies(short_text_data)
		short_types = [s.type for s in short_strategies]
		assert 'text_fuzzy' not in short_types, 'Should NOT generate text_fuzzy for short text (<=3 chars)'

		# Long text (> 3 chars) - should generate fuzzy
		long_text_data = {
			'tag_name': 'button',
			'text': 'Submit',  # 6 chars
			'attributes': {},
		}

		long_strategies = self.generator.generate_strategies(long_text_data)
		long_types = [s.type for s in long_strategies]
		assert 'text_fuzzy' in long_types, 'Should generate text_fuzzy for longer text (>3 chars)'

	# Test 13: SelectorStrategy to_dict and from_dict
	def test_selector_strategy_serialization(self):
		"""Test SelectorStrategy.to_dict() and from_dict() methods"""
		original = SelectorStrategy(type='text_exact', value='Submit', priority=1, metadata={'tag': 'button'})

		# Serialize to dict
		strategy_dict = original.to_dict()
		assert strategy_dict['type'] == 'text_exact'
		assert strategy_dict['value'] == 'Submit'
		assert strategy_dict['priority'] == 1
		assert strategy_dict['metadata'] == {'tag': 'button'}

		# Deserialize from dict
		restored = SelectorStrategy.from_dict(strategy_dict)
		assert restored.type == original.type
		assert restored.value == original.value
		assert restored.priority == original.priority
		assert restored.metadata == original.metadata

	# Test 14: get_summary returns readable output
	def test_get_summary(self):
		"""Test that get_summary returns human-readable summary"""
		element_data = {'tag_name': 'button', 'text': 'Submit Form', 'attributes': {'aria-label': 'Submit the form'}}

		strategies = self.generator.generate_strategies(element_data)
		summary = self.generator.get_summary(strategies)

		# Should contain count
		assert 'Generated' in summary, "Summary should contain 'Generated'"
		assert str(len(strategies)) in summary, 'Summary should contain strategy count'

		# Should contain strategy details
		assert 'text_exact' in summary, 'Summary should contain strategy type'
		assert 'priority' in summary, 'Summary should contain priority info'


if __name__ == '__main__':
	# Run all tests
	test = TestSelectorGenerator()
	test_methods = [m for m in dir(test) if m.startswith('test_')]

	print(f'\n{"=" * 80}')
	print(f'Running {len(test_methods)} tests for SelectorGenerator')
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
			print(f'   {str(e)}')
			failed += 1

	print(f'\n{"=" * 80}')
	print(f'Test Results: {passed} passed, {failed} failed')
	print(f'{"=" * 80}\n')

	exit(0 if failed == 0 else 1)
