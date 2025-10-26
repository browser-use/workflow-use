"""
Simple example: Create a workflow using deterministic conversion.

This script demonstrates how to automatically generate a semantic workflow
from a task description using the deterministic approach (no LLM for step creation).

Usage:
    python create_deterministic_workflow.py
"""

import asyncio
import json

import aiofiles
from browser_use.llm import ChatBrowserUse

from workflow_use.healing.service import HealingService


async def main():
	# Task description - what you want the workflow to do
	task = """
    Go to GitHub, search for the browser-use repository, click on it,
    and extract the star count.
    """

	print('=' * 80)
	print('CREATING WORKFLOW WITH DETERMINISTIC CONVERSION')
	print('=' * 80)
	print(f'\nTask: {task.strip()}\n')

	# Initialize LLM (needed for browser agent and optional variable identification)
	llm = ChatBrowserUse(model='bu-latest')

	# Create HealingService with deterministic conversion enabled
	print('Initializing HealingService with deterministic conversion...')
	healing_service = HealingService(
		llm=llm,
		enable_variable_extraction=True,  # Optional: use LLM to identify variables
		use_deterministic_conversion=True,  # 🔑 KEY: Enable deterministic mode
	)

	print('\nStep 1: Recording browser interactions...')
	print('(The browser agent will execute the task and record all actions)')

	# Generate workflow from the task
	# This will:
	# 1. Run a browser-use agent to complete the task
	# 2. Record all browser actions (navigate, click, input, etc.)
	# 3. Convert actions to semantic steps DETERMINISTICALLY (no LLM)
	# 4. Optionally use LLM to identify variables
	workflow = await healing_service.generate_workflow_from_prompt(prompt=task, agent_llm=llm, extraction_llm=llm)

	print('\n✅ Workflow generated successfully!')

	# Convert to dictionary for saving
	workflow_dict = workflow.model_dump(exclude_none=True)

	# Save to file
	output_file = 'github_stars_deterministic.workflow.json'
	async with aiofiles.open(output_file, 'w') as f:
		await f.write(json.dumps(workflow_dict, indent=2))

	print(f'\n📁 Workflow saved to: {output_file}')

	# Display workflow summary
	print('\n' + '=' * 80)
	print('WORKFLOW SUMMARY')
	print('=' * 80)

	print(f'\nName: {workflow_dict.get("name", "N/A")}')
	print(f'Description: {workflow_dict.get("description", "N/A")}')

	# Show input schema
	input_schema = workflow_dict.get('input_schema', [])
	if input_schema:
		print(f'\nInput Variables ({len(input_schema)}):')
		for var in input_schema:
			var_name = var.get('name', 'unknown')
			var_type = var.get('type', 'unknown')
			required = '(required)' if var.get('required', False) else '(optional)'
			print(f'  - {var_name}: {var_type} {required}')
	else:
		print('\nNo input variables defined')

	# Show steps
	steps = workflow_dict.get('steps', [])
	print(f'\nWorkflow Steps ({len(steps)}):')

	step_types = {}
	for i, step in enumerate(steps, 1):
		step_type = step.get('type', 'unknown')
		description = step.get('description', 'No description')

		# Count step types
		step_types[step_type] = step_types.get(step_type, 0) + 1

		print(f'\n  Step {i}: {step_type}')
		print(f'    Description: {description}')

		# Show key fields based on step type
		if step_type == 'navigation':
			print(f'    URL: {step.get("url", "N/A")}')
		elif step_type == 'input':
			print(f'    Target: {step.get("target_text", "N/A")}')
			print(f'    Value: {step.get("value", "N/A")}')
		elif step_type == 'click':
			print(f'    Target: {step.get("target_text", "N/A")}')
		elif step_type == 'keypress':
			print(f'    Key: {step.get("key", "N/A")}')
			print(f'    Target: {step.get("target_text", "N/A")}')
		elif step_type == 'extract_page_content':
			print(f'    Goal: {step.get("goal", "N/A")}')

	# Show step type summary
	print('\n' + '-' * 80)
	print('Step Type Summary:')
	for step_type, count in sorted(step_types.items()):
		print(f'  {step_type}: {count}')

	# Check for agent steps (should be 0 with deterministic conversion)
	agent_steps = step_types.get('agent', 0)
	if agent_steps == 0:
		print('\n✅ SUCCESS: Pure semantic workflow (no agent steps)')
		print('   This workflow will execute instantly and cost $0 per run!')
	else:
		print(f'\n⚠️  WARNING: Workflow contains {agent_steps} agent step(s)')
		print('   Agent steps are 10-30x slower and cost money per execution')

	# Usage instructions
	print('\n' + '=' * 80)
	print('NEXT STEPS')
	print('=' * 80)
	print('\nTo run this workflow:')
	print(f'  python -m workflow_use.cli run-workflow-no-ai {output_file}')

	if input_schema:
		print('\nWith variables:')
		var_examples = ' '.join([f'--{v["name"]} <value>' for v in input_schema])
		print(f'  python -m workflow_use.cli run-workflow-no-ai {output_file} {var_examples}')

	print('\n' + '=' * 80)


if __name__ == '__main__':
	asyncio.run(main())
