from typing import Any, Dict, Generic, List, Optional, TypeVar

from browser_use.agent.views import ActionResult, AgentHistoryList
from pydantic import BaseModel, Field

T = TypeVar('T', bound=BaseModel)


class WorkflowRunOutput(BaseModel, Generic[T]):
	"""Output of a workflow run"""

	step_results: List[ActionResult | AgentHistoryList]
	output_model: Optional[T] = None


class StructuredWorkflowOutput(BaseModel):
	"""Base model for structured workflow outputs.

	This can be used as a parent class for custom output models that
	will be filled by convert_results_to_output_model method.
	"""

	raw_data: Dict[str, Any] = Field(default_factory=dict, description='Raw extracted data from workflow execution')

	status: str = Field(default='success', description='Overall status of the workflow execution')

	error_message: Optional[str] = Field(default=None, description='Error message if the workflow failed')
