"""
Simple file-based storage service for workflows.
This can be extended to use a proper database (SQLite, PostgreSQL, etc.) in the future.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

import yaml
from pydantic import BaseModel, Field

from workflow_use.schema.views import WorkflowDefinitionSchema

logger = logging.getLogger(__name__)


class WorkflowMetadata(BaseModel):
	"""Metadata for a stored workflow."""

	id: str = Field(default_factory=lambda: str(uuid4()))
	name: str
	description: str
	version: str = '1.0'
	created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
	updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
	file_path: str
	generation_mode: str = 'manual'  # "manual" or "browser_use"
	original_task: Optional[str] = None  # The task prompt used for generation


class WorkflowStorageService:
	"""Service for storing and retrieving workflows."""

	def __init__(self, storage_dir: str | Path = './storage'):
		"""
		Initialize the workflow storage service.

		Args:
			storage_dir: Directory to store workflow files and metadata
		"""
		self.storage_dir = Path(storage_dir)
		self.workflows_dir = self.storage_dir / 'workflows'
		self.metadata_file = self.storage_dir / 'metadata.json'

		# Create directories if they don't exist
		self.workflows_dir.mkdir(parents=True, exist_ok=True)

		# Load or initialize metadata
		self.metadata: dict[str, WorkflowMetadata] = {}
		self._load_metadata()

	def _load_metadata(self) -> None:
		"""Load workflow metadata from disk."""
		if self.metadata_file.exists():
			try:
				with open(self.metadata_file, 'r') as f:
					data = json.load(f)
					self.metadata = {wf_id: WorkflowMetadata(**wf_data) for wf_id, wf_data in data.items()}
				logger.info(f'Loaded {len(self.metadata)} workflow metadata entries')
			except Exception as e:
				logger.error(f'Error loading metadata: {e}')
				self.metadata = {}
		else:
			logger.info('No existing metadata file, starting fresh')

	def _save_metadata(self) -> None:
		"""Save workflow metadata to disk."""
		try:
			with open(self.metadata_file, 'w') as f:
				json.dump({wf_id: wf.model_dump() for wf_id, wf in self.metadata.items()}, f, indent=2)
			logger.info(f'Saved metadata for {len(self.metadata)} workflows')
		except Exception as e:
			logger.error(f'Error saving metadata: {e}')
			raise

	def save_workflow(
		self,
		workflow: WorkflowDefinitionSchema,
		generation_mode: str = 'manual',
		original_task: Optional[str] = None,
		workflow_id: Optional[str] = None,
	) -> WorkflowMetadata:
		"""
		Save a workflow to storage.

		Args:
			workflow: The workflow definition to save
			generation_mode: How the workflow was created ("manual" or "browser_use")
			original_task: The original task prompt (for browser_use generation)
			workflow_id: Optional ID to use (for updates)

		Returns:
			WorkflowMetadata for the saved workflow
		"""
		# Create or update metadata
		if workflow_id and workflow_id in self.metadata:
			# Update existing workflow
			metadata = self.metadata[workflow_id]
			metadata.name = workflow.name
			metadata.description = workflow.description
			metadata.version = workflow.version
			metadata.updated_at = datetime.utcnow().isoformat()
			logger.info(f'Updating existing workflow: {workflow_id}')
		else:
			# Create new workflow
			workflow_id = workflow_id or str(uuid4())
			filename = f'{workflow_id}.workflow.yaml'
			file_path = str(self.workflows_dir / filename)

			metadata = WorkflowMetadata(
				id=workflow_id,
				name=workflow.name,
				description=workflow.description,
				version=workflow.version,
				file_path=file_path,
				generation_mode=generation_mode,
				original_task=original_task,
			)
			logger.info(f'Creating new workflow: {workflow_id}')

		# Save workflow file
		# Exclude legacy/unnecessary fields to keep workflow files clean
		workflow_dict = workflow.model_dump(mode='json', exclude_none=True)

		# Remove top-level bloat
		workflow_dict.pop('workflow_analysis', None)

		# Clean up steps by removing legacy/verbose/null fields
		if 'steps' in workflow_dict:
			for step in workflow_dict['steps']:
				# Remove legacy/verbose fields (but keep xpath as fallback selector)
				fields_to_remove = [
					'agent_reasoning',  # Verbose agent thinking
					'page_context_url',  # Redundant context
					'page_context_title',  # Redundant context
					'elementHash',  # Internal hash
					'elementTag',  # Can be inferred
					'container_hint',  # Usually null
					'position_hint',  # Usually null
					'interaction_type',  # Usually null
					'default_value',  # Usually null for inputs
					'output',  # Usually null
				]
				for field in fields_to_remove:
					step.pop(field, None)

				# Remove empty cssSelector
				if step.get('cssSelector') == '':
					step.pop('cssSelector', None)

				# Clean up selectorStrategies - remove if null or if all values are JavaScript href
				if 'selectorStrategies' in step:
					strategies = step['selectorStrategies']
					if strategies is None:
						step.pop('selectorStrategies', None)
					elif isinstance(strategies, list):
						# Filter out strategies with JavaScript href values
						cleaned_strategies = [
							s
							for s in strategies
							if not (isinstance(s.get('value'), str) and s.get('value', '').lower().startswith('javascript:'))
						]
						# Only keep if we have valid strategies
						if cleaned_strategies:
							step['selectorStrategies'] = cleaned_strategies
						else:
							step.pop('selectorStrategies', None)

		with open(metadata.file_path, 'w') as f:
			yaml.dump(workflow_dict, f, default_flow_style=False, sort_keys=False)

		# Update metadata
		self.metadata[workflow_id] = metadata
		self._save_metadata()

		logger.info(f"Saved workflow '{workflow.name}' to {metadata.file_path}")
		return metadata

	def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinitionSchema]:
		"""
		Retrieve a workflow by ID.

		Args:
			workflow_id: The workflow ID

		Returns:
			The workflow definition or None if not found
		"""
		if workflow_id not in self.metadata:
			logger.warning(f'Workflow not found: {workflow_id}')
			return None

		metadata = self.metadata[workflow_id]
		try:
			with open(metadata.file_path, 'r') as f:
				data = yaml.safe_load(f)
			workflow = WorkflowDefinitionSchema(**data)
			logger.info(f'Loaded workflow: {workflow_id}')
			return workflow
		except Exception as e:
			logger.error(f'Error loading workflow {workflow_id}: {e}')
			return None

	def get_workflow_by_name(self, name: str) -> Optional[WorkflowDefinitionSchema]:
		"""
		Retrieve a workflow by name.

		Args:
			name: The workflow name

		Returns:
			The workflow definition or None if not found
		"""
		for workflow_id, metadata in self.metadata.items():
			if metadata.name == name:
				return self.get_workflow(workflow_id)

		logger.warning(f'Workflow not found with name: {name}')
		return None

	def list_workflows(self) -> List[WorkflowMetadata]:
		"""
		List all stored workflows.

		Returns:
			List of workflow metadata
		"""
		return list(self.metadata.values())

	def delete_workflow(self, workflow_id: str) -> bool:
		"""
		Delete a workflow.

		Args:
			workflow_id: The workflow ID

		Returns:
			True if deleted, False if not found
		"""
		if workflow_id not in self.metadata:
			logger.warning(f'Cannot delete, workflow not found: {workflow_id}')
			return False

		metadata = self.metadata[workflow_id]

		# Delete file
		try:
			Path(metadata.file_path).unlink()
			logger.info(f'Deleted workflow file: {metadata.file_path}')
		except Exception as e:
			logger.warning(f'Error deleting workflow file: {e}')

		# Remove from metadata
		del self.metadata[workflow_id]
		self._save_metadata()

		logger.info(f'Deleted workflow: {workflow_id}')
		return True

	def search_workflows(self, query: Optional[str] = None, generation_mode: Optional[str] = None) -> List[WorkflowMetadata]:
		"""
		Search workflows by query string or generation mode.

		Args:
			query: Search term to match in name or description
			generation_mode: Filter by generation mode ("manual" or "browser_use")

		Returns:
			List of matching workflow metadata
		"""
		results = list(self.metadata.values())

		if generation_mode:
			results = [w for w in results if w.generation_mode == generation_mode]

		if query:
			query_lower = query.lower()
			results = [w for w in results if query_lower in w.name.lower() or query_lower in w.description.lower()]

		return results
