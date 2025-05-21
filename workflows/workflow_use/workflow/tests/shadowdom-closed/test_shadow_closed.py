import os
from pathlib import Path
from threading import Thread
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from workflow_use.workflow.service import Workflow

TEST_DIR = Path(__file__).parent

WORKFLOW_FILE = TEST_DIR / 'shadow-closed.workflow.json'


def start_server():
	os.chdir(TEST_DIR)
	server = ThreadingHTTPServer(('127.0.0.1', 8000), SimpleHTTPRequestHandler)
	t = Thread(target=server.serve_forever, daemon=True)
	t.start()
	return server, t


# ----------------------------- test ----------------------------------------
@pytest.mark.asyncio
async def test_shadow_closed_workflow():
	server, thread = start_server()
	try:
		workflow = Workflow.load_from_file(str(WORKFLOW_FILE))
		workflow.fallback_to_agent = False
		await workflow.run(close_browser_at_end=False)

		ctx = workflow.browser_context.session.context
		page = ctx.pages[0] if ctx.pages else await ctx.new_page()
		value = await page.input_value('css=outer-closed >> inner-closed >> #inner-input')
		assert value == 'hello-closed'
	finally:
		await workflow.browser_context.__aexit__(None, None, None)
		await workflow.browser.close()
		server.shutdown()
		thread.join()
