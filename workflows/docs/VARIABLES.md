# Workflow Variables Guide

## Overview

Variables make workflows reusable by parameterizing dynamic values.

## Quick Example

```json
{
  "name": "GitHub Star Search",
  "input_schema": [
    {"name": "repo_name", "type": "string", "required": true}
  ],
  "steps": [
    {"type": "navigation", "url": "https://github.com"},
    {"type": "input", "target_text": "Search", "value": "{repo_name}"},
    {"type": "keypress", "key": "Enter"},
    {"type": "click", "target_text": "{repo_name}"}
  ]
}
```

## Variable Syntax

Use single braces in workflow JSON:
```json
{"value": "{variable_name}"}
{"target_text": "{repo_name}"}
```

## Automatic Variable Extraction

The `VariableExtractor` analyzes workflows and suggests variables:

```python
from workflow_use.healing.variable_extractor import VariableExtractor

extractor = VariableExtractor(llm=llm)
result = await extractor.suggest_variables(workflow)

for suggestion in result.suggestions:
    print(f"{suggestion.name}: {suggestion.reasoning}")
```

## Using Variables

### CLI
```bash
cd /path/to/workflow-use/workflows
python cli.py run-workflow-no-ai workflow.json

# The CLI will prompt you interactively for variables:
# Enter value for repo_name (required, type: string): browser-use
```

### Python API
```python
await controller.run_workflow(
    workflow_definition,
    input_values={"repo_name": "browser-use"}
)
```

## Files

- `workflow_use/healing/variable_extractor.py` - Auto variable detection
- `workflow_use/healing/variable_utils.py` - Utility functions
- `examples/create_workflow_with_variables.py` - Example
- `examples/run_workflow_with_variables.py` - Usage example
