"""
Example: Creating Workflows with Variables

This example shows two ways to create workflows that use variables:
1. Manual JSON - Write JSON with {placeholders} directly
2. Automatic LLM - Let LLM identify and create variables automatically

Run: cd workflows && uv run python examples/create_workflow_with_variables.py
"""

import json
from pathlib import Path


def example_1_manual_json():
	"""Example 1: Create workflow manually with variables in JSON."""
	print('\n' + '=' * 70)
	print('EXAMPLE 1: Manual Creation - Write JSON with Variables')
	print('=' * 70)

	print('\n📝 Creating workflow by writing JSON with {placeholders}...\n')

	workflow = {
		'name': 'GitHub Repository Stars',
		'description': 'Get star count for any GitHub repository',
		'version': '1.0',
		'input_schema': [{'name': 'repo_name', 'type': 'string', 'format': 'owner/repo-name', 'required': True}],
		'steps': [
			{'type': 'navigation', 'url': 'https://github.com', 'description': 'Navigate to GitHub'},
			{'type': 'input', 'target_text': 'Search or jump to', 'value': '{repo_name}', 'description': 'Enter repository name'},
			{
				'type': 'click',
				'target_text': '{repo_name}',
				'container_hint': 'Repositories',
				'description': 'Click on repository - variable in target_text!',
			},
			{'type': 'extract', 'extractionGoal': 'Extract the star count', 'output': 'stars', 'description': 'Get star count'},
		],
	}

	# Save to file
	output_file = Path('/tmp/github_stars_manual.workflow.json')
	with open(output_file, 'w') as f:
		json.dump(workflow, f, indent=2)

	print(f'✅ Created: {output_file}')
	print('\n📋 Workflow structure:')
	print(f'   Name: {workflow["name"]}')
	print(f'   Variables: {[inp["name"] for inp in workflow["input_schema"]]}')
	print(f'   Steps: {len(workflow["steps"])}')

	print('\n🎯 Key feature - Step 3:')
	print(f'   {workflow["steps"][2]}')
	print('   └─> target_text uses {repo_name} variable!')

	print('\n💡 Usage:')
	print("   workflow.run(inputs={'repo_name': 'browser-use/browser-use'})")
	print("   workflow.run(inputs={'repo_name': 'anthropics/anthropic-sdk-python'})")

	print('\n✅ Best Practices:')
	print('   • Use variables in target_text for dynamic content')
	print("   • Add format hints for complex inputs (e.g., 'MM/DD/YYYY')")
	print('   • Use descriptive names (user_email, not email)')
	print('   • Mark required fields as required: true')
	print('   • Avoid agent steps for simple text variations')


def example_2_automatic_llm():
	"""Example 2: Let LLM automatically create variables."""
	print('\n\n' + '=' * 70)
	print('EXAMPLE 2: Automatic LLM - Variables Created Automatically')
	print('=' * 70)

	print('\n📝 How LLM automatically creates variables:\n')

	print('When you use HealingService.generate_workflow_from_prompt():')
	print('└─> LLM analyzes the task and browser actions')
	print('└─> Identifies which values should be variables')
	print('└─> Creates input_schema automatically')
	print('└─> Replaces values with {placeholders}')

	print('\n💻 Code example:')
	print("""
    from workflow_use.healing.service import HealingService
    from browser_use.llm import ChatBrowserUse

    llm = ChatBrowserUse(model='bu-latest')
    service = HealingService(llm=llm)

    # Generate workflow - variables created automatically!
    workflow = await service.generate_workflow_from_prompt(
        prompt="Search GitHub for repository and get its stars",
        agent_llm=llm,
        extraction_llm=llm
    )

    # LLM automatically creates:
    # - input_schema with "repo_name" variable
    # - Steps with {repo_name} in target_text
    # - No agent steps needed!
    """)

	print('\n✅ What LLM automatically parameterizes:')
	print('   • Personal info (names, emails, phone)')
	print('   • Search terms and queries')
	print('   • Form data (amounts, dates, IDs)')
	print('   • Product/item names')
	print('   • User identifiers')

	print('\n❌ What LLM keeps hardcoded:')
	print('   • Navigation URLs')
	print('   • UI element labels')
	print('   • Static button text')
	print('   • Configuration values')

	print('\n📚 See generated workflow examples:')
	print('   • examples/github_stars_parameterized.workflow.json')
	print('   • examples/semantic_form_fill.workflow.json')


def main():
	"""Run all examples."""
	print('\n')
	print('╔' + '=' * 68 + '╗')
	print('║' + ' ' * 15 + 'Creating Workflows with Variables' + ' ' * 19 + '║')
	print('╚' + '=' * 68 + '╝')

	example_1_manual_json()
	example_2_automatic_llm()

	print('\n\n' + '=' * 70)
	print('SUMMARY: 2 Ways to Create Workflows with Variables')
	print('=' * 70)

	print('\n1. Manual JSON - Write JSON with {placeholders} directly')
	print('   Best for: Complete control, hand-crafted workflows')
	print('   When: You know exactly what variables you need')

	print('\n2. Automatic LLM - Let LLM identify variables')
	print('   Best for: Converting browser-use recordings to workflows')
	print('   When: You want automatic variable detection')

	print('\n\n📚 Next Steps:')
	print('   1. See created workflow: /tmp/github_stars_manual.workflow.json')
	print('   2. Run: uv run python examples/run_workflow_with_variables.py')
	print('   3. Read: SEMANTIC_VARIABLES_GUIDE.md')

	print('\n💡 Key Takeaway:')
	print('   Variables in target_text = Same workflow, unlimited variations!')

	print('\n' + '=' * 70 + '\n')


if __name__ == '__main__':
	main()
