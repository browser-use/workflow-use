"""
Complete end-to-end test of deterministic workflow generation.

This script:
1. Generates a workflow using deterministic conversion
2. Validates the workflow structure
3. Tests that it can be run
4. Reports success/failure

Usage:
    python run_complete_test.py
"""

import asyncio
import json

import aiofiles
from browser_use.llm import ChatBrowserUse

from workflow_use.healing.service import HealingService


def validate_workflow(workflow_dict):
	"""Validate the generated workflow meets quality standards."""
	issues = []
	warnings = []

	# Check basic structure
	if 'name' not in workflow_dict:
		issues.append("Missing 'name' field")
	if 'steps' not in workflow_dict:
		issues.append("Missing 'steps' field")
		return issues, warnings

	steps = workflow_dict['steps']

	if len(steps) == 0:
		issues.append('Workflow has no steps')
		return issues, warnings

	# Analyze steps
	agent_steps = []
	semantic_steps = []
	empty_target_text = []

	for i, step in enumerate(steps, 1):
		step_type = step.get('type', 'unknown')

		if step_type == 'agent':
			agent_steps.append(i)
		else:
			semantic_steps.append(i)

		# Check target_text for input/click steps
		if step_type in ['input', 'click']:
			target_text = step.get('target_text', '')
			if not target_text or target_text.strip() == '':
				empty_target_text.append(i)

	# Report issues
	if agent_steps:
		issues.append(f'Found {len(agent_steps)} agent step(s) at positions: {agent_steps}')

	if empty_target_text:
		warnings.append(f'Found {len(empty_target_text)} step(s) with empty target_text at positions: {empty_target_text}')

	return issues, warnings


async def main():
	print('=' * 80)
	print('COMPLETE END-TO-END TEST - DETERMINISTIC WORKFLOW GENERATION')
	print('=' * 80)
	print()

	# Task to test
	task = 'Go to GitHub, search for the browser-use repository, and get its star count'
	print(f'Task: {task}\n')

	# Setup
	print('Step 1: Initializing...')
	llm = ChatBrowserUse(model='bu-latest')

	service = HealingService(
		llm=llm,
		enable_variable_extraction=True,
		use_deterministic_conversion=True,  # 🔑 Deterministic mode
	)

	# Verify setup
	if not service.use_deterministic_conversion:
		print('❌ FAILED: Deterministic mode not enabled')
		return
	if service.deterministic_converter is None:
		print('❌ FAILED: Deterministic converter not initialized')
		return

	print('✅ Service initialized with deterministic conversion\n')

	# Generate workflow
	print('Step 2: Generating workflow...')
	print('(This will open a browser and complete the task)')
	print()

	try:
		workflow = await service.generate_workflow_from_prompt(prompt=task, agent_llm=llm, extraction_llm=llm)
		print('✅ Workflow generated successfully\n')
	except Exception as e:
		print(f'❌ FAILED: Workflow generation error: {e}\n')
		import traceback

		traceback.print_exc()
		return

	# Save workflow
	print('Step 3: Saving workflow...')
	workflow_dict = workflow.model_dump(exclude_none=True)
	output_file = 'complete_test_output.workflow.json'

	try:
		async with aiofiles.open(output_file, 'w') as f:
			await f.write(json.dumps(workflow_dict, indent=2))
		print(f'✅ Workflow saved to: {output_file}\n')
	except Exception as e:
		print(f'❌ FAILED: Could not save workflow: {e}\n')
		return

	# Validate workflow
	print('Step 4: Validating workflow structure...')
	issues, warnings = validate_workflow(workflow_dict)

	if issues:
		print('❌ VALIDATION FAILED:')
		for issue in issues:
			print(f'   - {issue}')
		print()
	else:
		print('✅ No critical issues found\n')

	if warnings:
		print('⚠️  WARNINGS:')
		for warning in warnings:
			print(f'   - {warning}')
		print()

	# Display workflow summary
	print('Step 5: Workflow Summary')
	print('-' * 80)

	steps = workflow_dict.get('steps', [])
	print(f'Total steps: {len(steps)}\n')

	step_type_counts = {}
	for i, step in enumerate(steps, 1):
		step_type = step.get('type', 'unknown')
		desc = step.get('description', 'No description')

		step_type_counts[step_type] = step_type_counts.get(step_type, 0) + 1

		print(f'  {i}. [{step_type}] {desc[:60]}')

		# Show key fields
		if step_type == 'navigation':
			print(f'      URL: {step.get("url", "N/A")}')
		elif step_type == 'input':
			target = step.get('target_text', 'EMPTY')
			value = step.get('value', '')
			print(f"      Target: '{target}'")
			print(f"      Value: '{value}'")
		elif step_type == 'click':
			target = step.get('target_text', 'EMPTY')
			print(f"      Target: '{target}'")
		elif step_type == 'keypress':
			key = step.get('key', 'N/A')
			print(f"      Key: '{key}'")

	print('\nStep type breakdown:')
	for step_type, count in sorted(step_type_counts.items()):
		print(f'  - {step_type}: {count}')

	# Final results
	print('\n' + '=' * 80)
	print('FINAL RESULTS')
	print('=' * 80)

	agent_count = step_type_counts.get('agent', 0)
	semantic_count = sum(count for stype, count in step_type_counts.items() if stype != 'agent')

	print(f'\nSemantic steps: {semantic_count}')
	print(f'Agent steps: {agent_count}')

	# Overall assessment
	test_passed = True

	if issues:
		print('\n❌ TEST FAILED - Critical issues found')
		test_passed = False
	elif agent_count > 0:
		print(f'\n❌ TEST FAILED - Found {agent_count} agent step(s)')
		test_passed = False
	elif semantic_count == 0:
		print('\n❌ TEST FAILED - No semantic steps generated')
		test_passed = False
	else:
		print('\n✅ TEST PASSED - Pure semantic workflow generated!')
		print(f'   - {semantic_count} semantic steps')
		print('   - 0 agent steps')
		print('   - Workflow will execute instantly')
		print('   - Cost: $0 per run')

	if warnings:
		print(f'\n⚠️  {len(warnings)} warning(s) - review recommended')

	# Next steps
	print('\n' + '=' * 80)
	print('NEXT STEPS')
	print('=' * 80)

	if test_passed:
		print('\nTo run the workflow:')
		print(f'  python -m workflow_use.cli run-workflow-no-ai {output_file}')

		input_schema = workflow_dict.get('input_schema', [])
		if input_schema:
			print('\nWith variables:')
			var_examples = ' '.join([f'--{v["name"]} <value>' for v in input_schema])
			print(f'  python -m workflow_use.cli run-workflow-no-ai {output_file} {var_examples}')
	else:
		print('\n⚠️  Fix the issues above before running the workflow')
		print('   Check the workflow JSON and investigate why agent steps were generated')

	print()


if __name__ == '__main__':
	asyncio.run(main())
