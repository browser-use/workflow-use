"""Tests for variable extraction functionality."""

import pytest

from workflow_use.healing.variable_extractor import VariableExtractor
from workflow_use.schema.views import (
	ClickStep,
	InputStep,
	NavigationStep,
	SelectChangeStep,
	WorkflowDefinitionSchema,
	WorkflowInputSchemaDefinition,
)


def test_extract_manual_markers():
	"""Test extracting VAR: markers from text."""
	extractor = VariableExtractor()

	text = 'Enter VAR:email:user@example.com in the form'
	markers = extractor.extract_manual_markers(text)

	assert len(markers) == 1
	assert markers[0][1] == 'email'  # variable name
	assert markers[0][2] == 'user@example.com'  # value


def test_extract_multiple_markers():
	"""Test extracting multiple markers from text."""
	extractor = VariableExtractor()

	text = 'VAR:first_name:John and VAR:last_name:Doe'
	markers = extractor.extract_manual_markers(text)

	assert len(markers) == 2
	assert markers[0][1] == 'first_name'
	assert markers[0][2] == 'John'
	assert markers[1][1] == 'last_name'
	assert markers[1][2] == 'Doe'


def test_process_workflow_with_markers():
	"""Test processing a workflow with variable markers."""
	workflow = WorkflowDefinitionSchema(
		name='Test Workflow',
		description='Test',
		version='1.0',
		steps=[
			NavigationStep(type='navigation', url='https://example.com'),
			InputStep(type='input', target_text='Email', value='VAR:user_email:test@example.com', description='Enter email'),
			InputStep(type='input', target_text='Name', value='VAR:user_name:John Doe', description='Enter name'),
		],
		input_schema=[],
	)

	extractor = VariableExtractor()
	updated_workflow, extracted_inputs = extractor.process_workflow_with_markers(workflow)

	# Check that variables were extracted
	assert len(extracted_inputs) == 2
	var_names = {inp.name for inp in extracted_inputs}
	assert 'user_email' in var_names
	assert 'user_name' in var_names

	# Check that markers were replaced with placeholders
	input_steps = [s for s in updated_workflow.steps if isinstance(s, InputStep)]
	assert input_steps[0].value == '{user_email}'
	assert input_steps[1].value == '{user_name}'

	# Check that input_schema was updated
	assert len(updated_workflow.input_schema) == 2


def test_process_workflow_preserves_existing_inputs():
	"""Test that processing preserves existing input definitions."""
	existing_input = WorkflowInputSchemaDefinition(name='existing_var', type='string', required=True)

	workflow = WorkflowDefinitionSchema(
		name='Test Workflow',
		description='Test',
		version='1.0',
		steps=[
			InputStep(type='input', target_text='Email', value='VAR:new_var:test@example.com'),
		],
		input_schema=[existing_input],
	)

	extractor = VariableExtractor()
	updated_workflow, extracted_inputs = extractor.process_workflow_with_markers(workflow)

	# Should have both existing and new variable
	assert len(updated_workflow.input_schema) == 2
	var_names = {inp.name for inp in updated_workflow.input_schema}
	assert 'existing_var' in var_names
	assert 'new_var' in var_names


def test_marker_in_select_step():
	"""Test variable marker in select_change step."""
	workflow = WorkflowDefinitionSchema(
		name='Test Workflow',
		description='Test',
		version='1.0',
		steps=[
			SelectChangeStep(type='select_change', target_text='Country', selectedText='VAR:country:United States'),
		],
		input_schema=[],
	)

	extractor = VariableExtractor()
	updated_workflow, extracted_inputs = extractor.process_workflow_with_markers(workflow)

	assert len(extracted_inputs) == 1
	assert extracted_inputs[0].name == 'country'

	select_step = updated_workflow.steps[0]
	assert isinstance(select_step, SelectChangeStep)
	assert select_step.selectedText == '{country}'


def test_marker_in_navigation_url():
	"""Test variable marker in navigation URL."""
	workflow = WorkflowDefinitionSchema(
		name='Test Workflow',
		description='Test',
		version='1.0',
		steps=[
			NavigationStep(type='navigation', url='https://example.com/search?q=VAR:search_term:laptop'),
		],
		input_schema=[],
	)

	extractor = VariableExtractor()
	updated_workflow, extracted_inputs = extractor.process_workflow_with_markers(workflow)

	assert len(extracted_inputs) == 1
	assert extracted_inputs[0].name == 'search_term'

	nav_step = updated_workflow.steps[0]
	assert isinstance(nav_step, NavigationStep)
	assert nav_step.url == 'https://example.com/search?q={search_term}'


def test_no_markers():
	"""Test processing workflow without any markers."""
	workflow = WorkflowDefinitionSchema(
		name='Test Workflow',
		description='Test',
		version='1.0',
		steps=[
			NavigationStep(type='navigation', url='https://example.com'),
			ClickStep(type='click', target_text='Submit'),
		],
		input_schema=[],
	)

	extractor = VariableExtractor()
	updated_workflow, extracted_inputs = extractor.process_workflow_with_markers(workflow)

	# No changes should be made
	assert len(extracted_inputs) == 0
	assert len(updated_workflow.input_schema) == 0
	assert updated_workflow.steps == workflow.steps


def test_marker_with_special_characters():
	"""Test marker with special characters in value."""
	extractor = VariableExtractor()

	text = 'VAR:password:P@ssw0rd!123'
	markers = extractor.extract_manual_markers(text)

	assert len(markers) == 1
	assert markers[0][1] == 'password'
	assert markers[0][2] == 'P@ssw0rd!123'


def test_marker_at_end_of_string():
	"""Test marker at the end of a string."""
	extractor = VariableExtractor()

	text = 'Enter email: VAR:email:test@example.com'
	markers = extractor.extract_manual_markers(text)

	assert len(markers) == 1
	assert markers[0][1] == 'email'


if __name__ == '__main__':
	pytest.main([__file__, '-v'])
