import asyncio, os, shutil, tempfile
from pathlib import Path
from threading import Thread
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.async_api import async_playwright
from workflow_use.workflow.service import Workflow

TEST_DIR      = Path(__file__).parent
# Extension build output directory. The extension is built using `wxt build`
# which places the compiled files under `.output/chrome-mv3`.
# Tests rely on this path to load the monkey patching extension that forces
# closed shadow roots to open mode.
EXT_DIR       = TEST_DIR.parents[2] / "extension" / ".output" / "chrome-mv3"
if not EXT_DIR.exists():
    pytest.skip(
        f"Built extension not found at {EXT_DIR}. Run 'npm run build' in the extension directory."
    )

# Fallback script in case the extension cannot load in headless mode. It mirrors
# the patch applied in the extension's context script (content.ts) and forces
# all newly created shadow roots to be open.
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
        tmp_profile,
        headless=False,
        args=args,
        ignore_default_args=["--disable-extensions"],
    )

    # If the extension failed to load (no service worker detected), inject the
    # same patch used by the extension to force shadow roots open.
    if not ctx.service_workers:
        await ctx.add_init_script(SHADOW_PATCH)
        for page in ctx.pages:
            await page.add_init_script(SHADOW_PATCH)
            await page.evaluate(SHADOW_PATCH)

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
        workflow.fallback_to_agent = False
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
