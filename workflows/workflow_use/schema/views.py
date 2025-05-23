from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


# --- Base Step Model ---
# Common fields for all step types
class BaseWorkflowStep(BaseModel):
	description: Optional[str] = Field(None, description="Optional description/comment about the step's purpose.")
	output: Optional[str] = Field(None, description='Context key to store step output under.')
	# Allow other fields captured from raw events but not explicitly modeled
	model_config = {'extra': 'allow'}


# --- Timestamped Step Mixin (for deterministic actions) ---
class TimestampedWorkflowStep(BaseWorkflowStep):
	timestamp: Optional[int] = Field(None, description='Timestamp from recording (informational).')
	tabId: Optional[int] = Field(None, description='Browser tab ID from recording (informational).')


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
class NavigationStep(TimestampedWorkflowStep):
	"""Navigates using the 'navigation' action (likely maps to go_to_url)."""

	type: Literal['navigation']  # As seen in examples
	url: str = Field(..., description='Target URL to navigate to. Can use {context_var}.')


class ClickStep(TimestampedWorkflowStep):
	"""Clicks an element using 'click' (maps to workflow controller's click)."""

	type: Literal['click']  # As seen in examples
	cssSelector: str = Field(..., description='CSS selector for the target element.')
	xpath: Optional[str] = Field(None, description='XPath selector (often informational).')
	elementTag: Optional[str] = Field(None, description='HTML tag (informational).')
	elementText: Optional[str] = Field(None, description='Element text (informational).')


class InputStep(TimestampedWorkflowStep):
	"""Inputs text using 'input' (maps to workflow controller's input)."""

	type: Literal['input']  # As seen in examples
	cssSelector: str = Field(..., description='CSS selector for the target input element.')
	value: str = Field(..., description='Value to input. Can use {context_var}.')
	xpath: Optional[str] = Field(None, description='XPath selector (informational).')
	elementTag: Optional[str] = Field(None, description='HTML tag (informational).')


class SelectChangeStep(TimestampedWorkflowStep):
	"""Selects a dropdown option using 'select_change' (maps to workflow controller's select_change)."""

	type: Literal['select_change']  # Assumed type for workflow controller's select_change
	cssSelector: str = Field(..., description='CSS selector for the target select element.')
	selectedText: str = Field(..., description='Visible text of the option to select. Can use {context_var}.')
	xpath: Optional[str] = Field(None, description='XPath selector (informational).')
	elementTag: Optional[str] = Field(None, description='HTML tag (informational).')


class KeyPressStep(TimestampedWorkflowStep):
	"""Presses a key using 'key_press' (maps to workflow controller's key_press)."""

	type: Literal['key_press']  # As seen in examples
	cssSelector: str = Field(..., description='CSS selector for the target element.')
	key: str = Field(..., description="The key to press (e.g., 'Tab', 'Enter').")
	xpath: Optional[str] = Field(None, description='XPath selector (informational).')
	elementTag: Optional[str] = Field(None, description='HTML tag (informational).')


class ScrollStep(TimestampedWorkflowStep):
	"""Scrolls the page using 'scroll' (maps to workflow controller's scroll)."""

	type: Literal['scroll']  # Assumed type for workflow controller's scroll
	scrollX: int = Field(..., description='Horizontal scroll pixels.')
	scrollY: int = Field(..., description='Vertical scroll pixels.')


class PageExtractionStep(TimestampedWorkflowStep):
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
		description='A chain of thought reasoning analysis of the original workflow recording.',
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
