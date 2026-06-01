"""Test that process_workflow_file_with_markers handles YAML workflow files."""

import json
from pathlib import Path

import pytest

from workflow_use.healing.variable_utils import process_workflow_file_with_markers

_FIXTURE = Path(__file__).parent / 'test_go_back.workflow.yaml'


def test_process_yaml_workflow_does_not_raise(tmp_path):
	"""YAML workflow files must be parsed without JSONDecodeError."""
	output_file = tmp_path / 'output.json'
	result = process_workflow_file_with_markers(_FIXTURE, output_path=output_file)
	assert output_file.exists()
	data = json.loads(output_file.read_text())
	assert data['name'] == 'Test Go Back'
