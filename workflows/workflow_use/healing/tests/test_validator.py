"""
Test script for WorkflowValidator

This script tests the AI validation system with a sample workflow that has known issues.

Usage:
    BROWSER_USE_API_KEY=your_key uv run python workflow_use/healing/tests/test_validator.py
"""

import asyncio
import os

from browser_use.llm import ChatBrowserUse

from workflow_use.healing.validator import WorkflowValidator
from workflow_use.schema.views import (
	AgentTaskWorkflowStep,
	ExtractStep,
	InputStep,
	NavigationStep,
	WorkflowDefinitionSchema,
)


async def test_validator():
	"""Test the validator with a workflow that has issues."""

	# Check for API key
	if not os.getenv('BROWSER_USE_API_KEY'):
		print('Error: BROWSER_USE_API_KEY environment variable not set')
		print('Usage: BROWSER_USE_API_KEY=your_key uv run python workflow_use/healing/tests/test_validator.py')
		return

	# Create a sample workflow with known issues
	sample_workflow = WorkflowDefinitionSchema(
		name='Test Workflow with Issues',
		description='A test workflow with various issues to validate',
		version='1.0.0',
		steps=[
			# Issue 1: Agent step that should be semantic
			AgentTaskWorkflowStep(type='agent', task='click the search button'),
			# Issue 2: Navigation step (this is actually correct)
			NavigationStep(type='navigation', url='https://example.com'),
			# Issue 3: Input with hard-coded value that should be variable
			InputStep(type='input', target_text='First Name', value='John'),
			# Issue 4: Extract step with vague goal
			ExtractStep(type='extract', extractionGoal='get the data', output='result'),
		],
		input_schema=[],
	)

	# Initialize validator
	print('Initializing validator...')
	llm = ChatBrowserUse(model='bu-latest')
	validator = WorkflowValidator(llm=llm)

	# Run validation
	print('\nRunning validation on sample workflow...')
	result = await validator.validate_workflow(workflow=sample_workflow, original_task='Test task for validation')

	# Print report
	validator.print_validation_report(result)

	# Check if corrections were made
	if result.corrected_workflow:
		print('\n' + '=' * 80)
		print('CORRECTED WORKFLOW')
		print('=' * 80)
		print(result.corrected_workflow.model_dump_json(indent=2, exclude_none=True))

	return result


if __name__ == '__main__':
	asyncio.run(test_validator())
