"""Test script to verify wait_time functionality in workflows."""

import asyncio
import os
import time
from pathlib import Path

import yaml

from workflow_use.schema.views import WorkflowDefinitionSchema


async def test_wait_times():
	"""Test that default_wait_time and per-step wait_time work correctly."""
	print('🧪 Testing wait_time functionality...\n')

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

  - description: Step with default wait time
    type: extract
    extractionGoal: Get page content

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
		assert getattr(workflow_schema.steps[2], 'wait_time', None) is None, 'Step 3 should not have custom wait_time'

		print('✅ Schema validation passed!')
		print('  - default_wait_time correctly set to 0.5s')
		print('  - Step 2 has custom wait_time of 1.0s')
		print('  - Step 3 uses default wait_time\n')

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


if __name__ == '__main__':
	asyncio.run(test_wait_times())
