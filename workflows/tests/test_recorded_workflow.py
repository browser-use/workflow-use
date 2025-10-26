"""Test recorded workflow execution"""

import asyncio
import logging

from browser_use.llm import ChatBrowserUse

from workflow_use.workflow.service import Workflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
	llm = ChatBrowserUse(model='bu-latest')
	workflow = Workflow.load_from_file('tmp/temp_recording_kn1yz829.json', llm)

	logger.info('Starting workflow execution...')
	try:
		result = await workflow.run(inputs={}, close_browser_at_end=False)
		logger.info(f'✅ Workflow completed: {result}')
	except Exception as e:
		logger.error(f'❌ Workflow failed: {e}', exc_info=True)


if __name__ == '__main__':
	asyncio.run(main())
