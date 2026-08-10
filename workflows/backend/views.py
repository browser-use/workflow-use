from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# Task Models
class TaskInfo(BaseModel):
	status: str
	workflow: str
	result: Optional[List[Dict[str, Any]]] = None
	error: Optional[str] = None


# Request Models
class WorkflowUpdateRequest(BaseModel):
	filename: str
	nodeId: int
	stepData: Dict[str, Any]


class WorkflowMetadataUpdateRequest(BaseModel):
	name: str
	metadata: Dict[str, Any]


class WorkflowExecuteRequest(BaseModel):
	name: str
	inputs: Dict[str, Any]


class RecordingStatusResponse(BaseModel):
	status: str  # 'idle' | 'recording' | 'saving' | 'done' | 'error' | 'no_data'
	message: Optional[str] = None
	workflow_file: Optional[str] = None


# Response Models
class WorkflowResponse(BaseModel):
	success: bool
	error: Optional[str] = None


class WorkflowListResponse(BaseModel):
	workflows: List[str]


class WorkflowExecuteResponse(BaseModel):
	success: bool
	task_id: str
	workflow: str
	log_position: int
	message: str


class WorkflowLogsResponse(BaseModel):
	logs: List[str]
	position: int
	log_position: int
	status: str
	result: Optional[List[Dict[str, Any]]] = None
	error: Optional[str] = None


class WorkflowStatusResponse(BaseModel):
	task_id: str
	status: str
	workflow: str
	result: Optional[List[Dict[str, Any]]] = None
	error: Optional[str] = None


class WorkflowCancelResponse(BaseModel):
	success: bool
	message: str
