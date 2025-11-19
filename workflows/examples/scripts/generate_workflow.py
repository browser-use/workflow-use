"""
Generic Workflow Generator

This script creates a workflow from a task description and stores it in the workflow storage.
Simply modify the TASK_NAME and TASK_DESCRIPTION at the top of this file and run it.

Usage:
    cd workflows
    uv run python examples/scripts/generate_workflow.py

    Or with custom API key:
    BROWSER_USE_API_KEY=your_key uv run python examples/scripts/generate_workflow.py
"""

import asyncio
from pathlib import Path

from browser_use.llm import ChatBrowserUse

from workflow_use.healing.service import HealingService
from workflow_use.storage.service import WorkflowStorageService

# ============================================================================
# CONFIGURE YOUR TASK HERE
# ============================================================================

TASK_NAME = 'Get GitHub Repository Stars'
TASK_DESCRIPTION = """
Go to GitHub, search for the browser-use repository, click on it,
and extract the star count.
"""

# ============================================================================
# CONFIGURATION OPTIONS
# ============================================================================

# Enable variable extraction (uses LLM to identify reusable variables)
ENABLE_VARIABLE_EXTRACTION = True

# Use deterministic conversion (no LLM for step creation - faster, cheaper)
USE_DETERMINISTIC_CONVERSION = True

# Storage directory for workflows
STORAGE_DIR = Path(__file__).parent.parent.parent / 'storage'


# ============================================================================
# MAIN SCRIPT - DO NOT MODIFY BELOW UNLESS YOU KNOW WHAT YOU'RE DOING
# ============================================================================


async def generate_and_store_workflow():
	"""Generate a workflow from the task description and store it."""

	print('=' * 80)
	print('WORKFLOW GENERATOR')
	print('=' * 80)
	print(f'\nTask Name: {TASK_NAME}')
	print(f'Task Description: {TASK_DESCRIPTION.strip()}\n')

	# Initialize LLM
	print('Step 1: Initializing LLM...')
	llm = ChatBrowserUse(model='bu-latest')

	# Create HealingService for workflow generation
	print('Step 2: Setting up workflow generation service...')
	healing_service = HealingService(
		llm=llm, enable_variable_extraction=ENABLE_VARIABLE_EXTRACTION, use_deterministic_conversion=USE_DETERMINISTIC_CONVERSION
	)

	# Generate workflow
	print('\nStep 3: Recording browser interactions and generating workflow...')
	print('(This will open a browser and execute the task)\n')

	workflow = await healing_service.generate_workflow_from_prompt(
		prompt=TASK_DESCRIPTION, agent_llm=llm, extraction_llm=llm, use_cloud=True
	)

	print('✅ Workflow generated successfully!\n')

	# Initialize storage service
	print('Step 4: Storing workflow...')
	storage = WorkflowStorageService(storage_dir=STORAGE_DIR)

	# Save to storage
	metadata = storage.save_workflow(
		workflow=workflow,
		generation_mode='browser_use',
		original_task=TASK_DESCRIPTION.strip(),
	)

	print('✅ Workflow saved to storage!\n')

	# Display summary
	print('=' * 80)
	print('WORKFLOW SUMMARY')
	print('=' * 80)

	print(f'\nWorkflow ID: {metadata.id}')
	print(f'Name: {metadata.name}')
	print(f'Description: {metadata.description}')
	print(f'Version: {metadata.version}')
	print(f'File Path: {metadata.file_path}')
	print(f'Generation Mode: {metadata.generation_mode}')
	print(f'Created At: {metadata.created_at}')

	# Show input schema
	if workflow.input_schema:
		print(f'\nInput Variables ({len(workflow.input_schema)}):')
		for var in workflow.input_schema:
			required = '(required)' if var.required else '(optional)'
			format_info = f' - format: {var.format}' if var.format else ''
			print(f'  - {var.name}: {var.type} {required}{format_info}')
	else:
		print('\nNo input variables')

	# Show steps
	if workflow.steps:
		print(f'\nWorkflow Steps ({len(workflow.steps)}):')

		step_types = {}
		for i, step in enumerate(workflow.steps, 1):
			step_type = step.type
			step_types[step_type] = step_types.get(step_type, 0) + 1

			print(f'\n  Step {i}: {step_type}')
			if hasattr(step, 'description') and step.description:
				print(f'    Description: {step.description}')

			# Show key fields based on step type
			if step_type == 'navigation' and hasattr(step, 'url'):
				print(f'    URL: {step.url}')
			elif step_type == 'input' and hasattr(step, 'target_text'):
				print(f'    Target: {step.target_text}')
				if hasattr(step, 'value'):
					print(f'    Value: {step.value}')
			elif step_type == 'click' and hasattr(step, 'target_text'):
				print(f'    Target: {step.target_text}')
			elif step_type == 'key_press' and hasattr(step, 'key'):
				print(f'    Key: {step.key}')
			elif step_type == 'extract' and hasattr(step, 'extractionGoal'):
				print(f'    Goal: {step.extractionGoal}')
				if hasattr(step, 'output'):
					print(f'    Output Variable: {step.output}')

		# Show step type summary
		print('\n' + '-' * 80)
		print('Step Type Summary:')
		for step_type, count in sorted(step_types.items()):
			print(f'  {step_type}: {count}')

		# Check for agent steps
		agent_steps = step_types.get('agent', 0)
		if agent_steps == 0:
			print('\n✅ Pure semantic workflow (no agent steps)')
			print('   This workflow will execute fast and cost $0 per run!')
		else:
			print(f'\n⚠️  Contains {agent_steps} agent step(s)')
			print('   Agent steps may be slower and cost money per execution')

	# Usage instructions
	print('\n' + '=' * 80)
	print('HOW TO USE THIS WORKFLOW')
	print('=' * 80)

	print(f'\nWorkflow ID: {metadata.id}')
	print('\n1. List all workflows:')
	print('   cd workflows')
	print('   BROWSER_USE_API_KEY=your_key uv run python cli.py list-workflows')

	print('\n2. Run by ID:')
	print('   cd workflows')
	print(f'   BROWSER_USE_API_KEY=your_key uv run python cli.py run-workflow {metadata.id}')

	if workflow.input_schema:
		print('\n3. Run with input variables:')
		print('   cd workflows')
		var_args = ' '.join([f'--{v.name} <value>' for v in workflow.input_schema])
		print(f'   BROWSER_USE_API_KEY=your_key uv run python cli.py run-workflow {metadata.id} {var_args}')

	print('\n' + '=' * 80)
	print('DONE!')
	print('=' * 80 + '\n')


if __name__ == '__main__':
	asyncio.run(generate_and_store_workflow())
