"""
Example: Load recorded workflow and run with cloud browser (no AI)

Prerequisites:
- Set BROWSER_USE_API_KEY env var (get key at https://cloud.browser-use.com)
- Run: python cli.py create-workflow to create tmp/temp_recording_*.json
"""

import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from browser_use.llm import ChatBrowserUse

from workflow_use.workflow.service import Workflow

# Dummy LLM (not used in run_with_no_ai)
llm = ChatBrowserUse(model='bu-latest')


async def main():
	print('🌤️ Loading recorded workflow and running with cloud browser (no AI)')

	# Use example recorded workflow
	workflow_file = Path('examples/example_recording.workflow.json')

	if not workflow_file.exists():
		print(f'❌ Workflow file not found: {workflow_file}')
		return

	# Load workflow with cloud browser enabled
	workflow = Workflow.load_from_file(
		str(workflow_file),
		llm=llm,
		use_cloud=True,  # Enable cloud browser
	)

	try:
		# Run with semantic abstraction (no AI/LLM)
		result = await workflow.run_with_no_ai(close_browser_at_end=True)
		print('✅ Workflow completed with semantic abstraction')
		print(f'📊 Steps executed: {len(result.step_results)}')
	except Exception as e:
		print(f'❌ Error: {e}')
		if 'Authentication' in str(e):
			print('💡 Set BROWSER_USE_API_KEY at https://cloud.browser-use.com')


if __name__ == '__main__':
	asyncio.run(main())
