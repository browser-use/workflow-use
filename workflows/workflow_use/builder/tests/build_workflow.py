import asyncio
from pathlib import Path

from browser_use.llm import ChatOpenAI

from workflow_use.builder.service import BuilderService

# Instantiate the LLM and the service directly
llm_instance = ChatOpenAI(model='gpt-4.1')  # Or your preferred model
builder_service = BuilderService(llm=llm_instance)


async def test_build_workflow_from_path():
	"""
	Tests that the workflow is built correctly from a JSON file path.
	"""
	path = Path(__file__).parent / 'tmp' / 'recording.json'
	workflow_definition = await builder_service.build_workflow_from_path(
		path,
		'go to apple.com and extract the price of the iphone XY (where XY is a variable)',
	)

	print(workflow_definition)

	output_path = path.with_suffix('.workflow.json')
	await builder_service.save_workflow_to_path(workflow_definition, output_path)


if __name__ == '__main__':
	asyncio.run(test_build_workflow_from_path())
