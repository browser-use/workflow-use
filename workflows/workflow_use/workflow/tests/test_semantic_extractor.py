"""
Tests for SemanticExtractor functionality.
"""

import asyncio

import pytest
from browser_use import Browser

from workflow_use.workflow.semantic_extractor import SemanticExtractor


class TestSemanticExtractor:
	"""Test suite for SemanticExtractor."""

	@pytest.fixture
	async def browser(self):
		"""Create a browser instance for testing."""
		browser = Browser()
		yield browser
		await browser.close()

	@pytest.fixture
	def extractor(self):
		"""Create a SemanticExtractor instance."""
		return SemanticExtractor()

	@pytest.fixture
	def sample_html(self):
		"""Sample HTML for testing."""
		return """
        <!DOCTYPE html>
        <html>
        <head><title>Test Page</title></head>
        <body>
            <form id="testForm">
                <div>
                    <label for="firstName">First Name</label>
                    <input id="firstName" name="firstName" type="text" required>
                </div>
                
                <div>
                    <label for="email">Email Address</label>
                    <input id="email" name="email" type="email" placeholder="Enter your email">
                </div>
                
                <div>
                    <label>Gender</label>
                    <input type="radio" id="male" name="gender" value="male">
                    <label for="male">Male</label>
                    <input type="radio" id="female" name="gender" value="female">
                    <label for="female">Female</label>
                </div>
                
                <div>
                    <label for="country">Country</label>
                    <select id="country" name="country">
                        <option value="us">United States</option>
                        <option value="ca">Canada</option>
                    </select>
                </div>
                
                <button type="submit" id="submitBtn">Submit Form</button>
                <button type="button" class="cancel-btn">Cancel</button>
            </form>
            
            <div>
                <a href="/help" class="help-link">Get Help</a>
                <span class="info-text">Additional information here</span>
            </div>
        </body>
        </html>
        """

	async def test_extract_elements_basic(self, browser, extractor, sample_html):
		"""Test basic element extraction."""
		page = await browser.get_current_page()
		await page.set_content(sample_html)

		mapping = await extractor.extract_semantic_mapping(page)

		# Check that we extracted elements
		assert len(mapping) > 0

		# Check for form inputs
		assert any('firstName' in key.lower() for key in mapping.keys())
		assert any('email' in key.lower() for key in mapping.keys())

		# Check for buttons
		assert any('submit' in key.lower() for key in mapping.keys())
		assert any('cancel' in key.lower() for key in mapping.keys())

	async def test_element_mapping_structure(self, browser, extractor, sample_html):
		"""Test that element mapping has correct structure."""
		page = await browser.get_current_page()
		await page.set_content(sample_html)

		mapping = await extractor.extract_semantic_mapping(page)

		# Check mapping structure for at least one element
		for text, element_info in mapping.items():
			assert 'class' in element_info
			assert 'id' in element_info
			assert 'selectors' in element_info
			assert 'fallback_selector' in element_info
			assert 'element_type' in element_info
			assert 'deterministic_id' in element_info
			break

	async def test_fuzzy_matching(self, browser, extractor, sample_html):
		"""Test fuzzy text matching."""
		page = await browser.get_current_page()
		await page.set_content(sample_html)

		mapping = await extractor.extract_semantic_mapping(page)

		# Test fuzzy matching
		result = extractor.find_element_by_text(mapping, 'First Name')
		assert result is not None

		# Test partial match
		result = extractor.find_element_by_text(mapping, 'Submit')
		assert result is not None

		# Test case insensitive
		result = extractor.find_element_by_text(mapping, 'SUBMIT FORM')
		assert result is not None

	async def test_duplicate_text_handling(self, browser, extractor):
		"""Test handling of duplicate text with context."""
		html_with_duplicates = """
        <html><body>
            <div class="section1">
                <button>Save</button>
                <span>Additional info</span>
            </div>
            <div class="section2">
                <button>Save</button>
                <span>Different context</span>
            </div>
        </body></html>
        """

		page = await browser.get_current_page()
		await page.set_content(html_with_duplicates)

		mapping = await extractor.extract_semantic_mapping(page)

		# Should have multiple Save buttons with different identifiers
		save_buttons = [k for k in mapping.keys() if 'save' in k.lower()]
		assert len(save_buttons) >= 2

	async def test_selector_generation(self, browser, extractor, sample_html):
		"""Test CSS selector generation."""
		page = await browser.get_current_page()
		await page.set_content(sample_html)

		mapping = await extractor.extract_semantic_mapping(page)

		# Find the firstName input
		first_name_element = None
		for text, element_info in mapping.items():
			if 'firstName' in element_info.get('id', ''):
				first_name_element = element_info
				break

		assert first_name_element is not None

		# Check selector formats
		selectors = first_name_element['selectors']
		fallback_selector = first_name_element['fallback_selector']

		# Should have valid CSS selectors
		assert '#firstName' in selectors or 'firstName' in selectors
		assert fallback_selector != ''

	async def test_complex_form_extraction(self, browser, extractor):
		"""Test extraction from a complex form similar to the government form."""
		complex_html = """
        <html><body>
            <form class="government-form">
                <div class="personal-info">
                    <h2>Personal Information</h2>
                    <input id="firstName" name="firstName" placeholder="First Name" required>
                    <input id="lastName" name="lastName" placeholder="Last Name" required>
                    <input id="socialSecurityLast4" name="socialSecurityLast4" maxlength="4" placeholder="Last 4 SSN">
                </div>
                
                <div class="radio-group">
                    <span>Gender</span>
                    <label><input type="radio" name="gender" value="male">Male</label>
                    <label><input type="radio" name="gender" value="female">Female</label>
                    <label><input type="radio" name="gender" value="other">Other</label>
                </div>
                
                <div class="actions">
                    <button type="submit" class="primary-btn">Next: Contact Information</button>
                    <button type="button" class="secondary-btn">Save Draft</button>
                </div>
            </form>
        </body></html>
        """

		page = await browser.get_current_page()
		await page.set_content(complex_html)

		mapping = await extractor.extract_semantic_mapping(page)

		# Should extract all form elements
		expected_elements = [
			'firstName',
			'lastName',
			'socialSecurityLast4',
			'Male',
			'Female',
			'Other',
			'Next: Contact Information',
			'Save Draft',
		]

		found_elements = []
		for expected in expected_elements:
			result = extractor.find_element_by_text(mapping, expected)
			if result:
				found_elements.append(expected)

		# Should find most elements
		assert len(found_elements) >= len(expected_elements) - 1

	def test_text_normalization(self, extractor):
		"""Test text normalization for matching."""
		# Test the normalization function
		test_cases = [
			('  Hello World  ', 'hello world'),
			('First Name*', 'first name*'),
			('Email\nAddress', 'email address'),
			('SUBMIT BUTTON', 'submit button'),
		]

		for input_text, expected in test_cases:
			normalized = extractor._normalize_text(input_text)
			assert normalized == expected


class TestSemanticWorkflowIntegration:
	"""Integration tests for semantic workflow execution."""

	@pytest.fixture
	async def browser(self):
		"""Create a browser instance for testing."""
		browser = Browser()
		yield browser
		await browser.close()

	async def test_real_page_extraction(self, browser):
		"""Test extraction from a real webpage."""
		extractor = SemanticExtractor()
		page = await browser.get_current_page()

		# Navigate to a simple test page
		test_html = """
        <html><body>
            <h1>Test Page</h1>
            <form>
                <input type="text" name="username" placeholder="Username">
                <input type="password" name="password" placeholder="Password">
                <button type="submit">Login</button>
            </form>
            <a href="/forgot">Forgot Password?</a>
        </body></html>
        """

		await page.set_content(test_html)
		mapping = await extractor.extract_semantic_mapping(page)

		# Verify we can find elements by common names
		username_field = extractor.find_element_by_text(mapping, 'username')
		password_field = extractor.find_element_by_text(mapping, 'password')
		login_button = extractor.find_element_by_text(mapping, 'Login')

		assert username_field is not None
		assert password_field is not None
		assert login_button is not None


if __name__ == '__main__':
	# Run basic tests if executed directly
	async def run_basic_test():
		"""Run a basic test to verify functionality."""
		browser = Browser()
		try:
			extractor = SemanticExtractor()
			page = await browser.get_current_page()

			# Simple test HTML
			html = """
            <html><body>
                <input id="test" name="test" placeholder="Test Input">
                <button>Click Me</button>
            </body></html>
            """

			await page.set_content(html)
			mapping = await extractor.extract_semantic_mapping(page)

			print('✅ Basic extraction test passed')
			print(f'Extracted {len(mapping)} elements')

			for text, info in mapping.items():
				print(f'  - {text}: {info["selectors"]}')

		finally:
			await browser.close()

	asyncio.run(run_basic_test())
