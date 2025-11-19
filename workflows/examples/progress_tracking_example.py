"""
Example: Real-time Progress Tracking for Workflow Generation

This example demonstrates how to use the new on_step_recorded and on_status_update
callbacks to track workflow generation progress in real-time.

Usage:
    python examples/progress_tracking_example.py
"""

import asyncio
from datetime import datetime

from browser_use.llm import ChatBrowserUse

from workflow_use.healing.service import HealingService


# Example 1: Simple console logging
async def simple_console_example():
	"""Basic example: Print steps to console as they're recorded."""
	print('=' * 80)
	print('EXAMPLE 1: Simple Console Logging')
	print('=' * 80)

	def step_callback(step_data: dict):
		"""Called each time a step is recorded."""
		print(f'\n📍 Step {step_data["step_number"]}: {step_data["description"]}')
		print(f'   Type: {step_data["action_type"]}')
		print(f'   URL: {step_data["url"]}')
		if step_data.get('target_text'):
			print(f'   Target: {step_data["target_text"]}')
		if step_data.get('extracted_data'):
			print(f'   Extracted: {step_data["extracted_data"]}')

	def status_callback(status: str):
		"""Called for general status updates."""
		print(f'\n🔄 {status}')

	# Initialize service
	llm = ChatBrowserUse(model='bu-latest')
	healing_service = HealingService(
		llm=llm,
		use_deterministic_conversion=True,
		enable_variable_extraction=True,
	)

	# Generate workflow with callbacks
	workflow = await healing_service.generate_workflow_from_prompt(
		prompt='Go to example.com and extract the page title',
		agent_llm=llm,
		extraction_llm=llm,
		use_cloud=False,
		on_step_recorded=step_callback,
		on_status_update=status_callback,
	)

	print(f'\n✅ Generated workflow with {len(workflow.steps)} steps!')


# Example 2: Store steps in a list (for database storage)
async def database_storage_example():
	"""Example: Store steps in memory (simulates database storage)."""
	print('\n' + '=' * 80)
	print('EXAMPLE 2: Database Storage Pattern')
	print('=' * 80)

	# Simulated database storage
	stored_steps = []
	status_history = []

	async def step_callback(step_data: dict):
		"""Store step in database (simulated with list)."""
		stored_steps.append(step_data)
		print(f'✓ Stored step {step_data["step_number"]} in database')

	async def status_callback(status: str):
		"""Store status update in database."""
		status_history.append({'timestamp': datetime.now().isoformat(), 'status': status})
		print(f'ℹ️  {status}')

	# Initialize service
	llm = ChatBrowserUse(model='bu-latest')
	healing_service = HealingService(
		llm=llm,
		use_deterministic_conversion=True,
		enable_variable_extraction=True,
	)

	# Generate workflow with async callbacks
	workflow = await healing_service.generate_workflow_from_prompt(
		prompt='Go to example.com and extract the page title',
		agent_llm=llm,
		extraction_llm=llm,
		use_cloud=False,
		on_step_recorded=lambda data: asyncio.create_task(step_callback(data)),
		on_status_update=lambda status: asyncio.create_task(status_callback(status)),
	)

	# Display stored data
	print(f'\n📊 Stored {len(stored_steps)} steps and {len(status_history)} status updates')
	print('\nStored Steps:')
	for step in stored_steps:
		print(f'  {step["step_number"]}. {step["description"]}')

	print('\nStatus History:')
	for status in status_history:
		print(f'  [{status["timestamp"]}] {status["status"]}')


# Example 3: Real-time progress bar
async def progress_bar_example():
	"""Example: Show progress with a simple progress indicator."""
	print('\n' + '=' * 80)
	print('EXAMPLE 3: Progress Bar')
	print('=' * 80)

	step_count = {'count': 0}

	def step_callback(step_data: dict):
		"""Update progress bar as steps are recorded."""
		step_count['count'] = step_data['step_number']
		# Simple progress indicator
		bar = '█' * step_data['step_number'] + '░' * (10 - step_data['step_number'])
		print(f'\rProgress: [{bar}] Step {step_data["step_number"]}: {step_data["description"][:40]}...', end='')

	def status_callback(status: str):
		"""Display status updates."""
		print(f'\n\n🔄 {status}')

	# Initialize service
	llm = ChatBrowserUse(model='bu-latest')
	healing_service = HealingService(
		llm=llm,
		use_deterministic_conversion=True,
		enable_variable_extraction=True,
	)

	# Generate workflow with callbacks
	workflow = await healing_service.generate_workflow_from_prompt(
		prompt='Go to example.com and extract the page title',
		agent_llm=llm,
		extraction_llm=llm,
		use_cloud=False,
		on_step_recorded=step_callback,
		on_status_update=status_callback,
	)

	print(f'\n\n✅ Completed! Generated workflow with {step_count["count"]} steps')


# Example 4: Real-world pattern for Browser-Use Cloud backend
async def cloud_backend_pattern():
	"""
	Example: Pattern for Browser-Use Cloud backend integration.

	This shows how to integrate with your database to store steps
	in real-time for frontend polling.
	"""
	print('\n' + '=' * 80)
	print('EXAMPLE 4: Browser-Use Cloud Backend Pattern')
	print('=' * 80)

	# Simulated workflow_id (would come from your database)
	workflow_id = 'wf_123abc'
	generation_metadata = {'steps': [], 'status_history': []}

	async def step_callback(step_data: dict):
		"""
		Store step immediately in database for real-time display.

		In your actual implementation, this would be:
		async with await database.get_session() as session:
		    workflow = await get_workflow(session, workflow_id)
		    if workflow and workflow.generation_metadata:
		        steps = workflow.generation_metadata.get('steps', [])
		        steps.append(step_data)
		        workflow.generation_metadata['steps'] = steps
		        await session.commit()
		"""
		# Simulated database storage
		generation_metadata['steps'].append(step_data)

		print(f'💾 Stored step {step_data["step_number"]} to workflow {workflow_id}')
		print(f'   Description: {step_data["description"]}')
		print(f'   Type: {step_data["action_type"]}')
		print(f'   Timestamp: {step_data["timestamp"]}')

	async def status_callback(status: str):
		"""Store status updates for display in the frontend."""
		status_entry = {'timestamp': datetime.now().isoformat(), 'message': status}
		generation_metadata['status_history'].append(status_entry)

		print(f'ℹ️  Status update: {status}')

	# Initialize service
	llm = ChatBrowserUse(model='bu-latest')
	healing_service = HealingService(
		llm=llm,
		use_deterministic_conversion=True,
		enable_variable_extraction=True,
	)

	# Generate workflow with progress tracking
	print(f'\n🚀 Starting workflow generation for {workflow_id}...')

	workflow = await healing_service.generate_workflow_from_prompt(
		prompt='Go to example.com and extract the page title',
		agent_llm=llm,
		extraction_llm=llm,
		use_cloud=False,
		on_step_recorded=lambda data: asyncio.create_task(step_callback(data)),
		on_status_update=lambda status: asyncio.create_task(status_callback(status)),
	)

	# Display final metadata (what would be in your database)
	print('\n' + '=' * 80)
	print('FINAL DATABASE STATE')
	print('=' * 80)
	print(f'\nWorkflow ID: {workflow_id}')
	print(f'Total Steps Recorded: {len(generation_metadata["steps"])}')
	print(f'Total Status Updates: {len(generation_metadata["status_history"])}')

	print('\n📋 Steps Timeline:')
	for step in generation_metadata['steps']:
		print(f'  [{step["timestamp"]}] Step {step["step_number"]}: {step["description"]}')

	print('\n📊 Status Timeline:')
	for status in generation_metadata['status_history']:
		print(f'  [{status["timestamp"]}] {status["message"]}')

	print(f'\n✅ Workflow generation complete! Final workflow has {len(workflow.steps)} steps')


# Run all examples
async def main():
	"""Run all examples (commented out to avoid actual API calls)."""
	print('Progress Tracking Examples')
	print('=' * 80)
	print('\nThese examples demonstrate different patterns for tracking')
	print('workflow generation progress in real-time.')
	print('\nNote: Examples are commented out to avoid actual API calls.')
	print('Uncomment the examples you want to run.\n')

	# Uncomment the examples you want to run:

	# await simple_console_example()
	# await database_storage_example()
	# await progress_bar_example()
	# await cloud_backend_pattern()

	print('\n✅ Examples completed!')


if __name__ == '__main__':
	asyncio.run(main())
