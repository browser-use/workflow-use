import asyncio
import json
import os
import subprocess
import tempfile  # For temporary file handling
import webbrowser
from pathlib import Path

import aiofiles
import pandas as pd
import typer
from browser_use import Browser
from browser_use.llm import ChatBrowserUse
from browser_use.llm.base import BaseChatModel

from workflow_use.builder.service import BuilderService
from workflow_use.controller.service import WorkflowController
from workflow_use.healing.service import HealingService
from workflow_use.mcp.service import get_mcp_server
from workflow_use.recorder.service import RecordingService  # Added import
from workflow_use.storage.service import WorkflowStorageService
from workflow_use.workflow.service import Workflow

# Placeholder for recorder functionality
# from src.recorder.service import RecorderService

app = typer.Typer(
	name='workflow-cli',
	help='A CLI tool to create and run workflows.',
	add_completion=False,
	no_args_is_help=True,
)

# Default LLM instance to None
llm_instance: BaseChatModel
try:
	llm_instance = ChatBrowserUse(model='bu-latest')
	page_extraction_llm = ChatBrowserUse(model='bu-latest')
except Exception as e:
	typer.secho(f'Error initializing LLM: {e}. Would you like to set your BROWSER_USE_API_KEY?', fg=typer.colors.RED)
	set_browser_use_api_key = input('Set BROWSER_USE_API_KEY? (y/n): ')
	if set_browser_use_api_key.lower() == 'y':
		os.environ['BROWSER_USE_API_KEY'] = input('Enter your BROWSER_USE_API_KEY: ')
		llm_instance = ChatBrowserUse(model='bu-latest')
		page_extraction_llm = ChatBrowserUse(model='bu-latest')

builder_service = BuilderService(llm=llm_instance) if llm_instance else None
# recorder_service = RecorderService() # Placeholder
recording_service = (
	RecordingService()
)  # Assuming RecordingService does not need LLM, or handle its potential None state if it does.
healing_service = HealingService(llm=llm_instance) if llm_instance else None
storage_service = WorkflowStorageService()


def get_default_save_dir() -> Path:
	"""Returns the default save directory for workflows."""
	# Ensure ./tmp exists for temporary files as well if we use it
	tmp_dir = Path('./tmp').resolve()
	tmp_dir.mkdir(parents=True, exist_ok=True)
	return tmp_dir


# --- Helper function for building and saving workflow ---
def _build_and_save_workflow_from_recording(
	recording_path: Path,
	default_save_dir: Path,
	is_temp_recording: bool = False,  # To adjust messages if it's from a live recording
) -> Path | None:
	"""Builds a workflow from a recording file, prompts for details, and saves it."""
	if not builder_service:
		typer.secho(
			'BuilderService not initialized. Cannot build workflow.',
			fg=typer.colors.RED,
		)
		return None

	prompt_subject = 'recorded' if is_temp_recording else 'provided'
	typer.echo()  # Add space
	description: str = typer.prompt(typer.style(f'What is the purpose of this {prompt_subject} workflow?', bold=True))

	typer.echo()  # Add space
	output_dir_str: str = typer.prompt(
		typer.style('Where would you like to save the final built workflow?', bold=True)
		+ f" (e.g., ./my_workflows, press Enter for '{default_save_dir}')",
		default=str(default_save_dir),
	)
	output_dir = Path(output_dir_str).resolve()
	output_dir.mkdir(parents=True, exist_ok=True)

	typer.echo(f'The final built workflow will be saved in: {typer.style(str(output_dir), fg=typer.colors.CYAN)}')
	typer.echo()  # Add space

	typer.echo(
		f'Processing recording ({typer.style(str(recording_path.name), fg=typer.colors.MAGENTA)}) and building workflow...'
	)
	try:
		workflow_definition = asyncio.run(
			builder_service.build_workflow_from_path(
				recording_path,
				description,
			)
		)
	except FileNotFoundError:
		typer.secho(
			f'Error: Recording file not found at {recording_path}. Please ensure it exists.',
			fg=typer.colors.RED,
		)
		return None
	except Exception as e:
		typer.secho(f'Error building workflow: {e}', fg=typer.colors.RED)
		return None

	if not workflow_definition:
		typer.secho(
			f'Failed to build workflow definition from the {prompt_subject} recording.',
			fg=typer.colors.RED,
		)
		return None

	typer.secho('Workflow built successfully!', fg=typer.colors.GREEN, bold=True)
	typer.echo()  # Add space

	file_stem = recording_path.stem
	if is_temp_recording:
		file_stem = file_stem.replace('temp_recording_', '') or 'recorded'

	default_workflow_filename = f'{file_stem}.workflow.yaml'
	workflow_output_name: str = typer.prompt(
		typer.style('Enter a name for the generated workflow file', bold=True) + ' (e.g., my_search.workflow.yaml):',
		default=default_workflow_filename,
	)
	# Ensure the file name ends with .json, .yaml, or .yml
	if not (
		workflow_output_name.endswith('.json') or workflow_output_name.endswith('.yaml') or workflow_output_name.endswith('.yml')
	):
		workflow_output_name = f'{workflow_output_name}.yaml'
	final_workflow_path = output_dir / workflow_output_name

	try:
		asyncio.run(builder_service.save_workflow_to_path(workflow_definition, final_workflow_path))
		typer.secho(
			f'Final workflow definition saved to: {typer.style(str(final_workflow_path.resolve()), fg=typer.colors.BRIGHT_GREEN, bold=True)}',
			fg=typer.colors.GREEN,  # Overall message color
		)
		return final_workflow_path
	except Exception as e:
		typer.secho(f'Error saving workflow: {e}', fg=typer.colors.RED)
		return None


# --- Helper function for building semantic workflow from recording ---
def _build_and_save_semantic_workflow_from_recording(
	recording_path: Path,
	default_save_dir: Path,
	is_temp_recording: bool = False,
	simulate_interactions: bool = False,
	auto_fix_navigation: bool = False,
) -> Path | None:
	"""Builds a semantic workflow from a recording file using visible text mappings."""

	prompt_subject = 'recorded' if is_temp_recording else 'provided'
	typer.echo()  # Add space
	description: str = typer.prompt(typer.style(f'What is the purpose of this {prompt_subject} workflow?', bold=True))

	typer.echo()  # Add space
	output_dir_str: str = typer.prompt(
		typer.style('Where would you like to save the final semantic workflow?', bold=True)
		+ f" (e.g., ./my_workflows, press Enter for '{default_save_dir}')",
		default=str(default_save_dir),
	)
	output_dir = Path(output_dir_str).resolve()
	output_dir.mkdir(parents=True, exist_ok=True)

	typer.echo(f'The final semantic workflow will be saved in: {typer.style(str(output_dir), fg=typer.colors.CYAN)}')
	typer.echo()  # Add space

	typer.echo(
		f'Processing recording ({typer.style(str(recording_path.name), fg=typer.colors.MAGENTA)}) and building semantic workflow...'
	)

	# Load the recording
	try:
		with open(recording_path, 'r') as f:
			recording_data = json.load(f)
	except FileNotFoundError:
		typer.secho(
			f'Error: Recording file not found at {recording_path}. Please ensure it exists.',
			fg=typer.colors.RED,
		)
		return None
	except Exception as e:
		typer.secho(f'Error loading recording: {e}', fg=typer.colors.RED)
		return None

	# Convert recording to semantic workflow format
	try:
		semantic_workflow = asyncio.run(
			_convert_recording_to_semantic_workflow(recording_data, description, simulate_interactions, auto_fix_navigation)
		)
	except Exception as e:
		typer.secho(f'Error converting to semantic workflow: {e}', fg=typer.colors.RED)
		return None

	if not semantic_workflow:
		typer.secho(
			f'Failed to build semantic workflow definition from the {prompt_subject} recording.',
			fg=typer.colors.RED,
		)
		return None

	typer.secho('Semantic workflow built successfully!', fg=typer.colors.GREEN, bold=True)
	typer.echo()  # Add space

	file_stem = recording_path.stem
	if is_temp_recording:
		file_stem = file_stem.replace('temp_recording_', '') or 'recorded'

	default_workflow_filename = f'{file_stem}.semantic.workflow.yaml'
	workflow_output_name: str = typer.prompt(
		typer.style('Enter a name for the generated semantic workflow file', bold=True)
		+ ' (e.g., my_search.semantic.workflow.yaml):',
		default=default_workflow_filename,
	)
	# Ensure the file name ends with .json, .yaml, or .yml
	if not (
		workflow_output_name.endswith('.json') or workflow_output_name.endswith('.yaml') or workflow_output_name.endswith('.yml')
	):
		workflow_output_name = f'{workflow_output_name}.yaml'
	final_workflow_path = output_dir / workflow_output_name

	try:
		with open(final_workflow_path, 'w') as f:
			json.dump(semantic_workflow, f, indent=2)
		typer.secho(
			f'Final semantic workflow saved to: {typer.style(str(final_workflow_path.resolve()), fg=typer.colors.BRIGHT_GREEN, bold=True)}',
			fg=typer.colors.GREEN,
		)
		return final_workflow_path
	except Exception as e:
		typer.secho(f'Error saving semantic workflow: {e}', fg=typer.colors.RED)
		return None


def _fix_missing_navigation_steps(steps):
	"""Automatically detect and fix missing navigation steps in multi-page forms."""
	if not steps:
		return steps

	fixed_steps = []
	current_page_url = None

	for i, step in enumerate(steps):
		step_type = step.get('type', '').lower()
		step_url = step.get('url', '')

		# Track navigation steps
		if step_type == 'navigation':
			current_page_url = step_url
			fixed_steps.append(step)
			continue

		# For interactive steps, check if we need to add missing navigation
		if step_type in ['click', 'input', 'select', 'keypress']:
			# If step's URL is different from current page, we need navigation
			if step_url and current_page_url and step_url != current_page_url:
				# Check if this looks like a form progression (common patterns)
				if _is_form_progression(current_page_url, step_url):
					# Try to infer the missing navigation button
					navigation_step = _infer_navigation_step(current_page_url, step_url, steps, i)
					if navigation_step:
						typer.echo(
							f'🔧 Auto-fixing: Adding missing navigation from {current_page_url.split("/")[-1]} to {step_url.split("/")[-1]}'
						)
						fixed_steps.append(navigation_step)
						current_page_url = step_url
				else:
					# Add explicit navigation step
					fixed_steps.append({'description': f'Navigate to {step_url}', 'type': 'navigation', 'url': step_url})
					current_page_url = step_url

			fixed_steps.append(step)
		else:
			# Non-interactive steps (scroll, etc.)
			fixed_steps.append(step)

	return fixed_steps


def _is_form_progression(from_url, to_url):
	"""Check if this looks like a multi-step form progression."""
	if not from_url or not to_url:
		return False

	# Common form progression patterns
	form_patterns = [
		('personal-info', 'contact-info'),
		('contact-info', 'employment-info'),
		('employment-info', 'review'),
		('step-1', 'step-2'),
		('step-2', 'step-3'),
		('page-1', 'page-2'),
		('page-2', 'page-3'),
	]

	from_path = from_url.split('/')[-1]
	to_path = to_url.split('/')[-1]

	for from_pattern, to_pattern in form_patterns:
		if from_pattern in from_path and to_pattern in to_path:
			return True

	return False


def _infer_navigation_step(from_url, to_url, all_steps, current_index):
	"""Infer the missing navigation button based on URL progression."""
	from_path = from_url.split('/')[-1]
	to_path = to_url.split('/')[-1]

	# Look for navigation buttons that might have been clicked around this time
	search_range = 5  # Look 5 steps before and after
	start_idx = max(0, current_index - search_range)
	end_idx = min(len(all_steps), current_index + search_range)

	for i in range(start_idx, end_idx):
		step = all_steps[i]
		if step.get('type') == 'click':
			target_text = (step.get('target_text') or step.get('targetText') or '').lower()

			# Common navigation button patterns
			next_patterns = ['next', 'continue', 'proceed', 'forward']

			# Check if this looks like a navigation button for our target page
			if any(pattern in target_text for pattern in next_patterns):
				# Try to match the destination
				if 'contact' in target_text and 'contact' in to_path:
					return {
						'description': 'Click navigation button',
						'type': 'click',
						'target_text': step.get('target_text') or step.get('targetText'),
						'url': from_url,
					}
				elif 'employment' in target_text and 'employment' in to_path:
					return {
						'description': 'Click navigation button',
						'type': 'click',
						'target_text': step.get('target_text') or step.get('targetText'),
						'url': from_url,
					}
				elif 'review' in target_text and 'review' in to_path:
					return {
						'description': 'Click navigation button',
						'type': 'click',
						'target_text': step.get('target_text') or step.get('targetText'),
						'url': from_url,
					}

	# If we can't find a specific button, create a generic navigation step
	if 'contact' in to_path:
		return {
			'description': 'Navigate to contact information',
			'type': 'click',
			'target_text': 'Next: Contact Information',
			'url': from_url,
		}
	elif 'employment' in to_path:
		return {
			'description': 'Navigate to employment information',
			'type': 'click',
			'target_text': 'Next: Employment Information',
			'url': from_url,
		}
	elif 'review' in to_path:
		return {'description': 'Navigate to review', 'type': 'click', 'target_text': 'Next: Review', 'url': from_url}

	return None


async def _convert_recording_to_semantic_workflow(recording_data, description, simulate_interactions, auto_fix_navigation=False):
	"""Convert a recorded workflow to semantic format using target_text fields."""
	from workflow_use.workflow.semantic_extractor import SemanticExtractor

	# Extract workflow metadata
	workflow_name = recording_data.get('name', 'Recorded Workflow')
	steps = recording_data.get('steps', [])

	# Ensure steps is a list and not None
	if steps is None:
		steps = []

	if not steps:
		raise Exception('No steps found in recording')

	# Filter out redundant click events before processing
	filtered_steps = _filter_redundant_click_events(steps)
	if filtered_steps is None:
		filtered_steps = steps
	typer.echo(f'Filtered {len(steps) - len(filtered_steps)} redundant click events')

	# Auto-fix missing navigation steps (optional)
	if auto_fix_navigation:
		fixed_steps = _fix_missing_navigation_steps(filtered_steps)
		if len(fixed_steps) > len(filtered_steps):
			typer.echo(f'🔧 Auto-fixed {len(fixed_steps) - len(filtered_steps)} missing navigation steps')
	else:
		fixed_steps = filtered_steps
		typer.echo('⚠️ Skipping auto-fix navigation steps (disabled)')

	# Initialize semantic extractor
	semantic_extractor = SemanticExtractor()

	# Start browser to process pages
	browser = Browser()

	semantic_steps = []
	current_url = None
	semantic_mapping = {}

	try:
		for i, step in enumerate(fixed_steps):
			step_type = step.get('type', '').lower()

			if step_type == 'navigation':
				# Navigation step - extract semantic mapping for new page
				current_url = step.get('url')
				if current_url:
					semantic_steps.append({'description': f'Navigate to {current_url}', 'type': 'navigation', 'url': current_url})

					# Extract semantic mapping for this page
					try:
						page = await browser.get_current_page()
						await page.goto(current_url)
						# Wait for page to load and dynamic content
						await asyncio.sleep(2)
						semantic_mapping = await semantic_extractor.extract_semantic_mapping(page)
						if semantic_mapping is None:
							semantic_mapping = {}
						typer.echo(f'Extracted {len(semantic_mapping or {})} semantic elements from {current_url}')
					except Exception as e:
						typer.echo(f'Warning: Could not extract semantic mapping from {current_url}: {e}')
						semantic_mapping = {}

			elif step_type in ['click', 'input', 'select', 'keypress']:
				# Before processing interactive steps, refresh semantic mapping to catch dynamic changes
				# This is especially important after form interactions that might show/hide elements
				if i > 0 and current_url:  # Skip refresh for first step
					try:
						page = await browser.get_current_page()
						# Small delay to let any previous interactions take effect
						await asyncio.sleep(1)
						semantic_mapping = await semantic_extractor.extract_semantic_mapping(page)
						if semantic_mapping is None:
							semantic_mapping = {}
						typer.echo(f'Refreshed semantic mapping: {len(semantic_mapping or {})} elements available')
					except Exception as e:
						typer.echo(f'Warning: Could not refresh semantic mapping: {e}')
						semantic_mapping = {}

				# Interactive step - convert to semantic format
				# Ensure semantic_mapping is not None before passing it
				if semantic_mapping is None:
					semantic_mapping = {}
				semantic_step = await _convert_step_to_semantic(step, semantic_mapping, browser, simulate_interactions)
				if semantic_step:
					semantic_steps.append(semantic_step)

			elif step_type == 'scroll':
				# Keep scroll steps as-is
				semantic_steps.append(
					{
						'description': step.get('description', 'Scroll page'),
						'type': 'scroll',
						'scrollX': step.get('scrollX', 0),
						'scrollY': step.get('scrollY', 0),
					}
				)

				# After scroll, refresh semantic mapping as new elements might be visible
				if current_url:
					try:
						page = await browser.get_current_page()
						await page.evaluate(f'() => window.scrollBy({step.get("scrollX", 0)}, {step.get("scrollY", 0)})')
						await asyncio.sleep(1)  # Wait for scroll to complete
						semantic_mapping = await semantic_extractor.extract_semantic_mapping(page)
						if semantic_mapping is None:
							semantic_mapping = {}
						typer.echo(f'Refreshed semantic mapping after scroll: {len(semantic_mapping or {})} elements available')
					except Exception as e:
						typer.echo(f'Warning: Could not refresh semantic mapping after scroll: {e}')
						semantic_mapping = {}

			elif step_type == 'extract':
				# Keep extraction steps as-is with their extractionGoal
				extraction_step = {
					'description': step.get('description', 'Extract information with AI'),
					'type': 'extract',
					'extractionGoal': step.get('extractionGoal', 'Extract information from the page'),
					'url': step.get('url', current_url),
				}
				semantic_steps.append(extraction_step)
				typer.echo(f'Added extraction step: {extraction_step["extractionGoal"]}')

			else:
				# Unknown step type - keep as-is but warn
				typer.echo(f"Warning: Unknown step type '{step_type}' - keeping as-is")
				semantic_steps.append(step)

	finally:
		await browser.close()

	# Build the semantic workflow
	semantic_workflow = {
		'workflow_analysis': 'Semantic version of recorded workflow. Uses visible text to identify elements instead of CSS selectors for improved reliability.',
		'name': f'{workflow_name} (Semantic)',
		'description': description,
		'version': '1.0',
		'steps': semantic_steps,
		'input_schema': [],  # Can be enhanced later with variable detection
	}

	return semantic_workflow


def _filter_redundant_click_events(steps):
	"""Filter out redundant click events that occur within a short time window."""
	filtered_steps = []
	i = 0

	typer.echo(f'🔍 Filtering {len(steps)} steps to remove redundant clicks...')

	while i < len(steps):
		step = steps[i]

		if step.get('type') == 'click':
			# Look ahead for potential redundant clicks
			click_group = [step]
			j = i + 1

			# Group clicks that happen within 500ms of each other, but be smarter about it
			while j < len(steps) and j < i + 5:  # Look at most 5 steps ahead
				next_step = steps[j]

				# Don't group clicks if they're on different URLs (page navigation happened)
				current_url = step.get('url', '')
				next_url = next_step.get('url', '')
				if current_url and next_url and current_url != next_url:
					break

				# Check if this is a duplicate click on the same target
				step_text = str(step.get('target_text') or step.get('targetText') or '').strip()
				next_text = str(next_step.get('target_text') or next_step.get('targetText') or '').strip()

				# If they have the same target_text, they're likely duplicates
				if (
					next_step.get('type') == 'click'
					and step_text
					and next_text
					and step_text == next_text
					and abs(next_step.get('timestamp', 0) - step.get('timestamp', 0)) <= 2000
				):  # Increased to 2 seconds
					click_group.append(next_step)
					j += 1
					continue

				# Don't group clicks if one is a navigation button (different target_text)
				navigation_keywords = ['next', 'submit', 'continue', 'proceed', 'save', 'finish', 'confirm', 'back', 'previous']
				if any(keyword in step_text.lower() for keyword in navigation_keywords) or any(
					keyword in next_text.lower() for keyword in navigation_keywords
				):
					if step_text != next_text:  # Different navigation buttons
						break

				# Don't group radio buttons - each radio button selection is meaningful
				step_css = str(step.get('cssSelector') or '')
				next_css = str(next_step.get('cssSelector') or '')
				if 'role="radio"' in step_css and 'role="radio"' in next_css:
					# Radio buttons are always meaningful choices - don't group them
					step_text_display = (
						step.get('target_text') or step.get('targetText') or step.get('elementText') or 'radio button'
					)
					next_text_display = (
						next_step.get('target_text')
						or next_step.get('targetText')
						or next_step.get('elementText')
						or 'radio button'
					)
					typer.echo(f"Not grouping radio button selections: '{step_text_display}' vs '{next_text_display}'")
					break

				if next_step.get('type') == 'click' and abs(next_step.get('timestamp', 0) - step.get('timestamp', 0)) <= 500:
					click_group.append(next_step)
					j += 1
				else:
					break

			if len(click_group) > 1:
				# Multiple clicks in rapid succession - pick the best one
				best_click = _select_best_click_from_group(click_group)
				filtered_steps.append(best_click)
				typer.echo(
					f'Filtered {len(click_group) - 1} redundant clicks, kept: {best_click.get("target_text", best_click.get("targetText", best_click.get("elementText", "unknown")))}'
				)
			else:
				# Single click - keep as is
				filtered_steps.append(step)

			# Skip the steps we've already processed
			i = j
		else:
			# Non-click step - keep as is
			filtered_steps.append(step)
			i += 1

	return filtered_steps


def _select_best_click_from_group(click_group):
	"""Select the best click event from a group of rapid clicks."""
	# Priority order:
	# 1. Navigation/flow control buttons (Next, Submit, Continue, etc.)
	# 2. Form selections with meaningful text (radio buttons, checkboxes)
	# 3. Click with meaningful target_text
	# 4. Click with meaningful elementText
	# 5. Click with semantic info
	# 6. Click with shortest CSS selector

	# First priority: Navigation/flow control buttons
	navigation_keywords = ['next', 'submit', 'continue', 'proceed', 'save', 'finish', 'confirm', 'back', 'previous']
	for click in click_group:
		target_text = str(click.get('target_text') or click.get('targetText') or '').lower()
		element_text = str(click.get('elementText') or '').lower()
		try:
			if any(keyword in target_text or keyword in element_text for keyword in navigation_keywords):
				typer.echo(
					f"Prioritizing navigation button: '{click.get('target_text') or click.get('targetText') or click.get('elementText', 'unknown')}'"
				)
				return click
		except Exception as e:
			typer.echo(f'DEBUG: Error in navigation check: {e}, target_text={target_text}, element_text={element_text}')
			continue

	# Second priority: Form selections (radio buttons, checkboxes) that change state
	for click in click_group:
		try:
			css_selector = str(click.get('cssSelector') or '')
			if (
				'radio' in css_selector
				or 'checkbox' in css_selector
				or 'role="radio"' in css_selector
				or 'type="checkbox"' in css_selector
			):
				target_text = click.get('target_text') or click.get('targetText') or click.get('elementText')
				if target_text and len(str(target_text).strip()) > 1:
					typer.echo(f"Prioritizing form selection: '{target_text}'")
					return click
		except Exception as e:
			typer.echo(f'DEBUG: Error in form selection check: {e}')
			continue

	# Third priority: Click with meaningful target_text
	for click in click_group:
		target_text = (click.get('target_text') or click.get('targetText') or '').strip()
		if target_text and len(target_text) > 1 and not target_text.isdigit():
			return click

	# Fourth priority: Click with meaningful elementText
	for click in click_group:
		element_text = (click.get('elementText') or '').strip()
		if element_text and len(element_text) > 1 and not element_text.isdigit():
			return click

	# Fifth priority: Click with semantic info
	for click in click_group:
		semantic_info = click.get('semanticInfo', {})
		if semantic_info:
			for field in ['labelText', 'ariaLabel', 'name', 'id']:
				value = semantic_info.get(field, '').strip()
				if value and len(value) > 1:
					return click

	# Last resort - pick the one with shortest CSS selector (usually more specific)
	click_group.sort(key=lambda x: len(x.get('cssSelector') or ''))
	return click_group[0]


async def _convert_step_to_semantic(step, semantic_mapping, browser, simulate_interactions):
	"""Convert a single recorded step to semantic format."""
	step_type = step.get('type', '').lower()
	description = step.get('description', '')

	# Try to find the best semantic target_text for this step
	target_text = None

	# Look for element text or other identifiers from the recording
	element_text_raw = step.get('elementText')
	element_text = element_text_raw.strip() if element_text_raw else ''
	css_selector = step.get('cssSelector', '')
	xpath = step.get('xpath', '')

	# Also check for semantic info from the updated extension
	semantic_info = step.get('semanticInfo', {})
	# Check for existing target_text field (primary) or targetText field (fallback)
	target_text_raw = step.get('target_text') or step.get('targetText')
	existing_target_text = target_text_raw.strip() if target_text_raw else ''

	# Priority order for finding target_text:
	# 1. Existing target_text from recording (if available)
	# 2. Best semantic match from our current mapping
	# 3. Extract from semantic info
	# 4. Use element text
	# 5. Extract from CSS selector

	if existing_target_text:
		target_text = existing_target_text
		typer.echo(f"Using existing target_text from recording: '{target_text}'")
	elif element_text:
		# Try to find this text in our semantic mapping
		target_text = _find_best_semantic_match(element_text, semantic_mapping)
		if target_text:
			typer.echo(f"Found semantic match for '{element_text}' -> '{target_text}'")
		else:
			target_text = element_text
			typer.echo(f"Using original element text: '{target_text}'")
	elif semantic_info:
		# Extract from semantic info if available
		potential_texts = [
			semantic_info.get('labelText', ''),
			semantic_info.get('placeholder', ''),
			semantic_info.get('ariaLabel', ''),
			semantic_info.get('textContent', ''),
			semantic_info.get('name', ''),
			semantic_info.get('id', ''),
		]

		for text in potential_texts:
			if text.strip():
				target_text = _find_best_semantic_match(text.strip(), semantic_mapping)
				if target_text:
					typer.echo(f"Found semantic match from semanticInfo: '{text}' -> '{target_text}'")
					break

		# If no semantic match found, use the first meaningful text
		if not target_text:
			for text in potential_texts:
				if text.strip() and len(text.strip()) > 1:
					target_text = text.strip()
					typer.echo(f"Using text from semanticInfo: '{target_text}'")
					break

	# If no good semantic match, try to extract from CSS selector
	if not target_text and css_selector:
		target_text = _extract_target_from_selector(css_selector)
		if target_text:
			typer.echo(f"Extracted target from CSS selector: '{target_text}'")

	# Build the semantic step
	# Handle button events specifically
	if step_type == 'button':
		semantic_step = {
			'description': description or f"Click button '{target_text}'",
			'type': 'button',
			'button_text': step.get('button_text', target_text),
			'button_type': step.get('button_type', 'button'),
		}
	else:
		semantic_step = {'description': description or f'{step_type.title()} element', 'type': step_type}

	if target_text:
		semantic_step['target_text'] = target_text
	elif css_selector:
		# Fallback to original CSS selector if no semantic mapping available
		semantic_step['cssSelector'] = css_selector
		typer.echo('Warning: No semantic target found, using CSS selector fallback')
	else:
		typer.echo('Warning: No target method available for step, may need manual adjustment')

	# Add step-specific fields
	if step_type == 'input' and 'value' in step:
		semantic_step['value'] = step['value']
	elif step_type == 'select' and 'selectedText' in step:
		semantic_step['selectedText'] = step['selectedText']
	elif step_type == 'keypress' and 'key' in step:
		semantic_step['key'] = step['key']

	# Optionally simulate the interaction to keep the page state accurate for subsequent steps
	if simulate_interactions and browser:
		try:
			await _simulate_step_interaction(step, browser)
		except Exception as e:
			typer.echo(f'Warning: Could not simulate interaction for step: {e}')

	return semantic_step


async def _simulate_step_interaction(step, browser):
	"""Simulate the interaction to keep page state accurate (optional)."""
	step_type = step.get('type', '').lower()
	css_selector = step.get('cssSelector', '')

	if not css_selector:
		return

	try:
		page = await browser.get_current_page()

		if step_type == 'click':
			await page.click(css_selector, timeout=2000)
		elif step_type == 'input':
			value = step.get('value', '')
			await page.fill(css_selector, value, timeout=2000)
		elif step_type == 'select':
			selected_text = step.get('selectedText', '')
			if selected_text:
				await page.select_option(css_selector, label=selected_text, timeout=2000)
		elif step_type == 'keypress':
			key = step.get('key', '')
			if key:
				await page.press(css_selector, key, timeout=2000)

		# Small delay to let the interaction take effect
		await asyncio.sleep(0.5)

	except Exception:
		# Silently ignore simulation errors - this is just for page state accuracy
		pass


def _find_best_semantic_match(element_text, semantic_mapping):
	"""Find the best semantic match for element text."""
	if not element_text or not semantic_mapping:
		return None

	element_text_lower = element_text.lower().strip()

	# Exact match first
	for text_key in semantic_mapping.keys():
		if text_key.lower() == element_text_lower:
			return text_key

	# Partial match
	for text_key in semantic_mapping.keys():
		if element_text_lower in text_key.lower() or text_key.lower() in element_text_lower:
			return text_key

	# If no good match, return original text (the semantic executor will try to find it)
	return element_text


def _extract_target_from_selector(css_selector):
	"""Extract a target_text from CSS selector if possible."""
	if not css_selector:
		return None

	# Try to extract ID
	if '#' in css_selector:
		id_part = css_selector.split('#')[1].split('[')[0].split('.')[0]
		if id_part:
			return id_part

	# Try to extract name from attribute selector
	if '[name=' in css_selector:
		name_match = css_selector.split('[name=')[1].split(']')[0].strip('"\'')
		if name_match:
			return name_match

	return None


@app.command(
	name='create-workflow',
	help='Records a new browser interaction and then builds a workflow definition.',
)
def create_workflow():
	"""
	Guides the user through recording browser actions, then uses the helper
	to build and save the workflow definition.
	"""
	if not recording_service:
		# Adjusted RecordingService initialization check assuming it doesn't need LLM
		typer.secho(
			'RecordingService not available. Cannot create workflow.',
			fg=typer.colors.RED,
		)
		raise typer.Exit(code=1)

	default_tmp_dir = get_default_save_dir()  # Ensures ./tmp exists for temporary files

	typer.echo(typer.style('Starting interactive browser recording session...', bold=True))
	typer.echo('Please follow instructions in the browser. Close the browser or follow prompts to stop recording.')
	typer.echo()  # Add space

	temp_recording_path = None
	try:
		captured_recording_model = asyncio.run(recording_service.capture_workflow())

		if not captured_recording_model:
			typer.secho(
				'Recording session ended, but no workflow data was captured.',
				fg=typer.colors.YELLOW,
			)
			raise typer.Exit(code=1)

		typer.secho('Recording captured successfully!', fg=typer.colors.GREEN, bold=True)
		typer.echo()  # Add space

		with tempfile.NamedTemporaryFile(
			mode='w',
			suffix='.json',
			prefix='temp_recording_',
			delete=False,
			dir=default_tmp_dir,
			encoding='utf-8',
		) as tmp_file:
			try:
				tmp_file.write(captured_recording_model.model_dump_json(indent=2))
			except AttributeError:
				json.dump(captured_recording_model, tmp_file, indent=2)
			temp_recording_path = Path(tmp_file.name)

		# Use the helper function to build and save
		saved_path = _build_and_save_workflow_from_recording(temp_recording_path, default_tmp_dir, is_temp_recording=True)
		if not saved_path:
			typer.secho(
				'Failed to complete workflow creation after recording.',
				fg=typer.colors.RED,
			)
			raise typer.Exit(code=1)

	except Exception as e:
		typer.secho(f'An error occurred during workflow creation: {e}', fg=typer.colors.RED)
		raise typer.Exit(code=1)


@app.command(
	name='create-workflow-no-ai',
	help='Records a new browser interaction and builds a semantic workflow optimized for no-AI execution.',
)
def create_workflow_no_ai():
	"""
	Records browser actions and builds a semantic workflow using target_text fields
	instead of CSS selectors, optimized for run-workflow-no-ai execution.
	"""
	if not recording_service:
		typer.secho(
			'RecordingService not available. Cannot create workflow.',
			fg=typer.colors.RED,
		)
		raise typer.Exit(code=1)

	default_tmp_dir = get_default_save_dir()

	typer.echo(typer.style('Starting semantic workflow recording session...', bold=True))
	typer.echo('🎯 This will create a workflow optimized for semantic execution (no AI required)!')
	typer.echo('Please follow instructions in the browser. Close the browser or follow prompts to stop recording.')
	typer.echo()  # Add space

	temp_recording_path = None
	try:
		captured_recording_model = asyncio.run(recording_service.capture_workflow())

		if not captured_recording_model:
			typer.secho(
				'Recording session ended, but no workflow data was captured.',
				fg=typer.colors.YELLOW,
			)
			raise typer.Exit(code=1)

		typer.secho('Recording captured successfully!', fg=typer.colors.GREEN, bold=True)
		typer.echo()  # Add space

		with tempfile.NamedTemporaryFile(
			mode='w',
			suffix='.json',
			prefix='temp_recording_',
			delete=False,
			dir=default_tmp_dir,
			encoding='utf-8',
		) as tmp_file:
			try:
				tmp_file.write(captured_recording_model.model_dump_json(indent=2))
			except AttributeError:
				json.dump(captured_recording_model, tmp_file, indent=2)
			temp_recording_path = Path(tmp_file.name)

		# Use the semantic workflow builder instead of the regular one
		saved_path = _build_and_save_semantic_workflow_from_recording(
			temp_recording_path, default_tmp_dir, is_temp_recording=True, simulate_interactions=False, auto_fix_navigation=False
		)
		if not saved_path:
			typer.secho(
				'Failed to complete semantic workflow creation after recording.',
				fg=typer.colors.RED,
			)
			raise typer.Exit(code=1)

		# Show next steps
		typer.echo()
		typer.secho('🎉 Semantic workflow created successfully!', fg=typer.colors.GREEN, bold=True)
		typer.echo()
		typer.echo(typer.style('Next steps:', bold=True))
		typer.echo(
			f'1. Test your workflow: {typer.style(f"python cli.py run-workflow-no-ai {saved_path.name}", fg=typer.colors.CYAN)}'
		)
		typer.echo('2. Edit the workflow file to add variables or customize steps')
		typer.echo('3. The workflow uses visible text mappings for reliable execution!')

	except Exception as e:
		typer.secho(f'An error occurred during semantic workflow creation: {e}', fg=typer.colors.RED)
		raise typer.Exit(code=1)


@app.command(
	name='build-from-recording',
	help='Builds a workflow definition from an existing recording JSON file.',
)
def build_from_recording_command(
	recording_path: Path = typer.Argument(
		...,
		exists=True,
		file_okay=True,
		dir_okay=False,
		readable=True,
		resolve_path=True,
		help='Path to the existing recording JSON file.',
	),
):
	"""
	Takes a path to a recording JSON file, prompts for workflow details,
	builds the workflow using BuilderService, and saves it.
	"""
	default_save_dir = get_default_save_dir()
	typer.echo(
		typer.style(
			f'Building workflow from provided recording: {typer.style(str(recording_path.resolve()), fg=typer.colors.MAGENTA)}',
			bold=True,
		)
	)
	typer.echo()  # Add space

	saved_path = _build_and_save_workflow_from_recording(recording_path, default_save_dir, is_temp_recording=False)
	if not saved_path:
		typer.secho(f'Failed to build workflow from {recording_path.name}.', fg=typer.colors.RED)
		raise typer.Exit(code=1)


@app.command(
	name='build-semantic-from-recording',
	help='Builds a semantic workflow from an existing recording JSON file (optimized for no-AI execution).',
)
def build_semantic_from_recording_command(
	recording_path: Path = typer.Argument(
		...,
		exists=True,
		file_okay=True,
		dir_okay=False,
		readable=True,
		resolve_path=True,
		help='Path to the existing recording JSON file.',
	),
	simulate_interactions: bool = typer.Option(
		False,
		'--simulate-interactions',
		'-s',
		help='Simulate recorded interactions during conversion for better semantic mapping accuracy (slower but more accurate)',
	),
	auto_fix_navigation: bool = typer.Option(
		False,
		'--auto-fix-navigation',
		'-n',
		help='Automatically add missing navigation steps based on URL changes (may add unwanted back/forward navigation)',
	),
):
	"""
	Takes a path to a recording JSON file and builds a semantic workflow using target_text fields
	instead of CSS selectors, optimized for run-workflow-no-ai execution.
	"""
	default_save_dir = get_default_save_dir()
	typer.echo(
		typer.style(
			f'Building semantic workflow from recording: {typer.style(str(recording_path.resolve()), fg=typer.colors.MAGENTA)}',
			bold=True,
		)
	)

	if simulate_interactions:
		typer.echo(
			typer.style('⚙️ Interaction simulation enabled - this will be slower but more accurate', fg=typer.colors.YELLOW)
		)

	typer.echo()  # Add space

	saved_path = _build_and_save_semantic_workflow_from_recording(
		recording_path,
		default_save_dir,
		is_temp_recording=False,
		simulate_interactions=simulate_interactions,
		auto_fix_navigation=auto_fix_navigation,
	)
	if not saved_path:
		typer.secho(f'Failed to build semantic workflow from {recording_path.name}.', fg=typer.colors.RED)
		raise typer.Exit(code=1)

	# Show next steps
	typer.echo()
	typer.secho('🎉 Semantic workflow created successfully!', fg=typer.colors.GREEN, bold=True)
	typer.echo()
	typer.echo(typer.style('Next steps:', bold=True))
	typer.echo(
		f'1. Test your workflow: {typer.style(f"python cli.py run-workflow-no-ai {saved_path.name}", fg=typer.colors.CYAN)}'
	)
	typer.echo('2. Edit the workflow file to add variables or customize steps')
	typer.echo('3. The workflow uses visible text mappings for reliable execution!')


@app.command(
	name='run-as-tool',
	help='Runs an existing workflow and automatically parse the required variables from prompt.',
)
def run_as_tool_command(
	workflow_path: Path = typer.Argument(
		...,
		exists=True,
		file_okay=True,
		dir_okay=False,
		readable=True,
		help='Path to the .workflow.json file.',
		show_default=False,
	),
	prompt: str = typer.Option(
		...,
		'--prompt',
		'-p',
		help='Prompt for the LLM to reason about and execute the workflow.',
		prompt=True,  # Prompts interactively if not provided
	),
	use_cloud: bool = typer.Option(False, help='Use Browser-Use Cloud browser'),
):
	"""
	Run the workflow and automatically parse the required variables from the input/prompt that the user provides.
	"""
	if not llm_instance:
		typer.secho(
			'LLM not initialized. Please check your OpenAI API key. Cannot run as tool.',
			fg=typer.colors.RED,
		)
		raise typer.Exit(code=1)

	typer.echo(
		typer.style(f'Loading workflow from: {typer.style(str(workflow_path.resolve()), fg=typer.colors.MAGENTA)}', bold=True)
	)
	typer.echo()  # Add space

	try:
		# Pass llm_instance to ensure the workflow can use it if needed for as_tool() or run_with_prompt()
		workflow_obj = Workflow.load_from_file(
			str(workflow_path), llm=llm_instance, page_extraction_llm=page_extraction_llm, use_cloud=use_cloud
		)
	except Exception as e:
		typer.secho(f'Error loading workflow: {e}', fg=typer.colors.RED)
		raise typer.Exit(code=1)

	typer.secho('Workflow loaded successfully.', fg=typer.colors.GREEN, bold=True)
	typer.echo()  # Add space
	typer.echo(typer.style(f'Running workflow as tool with prompt: "{prompt}"', bold=True))

	try:
		result = asyncio.run(workflow_obj.run_as_tool(prompt))
		typer.secho('\nWorkflow execution completed!', fg=typer.colors.GREEN, bold=True)
		typer.echo(typer.style('Result:', bold=True))
		# Ensure result is JSON serializable for consistent output
		try:
			typer.echo(json.dumps(json.loads(result), indent=2))  # Assuming result from run_with_prompt is a JSON string
		except (json.JSONDecodeError, TypeError):
			typer.echo(result)  # Fallback to string if not a JSON string or not serializable
	except Exception as e:
		typer.secho(f'Error running workflow as tool: {e}', fg=typer.colors.RED)
		raise typer.Exit(code=1)


@app.command(name='run-workflow', help='Runs an existing workflow from a JSON file.')
def run_workflow_command(
	workflow_path: Path = typer.Argument(
		...,
		exists=True,
		file_okay=True,
		dir_okay=False,
		readable=True,
		help='Path to the .workflow.json file.',
		show_default=False,
	),
	use_cloud: bool = typer.Option(False, help='Use Browser-Use Cloud browser'),
):
	"""
	Loads and executes a workflow, prompting the user for required inputs.
	"""

	async def _run_workflow():
		typer.echo(
			typer.style(f'Loading workflow from: {typer.style(str(workflow_path.resolve()), fg=typer.colors.MAGENTA)}', bold=True)
		)
		typer.echo()  # Add space

		try:
			# Instantiate Browser and WorkflowController for the Workflow instance
			# Pass llm_instance for potential agent fallbacks or agentic steps
			browser = Browser(use_cloud=use_cloud)
			controller_instance = WorkflowController()  # Add any necessary config if required
			workflow_obj = Workflow.load_from_file(
				str(workflow_path),
				browser=browser,
				llm=llm_instance,
				controller=controller_instance,
				page_extraction_llm=page_extraction_llm,
			)
		except Exception as e:
			typer.secho(f'Error loading workflow: {e}', fg=typer.colors.RED)
			raise typer.Exit(code=1)

		typer.secho('Workflow loaded successfully.', fg=typer.colors.GREEN, bold=True)

		inputs = {}
		input_definitions = workflow_obj.inputs_def  # Access inputs_def from the Workflow instance

		if input_definitions:  # Check if the list is not empty
			# Check if all REQUIRED inputs have defaults (can skip prompting)
			# Note: Optional inputs can be skipped, so we only check required ones
			required_inputs = [inp for inp in input_definitions if inp.required]
			all_required_have_defaults = all(getattr(input_def, 'default', None) is not None for input_def in required_inputs)

			if all_required_have_defaults:
				# All required inputs have defaults, use defaults automatically
				typer.echo()  # Add space
				typer.echo(typer.style('Using default values for workflow inputs:', bold=True))
				typer.echo()  # Add space

				for input_def in input_definitions:
					default_value = getattr(input_def, 'default', None)
					if default_value is not None:
						inputs[input_def.name] = default_value
						var_name_styled = typer.style(input_def.name, fg=typer.colors.CYAN, bold=True)
						typer.echo(f'  • {var_name_styled} = {typer.style(str(default_value), fg=typer.colors.BLUE)}')
					elif not input_def.required:
						var_name_styled = typer.style(input_def.name, fg=typer.colors.CYAN, bold=True)
						typer.echo(f'  • {var_name_styled} = {typer.style("(not provided, optional)", fg=typer.colors.YELLOW)}')
				typer.echo()
			else:
				# Some inputs need user input
				typer.echo()  # Add space
				typer.echo(typer.style('Provide values for the following workflow inputs:', bold=True))
				typer.echo()  # Add space

				for input_def in input_definitions:
					var_name_styled = typer.style(input_def.name, fg=typer.colors.CYAN, bold=True)
					prompt_question = typer.style(f'Enter value for {var_name_styled}', bold=True)

					var_type = input_def.type.lower()  # type is a direct attribute
					is_required = input_def.required
					default_value = getattr(input_def, 'default', None)

					type_info_str = f'type: {var_type}'
					if is_required:
						status_str = typer.style('required', fg=typer.colors.RED)
					else:
						status_str = typer.style('optional', fg=typer.colors.YELLOW)

					# Add format information if available
					format_info_str = ''
					if hasattr(input_def, 'format') and input_def.format:
						format_info_str = f', format: {typer.style(input_def.format, fg=typer.colors.GREEN)}'

					# Add default value information if available
					default_info_str = ''
					if default_value is not None:
						default_info_str = f', default: {typer.style(str(default_value), fg=typer.colors.BLUE)}'

					full_prompt_text = f'{prompt_question} ({status_str}, {type_info_str}{format_info_str}{default_info_str})'

					input_val = None
					if var_type == 'bool':
						input_val = typer.confirm(full_prompt_text, default=default_value if default_value is not None else None)
					elif var_type == 'number':
						input_val = typer.prompt(
							full_prompt_text, type=float, default=default_value if default_value is not None else ...
						)
					elif var_type == 'string':  # Default to string for other unknown types as well
						input_val = typer.prompt(
							full_prompt_text, type=str, default=default_value if default_value is not None else ...
						)
					else:  # Should ideally not happen if schema is validated, but good to have a fallback
						typer.secho(
							f"Warning: Unknown type '{var_type}' for variable '{input_def.name}'. Treating as string.",
							fg=typer.colors.YELLOW,
						)
						input_val = typer.prompt(
							full_prompt_text, type=str, default=default_value if default_value is not None else ...
						)

					inputs[input_def.name] = input_val
					typer.echo()  # Add space after each prompt
		else:
			typer.echo('No input schema found in the workflow, or no properties defined. Proceeding without inputs.')

		typer.echo()  # Add space
		typer.echo(typer.style('Running workflow...', bold=True))

		try:
			# Call run on the Workflow instance
			# close_browser_at_end=True is the default for Workflow.run, but explicit for clarity
			result = await workflow_obj.run(inputs=inputs, close_browser_at_end=True)

			typer.secho('\nWorkflow execution completed!', fg=typer.colors.GREEN, bold=True)
			typer.echo(typer.style('Result:', bold=True))
			# Output the number of steps executed, similar to previous behavior
			typer.echo(f'{typer.style(str(len(result.step_results)), bold=True)} steps executed.')
			# For more detailed results, one might want to iterate through the 'result' list
			# and print each item, or serialize the whole list to JSON.
			# For now, sticking to the step count as per original output.

		except Exception as e:
			typer.secho(f'Error running workflow: {e}', fg=typer.colors.RED)
			raise typer.Exit(code=1)

	return asyncio.run(_run_workflow())


@app.command(name='run-workflow-no-ai', help='Runs an existing workflow without AI using semantic abstraction.')
def run_workflow_no_ai_command(
	workflow_path: Path = typer.Argument(
		...,
		exists=True,
		file_okay=True,
		dir_okay=False,
		readable=True,
		help='Path to the .workflow.json file.',
		show_default=False,
	),
	enable_extraction: bool = typer.Option(
		False,
		'--enable-extraction',
		'-e',
		help='Enable AI-powered extraction steps (requires OpenAI API key for extraction steps only)',
	),
	use_cloud: bool = typer.Option(False, help='Use Browser-Use Cloud browser'),
):
	"""
	Loads and executes a workflow using semantic abstraction without any AI/LLM involvement.
	This uses visible text mappings to deterministic selectors instead of fragile CSS selectors.
	Optionally enables AI-powered extraction steps while keeping semantic abstraction for interactions.
	"""

	async def _run_workflow_no_ai():
		typer.echo(
			typer.style(f'Loading workflow from: {typer.style(str(workflow_path.resolve()), fg=typer.colors.MAGENTA)}', bold=True)
		)
		typer.echo()  # Add space

		try:
			# Instantiate Browser for the Workflow instance
			browser = Browser(use_cloud=use_cloud)
			# Create a dummy LLM instance since it's required by the constructor but won't be used for interactions
			dummy_llm = None
			extraction_llm = None

			try:
				from browser_use.llm import ChatBrowserUse

				dummy_llm = ChatBrowserUse(model='bu-latest')
				if enable_extraction:
					extraction_llm = ChatBrowserUse(model='bu-latest')
					typer.secho('AI extraction enabled - will use LLM for extraction steps only.', fg=typer.colors.BLUE)
			except Exception as e:
				if enable_extraction:
					typer.secho(f'Warning: Could not initialize LLM for extraction: {e}', fg=typer.colors.YELLOW)
					typer.secho('Continuing with basic extraction fallback...', fg=typer.colors.YELLOW)

			workflow_obj = Workflow.load_from_file(
				str(workflow_path),
				browser=browser,
				llm=dummy_llm,  # Won't be used in run_with_no_ai for interactions
				page_extraction_llm=extraction_llm,  # Will be used for extraction steps if enabled
			)
		except Exception as e:
			typer.secho(f'Error loading workflow: {e}', fg=typer.colors.RED)
			raise typer.Exit(code=1)

		typer.secho('Workflow loaded successfully.', fg=typer.colors.GREEN, bold=True)
		if enable_extraction and extraction_llm:
			typer.secho('Using semantic abstraction mode with AI-powered extraction.', fg=typer.colors.BLUE, bold=True)
		else:
			typer.secho('Using semantic abstraction mode (no AI/LLM).', fg=typer.colors.BLUE, bold=True)

		inputs = {}
		input_definitions = workflow_obj.inputs_def  # Access inputs_def from the Workflow instance

		if input_definitions:  # Check if the list is not empty
			# Check if all REQUIRED inputs have defaults (can skip prompting)
			# Note: Optional inputs can be skipped, so we only check required ones
			required_inputs = [inp for inp in input_definitions if inp.required]
			all_required_have_defaults = all(getattr(input_def, 'default', None) is not None for input_def in required_inputs)

			if all_required_have_defaults:
				# All required inputs have defaults, use defaults automatically
				typer.echo()  # Add space
				typer.echo(typer.style('Using default values for workflow inputs:', bold=True))
				typer.echo()  # Add space

				for input_def in input_definitions:
					default_value = getattr(input_def, 'default', None)
					if default_value is not None:
						inputs[input_def.name] = default_value
						var_name_styled = typer.style(input_def.name, fg=typer.colors.CYAN, bold=True)
						typer.echo(f'  • {var_name_styled} = {typer.style(str(default_value), fg=typer.colors.BLUE)}')
					elif not input_def.required:
						var_name_styled = typer.style(input_def.name, fg=typer.colors.CYAN, bold=True)
						typer.echo(f'  • {var_name_styled} = {typer.style("(not provided, optional)", fg=typer.colors.YELLOW)}')
				typer.echo()
			else:
				# Some inputs need user input
				typer.echo()  # Add space
				typer.echo(typer.style('Provide values for the following workflow inputs:', bold=True))
				typer.echo()  # Add space

				for input_def in input_definitions:
					var_name_styled = typer.style(input_def.name, fg=typer.colors.CYAN, bold=True)
					prompt_question = typer.style(f'Enter value for {var_name_styled}', bold=True)

					var_type = input_def.type.lower()  # type is a direct attribute
					is_required = input_def.required
					default_value = getattr(input_def, 'default', None)

					type_info_str = f'type: {var_type}'
					if is_required:
						status_str = typer.style('required', fg=typer.colors.RED)
					else:
						status_str = typer.style('optional', fg=typer.colors.YELLOW)

					# Add format information if available
					format_info_str = ''
					if hasattr(input_def, 'format') and input_def.format:
						format_info_str = f', format: {typer.style(input_def.format, fg=typer.colors.GREEN)}'

					# Add default value information if available
					default_info_str = ''
					if default_value is not None:
						default_info_str = f', default: {typer.style(str(default_value), fg=typer.colors.BLUE)}'

					full_prompt_text = f'{prompt_question} ({status_str}, {type_info_str}{format_info_str}{default_info_str})'

					input_val = None
					if var_type == 'bool':
						input_val = typer.confirm(full_prompt_text, default=default_value if default_value is not None else None)
					elif var_type == 'number':
						input_val = typer.prompt(
							full_prompt_text, type=float, default=default_value if default_value is not None else ...
						)
					elif var_type == 'string':  # Default to string for other unknown types as well
						input_val = typer.prompt(
							full_prompt_text, type=str, default=default_value if default_value is not None else ...
						)
					else:  # Should ideally not happen if schema is validated, but good to have a fallback
						typer.secho(
							f"Warning: Unknown type '{var_type}' for variable '{input_def.name}'. Treating as string.",
							fg=typer.colors.YELLOW,
						)
						input_val = typer.prompt(
							full_prompt_text, type=str, default=default_value if default_value is not None else ...
						)

					inputs[input_def.name] = input_val
					typer.echo()  # Add space after each prompt
		else:
			typer.echo('No input schema found in the workflow, or no properties defined. Proceeding without inputs.')

		typer.echo()  # Add space
		typer.echo(typer.style('Running workflow with semantic abstraction (no AI)...', bold=True))

		try:
			# Call run_with_no_ai on the Workflow instance
			result = await workflow_obj.run_with_no_ai(inputs=inputs, close_browser_at_end=False)

			typer.secho('\nWorkflow execution completed!', fg=typer.colors.GREEN, bold=True)
			typer.echo(typer.style('Result:', bold=True))
			# Output the number of steps executed
			typer.echo(f'{typer.style(str(len(result.step_results)), bold=True)} steps executed using semantic abstraction.')

			# Display extraction results if any
			extraction_results = []
			for i, step_result in enumerate(result.step_results, 1):
				if hasattr(step_result, 'extracted_data') and step_result.extracted_data:
					extraction_results.append((i, step_result.extracted_data))

			if extraction_results:
				typer.echo()
				typer.secho('=== EXTRACTION RESULTS ===', fg=typer.colors.CYAN, bold=True)
				for step_num, extracted_data in extraction_results:
					typer.echo()
					typer.echo(f'{typer.style(f"Step {step_num} Extraction:", bold=True)}')
					typer.echo(f'  Goal: {typer.style(extracted_data.get("extraction_goal", "N/A"), fg=typer.colors.YELLOW)}')
					typer.echo(f'  URL: {extracted_data.get("page_url", "N/A")}')
					typer.echo(f'  Method: {extracted_data.get("extraction_method", "N/A")}')

					if 'extracted_content' in extracted_data:
						content = extracted_data['extracted_content']
						# Limit display length for readability
						if len(content) > 500:
							content = content[:500] + '... [truncated]'
						typer.echo('  Result:')
						# Indent the content for better readability
						for line in content.split('\n'):
							typer.echo(f'    {line}')
					elif 'error' in extracted_data:
						typer.secho(f'  Error: {extracted_data["error"]}', fg=typer.colors.RED)
				typer.echo()

		except Exception as e:
			typer.secho(f'Error running workflow: {e}', fg=typer.colors.RED)
			raise typer.Exit(code=1)

	return asyncio.run(_run_workflow_no_ai())


@app.command(name='generate-semantic-mapping', help='Generate semantic mapping for a URL to help with workflow creation.')
def generate_semantic_mapping_command(
	url: str = typer.Argument(..., help='URL to generate semantic mapping for'),
	output_file: Path = typer.Option(
		None,
		'--output',
		'-o',
		help='Output file to save the semantic mapping (optional)',
	),
):
	"""
	Generate a semantic mapping for a given URL to help with creating workflows.
	This shows how visible text maps to selectors.
	"""

	async def _generate_mapping():
		typer.echo(typer.style(f'Generating semantic mapping for: {url}', bold=True))
		typer.echo()

		try:
			from browser_use import Browser

			from workflow_use.workflow.semantic_extractor import SemanticExtractor

			browser = Browser()
			extractor = SemanticExtractor()

			await browser.start()
			page = await browser.get_current_page()
			await page.goto(url)
			await asyncio.sleep(2)  # Wait for page to load

			# Generate semantic mapping
			mapping = await extractor.extract_semantic_mapping(page)
			if mapping is None:
				mapping = {}

			typer.secho(f'Found {len(mapping)} interactive elements', fg=typer.colors.GREEN, bold=True)
			typer.echo()

			# Display mapping
			typer.echo(typer.style('=== SEMANTIC MAPPING ===', bold=True))
			typer.echo()

			for text, element_info in mapping.items():
				element_type = element_info['element_type']
				selector = element_info['selectors']
				class_name = element_info['class']
				element_id = element_info['id']

				# Color code by element type
				if element_type == 'button':
					text_color = typer.colors.GREEN
				elif element_type == 'input':
					text_color = typer.colors.BLUE
				elif element_type == 'select':
					text_color = typer.colors.MAGENTA
				else:
					text_color = typer.colors.CYAN

				typer.echo(f'{typer.style(text, fg=text_color, bold=True)}')
				typer.echo(f'  Type: {element_type}')
				typer.echo(f'  Class: {class_name or "(none)"}')
				typer.echo(f'  ID: {element_id or "(none)"}')
				typer.echo(f'  Selector: {selector}')
				typer.echo()

			# Save to file if requested
			if output_file:
				output_data = {}
				for text, element_info in mapping.items():
					output_data[text] = {
						'class': element_info['class'],
						'id': element_info['id'],
						'selectors': element_info['selectors'],
					}

				async with aiofiles.open(output_file, 'w') as f:
					import json

					await f.write(json.dumps(output_data, indent=2))

				typer.secho(f'Semantic mapping saved to: {output_file}', fg=typer.colors.GREEN)

			await browser.close()

		except Exception as e:
			typer.secho(f'Error generating semantic mapping: {e}', fg=typer.colors.RED)
			raise typer.Exit(code=1)

	return asyncio.run(_generate_mapping())


@app.command(name='create-semantic-workflow', help='Create a workflow template using semantic text mapping.')
def create_semantic_workflow_command(
	url: str = typer.Argument(..., help='URL to create workflow for'),
	output_file: Path = typer.Option(
		None,
		'--output',
		'-o',
		help='Output workflow file (defaults to semantic_workflow.json)',
	),
):
	"""
	Create a workflow template using semantic text mapping for a given URL.
	This generates a template that users can customize.
	"""

	async def _create_semantic_workflow():
		output_path = output_file or Path('semantic_workflow.json')

		typer.echo(typer.style(f'Creating semantic workflow for: {url}', bold=True))
		typer.echo()

		try:
			from browser_use import Browser

			from workflow_use.workflow.semantic_extractor import SemanticExtractor

			browser = Browser()
			extractor = SemanticExtractor()

			await browser.start()
			page = await browser.get_current_page()
			await page.goto(url)
			await asyncio.sleep(2)  # Wait for page to load

			# Generate semantic mapping
			mapping = await extractor.extract_semantic_mapping(page)
			if mapping is None:
				mapping = {}

			typer.secho(f'Found {len(mapping)} interactive elements', fg=typer.colors.GREEN, bold=True)
			typer.echo()

			# Show available elements
			typer.echo(typer.style('Available elements for workflow:', bold=True))
			for i, (text, element_info) in enumerate(mapping.items(), 1):
				element_type = element_info['element_type']

				# Color code by element type
				if element_type == 'button':
					text_color = typer.colors.GREEN
				elif element_type == 'input':
					text_color = typer.colors.BLUE
				elif element_type == 'select':
					text_color = typer.colors.MAGENTA
				else:
					text_color = typer.colors.CYAN

				typer.echo(f'{i:2}. {typer.style(text, fg=text_color)} ({element_type})')

			typer.echo()

			# Create basic workflow template
			workflow_name = typer.prompt('Enter workflow name', default='Semantic Workflow')
			workflow_description = typer.prompt(
				'Enter workflow description', default='Automated workflow using semantic text mapping'
			)

			# Create template workflow
			template = {
				'workflow_analysis': f'Semantic workflow for {url}. Uses visible text to identify elements instead of CSS selectors.',
				'name': workflow_name,
				'description': workflow_description,
				'version': '1.0',
				'steps': [{'description': f'Navigate to {url}', 'type': 'navigation', 'url': url}],
				'input_schema': [],
			}

			# Add some example steps as comments in the JSON
			example_steps = []
			for text, element_info in list(mapping.items())[:5]:  # Show first 5 elements as examples
				element_type = element_info['element_type']

				if element_type == 'button':
					example_steps.append(
						{
							'description': f'Click {text}',
							'type': 'click',
							'target_text': text,
							'_comment': "Remove this line - it's just an example",
						}
					)
				elif element_type == 'input':
					example_steps.append(
						{
							'description': f'Enter value into {text}',
							'type': 'input',
							'target_text': text,
							'value': '{variable_name}',
							'_comment': "Remove this line - it's just an example. Replace {variable_name} with actual variable.",
						}
					)

			template['example_steps_to_customize'] = example_steps

			# Save template
			async with aiofiles.open(output_path, 'w') as f:
				import json

				await f.write(json.dumps(template, indent=2))

			typer.secho(f'Workflow template created: {output_path}', fg=typer.colors.GREEN, bold=True)
			typer.echo()
			typer.echo(typer.style('Next steps:', bold=True))
			typer.echo('1. Edit the workflow file to add your specific steps')
			typer.echo('2. Use target_text field to reference visible text')
			typer.echo('3. Add input_schema for dynamic values')
			typer.echo('4. Test with: python cli.py run-workflow-no-ai your_workflow.json')

			await browser.close()

		except Exception as e:
			typer.secho(f'Error creating semantic workflow: {e}', fg=typer.colors.RED)
			raise typer.Exit(code=1)

	return asyncio.run(_create_semantic_workflow())


@app.command(name='run-workflow-csv', help='Runs a workflow multiple times using input values from a CSV file.')
def run_workflow_csv_command(
	workflow_path: Path = typer.Argument(
		...,
		exists=True,
		file_okay=True,
		dir_okay=False,
		readable=True,
		help='Path to the .workflow.json file.',
		show_default=False,
	),
	csv_path: Path = typer.Argument(
		...,
		exists=True,
		file_okay=True,
		dir_okay=False,
		readable=True,
		help='Path to the CSV file containing input values.',
		show_default=False,
	),
	use_ai: bool = typer.Option(
		False,
		'--use-ai',
		'-a',
		help='Use AI-powered execution instead of semantic abstraction (requires OpenAI API key)',
	),
	max_parallel: int = typer.Option(
		1,
		'--max-parallel',
		'-p',
		help='Maximum number of parallel workflow executions (default: 1 for sequential execution)',
		min=1,
		max=5,
	),
	use_cloud: bool = typer.Option(False, help='Use Browser-Use Cloud browser'),
	output_file: Path = typer.Option(
		None,
		'--output',
		'-o',
		help='Output file to save execution results (CSV format)',
	),
	start_row: int = typer.Option(
		1,
		'--start-row',
		'-s',
		help='Row number to start execution from (1-indexed, excluding header)',
		min=1,
	),
	end_row: int = typer.Option(
		None,
		'--end-row',
		'-e',
		help='Row number to end execution at (1-indexed, excluding header). If not specified, runs all rows.',
		min=1,
	),
):
	"""
	Executes a workflow multiple times using input values from a CSV file.
	Each row in the CSV represents one execution with different input values.
	CSV column headers should match the workflow input parameter names.
	"""

	async def _run_workflow_csv():
		from datetime import datetime

		import pandas as pd

		typer.echo(
			typer.style(f'Loading workflow from: {typer.style(str(workflow_path.resolve()), fg=typer.colors.MAGENTA)}', bold=True)
		)
		typer.echo(
			typer.style(f'Loading CSV data from: {typer.style(str(csv_path.resolve()), fg=typer.colors.MAGENTA)}', bold=True)
		)
		typer.echo()

		# Load and validate CSV data
		try:
			df = pd.read_csv(csv_path)
			if df.empty:
				typer.secho('Error: CSV file is empty.', fg=typer.colors.RED)
				raise typer.Exit(code=1)

			typer.secho(f'Loaded CSV with {len(df)} rows and {len(df.columns)} columns.', fg=typer.colors.GREEN)
			typer.echo(f'Columns: {", ".join(df.columns.tolist())}')
			typer.echo()

		except Exception as e:
			typer.secho(f'Error loading CSV file: {e}', fg=typer.colors.RED)
			raise typer.Exit(code=1)

		# Apply row filtering
		original_row_count = len(df)
		start_idx = start_row - 1  # Convert to 0-indexed
		end_idx = end_row if end_row is None else end_row

		if start_idx >= len(df):
			typer.secho(
				f'Error: Start row {start_row} is beyond the CSV data (only {len(df)} rows available).', fg=typer.colors.RED
			)
			raise typer.Exit(code=1)

		if end_idx is not None:
			if end_idx <= start_idx:
				typer.secho(f'Error: End row ({end_row}) must be greater than start row ({start_row}).', fg=typer.colors.RED)
				raise typer.Exit(code=1)
			df = df.iloc[start_idx:end_idx]
		else:
			df = df.iloc[start_idx:]

		typer.echo(f'Processing rows {start_row} to {start_row + len(df) - 1} ({len(df)} total executions)')
		typer.echo()

		# Load workflow
		try:
			browser = Browser(use_cloud=use_cloud)

			dummy_llm = None
			if use_ai and llm_instance:
				dummy_llm = llm_instance
			elif use_ai:
				typer.secho(
					'Warning: AI execution requested but no LLM available. Falling back to semantic mode.', fg=typer.colors.YELLOW
				)

			workflow_obj = Workflow.load_from_file(
				str(workflow_path),
				browser=browser,
				llm=dummy_llm,
			)
		except Exception as e:
			typer.secho(f'Error loading workflow: {e}', fg=typer.colors.RED)
			raise typer.Exit(code=1)

		typer.secho('Workflow loaded successfully.', fg=typer.colors.GREEN, bold=True)

		# Validate CSV columns against workflow input schema
		input_definitions = workflow_obj.inputs_def
		required_columns = set()
		optional_columns = set()

		for input_def in input_definitions:
			if input_def.required:
				required_columns.add(input_def.name)
			else:
				optional_columns.add(input_def.name)

		csv_columns = set(df.columns.tolist())
		missing_required = required_columns - csv_columns
		extra_columns = csv_columns - required_columns - optional_columns

		if missing_required:
			typer.secho(f'Error: Missing required columns in CSV: {", ".join(missing_required)}', fg=typer.colors.RED)
			typer.echo(f'Required columns: {", ".join(required_columns)}')
			typer.echo(f'Optional columns: {", ".join(optional_columns)}')
			raise typer.Exit(code=1)

		if extra_columns:
			typer.echo(f'Note: Extra columns in CSV will be ignored: {", ".join(extra_columns)}')

		execution_mode = 'AI-powered' if use_ai and dummy_llm else 'semantic abstraction (no AI)'
		typer.secho(f'Using {execution_mode} execution mode.', fg=typer.colors.BLUE, bold=True)
		typer.echo()

		# Prepare results tracking
		results = []
		start_time = datetime.now()

		# Execute workflows
		if max_parallel == 1:
			# Sequential execution
			typer.echo(typer.style('Starting sequential execution...', bold=True))
			for idx, row in df.iterrows():
				typer.echo(f'\n--- Execution {idx + 1 - start_idx} of {len(df)} ---')
				result = await _execute_single_workflow(workflow_obj, row, idx + 1, use_ai and dummy_llm)
				results.append(result)

				# Check if we should stop execution due to critical failures
				if result['failure_type'] in ['global_failure_limit', 'consecutive_failures']:
					typer.echo()
					typer.secho(
						'🛑 STOPPING EXECUTION: Critical workflow failure detected.', fg=typer.colors.BRIGHT_RED, bold=True
					)
					typer.echo(f'Reason: {result["error"]}')
					typer.echo(f'Completed {len(results)} out of {len(df)} planned executions.')
					break
		else:
			# Parallel execution (simplified for now)
			typer.echo(typer.style(f'Starting parallel execution (max {max_parallel} concurrent)...', bold=True))
			typer.echo('Note: Parallel execution is experimental and may cause browser conflicts.')

			# For now, implement as batched sequential to avoid browser conflicts
			batch_size = max_parallel
			for i in range(0, len(df), batch_size):
				batch = df.iloc[i : i + batch_size]
				typer.echo(
					f'\n--- Batch {i // batch_size + 1}: Processing rows {i + start_row} to {min(i + batch_size - 1 + start_row, start_row + len(df) - 1)} ---'
				)

				for idx, row in batch.iterrows():
					typer.echo(f'\nExecution {idx + 1 - start_idx} of {len(df)}')
					result = await _execute_single_workflow(workflow_obj, row, idx + 1, use_ai and dummy_llm)
					results.append(result)

		# Summary
		end_time = datetime.now()
		duration = end_time - start_time

		successful = sum(1 for r in results if r['status'] == 'success')
		failed = len(results) - successful

		# Categorize failures
		failure_types = {}
		for result in results:
			if result['status'] == 'failed':
				failure_type = result.get('failure_type', 'other')
				if failure_type not in failure_types:
					failure_types[failure_type] = []
				failure_types[failure_type].append(result)

		typer.echo('\n' + '=' * 60)
		typer.secho('EXECUTION SUMMARY', fg=typer.colors.CYAN, bold=True)
		typer.echo('=' * 60)
		typer.echo(f'Total executions: {len(results)}')
		typer.echo(f'Successful: {typer.style(str(successful), fg=typer.colors.GREEN, bold=True)}')
		if failed > 0:
			typer.echo(f'Failed: {typer.style(str(failed), fg=typer.colors.RED, bold=True)}')
		typer.echo(f'Duration: {duration}')
		typer.echo(f'Average per execution: {duration / len(results) if results else "N/A"}')

		if failed > 0:
			typer.echo('\n' + '-' * 40)
			typer.secho('FAILURE ANALYSIS', fg=typer.colors.YELLOW, bold=True)
			typer.echo('-' * 40)

			# Show failure type breakdown
			for failure_type, failed_results in failure_types.items():
				count = len(failed_results)
				if failure_type == 'global_failure_limit':
					typer.secho(f'  🛑 Global failure limit: {count} (workflow overwhelmed)', fg=typer.colors.BRIGHT_RED)
				elif failure_type == 'consecutive_failures':
					typer.secho(f'  🚫 Consecutive failures: {count} (systematic issues)', fg=typer.colors.BRIGHT_RED)
				elif failure_type == 'element_not_found':
					typer.secho(f'  🔍 Element not found: {count} (form structure changed)', fg=typer.colors.RED)
				elif failure_type == 'form_validation':
					typer.secho(f'  📝 Form validation: {count} (invalid input data)', fg=typer.colors.YELLOW)
				else:
					typer.secho(f'  ❓ Other failures: {count}', fg=typer.colors.RED)

			# Provide actionable recommendations
			typer.echo('\n' + '-' * 40)
			typer.secho('RECOMMENDATIONS', fg=typer.colors.CYAN, bold=True)
			typer.echo('-' * 40)
			if 'global_failure_limit' in failure_types or 'consecutive_failures' in failure_types:
				typer.secho('  • Check if the form structure has changed significantly', fg=typer.colors.CYAN)
				typer.secho('  • Verify workflow file is compatible with current form version', fg=typer.colors.CYAN)
				typer.secho('  • Consider re-recording the workflow if layout changed drastically', fg=typer.colors.CYAN)
			if 'element_not_found' in failure_types:
				typer.secho('  • Update element selectors in workflow file', fg=typer.colors.CYAN)
				typer.secho('  • Re-record workflow if form layout changed', fg=typer.colors.CYAN)
			if 'form_validation' in failure_types:
				typer.secho(
					'  • Check CSV data for invalid values (missing required fields, wrong formats)', fg=typer.colors.CYAN
				)
				typer.secho('  • Verify data types match form expectations', fg=typer.colors.CYAN)
				typer.secho('  • Check for proper validation rules in the target form', fg=typer.colors.CYAN)

		# Save results if requested
		if output_file:
			try:
				results_df = pd.DataFrame(results)
				results_df.to_csv(output_file, index=False)
				typer.secho(f'\nResults saved to: {output_file}', fg=typer.colors.GREEN, bold=True)
			except Exception as e:
				typer.secho(f'Error saving results: {e}', fg=typer.colors.RED)

		if failed > 0:
			raise typer.Exit(code=1)

	async def _execute_single_workflow(workflow_obj, row_data, row_number, use_ai_mode):
		"""Execute a single workflow with the given row data."""
		from datetime import datetime

		start_time = datetime.now()

		# Convert row data to inputs dictionary
		inputs = {}
		for input_def in workflow_obj.inputs_def:
			column_name = input_def.name
			if column_name in row_data:
				raw_value = row_data[column_name]

				# Handle NaN values
				if pd.isna(raw_value):
					if input_def.required:
						typer.secho(f'  Error: Required field "{column_name}" is empty in row {row_number}', fg=typer.colors.RED)
						return {
							'row_number': row_number,
							'status': 'failed',
							'error': f'Required field "{column_name}" is empty',
							'duration': 0,
							'steps_executed': 0,
							**dict(row_data),
						}
					else:
						continue  # Skip optional empty fields

				# Type conversion
				try:
					if input_def.type.lower() == 'bool':
						inputs[column_name] = str(raw_value).lower() in ['true', '1', 'yes', 'on']
					elif input_def.type.lower() == 'number':
						inputs[column_name] = float(raw_value)
					else:  # string or default
						inputs[column_name] = str(raw_value)
				except (ValueError, TypeError) as e:
					typer.secho(
						f'  Error: Cannot convert "{raw_value}" to {input_def.type} for field "{column_name}"',
						fg=typer.colors.RED,
					)
					return {
						'row_number': row_number,
						'status': 'failed',
						'error': f'Type conversion error for field "{column_name}": {e}',
						'duration': 0,
						'steps_executed': 0,
						**dict(row_data),
					}

		typer.echo(f'  Inputs: {inputs}')

		# Execute workflow
		try:
			if use_ai_mode:
				result = await workflow_obj.run(inputs=inputs, close_browser_at_end=False)
			else:
				result = await workflow_obj.run_with_no_ai(inputs=inputs, close_browser_at_end=False)

			end_time = datetime.now()
			duration = end_time - start_time

			typer.secho(f'  ✅ Success: {len(result.step_results)} steps executed in {duration}', fg=typer.colors.GREEN)

			return {
				'row_number': row_number,
				'status': 'success',
				'error': None,
				'duration': str(duration),
				'steps_executed': len(result.step_results),
				'failure_type': None,
				**dict(row_data),
			}

		except Exception as e:
			end_time = datetime.now()
			duration = end_time - start_time

			# Categorize the error type for better reporting
			error_str = str(e).lower()
			if 'global failure limit' in error_str:
				failure_type = 'global_failure_limit'
				typer.secho(f'  🛑 CRITICAL: {str(e)[:100]}{"..." if len(str(e)) > 100 else ""}', fg=typer.colors.BRIGHT_RED)
			elif 'consecutive verification failures' in error_str:
				failure_type = 'verification_failures'
				typer.secho(f'  🔄 VERIFICATION: {str(e)[:100]}{"..." if len(str(e)) > 100 else ""}', fg=typer.colors.BRIGHT_RED)
			elif 'consecutive failures' in error_str:
				failure_type = 'consecutive_failures'
				typer.secho(f'  🚫 SYSTEMATIC: {str(e)[:100]}{"..." if len(str(e)) > 100 else ""}', fg=typer.colors.BRIGHT_RED)
			elif any(pattern in error_str for pattern in ['element not found', 'timeout', 'selector failed']):
				failure_type = 'element_not_found'
				typer.secho(f'  🔍 ELEMENT: {str(e)[:100]}{"..." if len(str(e)) > 100 else ""}', fg=typer.colors.RED)
			elif 'validation' in error_str:
				failure_type = 'form_validation'
				typer.secho(f'  📝 VALIDATION: {str(e)[:100]}{"..." if len(str(e)) > 100 else ""}', fg=typer.colors.YELLOW)
			else:
				failure_type = 'other'
				typer.secho(f'  ❌ Failed: {str(e)[:100]}{"..." if len(str(e)) > 100 else ""}', fg=typer.colors.RED)

			return {
				'row_number': row_number,
				'status': 'failed',
				'error': str(e),
				'duration': str(duration),
				'steps_executed': 0,
				'failure_type': failure_type,
				**dict(row_data),
			}

	return asyncio.run(_run_workflow_csv())


@app.command(name='mcp-server', help='Starts the MCP server which expose all the created workflows as tools.')
def mcp_server_command(
	port: int = typer.Option(
		8008,
		'--port',
		'-p',
		help='Port to run the MCP server on.',
	),
):
	"""
	Starts the MCP server which expose all the created workflows as tools.
	"""
	typer.echo(typer.style('Starting MCP server...', bold=True))
	typer.echo()  # Add space

	llm_instance = ChatBrowserUse(model='bu-latest')
	page_extraction_llm = ChatBrowserUse(model='bu-latest')

	mcp = get_mcp_server(llm_instance, page_extraction_llm=page_extraction_llm, workflow_dir='./tmp')

	mcp.run(
		transport='sse',
		host='0.0.0.0',
		port=port,
	)


@app.command('launch-gui', help='Launch the workflow visualizer GUI.')
def launch_gui():
	"""Launch the workflow visualizer GUI."""
	typer.echo(typer.style('Launching workflow visualizer GUI...', bold=True))

	logs_dir = Path('./tmp/logs')
	logs_dir.mkdir(parents=True, exist_ok=True)
	backend_log = open(logs_dir / 'backend.log', 'w')
	frontend_log = open(logs_dir / 'frontend.log', 'w')

	backend = subprocess.Popen(['uvicorn', 'backend.api:app', '--reload'], stdout=backend_log, stderr=subprocess.STDOUT)
	typer.echo(typer.style('Starting frontend...', bold=True))
	frontend = subprocess.Popen(['npm', 'run', 'dev'], cwd='../ui', stdout=frontend_log, stderr=subprocess.STDOUT)
	typer.echo(typer.style('Opening browser...', bold=True))
	webbrowser.open('http://localhost:5173')
	try:
		typer.echo(typer.style('Press Ctrl+C to stop the GUI and servers.', fg=typer.colors.YELLOW, bold=True))
		backend.wait()
		frontend.wait()
	except KeyboardInterrupt:
		typer.echo(typer.style('\nShutting down servers...', fg=typer.colors.RED, bold=True))
		backend.terminate()
		frontend.terminate()


@app.command(name='generate-csv-template', help='Generate a CSV template file for a workflow to help with bulk execution.')
def generate_csv_template_command(
	workflow_path: Path = typer.Argument(
		...,
		exists=True,
		file_okay=True,
		dir_okay=False,
		readable=True,
		help='Path to the .workflow.json file.',
		show_default=False,
	),
	output_file: Path = typer.Option(
		None,
		'--output',
		'-o',
		help='Output CSV template file path (defaults to workflow_name_template.csv)',
	),
	num_examples: int = typer.Option(
		3,
		'--examples',
		'-n',
		help='Number of example rows to include in the template',
		min=1,
		max=10,
	),
):
	"""
	Generate a CSV template file for a workflow based on its input schema.
	This helps users understand the required CSV format for bulk execution.
	"""

	typer.echo(
		typer.style(f'Loading workflow from: {typer.style(str(workflow_path.resolve()), fg=typer.colors.MAGENTA)}', bold=True)
	)

	try:
		# Load workflow to get input schema
		with open(workflow_path, 'r') as f:
			workflow_data = json.load(f)

		workflow_name = workflow_data.get('name', 'workflow')
		input_schema = workflow_data.get('input_schema', [])

		if not input_schema:
			typer.secho('Warning: Workflow has no input schema defined. Creating a basic template.', fg=typer.colors.YELLOW)
			# Create a basic template anyway
			template_data = {'example_field': [f'example_value_{i + 1}' for i in range(num_examples)]}
		else:
			# Create template based on input schema
			template_data = {}

			for input_def in input_schema:
				column_name = input_def['name']
				field_type = input_def.get('type', 'string').lower()
				is_required = input_def.get('required', False)
				field_format = input_def.get('format', '')

				# Generate example values based on type and format
				example_values = []
				for i in range(num_examples):
					if field_type == 'bool':
						example_values.append(True if i % 2 == 0 else False)
					elif field_type == 'number':
						example_values.append(round(10.5 + i * 2.3, 2))
					else:  # string
						if 'email' in field_format.lower() or 'email' in column_name.lower():
							example_values.append(f'user{i + 1}@example.com')
						elif 'name' in column_name.lower():
							names = ['John Doe', 'Jane Smith', 'Bob Johnson']
							example_values.append(names[i % len(names)])
						elif 'phone' in column_name.lower():
							example_values.append(f'+1-555-000-{1000 + i}')
						elif 'url' in column_name.lower() or 'website' in column_name.lower():
							example_values.append(f'https://example{i + 1}.com')
						else:
							example_values.append(f'{column_name}_value_{i + 1}')

				template_data[column_name] = example_values

		# Create DataFrame and save as CSV
		template_df = pd.DataFrame(template_data)

		# Determine output file path
		if output_file is None:
			safe_name = workflow_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
			output_file = workflow_path.parent / f'{safe_name}_template.csv'

		template_df.to_csv(output_file, index=False)

		typer.secho('CSV template generated successfully!', fg=typer.colors.GREEN, bold=True)
		typer.echo(f'Template saved to: {typer.style(str(output_file.resolve()), fg=typer.colors.CYAN)}')
		typer.echo()

		# Display template info
		typer.echo(typer.style('Template columns:', bold=True))
		for input_def in input_schema:
			column_name = input_def['name']
			field_type = input_def.get('type', 'string')
			is_required = input_def.get('required', False)
			status = (
				typer.style('required', fg=typer.colors.RED) if is_required else typer.style('optional', fg=typer.colors.YELLOW)
			)
			typer.echo(f'  • {typer.style(column_name, fg=typer.colors.CYAN)} ({field_type}, {status})')

		typer.echo()
		typer.echo(typer.style('Usage:', bold=True))
		typer.echo(f'1. Edit the CSV file: {output_file}')
		typer.echo('2. Add your data rows (replace the example values)')
		typer.echo(f'3. Run: python cli.py run-workflow-csv {workflow_path} {output_file}')

	except Exception as e:
		typer.secho(f'Error generating CSV template: {e}', fg=typer.colors.RED)
		raise typer.Exit(code=1)


# ==================== GENERATION MODE COMMANDS ====================


@app.command(name='generate-workflow')
def generate_workflow_from_task(
	task: str = typer.Argument(..., help='The task to automate (e.g., "Fill out the contact form")'),
	agent_model: str = typer.Option('gpt-4.1-mini', help='Model for browser automation'),
	extraction_model: str = typer.Option('gpt-4.1-mini', help='Model for page extraction'),
	workflow_model: str = typer.Option('gpt-4.1', help='Model for workflow generation'),
	save_to_storage: bool = typer.Option(True, help='Save workflow to storage database'),
	output_file: Path | None = typer.Option(None, help='Optional: Save to specific file path'),
	use_cloud: bool = typer.Option(False, help='Use Browser-Use Cloud browser'),
):
	"""
	🤖 GENERATION MODE: Generate a semantic workflow from a task description.

	This command:
	1. Runs browser-use to complete the task
	2. Generates a semantic workflow from the execution
	3. Saves it to the storage database

	Example:
	  python cli.py generate-workflow "Fill out the contact form on example.com"
	"""
	if not healing_service:
		typer.secho('Error: HealingService not initialized. Cannot generate workflow.', fg=typer.colors.RED)
		raise typer.Exit(code=1)

	typer.echo()
	typer.secho('🤖 GENERATION MODE: Creating workflow from task', fg=typer.colors.CYAN, bold=True)
	typer.echo(f'Task: {typer.style(task, fg=typer.colors.YELLOW)}')
	typer.echo()

	# Initialize LLMs
	agent_llm = ChatBrowserUse(model='bu-latest')
	extraction_llm = ChatBrowserUse(model='bu-latest')

	typer.echo('Starting browser automation to complete the task...')
	typer.echo(f'  Agent Model: {agent_model}')
	typer.echo(f'  Extraction Model: {extraction_model}')
	typer.echo(f'  Workflow Model: {workflow_model}')
	typer.echo(f'  Browser: {"☁️  Cloud" if use_cloud else "🖥️  Local"}')
	typer.echo()

	try:
		# Generate workflow from task
		workflow_definition = asyncio.run(
			healing_service.generate_workflow_from_prompt(
				prompt=task, agent_llm=agent_llm, extraction_llm=extraction_llm, use_cloud=use_cloud
			)
		)

		if not workflow_definition:
			typer.secho('Failed to generate workflow from task.', fg=typer.colors.RED)
			raise typer.Exit(code=1)

		typer.secho('✅ Workflow generated successfully!', fg=typer.colors.GREEN, bold=True)
		typer.echo()

		# Display workflow info
		typer.echo(typer.style('Workflow Details:', bold=True))
		typer.echo(f'  Name: {typer.style(workflow_definition.name, fg=typer.colors.CYAN)}')
		typer.echo(f'  Description: {workflow_definition.description}')
		typer.echo(f'  Steps: {len(workflow_definition.steps)}')
		typer.echo(f'  Input Parameters: {len(workflow_definition.input_schema)}')
		typer.echo()

		# Save to storage database
		if save_to_storage:
			metadata = storage_service.save_workflow(
				workflow=workflow_definition, generation_mode='browser_use', original_task=task
			)
			typer.secho(f'💾 Saved to storage database with ID: {metadata.id}', fg=typer.colors.GREEN)
			typer.echo(f'   Storage path: {metadata.file_path}')
			typer.echo()

		# Save to output file if specified
		if output_file:
			with open(output_file, 'w') as f:
				json.dump(workflow_definition.model_dump(mode='json'), f, indent=2)
			typer.secho(f'💾 Also saved to: {output_file}', fg=typer.colors.GREEN)
			typer.echo()

		# Display next steps
		typer.echo(typer.style('Next Steps:', bold=True))
		typer.echo('  1. List workflows: python cli.py list-workflows')
		if save_to_storage:
			typer.echo(
				f'  2. Run workflow: python cli.py run-stored-workflow {metadata.id if save_to_storage else "<workflow-id>"}'
			)
		typer.echo('  3. Run as tool: python cli.py run-as-tool <workflow-file> --prompt "Your task"')

	except Exception as e:
		typer.secho(f'Error generating workflow: {e}', fg=typer.colors.RED)
		import traceback

		typer.echo('\nFull error traceback:')
		typer.echo(traceback.format_exc())
		raise typer.Exit(code=1)


@app.command(name='list-workflows')
def list_workflows(
	generation_mode: str | None = typer.Option(None, help='Filter by generation mode (manual/browser_use)'),
	query: str | None = typer.Option(None, help='Search query for name or description'),
):
	"""
	📋 List all stored workflows.

	Examples:
	  python cli.py list-workflows
	  python cli.py list-workflows --generation-mode browser_use
	  python cli.py list-workflows --query "contact form"
	"""
	workflows = storage_service.search_workflows(query=query, generation_mode=generation_mode)

	if not workflows:
		typer.secho('No workflows found.', fg=typer.colors.YELLOW)
		return

	typer.echo()
	typer.secho(f'Found {len(workflows)} workflow(s):', fg=typer.colors.CYAN, bold=True)
	typer.echo()

	for wf in workflows:
		mode_color = typer.colors.GREEN if wf.generation_mode == 'browser_use' else typer.colors.BLUE
		mode_icon = '🤖' if wf.generation_mode == 'browser_use' else '✋'

		typer.echo(f'{mode_icon} {typer.style(wf.name, fg=typer.colors.CYAN, bold=True)}')
		typer.echo(f'   ID: {wf.id}')
		typer.echo(f'   Description: {wf.description}')
		typer.echo(f'   Mode: {typer.style(wf.generation_mode, fg=mode_color)}')
		typer.echo(f'   Created: {wf.created_at}')
		if wf.original_task:
			typer.echo(f'   Original Task: {wf.original_task}')
		typer.echo()


@app.command(name='run-stored-workflow')
def run_stored_workflow(
	workflow_id: str = typer.Argument(..., help='Workflow ID from storage'),
	prompt: str | None = typer.Option(None, help='Run as tool with this prompt'),
	use_cloud: bool = typer.Option(False, help='Use Browser-Use Cloud browser'),
):
	"""
	▶️  Run a workflow from storage.

	Examples:
	  python cli.py run-stored-workflow <workflow-id>
	  python cli.py run-stored-workflow <workflow-id> --prompt "Fill with test data"
	"""
	if not llm_instance:
		typer.secho('Error: LLM not initialized.', fg=typer.colors.RED)
		raise typer.Exit(code=1)

	# Load workflow from storage
	workflow_definition = storage_service.get_workflow(workflow_id)

	if not workflow_definition:
		typer.secho(f'Workflow not found: {workflow_id}', fg=typer.colors.RED)
		raise typer.Exit(code=1)

	metadata = storage_service.metadata.get(workflow_id)

	typer.echo()
	typer.secho(f'▶️  Running workflow: {workflow_definition.name}', fg=typer.colors.CYAN, bold=True)
	if metadata and metadata.original_task:
		typer.echo(f'Original Task: {metadata.original_task}')
	typer.echo()

	# Save to temp file and run
	temp_file = Path('./tmp') / f'temp_workflow_{workflow_id}.json'
	temp_file.parent.mkdir(parents=True, exist_ok=True)

	with open(temp_file, 'w') as f:
		json.dump(workflow_definition.model_dump(mode='json'), f, indent=2)

	try:
		if prompt:
			# Run as tool with prompt
			workflow = Workflow.load_from_file(
				temp_file, llm_instance, page_extraction_llm=page_extraction_llm, use_cloud=use_cloud
			)
			result = asyncio.run(workflow.run_as_tool(prompt))

			typer.secho('✅ Workflow completed!', fg=typer.colors.GREEN, bold=True)
			typer.echo()
			typer.echo('Result:')
			typer.echo(json.dumps(result, indent=2))
		elif not workflow_definition.input_schema:
			# No inputs needed, run directly
			typer.secho('▶️  Running workflow (no inputs required)...', fg=typer.colors.CYAN)
			workflow = Workflow.load_from_file(
				temp_file, llm_instance, page_extraction_llm=page_extraction_llm, use_cloud=use_cloud
			)
			result = asyncio.run(workflow.run(inputs={}))

			typer.secho('✅ Workflow completed!', fg=typer.colors.GREEN, bold=True)
			typer.echo()
			if result:
				typer.echo('Result:')
				# Extract the actual data from step results
				if hasattr(result, 'step_results'):
					for i, step_result in enumerate(result.step_results, 1):
						if hasattr(step_result, 'extracted_content') and step_result.extracted_content:
							typer.echo(f'Step {i}: {step_result.extracted_content}')
				else:
					typer.echo(str(result))
		else:
			# Check if all REQUIRED inputs have defaults (can run without user input)
			# Note: Optional inputs can be skipped, so we only check required ones
			required_inputs = [inp for inp in workflow_definition.input_schema if inp.required]
			all_required_have_defaults = all(getattr(inp, 'default', None) is not None for inp in required_inputs)

			if all_required_have_defaults:
				# All required inputs have defaults, run with defaults
				typer.secho('▶️  Running workflow with default values...', fg=typer.colors.CYAN)
				typer.echo()
				typer.echo('Using default values:')
				for inp in workflow_definition.input_schema:
					default_value = getattr(inp, 'default', None)
					if default_value is not None:
						typer.echo(f'  • {inp.name} = {typer.style(str(default_value), fg=typer.colors.BLUE)}')
					elif not inp.required:
						typer.echo(f'  • {inp.name} = {typer.style("(not provided, optional)", fg=typer.colors.YELLOW)}')
				typer.echo()

				# Build inputs dict with defaults (only include values that have defaults)
				inputs = {}
				for inp in workflow_definition.input_schema:
					default_value = getattr(inp, 'default', None)
					if default_value is not None:
						inputs[inp.name] = default_value
					# Optional parameters without defaults are simply not included

				workflow = Workflow.load_from_file(
					temp_file, llm_instance, page_extraction_llm=page_extraction_llm, use_cloud=use_cloud
				)
				result = asyncio.run(workflow.run(inputs=inputs))

				typer.secho('✅ Workflow completed!', fg=typer.colors.GREEN, bold=True)
				typer.echo()
				if result:
					typer.echo('Result:')
					# Extract the actual data from step results
					if hasattr(result, 'step_results'):
						for i, step_result in enumerate(result.step_results, 1):
							if hasattr(step_result, 'extracted_content') and step_result.extracted_content:
								typer.echo(f'Step {i}: {step_result.extracted_content}')
					else:
						typer.echo(str(result))
			else:
				# Has required inputs without defaults - need to collect them
				typer.secho('This workflow requires input parameters:', fg=typer.colors.YELLOW)
				typer.echo()
				for inp in workflow_definition.input_schema:
					required = (
						typer.style('required', fg=typer.colors.RED)
						if inp.required
						else typer.style('optional', fg=typer.colors.YELLOW)
					)
					default_value = getattr(inp, 'default', None)
					default_str = (
						f', default: {typer.style(str(default_value), fg=typer.colors.BLUE)}' if default_value is not None else ''
					)
					typer.echo(f'  • {inp.name} ({inp.type}, {required}{default_str})')
				typer.echo()
				typer.echo('Options:')
				typer.echo(f'  1. Run as tool: python cli.py run-stored-workflow {workflow_id} --prompt "Your task"')
				typer.echo(f'  2. Run with inputs: python cli.py run-workflow {metadata.file_path if metadata else temp_file}')

	finally:
		# Cleanup temp file
		if temp_file.exists():
			temp_file.unlink()


@app.command(name='delete-workflow')
def delete_workflow(
	workflow_id: str = typer.Argument(..., help='Workflow ID to delete'),
	confirm: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
):
	"""
	🗑️  Delete a workflow from storage.

	Example:
	  python cli.py delete-workflow <workflow-id>
	"""
	workflow = storage_service.get_workflow(workflow_id)

	if not workflow:
		typer.secho(f'Workflow not found: {workflow_id}', fg=typer.colors.RED)
		raise typer.Exit(code=1)

	if not confirm:
		typer.echo(f'Delete workflow: {typer.style(workflow.name, fg=typer.colors.YELLOW)}?')
		confirm = typer.confirm('Are you sure?')

	if confirm:
		storage_service.delete_workflow(workflow_id)
		typer.secho(f'✅ Deleted workflow: {workflow.name}', fg=typer.colors.GREEN)
	else:
		typer.echo('Cancelled.')


@app.command(name='workflow-info')
def workflow_info(
	workflow_id: str = typer.Argument(..., help='Workflow ID'),
):
	"""
	ℹ️  Show detailed information about a workflow.

	Example:
	  python cli.py workflow-info <workflow-id>
	"""
	workflow = storage_service.get_workflow(workflow_id)
	metadata = storage_service.metadata.get(workflow_id)

	if not workflow or not metadata:
		typer.secho(f'Workflow not found: {workflow_id}', fg=typer.colors.RED)
		raise typer.Exit(code=1)

	mode_color = typer.colors.GREEN if metadata.generation_mode == 'browser_use' else typer.colors.BLUE
	mode_icon = '🤖' if metadata.generation_mode == 'browser_use' else '✋'

	typer.echo()
	typer.secho(f'{mode_icon} Workflow: {workflow.name}', fg=typer.colors.CYAN, bold=True)
	typer.echo()

	typer.echo(typer.style('Metadata:', bold=True))
	typer.echo(f'  ID: {metadata.id}')
	typer.echo(f'  Description: {metadata.description}')
	typer.echo(f'  Version: {metadata.version}')
	typer.echo(f'  Generation Mode: {typer.style(metadata.generation_mode, fg=mode_color)}')
	typer.echo(f'  Created: {metadata.created_at}')
	typer.echo(f'  Updated: {metadata.updated_at}')
	typer.echo(f'  File Path: {metadata.file_path}')
	if metadata.original_task:
		typer.echo(f'  Original Task: {metadata.original_task}')
	typer.echo()

	typer.echo(typer.style('Workflow Details:', bold=True))
	typer.echo(f'  Steps: {len(workflow.steps)}')
	typer.echo(f'  Input Parameters: {len(workflow.input_schema)}')
	typer.echo()

	if workflow.input_schema:
		typer.echo(typer.style('Input Schema:', bold=True))
		for inp in workflow.input_schema:
			required = (
				typer.style('required', fg=typer.colors.RED) if inp.required else typer.style('optional', fg=typer.colors.YELLOW)
			)
			typer.echo(f'  • {typer.style(inp.name, fg=typer.colors.CYAN)} ({inp.type}, {required})')
		typer.echo()

	typer.echo(typer.style('Steps:', bold=True))
	for i, step in enumerate(workflow.steps, 1):
		typer.echo(f'  {i}. [{step.type}] {step.description}')
	typer.echo()


if __name__ == '__main__':
	app()
