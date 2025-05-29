from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from workflow_use.schema.views import WorkflowDefinitionSchema


# Task Models
class TaskInfo(BaseModel):
	model_config = ConfigDict(extra='ignore')
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


class WorkflowDeleteStepRequest(BaseModel):
	workflowName: str
	stepIndex: int

class WorkflowAddRequest(BaseModel):
	name: str
	content: str  # JSON string containing the workflow definition


class WorkflowBuildRequest(BaseModel):
	workflow: WorkflowDefinitionSchema
	prompt: str
	name: str


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


class WorkflowRecordResponse(BaseModel):
	success: bool
	workflow: Optional[WorkflowDefinitionSchema] = None
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


class WorkflowBuildResponse(BaseModel):
	success: bool
	message: str
	error: Optional[str] = None
