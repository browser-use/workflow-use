"""Tests for the variable marker file utilities."""

import datetime
import json

import yaml

from workflow_use.healing.variable_utils import process_workflow_file_with_markers

WORKFLOW = {
	'name': 'Test Workflow',
	'description': 'Test',
	'version': '1.0',
	'steps': [
		{'type': 'input', 'target_text': 'Email', 'value': 'VAR:user_email:test@example.com'},
		{'type': 'extract', 'extractionGoal': 'Extract the result'},
	],
	'input_schema': [],
}


def test_process_yaml_workflow_file(tmp_path):
	"""A .workflow.yaml file, the format the storage service writes, is processed in place."""
	path = tmp_path / 'test.workflow.yaml'
	path.write_text(yaml.dump(WORKFLOW, sort_keys=False))

	process_workflow_file_with_markers(path)

	saved = yaml.safe_load(path.read_text())
	assert saved['steps'][0]['value'] == '{user_email}'
	assert [inp['name'] for inp in saved['input_schema']] == ['user_email']


def test_process_json_workflow_file(tmp_path):
	"""A JSON workflow file still works and stays JSON."""
	path = tmp_path / 'test.workflow.json'
	path.write_text(json.dumps(WORKFLOW))

	process_workflow_file_with_markers(path)

	saved = json.loads(path.read_text())
	assert saved['steps'][0]['value'] == '{user_email}'


def test_yaml_input_to_json_output(tmp_path):
	"""The output format follows the output path extension."""
	source = tmp_path / 'test.workflow.yaml'
	source.write_text(yaml.dump(WORKFLOW, sort_keys=False))
	output = tmp_path / 'out.json'

	process_workflow_file_with_markers(source, output)

	saved = json.loads(output.read_text())
	assert saved['steps'][0]['value'] == '{user_email}'


def test_yaml_date_value_to_json_output(tmp_path):
	"""YAML-native values such as unquoted dates are written as JSON strings."""
	steps = [dict(WORKFLOW['steps'][0], recorded_on=datetime.date(2026, 1, 1)), WORKFLOW['steps'][1]]
	source = tmp_path / 'test.workflow.yaml'
	source.write_text(yaml.dump(dict(WORKFLOW, steps=steps), sort_keys=False))
	output = tmp_path / 'out.json'

	process_workflow_file_with_markers(source, output)

	saved = json.loads(output.read_text())
	assert saved['steps'][0]['recorded_on'] == '2026-01-01'
	assert saved['steps'][0]['value'] == '{user_email}'
