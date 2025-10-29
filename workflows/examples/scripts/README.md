# Workflow Generation Scripts

This directory contains scripts for creating and managing workflows.

## Quick Start: Generate a Workflow

Use `generate_workflow.py` to create a workflow from any task description and automatically store it.

### How to Use

1. **Edit the task configuration** in `generate_workflow.py`:

```python
# At the top of generate_workflow.py
TASK_NAME = "Your Task Name"
TASK_DESCRIPTION = """
Your task description here.
For example: Go to GitHub, search for a repository, and extract the star count.
"""
```

2. **Run the script**:

```bash
cd workflows
uv run python examples/scripts/generate_workflow.py
```

Or with a custom API key:

```bash
cd workflows
BROWSER_USE_API_KEY=your_key uv run python examples/scripts/generate_workflow.py
```

3. **The script will**:
   - Open a browser and execute your task
   - Record all browser interactions
   - Generate a semantic workflow with steps
   - Automatically extract variables (optional)
   - Store the workflow in `workflows/storage/`
   - Provide you with the workflow ID and usage instructions

### Configuration Options

In `generate_workflow.py`, you can configure:

```python
# Enable variable extraction (uses LLM to identify reusable variables)
ENABLE_VARIABLE_EXTRACTION = True

# Use deterministic conversion (no LLM for step creation - faster, cheaper)
USE_DETERMINISTIC_CONVERSION = True

# Storage directory for workflows
STORAGE_DIR = Path(__file__).parent.parent.parent / 'storage'
```

### What You Get

After running the script, you'll get:

- **Workflow ID**: Unique identifier for your workflow
- **Workflow File**: Stored as `{workflow_id}.workflow.yaml` in the storage directory
- **Metadata**: Tracked in `storage/metadata.json`
- **Usage Instructions**: How to run the workflow with or without variables

### Example Output

```
================================================================================
WORKFLOW SUMMARY
================================================================================

Workflow ID: 8077c0ec-f61b-4b48-b0df-65aac77372ae
Name: Get GitHub Repository Stars
Description: Search for a GitHub repository and extract its star count
Version: 1.0
File Path: workflows/storage/workflows/8077c0ec-f61b-4b48-b0df-65aac77372ae.workflow.yaml

Input Variables (1):
  - repo_name: string (required) - format: owner/repo-name

Workflow Steps (5):
  Step 1: navigation
    URL: https://github.com

  Step 2: input
    Target: Search or jump to
    Value: {repo_name}

  Step 3: key_press
    Key: Enter

  Step 4: click
    Target: {repo_name}

  Step 5: extract
    Goal: Extract the number of stars
    Output Variable: star_count

✅ Pure semantic workflow (no agent steps)
   This workflow will execute fast and cost $0 per run!
```

### Running Your Generated Workflow

After generation, you can run your workflow:

```bash
cd workflows

# List all workflows
BROWSER_USE_API_KEY=your_key uv run python cli.py list-workflows

# Run by ID
BROWSER_USE_API_KEY=your_key uv run python cli.py run-workflow {workflow_id}

# Run with variables
BROWSER_USE_API_KEY=your_key uv run python cli.py run-workflow {workflow_id} --repo_name browser-use/browser-use
```

**Important**: Always run from the `workflows` directory!

## Other Scripts

### Deterministic Workflows

See `deterministic/` directory for more examples:

- `create_deterministic_workflow.py` - Create pure semantic workflows
- `auto_generate_workflow.py` - Auto-generate with variable detection
- `test_deterministic_workflow.py` - Test deterministic conversion
- `test_custom_task.py` - Test with custom tasks

### Variables

See `variables/` directory for examples of creating workflows with parameterized inputs.

## Tips

1. **Keep tasks simple**: The more specific your task description, the better the workflow
2. **Use deterministic mode**: Set `USE_DETERMINISTIC_CONVERSION = True` for faster, cheaper workflows
3. **Test your workflows**: Always test generated workflows to ensure they work as expected
4. **Variable extraction**: Enable `ENABLE_VARIABLE_EXTRACTION` to make workflows reusable with different inputs

## Troubleshooting

**Module not found errors**: Make sure you're running from the `workflows` directory with `uv run`

**API key errors**: Set your API key:
```bash
export BROWSER_USE_API_KEY=your_key
```

**Browser issues**: Ensure you have Chrome/Chromium installed and playwright dependencies set up
