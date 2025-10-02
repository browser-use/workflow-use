import asyncio
import json
import os
from pathlib import Path

import aiofiles
from browser_use.llm import ChatOpenAI
from pydantic import SecretStr

from workflow_use.healing.service import HealingService
from workflow_use.healing.tests.constants import TASK_MESSAGE


async def test_generate_workflow_from_prompt():
	"""
	Test the complete workflow generation from prompt using 3 separate LLMs:
	1. Workflow creation LLM (high-quality model for structured output)
	2. Agent LLM (faster model for browser automation)
	3. Extraction LLM (specialized model for page content extraction)
	"""

	# LLM for workflow creation (use high-quality model)
	workflow_llm = ChatOpenAI(
		model='gpt-4.1',
		temperature=0.0,
	)

	# LLM for browser agent (can use faster model)
	agent_llm = ChatOpenAI(
		base_url='https://api.groq.com/openai/v1',
		model='meta-llama/llama-4-maverick-17b-128e-instruct',
		api_key=SecretStr(os.environ['GROQ_API_KEY']),
		temperature=0.0,
	)

	# LLM for page extraction (specialized model)
	extraction_llm = ChatOpenAI(
		base_url='https://api.groq.com/openai/v1',
		model='meta-llama/llama-4-scout-17b-16e-instruct',
		api_key=SecretStr(os.environ['GROQ_API_KEY']),
		temperature=0.0,
	)

	# Initialize the healing service with 3 separate LLMs
	healing_service = HealingService(
		llm=workflow_llm,  # For workflow creation
	)

	# Define the task prompt
	task_prompt = TASK_MESSAGE

	try:
		# Generate workflow definition from prompt
		workflow_definition = await healing_service.generate_workflow_from_prompt(task_prompt, agent_llm, extraction_llm)

		# Save the workflow definition
		file_save_path = Path('./tmp/generated_workflow.json')
		file_save_path.parent.mkdir(exist_ok=True)

		async with aiofiles.open(file_save_path, mode='w') as f:
			await f.write(json.dumps(workflow_definition.model_dump(), indent=2))

		print(f'Workflow definition saved to {file_save_path}')
		print(f'Generated {len(workflow_definition.steps)} workflow steps')

	except Exception as e:
		print(f'Error generating workflow: {e}')
		raise


if __name__ == '__main__':
	asyncio.run(test_generate_workflow_from_prompt())
