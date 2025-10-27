import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiofiles
import yaml
from browser_use.browser.browser import Browser
from browser_use.llm import ChatBrowserUse

from workflow_use.controller.service import WorkflowController
from workflow_use.workflow.service import Workflow

from .views import (
	TaskInfo,
	WorkflowCancelResponse,
	WorkflowExecuteRequest,
	WorkflowMetadataUpdateRequest,
	WorkflowResponse,
	WorkflowStatusResponse,
	WorkflowUpdateRequest,
)


def json_serializer(obj):
	"""Convert non-JSON-serializable objects to JSON-compatible types."""
	# Handle datetime objects
	if hasattr(obj, 'isoformat'):
		return obj.isoformat()
	# Handle other types by converting to string
	return str(obj)


class WorkflowService:
	"""Workflow execution service."""

	def __init__(self) -> None:
		# ---------- Core resources ----------
		self.tmp_dir: Path = Path('./tmp')
		self.log_dir: Path = self.tmp_dir / 'logs'
		self.log_dir.mkdir(exist_ok=True, parents=True)

		# LLM / workflow executor
		self.llm_instance = ChatBrowserUse(model='bu-latest')

		self.browser_instance = Browser()
		self.controller_instance = WorkflowController()

		# In‑memory task tracking
		self.active_tasks: Dict[str, TaskInfo] = {}
		self.workflow_tasks: Dict[str, asyncio.Task] = {}
		self.cancel_events: Dict[str, asyncio.Event] = {}

	async def _log_file_position(self) -> int:
		log_file = self.log_dir / 'backend.log'
		if not log_file.exists():
			async with aiofiles.open(log_file, 'w') as f:
				await f.write('')
			return 0
		return log_file.stat().st_size

	async def _read_logs_from_position(self, position: int) -> Tuple[List[str], int]:
		log_file = self.log_dir / 'backend.log'
		if not log_file.exists():
			return [], 0

		current_size = log_file.stat().st_size
		if position >= current_size:
			return [], position

		async with aiofiles.open(log_file, 'r') as f:
			await f.seek(position)
			all_logs = await f.readlines()
			new_logs = [
				line
				for line in all_logs
				if not line.strip().startswith('INFO:')
				and not line.strip().startswith('WARNING:')
				and not line.strip().startswith('DEBUG:')
				and not line.strip().startswith('ERROR:')
			]
		return new_logs, current_size

	async def _write_log(self, log_file: Path, message: str) -> None:
		async with aiofiles.open(log_file, 'a') as f:
			await f.write(message)

	def list_workflows(self) -> List[str]:
		"""List only valid workflow files (JSON or YAML format)."""
		return [
			f.name
			for f in self.tmp_dir.iterdir()
			if f.is_file()
			and not f.name.startswith('temp_recording')
			and (f.name.endswith('.workflow.json') or f.name.endswith('.workflow.yaml') or f.name.endswith('.workflow.yml'))
		]

	def get_workflow(self, name: str) -> str:
		"""Get workflow content, converting YAML to JSON for frontend compatibility."""
		wf_file = self.tmp_dir / name

		# Validate file exists
		if not wf_file.exists():
			raise FileNotFoundError(f"Workflow file '{name}' not found")

		# Validate file is a workflow file
		if not (name.endswith('.workflow.json') or name.endswith('.workflow.yaml') or name.endswith('.workflow.yml')):
			raise ValueError(f"File '{name}' is not a valid workflow file")

		try:
			# Load YAML/JSON and convert to JSON for frontend compatibility
			content = yaml.safe_load(wf_file.read_text())
			return json.dumps(content, indent=2, default=json_serializer)
		except yaml.YAMLError as e:
			raise ValueError(f"Failed to parse workflow file '{name}': {e}")
		except TypeError as e:
			raise ValueError(f"Failed to serialize workflow file '{name}' to JSON: {e}")

	def update_workflow(self, request: WorkflowUpdateRequest) -> WorkflowResponse:
		workflow_filename = request.filename
		node_id = request.nodeId
		updated_step_data = request.stepData

		if not (workflow_filename and node_id is not None and updated_step_data):
			return WorkflowResponse(success=False, error='Missing required fields')

		wf_file = self.tmp_dir / workflow_filename
		if not wf_file.exists():
			return WorkflowResponse(success=False, error=f"Workflow file '{workflow_filename}' not found")

		workflow_content = yaml.safe_load(wf_file.read_text())
		steps = workflow_content.get('steps', [])

		if 0 <= int(node_id) < len(steps):
			steps[int(node_id)] = updated_step_data
			wf_file.write_text(yaml.dump(workflow_content, default_flow_style=False, sort_keys=False))
			return WorkflowResponse(success=True)

		return WorkflowResponse(success=False, error='Node not found in workflow')

	def update_workflow_metadata(self, request: WorkflowMetadataUpdateRequest) -> WorkflowResponse:
		workflow_name = request.name
		updated_metadata = request.metadata

		if not (workflow_name and updated_metadata):
			return WorkflowResponse(success=False, error='Missing required fields')

		wf_file = self.tmp_dir / workflow_name
		if not wf_file.exists():
			return WorkflowResponse(success=False, error='Workflow not found')

		workflow_content = yaml.safe_load(wf_file.read_text())
		workflow_content['name'] = updated_metadata.get('name', workflow_content.get('name', ''))
		workflow_content['description'] = updated_metadata.get('description', workflow_content.get('description', ''))
		workflow_content['version'] = updated_metadata.get('version', workflow_content.get('version', ''))

		if 'input_schema' in updated_metadata:
			workflow_content['input_schema'] = updated_metadata['input_schema']

		wf_file.write_text(yaml.dump(workflow_content, default_flow_style=False, sort_keys=False))
		return WorkflowResponse(success=True)

	async def run_workflow_in_background(
		self,
		task_id: str,
		request: WorkflowExecuteRequest,
		cancel_event: asyncio.Event,
	) -> None:
		workflow_name = request.name
		inputs = request.inputs
		log_file = self.log_dir / 'backend.log'
		try:
			self.active_tasks[task_id] = TaskInfo(status='running', workflow=workflow_name)
			ts = time.strftime('%Y-%m-%d %H:%M:%S')
			await self._write_log(log_file, f"[{ts}] Starting workflow '{workflow_name}'\n")
			await self._write_log(log_file, f'[{ts}] Input parameters: {json.dumps(inputs, default=json_serializer)}\n')

			if cancel_event.is_set():
				await self._write_log(log_file, f'[{ts}] Workflow cancelled before execution\n')
				self.active_tasks[task_id].status = 'cancelled'
				return

			workflow_path = self.tmp_dir / workflow_name
			try:
				self.workflow_obj = Workflow.load_from_file(
					str(workflow_path), llm=self.llm_instance, browser=self.browser_instance, controller=self.controller_instance
				)
			except Exception as e:
				print(f'Error loading workflow: {e}')
				return

			await self._write_log(log_file, f'[{ts}] Executing workflow...\n')

			if cancel_event.is_set():
				await self._write_log(log_file, f'[{ts}] Workflow cancelled before execution\n')
				self.active_tasks[task_id].status = 'cancelled'
				return

			result = await self.workflow_obj.run(inputs, close_browser_at_end=True, cancel_event=cancel_event)

			if cancel_event.is_set():
				await self._write_log(log_file, f'[{ts}] Workflow execution was cancelled\n')
				self.active_tasks[task_id].status = 'cancelled'
				return

			formatted_result = [
				{
					'step_id': i,
					'extracted_content': s.extracted_content,
					'status': 'completed',
				}
				for i, s in enumerate(result.step_results)
			]
			for step in formatted_result:
				await self._write_log(log_file, f'[{ts}] Completed step {step["step_id"]}: {step["extracted_content"]}\n')

			self.active_tasks[task_id].status = 'completed'
			self.active_tasks[task_id].result = formatted_result
			await self._write_log(log_file, f'[{ts}] Workflow completed successfully with {len(result.step_results)} steps\n')

		except asyncio.CancelledError:
			await self._write_log(log_file, f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Workflow force‑cancelled\n')
			self.active_tasks[task_id].status = 'cancelled'
			raise
		except Exception as exc:
			await self._write_log(log_file, f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Error: {exc}\n')
			self.active_tasks[task_id].status = 'failed'
			self.active_tasks[task_id].error = str(exc)

	def get_task_status(self, task_id: str) -> Optional[WorkflowStatusResponse]:
		task_info = self.active_tasks.get(task_id)
		if not task_info:
			return None

		return WorkflowStatusResponse(
			task_id=task_id,
			status=task_info.status,
			workflow=task_info.workflow,
			result=task_info.result,
			error=task_info.error,
		)

	async def cancel_workflow(self, task_id: str) -> WorkflowCancelResponse:
		task_info = self.active_tasks.get(task_id)
		if not task_info:
			return WorkflowCancelResponse(success=False, message='Task not found')
		if task_info.status != 'running':
			return WorkflowCancelResponse(success=False, message=f'Task is already {task_info.status}')

		task = self.workflow_tasks.get(task_id)
		cancel_event = self.cancel_events.get(task_id)

		if cancel_event:
			cancel_event.set()
		if task and not task.done():
			task.cancel()

		await self._write_log(
			self.log_dir / 'backend.log',
			f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Workflow execution for task {task_id} cancelled by user\n',
		)

		self.active_tasks[task_id].status = 'cancelling'
		return WorkflowCancelResponse(success=True, message='Workflow cancellation requested')
