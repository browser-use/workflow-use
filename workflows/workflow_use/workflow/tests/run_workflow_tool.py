import asyncio
from pathlib import Path

from browser_use.llm import ChatOpenAI

from workflow_use.workflow.service import Workflow

# Instantiate the LLM and the service directly
llm_instance = ChatOpenAI(model='gpt-4.1-mini')  # Or your preferred model
page_extraction_llm = ChatOpenAI(model='gpt-4.1-mini')


async def test_run_workflow():
	"""
	Tests that the workflow is built correctly from a JSON file path.
	"""
	path = Path(__file__).parent.parent.parent.parent / 'tmp' / 'workflow_definition.json'

	workflow = Workflow.load_from_file(path, llm=llm_instance, page_extraction_llm=page_extraction_llm)
	result = await workflow.run_as_tool(
		'john, doe, test@test.com, +15555555555, cesta blmasd 123, san francisco, california, 12341, 1st of may 2002, male, citizen, unemployed, 150k+ income, license application, make up excuse'
	)
	print(result)


if __name__ == '__main__':
	asyncio.run(test_run_workflow())
