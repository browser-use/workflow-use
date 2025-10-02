import asyncio
import logging
import os

from browser_use import Agent, Browser
from browser_use.llm import ChatOpenAI
from pydantic import SecretStr

from workflow_use.healing._agent.controller import HealingController
from workflow_use.healing.tests.constants import TASK_MESSAGE

logger = logging.getLogger(__name__)


llm = ChatOpenAI(
	base_url='https://api.groq.com/openai/v1',
	model='meta-llama/llama-4-maverick-17b-128e-instruct',
	api_key=SecretStr(os.environ['GROQ_API_KEY']),
	# model='gpt-4.1-mini',
	temperature=0.0,
)
page_extraction_llm = ChatOpenAI(
	base_url='https://api.groq.com/openai/v1',
	model='meta-llama/llama-4-scout-17b-16e-instruct',
	api_key=SecretStr(os.environ['GROQ_API_KEY']),
	temperature=0.0,
)

system_prompt = open('workflow_use/healing/_agent/agent_prompt.md').read()


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
