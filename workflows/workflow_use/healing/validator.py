"""
Workflow Validator - AI-powered validation and correction of generated workflows.

This module provides tools to:
1. Validate generated workflows for common issues
2. Suggest fixes for identified problems
3. Apply corrections to improve workflow quality
"""

from pathlib import Path
from typing import List, Optional

import aiofiles
from browser_use.llm import SystemMessage, UserMessage
from browser_use.llm.base import BaseChatModel
from pydantic import BaseModel, Field

from workflow_use.schema.views import WorkflowDefinitionSchema

# Get the absolute path to the prompts directory
_PROMPTS_DIR = Path(__file__).parent / 'prompts'


class WorkflowIssue(BaseModel):
	"""Represents an issue found in a workflow."""

	severity: str = Field(..., description="Severity: 'critical', 'warning', or 'suggestion'")
	step_index: Optional[int] = Field(None, description='Index of the step with the issue (if applicable)')
	issue_type: str = Field(..., description="Type of issue: 'agent_step', 'missing_selector', 'incorrect_step_type', etc.")
	description: str = Field(..., description='Human-readable description of the issue')
	suggestion: str = Field(..., description='Suggested fix for the issue')


class WorkflowValidationResult(BaseModel):
	"""Result of workflow validation."""

	issues: List[WorkflowIssue] = Field(default_factory=list, description='List of issues found')
	corrected_workflow: Optional[WorkflowDefinitionSchema] = Field(None, description='Corrected workflow (if fixes were applied)')
	validation_summary: str = Field(..., description='Summary of validation results')


class WorkflowValidator:
	"""AI-powered workflow validator and corrector."""

	def __init__(self, llm: BaseChatModel):
		self.llm = llm

	async def validate_workflow(
		self, workflow: WorkflowDefinitionSchema, original_task: str = '', browser_logs: Optional[str] = None
	) -> WorkflowValidationResult:
		"""
		Validate a workflow and identify issues.

		Args:
		    workflow: The workflow to validate
		    original_task: The original task description (helps with context)
		    browser_logs: Optional browser-use logs from a failed run (for runtime validation)

		Returns:
		    WorkflowValidationResult with identified issues and optional corrections
		"""
		# Load validation prompt using absolute path
		prompt_file = _PROMPTS_DIR / 'workflow_validation_prompt.md'
		async with aiofiles.open(prompt_file, mode='r') as f:
			prompt_content = await f.read()

		# Prepare workflow JSON for review
		workflow_json = workflow.model_dump_json(indent=2, exclude_none=True)

		# Build the validation request
		validation_context = f"""
# Workflow to Validate

{workflow_json}

# Original Task
{original_task if original_task else 'Not provided'}

# Browser Logs (if available)
{browser_logs if browser_logs else 'Not provided - this is a post-generation validation'}
"""

		system_message = SystemMessage(content=prompt_content)
		user_message = UserMessage(content=validation_context)

		# Get validation result from AI
		try:
			response = await self.llm.ainvoke([system_message, user_message], output_format=WorkflowValidationResult)
			result: WorkflowValidationResult = response.completion  # type: ignore
		except Exception as e:
			print('ERROR: Failed to validate workflow')
			print(f'Error details: {e}')
			# Return empty validation result
			result = WorkflowValidationResult(issues=[], validation_summary=f'Validation failed due to error: {e}')

		return result

	async def validate_and_correct(
		self, workflow: WorkflowDefinitionSchema, original_task: str = '', browser_logs: Optional[str] = None
	) -> WorkflowDefinitionSchema:
		"""
		Validate a workflow and automatically apply corrections if issues are found.

		Args:
		    workflow: The workflow to validate
		    original_task: The original task description
		    browser_logs: Optional browser-use logs from a failed run

		Returns:
		    Corrected workflow (or original if no issues)
		"""
		result = await self.validate_workflow(workflow, original_task, browser_logs)

		if result.corrected_workflow:
			return result.corrected_workflow

		# No corrections were made, return original
		return workflow

	def print_validation_report(self, result: WorkflowValidationResult) -> None:
		"""Print a human-readable validation report."""
		print('\n' + '=' * 80)
		print('WORKFLOW VALIDATION REPORT')
		print('=' * 80)

		print(f'\n{result.validation_summary}\n')

		if not result.issues:
			print('✅ No issues found!')
			return

		# Group by severity
		critical = [i for i in result.issues if i.severity == 'critical']
		warnings = [i for i in result.issues if i.severity == 'warning']
		suggestions = [i for i in result.issues if i.severity == 'suggestion']

		if critical:
			print(f'🔴 CRITICAL ISSUES ({len(critical)}):')
			for i, issue in enumerate(critical, 1):
				step_info = f' (Step {issue.step_index})' if issue.step_index is not None else ''
				print(f'\n  {i}. {issue.issue_type}{step_info}')
				print(f'     {issue.description}')
				print(f'     💡 {issue.suggestion}')

		if warnings:
			print(f'\n⚠️  WARNINGS ({len(warnings)}):')
			for i, issue in enumerate(warnings, 1):
				step_info = f' (Step {issue.step_index})' if issue.step_index is not None else ''
				print(f'\n  {i}. {issue.issue_type}{step_info}')
				print(f'     {issue.description}')
				print(f'     💡 {issue.suggestion}')

		if suggestions:
			print(f'\n💡 SUGGESTIONS ({len(suggestions)}):')
			for i, issue in enumerate(suggestions, 1):
				step_info = f' (Step {issue.step_index})' if issue.step_index is not None else ''
				print(f'\n  {i}. {issue.issue_type}{step_info}')
				print(f'     {issue.description}')
				print(f'     💡 {issue.suggestion}')

		print('\n' + '=' * 80)
