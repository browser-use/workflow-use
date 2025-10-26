"""
Simple script to automatically generate a workflow with variables from a task description.

Usage:
    cd workflows
    uv run python examples/auto_generate_workflow.py
"""

import asyncio
import os

import aiofiles
from browser_use.llm import ChatBrowserUse

from workflow_use.healing.service import HealingService


async def auto_generate_workflow():
	"""Automatically generate a workflow with variables from a task description."""

	# Check for API key
	if not os.getenv('OPENAI_API_KEY'):
		print('❌ Error: OPENAI_API_KEY environment variable not set')
		print('   Please set it with: export OPENAI_API_KEY=your_key_here')
		return

	print('=' * 70)
	print('AUTOMATIC WORKFLOW GENERATION WITH VARIABLES')
	print('=' * 70)
	print()

	# Your task description - the LLM will automatically identify variables!
	task = """
    Go to GitHub, search for the browser-use repository, click on it, and extract the star count.
    """

	print('🎯 Task Description:')
	print(f'   {task.strip()}')
	print()

	# Initialize LLM
	print('🔧 Initializing LLM...')
	llm = ChatBrowserUse(model='bu-latest')
	print('   ✅ LLM initialized')
	print()

	# Create healing service
	print('🔧 Creating HealingService...')
	healing_service = HealingService(llm=llm)
	print('   ✅ HealingService ready')
	print()

	# Generate workflow - variables will be created automatically!
	print('🤖 Generating workflow (this will open a browser and execute the task)...')
	print('   The LLM will:')
	print('   1. Execute the task in a browser')
	print('   2. Record all actions')
	print('   3. Automatically identify which values should be variables')
	print('   4. Create semantic target_text fields')
	print('   5. Generate a reusable workflow')
	print()

	try:
		workflow = await healing_service.generate_workflow_from_prompt(prompt=task, agent_llm=llm, extraction_llm=llm)

		if not workflow:
			print('❌ Failed to generate workflow')
			return

		print('✅ Workflow generated successfully!')
		print()

		# Display workflow details
		print('=' * 70)
		print('WORKFLOW DETAILS')
		print('=' * 70)
		print()
		print(f'📋 Name: {workflow.name}')
		print(f'📝 Description: {workflow.description}')
		print(f'🔧 Total Steps: {len(workflow.steps)}')
		print()

		# Display automatically detected variables
		print('🔄 AUTOMATICALLY DETECTED VARIABLES:')
		if workflow.input_schema:
			for inp in workflow.input_schema:
				required = '✓ required' if inp.required else '○ optional'
				format_str = f' (format: {inp.format})' if hasattr(inp, 'format') and inp.format else ''
				print(f'   • {inp.name}: {inp.type} [{required}]{format_str}')
		else:
			print('   (No variables detected)')
		print()

		# Display workflow steps
		print('📍 WORKFLOW STEPS:')
		for i, step in enumerate(workflow.steps, 1):
			print(f'   {i}. [{step.type.upper()}] {step.description}')

			# Show if step uses variables
			if hasattr(step, 'value') and step.value and '{' in str(step.value):
				print(f'      └─ value: {step.value}')
			if hasattr(step, 'target_text') and step.target_text and '{' in str(step.target_text):
				print(f'      └─ target_text: {step.target_text} ⭐ (semantic + variable!)')
		print()

		# Save the workflow
		output_file = 'auto_generated_workflow.workflow.json'
		print(f'💾 Saving workflow to: {output_file}')

		# Convert to dict and save
		import json

		workflow_dict = workflow.model_dump() if hasattr(workflow, 'model_dump') else workflow.dict()

		async with aiofiles.open(output_file, 'w') as f:
			await f.write(json.dumps(workflow_dict, indent=2))

		print(f'   ✅ Saved to: {output_file}')
		print()

		# Show next steps
		print('=' * 70)
		print('NEXT STEPS')
		print('=' * 70)
		print()
		print('1️⃣  View the workflow file:')
		print(f'   cat {output_file}')
		print()
		print('2️⃣  Run the workflow with different inputs:')
		print(f'   python workflows/cli.py run-workflow {output_file}')
		print()
		print('3️⃣  Run without AI (semantic mode):')
		print(f'   python workflows/cli.py run-workflow-no-ai {output_file}')
		print()
		print('4️⃣  Customize the workflow:')
		print(f'   - Edit {output_file}')
		print('   - Add more variables')
		print('   - Modify steps')
		print()

	except Exception as e:
		print(f'❌ Error generating workflow: {e}')
		import traceback

		traceback.print_exc()
		return


if __name__ == '__main__':
	print()
	asyncio.run(auto_generate_workflow())
	print()
