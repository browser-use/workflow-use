import asyncio
import json
import os
import subprocess
import tempfile  # For temporary file handling
import webbrowser
from pathlib import Path

import typer
from browser_use import Browser

# Assuming OPENAI_API_KEY is set in the environment
from langchain_openai import ChatOpenAI
from patchright.async_api import async_playwright as patchright_async_playwright

from workflow_use.builder.service import BuilderService
from workflow_use.controller.service import WorkflowController
from workflow_use.mcp.service import get_mcp_server
from workflow_use.recorder.service import RecordingService  # Added import
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
llm_instance = None
try:
	llm_instance = ChatOpenAI(model='gpt-4o')
	page_extraction_llm = ChatOpenAI(model='gpt-4o-mini')
except Exception as e:
	typer.secho(f'Error initializing LLM: {e}. Would you like to set your OPENAI_API_KEY?', fg=typer.colors.RED)
	set_openai_api_key = input('Set OPENAI_API_KEY? (y/n): ')
	if set_openai_api_key.lower() == 'y':
		os.environ['OPENAI_API_KEY'] = input('Enter your OPENAI_API_KEY: ')
		llm_instance = ChatOpenAI(model='gpt-4o')
		page_extraction_llm = ChatOpenAI(model='gpt-4o-mini')

builder_service = BuilderService(llm=llm_instance) if llm_instance else None
# recorder_service = RecorderService() # Placeholder
recording_service = (
	RecordingService()
)  # Assuming RecordingService does not need LLM, or handle its potential None state if it does.


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

	default_workflow_filename = f'{file_stem}.workflow.json'
	workflow_output_name: str = typer.prompt(
		typer.style('Enter a name for the generated workflow file', bold=True) + ' (e.g., my_search.workflow.json):',
		default=default_workflow_filename,
	)
	# Ensure the file name ends with .json
	if not workflow_output_name.endswith('.json'):
		workflow_output_name = f'{workflow_output_name}.json'
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
		workflow_obj = Workflow.load_from_file(str(workflow_path), llm=llm_instance, page_extraction_llm=page_extraction_llm)
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
			playwright = await patchright_async_playwright().start()

			browser = Browser(playwright=playwright)
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
			typer.echo()  # Add space
			typer.echo(typer.style('Provide values for the following workflow inputs:', bold=True))
			typer.echo()  # Add space

			for input_def in input_definitions:
				var_name_styled = typer.style(input_def.name, fg=typer.colors.CYAN, bold=True)
				prompt_question = typer.style(f'Enter value for {var_name_styled}', bold=True)

				var_type = input_def.type.lower()  # type is a direct attribute
				is_required = input_def.required

				type_info_str = f'type: {var_type}'
				if is_required:
					status_str = typer.style('required', fg=typer.colors.RED)
				else:
					status_str = typer.style('optional', fg=typer.colors.YELLOW)

				full_prompt_text = f'{prompt_question} ({status_str}, {type_info_str})'

				input_val = None
				if var_type == 'bool':
					input_val = typer.confirm(full_prompt_text)
				elif var_type == 'number':
					input_val = typer.prompt(full_prompt_text, type=float)
				elif var_type == 'string':  # Default to string for other unknown types as well
					input_val = typer.prompt(full_prompt_text, type=str)
				else:  # Should ideally not happen if schema is validated, but good to have a fallback
					typer.secho(
						f"Warning: Unknown type '{var_type}' for variable '{input_def.name}'. Treating as string.",
						fg=typer.colors.YELLOW,
					)
					input_val = typer.prompt(full_prompt_text, type=str)

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

	llm_instance = ChatOpenAI(model='gpt-4o')
	page_extraction_llm = ChatOpenAI(model='gpt-4o-mini')

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

	backend = subprocess.Popen(['uvicorn', 'backend.api:app'], stdout=backend_log, stderr=subprocess.STDOUT)
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


if __name__ == '__main__':
	app()
