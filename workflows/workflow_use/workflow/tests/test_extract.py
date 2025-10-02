import asyncio
from pathlib import Path

from browser_use.llm import ChatOpenAI
from pydantic import BaseModel

from workflow_use.workflow.service import Workflow

# Instantiate the LLM and the service directly
llm_instance = ChatOpenAI(model='gpt-4.1')  # Or your preferred model
page_extraction_llm = ChatOpenAI(model='gpt-4.1-mini')


class OutputModel(BaseModel):
	api_key: str


async def test_run_workflow():
	"""
	Tests that the workflow is built correctly from a JSON file path.
	"""
	path = Path(__file__).parent / 'tmp' / 'extract.workflow.json'

	workflow = Workflow.load_from_file(path, llm=llm_instance, page_extraction_llm=page_extraction_llm)

	result = await workflow.run({'api_key_name': 'test key'}, output_model=OutputModel)

	assert result.output_model is not None

	print(result.output_model.api_key)


if __name__ == '__main__':
	asyncio.run(test_run_workflow())
