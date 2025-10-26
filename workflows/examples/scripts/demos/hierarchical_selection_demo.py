#!/usr/bin/env python3
"""
Hierarchical Selection Demo

This example demonstrates how the enhanced semantic executor handles repeated text elements
using hierarchical context and intelligent disambiguation.
"""

import asyncio
import json
import logging
from datetime import datetime

from browser_use import Browser

from workflow_use.workflow.semantic_executor import SemanticWorkflowExecutor

# Set up logging to see the hierarchical context in action
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store interaction examples during the demo
interaction_mapping = {
	'metadata': {
		'generated_at': None,
		'demo_version': '1.0',
		'description': 'Comprehensive mapping of element interaction methods',
	},
	'element_categories': {},
	'interaction_examples': [],
	'selector_strategies': {},
	'troubleshooting_guide': {},
}

# Sample HTML with repeated elements - a common real-world scenario
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Multi-Section Form with Repeated Elements</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .section { 
            margin: 20px 0; 
            padding: 20px; 
            border: 2px solid #333; 
            background-color: white;
            border-radius: 8px;
        }
        .section h2 { 
            margin-top: 0; 
            color: #333; 
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        .form-row { margin: 15px 0; }
        .form-row label { 
            display: inline-block; 
            width: 120px; 
            font-weight: bold; 
        }
        .form-row input { 
            padding: 8px; 
            border: 1px solid #ddd; 
            border-radius: 4px;
            width: 200px;
        }
        .form-row button { 
            padding: 10px 20px; 
            margin: 5px; 
            border: none; 
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
        }
        .submit-btn { background-color: #007bff; color: white; }
        .cancel-btn { background-color: #6c757d; color: white; }
        .edit-btn { background-color: #ffc107; color: black; }
        .delete-btn { background-color: #dc3545; color: white; }
        
        table { 
            border-collapse: collapse; 
            width: 100%; 
            margin-top: 15px;
        }
        td, th { 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: left;
        }
        th { background-color: #f8f9fa; font-weight: bold; }
        tr:nth-child(even) { background-color: #f8f9fa; }
        
        .highlight { 
            border: 3px solid #ff6b6b !important; 
            background-color: #ffe6e6 !important;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        
        .demo-info {
            position: fixed;
            top: 10px;
            right: 10px;
            background: #333;
            color: white;
            padding: 15px;
            border-radius: 8px;
            max-width: 300px;
            font-size: 12px;
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div class="demo-info">
        🚀 <strong>Hierarchical Selection Demo</strong><br>
        This page shows how the system handles repeated text elements<br>
        <em>Keep this browser open to see the selection in action!</em>
    </div>
    
    <h1>🔄 User Registration Form - Hierarchical Selection Demo</h1>
    
    <!-- Personal Information Section -->
    <section class="section" id="personal-info">
        <h2>👤 Personal Information</h2>
        <form id="personal-form">
            <div class="form-row">
                <label for="personal-firstName">First Name:</label>
                <input type="text" id="personal-firstName" name="firstName" placeholder="Enter your first name">
            </div>
            <div class="form-row">
                <label for="personal-email">Email:</label>
                <input type="email" id="personal-email" name="email" placeholder="Enter your email">
            </div>
            <div class="form-row">
                <button type="submit" class="submit-btn">Submit</button>
                <button type="button" class="cancel-btn">Cancel</button>
            </div>
        </form>
    </section>
    
    <!-- Billing Information Section -->
    <section class="section" id="billing-info">
        <h2>💳 Billing Information</h2>
        <form id="billing-form">
            <div class="form-row">
                <label for="billing-firstName">First Name:</label>
                <input type="text" id="billing-firstName" name="billingFirstName" placeholder="Billing first name">
            </div>
            <div class="form-row">
                <label for="billing-email">Email:</label>
                <input type="email" id="billing-email" name="billingEmail" placeholder="Billing email">
            </div>
            <div class="form-row">
                <button type="submit" class="submit-btn">Submit</button>
                <button type="button" class="cancel-btn">Cancel</button>
            </div>
        </form>
    </section>
    
    <!-- Data Table with Repeated Actions -->
    <section class="section" id="user-table">
        <h2>👥 User Management</h2>
        <table>
            <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Actions</th>
            </tr>
            <tr>
                <td>John Doe</td>
                <td>john@example.com</td>
                <td>
                    <button class="edit-btn">Edit</button>
                    <button class="delete-btn">Delete</button>
                </td>
            </tr>
            <tr>
                <td>Jane Smith</td>
                <td>jane@example.com</td>
                <td>
                    <button class="edit-btn">Edit</button>
                    <button class="delete-btn">Delete</button>
                </td>
            </tr>
            <tr>
                <td>Bob Johnson</td>
                <td>bob@example.com</td>
                <td>
                    <button class="edit-btn">Edit</button>
                    <button class="delete-btn">Delete</button>
                </td>
            </tr>
        </table>
    </section>
    
    <!-- Newsletter Signup with Similar Elements -->
    <section class="section" id="newsletter">
        <h2>📧 Newsletter Signup</h2>
        <fieldset>
            <legend>Subscribe to Updates</legend>
            <form id="newsletter-form">
                <div class="form-row">
                    <label for="newsletter-email">Email:</label>
                    <input type="email" id="newsletter-email" name="newsletterEmail" placeholder="Your email address">
                </div>
                <div class="form-row">
                    <input type="radio" id="daily" name="frequency" value="daily">
                    <label for="daily">Daily</label>
                    
                    <input type="radio" id="weekly" name="frequency" value="weekly">
                    <label for="weekly">Weekly</label>
                    
                    <input type="radio" id="monthly" name="frequency" value="monthly">
                    <label for="monthly">Monthly</label>
                </div>
                <div class="form-row">
                    <button type="submit" class="submit-btn">Submit</button>
                    <button type="reset" class="cancel-btn">Cancel</button>
                </div>
            </form>
        </fieldset>
    </section>
    
    <script>
        // Add visual highlighting when elements are selected
        function highlightElement(selector) {
            console.log('Highlighting selector:', selector);
            
            // Remove previous highlights
            document.querySelectorAll('.highlight').forEach(el => el.classList.remove('highlight'));
            
            // Try to find the element with the given selector
            let element = null;
            try {
                const elements = document.querySelectorAll(selector);
                console.log(`Found ${elements.length} elements for selector: ${selector}`);
                
                if (elements.length === 1) {
                    element = elements[0];
                } else if (elements.length > 1) {
                    // For multiple elements, show all of them for debugging
                    console.warn(`Multiple elements found for selector ${selector}:`, elements);
                    element = elements[0]; // Still highlight the first one
                }
            } catch (e) {
                console.error('Error with selector:', selector, e);
                return false;
            }
            
            if (element) {
                element.classList.add('highlight');
                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                
                // Add debug info to element
                console.log('Highlighted element:', element);
                console.log('Element parent:', element.parentElement);
                console.log('Element context:', {
                    id: element.id,
                    className: element.className,
                    tagName: element.tagName,
                    type: element.type,
                    textContent: element.textContent?.trim(),
                    parentId: element.parentElement?.id,
                    parentClass: element.parentElement?.className
                });
                
                return true;
            } else {
                console.error('No element found for selector:', selector);
                return false;
            }
        }
        
        // Expose function globally for demo purposes
        window.highlightElement = highlightElement;
    </script>
</body>
</html>
"""


async def highlight_element(page, selector: str, description: str, element_info: dict):
	"""Highlight an element on the page with enhanced debugging"""
	try:
		print(f'🎯 Attempting to highlight: {description}')
		print(f'   Using selector: {selector}')

		# First check if the selector matches any elements
		element_count = await page.evaluate(f"""
            document.querySelectorAll('{selector}').length
        """)

		if element_count == 0:
			print('   ❌ Selector matches no elements')
			return False
		elif element_count > 1:
			print(f'   ⚠️  Selector matches {element_count} elements (may highlight wrong one)')
		else:
			print('   ✅ Selector matches exactly 1 element')

		# Try to highlight the element
		await page.evaluate(f"""
            const elements = document.querySelectorAll('{selector}');
            if (elements.length > 0) {{
                // Remove any existing highlights
                document.querySelectorAll('.demo-highlight').forEach(el => {{
                    el.classList.remove('demo-highlight');
                    el.style.border = '';
                    el.style.backgroundColor = '';
                }});
                
                // Highlight the first matching element
                const el = elements[0];
                el.classList.add('demo-highlight');
                el.style.border = '3px solid #ff6b6b';
                el.style.backgroundColor = 'rgba(255, 107, 107, 0.1)';
                
                // Scroll into view
                el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                
                console.log('Highlighted element:', el);
                console.log('Element text:', el.textContent.trim());
                console.log('Element tag:', el.tagName);
                console.log('Element classes:', el.className);
            }}
        """)

		print(f'   ✅ Successfully highlighted: {description}')
		return True

	except Exception as e:
		print(f'   ❌ Failed to highlight {description}: {str(e)}')
		return False


async def demonstrate_interactive_selection():
	"""
	Interactive demonstration of hierarchical element selection with comprehensive output mapping generation.
	"""
	print('🔄 Setting up browser and loading sample page...')
	print('📱 A browser window will open - keep it visible to see the selection in action!')

	browser = Browser()
	await browser.start()

	# Load the sample HTML
	page = await browser.get_current_page()
	await page.set_content(SAMPLE_HTML)
	await page.wait_for_load_state()

	# Create semantic executor
	executor = SemanticWorkflowExecutor(browser)

	print('\n' + '=' * 80)
	print('📋 BUILDING SEMANTIC MAPPING WITH HIERARCHICAL CONTEXT')
	print('=' * 80)

	# Initialize selector strategies documentation
	add_selector_strategy(
		'hierarchical_container',
		'Find elements by first locating their container, then searching within',
		'When dealing with repeated elements in structured content (tables, lists, forms)',
		[
			"await executor.find_element_in_container('Edit', container_selector='#table tr:nth-of-type(2)')",
			"await executor.find_element_in_container('Submit', container_text='Personal Information')",
		],
	)

	add_selector_strategy(
		'context_hints',
		'Use context hints to disambiguate between similar elements',
		'When elements have the same text but different semantic contexts',
		[
			"await executor.find_element_with_context('Submit', ['personal', 'form'])",
			"await executor.find_element_with_context('First Name', ['billing'])",
		],
	)

	add_selector_strategy(
		'direct_semantic',
		'Direct semantic mapping lookup for unique elements',
		'When element text is already unique or has been disambiguated',
		["await executor.find_element_with_context('Weekly')", "element = mapping['Newsletter Email']"],
	)

	# Show all available elements with their hierarchical context
	mapping = await executor.list_available_elements_with_context()

	input('\n⏸️  Press Enter to see element selection examples...')

	print('\n' + '=' * 80)
	print('🎯 INTERACTIVE ELEMENT SELECTION EXAMPLES')
	print('=' * 80)

	# Example 1: Show all Submit buttons with context
	print('\n1️⃣ Finding all Submit buttons:')
	await executor._refresh_semantic_mapping()
	submit_buttons = []
	for text, info in executor.current_mapping.items():
		if 'submit' in text.lower():
			submit_buttons.append((text, info['selectors']))

	for i, (text, selector) in enumerate(submit_buttons):
		print(f"   Submit #{i + 1}: '{text}' -> {selector}")

	input('\n⏸️  Press Enter to highlight the Personal Information Submit button...')

	# Example 2: Highlight specific Submit button
	print('\n2️⃣ Contextual Selection - Personal Information Submit:')
	personal_submit = await executor.find_element_with_context('Submit', ['personal'])
	if personal_submit:
		selector = personal_submit['selectors']
		success = await highlight_element(page, selector, 'Personal Submit button', personal_submit)
		print(f'   ✅ Found and highlighted: {selector}')

		# Record this interaction
		record_interaction_example('button', 'Submit', 'context_hints', personal_submit, 'Personal Information', success)

	input('\n⏸️  Press Enter to highlight the Billing Information Submit button...')

	# Example 3: Highlight billing submit
	print('\n3️⃣ Contextual Selection - Billing Information Submit:')
	billing_submit = await executor.find_element_with_context('Submit', ['billing'])
	if billing_submit:
		selector = billing_submit['selectors']
		success = await highlight_element(page, selector, 'Billing Submit button', billing_submit)
		print(f'   ✅ Found and highlighted: {selector}')

		# Record this interaction
		record_interaction_example('button', 'Submit', 'context_hints', billing_submit, 'Billing Information', success)

	input('\n⏸️  Press Enter to see table row selection...')

	# Example 4: Table row selection with comprehensive recording
	print('\n4️⃣ Table Row Selection - Edit buttons:')

	# First, let's see what selectors are actually generated for Edit buttons
	await executor._refresh_semantic_mapping()
	edit_buttons_info = []
	for text, info in executor.current_mapping.items():
		if 'edit' in text.lower():
			edit_buttons_info.append((text, info))

	print('   📋 Available Edit buttons found:')
	for text, info in edit_buttons_info:
		print(f"      '{text}' -> {info['selectors']}")
		print(f'         Hierarchical: {info.get("hierarchical_selector", "N/A")}')
		print(f'         Fallback: {info.get("fallback_selector", "N/A")}')

	# NEW APPROACH: Find Edit buttons by first finding their table rows
	print('\n   🎯 Using hierarchical container approach:')

	# Define the users and their row positions
	users = [
		('John Doe', 2),  # First data row (after header)
		('Jane Smith', 3),  # Second data row
		('Bob Johnson', 4),  # Third data row
	]

	for i, (user_name, row_num) in enumerate(users, 1):
		print(f'\n   Finding Edit button for {user_name} (row {row_num})...')

		# Method 1: Find by row selector
		row_selector = f'#user-table tr:nth-of-type({row_num})'
		edit_button = await executor.find_element_in_container('Edit', container_selector=row_selector)

		if edit_button:
			print(f'   ✅ Found Edit button using row selector: {edit_button["selectors"]}')
			success = await highlight_element(page, edit_button['selectors'], f'Edit button for {user_name}', edit_button)

			# Record this interaction
			record_interaction_example(
				'button', 'Edit', 'hierarchical_container', edit_button, f'Table row for {user_name}', success
			)

			if not success:
				print('   ⚠️  Row selector highlighting failed, trying alternative...')
				# Method 2: Find by user name in the row
				alt_edit_button = await executor.find_element_in_container('Edit', container_text=user_name)
				if alt_edit_button:
					print(f'   ✅ Found Edit button using user name: {alt_edit_button["selectors"]}')
					success = await highlight_element(
						page, alt_edit_button['selectors'], f'Edit button for {user_name} (by name)', alt_edit_button
					)

					# Record the alternative method
					record_interaction_example(
						'button', 'Edit', 'hierarchical_container', alt_edit_button, f'Container text: {user_name}', success
					)
		else:
			print(f'   ❌ Could not find Edit button for {user_name}')
			# Try the alternative approach
			alt_edit_button = await executor.find_element_in_container('Edit', container_text=user_name)
			if alt_edit_button:
				print(f'   💡 Found using user name approach: {alt_edit_button["selectors"]}')
				success = await highlight_element(
					page, alt_edit_button['selectors'], f'Edit button for {user_name} (by name)', alt_edit_button
				)

				# Record this interaction
				record_interaction_example(
					'button',
					'Edit',
					'hierarchical_container',
					alt_edit_button,
					f'Fallback - Container text: {user_name}',
					success,
				)
			else:
				# Record failed interaction
				record_interaction_example('button', 'Edit', 'hierarchical_container', {}, f'Failed for {user_name}', False)

		if i < len(users):  # Don't pause after the last one
			input(f'     ⏸️  Press Enter to find Edit button for {users[i][0]}...')

	# Also demonstrate Delete buttons
	print('\n   🗑️  Now finding Delete buttons in the same rows...')

	for i, (user_name, row_num) in enumerate(users, 1):
		if i > 1:  # Skip first one to save time
			break

		print(f'\n   Finding Delete button for {user_name}...')
		row_selector = f'#user-table tr:nth-of-type({row_num})'
		delete_button = await executor.find_element_in_container('Delete', container_selector=row_selector)

		if delete_button:
			print(f'   ✅ Found Delete button: {delete_button["selectors"]}')
			success = await highlight_element(page, delete_button['selectors'], f'Delete button for {user_name}', delete_button)

			# Record this interaction
			record_interaction_example(
				'button', 'Delete', 'hierarchical_container', delete_button, f'Table row for {user_name}', success
			)
		else:
			print(f'   ❌ Could not find Delete button for {user_name}')
			record_interaction_example('button', 'Delete', 'hierarchical_container', {}, f'Failed for {user_name}', False)

	input('\n⏸️  Press Enter to test form field disambiguation...')

	# Example 5: Form field disambiguation
	print('\n5️⃣ Form Field Disambiguation:')

	# Personal first name
	personal_firstName = await executor.find_element_with_context('First Name', ['personal'])
	if personal_firstName:
		selector = personal_firstName['selectors']
		success = await highlight_element(page, selector, 'Personal First Name field', personal_firstName)
		print(f'   ✅ Personal First Name: {selector}')

		# Record this interaction
		record_interaction_example('input', 'First Name', 'context_hints', personal_firstName, 'Personal Information', success)

	input('     ⏸️  Press Enter to highlight Billing First Name...')

	# Billing first name
	billing_firstName = await executor.find_element_with_context('First Name', ['billing'])
	if billing_firstName:
		selector = billing_firstName['selectors']
		success = await highlight_element(page, selector, 'Billing First Name field', billing_firstName)
		print(f'   ✅ Billing First Name: {selector}')

		# Record this interaction
		record_interaction_example('input', 'First Name', 'context_hints', billing_firstName, 'Billing Information', success)

	input('\n⏸️  Press Enter to see radio button selection...')

	# Example 6: Radio button selection
	print('\n6️⃣ Radio Button Selection:')
	weekly_radio = await executor.find_element_with_context('Weekly', ['newsletter'])
	if weekly_radio:
		selector = weekly_radio['selectors']
		success = await highlight_element(page, selector, 'Weekly radio button', weekly_radio)
		print(f'   ✅ Weekly radio button: {selector}')

		# Record this interaction
		record_interaction_example('radio', 'Weekly', 'context_hints', weekly_radio, 'Newsletter frequency', success)

	# Add troubleshooting tips based on what we observed
	add_troubleshooting_tip(
		'Element selector matches multiple elements',
		'Use hierarchical container approach or add more specific context hints',
		"await executor.find_element_in_container('Edit', container_selector='#table tr:nth-of-type(2)')",
	)

	add_troubleshooting_tip(
		"Element text is ambiguous (like 'Submit' appearing multiple times)",
		'Use context hints to specify which section or form',
		"await executor.find_element_with_context('Submit', ['billing', 'form'])",
	)

	add_troubleshooting_tip(
		'Complex table or list interactions',
		'Find the row/item first, then the specific button within it',
		"await executor.find_element_in_container('Edit', container_text='John Doe')",
	)

	print('\n' + '=' * 80)
	print("💡 WHAT YOU'RE SEEING")
	print('=' * 80)
	print("""
    🎯 Visual Highlighting: Each selected element is highlighted with a red border and animation
    📍 Precise Selection: Even with repeated text like "Submit" and "Edit", the system finds the exact element
    🔄 Hierarchical Context: Elements get context like "(in Personal Information)" or "(item 2 of 3)"
    🛡️  Fallback Selectors: Multiple selector strategies ensure reliability
    
    Key Benefits:
    • No more ambiguous element selection
    • Works with complex forms and data tables
    • Clear debugging information
    • Backward compatible with existing workflows
    """)

	print('\n' + '=' * 80)
	print('🔍 DEBUG INSPECTION')
	print('=' * 80)

	# Show detailed selector information for a complex element
	print('\nDetailed selector hierarchy for table Edit button:')
	edit_element = await executor.find_element_with_context('Edit', ['item 2'])
	if edit_element:
		print("  Element text: 'Edit (item 2 of 3)'")
		print(f'  Primary selector: {edit_element.get("selectors", "N/A")}')
		print(f'  Hierarchical selector: {edit_element.get("hierarchical_selector", "N/A")}')
		print(f'  Fallback selector: {edit_element.get("fallback_selector", "N/A")}')
		print(f'  XPath selector: {edit_element.get("text_xpath", "N/A")}')
		print(f'  Container context: {edit_element.get("container_context", {})}')
		print(f'  Sibling context: {edit_element.get("sibling_context", {})}')

	print('\n✅ Demo completed successfully!')
	print('\n🌟 The browser will stay open so you can:')
	print('   • Inspect the highlighted elements')
	print('   • Use browser dev tools to see the DOM structure')
	print('   • Understand how hierarchical selection works')
	print('   • Test the selectors manually')

	if mapping:
		print(f'\n📊 Found {len(mapping)} elements with hierarchical context')
	else:
		print('\n📊 Semantic mapping completed')
	print('🎯 All repeated text elements are now uniquely identifiable')

	# Generate the comprehensive interaction mapping
	print('\n' + '=' * 80)
	print('📋 GENERATING INTERACTION MAPPING OUTPUT')
	print('=' * 80)

	output_file = generate_interaction_mapping_output()
	print(f'✅ Generated comprehensive interaction mapping: {output_file}')
	print('\n📄 This file contains:')
	print('   • All interaction examples from this demo')
	print('   • Selector strategies and when to use them')
	print('   • Troubleshooting guide for common issues')
	print('   • Code examples for each interaction method')
	print('   • Element categorization and success rates')

	input("\n⏸️  Press Enter when you're done inspecting the browser...")

	print('\n👋 Closing browser...')
	await browser.close()

	return output_file


def record_interaction_example(
	element_type: str, element_text: str, interaction_method: str, selector_info: dict, context: str = '', success: bool = True
):
	"""Record an interaction example for the output mapping"""
	example = {
		'element_type': element_type,
		'element_text': element_text,
		'interaction_method': interaction_method,
		'context': context,
		'success': success,
		'selectors': {
			'primary': selector_info.get('selectors', ''),
			'hierarchical': selector_info.get('hierarchical_selector', ''),
			'fallback': selector_info.get('fallback_selector', ''),
			'xpath': selector_info.get('text_xpath', ''),
		},
		'usage_examples': [],
	}

	# Add usage examples based on interaction method
	if interaction_method == 'hierarchical_container':
		example['usage_examples'] = [
			f'await executor.find_element_in_container("{element_text}", container_selector="...")',
			f'await executor.find_element_in_container("{element_text}", container_text="...")',
		]
	elif interaction_method == 'context_hints':
		example['usage_examples'] = [
			f'await executor.find_element_with_context("{element_text}", ["{context.lower()}"])',
			f'await executor.find_element_with_context("{element_text}", ["section", "{context.lower()}"])',
		]
	elif interaction_method == 'direct_semantic':
		example['usage_examples'] = [
			f'await executor.find_element_with_context("{element_text}")',
			f'element = mapping["{element_text}"]  # Direct mapping access',
		]

	interaction_mapping['interaction_examples'].append(example)

	# Categorize by element type
	if element_type not in interaction_mapping['element_categories']:
		interaction_mapping['element_categories'][element_type] = []
	interaction_mapping['element_categories'][element_type].append(
		{'text': element_text, 'context': context, 'primary_selector': selector_info.get('selectors', ''), 'success': success}
	)


def add_selector_strategy(strategy_name: str, description: str, when_to_use: str, examples: list):
	"""Add a selector strategy to the mapping"""
	interaction_mapping['selector_strategies'][strategy_name] = {
		'description': description,
		'when_to_use': when_to_use,
		'examples': examples,
		'reliability': 'high' if 'hierarchical' in strategy_name.lower() else 'medium',
	}


def add_troubleshooting_tip(problem: str, solution: str, code_example: str = ''):
	"""Add troubleshooting information"""
	if 'common_issues' not in interaction_mapping['troubleshooting_guide']:
		interaction_mapping['troubleshooting_guide']['common_issues'] = []

	interaction_mapping['troubleshooting_guide']['common_issues'].append(
		{'problem': problem, 'solution': solution, 'code_example': code_example}
	)


def generate_interaction_mapping_output():
	"""Generate the final interaction mapping with comprehensive examples"""
	interaction_mapping['metadata']['generated_at'] = datetime.now().isoformat()

	# Add summary statistics
	interaction_mapping['summary'] = {
		'total_elements_tested': len(interaction_mapping['interaction_examples']),
		'element_types': list(interaction_mapping['element_categories'].keys()),
		'successful_interactions': len([ex for ex in interaction_mapping['interaction_examples'] if ex['success']]),
		'selector_strategies_available': len(interaction_mapping['selector_strategies']),
	}

	# Save to file
	output_file = 'hierarchical_selection_interaction_mapping.json'
	with open(output_file, 'w') as f:
		json.dump(interaction_mapping, f, indent=2)

	return output_file


if __name__ == '__main__':
	print('🚀 Interactive Hierarchical Selection Demo')
	print('=' * 80)
	print('This demo shows how the enhanced semantic executor handles repeated text elements')
	print('using hierarchical context and intelligent disambiguation.')
	print()
	print("🔥 Features you'll see:")
	print('   • Visual element highlighting')
	print('   • Context-aware element selection')
	print('   • Multiple fallback strategies')
	print('   • Clear debugging information')
	print('   • Comprehensive interaction mapping output')
	print()

	try:
		output_file = asyncio.run(demonstrate_interactive_selection())

		print('\n' + '=' * 80)
		print('🎉 DEMO COMPLETED SUCCESSFULLY!')
		print('=' * 80)
		print(f'📄 Generated interaction mapping: {output_file}')
		print('\n🔍 To view the comprehensive mapping:')
		print(f'   cat {output_file}')
		print('   # or open it in your favorite JSON viewer')
		print('\n💡 The mapping includes:')
		print('   • Step-by-step interaction examples')
		print('   • Selector strategies for different scenarios')
		print('   • Troubleshooting guide for common issues')
		print('   • Success rates and reliability metrics')
		print('   • Ready-to-use code snippets')

	except KeyboardInterrupt:
		print('\n\n👋 Demo interrupted by user')
	except Exception as e:
		print(f'\n\n❌ Demo failed with error: {e}')
		import traceback

		traceback.print_exc()
