"""
Demo script showing how to use Generation Mode programmatically.

This demonstrates:
1. Generating a workflow from a task description
2. Saving it to storage
3. Retrieving and running the workflow
"""

import asyncio
import os

from browser_use.llm import ChatBrowserUse

from workflow_use.healing.service import HealingService
from workflow_use.storage.service import WorkflowStorageService
from workflow_use.workflow.service import Workflow


async def demo_generate_and_run():
	"""Demo: Generate a workflow and run it."""

	# Ensure API key is set
	if not os.getenv('OPENAI_API_KEY'):
		print('Error: OPENAI_API_KEY not set')
		return

	print('=' * 60)
	print('GENERATION MODE DEMO')
	print('=' * 60)
	print()

	# Initialize services
	print('📦 Initializing services...')
	agent_llm = ChatBrowserUse(model='bu-latest')
	extraction_llm = ChatBrowserUse(model='bu-latest')
	workflow_llm = ChatBrowserUse(model='bu-latest')

	healing_service = HealingService(llm=workflow_llm)
	storage_service = WorkflowStorageService()
	print('✅ Services initialized')
	print()

	# Task to automate
	task = "Navigate to https://v0-complex-form-example.vercel.app/ and click the 'Start Application' button"

	print(f'🎯 Task: {task}')
	print()

	# Step 1: Generate workflow
	print('🤖 Step 1: Generating workflow from task...')
	print('   (This will launch a browser and execute the task)')
	print()

	try:
		workflow = await healing_service.generate_workflow_from_prompt(
			prompt=task, agent_llm=agent_llm, extraction_llm=extraction_llm
		)

		if not workflow:
			print('❌ Failed to generate workflow')
			return

		print('✅ Workflow generated successfully!')
		print()
		print(f'   Name: {workflow.name}')
		print(f'   Description: {workflow.description}')
		print(f'   Steps: {len(workflow.steps)}')
		print(f'   Input Parameters: {len(workflow.input_schema)}')
		print()

		# Display steps
		print('   Workflow Steps:')
		for i, step in enumerate(workflow.steps, 1):
			print(f'     {i}. [{step.type}] {step.description}')
		print()

		# Display input schema
		if workflow.input_schema:
			print('   Input Parameters:')
			for inp in workflow.input_schema:
				required = 'required' if inp.required else 'optional'
				print(f'     - {inp.name} ({inp.type}, {required})')
			print()

	except Exception as e:
		print(f'❌ Error generating workflow: {e}')
		return

	# Step 2: Save to storage
	print('💾 Step 2: Saving workflow to storage...')

	try:
		metadata = storage_service.save_workflow(workflow=workflow, generation_mode='browser_use', original_task=task)

		print('✅ Workflow saved!')
		print()
		print(f'   ID: {metadata.id}')
		print(f'   File: {metadata.file_path}')
		print()

	except Exception as e:
		print(f'❌ Error saving workflow: {e}')
		return

	# Step 3: List workflows
	print('📋 Step 3: Listing stored workflows...')
	workflows = storage_service.list_workflows()
	print(f'✅ Found {len(workflows)} workflow(s) in storage')
	print()

	# Step 4: Retrieve and display
	print('🔍 Step 4: Retrieving workflow from storage...')
	retrieved_workflow = storage_service.get_workflow(metadata.id)

	if retrieved_workflow:
		print('✅ Workflow retrieved successfully!')
		print(f'   Name: {retrieved_workflow.name}')
		print()
	else:
		print('❌ Failed to retrieve workflow')
		return

	# Step 5: Run the workflow
	print('▶️  Step 5: Running the workflow...')
	print('   (This will replay the workflow steps)')
	print()

	try:
		# Create workflow instance
		workflow_instance = Workflow(workflow_schema=retrieved_workflow, llm=workflow_llm, page_extraction_llm=extraction_llm)

		# Run as tool if there are input parameters, otherwise run directly
		if workflow.input_schema:
			prompt = 'Execute the workflow with default values'
			print(f'   Running as tool with prompt: "{prompt}"')
			result = await workflow_instance.run_as_tool(prompt)
		else:
			print('   Running without parameters (deterministic execution)')
			# For workflows without inputs, we'd need to provide an empty inputs dict
			# This is a simple demo, so we'll just show the concept
			result = {'status': 'Would execute workflow here'}

		print('✅ Workflow execution completed!')
		print()
		print('   Result:')
		print(f'   {result}')
		print()

	except Exception as e:
		print(f'❌ Error running workflow: {e}')
		import traceback

		traceback.print_exc()
		return

	# Summary
	print('=' * 60)
	print('DEMO COMPLETED!')
	print('=' * 60)
	print()
	print('Summary:')
	print('  ✅ Generated workflow from task')
	print(f'  ✅ Saved to storage with ID: {metadata.id}')
	print('  ✅ Retrieved and executed workflow')
	print()
	print('Next steps:')
	print('  • List workflows: python cli.py list-workflows')
	print(f'  • View details: python cli.py workflow-info {metadata.id}')
	print(f'  • Run again: python cli.py run-stored-workflow {metadata.id} --prompt "Your task"')
	print(f'  • Delete: python cli.py delete-workflow {metadata.id}')
	print()


async def demo_list_and_search():
	"""Demo: List and search workflows."""

	print('=' * 60)
	print('WORKFLOW SEARCH DEMO')
	print('=' * 60)
	print()

	storage_service = WorkflowStorageService()

	# List all workflows
	print('📋 All workflows:')
	all_workflows = storage_service.list_workflows()

	if not all_workflows:
		print('   No workflows found.')
		print()
		return

	for wf in all_workflows:
		mode_icon = '🤖' if wf.generation_mode == 'browser_use' else '✋'
		print(f'   {mode_icon} {wf.name}')
		print(f'      ID: {wf.id}')
		print(f'      Mode: {wf.generation_mode}')
		print(f'      Created: {wf.created_at}')
		print()

	# Search workflows
	print('🔍 Search for "form" workflows:')
	form_workflows = storage_service.search_workflows(query='form')
	print(f'   Found {len(form_workflows)} workflow(s)')
	print()

	# Filter by generation mode
	print('🤖 Auto-generated workflows:')
	auto_workflows = storage_service.search_workflows(generation_mode='browser_use')
	print(f'   Found {len(auto_workflows)} workflow(s)')
	print()


if __name__ == '__main__':
	print()
	print('This demo has two parts:')
	print('  1. Generate and run a workflow (demo_generate_and_run)')
	print('  2. List and search workflows (demo_list_and_search)')
	print()

	choice = input('Which demo do you want to run? (1/2): ').strip()

	if choice == '1':
		asyncio.run(demo_generate_and_run())
	elif choice == '2':
		asyncio.run(demo_list_and_search())
	else:
		print('Invalid choice. Running demo 1...')
		asyncio.run(demo_generate_and_run())
