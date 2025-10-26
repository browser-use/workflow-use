"""
Test script to demonstrate deterministic workflow generation.

This approach converts browser-use agent actions to semantic workflow steps
WITHOUT using LLM for step creation. LLM is only used for variable identification.

Benefits:
- Much faster (no LLM calls for step creation)
- More deterministic and predictable
- Lower cost (fewer LLM calls)
- Direct mapping from actions to semantic steps
"""

import asyncio
import json

import aiofiles
from browser_use.llm import ChatBrowserUse

from workflow_use.healing.service import HealingService


async def test_deterministic_generation():
	"""Test deterministic workflow generation vs LLM-based generation."""

	# Task to generate workflow for
	task = 'Go to GitHub, search for the browser-use repository, and get its star count'

	print('=' * 80)
	print('DETERMINISTIC WORKFLOW GENERATION TEST')
	print('=' * 80)
	print(f'\nTask: {task}\n')

	# Initialize LLM (still needed for variable identification and browser agent)
	llm = ChatBrowserUse(model='bu-latest')

	# Test 1: Deterministic conversion (new approach)
	print('\n' + '=' * 80)
	print('TEST 1: DETERMINISTIC CONVERSION (Action → Semantic Step)')
	print('=' * 80)

	healing_service_deterministic = HealingService(
		llm=llm,
		enable_variable_extraction=True,
		use_deterministic_conversion=True,  # 🔑 Enable deterministic mode
	)

	try:
		workflow_deterministic = await healing_service_deterministic.generate_workflow_from_prompt(
			prompt=task, agent_llm=llm, extraction_llm=llm
		)

		# Save the workflow
		workflow_dict = workflow_deterministic.model_dump(exclude_none=True)

		output_file = 'deterministic_workflow.workflow.json'
		async with aiofiles.open(output_file, 'w') as f:
			await f.write(json.dumps(workflow_dict, indent=2))

		print(f'\n✅ Deterministic workflow saved to: {output_file}')

		# Analyze the workflow
		steps = workflow_dict.get('steps', [])
		print(f'\nGenerated {len(steps)} steps:')

		step_types = {}
		for step in steps:
			step_type = step.get('type', 'unknown')
			step_types[step_type] = step_types.get(step_type, 0) + 1
			print(f'  - {step_type}: {step.get("description", "No description")}')

		print('\nStep type breakdown:')
		for step_type, count in step_types.items():
			print(f'  {step_type}: {count}')

		# Check for agent steps (should be ZERO with deterministic conversion)
		agent_step_count = step_types.get('agent', 0)
		if agent_step_count == 0:
			print('\n✅ SUCCESS: No agent steps! Pure semantic workflow.')
		else:
			print(f'\n⚠️  WARNING: Found {agent_step_count} agent steps')

	except Exception as e:
		print(f'\n❌ Deterministic generation failed: {e}')
		import traceback

		traceback.print_exc()

	# Test 2: LLM-based conversion (original approach) for comparison
	print('\n' + '=' * 80)
	print('TEST 2: LLM-BASED CONVERSION (for comparison)')
	print('=' * 80)

	healing_service_llm = HealingService(
		llm=llm,
		enable_variable_extraction=True,
		use_deterministic_conversion=False,  # Use LLM for step creation
	)

	try:
		workflow_llm = await healing_service_llm.generate_workflow_from_prompt(prompt=task, agent_llm=llm, extraction_llm=llm)

		# Save the workflow
		workflow_dict_llm = workflow_llm.model_dump(exclude_none=True)

		output_file_llm = 'llm_based_workflow.workflow.json'
		async with aiofiles.open(output_file_llm, 'w') as f:
			await f.write(json.dumps(workflow_dict_llm, indent=2))

		print(f'\n✅ LLM-based workflow saved to: {output_file_llm}')

		# Analyze the workflow
		steps_llm = workflow_dict_llm.get('steps', [])
		print(f'\nGenerated {len(steps_llm)} steps:')

		step_types_llm = {}
		for step in steps_llm:
			step_type = step.get('type', 'unknown')
			step_types_llm[step_type] = step_types_llm.get(step_type, 0) + 1
			print(f'  - {step_type}: {step.get("description", "No description")}')

		print('\nStep type breakdown:')
		for step_type, count in step_types_llm.items():
			print(f'  {step_type}: {count}')

		# Check for agent steps
		agent_step_count_llm = step_types_llm.get('agent', 0)
		if agent_step_count_llm == 0:
			print('\n✅ No agent steps in LLM-based workflow')
		else:
			print(f'\n⚠️  Found {agent_step_count_llm} agent steps in LLM-based workflow')

	except Exception as e:
		print(f'\n❌ LLM-based generation failed: {e}')
		import traceback

		traceback.print_exc()

	# Comparison
	print('\n' + '=' * 80)
	print('COMPARISON SUMMARY')
	print('=' * 80)

	print('\nDeterministic Conversion:')
	print('  ✅ No LLM calls for step creation (faster, cheaper)')
	print('  ✅ Direct action → semantic step mapping (deterministic)')
	print('  ✅ Guaranteed semantic steps (no agent steps)')
	print('  ⚠️  May need LLM for variable identification')

	print('\nLLM-Based Conversion:')
	print('  ⚠️  Requires LLM call for step creation (slower, more expensive)')
	print('  ⚠️  Non-deterministic (LLM may generate different steps)')
	print('  ⚠️  May generate agent steps (slower execution)')
	print('  ✅ Better at understanding context and intent')

	print('\n' + '=' * 80)


if __name__ == '__main__':
	asyncio.run(test_deterministic_generation())
