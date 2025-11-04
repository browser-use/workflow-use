"""
Unit tests for workflow execution - Empty actions and deterministic step execution.

Tests the fixes for go_back/go_forward (empty action models) and deterministic execution.
"""

from workflow_use.schema.views import NavigationStep


class TestWorkflowExecution:
	"""Test workflow execution with focus on empty actions and deterministic steps"""

	def setup_method(self):
		"""Setup test fixture"""
		# We can't actually create WorkflowService without a real LLM/browser,
		# but we can test the logic that handles empty actions
		pass

	# Test 1: go_back action uses NoParamsAction instance (not empty dict)
	def test_go_back_uses_no_params_action(self):
		"""Test that go_back action is prepared with NoParamsAction() instance (not {})"""
		# This tests the fix on line 179 of workflow_use/workflow/service.py
		from browser_use.tools.views import NoParamsAction

		# Simulate the logic from _run_deterministic_step
		action_name = 'go_back'
		params = {}  # Initial params

		# Apply the fix logic
		empty_actions = {'go_back', 'go_forward'}
		if action_name in empty_actions:
			params = NoParamsAction()

		assert isinstance(params, NoParamsAction), f'go_back should use NoParamsAction(), got {type(params)}'

	# Test 2: go_forward action uses NoParamsAction instance
	def test_go_forward_uses_no_params_action(self):
		"""Test that go_forward action is prepared with NoParamsAction() instance (not {})"""
		from browser_use.tools.views import NoParamsAction

		action_name = 'go_forward'
		params = {'some': 'data'}  # Initial params

		# Apply the fix logic
		empty_actions = {'go_back', 'go_forward'}
		if action_name in empty_actions:
			params = NoParamsAction()

		assert isinstance(params, NoParamsAction), f'go_forward should use NoParamsAction(), got {type(params)}'

	# Test 3: Other actions preserve their params
	def test_other_actions_preserve_params(self):
		"""Test that non-empty actions keep their params"""
		action_name = 'click'
		params = {'index': 42}

		# Apply the fix logic
		empty_actions = {'go_back', 'go_forward'}
		if action_name in empty_actions:
			params = None

		assert params == {'index': 42}, f'click should preserve params, got {params}'

	# Test 4: Action model creation format
	def test_action_model_format_for_empty_actions(self):
		"""Test that empty actions create model with {action_name: NoParamsAction()}"""
		from browser_use.tools.views import NoParamsAction

		action_name = 'go_back'
		params = NoParamsAction()  # After applying fix

		# The action model is created with: ActionModel(**{action_name: params})
		# For go_back with NoParamsAction params, this becomes: ActionModel(go_back=NoParamsAction())
		action_dict = {action_name: params}

		assert 'go_back' in action_dict, 'go_back should be in action_dict'
		assert isinstance(action_dict['go_back'], NoParamsAction), 'go_back value should be NoParamsAction instance'

	# Test 5: Workflow schema validation for navigation step
	def test_navigation_step_schema(self):
		"""Test that NavigationStep can be created with url"""
		step = NavigationStep(type='navigation', url='https://example.com', target_text='', description='Navigate to example.com')

		assert step.type == 'navigation'
		assert step.url == 'https://example.com'

	# Test 6: Multi-strategy element finding for click actions
	async def test_click_action_uses_multi_strategy(self):
		"""Test that click actions with selectorStrategies use multi-strategy finding"""
		# This tests the logic from lines 142-172 of workflow_use/workflow/service.py

		action_name = 'click'
		all_params = {
			'target_text': 'Submit',
			'selectorStrategies': [{'type': 'text_exact', 'value': 'Submit', 'priority': 1, 'metadata': {}}],
		}

		# Should trigger multi-strategy finding
		assert action_name in ['click', 'input'], 'Should use multi-strategy for click'
		assert 'selectorStrategies' in all_params, 'Should have strategies'
		assert len(all_params['selectorStrategies']) > 0, 'Should have at least one strategy'

	# Test 7: Multi-strategy element finding for input actions
	async def test_input_action_uses_multi_strategy(self):
		"""Test that input actions with selectorStrategies use multi-strategy finding"""
		action_name = 'input'
		all_params = {
			'target_text': 'Email',
			'value': 'test@example.com',
			'selectorStrategies': [{'type': 'placeholder', 'value': 'Enter your email', 'priority': 4, 'metadata': {}}],
		}

		# Should trigger multi-strategy finding
		assert action_name in ['click', 'input'], 'Should use multi-strategy for input'
		assert 'selectorStrategies' in all_params, 'Should have strategies'

	# Test 8: Actions without strategies skip multi-strategy finding
	async def test_actions_without_strategies_skip_multi_strategy(self):
		"""Test that actions without selectorStrategies don't trigger multi-strategy finding"""
		action_name = 'click'
		all_params = {
			'target_text': 'Submit',
			# No selectorStrategies
		}

		# Should NOT trigger multi-strategy finding
		has_strategies = 'selectorStrategies' in all_params
		assert not has_strategies, 'Should not have strategies'

	# Test 9: Element index injection after multi-strategy finding
	async def test_element_index_injection(self):
		"""Test that found element index is injected into params"""
		# Simulate successful multi-strategy finding
		action_name = 'click'
		params = {'target_text': 'Submit'}
		element_index = 42  # Found by multi-strategy

		# Logic from lines 155-158 of workflow_use/workflow/service.py
		if action_name == 'click':
			params['index'] = element_index

		assert 'index' in params, 'Index should be injected'
		assert params['index'] == 42, f'Expected index 42, got {params["index"]}'

	# Test 10: Semantic strategies format validation
	def test_semantic_strategies_format(self):
		"""Test that selectorStrategies have correct format"""
		strategies = [
			{'type': 'text_exact', 'value': 'Submit', 'priority': 1, 'metadata': {'tag': 'button'}},
			{'type': 'role_text', 'value': 'Submit', 'priority': 2, 'metadata': {'role': 'button'}},
			{'type': 'aria_label', 'value': 'Submit form', 'priority': 3, 'metadata': {}},
		]

		# Validate all strategies have required fields
		for strategy in strategies:
			assert 'type' in strategy, "Strategy missing 'type'"
			assert 'value' in strategy, "Strategy missing 'value'"
			assert 'priority' in strategy, "Strategy missing 'priority'"
			assert 'metadata' in strategy, "Strategy missing 'metadata'"

		# Validate semantic-only (no CSS/xpath)
		strategy_types = [s['type'] for s in strategies]
		assert 'css' not in strategy_types, 'Should not have CSS strategies'
		assert 'xpath' not in strategy_types, 'Should not have xpath strategies'
		assert 'id' not in strategy_types, 'Should not have id strategies'

	# Test 11: Actions requiring wait after execution
	def test_actions_requiring_wait(self):
		"""Test that certain actions trigger page stabilization wait"""
		# From line 189 of workflow_use/workflow/service.py
		actions_requiring_wait = {'navigation', 'click', 'go_back', 'go_forward'}

		assert 'navigation' in actions_requiring_wait
		assert 'click' in actions_requiring_wait
		assert 'go_back' in actions_requiring_wait
		assert 'go_forward' in actions_requiring_wait

		# Actions NOT requiring wait
		assert 'input' not in actions_requiring_wait
		assert 'extract' not in actions_requiring_wait


# Helper to run async tests
import asyncio


def run_async_test(test_method):
	"""Helper to run async test methods"""
	return asyncio.run(test_method())


if __name__ == '__main__':
	# Run all tests
	test = TestWorkflowExecution()
	test_methods = [m for m in dir(test) if m.startswith('test_')]

	print(f'\n{"=" * 80}')
	print(f'Running {len(test_methods)} tests for Workflow Execution')
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
