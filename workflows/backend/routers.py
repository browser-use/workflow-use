import asyncio
import uuid

from fastapi import APIRouter, HTTPException

from .service import WorkflowService
from .views import (
	WorkflowCancelResponse,
	WorkflowExecuteRequest,
	WorkflowExecuteResponse,
	WorkflowListResponse,
	WorkflowLogsResponse,
	WorkflowMetadataUpdateRequest,
	WorkflowResponse,
	WorkflowStatusResponse,
	WorkflowUpdateRequest,
)

router = APIRouter(prefix='/api/workflows')


def get_service() -> WorkflowService:
	return WorkflowService()


@router.get('', response_model=WorkflowListResponse)
async def list_workflows():
	service = get_service()
	workflows = service.list_workflows()
	return WorkflowListResponse(workflows=workflows)


@router.get('/{name}', response_model=str)
async def get_workflow(name: str):
	service = get_service()
	return service.get_workflow(name)


@router.post('/update', response_model=WorkflowResponse)
async def update_workflow(request: WorkflowUpdateRequest):
	service = get_service()
	return service.update_workflow(request)


@router.post('/update-metadata', response_model=WorkflowResponse)
async def update_workflow_metadata(request: WorkflowMetadataUpdateRequest):
	service = get_service()
	return service.update_workflow_metadata(request)


@router.post('/execute', response_model=WorkflowExecuteResponse)
async def execute_workflow(request: WorkflowExecuteRequest):
	service = get_service()
	workflow_name = request.name
	inputs = request.inputs

	if not workflow_name:
		raise HTTPException(status_code=400, detail='Missing workflow name')

	workflow_path = service.tmp_dir / workflow_name
	if not workflow_path.exists():
		raise HTTPException(status_code=404, detail=f'Workflow {workflow_name} not found')

	try:
		task_id = str(uuid.uuid4())
		cancel_event = asyncio.Event()
		service.cancel_events[task_id] = cancel_event
		log_pos = await service._log_file_position()

		task = asyncio.create_task(service.run_workflow_in_background(task_id, request, cancel_event))
		service.workflow_tasks[task_id] = task
		task.add_done_callback(
			lambda _: (
				service.workflow_tasks.pop(task_id, None),
				service.cancel_events.pop(task_id, None),
			)
		)
		return WorkflowExecuteResponse(
			success=True,
			task_id=task_id,
			workflow=workflow_name,
			log_position=log_pos,
			message=f"Workflow '{workflow_name}' execution started with task ID: {task_id}",
		)
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f'Error starting workflow: {exc}')


@router.get('/logs/{task_id}', response_model=WorkflowLogsResponse)
async def get_logs(task_id: str, position: int = 0):
	service = get_service()
	task_info = service.active_tasks.get(task_id)
	logs, new_pos = await service._read_logs_from_position(position)
	return WorkflowLogsResponse(
		logs=logs,
		position=new_pos,
		log_position=new_pos,
		status=task_info.status if task_info else 'unknown',
		result=task_info.result if task_info else None,
		error=task_info.error if task_info else None,
	)


@router.get('/tasks/{task_id}/status', response_model=WorkflowStatusResponse)
async def get_task_status(task_id: str):
	service = get_service()
	task_info = service.get_task_status(task_id)
	if not task_info:
		raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
	return task_info


@router.post('/tasks/{task_id}/cancel', response_model=WorkflowCancelResponse)
async def cancel_workflow(task_id: str):
	service = get_service()
	result = await service.cancel_workflow(task_id)
	if not result.success and result.message == 'Task not found':
		raise HTTPException(status_code=404, detail=f'Task {task_id} not found')
	return result
