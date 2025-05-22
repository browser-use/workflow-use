import asyncio
from pathlib import Path
from typing import List

# Ensure langchain-openai is installed and OPENAI_API_KEY is set
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from workflow_use.builder.service import BuilderService
from workflow_use.workflow.service import Workflow

# Instantiate the LLM and the service directly
llm_instance = ChatOpenAI(model='gpt-4o')  # Or your preferred model
builder_service = BuilderService(llm=llm_instance)


async def test_run_workflow():
	"""
	Tests that the workflow is built correctly from a JSON file path.
	"""
	path = Path(__file__).parent / 'tmp' / 'recording.workflow.json'

	workflow = Workflow.load_from_file(path)
	result = await workflow.run({'model': '12'})
	print(result)


async def test_scrape_workflow():
	"""
	Tests the scraping functionality of the workflow system.
	This test demonstrates how to extract content from web pages using the workflow's scrape method.
	"""
	path = Path(__file__).parent.parent.parent.parent / 'examples' / 'example.workflow.json'

	# Load the workflow
	workflow = Workflow.load_from_file(path, llm=ChatOpenAI(model='gpt-4o'))

	class ScrapedContent(BaseModel):
		title: str = Field(..., description='The title of the page')
		main_content: str = Field(..., description='The main content of the page')
		title_content: List[str] = Field(default_factory=list, description='List of title and content found on the page')

	# Run the scraping with custom output model and user prompt
	result = await workflow.scrape(
		inputs={'first_name': 'John', 'last_name': 'Doe', 'social_security_last4': '1234'},
		close_browser_at_end=True,
		user_prompt='Extract the main content, title, and links from the page',
		output_model=ScrapedContent,
	)

	print('Scraping Results:')
	print(result.model_dump())


if __name__ == '__main__':
	asyncio.run(test_run_workflow())
