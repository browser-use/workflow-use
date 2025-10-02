import hashlib
import json
from typing import Any, Dict, List, Sequence, Union

import aiofiles
from browser_use import Agent, AgentHistoryList, Browser
from browser_use.agent.views import DOMHistoryElement
from browser_use.llm.base import BaseChatModel
from browser_use.llm import UserMessage, SystemMessage

from workflow_use.builder.service import BuilderService
from workflow_use.healing._agent.controller import HealingController
from workflow_use.healing.prompts import HEALING_AGENT_SYSTEM_PROMPT
from workflow_use.healing.views import ParsedAgentStep, SimpleDomElement, SimpleResult
from workflow_use.schema.views import SelectorWorkflowSteps, WorkflowDefinitionSchema


class HealingService:
	def __init__(
		self,
		llm: BaseChatModel,
	):
		self.llm = llm

		self.interacted_elements_hash_map: dict[str, DOMHistoryElement] = {}

	def _remove_none_fields_from_dict(self, d: dict) -> dict:
		return {k: v for k, v in d.items() if v is not None}

	def _history_to_workflow_definition(self, history_list: AgentHistoryList) -> list[HumanMessage]:
		# history

		messages: list[HumanMessage] = []

		for history in history_list.history:
			if history.model_output is None:
				continue

			interacted_elements: list[SimpleDomElement] = []
			for element in history.state.interacted_element:
				if element is None:
					continue

				# hash element by hacshing the tag_name + css_selector + highlight_index
				element_hash = hashlib.sha256(
					f'{element.tag_name}_{element.css_selector}_{element.highlight_index}'.encode()
				).hexdigest()[:10]

				if element_hash not in self.interacted_elements_hash_map:
					self.interacted_elements_hash_map[element_hash] = element

				interacted_elements.append(
					SimpleDomElement(
						tag_name=element.tag_name,
						highlight_index=element.highlight_index,
						shadow_root=element.shadow_root,
						element_hash=element_hash,
					)
				)

			screenshot = history.state.screenshot
			parsed_step = ParsedAgentStep(
				url=history.state.url,
				title=history.state.title,
				agent_brain=history.model_output.current_state,
				actions=[self._remove_none_fields_from_dict(action.model_dump()) for action in history.model_output.action],
				results=[
					SimpleResult(
						success=result.success or False,
						extracted_content=result.extracted_content,
					)
					for result in history.result
				],
				interacted_elements=interacted_elements,
			)

			parsed_step_json = json.dumps(parsed_step.model_dump(exclude_none=True))
			content_blocks: List[Union[str, Dict[str, Any]]] = []

			text_block: Dict[str, Any] = {'type': 'text', 'text': parsed_step_json}
			content_blocks.append(text_block)

			if screenshot:
				# Assuming screenshot is a base64 encoded string.
				# Adjust mime type if necessary (e.g., image/png)
				image_block: Dict[str, Any] = {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{screenshot}'}}
				content_blocks.append(image_block)

			messages.append(HumanMessage(content=content_blocks))

		return messages

	def _populate_selector_fields(self, workflow_definition: WorkflowDefinitionSchema) -> WorkflowDefinitionSchema:
		"""Populate cssSelector, xpath, and elementTag fields from interacted_elements_hash_map"""
		# Process each step to add back the selector fields
		for step in workflow_definition.steps:
			if isinstance(step, SelectorWorkflowSteps):
				if step.elementHash in self.interacted_elements_hash_map:
					dom_element = self.interacted_elements_hash_map[step.elementHash]
					step.cssSelector = dom_element.css_selector or ''
					step.xpath = dom_element.xpath
					step.elementTag = dom_element.tag_name

		# Create the full WorkflowDefinitionSchema with populated fields
		return workflow_definition

	async def create_workflow_definition(self, task: str, history_list: AgentHistoryList) -> WorkflowDefinitionSchema:
		async with aiofiles.open('workflow_use/healing/prompts/workflow_creation_prompt.md', mode='r') as f:
			prompt_content = await f.read()

		prompt_content = prompt_content.format(goal=task, actions=BuilderService._get_available_actions_markdown())

		system_message = SystemMessage(content=prompt_content)
		human_messages = self._history_to_workflow_definition(history_list)

		all_messages: Sequence[BaseMessage] = [system_message] + human_messages

		# Chain the model with the structured output schema
		structured_llm = self.llm.with_structured_output(WorkflowDefinitionSchema, method='function_calling')

		workflow_definition: WorkflowDefinitionSchema = await structured_llm.ainvoke(all_messages)  # type: ignore

		workflow_definition = self._populate_selector_fields(workflow_definition)

		return workflow_definition

	# Generate workflow from prompt
	async def generate_workflow_from_prompt(
		self, prompt: str, agent_llm: BaseChatModel, extraction_llm: BaseChatModel
	) -> WorkflowDefinitionSchema:
		"""
		Generate a workflow definition from a prompt by:
		1. Running a browser agent to explore and complete the task
		2. Converting the agent history into a workflow definition
		"""

		browser = Browser()

		agent = Agent(
			task=prompt,
			browser_session=browser,
			llm=agent_llm,
			page_extraction_llm=extraction_llm,
			controller=HealingController(extraction_llm=extraction_llm),
			override_system_message=HEALING_AGENT_SYSTEM_PROMPT,
			enable_memory=False,
			max_failures=10,
			tool_calling_method='auto',
		)

		# Run the agent to get history
		history = await agent.run()

		# Create workflow definition from the history
		workflow_definition = await self.create_workflow_definition(prompt, history)

		return workflow_definition
