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
