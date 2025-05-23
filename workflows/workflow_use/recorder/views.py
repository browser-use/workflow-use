from typing import Literal, Union

from pydantic import BaseModel

from workflow_use.schema.views import WorkflowDefinitionSchema

# --- Event Payloads ---


class RecordingStatusPayload(BaseModel):
	message: str


# --- Main Event Models (mirroring HttpEvent types from message-bus-types.ts) ---


class BaseHttpEvent(BaseModel):
	timestamp: int


class HttpWorkflowUpdateEvent(BaseHttpEvent):
	type: Literal['WORKFLOW_UPDATE'] = 'WORKFLOW_UPDATE'
	payload: WorkflowDefinitionSchema


class HttpRecordingStartedEvent(BaseHttpEvent):
	type: Literal['RECORDING_STARTED'] = 'RECORDING_STARTED'
	payload: RecordingStatusPayload


class HttpRecordingStoppedEvent(BaseHttpEvent):
	type: Literal['RECORDING_STOPPED'] = 'RECORDING_STOPPED'
	payload: RecordingStatusPayload


# Union of all possible event types received by the recorder
RecorderEvent = Union[
	HttpWorkflowUpdateEvent,
	HttpRecordingStartedEvent,
	HttpRecordingStoppedEvent,
]
