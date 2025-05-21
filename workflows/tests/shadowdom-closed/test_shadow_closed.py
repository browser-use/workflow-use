import asyncio, os, shutil, tempfile
from pathlib import Path
from threading import Thread
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.async_api import async_playwright
from workflow_use.workflow.service import Workflow

TEST_DIR      = Path(__file__).parent
EXT_DIR       = TEST_DIR.parents[2] / "extension" / "dist"
WORKFLOW_FILE = TEST_DIR / "shadow-closed.workflow.json"

# ---------- tiny shim ------------------------------------------------------
class BorrowedCtxWrapper:
    """Wrap a Playwright BrowserContext so browser-use actions can use it."""
    def __init__(self, pw_ctx):
        self._ctx = pw_ctx            # real Playwright context

    # -- async-context-manager no-ops -------------------------------------
    async def __aenter__(self):                       # allows: async with browser
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False

    # -- minimal API surface that browser-use expects ---------------------
    async def get_current_page(self):
        """Return the current page, or open one if none exist."""
        if self._ctx.pages:
            return self._ctx.pages[0]
        return await self._ctx.new_page()

    # Let *any other* attribute fall through to the underlying context
    def __getattr__(self, item):
        return getattr(self._ctx, item)
# --------------------------------------------------------------------------

def start_server():
    os.chdir(TEST_DIR)
    server = ThreadingHTTPServer(("127.0.0.1", 8000), SimpleHTTPRequestHandler)
    t = Thread(target=server.serve_forever, daemon=True); t.start()
    return server, t

async def launch_chromium_with_extension():
    tmp_profile = tempfile.mkdtemp(prefix="pw-profile-")
    args = [
        f"--disable-extensions-except={EXT_DIR}",
        f"--load-extension={EXT_DIR}",
    ]
    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        tmp_profile, headless=True, args=args
    )
    return pw, ctx, tmp_profile

# ----------------------------- test ----------------------------------------
@pytest.mark.asyncio
async def test_shadow_closed_workflow():
    server, thread        = start_server()
    pw, ctx, profile      = await launch_chromium_with_extension()
    try:
        workflow = Workflow.load_from_file(
            str(WORKFLOW_FILE),
            existing_pw_context=BorrowedCtxWrapper(ctx),
        )
        await workflow.run(close_browser_at_end=False)

        # sanity-check: patch opened closed shadow DOM so selectors work
        page  = ctx.pages[0] if ctx.pages else await ctx.new_page()
        value = await page.input_value(
            "css=outer-closed >> inner-closed >> #inner-input"
        )
        assert value == "hello-closed"
    finally:
        await ctx.close()
        await pw.stop()
        shutil.rmtree(profile, ignore_errors=True)
        server.shutdown(); thread.join()
