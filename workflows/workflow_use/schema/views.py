from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


# --- Base Step Model ---
# Common fields for all step types
class BaseWorkflowStep(BaseModel):
	description: Optional[str] = Field(None, description="Description of the step's purpose.")
	output: Optional[str] = Field(None, description='Context key to store step output under.')
	# Allow other fields captured from raw events but not explicitly modeled
	model_config = {'extra': 'allow'}


# --- Steps that require interaction with a DOM element ---
class SelectorWorkflowSteps(BaseWorkflowStep):
	cssSelector: Optional[str] = Field(None, description='CSS selector for the target element.')
	xpath: Optional[str] = Field(None, description='XPath selector (often informational).')
	elementTag: Optional[str] = Field(None, description='HTML tag (informational).')

	elementHash: str = Field(..., description='Hash of the element.')


# --- Agent Step ---
class AgentTaskWorkflowStep(BaseWorkflowStep):
	type: Literal['agent']
	task: str = Field(..., description='The objective or task description for the agent.')
	max_steps: Optional[int] = Field(
		None,
		description='Maximum number of iterations for the agent (default handled in code).',
	)

	# Agent steps might also have 'params' for other configs, handled by extra='allow'


# --- Deterministic Action Steps (based on controllers and examples) ---


# Actions from src/workflows/controller/service.py & Examples
class NavigationStep(BaseWorkflowStep):
	"""Navigates using the 'navigation' action (likely maps to go_to_url)."""

	type: Literal['navigation']  # As seen in examples
	url: str = Field(..., description='Target URL to navigate to. Can use {context_var}.')


class ClickStep(SelectorWorkflowSteps):
	"""Clicks an element using 'click' (maps to workflow controller's click)."""

	type: Literal['click']  # As seen in examples


class InputStep(SelectorWorkflowSteps):
	"""Inputs text using 'input' (maps to workflow controller's input)."""

	description: Optional[str] = Field(
		None,
		description="Description of the step's purpose. If neccesary describe the format that data should be in.",
	)

	type: Literal['input']  # As seen in examples

	value: str = Field(..., description='Value to input. Can use {context_var}.')


class SelectChangeStep(SelectorWorkflowSteps):
	"""Selects a dropdown option using 'select_change' (maps to workflow controller's select_change)."""

	type: Literal['select_change']  # Assumed type for workflow controller's select_change

	selectedText: str = Field(..., description='Visible text of the option to select. Can use {context_var}.')


class KeyPressStep(SelectorWorkflowSteps):
	"""Presses a key using 'key_press' (maps to workflow controller's key_press)."""

	type: Literal['key_press']  # As seen in examples

	key: str = Field(..., description="The key to press (e.g., 'Tab', 'Enter').")


class ScrollStep(BaseWorkflowStep):
	"""Scrolls the page using 'scroll' (maps to workflow controller's scroll)."""

	type: Literal['scroll']  # Assumed type for workflow controller's scroll
	scrollX: int = Field(..., description='Horizontal scroll pixels.')
	scrollY: int = Field(..., description='Vertical scroll pixels.')


class PageExtractionStep(BaseWorkflowStep):
	"""Extracts text from the page using 'page_extraction' (maps to workflow controller's page_extraction)."""

	type: Literal['extract_page_content']  # Assumed type for workflow controller's page_extraction
	goal: str = Field(..., description='The goal of the page extraction.')


# --- Union of all possible step types ---
# This Union defines what constitutes a valid step in the "steps" list.
DeterministicWorkflowStep = Union[
	NavigationStep,
	ClickStep,
	InputStep,
	SelectChangeStep,
	KeyPressStep,
	ScrollStep,
	PageExtractionStep,
]

AgenticWorkflowStep = AgentTaskWorkflowStep


WorkflowStep = Union[
	# Pure workflow
	DeterministicWorkflowStep,
	# Agentic
	AgenticWorkflowStep,
]

allowed_controller_actions = []


# --- Input Schema Definition ---
# (Remains the same)
class WorkflowInputSchemaDefinition(BaseModel):
	name: str = Field(
		...,
		description='The name of the property. This will be used as the key in the input schema.',
	)
	type: Literal['string', 'number', 'bool']

	format: Optional[str] = Field(
		None,
		description='Format of the input. If the input is a string, you can specify the format of the string.',
	)

	required: Optional[bool] = Field(
		default=None,
		description='None if the property is optional, True if the property is required.',
	)


# --- Top-Level Workflow Definition File ---
# Uses the Union WorkflowStep type


class WorkflowDefinitionSchema(BaseModel):
	"""Pydantic model representing the structure of the workflow JSON file."""

	workflow_analysis: Optional[str] = Field(
		None,
		description='A chain of thought reasoning about the workflow. Think about which variables should be extracted.',
	)

	name: str = Field(..., description='The name of the workflow.')
	description: str = Field(..., description='A human-readable description of the workflow.')
	version: str = Field(..., description='The version identifier for this workflow definition.')
	steps: List[WorkflowStep] = Field(
		...,
		min_length=1,
		description='An ordered list of steps (actions or agent tasks) to be executed.',
	)
	input_schema: list[WorkflowInputSchemaDefinition] = Field(
		# default=WorkflowInputSchemaDefinition(),
		description='List of input schema definitions.',
	)

	# Add loader from json file
	@classmethod
	def load_from_json(cls, json_path: str):
		with open(json_path, 'r') as f:
			return cls.model_validate_json(f.read())
