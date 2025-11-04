"""Test script to verify wait_time functionality in workflows.

This test suite covers four critical areas:

1. Runtime execution logic (test_runtime_wait_logic):
   - Verifies that asyncio.sleep is called with correct durations in run()
   - Tests default_wait_time, per-step wait_time, and wait_time=0
   - Ensures the execution loop in workflow/service.py works correctly

2. No-AI execution path (test_run_with_no_ai_wait_logic):
   - Verifies run_with_no_ai uses the same wait logic as run()
   - Ensures architectural consistency between execution paths
   - Tests that both methods respect default_wait_time and per-step wait_time

3. Actual timing validation (test_actual_timing):
   - Measures real wall-clock time during workflow execution
   - Validates that workflows actually pause for the expected duration
   - Ensures timing is within acceptable tolerance

4. Schema validation (test_wait_times):
   - Tests that wait_time values are loaded correctly from YAML
   - Validates Workflow initialization respects default_wait_time
   - Tests edge cases like wait_time=0 and default_wait_time=0

All tests use mocking to avoid external dependencies (browsers, LLMs, networks).
"""

import asyncio
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from workflow_use.schema.views import WorkflowDefinitionSchema


async def test_runtime_wait_logic():
	"""Test that workflow execution actually waits the correct duration between steps."""
	print('🧪 Testing runtime wait logic...\n')

	from browser_use.agent.views import ActionResult

	# Create a test workflow with various wait times
	workflow_schema = WorkflowDefinitionSchema(
		name='Runtime Wait Test',
		description='Test actual execution timing',
		version='1.0',
		default_wait_time=0.5,
		steps=[
			{'type': 'navigation', 'url': 'https://example.com', 'description': 'Step 1'},
			{'type': 'extract', 'extractionGoal': 'Test 2', 'description': 'Step 2 (wait 1.0s)', 'wait_time': 1.0},
			{'type': 'extract', 'extractionGoal': 'Test 3', 'description': 'Step 3 (wait 0s)', 'wait_time': 0},
			{'type': 'extract', 'extractionGoal': 'Test 4', 'description': 'Step 4 (default 0.5s)'},
		],
		input_schema=[],
	)

	# Mock the Workflow class to track sleep calls
	sleep_calls = []
	original_sleep = asyncio.sleep

	async def mock_sleep(duration):
		sleep_calls.append(duration)
		# Actually sleep a tiny amount to simulate timing
		await original_sleep(0.001)

	# Mock Browser and LLM
	mock_browser = Mock()
	mock_browser.start = AsyncMock()
	mock_browser.stop = AsyncMock()
	mock_browser.get_current_page = AsyncMock(return_value=Mock())

	mock_llm = Mock()

	# Import and patch
	from workflow_use.workflow.service import Workflow

	with patch('asyncio.sleep', mock_sleep):
		with patch.object(
			Workflow, '_execute_step', new_callable=lambda: AsyncMock(return_value=ActionResult(extracted_content='test'))
		):
			workflow = Workflow(
				workflow_schema=workflow_schema,
				llm=mock_llm,
				browser=mock_browser,
			)

			# Run the workflow
			await workflow.run(inputs={}, close_browser_at_end=False)

	# Verify sleep was called with correct durations
	print('Sleep calls during execution:')
	for i, duration in enumerate(sleep_calls):
		print(f'  Sleep {i + 1}: {duration}s')

	# Expected: No sleep before step 1, then 0.5s, 1.0s, 0s
	expected_sleeps = [0.5, 1.0, 0.0]

	assert len(sleep_calls) >= len(expected_sleeps), (
		f'Expected at least {len(expected_sleeps)} sleep calls, got {len(sleep_calls)}'
	)

	# Check the first few sleeps match our expectations (allow extra sleeps from other parts)
	for i, expected in enumerate(expected_sleeps):
		actual = sleep_calls[i]
		assert actual == expected, f'Sleep {i + 1}: expected {expected}s, got {actual}s'

	print('\n✅ Runtime wait logic tests passed!')
	print('  ✓ Step 1 (no wait_time) → waited 0.5s (default)')
	print('  ✓ Step 2 (wait_time=1.0) → waited 1.0s')
	print('  ✓ Step 3 (wait_time=0) → waited 0s (skip)')
	print('')


async def test_wait_times():
	"""Test that default_wait_time and per-step wait_time work correctly."""
	print('🧪 Testing wait_time schema functionality...\n')

	# Create a simple test workflow YAML
	test_workflow_yaml = """
workflow_analysis: Test workflow for wait_time functionality
name: Wait Time Test Workflow
description: Tests default and per-step wait times
version: '1.0'
default_wait_time: 0.5
steps:
  - description: Navigate to example.com
    type: navigation
    url: https://example.com

  - description: Step with custom wait time
    type: extract
    extractionGoal: Get page title
    wait_time: 1.0

  - description: Step with zero wait time (intentionally skip delay)
    type: extract
    extractionGoal: Get page content
    wait_time: 0

  - description: Step with default wait time
    type: extract
    extractionGoal: Get more content

input_schema: []
"""

	# Save test workflow
	test_file = Path('test_workflow_wait_times.yaml')
	test_file.write_text(test_workflow_yaml)

	try:
		# Load workflow
		workflow_schema = WorkflowDefinitionSchema.load_from_file(str(test_file))

		print('✅ Workflow loaded successfully')
		print(f'  Default wait time: {workflow_schema.default_wait_time}s')
		print(f'  Number of steps: {len(workflow_schema.steps)}\n')

		# Verify schema values
		assert workflow_schema.default_wait_time == 0.5, 'Default wait time should be 0.5'
		assert getattr(workflow_schema.steps[1], 'wait_time', None) == 1.0, 'Step 2 should have wait_time=1.0'
		assert getattr(workflow_schema.steps[2], 'wait_time', None) == 0, 'Step 3 should have wait_time=0'
		assert getattr(workflow_schema.steps[3], 'wait_time', None) is None, 'Step 4 should not have custom wait_time'

		print('✅ Schema validation passed!')
		print('  - default_wait_time correctly set to 0.5s')
		print('  - Step 2 has custom wait_time of 1.0s')
		print('  - Step 3 has wait_time of 0 (intentionally skip delay)')
		print('  - Step 4 uses default wait_time\n')

		# Test that default_wait_time=0 is respected
		workflow_zero_default = WorkflowDefinitionSchema(
			name='Zero Default Test',
			description='Test default_wait_time=0',
			version='1.0',
			default_wait_time=0.0,
			steps=[{'type': 'navigation', 'url': 'https://example.com', 'description': 'Nav'}],
			input_schema=[],
		)
		assert workflow_zero_default.default_wait_time == 0.0, 'default_wait_time should be 0.0'
		print('✅ default_wait_time=0.0 is preserved in schema')
		print('  - Allows workflows to disable all waits globally\n')

		# Test Workflow initialization (only if API key is available)
		if os.getenv('BROWSER_USE_API_KEY'):
			from browser_use.llm import ChatBrowserUse

			from workflow_use.workflow.service import Workflow

			llm = ChatBrowserUse()
			workflow = Workflow(
				workflow_schema=workflow_schema,
				llm=llm,
			)

			print('✅ Workflow instance created successfully')
			print(f'  Workflow.step_wait_time: {workflow.step_wait_time}s')

			# Verify the workflow picked up the default_wait_time
			assert workflow.step_wait_time == 0.5, f'Expected step_wait_time=0.5, got {workflow.step_wait_time}'

			print('✅ Workflow uses default_wait_time from schema\n')

			# Test that explicitly passing step_wait_time overrides schema
			workflow_override = Workflow(workflow_schema=workflow_schema, llm=llm, step_wait_time=2.0)

			assert workflow_override.step_wait_time == 2.0, f'Expected step_wait_time=2.0, got {workflow_override.step_wait_time}'

			print('✅ Explicit step_wait_time parameter overrides schema default\n')

			# Test that default_wait_time=0 is respected in Workflow initialization
			workflow_zero = Workflow(
				workflow_schema=workflow_zero_default,
				llm=llm,
			)
			assert workflow_zero.step_wait_time == 0.0, f'Expected step_wait_time=0.0, got {workflow_zero.step_wait_time}'
			print('✅ Workflow respects default_wait_time=0.0 from schema')
			print('  - Workflows can disable all waits via schema\n')
		else:
			print('⏭️  Skipping Workflow instance tests (BROWSER_USE_API_KEY not set)\n')

		print('=' * 60)
		print('✅ ALL TESTS PASSED!')
		print('=' * 60)
		print('\nKey features verified:')
		print('  ✓ default_wait_time field in workflow schema')
		print('  ✓ wait_time field per step')
		print('  ✓ Schema validation works correctly')
		if os.getenv('BROWSER_USE_API_KEY'):
			print('  ✓ Workflow uses default_wait_time from schema')
			print('  ✓ Explicit step_wait_time parameter overrides schema')

	finally:
		# Cleanup
		if test_file.exists():
			test_file.unlink()


async def test_actual_timing():
	"""Test that workflow execution takes approximately the expected time."""
	print('🧪 Testing actual execution timing...\n')

	from browser_use.agent.views import ActionResult

	from workflow_use.workflow.service import Workflow

	# Create a workflow with known wait times
	workflow_schema = WorkflowDefinitionSchema(
		name='Timing Test',
		description='Test actual timing',
		version='1.0',
		default_wait_time=0.1,
		steps=[
			{'type': 'navigation', 'url': 'https://example.com', 'description': 'Step 1'},
			{'type': 'extract', 'extractionGoal': 'Test', 'description': 'Step 2 (wait 0.2s)', 'wait_time': 0.2},
			{'type': 'extract', 'extractionGoal': 'Test', 'description': 'Step 3 (wait 0.1s)'},
		],
		input_schema=[],
	)

	# Expected total wait time: 0.1s + 0.2s = 0.3s
	expected_wait_time = 0.3

	# Mock Browser and LLM
	mock_browser = Mock()
	mock_browser.start = AsyncMock()
	mock_browser.stop = AsyncMock()
	mock_browser.get_current_page = AsyncMock(return_value=Mock())

	mock_llm = Mock()

	# Mock _execute_step to return immediately
	with patch.object(
		Workflow, '_execute_step', new_callable=lambda: AsyncMock(return_value=ActionResult(extracted_content='test'))
	):
		workflow = Workflow(
			workflow_schema=workflow_schema,
			llm=mock_llm,
			browser=mock_browser,
		)

		# Measure actual execution time
		start_time = time.time()
		await workflow.run(inputs={}, close_browser_at_end=False)
		actual_time = time.time() - start_time

	print(f'Expected wait time: {expected_wait_time}s')
	print(f'Actual execution time: {actual_time:.3f}s')

	# Allow for some overhead (0.1s tolerance)
	tolerance = 0.15
	assert actual_time >= expected_wait_time, f'Execution too fast: {actual_time:.3f}s < {expected_wait_time}s'
	assert actual_time <= expected_wait_time + tolerance, (
		f'Execution too slow: {actual_time:.3f}s > {expected_wait_time + tolerance}s'
	)

	print(f'✅ Actual timing is within tolerance ({tolerance}s)')
	print(f'  ✓ Execution took {actual_time:.3f}s (expected ~{expected_wait_time}s)')
	print('')


async def test_run_with_no_ai_wait_logic():
	"""Test that run_with_no_ai also respects wait time configuration."""
	print('🧪 Testing run_with_no_ai wait logic...\n')

	from browser_use.agent.views import ActionResult

	# Create a test workflow with various wait times
	workflow_schema = WorkflowDefinitionSchema(
		name='No AI Wait Test',
		description='Test wait times in run_with_no_ai',
		version='1.0',
		default_wait_time=0.3,
		steps=[
			{'type': 'navigation', 'url': 'https://example.com', 'description': 'Step 1'},
			{'type': 'extract', 'extractionGoal': 'Test 2', 'description': 'Step 2 (wait 0.6s)', 'wait_time': 0.6},
			{'type': 'extract', 'extractionGoal': 'Test 3', 'description': 'Step 3 (wait 0s)', 'wait_time': 0},
			{'type': 'extract', 'extractionGoal': 'Test 4', 'description': 'Step 4 (default 0.3s)'},
		],
		input_schema=[],
	)

	# Mock the SemanticWorkflowExecutor
	sleep_calls = []
	original_sleep = asyncio.sleep

	async def mock_sleep(duration):
		sleep_calls.append(duration)
		await original_sleep(0.001)

	# Mock Browser and LLM
	mock_browser = Mock()
	mock_browser.start = AsyncMock()
	mock_browser.stop = AsyncMock()
	mock_browser.get_current_page = AsyncMock(return_value=Mock())

	mock_llm = Mock()

	# Import and patch
	from workflow_use.workflow.semantic_executor import SemanticWorkflowExecutor
	from workflow_use.workflow.service import Workflow

	with patch('asyncio.sleep', mock_sleep):
		with patch.object(
			SemanticWorkflowExecutor,
			'execute_step',
			new_callable=lambda: AsyncMock(return_value=ActionResult(extracted_content='test')),
		):
			workflow = Workflow(
				workflow_schema=workflow_schema,
				llm=mock_llm,
				browser=mock_browser,
			)

			# Run the workflow with no AI
			await workflow.run_with_no_ai(inputs={}, close_browser_at_end=False)

	# Verify sleep was called with correct durations
	print('Sleep calls during run_with_no_ai execution:')
	for i, duration in enumerate(sleep_calls):
		print(f'  Sleep {i + 1}: {duration}s')

	# Expected: No sleep before step 1, then 0.3s, 0.6s, 0s
	expected_sleeps = [0.3, 0.6, 0.0]

	assert len(sleep_calls) >= len(expected_sleeps), (
		f'Expected at least {len(expected_sleeps)} sleep calls, got {len(sleep_calls)}'
	)

	# Check the first few sleeps match our expectations
	for i, expected in enumerate(expected_sleeps):
		actual = sleep_calls[i]
		assert actual == expected, f'Sleep {i + 1}: expected {expected}s, got {actual}s'

	print('\n✅ run_with_no_ai wait logic tests passed!')
	print('  ✓ Step 1 (no wait_time) → waited 0.3s (default)')
	print('  ✓ Step 2 (wait_time=0.6) → waited 0.6s')
	print('  ✓ Step 3 (wait_time=0) → waited 0s (skip)')
	print('  ✓ Consistent with run() method behavior')
	print('')


async def run_all_tests():
	"""Run all wait_time tests."""
	# Run runtime test first (most important)
	await test_runtime_wait_logic()

	# Run run_with_no_ai test
	await test_run_with_no_ai_wait_logic()

	# Run actual timing test
	await test_actual_timing()

	# Run schema tests
	await test_wait_times()


if __name__ == '__main__':
	asyncio.run(run_all_tests())
