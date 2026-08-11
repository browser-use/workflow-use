import asyncio
import logging

from browser_use import Browser
from browser_use.agent.views import ActionResult
from browser_use.controller import Controller
from browser_use.llm.base import BaseChatModel
from browser_use.tools.views import NoParamsAction

from workflow_use.compat import cdp
from workflow_use.controller.utils import get_best_element_handle, truncate_selector
from workflow_use.controller.views import (
	ClickElementDeterministicAction,
	InputTextDeterministicAction,
	KeyPressDeterministicAction,
	NavigationAction,
	PageExtractionAction,
	ScrollDeterministicAction,
	SelectDropdownOptionDeterministicAction,
)

logger = logging.getLogger(__name__)

DEFAULT_ACTION_TIMEOUT_MS = 1000


# The WorkflowController executes deterministic workflow steps only; agentic steps
# run through their own Agent with a separate controller. Every browser-use builtin
# is therefore excluded so that (a) the registry contains exactly the deterministic
# step vocabulary, (b) our custom 'click'/'input'/'scroll' registrations don't rely
# on silently overwriting builtins of the same name, and (c) the builder prompt
# (which lists this registry) can only suggest step types the schema accepts.
def _all_builtin_action_names() -> list[str]:
	from browser_use.tools.service import Tools

	return list(Tools().registry.registry.actions.keys())


class WorkflowController(Controller):
	def __init__(self, *args, **kwargs):
		# Exclude every builtin (allowlist style): only actions registered below exist.
		super().__init__(*args, exclude_actions=_all_builtin_action_names(), **kwargs)
		# The exclusion list also applies to our own registrations below (several
		# reuse builtin names like 'click'/'input'/'scroll'); clear it now that the
		# builtins have been filtered out.
		self.registry.exclude_actions = []
		self.__register_actions()

	def __register_actions(self):
		# Navigate to URL ------------------------------------------------------------
		@self.registry.action('Manually navigate to URL', param_model=NavigationAction)
		async def navigation(params: NavigationAction, browser_session: Browser) -> ActionResult:
			"""Navigate to the given URL."""
			page = await browser_session.get_current_page()
			await page.goto(params.url)
			# CDP navigate doesn't wait automatically; wait for the document to load.
			await cdp.wait_for_load_state(page, 'load', timeout_ms=10000)

			msg = f'🔗  Navigated to URL: {params.url}'
			logger.info(msg)
			return ActionResult(extracted_content=msg, include_in_memory=True)

		# History navigation --------------------------------------------------------
		@self.registry.action('Go back to the previous page', param_model=NoParamsAction)
		async def go_back(_: NoParamsAction, browser_session: Browser) -> ActionResult:
			page = await browser_session.get_current_page()
			await page.go_back()
			await cdp.wait_for_load_state(page, 'load', timeout_ms=10000)
			msg = '🔙  Navigated back'
			logger.info(msg)
			return ActionResult(extracted_content=msg, include_in_memory=True)

		@self.registry.action('Go forward to the next page', param_model=NoParamsAction)
		async def go_forward(_: NoParamsAction, browser_session: Browser) -> ActionResult:
			page = await browser_session.get_current_page()
			await page.go_forward()
			await cdp.wait_for_load_state(page, 'load', timeout_ms=10000)
			msg = '🔜  Navigated forward'
			logger.info(msg)
			return ActionResult(extracted_content=msg, include_in_memory=True)

		# Click element by CSS selector --------------------------------------------------

		@self.registry.action(
			'Click element by all available selectors',
			param_model=ClickElementDeterministicAction,
		)
		async def click(params: ClickElementDeterministicAction, browser_session: Browser) -> ActionResult:
			"""Click the first element matching *params.cssSelector* with fallback mechanisms."""
			page = await browser_session.get_current_page()
			original_selector = params.cssSelector

			try:
				element, selector_used = await get_best_element_handle(
					page,
					params.cssSelector,
					params,
					timeout_ms=DEFAULT_ACTION_TIMEOUT_MS,
				)
				await element.click()

				msg = f'🖱️  Clicked element with CSS selector: {truncate_selector(selector_used)} (original: {truncate_selector(original_selector)})'
				logger.info(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True)
			except Exception as e:
				error_msg = f'Failed to click element. Original selector: {truncate_selector(original_selector)}. Error: {str(e)}'
				logger.error(error_msg)
				raise Exception(error_msg)

		# Input text into element --------------------------------------------------------
		@self.registry.action(
			'Input text into an element by all available selectors',
			param_model=InputTextDeterministicAction,
		)
		async def input(
			params: InputTextDeterministicAction,
			browser_session: Browser,
			has_sensitive_data: bool = False,
		) -> ActionResult:
			"""Fill text into the element located with *params.cssSelector*."""
			page = await browser_session.get_current_page()
			original_selector = params.cssSelector

			try:
				element, selector_used = await get_best_element_handle(
					page,
					params.cssSelector,
					params,
					timeout_ms=DEFAULT_ACTION_TIMEOUT_MS,
				)

				# Check if it's a SELECT element (select values are set via select_change)
				if await cdp.is_select_element(element):
					return ActionResult(
						extracted_content='Ignored input into select element',
						include_in_memory=True,
					)

				await element.fill(params.value)
				await asyncio.sleep(0.5)

				msg = f'⌨️  Input "{params.value}" into element with CSS selector: {truncate_selector(selector_used)} (original: {truncate_selector(original_selector)})'
				logger.info(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True)
			except Exception as e:
				error_msg = f'Failed to input text. Original selector: {truncate_selector(original_selector)}. Error: {str(e)}'
				logger.error(error_msg)
				raise Exception(error_msg)

		# Select dropdown option ---------------------------------------------------------
		@self.registry.action(
			'Select dropdown option by all available selectors and visible text',
			param_model=SelectDropdownOptionDeterministicAction,
		)
		async def select_change(params: SelectDropdownOptionDeterministicAction, browser_session: Browser) -> ActionResult:
			"""Select dropdown option whose visible text equals *params.value*."""
			page = await browser_session.get_current_page()
			original_selector = params.cssSelector

			try:
				element, selector_used = await get_best_element_handle(
					page,
					params.cssSelector,
					params,
					timeout_ms=DEFAULT_ACTION_TIMEOUT_MS,
				)

				# Match by visible label text (Element.select_option only matches values)
				if not await cdp.select_option_by_text(element, params.selectedText):
					raise Exception(f'No option with visible text "{params.selectedText}" found')

				msg = f'Selected option "{params.selectedText}" in dropdown {truncate_selector(selector_used)} (original: {truncate_selector(original_selector)})'
				logger.info(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True)
			except Exception as e:
				error_msg = f'Failed to select option. Original selector: {truncate_selector(original_selector)}. Error: {str(e)}'
				logger.error(error_msg)
				raise Exception(error_msg)

		# Key press action ------------------------------------------------------------
		@self.registry.action(
			'Press key on element by all available selectors',
			param_model=KeyPressDeterministicAction,
		)
		async def key_press(params: KeyPressDeterministicAction, browser_session: Browser) -> ActionResult:
			"""Press *params.key* on the element identified by *params.cssSelector*."""
			page = await browser_session.get_current_page()
			original_selector = params.cssSelector

			try:
				element, selector_used = await get_best_element_handle(page, params.cssSelector, params, timeout_ms=5000)

				# Element has no press(); focus it and press on the page
				await cdp.press_key_on_element(page, element, params.key)

				msg = f"🔑  Pressed key '{params.key}' on element with CSS selector: {truncate_selector(selector_used)} (original: {truncate_selector(original_selector)})"
				logger.info(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True)
			except Exception as e:
				error_msg = f'Failed to press key. Original selector: {truncate_selector(original_selector)}. Error: {str(e)}'
				logger.error(error_msg)
				raise Exception(error_msg)

		# Scroll action --------------------------------------------------------------
		@self.registry.action('Scroll page', param_model=ScrollDeterministicAction)
		async def scroll(params: ScrollDeterministicAction, browser_session: Browser) -> ActionResult:
			"""Scroll the page by the given x/y pixel offsets."""
			page = await browser_session.get_current_page()
			await page.evaluate(f'() => window.scrollBy({params.scrollX}, {params.scrollY})')
			msg = f'📜  Scrolled page by (x={params.scrollX}, y={params.scrollY})'
			logger.info(msg)
			return ActionResult(extracted_content=msg, include_in_memory=True)

			# Extract content ------------------------------------------------------------

		@self.registry.action(
			'Extract page content to retrieve specific information from the page, e.g. all company names, a specific description, all information about, links with companies in structured format or simply links',
			param_model=PageExtractionAction,
		)
		async def extract_page_content(
			params: PageExtractionAction, browser_session: Browser, page_extraction_llm: BaseChatModel
		):
			page = await browser_session.get_current_page()
			import markdownify

			strip = ['a', 'img']

			# Get page HTML content using CDP evaluate
			html_content = await page.evaluate('() => document.documentElement.outerHTML')
			content = markdownify.markdownify(html_content, strip=strip)

			# Note: iframe content extraction is not yet supported in CDP-based implementation
			# TODO: Implement iframe content extraction using CDP

			prompt = f'Your task is to extract the content of the page. You will be given a page and a goal and you should extract all relevant information around this goal from the page. If the goal is vague, summarize the page. Respond in json format. Extraction goal: {params.goal}, Page: {content}'
			try:
				from browser_use.llm import UserMessage

				output = await page_extraction_llm.ainvoke([UserMessage(content=prompt)])
				msg = f'📄  Extracted from page\n: {output.completion}\n'
				logger.info(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True)
			except Exception as e:
				logger.debug(f'Error extracting content: {e}')
				msg = f'📄  Extracted from page\n: {content}\n'
				logger.info(msg)
				return ActionResult(extracted_content=msg)
