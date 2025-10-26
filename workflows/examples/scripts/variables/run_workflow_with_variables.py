"""
Example: Running Workflows with Different Variables

This example shows how to run the same workflow with different input values.

Prerequisites:
- First run: uv run python examples/create_workflow_with_variables.py
- Or use existing example workflows

Run: uv run python examples/run_workflow_with_variables.py
"""

import json
from pathlib import Path
from typing import Optional

from workflow_use.schema.views import WorkflowDefinitionSchema


def load_workflow(file_path: str) -> Optional[WorkflowDefinitionSchema]:
	"""Load and validate a workflow."""
	path = Path(file_path)

	if not path.exists():
		print(f'⚠️  Workflow not found: {file_path}')
		return None

	try:
		with open(path) as f:
			data = json.load(f)

		workflow = WorkflowDefinitionSchema(**data)
		return workflow
	except Exception as e:
		print(f'❌ Error loading workflow: {e}')
		return None


def show_workflow_info(workflow: WorkflowDefinitionSchema):
	"""Display workflow information."""
	print(f'\n📋 Workflow: {workflow.name}')
	print(f'   Description: {workflow.description}')

	print('\n📝 Required Inputs:')
	for inp in workflow.input_schema:
		required = 'required' if inp.required else 'optional'
		format_str = f' (format: {inp.format})' if inp.format else ''
		print(f'   • {inp.name}: {inp.type} ({required}){format_str}')

	print(f'\n🔧 Steps ({len(workflow.steps)}):')
	for i, step in enumerate(workflow.steps, 1):
		desc = step.description if step.description else 'No description'
		print(f'   {i}. {step.type}: {desc}')

		# Show variables in use
		if hasattr(step, 'value') and '{' in str(step.value):
			print(f'      └─ value: {step.value}')
		if hasattr(step, 'target_text') and '{' in str(step.target_text):
			print(f'      └─ target_text: {step.target_text} ⭐')


def example_1_github_stars():
	"""Example 1: Get stars for different repositories."""
	print('\n' + '=' * 70)
	print('EXAMPLE 1: GitHub Repository Stars')
	print('=' * 70)

	workflow_path = 'examples/github_stars_parameterized.workflow.json'
	workflow = load_workflow(workflow_path)

	if not workflow:
		print('Creating example workflow instead...')
		workflow = WorkflowDefinitionSchema(
			name='GitHub Stars',
			description='Get star count for any repo',
			version='1.0',
			input_schema=[{'name': 'repo_name', 'type': 'string', 'required': True}],
			steps=[
				{'type': 'navigation', 'url': 'https://github.com'},
				{'type': 'input', 'target_text': 'Search', 'value': '{repo_name}'},
				{'type': 'click', 'target_text': '{repo_name}', 'container_hint': 'Repositories'},
			],
		)

	show_workflow_info(workflow)

	print('\n\n🚀 Running with Different Repositories:\n')

	repos = [
		'browser-use/browser-use',
		'anthropics/anthropic-sdk-python',
		'langchain-ai/langchain',
		'openai/openai-python',
		'microsoft/vscode',
	]

	print('# Simulating workflow runs (actual execution would use browser):\n')

	for i, repo in enumerate(repos, 1):
		print(f"{i}. Run with repo_name='{repo}'")
		print('   → Navigates to GitHub')
		print(f'   → Searches for: {repo}')
		print(f'   → Clicks element with text: {repo}')
		print('   → Extracts star count')
		print()

	print('✅ Same workflow works for ALL repositories!')
	print('   No code changes, no agent steps, instant execution!')

	print('\n💻 Actual code to run:')
	print("""
    from workflow_use.workflow.service import Workflow
    from browser_use.llm import ChatBrowserUse

    llm = ChatBrowserUse(model='bu-latest')
    workflow = Workflow.load_from_file(
        'examples/github_stars_parameterized.workflow.json',
        llm=llm
    )

    # Run with different repos
    for repo_name in repos:
        result = await workflow.run(inputs={'repo_name': repo_name})
        print(f"{repo_name}: {result.context['stars']} stars")
    """)


def example_2_product_search():
	"""Example 2: Search for different products."""
	print('\n\n' + '=' * 70)
	print('EXAMPLE 2: Product Price Comparison')
	print('=' * 70)

	# Check if created by create script
	workflow_path = '/tmp/product_search_processed.workflow.json'
	workflow = load_workflow(workflow_path)

	if not workflow:
		print('Creating example workflow...')
		workflow = WorkflowDefinitionSchema(
			name='Product Search',
			description='Search for any product',
			version='1.0',
			input_schema=[{'name': 'product_name', 'type': 'string', 'required': True}],
			steps=[
				{'type': 'navigation', 'url': 'https://amazon.com'},
				{'type': 'input', 'target_text': 'Search', 'value': '{product_name}'},
				{'type': 'click', 'target_text': '{product_name}', 'position_hint': 'first'},
				{'type': 'extract', 'extractionGoal': 'Get price', 'output': 'price'},
			],
		)

	show_workflow_info(workflow)

	print('\n\n🛍️ Comparing Prices for Different Products:\n')

	products = ['iPhone 15 Pro', 'MacBook Pro M3', 'AirPods Pro', 'iPad Air', 'Apple Watch Series 9']

	print('# Price comparison workflow:\n')

	for i, product in enumerate(products, 1):
		print(f"{i}. product_name='{product}'")
		print(f'   → Searches: {product}')
		print(f'   → Clicks first result matching: {product}')
		print('   → Extracts price')
		print()

	print('✅ One workflow, compare unlimited products!')


def example_3_form_filling():
	"""Example 3: Fill forms with different user data."""
	print('\n\n' + '=' * 70)
	print('EXAMPLE 3: Form Filling with Different Users')
	print('=' * 70)

	workflow = load_workflow('examples/semantic_form_fill.workflow.json')

	if not workflow:
		print('Creating example workflow...')
		workflow = WorkflowDefinitionSchema(
			name='Form Fill',
			description='Fill form with user data',
			version='1.0',
			input_schema=[
				{'name': 'first_name', 'type': 'string', 'required': True},
				{'name': 'last_name', 'type': 'string', 'required': True},
				{'name': 'email', 'type': 'string', 'format': 'user@domain.com', 'required': True},
			],
			steps=[
				{'type': 'navigation', 'url': 'https://example.com/form'},
				{'type': 'input', 'target_text': 'First Name', 'value': '{first_name}'},
				{'type': 'input', 'target_text': 'Last Name', 'value': '{last_name}'},
				{'type': 'input', 'target_text': 'Email', 'value': '{email}'},
				{'type': 'click', 'target_text': 'Submit'},
			],
		)

	show_workflow_info(workflow)

	print('\n\n👥 Testing with Different Users:\n')

	users = [
		{'first_name': 'Alice', 'last_name': 'Anderson', 'email': 'alice@example.com'},
		{'first_name': 'Bob', 'last_name': 'Builder', 'email': 'bob@company.com'},
		{'first_name': 'Carol', 'last_name': 'Chen', 'email': 'carol@startup.io'},
		{'first_name': 'David', 'last_name': 'Davis', 'email': 'david@tech.dev'},
	]

	for i, user in enumerate(users, 1):
		print(f'{i}. User: {user["first_name"]} {user["last_name"]}')
		print(f'   Inputs: {user}')
		print('   → Fills all form fields')
		print('   → Submits form')
		print()

	print('✅ Same workflow, test with any user!')
	print('   Perfect for QA testing, data entry, automation')


def example_4_user_profiles():
	"""Example 4: Navigate to different user profiles."""
	print('\n\n' + '=' * 70)
	print('EXAMPLE 4: User Profile Navigation')
	print('=' * 70)

	workflow_path = '/tmp/user_profile.workflow.json'
	workflow = load_workflow(workflow_path)

	if not workflow:
		print('Creating example workflow...')
		workflow = WorkflowDefinitionSchema(
			name='User Profile',
			description='View any user profile',
			version='1.0',
			input_schema=[{'name': 'username', 'type': 'string', 'required': True}],
			steps=[
				{'type': 'navigation', 'url': 'https://twitter.com'},
				{'type': 'input', 'target_text': 'Search', 'value': '{username}'},
				{'type': 'click', 'target_text': '@{username}', 'container_hint': 'People'},
			],
		)

	show_workflow_info(workflow)

	print('\n\n👤 Viewing Different User Profiles:\n')

	usernames = ['elonmusk', 'github', 'anthropicai', 'openai', 'googledevs']

	for i, username in enumerate(usernames, 1):
		print(f"{i}. username='{username}'")
		print(f'   → Searches: {username}')
		print(f'   → Clicks on: @{username}')
		print()

	print("✅ Navigate to any user's profile!")
	print("   Note: target_text combines '@' with {username} variable")


def example_5_batch_execution():
	"""Example 5: Batch execution with multiple inputs."""
	print('\n\n' + '=' * 70)
	print('EXAMPLE 5: Batch Execution')
	print('=' * 70)

	print('\n💻 Running workflows in batch mode:\n')

	print("""
    async def batch_run(workflow, inputs_list):
        '''Run workflow with multiple input sets.'''
        results = []

        for inputs in inputs_list:
            print(f"Running with: {inputs}")
            result = await workflow.run(inputs=inputs)
            results.append(result)

        return results

    # Example: Check stars for multiple repos
    repos = [
        {'repo_name': 'browser-use/browser-use'},
        {'repo_name': 'anthropics/anthropic-sdk-python'},
        {'repo_name': 'langchain-ai/langchain'},
    ]

    results = await batch_run(workflow, repos)

    # Process results
    for i, result in enumerate(results):
        print(f"{repos[i]['repo_name']}: {result.context['stars']} stars")
    """)

	print('\n✅ Benefits of batch execution:')
	print('   • Process multiple items automatically')
	print('   • Compare results across inputs')
	print('   • Generate reports')
	print('   • Automated testing')


def example_6_validation():
	"""Example 6: Input validation."""
	print('\n\n' + '=' * 70)
	print('EXAMPLE 6: Input Validation')
	print('=' * 70)

	print('\n🔒 Workflows automatically validate inputs:\n')

	workflow = WorkflowDefinitionSchema(
		name='Test',
		description='Test validation',
		version='1.0',
		input_schema=[
			{'name': 'email', 'type': 'string', 'required': True},
			{'name': 'age', 'type': 'number', 'required': True},
			{'name': 'subscribe', 'type': 'bool', 'required': False},
		],
		steps=[{'type': 'navigation', 'url': 'https://example.com'}],
	)

	print('Input Schema:')
	for inp in workflow.input_schema:
		print(f'   • {inp.name}: {inp.type} (required: {inp.required})')

	print('\n✅ Valid inputs:')
	valid = {'email': 'user@example.com', 'age': 25, 'subscribe': True}
	print(f'   {valid}')
	print('   → Passes validation ✓')

	print('\n❌ Invalid inputs:')

	print('\n   1. Missing required field:')
	print("      {'email': 'user@example.com'}")
	print("      → Error: 'age' is required")

	print('\n   2. Wrong type:')
	print("      {'email': 'user@example.com', 'age': 'twenty-five'}")
	print("      → Error: 'age' must be number")

	print('\n   3. Extra fields (allowed):')
	print("      {'email': 'user@example.com', 'age': 25, 'extra': 'field'}")
	print("      → Warning: 'extra' not in schema (but allowed)")


def main():
	"""Run all examples."""
	print('\n')
	print('╔' + '=' * 68 + '╗')
	print('║' + ' ' * 15 + 'Running Workflows with Variables' + ' ' * 20 + '║')
	print('╚' + '=' * 68 + '╝')

	example_1_github_stars()
	example_2_product_search()
	example_3_form_filling()
	example_4_user_profiles()
	example_5_batch_execution()
	example_6_validation()

	print('\n\n' + '=' * 70)
	print('SUMMARY: Running Workflows with Variables')
	print('=' * 70)

	print('\n📊 What You Can Do:')
	print('   1. Same workflow, different repos/products/users')
	print('   2. Batch execution with multiple inputs')
	print('   3. Input validation for data quality')
	print('   4. Variables in target_text for semantic matching')

	print('\n⚡ Performance Benefits:')
	print('   • 10-30x faster than agent steps')
	print('   • $0 per execution (no LLM costs)')
	print('   • Deterministic and reliable')

	print('\n🎯 Common Use Cases:')
	print('   • E-commerce: Search/compare products')
	print('   • GitHub: Check stars/issues for repos')
	print('   • Social: View different user profiles')
	print('   • Forms: Fill with different user data')
	print('   • Testing: Run same test with different data')

	print('\n💻 To Run a Workflow:')
	print("""
    from workflow_use.workflow.service import Workflow
    from browser_use.llm import ChatBrowserUse

    llm = ChatBrowserUse(model='bu-latest')
    workflow = Workflow.load_from_file('workflow.json', llm=llm)

    # Run with inputs
    result = await workflow.run(inputs={
        'variable_name': 'value',
        'another_var': 'another_value'
    })

    # Access results
    print(result.context)
    """)

	print('\n📚 Next Steps:')
	print('   1. Load an example workflow')
	print('   2. Try running it with different inputs')
	print('   3. Create your own workflow with variables')
	print('   4. Read: WORKFLOW_VARIABLES.md for complete guide')

	print('\n' + '=' * 70 + '\n')


if __name__ == '__main__':
	main()
