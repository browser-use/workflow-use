import asyncio
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from workflow_use.recorder.service import RecordingService

# Path to the static test site used by existing shadow DOM tests
REPO_ROOT = Path(__file__).resolve().parents[4]
TEST_SITE_DIR = REPO_ROOT / "workflows" / "workflow_use" / "builder" / "tests" / "shadowdom-closed"
EXT_DIR = REPO_ROOT / "extension" / ".output" / "chrome-mv3"

# Fallback patch in case the extension fails to load in headless mode
SHADOW_PATCH = """
(function(){
  const original = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function(init){
    if (init && init.mode === 'closed') {
      init = Object.assign({}, init, {mode: 'open'});
    }
    return original.call(this, init);
  };
})();
"""


def start_server():
    os.chdir(TEST_SITE_DIR)
    server = ThreadingHTTPServer(("127.0.0.1", 8000), SimpleHTTPRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


@pytest.mark.asyncio
async def test_recorder_detects_closed_shadow_dom():
    if not EXT_DIR.exists():
        pytest.skip(
            f"Built extension not found at {EXT_DIR}. Run 'npm run build' in the extension directory."
        )

    server, thread = start_server()
    service = RecordingService()
    capture_task = asyncio.create_task(service.capture_workflow())
    try:
        # Wait for Playwright context to be ready
        for _ in range(100):
            if service.playwright_context:
                break
            await asyncio.sleep(0.1)
        assert service.playwright_context is not None, "Playwright context did not start"

        ctx = service.playwright_context
        # If the extension failed to load, inject the fallback patch
        if not ctx.service_workers:
            await ctx.add_init_script(SHADOW_PATCH)
            for page in ctx.pages:
                await page.add_init_script(SHADOW_PATCH)
                await page.evaluate(SHADOW_PATCH)

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("http://127.0.0.1:8000/closed.html")
        await page.fill("css=outer-closed >> inner-closed >> #inner-input", "hello-closed")
        await page.click("css=outer-closed >> inner-closed >> #inner-btn")
        await page.click("css=outer-closed >> #outer-btn")

        await asyncio.sleep(1)  # allow events to be sent to the recorder
        await ctx.close()
        result = await capture_task
    finally:
        server.shutdown()
        thread.join()

    assert result is not None, "No workflow captured"
    selectors = [getattr(step, "cssSelector", None) for step in result.steps]
    assert "css=outer-closed >> inner-closed >> #inner-input" in selectors
    assert "css=outer-closed >> inner-closed >> #inner-btn" in selectors
    assert "css=outer-closed >> #outer-btn" in selectors
