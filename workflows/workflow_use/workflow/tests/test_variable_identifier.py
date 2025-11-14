"""
Tests for Variable Identifier

Tests the automatic identification and parameterization of variables in workflows.
"""

import pytest

from workflow_use.workflow.variable_config import VariableConfigPresets
from workflow_use.workflow.variable_identifier import (
	VariableIdentifier,
	VariableType,
	identify_variables_in_workflow,
)


class TestVariableIdentifier:
	"""Test the VariableIdentifier class."""

	def test_pattern_detection_email(self):
		"""Test email pattern detection."""
		identifier = VariableIdentifier()
		context = {'name': 'email', 'label': 'Email Address'}

		candidate = identifier.identify_variable('john.doe@example.com', context)

		assert candidate is not None
		assert candidate.variable_type == VariableType.EMAIL
		assert candidate.confidence >= 0.85
		assert 'email' in candidate.variable_name.lower()

	def test_pattern_detection_phone(self):
		"""Test phone number pattern detection."""
		identifier = VariableIdentifier()
		context = {'name': 'phone', 'placeholder': 'Enter phone number'}

		candidate = identifier.identify_variable('555-123-4567', context)

		assert candidate is not None
		assert candidate.variable_type == VariableType.PHONE
		assert candidate.confidence >= 0.85

	def test_pattern_detection_ssn(self):
		"""Test SSN pattern detection."""
		identifier = VariableIdentifier()
		context = {'name': 'ssn'}

		candidate = identifier.identify_variable('123-45-6789', context)

		assert candidate is not None
		assert candidate.variable_type == VariableType.SSN
		assert candidate.confidence >= 0.85

	def test_context_based_detection(self):
		"""Test context-based variable detection."""
		identifier = VariableIdentifier()

		# First name field
		context = {'name': 'firstName', 'label': 'First Name'}
		candidate = identifier.identify_variable('John', context)

		assert candidate is not None
		assert 'name' in candidate.variable_name.lower()
		assert candidate.confidence >= 0.6

	def test_static_value_rejection(self):
		"""Test that static values are not parameterized."""
		identifier = VariableIdentifier()
		context = {}

		# Common static values should be rejected
		for value in ['submit', 'yes', 'no', 'true', 'false', '']:
			candidate = identifier.identify_variable(value, context)
			assert candidate is None

	def test_variable_name_normalization(self):
		"""Test variable name normalization."""
		identifier = VariableIdentifier()

		# Test various input formats
		test_cases = [
			('firstName', 'firstname'),
			('first-name', 'first_name'),
			('input-email-field', 'email_field'),
			('123test', 'field_123test'),
		]

		for input_name, expected_pattern in test_cases:
			normalized = identifier._normalize_variable_name(input_name)
			assert expected_pattern in normalized or normalized == expected_pattern

	def test_unique_variable_names(self):
		"""Test that duplicate variable names get unique suffixes."""
		identifier = VariableIdentifier()
		context = {'name': 'email'}

		# First email
		name1 = identifier._ensure_unique_variable_name('email')
		assert name1 == 'email'

		# Second email
		name2 = identifier._ensure_unique_variable_name('email')
		assert name2 == 'email_2'

		# Third email
		name3 = identifier._ensure_unique_variable_name('email')
		assert name3 == 'email_3'

	def test_workflow_identification(self):
		"""Test end-to-end workflow variable identification."""
		workflow_data = {
			'name': 'Test Form',
			'steps': [
				{
					'type': 'navigation',
					'url': 'https://example.com',
				},
				{
					'type': 'input',
					'value': 'john.doe@example.com',
					'cssSelector': 'input[name="email"]',
					'semanticInfo': {'name': 'email', 'labelText': 'Email Address'},
				},
				{
					'type': 'input',
					'value': 'JohnDoe123',
					'cssSelector': 'input[name="username"]',
					'semanticInfo': {'name': 'username', 'placeholder': 'Enter username'},
				},
				{
					'type': 'input',
					'value': 'submit',  # Should NOT be parameterized
					'cssSelector': 'button[type="submit"]',
				},
			],
		}

		result = identify_variables_in_workflow(workflow_data, min_confidence=0.6)

		# Check that variables were identified
		assert 'input_schema' in result
		assert len(result['input_schema']) >= 2  # email and username

		# Check that email was replaced with placeholder
		email_step = result['steps'][1]
		assert email_step['value'] == '{email}'

		# Check that username was replaced
		username_step = result['steps'][2]
		assert '{' in username_step['value']  # Should be a variable placeholder

		# Check that submit button was NOT parameterized
		submit_step = result['steps'][3]
		assert submit_step['value'] == 'submit'

	def test_input_schema_generation(self):
		"""Test that input schema is generated correctly."""
		workflow_data = {
			'name': 'Registration Form',
			'steps': [
				{
					'type': 'input',
					'value': 'john@example.com',
					'cssSelector': 'input[id="email"]',
					'semanticInfo': {'id': 'email'},
				},
				{
					'type': 'input',
					'value': '555-1234',
					'cssSelector': 'input[name="phone"]',
					'semanticInfo': {'name': 'phone'},
				},
			],
		}

		result = identify_variables_in_workflow(workflow_data)

		schema = result.get('input_schema', [])
		assert len(schema) >= 2

		# Check schema structure
		email_schema = next((s for s in schema if 'email' in s['name']), None)
		assert email_schema is not None
		assert email_schema['type'] == 'string'
		assert email_schema['required'] is True

	def test_already_parameterized_values(self):
		"""Test that already parameterized values are not re-processed."""
		workflow_data = {
			'name': 'Test',
			'steps': [
				{
					'type': 'input',
					'value': '{email}',  # Already a variable
					'cssSelector': 'input[name="email"]',
				}
			],
		}

		result = identify_variables_in_workflow(workflow_data)

		# Should not add duplicate variables
		assert result['steps'][0]['value'] == '{email}'

	def test_dynamic_value_detection(self):
		"""Test heuristic detection of dynamic-looking values."""
		identifier = VariableIdentifier(min_confidence=0.4)
		context = {}

		# Values that look dynamic
		dynamic_values = [
			'MyPassword123!',
			'User_2024_Name',
			'ComplexValue@123',
		]

		for value in dynamic_values:
			candidate = identifier.identify_variable(value, context)
			assert candidate is not None, f'Failed to detect dynamic value: {value}'

	def test_config_presets(self):
		"""Test configuration presets."""
		strict_config = VariableConfigPresets.strict()
		assert strict_config.min_confidence == 0.85

		aggressive_config = VariableConfigPresets.aggressive()
		assert aggressive_config.min_confidence == 0.4

		form_config = VariableConfigPresets.form_filling()
		assert 'address' in form_config.always_parameterize


class TestIntegrationWithSemanticConverter:
	"""Test integration with the semantic converter."""

	def test_semantic_converter_with_variables(self):
		"""Test that semantic converter can identify variables."""
		from workflow_use.recorder.semantic_converter import SemanticWorkflowConverter

		workflow_data = {
			'name': 'Test Workflow',
			'steps': [
				{
					'type': 'input',
					'value': 'test@example.com',
					'cssSelector': 'input[name="email"]',
					'semanticInfo': {'name': 'email'},
					'targetText': 'Email',
				}
			],
		}

		converter = SemanticWorkflowConverter(enable_variable_identification=True, variable_config={'min_confidence': 0.6})

		result = converter.convert_workflow_to_semantic(workflow_data)

		# Check that variables were identified
		assert 'input_schema' in result or result['steps'][0]['value'] == '{email}'

	def test_semantic_converter_disable_variables(self):
		"""Test that variable identification can be disabled."""
		from workflow_use.recorder.semantic_converter import SemanticWorkflowConverter

		workflow_data = {
			'name': 'Test Workflow',
			'steps': [
				{
					'type': 'input',
					'value': 'test@example.com',
					'cssSelector': 'input[name="email"]',
					'targetText': 'Email',
				}
			],
		}

		converter = SemanticWorkflowConverter(enable_variable_identification=False)

		result = converter.convert_workflow_to_semantic(workflow_data)

		# Value should remain unchanged
		assert result['steps'][0]['value'] == 'test@example.com'


if __name__ == '__main__':
	pytest.main([__file__, '-v'])
