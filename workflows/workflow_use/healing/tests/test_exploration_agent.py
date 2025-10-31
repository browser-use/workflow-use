import asyncio
import logging
import os
from pathlib import Path

from browser_use import Agent, Browser
from browser_use.llm import ChatBrowserUse
from pydantic import SecretStr

from workflow_use.healing._agent.controller import HealingController
from workflow_use.healing.tests.constants import TASK_MESSAGE

logger = logging.getLogger(__name__)


llm = ChatBrowserUse(
	base_url='https://api.groq.com/openai/v1',
	model='meta-llama/llama-4-maverick-17b-128e-instruct',
	api_key=SecretStr(os.environ['GROQ_API_KEY']),
	# model='bu-latest',
	temperature=0.0,
)
page_extraction_llm = ChatBrowserUse(
	base_url='https://api.groq.com/openai/v1',
	model='meta-llama/llama-4-scout-17b-16e-instruct',
	api_key=SecretStr(os.environ['GROQ_API_KEY']),
	temperature=0.0,
)

# Use absolute path for prompt file
_PROMPT_FILE = Path(__file__).parent.parent / '_agent' / 'agent_prompt.md'
system_prompt = _PROMPT_FILE.read_text()


async def explore_page():
	browser = Browser()

	agent = Agent(
		task=TASK_MESSAGE,
		browser_session=browser,
		llm=llm,
		page_extraction_llm=page_extraction_llm,
		controller=HealingController(extraction_llm=page_extraction_llm),
		override_system_message=system_prompt,
		enable_memory=False,
		max_failures=10,
		# max_actions_per_step=1,
		tool_calling_method='auto',
	)

	history = await agent.run()

	history.save_to_file('./tmp/history.json')


if __name__ == '__main__':
	asyncio.run(explore_page())
