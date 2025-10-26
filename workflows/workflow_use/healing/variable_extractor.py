"""Service for extracting and managing variables in workflows.

This module provides functionality to:
1. Analyze workflow steps to identify values that should be parameterized
2. Extract variables from text using special markers (e.g., VAR:name:value)
3. Convert hardcoded values to variable placeholders
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from browser_use.llm import SystemMessage, UserMessage
from browser_use.llm.base import BaseChatModel
from pydantic import BaseModel

from workflow_use.schema.views import (
	InputStep,
	NavigationStep,
	SelectChangeStep,
	WorkflowDefinitionSchema,
	WorkflowInputSchemaDefinition,
	WorkflowStep,
)


class VariableSuggestion(BaseModel):
	"""Suggested variable to extract from a workflow."""

	name: str  # Variable name (e.g., "first_name")
	type: str  # Type: "string", "number", or "bool"
	format: Optional[str] = None  # Format hint (e.g., "MM/DD/YYYY")
	required: bool = True
	original_value: str  # The hardcoded value to replace
	step_indices: List[int]  # Which steps use this value
	reasoning: str  # Why this should be a variable


class VariableExtractionResult(BaseModel):
	"""Result of variable extraction analysis."""

	suggestions: List[VariableSuggestion]
	updated_workflow: Optional[WorkflowDefinitionSchema] = None


VARIABLE_ANALYSIS_PROMPT = """You are an expert at analyzing workflows to identify values that should be parameterized.

Analyze the provided workflow and identify ALL values that should be converted to input variables instead of being hardcoded.

## Guidelines for Variable Identification

**SHOULD BE VARIABLES:**
- Personal information (names, emails, phone numbers, addresses)
- Search terms or filter criteria
- User-entered form data (text fields, amounts, quantities)
- Dates and times
- Selection options that vary by use case
- Any value that would change between different executions of the workflow

**SHOULD STAY HARDCODED:**
- Navigation URLs (unless the URL itself is dynamic)
- UI element labels/text used for targeting elements
- Static button/link text
- Fixed dropdown options used for navigation
- Constant configuration values

## Analysis Process

1. Review each step in the workflow
2. Identify all hardcoded values in `value`, `selectedText`, `url`, and other fields
3. For each value, determine if it's user-specific or static
4. Suggest appropriate variable names (use snake_case)
5. Specify the type and format requirements

## Output Format

Return a JSON object with the following structure:

```json
{
  "suggestions": [
    {
      "name": "variable_name",
      "type": "string",
      "format": "optional format hint",
      "required": true,
      "original_value": "the hardcoded value",
      "step_indices": [0, 2],
      "reasoning": "why this should be a variable"
    }
  ]
}
```

## Workflow to Analyze

{workflow_json}
"""


class VariableExtractor:
	"""Service for extracting variables from workflows."""

	# Pattern for manual variable markers: VAR:variable_name:value
	# Matches one or more markers anywhere in the text
	# Value is captured until whitespace or end of string
	MANUAL_MARKER_PATTERN = re.compile(r'VAR:([a-z_][a-z0-9_]*):(\S+)')

	def __init__(self, llm: Optional[BaseChatModel] = None):
		"""Initialize the variable extractor.

		Args:
		    llm: Optional LLM for automatic variable extraction
		"""
		self.llm = llm

	def extract_manual_markers(self, text: str) -> List[Tuple[str, str, str]]:
		"""Extract variable markers from text.

		Args:
		    text: Text potentially containing VAR:name:value markers

		Returns:
		    List of (marker_text, variable_name, value) tuples
		"""
		markers = []
		for match in self.MANUAL_MARKER_PATTERN.finditer(text):
			markers.append((match.group(0), match.group(1), match.group(2)))
		return markers

	def process_workflow_with_markers(
		self, workflow: WorkflowDefinitionSchema
	) -> Tuple[WorkflowDefinitionSchema, List[WorkflowInputSchemaDefinition]]:
		"""Process workflow to extract manual variable markers.

		Scans all workflow steps for VAR:name:value markers and:
		1. Extracts the variable definitions
		2. Replaces markers with {variable_name} placeholders

		Args:
		    workflow: Workflow potentially containing variable markers

		Returns:
		    Tuple of (updated workflow, list of extracted input definitions)
		"""
		extracted_inputs: Dict[str, WorkflowInputSchemaDefinition] = {}

		# Process each step
		for step_index, step in enumerate(workflow.steps):
			self._process_step_markers(step, extracted_inputs)

		# Update workflow with extracted inputs
		workflow_dict = workflow.model_dump()
		existing_inputs = {inp.name: inp for inp in workflow.input_schema}

		# Merge extracted inputs with existing ones
		existing_inputs.update(extracted_inputs)
		workflow_dict['input_schema'] = list(existing_inputs.values())

		updated_workflow = WorkflowDefinitionSchema(**workflow_dict)
		return updated_workflow, list(extracted_inputs.values())

	def _process_step_markers(self, step: WorkflowStep, extracted_inputs: Dict[str, WorkflowInputSchemaDefinition]) -> None:
		"""Process a single step to extract and replace variable markers.

		Args:
		    step: Workflow step to process (modified in place)
		    extracted_inputs: Dictionary to accumulate extracted inputs
		"""
		# Check common fields that might contain markers
		fields_to_check = []

		if isinstance(step, InputStep):
			fields_to_check.append('value')
		elif isinstance(step, SelectChangeStep):
			fields_to_check.append('selectedText')
		elif isinstance(step, NavigationStep):
			fields_to_check.append('url')

		# Check target_text for steps that have it (this is the key feature!)
		if hasattr(step, 'target_text'):
			fields_to_check.append('target_text')

		# Also check description field for all steps
		fields_to_check.append('description')

		for field_name in fields_to_check:
			field_value = getattr(step, field_name, None)
			if not field_value or not isinstance(field_value, str):
				continue

			markers = self.extract_manual_markers(field_value)
			if not markers:
				continue

			# Replace markers and extract variables
			updated_value = field_value
			for marker_text, var_name, var_value in markers:
				# Add to extracted inputs if not already present
				if var_name not in extracted_inputs:
					extracted_inputs[var_name] = WorkflowInputSchemaDefinition(
						name=var_name,
						type='string',  # Default to string
						required=True,
					)

				# Replace entire field value with placeholder (since marker is the whole value)
				updated_value = f'{{{var_name}}}'

			# Update the field
			setattr(step, field_name, updated_value.strip())

	async def suggest_variables(self, workflow: WorkflowDefinitionSchema) -> VariableExtractionResult:
		"""Use LLM to suggest which values should be variables.

		Args:
		    workflow: Workflow to analyze

		Returns:
		    VariableExtractionResult with suggestions

		Raises:
		    ValueError: If no LLM is configured
		"""
		if not self.llm:
			raise ValueError('LLM is required for automatic variable suggestion')

		workflow_json = workflow.model_dump_json(indent=2)
		prompt = VARIABLE_ANALYSIS_PROMPT.format(workflow_json=workflow_json)

		messages = [SystemMessage(content=prompt), UserMessage(content='Please analyze this workflow and suggest variables.')]

		# Use structured output to get suggestions
		response = await self.llm.ainvoke(messages, output_format=VariableExtractionResult)
		result: VariableExtractionResult = response.completion

		return result

	def apply_variable_suggestions(
		self,
		workflow: WorkflowDefinitionSchema,
		suggestions: List[VariableSuggestion],
		apply_all: bool = False,
	) -> WorkflowDefinitionSchema:
		"""Apply variable suggestions to a workflow.

		Args:
		    workflow: Original workflow
		    suggestions: List of variable suggestions to apply
		    apply_all: If True, apply all suggestions. If False, only apply those marked as should_apply

		Returns:
		    Updated workflow with variables applied
		"""
		workflow_dict = workflow.model_dump()

		# Build input schema from suggestions
		new_inputs: Dict[str, WorkflowInputSchemaDefinition] = {}
		for suggestion in suggestions:
			if apply_all:
				new_inputs[suggestion.name] = WorkflowInputSchemaDefinition(
					name=suggestion.name,
					type=suggestion.type,
					format=suggestion.format,
					required=suggestion.required,
				)

		# Update steps to use variables
		for step_index in range(len(workflow_dict['steps'])):
			step = workflow_dict['steps'][step_index]

			for suggestion in suggestions:
				if apply_all and step_index in suggestion.step_indices:
					# Replace original value with placeholder
					self._replace_value_in_step(step, suggestion.original_value, f'{{{suggestion.name}}}')

		# Merge with existing inputs
		existing_inputs = {inp['name']: inp for inp in workflow_dict.get('input_schema', [])}
		existing_inputs.update({k: v.model_dump() for k, v in new_inputs.items()})
		workflow_dict['input_schema'] = list(existing_inputs.values())

		return WorkflowDefinitionSchema(**workflow_dict)

	def _replace_value_in_step(self, step_dict: Dict[str, Any], old_value: str, new_value: str) -> None:
		"""Replace a value in a step dictionary.

		Args:
		    step_dict: Step dictionary to modify
		    old_value: Value to replace
		    new_value: Replacement value
		"""
		for key in ['value', 'selectedText', 'url', 'task', 'target_text']:
			if key in step_dict and step_dict[key] == old_value:
				step_dict[key] = new_value
