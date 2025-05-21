import asyncio
import os
from pathlib import Path
from threading import Thread
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from workflow_use.workflow.service import Workflow


TEST_DIR = Path(__file__).parent



def start_server():
    os.chdir(TEST_DIR)
    server = ThreadingHTTPServer(("127.0.0.1", 8000), SimpleHTTPRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


@pytest.mark.asyncio
async def test_shadow_nextjs_workflow():
    server, thread = start_server()
    try:
        wf_path = TEST_DIR / "shadow-next.workflow.json"
        workflow = Workflow.load_from_file(str(wf_path))
        await workflow.run(close_browser_at_end=True)
    finally:
        server.shutdown()
        thread.join()
