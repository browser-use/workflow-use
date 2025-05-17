import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI

from browser_use.browser.browser import Browser
from workflow_use.controller.service import WorkflowController
from workflow_use.workflow.service import Workflow

class WorkflowService:
    """Workflow execution service."""

    def __init__(self) -> None:
        # ---------- Core resources ----------
        self.app = FastAPI(title="Workflow Execution Service")
        self.tmp_dir: Path = Path("./tmp")
        self.log_dir: Path = self.tmp_dir / "logs"
        self.log_dir.mkdir(exist_ok=True, parents=True)

        # LLM / workflow executor
        try:
            self.llm_instance = ChatOpenAI(model="gpt-4.1-mini")
        except Exception as exc:
            print(f"Error initializing LLM: {exc}. Ensure OPENAI_API_KEY is set.")
            self.llm_instance = None

        self.browser_instance = Browser()
        self.controller_instance = WorkflowController()
        
        # In‑memory task tracking
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.workflow_tasks: Dict[str, asyncio.Task] = {}
        self.cancel_events: Dict[str, asyncio.Event] = {}

        # ---------- Middleware & routes ----------
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self._register_routes()

    # --------------------------------------------------------------------- #
    #                               Routes                                   #
    # --------------------------------------------------------------------- #
    def _register_routes(self) -> None:
        self.app.add_api_route(
            "/api/workflows", self._list_workflows, methods=["GET"]
        )
        self.app.add_api_route(
            "/api/workflows/{name}", self._get_workflow, methods=["GET"]
        )
        self.app.add_api_route(
            "/api/workflows/update", self._update_workflow, methods=["POST"]
        )
        self.app.add_api_route(
            "/api/workflows/update-metadata",
            self._update_workflow_metadata,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/workflows/execute",
            self._execute_workflow,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/workflows/logs/{task_id}",
            self._get_logs,
            methods=["GET"],
        )
        self.app.add_api_route(
            "/api/workflows/tasks/{task_id}/status",
            self._get_task_status,
            methods=["GET"],
        )
        self.app.add_api_route(
            "/api/workflows/tasks/{task_id}/cancel",
            self._cancel_workflow,
            methods=["POST"],
        )

    # --------------------------------------------------------------------- #
    #                         Helper utilities                               #
    # --------------------------------------------------------------------- #
    def _log_file_position(self) -> int:
        log_file = self.log_dir / "backend.log"
        if not log_file.exists():
            log_file.write_text("")
            return 0
        return log_file.stat().st_size

    def _read_logs_from_position(self, position: int) -> Tuple[List[str], int]:
        log_file = self.log_dir / "backend.log"
        if not log_file.exists():
            return [], 0

        current_size = log_file.stat().st_size
        if position >= current_size:
            return [], position

        with open(log_file, "r") as f:
            f.seek(position)
            all_logs = f.readlines()
            new_logs = [
                line
                for line in all_logs
                if not line.strip().startswith("INFO:")
                and not line.strip().startswith("WARNING:")
                and not line.strip().startswith("DEBUG:")
                and not line.strip().startswith("ERROR:")
            ]
        return new_logs, current_size

    # --------------------------------------------------------------------- #
    #                          Route handlers                                #
    # --------------------------------------------------------------------- #
    def _list_workflows(self) -> List[str]:
        return [
            f.name
            for f in self.tmp_dir.iterdir()
            if f.is_file() and not f.name.startswith("temp_recording")
        ]

    def _get_workflow(self, name: str) -> str:
        wf_file = self.tmp_dir / name
        return wf_file.read_text()

    def _update_workflow(self, workflow_data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        workflow_filename = workflow_data.get("filename")
        node_id = workflow_data.get("nodeId")
        updated_step_data = workflow_data.get("stepData")

        if not (workflow_filename and node_id is not None and updated_step_data):
            return {"success": False, "error": "Missing required fields"}

        wf_file = self.tmp_dir / workflow_filename
        if not wf_file.exists():
            return {"success": False, "error": f"Workflow file '{workflow_filename}' not found"}

        workflow_content = json.loads(wf_file.read_text())
        steps = workflow_content.get("steps", [])

        if 0 <= int(node_id) < len(steps):
            steps[int(node_id)] = updated_step_data
            wf_file.write_text(json.dumps(workflow_content, indent=2))
            return {"success": True}

        return {"success": False, "error": "Node not found in workflow"}

    def _update_workflow_metadata(self, data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        workflow_name = data.get("name")
        updated_metadata = data.get("metadata")

        if not (workflow_name and updated_metadata):
            return {"success": False, "error": "Missing required fields"}

        wf_file = self.tmp_dir / workflow_name
        if not wf_file.exists():
            return {"success": False, "error": "Workflow not found"}

        workflow_content = json.loads(wf_file.read_text())
        workflow_content["name"] = updated_metadata.get("name", workflow_content.get("name", ""))
        workflow_content["description"] = updated_metadata.get(
            "description", workflow_content.get("description", "")
        )
        workflow_content["version"] = updated_metadata.get(
            "version", workflow_content.get("version", "")
        )

        if "input_schema" in updated_metadata:
            workflow_content["input_schema"] = updated_metadata["input_schema"]

        wf_file.write_text(json.dumps(workflow_content, indent=2))
        return {"success": True}

    async def _run_workflow_in_background(
        self,
        task_id: str,
        workflow_name: str,
        inputs: Dict[str, Any],
        cancel_event: asyncio.Event,
    ) -> None:
        log_file = self.log_dir / "backend.log"
        try:
            self.active_tasks[task_id] = {"status": "running", "workflow": workflow_name}
            with open(log_file, "a") as f:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{ts}] Starting workflow '{workflow_name}'\n")
                f.write(f"[{ts}] Input parameters: {json.dumps(inputs)}\n")

            if cancel_event.is_set():
                with open(log_file, "a") as f:
                    f.write(f"[{ts}] Workflow cancelled before execution\n")
                self.active_tasks[task_id]["status"] = "cancelled"
                return

            workflow_path = self.tmp_dir / workflow_name
            try:
                self.workflow_obj = Workflow.load_from_file(
                    str(workflow_path), 
                    llm=self.llm_instance,
                    browser=self.browser_instance,
                    controller=self.controller_instance
                )
            except Exception as e:
                print(f'Error loading workflow: {e}')
                return

            with open(log_file, "a") as f:
                f.write(f"[{ts}] Executing workflow...\n")

            if cancel_event.is_set():
                with open(log_file, "a") as f:
                    f.write(f"[{ts}] Workflow cancelled before execution\n")
                self.active_tasks[task_id]["status"] = "cancelled"
                return

            result = await self.workflow_obj.run(
                inputs, close_browser_at_end=True, cancel_event=cancel_event
            )

            if cancel_event.is_set():
                with open(log_file, "a") as f:
                    f.write(f"[{ts}] Workflow execution was cancelled\n")
                self.active_tasks[task_id]["status"] = "cancelled"
                return

            formatted_result = [
                {
                    "step_id": i,
                    "description": s.get("description", f"Step {i}"),
                    "status": "completed",
                    "timestamp": s.get("timestamp", 0),
                }
                for i, s in enumerate(result)
            ]
            for step in formatted_result:
                with open(log_file, "a") as f:
                    f.write(
                        f"[{ts}] Completed step {step['step_id']}: {step['description']}\n"
                    )

            self.active_tasks[task_id].update(
                {"status": "completed", "result": formatted_result}
            )
            with open(log_file, "a") as f:
                f.write(f"[{ts}] Workflow completed successfully with {len(result)} steps\n")

        except asyncio.CancelledError:
            with open(log_file, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Workflow force‑cancelled\n")
            self.active_tasks[task_id]["status"] = "cancelled"
            raise
        except Exception as exc:
            with open(log_file, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error: {exc}\n")
            self.active_tasks[task_id].update({"status": "failed", "error": str(exc)})

    # ---------------------- Execution endpoints ---------------------- #
    async def _execute_workflow(self, data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        workflow_name = data.get("name")
        inputs = data.get("inputs", {})

        if not workflow_name:
            raise HTTPException(status_code=400, detail="Missing workflow name")

        workflow_path = self.tmp_dir / workflow_name
        if not workflow_path.exists():
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_name} not found")

        try:
            task_id = str(uuid.uuid4())
            cancel_event = asyncio.Event()
            self.cancel_events[task_id] = cancel_event
            log_pos = self._log_file_position()

            task = asyncio.create_task(
                self._run_workflow_in_background(task_id, workflow_name, inputs, cancel_event)
            )
            self.workflow_tasks[task_id] = task
            task.add_done_callback(
                lambda _: (
                    self.workflow_tasks.pop(task_id, None),
                    self.cancel_events.pop(task_id, None),
                )
            )
            return {
                "success": True,
                "task_id": task_id,
                "workflow": workflow_name,
                "log_position": log_pos,
                "message": f"Workflow '{workflow_name}' execution started with task ID: {task_id}",
            }
        except HTTPException:
            raise
        except Exception as exc:
            print(f"Error starting workflow: {exc}")
            raise HTTPException(status_code=500, detail=f"Error starting workflow: {exc}") from exc

    async def _get_logs(self, task_id: str, position: int = 0) -> Dict[str, Any]:
        task_info = self.active_tasks.get(task_id)
        logs, new_pos = self._read_logs_from_position(position)
        return {
            "logs": logs,
            "position": new_pos,
            "log_position": new_pos,
            "status": task_info["status"] if task_info else "unknown",
            "result": task_info.get("result") if task_info else None,
            "error": task_info.get("error") if task_info else None,
        }

    async def _get_task_status(self, task_id: str) -> Dict[str, Any]:
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return {
            "task_id": task_id,
            "status": task_info["status"],
            "workflow": task_info["workflow"],
            "result": task_info.get("result"),
            "error": task_info.get("error"),
        }

    async def _cancel_workflow(self, task_id: str) -> Dict[str, Any]:
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        if task_info["status"] != "running":
            return {"success": False, "message": f"Task is already {task_info['status']}"}

        task = self.workflow_tasks.get(task_id)
        cancel_event = self.cancel_events.get(task_id)

        if cancel_event:
            cancel_event.set()
        if task and not task.done():
            task.cancel()

        with open(self.log_dir / "backend.log", "a") as f:
            f.write(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Workflow execution for task {task_id} cancelled by user\n"
            )

        self.active_tasks[task_id]["status"] = "cancelling"
        return {"success": True, "message": "Workflow cancellation requested"}

# --------------------------------------------------------
#            Module‑level service & FastAPI app
# --------------------------------------------------------
_service = WorkflowService()
app = _service.app

# Optional standalone runner (similar to RecordingService)
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")