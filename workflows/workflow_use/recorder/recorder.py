# Example for your new main runner (e.g., in recorder.py or a new script)
import asyncio

from workflow_use.recorder.service import RecordingService  # Adjust import path if necessary


async def run_recording():
	service = RecordingService()
	print('Starting recording session via service...')
	workflow_schema = await service.capture_workflow()

	if workflow_schema:
		print('\n--- MAIN SCRIPT: CAPTURED WORKFLOW ---')
		try:
			print(workflow_schema.model_dump_json(indent=2))
		except AttributeError:
			# Fallback if model_dump_json isn't available (e.g. if it's a dict)
			import json

			print(json.dumps(workflow_schema, indent=2))  # Ensure schema is serializable
		print('------------------------------------')
	else:
		print('MAIN SCRIPT: No workflow was captured.')


if __name__ == '__main__':
	try:
		asyncio.run(run_recording())
	except KeyboardInterrupt:
		print('Main recording script interrupted.')
	except Exception as e:
		print(f'An error occurred in the main recording script: {e}')
