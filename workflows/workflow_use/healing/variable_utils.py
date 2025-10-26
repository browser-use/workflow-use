"""Utility functions for working with workflow variables."""

import json
from pathlib import Path
from typing import Optional

from workflow_use.healing.variable_extractor import VariableExtractor
from workflow_use.schema.views import WorkflowDefinitionSchema


def process_workflow_file_with_markers(
	input_path: str | Path, output_path: Optional[str | Path] = None
) -> WorkflowDefinitionSchema:
	"""Process a workflow file to extract manual variable markers.

	This function reads a workflow file, extracts any VAR:name:value markers,
	converts them to proper input_schema definitions, and replaces them with
	{variable_name} placeholders.

	Example workflow step with markers:
	```json
	{
	  "type": "input",
	  "target_text": "Email",
	  "value": "VAR:user_email:john@example.com",
	  "description": "Enter user email"
	}
	```

	After processing:
	```json
	{
	  "type": "input",
	  "target_text": "Email",
	  "value": "{user_email}",
	  "description": "Enter user email"
	}
	```

	And adds to input_schema:
	```json
	{
	  "name": "user_email",
	  "type": "string",
	  "required": true
	}
	```

	Args:
	    input_path: Path to the workflow JSON file
	    output_path: Optional path to save the processed workflow.
	                 If None, overwrites the input file.

	Returns:
	    The processed workflow schema
	"""
	input_path = Path(input_path)
	output_path = Path(output_path) if output_path else input_path

	# Load the workflow
	with open(input_path, 'r') as f:
		workflow_data = json.load(f)

	workflow = WorkflowDefinitionSchema(**workflow_data)

	# Extract variables from markers
	extractor = VariableExtractor()
	updated_workflow, extracted_inputs = extractor.process_workflow_with_markers(workflow)

	# Save the updated workflow
	with open(output_path, 'w') as f:
		json.dump(updated_workflow.model_dump(), f, indent=2)

	print(f'Processed workflow: {input_path}')
	if extracted_inputs:
		print(f'Extracted {len(extracted_inputs)} variables:')
		for inp in extracted_inputs:
			print(f'  - {inp.name} ({inp.type})')
	else:
		print('No variable markers found')

	if output_path != input_path:
		print(f'Saved to: {output_path}')

	return updated_workflow


def print_variable_marker_help():
	"""Print help text for using variable markers."""
	help_text = """
# Manual Variable Markers

You can manually mark values as variables in your workflow using the VAR:name:value syntax.

## Syntax

VAR:variable_name:default_value

- variable_name: Must be lowercase with underscores (snake_case)
- default_value: The actual value to use

## Examples

### In Input Steps
```json
{
  "type": "input",
  "target_text": "First Name",
  "value": "VAR:first_name:John"
}
```

### In Select Steps
```json
{
  "type": "select_change",
  "target_text": "Country",
  "selectedText": "VAR:country:United States"
}
```

### In Navigation Steps
```json
{
  "type": "navigation",
  "url": "https://example.com/search?q=VAR:search_term:laptop"
}
```

### In Agent Tasks
```json
{
  "type": "agent",
  "task": "Find and click the product named VAR:product_name:iPhone"
}
```

## Processing

After adding markers to your workflow, run:

```bash
python -m workflow_use.healing.variable_utils process <workflow_file>
```

This will:
1. Extract all VAR: markers
2. Add them to the input_schema
3. Replace markers with {variable_name} placeholders
4. Save the updated workflow

## Tips

- Use descriptive variable names (e.g., user_email, search_query, product_id)
- Default values help document expected format
- You can mix markers with existing input_schema definitions
- Markers work in any string field in the workflow
"""
	print(help_text)


if __name__ == '__main__':
	import sys

	if len(sys.argv) < 2:
		print('Usage:')
		print('  python -m workflow_use.healing.variable_utils process <workflow_file> [output_file]')
		print('  python -m workflow_use.healing.variable_utils help')
		sys.exit(1)

	command = sys.argv[1]

	if command == 'help':
		print_variable_marker_help()
	elif command == 'process':
		if len(sys.argv) < 3:
			print('Error: workflow file path required')
			sys.exit(1)

		input_file = sys.argv[2]
		output_file = sys.argv[3] if len(sys.argv) > 3 else None

		try:
			process_workflow_file_with_markers(input_file, output_file)
		except Exception as e:
			print(f'Error processing workflow: {e}')
			import traceback

			traceback.print_exc()
			sys.exit(1)
	else:
		print(f'Unknown command: {command}')
		print("Use 'help' or 'process'")
		sys.exit(1)
