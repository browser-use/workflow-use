import logging

from browser_use import ActionResult, Controller
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class WorkflowStepAgentController(Controller):
	def __init__(self, exclude_actions: list[str] = ['done'], output_model: type[BaseModel] | None = None):
		super().__init__(exclude_actions=exclude_actions, output_model=output_model)

		self.registry.action('Continue to the next step of the workflow.')(self.continue_to_next_step)

	async def continue_to_next_step(self, is_current_step_success: bool = True):
		return ActionResult(is_done=True, success=is_current_step_success)
