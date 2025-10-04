<picture>
  <img alt="Workflow Use logo - a product by Browser Use." src="./static/workflow-use.png"  width="full">
</picture>

<br />

<h1 align="center">Deterministic, Self Healing Workflows (RPA 2.0)</h1>

[![GitHub stars](https://img.shields.io/github/stars/browser-use/workflow-use?style=social)](https://github.com/browser-use/workflow-use/stargazers)
[![Discord](https://img.shields.io/discord/1303749220842340412?color=7289DA&label=Discord&logo=discord&logoColor=white)](https://link.browser-use.com/discord)
[![Cloud](https://img.shields.io/badge/Cloud-☁️-blue)](https://cloud.browser-use.com)
[![Twitter Follow](https://img.shields.io/twitter/follow/Gregor?style=social)](https://x.com/gregpr07)
[![Twitter Follow](https://img.shields.io/twitter/follow/Magnus?style=social)](https://x.com/mamagnus00)

⚙️ **Workflow Use** is the easiest way to create and execute deterministic workflows with variables which fallback to [Browser Use](https://github.com/browser-use/browser-use) if a step fails. You just _show_ the recorder the workflow, we automatically generate the workflow.

❗ This project is in very early development so we don't recommend using this in production. Lots of things will change and we don't have a release schedule yet. Originally, the project was born out of customer demand to make Browser Use more reliable and deterministic.

## 🚀 NEW: Generation Mode

Automatically generate workflows from natural language! Describe your task, we run browser-use once, then create a reusable semantic workflow stored in a database.

### Quick Commands

```bash
# Generate workflow from task description
python cli.py generate-workflow "Find GitHub stars for browser-use repo"

# List all workflows
python cli.py list-workflows

# Filter by generation mode
python cli.py list-workflows --generation-mode browser_use

# Run stored workflow
python cli.py run-stored-workflow <workflow-id> --prompt "Find stars for playwright repo"

# View workflow details
python cli.py workflow-info <workflow-id>

# Delete workflow
python cli.py delete-workflow <workflow-id>
```

### How It Works

1. **Describe**: Give a task in natural language
2. **Execute**: Browser-use completes the task once
3. **Generate**: Execution history → semantic workflow with parameters
4. **Store**: Save to database with metadata
5. **Reuse**: Run the workflow with different inputs, no AI needed

### Advanced Options

```bash
# Custom models for generation
python cli.py generate-workflow "Your task" \
  --agent-model "gpt-4.1-mini" \
  --extraction-model "gpt-4.1-mini" \
  --workflow-model "gpt-4o"

# Use Browser-Use Cloud browser
python cli.py generate-workflow "Your task" --use-cloud

# Save to custom location
python cli.py generate-workflow "Your task" --output-file ./my-workflow.json

# Skip database storage
python cli.py generate-workflow "Your task" --no-save-to-storage
```

### Storage

Workflows stored at `workflows/storage/`:
- `metadata.json` - Searchable index of all workflows
- `workflows/<id>.workflow.json` - Individual workflow files

### Programmatic Usage

```python
from workflow_use.healing.service import HealingService
from workflow_use.storage.service import WorkflowStorageService
from browser_use.llm import ChatOpenAI

healing_service = HealingService(llm=ChatOpenAI(model='gpt-4o'))
storage_service = WorkflowStorageService()

# Generate workflow
workflow = await healing_service.generate_workflow_from_prompt(
    prompt="Fill contact form on example.com",
    agent_llm=ChatOpenAI(model='gpt-4.1-mini'),
    extraction_llm=ChatOpenAI(model='gpt-4.1-mini'),
    use_cloud=True  # Optional: use Browser-Use Cloud
)

# Save to storage
metadata = storage_service.save_workflow(
    workflow=workflow,
    generation_mode='browser_use',
    original_task="Fill contact form on example.com"
)

# Retrieve and execute
loaded_workflow = storage_service.get_workflow(metadata.id)
```

# Quick start

```bash
git clone https://github.com/browser-use/workflow-use
```

## Build the extension

```bash
cd extension && npm install && npm run build
```

## Setup workflow environment

```bash
cd .. && cd workflows
uv sync
source .venv/bin/activate # for mac / linux
playwright install chromium
cp .env.example .env # add your OPENAI_API_KEY to the .env file
```


## Run workflow as tool

```bash
python cli.py run-as-tool examples/example.workflow.json --prompt "fill the form with example data"
```

## Run workflow with predefined variables

```bash
python cli.py run-workflow examples/example.workflow.json
```

## Record your own workflow

```bash
python cli.py create-workflow
```

## See all commands

```bash
python cli.py --help
```

# Usage from python

Running the workflow files is as simple as:

```python
from workflow_use import Workflow

workflow = Workflow.load_from_file("example.workflow.json")
result = asyncio.run(workflow.run_as_tool("I want to search for 'workflow use'"))
```

## Cloud Browser Support

Run workflows in [Browser-Use Cloud](https://cloud.browser-use.com) with semantic abstraction (no AI):
(NOTE: Set BROWSER_USE_API_KEY environment variable)
```python
from workflow_use import Workflow

workflow = Workflow.load_from_file("workflow.json", llm, use_cloud=True)
result = await workflow.run_with_no_ai()  # No LLM calls, uses semantic mapping
```

Examples:
- `examples/cloud_browser_demo.py` - Load recorded workflow and run on cloud

## Launch the GUI

The Workflow UI provides a visual interface for managing, viewing, and executing workflows.

### Option 1: Using the CLI command (Recommended)

The easiest way to start the GUI is with the built-in CLI command:

```bash
cd workflows
python cli.py launch-gui
```

This command will:
- Start the backend server (FastAPI)
- Start the frontend development server
- Automatically open http://localhost:5173 in your browser
- Capture logs to the `./tmp/logs` directory

Press Ctrl+C to stop both servers when you're done.

### Option 2: Start servers separately

Alternatively, you can start the servers individually:

#### Start the backend server

```bash
cd workflows
uvicorn backend.api:app --reload
```

#### Start the frontend development server

```bash
cd ui
npm install
npm run dev
```

Once both servers are running, you can access the Workflow GUI at http://localhost:5173 in your browser. The UI allows you to:

- Visualize workflows as interactive graphs
- Execute workflows with custom input parameters
- Monitor workflow execution logs in real-time
- Edit workflow metadata and details

# Demos

## Workflow Use filling out form instantly

https://github.com/user-attachments/assets/cf284e08-8c8c-484a-820a-02c507de11d4

## Gregor's explanation

https://github.com/user-attachments/assets/379e57c7-f03e-4eb9-8184-521377d5c0f9

# Features

- 🔁 **Record Once, Reuse Forever**: Record browser interactions once and replay them indefinitely.
- ⏳ **Show, don't prompt**: No need to spend hours prompting Browser Use to do the same thing over and over again.
- ⚙️ **Structured & Executable Workflows**: Converts recordings into deterministic, fast, and reliable workflows which automatically extract variables from forms.
- 🪄 **Human-like Interaction Understanding**: Intelligently filters noise from recordings to create meaningful workflows.
- 🔒 **Enterprise-Ready Foundation**: Built for future scalability with features like self-healing and workflow diffs.

# Vision and roadmap

Show computer what it needs to do once, and it will do it over and over again without any human intervention.

## Workflows

- [ ] Nice way to use the `.json` files inside python code
- [ ] Improve LLM fallback when step fails (currently really bad)
- [ ] Self healing, if it fails automatically agent kicks in and updates the workflow file
- [ ] Better support for LLM steps
- [ ] Take output from previous steps and use it as input for next steps
- [ ] Expose workflows as MCP tools
- [ ] Use Browser Use to automatically create workflows from websites

## Developer experience

- [ ] Improve CLI
- [ ] Improve extension
- [ ] Step editor

## Agent

- [ ] Allow Browser Use to use the workflows as MCP tools
- [ ] Use workflows as website caching layer
