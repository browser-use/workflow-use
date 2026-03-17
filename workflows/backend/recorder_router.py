"""
Recorder endpoints for Phase 2 — receives events directly from the Chrome extension.
Replaces the temporary :7331 server from the Playwright-based recording flow.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter

from workflow_use.recorder.views import (
	HttpRecordingStoppedEvent,
	HttpWorkflowUpdateEvent,
	RecorderEvent,
)

router = APIRouter(prefix='/api/recorder')

# Module-level state for the recording session
_last_workflow_update: Optional[HttpWorkflowUpdateEvent] = None
_recording_active: bool = False
_recording_start_time: Optional[float] = None
_workflow_save_dir: Path = Path('./tmp')
_workflow_save_dir.mkdir(exist_ok=True, parents=True)


class RecorderSessionState:
	"""Manages recording session state."""

	def __init__(self):
		self.last_workflow_update: Optional[HttpWorkflowUpdateEvent] = None
		self.recording_active: bool = False
		self.recording_start_time: Optional[float] = None
		self.save_dir: Path = Path('./tmp')
		self.save_dir.mkdir(exist_ok=True, parents=True)

	def reset(self):
		self.last_workflow_update = None
		self.recording_active = False
		self.recording_start_time = None


_session = RecorderSessionState()


@router.post('/event', status_code=202)
async def receive_event(event_data: RecorderEvent):
	"""Receive recording events from the Chrome extension.
	Same contract as the old :7331/event endpoint."""
	if isinstance(event_data, HttpWorkflowUpdateEvent):
		_session.last_workflow_update = event_data
	elif isinstance(event_data, HttpRecordingStoppedEvent):
		_session.recording_active = False

	return {'status': 'accepted', 'message': 'Event received'}


@router.post('/start')
async def start_recording():
	"""Initialize a new recording session."""
	_session.reset()
	_session.recording_active = True
	_session.recording_start_time = time.time()
	return {
		'status': 'started',
		'message': 'Recording session initialized on backend',
	}


@router.post('/stop')
async def stop_recording():
	"""Finalize the recording session and return the captured workflow."""
	_session.recording_active = False

	if _session.last_workflow_update and _session.last_workflow_update.payload:
		workflow_data = _session.last_workflow_update.payload
		return {
			'status': 'stopped',
			'workflow': workflow_data.model_dump() if hasattr(workflow_data, 'model_dump') else workflow_data,
			'message': 'Recording stopped. Workflow data available.',
		}

	return {
		'status': 'stopped',
		'workflow': None,
		'message': 'Recording stopped. No workflow data was captured.',
	}


@router.get('/status')
async def get_status():
	"""Check if a recording session is active."""
	step_count = 0
	if _session.last_workflow_update and _session.last_workflow_update.payload:
		payload = _session.last_workflow_update.payload
		if hasattr(payload, 'steps') and payload.steps:
			step_count = len(payload.steps)

	return {
		'recording': _session.recording_active,
		'has_workflow_data': _session.last_workflow_update is not None,
		'step_count': step_count,
		'started_at': _session.recording_start_time,
	}


@router.post('/save')
async def save_workflow(request: dict):
	"""Save a recorded workflow to the tmp/ directory as a YAML file."""
	workflow_data = request.get('workflow')
	name = request.get('name', '').strip()

	if not workflow_data:
		return {'success': False, 'error': 'No workflow data provided'}

	if not name:
		# Generate a name from timestamp
		name = f'recorded_{time.strftime("%Y%m%d_%H%M%S")}'

	# Sanitize filename
	safe_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in name).lower()
	filename = f'{safe_name}.workflow.yaml'
	filepath = _session.save_dir / filename

	# Convert to YAML and save
	try:
		yaml_content = yaml.dump(workflow_data, default_flow_style=False, sort_keys=False, allow_unicode=True)
		filepath.write_text(yaml_content, encoding='utf-8')
		return {
			'success': True,
			'filename': filename,
			'message': f'Workflow saved as {filename}',
		}
	except Exception as e:
		return {'success': False, 'error': f'Failed to save workflow: {str(e)}'}


@router.get('/health')
async def health_check():
	"""Health check endpoint for the extension to verify backend connectivity."""
	return {
		'status': 'ok',
		'service': 'workflow-use-backend',
		'recording_available': True,
		'timestamp': int(time.time() * 1000),
	}
