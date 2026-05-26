"""
Tests for two bugs in the workflow backend service:

1. get_service() singleton — previously returned a *new* WorkflowService on every call,
   so active_tasks / workflow_tasks / cancel_events were lost between HTTP requests.

2. Workflow load failure — previously the exception handler called print() and returned
   without marking the task as 'failed', leaving it permanently stuck as 'running'.
"""

import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Minimal stubs for heavy optional deps so the backend module imports cleanly.
# ---------------------------------------------------------------------------

def _make_stub(name: str):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


for _name in [
    "browser_use",
    "browser_use.browser",
    "browser_use.browser.browser",
    "browser_use.llm",
    "workflow_use",
    "workflow_use.controller",
    "workflow_use.controller.service",
    "workflow_use.workflow",
    "workflow_use.workflow.service",
    "aiofiles",
    "yaml",
]:
    if _name not in sys.modules:
        _make_stub(_name)

# Provide realistic-enough stub objects
sys.modules["browser_use.browser.browser"].Browser = MagicMock
sys.modules["browser_use.llm"].ChatBrowserUse = MagicMock
sys.modules["workflow_use.controller.service"].WorkflowController = MagicMock

_MockWorkflow = MagicMock
sys.modules["workflow_use.workflow.service"].Workflow = _MockWorkflow

# aiofiles stub that makes open() an async context manager
_aiofiles_mock = MagicMock()
_aiofiles_open_cm = MagicMock()
_aiofiles_file = AsyncMock()
_aiofiles_file.write = AsyncMock()
_aiofiles_file.readlines = AsyncMock(return_value=[])
_aiofiles_file.seek = AsyncMock()
_aiofiles_open_cm.__aenter__ = AsyncMock(return_value=_aiofiles_file)
_aiofiles_open_cm.__aexit__ = AsyncMock(return_value=False)
_aiofiles_mock.open = MagicMock(return_value=_aiofiles_open_cm)
sys.modules["aiofiles"] = _aiofiles_mock

sys.modules["yaml"].safe_load = MagicMock(return_value={})
sys.modules["yaml"].dump = MagicMock(return_value="")

# Add the backend package to sys.path so relative imports resolve
_backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(_backend_dir.parent))


# ---------------------------------------------------------------------------
# Import the modules under test *after* stubs are in place.
# ---------------------------------------------------------------------------

import importlib as _il

# Force a clean import so the module-level singleton starts as None.
if "backend.routers" in sys.modules:
    del sys.modules["backend.routers"]
if "backend.service" in sys.modules:
    del sys.modules["backend.service"]
if "backend.views" in sys.modules:
    del sys.modules["backend.views"]

from backend import routers as _routers_mod  # noqa: E402
from backend.routers import get_service  # noqa: E402
from backend.service import WorkflowService  # noqa: E402
from backend.views import TaskInfo  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: reset the module-level singleton between tests.
# ---------------------------------------------------------------------------

def _reset_singleton():
    _routers_mod._service_instance = None


# ===========================================================================
# Test Suite 1 — get_service() singleton
# ===========================================================================

class TestGetServiceSingleton(unittest.TestCase):
    """get_service() must return the same WorkflowService instance on every call."""

    def setUp(self):
        _reset_singleton()

    def tearDown(self):
        _reset_singleton()

    def test_returns_workflow_service_instance(self):
        svc = get_service()
        self.assertIsInstance(svc, WorkflowService)

    def test_same_instance_on_repeated_calls(self):
        """Every call within a request cycle must return the exact same object."""
        svc1 = get_service()
        svc2 = get_service()
        self.assertIs(svc1, svc2, "get_service() must return a singleton, not a new instance")

    def test_task_state_survives_across_calls(self):
        """Task state written via one call must be readable via a subsequent call."""
        svc = get_service()
        svc.active_tasks["task-abc"] = TaskInfo(status="running", workflow="demo.workflow.json")

        # Simulate a second HTTP request hitting get_service()
        svc2 = get_service()
        self.assertIn("task-abc", svc2.active_tasks)
        self.assertEqual(svc2.active_tasks["task-abc"].status, "running")

    def test_singleton_reset_creates_new_instance(self):
        svc1 = get_service()
        _reset_singleton()
        svc2 = get_service()
        self.assertIsNot(svc1, svc2)


# ===========================================================================
# Test Suite 2 — load failure marks task as 'failed'
# ===========================================================================

class TestWorkflowLoadFailureStatus(unittest.IsolatedAsyncioTestCase):
    """When Workflow.load_from_file raises, active_tasks[task_id].status must be 'failed'."""

    def _make_service(self):
        svc = WorkflowService.__new__(WorkflowService)
        svc.tmp_dir = Path("/tmp/fake_wf_dir")
        svc.log_dir = Path("/tmp/fake_wf_dir/logs")
        svc.active_tasks = {}
        svc.workflow_tasks = {}
        svc.cancel_events = {}
        svc.llm_instance = MagicMock()
        svc.browser_instance = MagicMock()
        svc.controller_instance = MagicMock()
        return svc

    async def test_load_failure_sets_status_to_failed(self):
        svc = self._make_service()

        from backend.views import WorkflowExecuteRequest

        request = WorkflowExecuteRequest(name="bad.workflow.json", inputs={})
        task_id = "test-task-001"
        cancel_event = asyncio.Event()

        # Patch Workflow.load_from_file to raise
        load_error = FileNotFoundError("workflow schema invalid")
        sys.modules["workflow_use.workflow.service"].Workflow.load_from_file = MagicMock(
            side_effect=load_error
        )

        # Patch _write_log so we don't touch the filesystem
        svc._write_log = AsyncMock()

        # Patch Path.exists to return True (so the workflow_path check passes)
        with patch.object(Path, "exists", return_value=True):
            await svc.run_workflow_in_background(task_id, request, cancel_event)

        task_info = svc.active_tasks.get(task_id)
        self.assertIsNotNone(task_info, "active_tasks entry must exist after run")
        self.assertEqual(
            task_info.status,
            "failed",
            f"Expected status 'failed' after load error, got '{task_info.status}'",
        )
        self.assertIsNotNone(task_info.error, "error field must be populated")
        self.assertIn("workflow schema invalid", task_info.error)

    async def test_load_failure_logs_error(self):
        """The load error must be written to the log, not silently dropped."""
        svc = self._make_service()

        from backend.views import WorkflowExecuteRequest

        request = WorkflowExecuteRequest(name="bad.workflow.json", inputs={})
        task_id = "test-task-002"
        cancel_event = asyncio.Event()

        sys.modules["workflow_use.workflow.service"].Workflow.load_from_file = MagicMock(
            side_effect=ValueError("corrupt yaml")
        )

        log_calls = []

        async def capture_log(path, msg):
            log_calls.append(msg)

        svc._write_log = capture_log

        with patch.object(Path, "exists", return_value=True):
            await svc.run_workflow_in_background(task_id, request, cancel_event)

        error_logged = any("corrupt yaml" in msg for msg in log_calls)
        self.assertTrue(error_logged, "Load error must appear in the log output")


if __name__ == "__main__":
    unittest.main()
