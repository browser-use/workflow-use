import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiofiles
from browser_use.agent.views import ActionResult
from browser_use.browser.browser import Browser
from langchain_openai import ChatOpenAI

from workflow_use.builder.service import BuilderService
from workflow_use.controller.service import WorkflowController
from workflow_use.recorder.service import RecordingService
from workflow_use.workflow.service import Workflow

from .views import (
	TaskInfo,
	WorkflowAddRequest,
	WorkflowBuildRequest,
	WorkflowBuildResponse,
	WorkflowCancelResponse,
	WorkflowDeleteStepRequest,
	WorkflowExecuteRequest,
	WorkflowMetadataUpdateRequest,
	WorkflowRecordResponse,
	WorkflowResponse,
	WorkflowStatusResponse,
	WorkflowUpdateRequest,
)


class WorkflowService:
	"""Workflow execution service."""

	def __init__(self, app=None) -> None:
		# ---------- Core resources ----------
		self.tmp_dir: Path = Path('./tmp')
		self.log_dir: Path = self.tmp_dir / 'logs'
		self.log_dir.mkdir(exist_ok=True, parents=True)

		# LLM / workflow executor
		try:
			self.llm_instance = ChatOpenAI(model='gpt-4.1-mini')
		except Exception as exc:
			print(f'Error initializing LLM: {exc}. Ensure OPENAI_API_KEY is set.')
			self.llm_instance = None

		self.browser_instance = Browser()
		self.controller_instance = WorkflowController()
		self.recording_service = RecordingService(app=app)

		# In‑memory task tracking
		self.active_tasks: Dict[str, TaskInfo] = {}
		self.workflow_tasks: Dict[str, asyncio.Task] = {}
		self.cancel_events: Dict[str, asyncio.Event] = {}

	def _get_timestamp(self) -> str:
		"""Get current timestamp in the format used for logging."""
		return time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(time.time() * 1000) % 1000:03d}'

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

		async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
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
		async with aiofiles.open(log_file, 'a', encoding='utf-8') as f:
			await f.write(message)

	def _sync_workflow_filename(self, file_path: Path, workflow_content: dict) -> Path:
		"""Synchronize the workflow file name with its internal name."""
		current_name = workflow_content.get('name')
		if not current_name:
			return file_path

		# Check if a file with this name already exists (excluding current file)
		name_exists = False
		for path in self.tmp_dir.iterdir():
			if (path.is_file() and not path.name.startswith('temp_recording') 
				and path != file_path 
				and path.stem == current_name):
				name_exists = True
				break

		if name_exists:
			# If name exists, update both file name and internal name
			new_filename = self._get_next_available_filename(current_name)
			new_name = Path(new_filename).stem  # Get name without extension
			workflow_content['name'] = new_name
			new_file_path = self.tmp_dir / new_filename
			file_path.rename(new_file_path)
			return new_file_path
		elif file_path.stem != current_name:
			# If name doesn't exist but file name doesn't match internal name
			new_filename = f"{current_name}.json"
			new_file_path = self.tmp_dir / new_filename
			file_path.rename(new_file_path)
			return new_file_path

		return file_path
	
	def list_workflows(self) -> List[str]:
		return [f.name for f in self.tmp_dir.iterdir() if f.is_file() and not f.name.startswith('temp_recording')]

	def get_workflow(self, name: str) -> str:
		wf_file = self.tmp_dir / name
		try:
			data = wf_file.read_text()
			workflow_content = json.loads(data)
			
			# If file name doesn't match internal name, sync them
			if workflow_content.get('name') != wf_file.stem:
				wf_file = self._sync_workflow_filename(wf_file, workflow_content)
				return json.loads(wf_file.read_text())
				
			return data
		except (FileNotFoundError, json.JSONDecodeError):
			return ""

	def update_workflow(self, request: WorkflowUpdateRequest) -> WorkflowResponse:
		workflow_filename = request.filename
		node_id = request.nodeId
		updated_step_data = request.stepData

		if not (workflow_filename and node_id is not None and updated_step_data):
			return WorkflowResponse(success=False, error='Missing required fields')

		# Search through all files in tmp_dir to find the matching workflow
		matching_file = None
		for file_path in self.tmp_dir.iterdir():
			if not file_path.is_file() or file_path.name.startswith('temp_recording'):
				continue
			try:
				workflow_content = json.loads(file_path.read_text())
				if workflow_content.get('name') == workflow_filename:
					matching_file = file_path
					break
			except (json.JSONDecodeError, KeyError):
				continue

		if not matching_file:
			return WorkflowResponse(success=False, error=f"Workflow with name '{workflow_filename}' not found")
		# Load and modify the workflow
		workflow_content = json.loads(matching_file.read_text())
		steps = workflow_content.get('steps', [])

		try:
			node_index = int(node_id)
		except ValueError:
			return WorkflowResponse(success=False, error='Invalid node ID')

		# Updating or adding a step
		if 0 <= node_index < len(steps):
			steps[node_index] = updated_step_data
		elif node_index == len(steps):  # Add new step
			steps.append(updated_step_data)
		else:
			return WorkflowResponse(success=False, error='Node index out of bounds for adding step')

		workflow_content['steps'] = steps
		matching_file.write_text(json.dumps(workflow_content, indent=2))
		return WorkflowResponse(success=True)

	def update_workflow_metadata(self, request: WorkflowMetadataUpdateRequest) -> WorkflowResponse:
		workflow_name = request.name
		updated_metadata = request.metadata

		if not (workflow_name and updated_metadata):
			return WorkflowResponse(success=False, error='Missing required fields')

		# Search through all files in tmp_dir to find the matching workflow
		matching_file = None
		for file_path in self.tmp_dir.iterdir():
			if not file_path.is_file() or file_path.name.startswith('temp_recording'):
				continue
			try:
				workflow_content = json.loads(file_path.read_text())
				if workflow_content.get('name') == workflow_name:
					matching_file = file_path
					break
			except (json.JSONDecodeError, KeyError):
				continue

		if not matching_file:
			print(f"Workflow with name '{workflow_name}' not found")
			return WorkflowResponse(success=False, error=f"Workflow with name '{workflow_name}' not found")

		workflow_content = json.loads(matching_file.read_text())
		
		# Update metadata fields directly from updated_metadata
		if 'name' in updated_metadata:
			workflow_content['name'] = updated_metadata['name']
		if 'description' in updated_metadata:
			workflow_content['description'] = updated_metadata['description']
		if 'workflow_analysis' in updated_metadata:
			workflow_content['workflow_analysis'] = updated_metadata['workflow_analysis']
		if 'version' in updated_metadata:
			workflow_content['version'] = updated_metadata['version']
		if 'input_schema' in updated_metadata:
			workflow_content['input_schema'] = updated_metadata['input_schema']

		# Only sync if the name was updated and is different from current file name
		if 'name' in updated_metadata and updated_metadata['name'] != matching_file.stem:
			matching_file = self._sync_workflow_filename(matching_file, workflow_content)

		matching_file.write_text(json.dumps(workflow_content, indent=2))
		return WorkflowResponse(success=True)
	
	def delete_step(self, request: WorkflowDeleteStepRequest) -> WorkflowResponse:
		workflow_name = request.workflowName
		step_index = request.stepIndex

		if not (workflow_name and step_index):
			return WorkflowResponse(success=False, error='Missing required fields')

		# Search through all files in tmp_dir to find the matching workflow
		matching_file = None
		for file_path in self.tmp_dir.iterdir():
			if not file_path.is_file() or file_path.name.startswith('temp_recording'):
				continue
			try:
				workflow_content = json.loads(file_path.read_text())
				if workflow_content.get('name') == workflow_name:
					matching_file = file_path
					break
			except (json.JSONDecodeError, KeyError):
				continue

		if not matching_file:
			print(f"Workflow with name '{workflow_name}' not found")
			return WorkflowResponse(success=False, error=f"Workflow with name '{workflow_name}' not found")

		if not matching_file:
			return WorkflowResponse(success=False, error="Workflow not found")

		workflow_content = json.loads(matching_file.read_text())
		steps = workflow_content.get('steps', [])

		if 0 <= step_index < len(steps):
			del steps[step_index]
			workflow_content['steps'] = steps
			matching_file.write_text(json.dumps(workflow_content, indent=2))
			return WorkflowResponse(success=True)

		return WorkflowResponse(success=False, error="Invalid step index")

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
			await self._write_log(log_file, f"[{self._get_timestamp()}] Starting workflow '{workflow_name}'\n")
			await self._write_log(log_file, f'[{self._get_timestamp()}] Input parameters: {json.dumps(inputs)}\n')

			if cancel_event.is_set():
				await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow cancelled before execution\n')
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

			await self._write_log(log_file, f'[{self._get_timestamp()}] Executing workflow...\n')

			if cancel_event.is_set():
				await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow cancelled before execution\n')
				self.active_tasks[task_id].status = 'cancelled'
				return

			result = await self.workflow_obj.run(inputs, close_browser_at_end=True, cancel_event=cancel_event)

			if cancel_event.is_set():
				await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow execution was cancelled\n')
				self.active_tasks[task_id].status = 'cancelled'
				return

			formatted_result = []
			for i, s in enumerate(result.step_results):
				content = None
				if isinstance(s, ActionResult):  # Handle agentic steps and agent fallback
					content = s.extracted_content
				elif hasattr(s, 'history') and s.history:  # AgentHistoryList
					# For AgentHistoryList, get the last successful result
					last_item = s.history[-1]
					last_action_result = next(
						(r for r in reversed(last_item.result) if r.extracted_content is not None),
						None,
					)
					if last_action_result:
						content = last_action_result.extracted_content

				formatted_result.append(
					{
						'step_id': i,
						'extracted_content': content,
						'status': 'completed',
					}
				)

			for step in formatted_result:
				await self._write_log(
					log_file, f'[{self._get_timestamp()}] Completed step {step["step_id"]}: {step["extracted_content"]}\n'
				)

			self.active_tasks[task_id].status = 'completed'
			self.active_tasks[task_id].result = formatted_result
			await self._write_log(
				log_file, f'[{self._get_timestamp()}] Workflow completed successfully with {len(result.step_results)} steps\n'
			)

		except asyncio.CancelledError:
			await self._write_log(log_file, f'[{self._get_timestamp()}] Workflow force‑cancelled\n')
			self.active_tasks[task_id].status = 'cancelled'
			raise
		except Exception as exc:
			await self._write_log(log_file, f'[{self._get_timestamp()}] Error: {exc}\n')
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
			f'[{self._get_timestamp()}] Workflow execution for task {task_id} cancelled by user\n',
		)

		self.active_tasks[task_id].status = 'cancelling'
		return WorkflowCancelResponse(success=True, message='Workflow cancellation requested')

	def add_workflow(self, request: WorkflowAddRequest) -> WorkflowResponse:
		"""Add a new workflow file."""
		if not request.name or not request.content:
			return WorkflowResponse(success=False, error='Missing required fields')

		# Create new workflow file with collision handling
		try:
			workflow_file = self.tmp_dir / self._get_next_available_filename(request.name)
			workflow_file.write_text(request.content)
			return WorkflowResponse(success=True)
		except Exception as e:
			return WorkflowResponse(success=False, error=f'Error creating workflow: {str(e)}')

	def delete_workflow(self, name: str) -> WorkflowResponse:
		"""Delete a workflow file."""
		if not name:
			return WorkflowResponse(success=False, error='Missing workflow name')

		# Find and delete the workflow file
		for file_path in self.tmp_dir.iterdir():
			if not file_path.is_file() or file_path.name.startswith('temp_recording'):
				continue
			try:
				workflow_content = json.loads(file_path.read_text())
				if workflow_content.get('name') == name:
					file_path.unlink()
					return WorkflowResponse(success=True)
			except (json.JSONDecodeError, KeyError):
				continue

		return WorkflowResponse(success=False, error=f"Workflow '{name}' not found")

	async def record_workflow(self) -> WorkflowRecordResponse:
		"""Record a new workflow using the recording service."""
		try:
			workflow_data = await self.recording_service.record_workflow_using_main_server()
			return WorkflowRecordResponse(success=True, workflow=workflow_data)
		except Exception as e:
			print(f'Error recording workflow: {e}')
			return WorkflowRecordResponse(success=False, workflow=None, error=str(e))

	async def cancel_recording(self) -> WorkflowRecordResponse:
		"""Cancel an ongoing workflow recording."""
		try:
			await self.recording_service.cancel_recording()
			return WorkflowRecordResponse(success=True, workflow=None)
		except Exception as e:
			print(f'Error cancelling recording: {e}')
			return WorkflowRecordResponse(success=False, workflow=None, error=str(e))

	def _get_next_available_filename(self, base_name: str) -> str:
		"""Get the next available filename by adding incremental numbers."""
		counter = 1
		file_name = f'{base_name}.json'
		while (self.tmp_dir / file_name).exists():
			file_name = f'{base_name}{counter}.json'
			counter += 1
		return file_name

	async def build_workflow(self, request: WorkflowBuildRequest) -> WorkflowBuildResponse:
		"""Build a workflow from the edited recording."""
		try:
			if not self.llm_instance:
				return WorkflowBuildResponse(
					success=False,
					message='Failed to build workflow',
					error='LLM instance not available. Please ensure OPENAI_API_KEY is set.',
				)

			# Initialize the builder service with the LLM instance
			builder_service = BuilderService(llm=self.llm_instance)

			# Build the workflow using the builder service
			built_workflow = await builder_service.build_workflow(
				input_workflow=request.workflow,
				user_goal=request.prompt,
				use_screenshots=False,  # We don't need screenshots for now
			)

			# Set timestamps for steps that don't have them
			current_time = int(time.time() * 1000)  # Current time in milliseconds
			has_timestamp = False
			for step in built_workflow.steps:
				if hasattr(step, 'type') and step.type != 'agent' and hasattr(step, 'timestamp') and step.timestamp is not None:
					has_timestamp = True
					break
			if not has_timestamp:
				for step in built_workflow.steps:
					if hasattr(step, 'type') and step.type != 'agent' and hasattr(step, 'timestamp'):
						step.timestamp = current_time

			# Handle workflow name
			if not request.name:
				workflow_name = built_workflow.name
			else:
				built_workflow.name = request.name
				workflow_name = request.name

			# Save the built workflow to the final location with collision handling
			final_file = self.tmp_dir / self._get_next_available_filename(workflow_name)
			final_file.write_text(built_workflow.model_dump_json(indent=2))

			return WorkflowBuildResponse(success=True, message=f"Workflow '{final_file.stem}' built successfully")
		except Exception as e:
			print(f'Error building workflow: {e}')
			return WorkflowBuildResponse(success=False, message='Failed to build workflow', error=str(e))
