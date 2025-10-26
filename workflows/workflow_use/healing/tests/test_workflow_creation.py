import asyncio
import json
from pathlib import Path

import aiofiles
from browser_use import AgentHistoryList
from browser_use.agent.views import AgentOutput
from browser_use.llm import ChatBrowserUse

from workflow_use.healing._agent.controller import HealingController
from workflow_use.healing.service import HealingService
from workflow_use.healing.tests.constants import TASK_MESSAGE

llm = ChatBrowserUse(model='bu-latest')


ActionModel = HealingController(extraction_llm=llm).registry.create_action_model()
WorkflowAgentOutput = AgentOutput.type_with_custom_actions(ActionModel)


async def test_workflow_creation():
	healing_service = HealingService(llm)

	history_list = AgentHistoryList.load_from_file('./tmp/history.json', output_model=WorkflowAgentOutput)

	workflow_definition = await healing_service.create_workflow_definition(TASK_MESSAGE, history_list)

	file_save_path = Path('./tmp/workflow_definition.json')

	# save to json
	async with aiofiles.open(file_save_path, mode='w') as f:
		await f.write(json.dumps(workflow_definition.model_dump(), indent=2))

	print(f'file saved to {file_save_path}')


if __name__ == '__main__':
	asyncio.run(test_workflow_creation())
