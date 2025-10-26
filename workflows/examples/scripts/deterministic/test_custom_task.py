"""
Quick test script for deterministic workflow generation with a custom task.

Usage:
    python test_custom_task.py
"""

import asyncio
import json

import aiofiles
from browser_use.llm import ChatBrowserUse

from workflow_use.healing.service import HealingService


async def main():
	# 🔧 CUSTOMIZE THIS - Change to your task
	task = """
    Go to GitHub, search for the stagehand repository,
    click on it, and extract the star count.
    """

	print('Testing Deterministic Workflow Generation')
	print('=' * 80)
	print(f'Task: {task.strip()}\n')

	llm = ChatBrowserUse(model='bu-latest')

	# Create service with deterministic conversion
	service = HealingService(
		llm=llm,
		use_deterministic_conversion=True,  # 🔑 Deterministic mode
	)

	print('Recording browser interactions and generating workflow...')
	print('(This will open a browser and complete the task)\n')

	try:
		workflow = await service.generate_workflow_from_prompt(prompt=task, agent_llm=llm, extraction_llm=llm)

		# Save and analyze
		workflow_dict = workflow.model_dump(exclude_none=True)

		async with aiofiles.open('test_output.workflow.json', 'w') as f:
			await f.write(json.dumps(workflow_dict, indent=2))

		print('\n' + '=' * 80)
		print('RESULTS')
		print('=' * 80)

		steps = workflow_dict.get('steps', [])
		print(f'\n✅ Generated {len(steps)} steps\n')

		# Analyze step types
		agent_steps = 0
		semantic_steps = 0

		for i, step in enumerate(steps, 1):
			step_type = step.get('type')
			desc = step.get('description', 'No description')[:60]

			print(f'{i}. [{step_type}] {desc}')

			# Show important fields
			if step_type == 'input':
				target = step.get('target_text', 'MISSING')
				value = step.get('value', '')
				print(f"   → target_text: '{target}'")
				print(f"   → value: '{value}'")
			elif step_type == 'click':
				target = step.get('target_text', 'MISSING')
				print(f"   → target_text: '{target}'")

			# Count step types
			if step_type == 'agent':
				agent_steps += 1
			else:
				semantic_steps += 1

		print('\n' + '=' * 80)
		print('SUMMARY')
		print('=' * 80)
		print(f'Semantic steps: {semantic_steps}')
		print(f'Agent steps: {agent_steps}')

		if agent_steps == 0:
			print('\n✅ SUCCESS! Pure semantic workflow (instant execution, $0/run)')
		else:
			print(f'\n❌ FAILED! Found {agent_steps} agent steps (slow, expensive)')

		print('\nWorkflow saved to: test_output.workflow.json')
		print('\nTo run it:')
		print('  python -m workflow_use.cli run-workflow-no-ai test_output.workflow.json')

	except Exception as e:
		print(f'\n❌ ERROR: {e}')
		import traceback

		traceback.print_exc()


if __name__ == '__main__':
	asyncio.run(main())
