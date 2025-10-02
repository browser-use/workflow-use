import asyncio
from pathlib import Path

from browser_use.llm import ChatOpenAI

from workflow_use.workflow.service import Workflow

# Instantiate the LLM and the service directly
llm_instance = ChatOpenAI(model='gpt-4.1')  # Or your preferred model


async def test_run_workflow():
	"""
	Tests that the workflow is built correctly from a JSON file path.
	"""
	path = Path(__file__).parent / 'tmp' / 'recording.workflow.json'

	workflow = Workflow.load_from_file(path, llm=llm_instance)
	result = await workflow.run({'model': '12'})
	print(result)


if __name__ == '__main__':
	asyncio.run(test_run_workflow())
