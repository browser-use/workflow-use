"""Test button click with text filtering"""
import asyncio
import logging
from workflow_use.workflow.semantic_executor import SemanticWorkflowExecutor
from browser_use import Browser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_button_click():
    browser = Browser()
    await browser.start()
    executor = SemanticWorkflowExecutor(browser)

    try:
        # Navigate to the form page
        page = await browser.get_current_page()
        await page.goto("https://v0-complex-form-example.vercel.app/")
        await asyncio.sleep(2)

        # Click "Start Application" button
        logger.info("===Testing 'Start Application' button click===")
        success1 = await executor._click_element_intelligently("button", "Start Application")
        logger.info(f"Start Application click: {'SUCCESS' if success1 else 'FAILED'}")

        await asyncio.sleep(3)

        # Fill some form fields quickly
        await page.fill("#firstName", "Test")
        await page.fill("#lastName", "User")
        await page.fill("#socialSecurityLast4", "1234")
        await page.check("#male")
        await page.check("#single")
        await asyncio.sleep(1)

        # Get all buttons before clicking
        all_buttons = await executor._get_elements_by_selector('button')
        logger.info(f"Total buttons on page: {len(all_buttons)}")

        # Click "Next: Contact Information" button
        logger.info("===Testing 'Next: Contact Information' button click===")
        success2 = await executor._click_element_intelligently("button", "Next: Contact Information")
        logger.info(f"Next button click: {'SUCCESS' if success2 else 'FAILED'}")

        await asyncio.sleep(2)

        # Check final URL
        final_url = page.url
        logger.info(f"Final URL: {final_url}")
        if "/contact-info" in final_url:
            logger.info("✅ SUCCESS: Navigated to contact info page!")
        else:
            logger.error("❌ FAILED: Still on personal info page")

    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_button_click())
