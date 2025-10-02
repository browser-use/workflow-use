import asyncio
import logging
from typing import Any, Dict, Optional, List, Tuple, TYPE_CHECKING

from browser_use import Browser

if TYPE_CHECKING:
	from browser_use.actor.page import Page
from browser_use.agent.views import ActionResult
from browser_use.llm.base import BaseChatModel
from workflow_use.schema.views import (
    ClickStep,
    InputStep,
    KeyPressStep,
    NavigationStep,
    ScrollStep,
    SelectChangeStep,
    WorkflowStep,
    ExtractStep,
)
from workflow_use.workflow.semantic_extractor import SemanticExtractor

logger = logging.getLogger(__name__)


class SemanticWorkflowExecutor:
    """Executes workflow steps using semantic mappings with optional AI extraction."""

    def __init__(self, browser: Browser, max_retries: int = 3, max_global_failures: int = 5, max_verification_failures: int = 3, page_extraction_llm: BaseChatModel | None = None):
        self.browser = browser
        self.semantic_extractor = SemanticExtractor()
        self.current_mapping: Dict[str, Dict] = {}
        self.max_retries = max_retries
        self.max_global_failures = max_global_failures
        self.max_verification_failures = max_verification_failures
        self.global_failure_count = 0
        self.consecutive_failures = 0
        self.consecutive_verification_failures = 0
        self.last_successful_step = None
        self.page_extraction_llm = page_extraction_llm

    async def _get_elements_by_selector(self, selector: str):
        """Helper to get elements by CSS selector (CDP replacement for page.locator).

        Returns list of Elements. XPath selectors are not supported.
        """
        page = await self.browser.get_current_page()

        # Skip XPath selectors
        if selector.startswith('xpath='):
            return []

        try:
            return await page.get_elements_by_css_selector(selector)
        except Exception as e:
            logger.debug(f"Error getting elements with selector {selector}: {e}")
            return []

    async def _element_get_property(self, element, property_name: str):
        """Get a property value from an element using CDP."""
        try:
            from browser_use.actor.element import Element
            if not isinstance(element, Element):
                raise ValueError("element must be an Element instance")

            # Get remote object ID for the element
            object_id = await element._get_remote_object_id()
            if not object_id:
                return None

            # Call JavaScript function to get property
            result = await element._client.send.Runtime.callFunctionOn(
                params={
                    'functionDeclaration': f'function() {{ return this.{property_name}; }}',
                    'objectId': object_id,
                    'returnByValue': True,
                },
                session_id=element._session_id,
            )

            return result.get('result', {}).get('value')
        except Exception as e:
            logger.debug(f"Error getting property {property_name}: {e}")
            return None

    async def _element_evaluate(self, element, js_function: str):
        """Evaluate JavaScript function on an element using CDP."""
        try:
            from browser_use.actor.element import Element
            if not isinstance(element, Element):
                raise ValueError("element must be an Element instance")

            # Get remote object ID for the element
            object_id = await element._get_remote_object_id()
            if not object_id:
                return None

            # Call JavaScript function
            result = await element._client.send.Runtime.callFunctionOn(
                params={
                    'functionDeclaration': js_function,
                    'objectId': object_id,
                    'returnByValue': True,
                },
                session_id=element._session_id,
            )

            return result.get('result', {}).get('value')
        except Exception as e:
            logger.debug(f"Error evaluating JS: {e}")
            return None

    async def _element_is_checked(self, element) -> bool:
        """Check if an element is checked (for radio/checkbox)."""
        checked = await self._element_get_property(element, 'checked')
        return bool(checked)

    async def _element_is_visible(self, element) -> bool:
        """Check if an element is visible."""
        try:
            bbox = await element.get_bounding_box()
            return bbox is not None and bbox['width'] > 0 and bbox['height'] > 0
        except:
            return False

    async def _element_input_value(self, element) -> str:
        """Get the input value of an element."""
        value = await self._element_get_property(element, 'value')
        return str(value) if value is not None else ''

    async def _element_press_key(self, element, key: str):
        """Press a key on an element using CDP."""
        try:
            from browser_use.actor.element import Element
            if not isinstance(element, Element):
                raise ValueError("element must be an Element instance")

            # Focus the element first
            await element.focus()
            await asyncio.sleep(0.05)

            # Get the page to send key events
            page = await self.browser.get_current_page()

            # Send key event through CDP
            key_map = {
                'Enter': {'key': 'Enter', 'code': 'Enter', 'keyCode': 13},
                'Tab': {'key': 'Tab', 'code': 'Tab', 'keyCode': 9},
                'Escape': {'key': 'Escape', 'code': 'Escape', 'keyCode': 27},
                'ArrowDown': {'key': 'ArrowDown', 'code': 'ArrowDown', 'keyCode': 40},
                'ArrowUp': {'key': 'ArrowUp', 'code': 'ArrowUp', 'keyCode': 38},
            }

            key_info = key_map.get(key, {'key': key, 'code': f'Key{key.upper()}', 'keyCode': ord(key.upper())})

            # Send keydown
            await page._client.send.Input.dispatchKeyEvent(
                params={
                    'type': 'keyDown',
                    'key': key_info['key'],
                    'code': key_info['code'],
                    'windowsVirtualKeyCode': key_info['keyCode'],
                },
                session_id=page._session_id,
            )

            await asyncio.sleep(0.05)

            # Send keyup
            await page._client.send.Input.dispatchKeyEvent(
                params={
                    'type': 'keyUp',
                    'key': key_info['key'],
                    'code': key_info['code'],
                    'windowsVirtualKeyCode': key_info['keyCode'],
                },
                session_id=page._session_id,
            )
        except Exception as e:
            raise Exception(f"Failed to press key {key}: {e}")

    async def _element_text_content(self, element) -> str:
        """Get text content of an element using CDP."""
        try:
            text = await self._element_evaluate(element, '(function() { return this.textContent || ""; })')
            return str(text) if text is not None else ''
        except:
            return ''

    async def _refresh_semantic_mapping(self) -> None:
        """Refresh the semantic mapping for the current page."""
        page = await self.browser.get_current_page()
        self.current_mapping = await self.semantic_extractor.extract_semantic_mapping(page)
        logger.info(f"Refreshed semantic mapping with {len(self.current_mapping)} elements")

        # Print detailed mapping for debugging
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("=== Current Semantic Mapping ===")
            for text, element_info in self.current_mapping.items():
                logger.debug(f"'{text}' -> {element_info['selectors']} (fallback: {element_info.get('fallback_selector', 'none')})")
            logger.debug("=== End Semantic Mapping ===")

    def _find_element_by_text(self, target_text: str, context_hints: List[str] = None) -> Optional[Dict]:
        """Find element by visible text using semantic mapping with improved hierarchical fallback strategies."""
        if not target_text:
            return None

        # Try the semantic extractor's hierarchical find method first if context is provided
        element_info = None
        if context_hints:
            element_info = self.semantic_extractor.find_element_by_hierarchy(self.current_mapping, target_text, context_hints)
            if element_info:
                logger.info(f"Found element using hierarchical context: '{target_text}' with context {context_hints}")
                return element_info

        # Try the semantic extractor's regular find method
        element_info = self.semantic_extractor.find_element_by_text(self.current_mapping, target_text)
        if element_info:
            return element_info

        # Enhanced fallback strategies for repeated elements
        target_lower = target_text.lower()

        # Strategy 1: Try to find by hierarchical selector (if available and more specific)
        best_hierarchical_match = None
        best_hierarchical_score = 0

        for text, element_info in self.current_mapping.items():
            text_lower = text.lower()
            original_text = element_info.get('original_text', '').lower()

            # Check if target matches either the full text or original text
            text_match_score = 0
            if target_lower == text_lower or target_lower == original_text:
                text_match_score = 1.0
            elif target_lower in text_lower or target_lower in original_text:
                text_match_score = 0.8
            elif text_lower in target_lower or original_text in target_lower:
                text_match_score = 0.6

            if text_match_score > 0:
                # For elements with hierarchical selectors, prefer those that provide more context
                hierarchical_selector = element_info.get('hierarchical_selector', '')
                if hierarchical_selector and hierarchical_selector != element_info.get('selectors', ''):
                    # This element has a more specific hierarchical selector

                    # Calculate specificity score based on selector complexity
                    specificity_score = 0
                    if '#' in hierarchical_selector:
                        specificity_score += 1.0  # ID selectors are most specific
                    if ':nth-of-type' in hierarchical_selector:
                        specificity_score += 0.8  # Position-based selectors are very specific
                    if '>' in hierarchical_selector:
                        specificity_score += 0.6  # Parent-child relationships are specific
                    if '.' in hierarchical_selector:
                        specificity_score += 0.4  # Class selectors add some specificity

                    # Combine text match and specificity scores
                    combined_score = text_match_score * 0.7 + specificity_score * 0.3

                    if combined_score > best_hierarchical_score:
                        best_hierarchical_match = element_info
                        best_hierarchical_score = combined_score

        if best_hierarchical_match:
            # Find the corresponding text key for logging
            matched_text = ""
            for text, element_info in self.current_mapping.items():
                if element_info == best_hierarchical_match:
                    matched_text = text
                    break
            logger.info(f"Found element by hierarchical selector: '{target_text}' -> '{matched_text}' (score: {best_hierarchical_score:.2f})")
            return best_hierarchical_match

        # Strategy 2: Try partial matches with different strategies (original fallback)
        for text, element_info in self.current_mapping.items():
            text_lower = text.lower()
            original_text = element_info.get('original_text', '').lower()

            # Check if target text is contained in element text (more lenient)
            if target_lower in text_lower or text_lower in target_lower or (original_text and (target_lower in original_text or original_text in target_lower)):
                # For radio buttons and checkboxes, be more specific
                if element_info.get('element_type') in ['radio', 'checkbox']:
                    # Check if the target text matches the value or is close to the label
                    element_value = element_info.get('selectors', '')
                    if 'value=' in element_value and target_lower in element_value.lower():
                        logger.info(f"Found radio/checkbox by value match: '{target_text}' -> {element_info['selectors']}")
                        return element_info

                # For other elements, use the match
                logger.info(f"Found element by partial text match: '{target_text}' -> '{text}'")
                return element_info

        # Strategy 3: Try to find by checking common form patterns (original fallback)
        target_words = target_text.lower().split()
        best_match = None
        best_score = 0

        for text, element_info in self.current_mapping.items():
            text_words = text.lower().split()
            original_words = element_info.get('original_text', '').lower().split()

            # Calculate word overlap score for both full text and original text
            for word_set in [text_words, original_words]:
                if word_set:
                    overlap = len(set(target_words) & set(word_set))
                    if overlap > 0:
                        score = overlap / max(len(target_words), len(word_set))
                        if score > best_score and score > 0.3:  # At least 30% overlap
                            best_match = element_info
                            best_score = score

        if best_match:
            # Find the corresponding text key for logging
            matched_text = ""
            for text, element_info in self.current_mapping.items():
                if element_info == best_match:
                    matched_text = text
                    break
            logger.info(f"Found element by word overlap: '{target_text}' -> '{matched_text}' (score: {best_score:.2f})")
            return best_match

        return None

    async def _try_direct_selector(self, target_text: str) -> Optional[str]:
        """Try to use target_text as a direct selector (ID or name) with improved robustness."""
        if not target_text or not target_text.replace('_', '').replace('-', '').replace('.', '').isalnum():
            return None

        # Clean the target text to make it a valid selector
        cleaned_text = target_text.strip()

        # Try as ID first, then name attribute, then other common patterns
        selectors_to_try = [
            f"#{cleaned_text}",
            f"[name='{cleaned_text}']",
            f"[id='{cleaned_text}']",
            f"[data-testid='{cleaned_text}']",
            f"[placeholder='{cleaned_text}']"
        ]

        # Also try with common variations
        if '_' in cleaned_text or '-' in cleaned_text:
            # Try camelCase version
            camel_case = ''.join(word.capitalize() if i > 0 else word for i, word in enumerate(cleaned_text.replace('-', '_').split('_')))
            selectors_to_try.extend([
                f"#{camel_case}",
                f"[name='{camel_case}']",
                f"[id='{camel_case}']"
            ])

            # Try lowercase version
            lower_case = cleaned_text.lower()
            selectors_to_try.extend([
                f"#{lower_case}",
                f"[name='{lower_case}']",
                f"[id='{lower_case}']"
            ])

        for selector in selectors_to_try:
            try:
                page = await self.browser.get_current_page()

                # Check if element exists first
                elements = await self._get_elements_by_selector(selector)
                element_count = len(elements)
                if element_count == 0:
                    continue

                # Check if it's visible
                await page.wait_for_selector(selector, timeout=2000, state="visible")

                # Check if this selector resolves to multiple elements (strict mode violation)
                if element_count > 1:
                    logger.warning(f"Selector {selector} matches {element_count} elements, trying to make it more specific")

                    # Try to make it more specific for form elements
                    specific_selectors = [
                        f"{selector}:not([type='hidden'])",
                        f"{selector}:visible",
                        f"{selector}:first-of-type"
                    ]

                    for specific_selector in specific_selectors:
                        try:
                            specific_elements = await self._get_elements_by_selector(specific_selector)
                            specific_count = len(specific_elements)
                            if specific_count == 1:
                                await page.wait_for_selector(specific_selector, timeout=1000, state="visible")
                                logger.info(f"Found specific element using selector: {specific_selector}")
                                return specific_selector
                        except:
                            continue

                    # If we can't make it specific, return the original but log the issue
                    logger.warning(f"Using non-specific selector {selector} (matches {element_count} elements)")
                    return selector

                logger.info(f"Found element using direct selector: {selector}")
                return selector

            except Exception as e:
                logger.debug(f"Element not found with selector {selector}: {e}")
                continue

        return None

    async def _handle_strict_mode_violation(self, selector: str, target_text: str = None) -> Optional[str]:
        """Handle cases where selector matches multiple elements."""
        page = await self.browser.get_current_page()

        try:
            elements = await page.get_elements_by_css_selector(selector)
            if len(elements) <= 1:
                return selector  # No violation

            logger.warning(f"Selector {selector} matches {len(elements)} elements, trying to narrow down...")

            # For radio buttons, try to be more specific
            if "radio" in selector.lower():
                # Try to find radio button by value if target_text looks like a value
                if target_text:
                    value_selector = f'input[type="radio"][value="{target_text.lower()}"]'
                    try:
                        value_elements = await page.get_elements_by_css_selector(value_selector)
                        if len(value_elements) == 1:
                            logger.info(f"Found specific radio button by value: {value_selector}")
                            return value_selector
                    except:
                        pass

                    # Note: get_by_label is not supported in CDP, skipping label-based search
                    pass

                # For radio buttons, cannot resolve automatically, let the calling code handle it
                logger.warning(f"Cannot automatically resolve radio button selector, returning None")
                return None

            # For other elements, cannot resolve automatically either
            logger.warning(f"Cannot automatically resolve selector, returning None")
            return None

        except Exception as e:
            logger.error(f"Error handling strict mode violation: {e}")
            return None

    async def _wait_for_element(self, selector: str, timeout_ms: int = 5000, fallback_selectors: List[str] = None) -> Tuple[bool, str]:
        """Wait for element to be available, with hierarchical fallback options.

        Returns:
            Tuple of (success, actual_selector_used)
        """
        selectors_to_try = [selector]
        if fallback_selectors:
            selectors_to_try.extend(fallback_selectors)

        page = await self.browser.get_current_page()
        end_time = asyncio.get_event_loop().time() + (timeout_ms / 1000)

        for sel in selectors_to_try:
            try:
                # XPath selectors need special handling - skip for now in CDP
                if sel.startswith('xpath='):
                    logger.debug(f"XPath selector not supported in CDP: {sel}")
                    continue

                # Poll for element with timeout
                while asyncio.get_event_loop().time() < end_time:
                    try:
                        elements = await page.get_elements_by_css_selector(sel)

                        if len(elements) > 0:
                            if len(elements) > 1:
                                logger.warning(f"Selector {sel} matches {len(elements)} elements during wait")
                                # Try to make it more specific if it's the hierarchical selector
                                if sel != selector and ':nth-of-type' in sel:
                                    return True, sel  # Hierarchical selectors with nth-of-type are usually fine
                                return True, sel  # Element exists, but we'll handle the strict mode later

                            return True, sel
                    except Exception as e:
                        logger.debug(f"Error checking selector {sel}: {e}")

                    # Wait a bit before retrying
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.debug(f"Element not found with selector {sel}: {e}")
                continue

        logger.warning(f"Element not found with any selector: {selectors_to_try}")
        return False, selector

    async def execute_navigation_step(self, step: NavigationStep) -> ActionResult:
        """Execute navigation step."""
        page = await self.browser.get_current_page()

        # Get current URL and normalize both URLs for comparison
        current_url = await page.get_url()
        target_url = step.url

        # Normalize URLs by removing fragments and trailing slashes
        def normalize_url(url: str) -> str:
            if not url:
                return ""
            # Remove fragment (everything after #)
            if '#' in url:
                url = url.split('#')[0]
            # Remove trailing slash
            return url.rstrip('/')

        current_normalized = normalize_url(current_url)
        target_normalized = normalize_url(target_url)

        # Skip navigation if we're already at the target URL
        if current_normalized == target_normalized:
            msg = f"⏭️ Skipped navigation - already at URL: {step.url}"
            logger.info(msg)
            # Still refresh semantic mapping even if we don't navigate, in case page state has changed
            await self._refresh_semantic_mapping()
            return ActionResult(extracted_content=msg, include_in_memory=True)

        # Perform navigation
        await page.goto(step.url)

        # Wait for page to load and dynamic content (SPAs, etc.)
        await asyncio.sleep(3)

        # Wait for common form elements to be present (indicates page is ready)
        try:
            # Wait for any input, button, or form element to be present
            await page.wait_for_selector('input, button, form, textarea, select', timeout=10000)
        except:
            logger.warning("No form elements found after navigation, continuing anyway")

        # Refresh semantic mapping after navigation
        await self._refresh_semantic_mapping()

        # Execute navigation with verification and retry
        async def navigation_executor():
            msg = f"🔗 Navigated to URL: {step.url}"
            logger.info(msg)
            return ActionResult(extracted_content=msg, include_in_memory=True)

        async def navigation_verifier():
            return await self._verify_navigation_action(step.url)

        return await self._execute_with_verification_and_retry(navigation_executor, step, navigation_verifier)

    async def execute_click_step(self, step: ClickStep) -> ActionResult:
        """Execute click step using semantic mapping with improved selector strategies."""
        page = await self.browser.get_current_page()

        # Try to find element using multiple strategies (prioritize target_text)
        element_info = None
        target_identifier = None
        selector_to_use = None

        if hasattr(step, 'target_text') and step.target_text:
            target_identifier = step.target_text

            # Always try to get element_info from semantic mapping for metadata (element_type, etc.)
            element_info = self._find_element_by_text(step.target_text)

            # Try direct selector first (for ID/name attributes)
            selector_to_use = await self._try_direct_selector(step.target_text)

            # If direct selector fails, use semantic mapping selector
            if not selector_to_use:
                if element_info:
                    selector_to_use = element_info['selectors']
                    logger.info(f"Using semantic mapping: '{target_identifier}' -> {selector_to_use}")
            else:
                # Direct selector worked, but we still want the element_info for metadata
                if element_info:
                    logger.info(f"Using semantic mapping: '{target_identifier}' -> {selector_to_use}")

        elif step.description:
            target_identifier = step.description
            element_info = self._find_element_by_text(step.description)
            if element_info:
                selector_to_use = element_info['selectors']
                logger.info(f"Using semantic mapping: '{target_identifier}' -> {selector_to_use}")

        # Final fallback to original CSS selector
        if not selector_to_use:
            if step.cssSelector:
                selector_to_use = step.cssSelector
                logger.info(f"Falling back to original CSS selector: {selector_to_use}")
            else:
                # Enhanced error message with debugging info
                available_texts = list(self.current_mapping.keys())[:15]  # Show first 15 available options
                error_msg = f"No selector available for click step: '{target_identifier or step.description}'"
                error_msg += f"\nAvailable elements on page: {available_texts}"
                if len(self.current_mapping) > 15:
                    error_msg += f" (and {len(self.current_mapping) - 15} more)"

                # Try to find similar text matches for debugging
                if target_identifier:
                    similar_matches = []
                    target_lower = target_identifier.lower()
                    for text in self.current_mapping.keys():
                        if any(word in text.lower() for word in target_lower.split()):
                            similar_matches.append(text)

                    if similar_matches:
                        error_msg += f"\nSimilar text found: {similar_matches[:5]}"

                logger.error(error_msg)
                raise Exception(error_msg)

        # Wait for element using hierarchical fallback strategies
        fallback_selectors = []
        if element_info:
            # Add hierarchical selector as first fallback
            hierarchical_selector = element_info.get('hierarchical_selector')
            if hierarchical_selector and hierarchical_selector != selector_to_use:
                fallback_selectors.append(hierarchical_selector)

            # Add original fallback selector
            fallback_selector = element_info.get('fallback_selector')
            if fallback_selector and fallback_selector not in fallback_selectors:
                fallback_selectors.append(fallback_selector)

            # Add XPath selector as final fallback
            xpath_selector = element_info.get('text_xpath')
            if xpath_selector:
                fallback_selectors.append(f"xpath={xpath_selector}")

        success, actual_selector = await self._wait_for_element(selector_to_use, fallback_selectors=fallback_selectors)
        if not success:
            available_texts = list(self.current_mapping.keys())[:10]
            error_msg = f"Element not found with any selector for: '{target_identifier or step.description}'"
            error_msg += f"\nTried selectors: {[selector_to_use] + fallback_selectors}"
            error_msg += f"\nAvailable elements on page: {available_texts}"
            raise Exception(error_msg)

        # Use the selector that actually worked
        selector_to_use = actual_selector

        # Execute click with verification and retry
        async def click_executor():
            success = await self._click_element_intelligently(selector_to_use, target_identifier, element_info)
            if not success:
                raise Exception(f"Failed to click element: {target_identifier or step.description or selector_to_use}")

            msg = f"🖱️ Clicked element: {target_identifier or step.description or selector_to_use}"
            logger.info(msg)
            return ActionResult(extracted_content=msg, include_in_memory=True)

        async def click_verifier():
            return await self._verify_click_action(selector_to_use, target_identifier, step.type, step, element_info)

        return await self._execute_with_verification_and_retry(click_executor, step, click_verifier)

    async def _click_element_intelligently(self, selector: str, target_text: str, element_info: Dict | None = None) -> bool:
        """Click element using the most appropriate strategy based on element type."""
        page = await self.browser.get_current_page()

        try:
            # Strategy -1: Check if element_info indicates this is a radio/checkbox, even if selector doesn't show it
            if element_info and element_info.get('element_type') in ['radio', 'checkbox']:
                logger.info(f"Detected {element_info['element_type']} from semantic mapping")

                # First, try to find the actual input element within or associated with the selector
                try:
                    # Strategy A: Check if the selector itself points to an input or button
                    elements = await self._get_elements_by_selector(selector)
                    if elements:
                        element = elements[0]
                        tag_name = await self._element_get_property(element, 'tagName')
                        role = await self._element_get_property(element, 'role')
                        tag_name = tag_name.lower() if tag_name else ''
                        role = role.lower() if role else ''

                        logger.info(f"Selector points to tag={tag_name}, role={role}")

                        # Handle Radix UI / ARIA radio buttons (button with role="radio")
                        if tag_name == 'button' and role == 'radio':
                            logger.info(f"Detected Radix UI / ARIA radio button, clicking directly")
                            await element.click()
                            logger.info(f"Successfully clicked ARIA radio button: {selector}")
                            return True
                        elif tag_name == 'input':
                            # Traditional input, use check() method
                            await page.check(selector)
                            logger.info(f"Successfully checked {element_info['element_type']}: {selector}")
                            return True
                        else:
                            # Container element, try multiple strategies
                            logger.info(f"Selector points to {tag_name}, searching for radio control inside")

                            # Strategy 1: Look for button[role="radio"] (Radix UI pattern)
                            aria_radio_selector = f"{selector} button[role='radio']"
                            try:
                                aria_radio_elements = await self._get_elements_by_selector(aria_radio_selector)
                                if aria_radio_elements:
                                    await aria_radio_elements[0].click()
                                    logger.info(f"Successfully clicked ARIA radio button inside container: {aria_radio_selector}")
                                    return True
                            except Exception as e:
                                logger.debug(f"Failed to find ARIA radio button inside container: {e}")

                            # Strategy 2: Look for traditional input[type="radio"]
                            input_selector = f"{selector} input[type='{element_info['element_type']}']"
                            try:
                                input_elements = await self._get_elements_by_selector(input_selector)
                                if input_elements:
                                    # Check if input has pointer-events: none (hidden input pattern)
                                    pointer_events = await self._element_evaluate(
                                        input_elements[0],
                                        '(function() { return window.getComputedStyle(this).pointerEvents; })'
                                    )
                                    if pointer_events == 'none':
                                        logger.info(f"Input has pointer-events: none, clicking container instead")
                                        await element.click()
                                        return True
                                    else:
                                        await page.check(input_selector)
                                        logger.info(f"Successfully checked {element_info['element_type']} input inside container: {input_selector}")
                                        return True
                            except Exception as e:
                                logger.debug(f"Failed to find input inside container: {e}")

                            # Fallback: Click the container (label) which might trigger the input
                            await element.click()
                            logger.info(f"Clicked container element that should trigger {element_info['element_type']}: {selector}")
                            return True
                except Exception as e:
                    logger.warning(f"Radio/checkbox detection strategy failed: {e}")
                    # Continue to other strategies

            # Strategy 0: For buttons, ensure we're clicking the right button by text content
            if "button" in selector.lower() or "submit" in selector.lower():
                # If we have target_text, try to find the specific button by its text content
                if target_text and target_text.strip():
                    # First try simple input submit/button with value attribute
                    value_strategies = [
                        f'input[type="submit"][value="{target_text}"]',
                        f'input[type="button"][value="{target_text}"]',
                    ]

                    for button_selector in value_strategies:
                        try:
                            elements = await self._get_elements_by_selector(button_selector)
                            count = len(elements)
                            if count == 1:
                                await elements[0].click()
                                logger.info(f"Successfully clicked button using value selector: {button_selector}")
                                return True
                            elif count > 1:
                                await elements[0].click()
                                logger.info(f"Clicked first matching button: {button_selector}")
                                return True
                        except Exception as e:
                            logger.debug(f"Button strategy failed for {button_selector}: {e}")
                            continue

                    # Strategy: Get all buttons and filter by text content using JavaScript
                    try:
                        # Get all button elements
                        all_buttons = await self._get_elements_by_selector('button')
                        logger.info(f"🔍 Found {len(all_buttons)} total button elements, filtering by text '{target_text}'")

                        # Filter buttons by text content using JavaScript evaluation
                        matching_buttons = []
                        for i, btn in enumerate(all_buttons):
                            if i > 20:  # Limit to first 20 buttons to avoid timeout
                                logger.info(f"⚠️ Stopping button search after checking 20 buttons")
                                break
                            try:
                                text_content = await asyncio.wait_for(
                                    self._element_evaluate(btn, '(function() { return this.textContent.trim(); })'),
                                    timeout=1.0  # 1 second timeout per button
                                )
                                logger.info(f"Button {i}: '{text_content[:50]}'...")  # Log each button text
                                if text_content and target_text in text_content:
                                    matching_buttons.append(btn)
                                    logger.info(f"✅ Button text match found: '{text_content}' contains '{target_text}'")
                            except asyncio.TimeoutError:
                                logger.warning(f"⏱️ Timeout evaluating button {i} text")
                                continue
                            except Exception as e:
                                logger.warning(f"❌ Error evaluating button {i} text: {e}")
                                continue

                        if len(matching_buttons) == 1:
                            logger.info(f"🎯 Clicking the 1 matching button for '{target_text}'")
                            button_element = matching_buttons[0]

                            # Check button type attribute to see if it's a submit button
                            try:
                                button_type = await asyncio.wait_for(
                                    self._element_evaluate(button_element, '(function() { return this.getAttribute("type"); })'),
                                    timeout=1.0
                                )
                                logger.info(f"📋 Button type attribute: {button_type}")
                            except Exception as e:
                                logger.debug(f"Could not get button type: {e}")
                                button_type = None

                            # Check if this is a submit button that should trigger navigation
                            is_submit_button = (
                                button_type == "submit" or
                                any(keyword in target_text.lower() for keyword in ['next', 'submit', 'continue', 'save', 'finish'])
                            )

                            if is_submit_button:
                                logger.info(f"🔄 Detected submit button (type={button_type}), will wait for navigation")

                                # Give form state time to settle before submitting (important for React forms)
                                await asyncio.sleep(0.5)

                                # Get current URL before clicking
                                current_url = await page.get_url()

                                # Try to find and submit the parent form directly if clicking doesn't work
                                try:
                                    # First attempt: Click the button normally
                                    await button_element.click()
                                    logger.info(f"✅ Clicked submit button, waiting for navigation from {current_url}")

                                    # Wait for navigation to complete (up to 5 seconds)
                                    await asyncio.sleep(2)  # Give page time to start navigating
                                    new_url = await page.get_url()

                                    if new_url != current_url:
                                        logger.info(f"✅ Navigation successful: {current_url} -> {new_url}")
                                        return True
                                    else:
                                        logger.warning(f"⚠️ No navigation occurred after clicking '{target_text}'. URL still: {new_url}")

                                        # Check for validation errors
                                        validation_errors = await self._detect_form_validation_errors()
                                        if validation_errors:
                                            logger.error(f"❌ Form validation errors preventing submission: {validation_errors}")
                                            return False

                                        # No validation errors but still no navigation - try submitting form directly
                                        logger.info(f"🔧 Attempting to submit parent form directly via JavaScript")
                                        try:
                                            # Find parent form and submit it
                                            form_submitted = await self._element_evaluate(
                                                button_element,
                                                '(function() { var form = this.closest("form"); if(form) { form.requestSubmit(); return true; } return false; })'
                                            )

                                            if form_submitted:
                                                logger.info(f"✅ Triggered form.requestSubmit()")
                                                await asyncio.sleep(2)
                                                final_url = await page.get_url()

                                                if final_url != current_url:
                                                    logger.info(f"✅ Navigation successful via form submit: {current_url} -> {final_url}")
                                                    return True
                                                else:
                                                    logger.error(f"❌ Form submit didn't trigger navigation either")
                                                    return False
                                            else:
                                                logger.warning(f"⚠️ Could not find parent form to submit")
                                                return False
                                        except Exception as submit_error:
                                            logger.error(f"❌ Error submitting form directly: {submit_error}")
                                            return False

                                except Exception as e:
                                    logger.error(f"❌ Error during submit button handling: {e}")
                                    return False
                            else:
                                # Regular button click
                                await button_element.click()
                                logger.info(f"✅ Successfully clicked button by text content: '{target_text}'")
                                await asyncio.sleep(1)
                                return True
                        elif len(matching_buttons) > 1:
                            # Multiple matches, use the first one
                            logger.warning(f"⚠️ Found {len(matching_buttons)} buttons containing '{target_text}', clicking first one")
                            await matching_buttons[0].click()
                            # Wait for potential navigation
                            await asyncio.sleep(1)
                            return True
                        else:
                            logger.warning(f"❌ No buttons found with text containing '{target_text}'")
                    except Exception as e:
                        logger.error(f"❌ Button text filtering failed: {e}")

                # Fall back to original selector if text-based strategies fail
                try:
                    elements = await self._get_elements_by_selector(selector)
                    count = len(elements)
                    if count >= 1:
                        if count > 1:
                            logger.warning(f"Multiple buttons found with selector {selector}, clicking first")
                        await elements[0].click()
                        logger.info(f"Successfully clicked button using original selector: {selector}")
                        return True
                except Exception as e:
                    logger.debug(f"Original button selector failed: {e}")

            # Strategy 1: For radio buttons and checkboxes, try label clicking first
            elif "radio" in selector.lower() or "checkbox" in selector.lower():
                # Try clicking the associated label first (most reliable)
                if target_text:
                    label_strategies = [
                        f'label:has-text("{target_text}")',
                        f'label[for*="{target_text.lower()}"]',
                        f'label:has(input[value="{target_text.lower()}"])'
                    ]

                    for label_selector in label_strategies:
                        try:
                            label_elements = await self._get_elements_by_selector(label_selector)
                            label_count = len(label_elements)
                            if label_count == 1:
                                await label_elements[0].click()
                                logger.info(f"Successfully clicked label: {label_selector}")
                                return True
                            elif label_count > 1:
                                # Multiple labels found, be more specific
                                await label_elements[0].click()
                                logger.info(f"Clicked first matching label: {label_selector}")
                                return True
                        except Exception as e:
                            logger.debug(f"Label click failed for {label_selector}: {e}")
                            continue

                # Strategy 2: Use .check() for radio buttons and checkboxes
                try:
                    # Make selector more specific if needed
                    if selector == 'input[type="radio"]' or selector == 'input[type="checkbox"]':
                        # This is too generic, try to make it specific
                        if target_text:
                            specific_selectors = [
                                f'input[type="radio"][value="{target_text.lower()}"]',
                                f'input[type="checkbox"][value="{target_text.lower()}"]',
                                f'input[value="{target_text.lower()}"]'
                            ]

                            for specific_selector in specific_selectors:
                                try:
                                    specific_elements = await self._get_elements_by_selector(specific_selector)
                                    count = len(specific_elements)
                                    if count == 1:
                                        await page.check(specific_selector)
                                        logger.info(f"Successfully checked using specific selector: {specific_selector}")
                                        return True
                                except Exception as e:
                                    logger.debug(f"Specific check failed for {specific_selector}: {e}")
                                    continue
                    else:
                        # Use the provided selector with .check()
                        await page.check(selector)
                        logger.info(f"Successfully checked: {selector}")
                        return True

                except Exception as e:
                    logger.debug(f"Check operation failed: {e}")

                # Strategy 3: Fall back to clicking the input directly (with specificity)
                try:
                    elements = await self._get_elements_by_selector(selector)
                    count = len(elements)
                    if count == 1:
                        await elements[0].click()
                        logger.info(f"Successfully clicked radio/checkbox: {selector}")
                        return True
                    elif count > 1:
                        # Multiple elements, try to be more specific
                        if target_text:
                            specific_elements = await self._get_elements_by_selector(f'{selector}[value="{target_text.lower()}"]')
                            if len(specific_elements) > 0:
                                await specific_elements[0].click()
                                logger.info(f"Clicked specific radio/checkbox by value: {target_text}")
                                return True

                        # Fall back to first match - use page.check with selector since we can't .check() on element
                        await page.check(selector)
                        logger.warning(f"Selected first radio button (multiple found): {selector}")
                        return True
                except Exception as e:
                    logger.debug(f"Direct radio/checkbox click failed: {e}")

            # Strategy 4: For buttons and other elements, use regular click
            try:
                elements = await self._get_elements_by_selector(selector)
                if len(elements) == 1:
                    await elements[0].click()
                    logger.info(f"Successfully clicked element: {selector}")
                    return True
                elif len(elements) > 1:
                    # Multiple elements found, click first one with warning
                    await elements[0].click()
                    logger.warning(f"Clicked first element (multiple found): {selector}")
                    return True
                else:
                    logger.error(f"No elements found for selector: {selector}")
                    return False
            except Exception as e:
                logger.error(f"Regular click failed: {e}")
                return False

        except Exception as e:
            logger.error(f"Intelligent click failed: {e}")
            return False

    async def execute_input_step(self, step: InputStep) -> ActionResult:
        """Execute input step using semantic mapping."""
        page = await self.browser.get_current_page()

        # Try to find element using multiple strategies (prioritize target_text)
        element_info = None
        target_identifier = None
        selector_to_use = None

        if hasattr(step, 'target_text') and step.target_text:
            target_identifier = step.target_text

            # Try direct selector first (for ID/name attributes)
            selector_to_use = await self._try_direct_selector(step.target_text)

            # If direct selector fails, try semantic mapping
            if not selector_to_use:
                element_info = self._find_element_by_text(step.target_text)
                if element_info:
                    selector_to_use = element_info['selectors']
                    logger.info(f"Using semantic mapping: '{target_identifier}' -> {selector_to_use}")

        elif step.description:
            target_identifier = step.description
            element_info = self._find_element_by_text(step.description)
            if element_info:
                selector_to_use = element_info['selectors']
                logger.info(f"Using semantic mapping: '{target_identifier}' -> {selector_to_use}")

        # Final fallback to original CSS selector
        if not selector_to_use:
            if step.cssSelector:
                selector_to_use = step.cssSelector
                logger.info(f"Falling back to original CSS selector: {selector_to_use}")
            else:
                # Enhanced error message with debugging info
                available_texts = list(self.current_mapping.keys())[:15]  # Show first 15 available options
                error_msg = f"No selector available for input step: '{target_identifier or step.description}'"
                error_msg += f"\nAvailable elements on page: {available_texts}"
                if len(self.current_mapping) > 15:
                    error_msg += f" (and {len(self.current_mapping) - 15} more)"

                # Try to find similar text matches for debugging
                if target_identifier:
                    similar_matches = []
                    target_lower = target_identifier.lower()
                    for text in self.current_mapping.keys():
                        if any(word in text.lower() for word in target_lower.split()):
                            similar_matches.append(text)

                    if similar_matches:
                        error_msg += f"\nSimilar text found: {similar_matches[:5]}"

                logger.error(error_msg)
                raise Exception(error_msg)

        # Wait for element using hierarchical fallback strategies
        fallback_selectors = []
        if element_info:
            # Add hierarchical selector as first fallback
            hierarchical_selector = element_info.get('hierarchical_selector')
            if hierarchical_selector and hierarchical_selector != selector_to_use:
                fallback_selectors.append(hierarchical_selector)

            # Add original fallback selector
            fallback_selector = element_info.get('fallback_selector')
            if fallback_selector and fallback_selector not in fallback_selectors:
                fallback_selectors.append(fallback_selector)

            # Add XPath selector as final fallback
            xpath_selector = element_info.get('text_xpath')
            if xpath_selector:
                fallback_selectors.append(f"xpath={xpath_selector}")

        success, actual_selector = await self._wait_for_element(selector_to_use, fallback_selectors=fallback_selectors)
        if not success:
            available_texts = list(self.current_mapping.keys())[:10]
            error_msg = f"Element not found with any selector for input: '{target_identifier or step.description}'"
            error_msg += f"\nTried selectors: {[selector_to_use] + fallback_selectors}"
            error_msg += f"\nAvailable elements on page: {available_texts}"
            raise Exception(error_msg)

        # Use the selector that actually worked
        selector_to_use = actual_selector

        elements = await self._get_elements_by_selector(selector_to_use)
        if len(elements) == 0:
            raise Exception(f"Element not found with selector: {selector_to_use}")

        # Check element type to handle different input types properly
        element_type = await self._element_evaluate(elements[0], '(function() { return { tagName: this.tagName, type: this.type, value: this.value }; })')

        if element_type['tagName'] == 'SELECT':
            return ActionResult(
                extracted_content='Ignored input into select element',
                include_in_memory=True,
            )

        # Execute input with verification and retry
        async def input_executor():
            elements = await self._get_elements_by_selector(selector_to_use)
            if len(elements) == 0:
                raise Exception(f"Element not found with selector: {selector_to_use}")
            element = elements[0]
            element_type = await self._element_evaluate(element, '(function() { return { tagName: this.tagName, type: this.type, value: this.value }; })')

            # Handle radio buttons and checkboxes with improved strategies
            if element_type['type'] in ['radio', 'checkbox']:
                success = await self._handle_radio_checkbox_input(selector_to_use, step.value, target_identifier, element_type['type'])
                if not success:
                    raise Exception(f"Failed to select {element_type['type']} button: {target_identifier}")

                action_type = "🔘" if element_type['type'] == 'radio' else "☑️"
                msg = f"{action_type} Selected '{step.value}' for: {target_identifier or step.description}"
                logger.info(msg)
                return ActionResult(extracted_content=msg, include_in_memory=True)

            # Regular input handling for text fields, etc.
            await element.fill(step.value)
            await asyncio.sleep(0.5)
            # Click removed - not needed after fill and CDP doesn't support force parameter
            await asyncio.sleep(0.5)

            msg = f"⌨️ Input '{step.value}' into: {target_identifier or step.description or selector_to_use}"
            logger.info(msg)
            return ActionResult(extracted_content=msg, include_in_memory=True)

        async def input_verifier():
            elements = await self._get_elements_by_selector(selector_to_use)
            if len(elements) == 0:
                return False
            element = elements[0]
            element_type = await self._element_evaluate(element, '(function() { return { tagName: this.tagName, type: this.type, value: this.value }; })')
            return await self._verify_input_action(selector_to_use, step.value, element_type['type'])

        return await self._execute_with_verification_and_retry(input_executor, step, input_verifier)

    async def _handle_radio_checkbox_input(self, selector: str, value: str, target_text: str, input_type: str) -> bool:
        """Handle radio button and checkbox input with improved strategies."""
        page = await self.browser.get_current_page()

        try:
            # Strategy 1: For radio buttons, find the specific radio button by value
            if input_type == 'radio':
                # Try to be more specific with radio button selection
                radio_strategies = [
                    f'input[type="radio"][value="{value.lower()}"]',
                    f'input[type="radio"][value="{value}"]',
                    f'input[value="{value.lower()}"]',
                    f'input[value="{value}"]'
                ]

                for radio_selector in radio_strategies:
                    try:
                        radio_elements = await self._get_elements_by_selector(radio_selector)
                        count = len(radio_elements)
                        if count == 1:
                            await page.check(radio_selector)
                            logger.info(f"Successfully selected radio button: {radio_selector}")
                            return True
                        elif count > 1:
                            # Multiple radio buttons with same value, try to narrow down by name or context
                            if target_text:
                                # Try to find by label association
                                contextual_selectors = [
                                    f'input[type="radio"][value="{value.lower()}"][name*="{target_text.lower()}"]',
                                    f'label:has-text("{target_text}") input[type="radio"][value="{value.lower()}"]'
                                ]

                                for ctx_selector in contextual_selectors:
                                    try:
                                        ctx_elements = await self._get_elements_by_selector(ctx_selector)
                                        ctx_count = len(ctx_elements)
                                        if ctx_count == 1:
                                            await page.check(ctx_selector)
                                            logger.info(f"Selected radio button with context: {ctx_selector}")
                                            return True
                                    except Exception as e:
                                        logger.debug(f"Contextual radio selection failed: {e}")
                                        continue

                            # Fall back to first match - use page.check with selector since we can't .check() on element
                            await page.check(radio_selector)
                            logger.warning(f"Selected first radio button (multiple found): {radio_selector}")
                            return True
                    except Exception as e:
                        logger.debug(f"Radio button selection failed for {radio_selector}: {e}")
                        continue

                # Note: label:has-text() selector is not supported in CDP
                # Skipping label click fallback
                pass

            # Strategy 2: For checkboxes, determine desired state and set accordingly
            elif input_type == 'checkbox':
                should_check = value.lower() in ['true', '1', 'on', 'yes', 'checked']

                try:
                    # Get current state using CDP
                    checkbox_elements = await self._get_elements_by_selector(selector)
                    if len(checkbox_elements) == 0:
                        raise Exception(f"Checkbox element not found: {selector}")
                    is_currently_checked = await self._element_is_checked(checkbox_elements[0])

                    if should_check and not is_currently_checked:
                        await page.check(selector)
                        logger.info(f"Checked checkbox: {target_text}")
                        return True
                    elif not should_check and is_currently_checked:
                        await page.uncheck(selector)
                        logger.info(f"Unchecked checkbox: {target_text}")
                        return True
                    else:
                        logger.info(f"Checkbox already in desired state: {target_text}")
                        return True
                except Exception as e:
                    logger.debug(f"Checkbox operation failed: {e}")

                    # Note: label:has-text() selector is not supported in CDP
                    # Skipping label click fallback
                    pass

            return False

        except Exception as e:
            logger.error(f"Radio/checkbox input handling failed: {e}")
            return False

    async def execute_select_step(self, step: SelectChangeStep) -> ActionResult:
        """Execute select dropdown step using semantic mapping."""
        page = await self.browser.get_current_page()

        # Try to find element using semantic mapping first (prioritize target_text)
        element_info = None
        target_identifier = None

        if hasattr(step, 'target_text') and step.target_text:
            target_identifier = step.target_text
            element_info = self._find_element_by_text(step.target_text)
        elif step.description:
            target_identifier = step.description
            element_info = self._find_element_by_text(step.description)

        # Fallback to original CSS selector if semantic mapping fails
        selector_to_use = None
        if element_info:
            selector_to_use = element_info['selectors']
            logger.info(f"Using semantic mapping: '{target_identifier}' -> {selector_to_use}")
        elif step.cssSelector:
            selector_to_use = step.cssSelector
            logger.info(f"Falling back to original CSS selector: {selector_to_use}")
        else:
            # Enhanced error message with debugging info
            available_texts = list(self.current_mapping.keys())[:10]  # Show first 10 available options
            error_msg = f"No selector available for select step: {target_identifier or step.description}"
            error_msg += f"\nAvailable elements on page: {available_texts}"
            if len(self.current_mapping) > 10:
                error_msg += f" (and {len(self.current_mapping) - 10} more)"
            logger.error(error_msg)
            raise Exception(error_msg)

        # Wait for element using hierarchical fallback strategies
        fallback_selectors = []
        if element_info:
            # Add hierarchical selector as first fallback
            hierarchical_selector = element_info.get('hierarchical_selector')
            if hierarchical_selector and hierarchical_selector != selector_to_use:
                fallback_selectors.append(hierarchical_selector)

            # Add original fallback selector
            fallback_selector = element_info.get('fallback_selector')
            if fallback_selector and fallback_selector not in fallback_selectors:
                fallback_selectors.append(fallback_selector)

            # Add XPath selector as final fallback
            xpath_selector = element_info.get('text_xpath')
            if xpath_selector:
                fallback_selectors.append(f"xpath={xpath_selector}")

        success, actual_selector = await self._wait_for_element(selector_to_use, fallback_selectors=fallback_selectors)
        if not success:
            available_texts = list(self.current_mapping.keys())[:10]
            error_msg = f"Element not found with any selector for select: '{target_identifier or step.description}'"
            error_msg += f"\nTried selectors: {[selector_to_use] + fallback_selectors}"
            error_msg += f"\nAvailable elements on page: {available_texts}"
            raise Exception(error_msg)

        # Use the selector that actually worked
        selector_to_use = actual_selector

        # Execute select with verification and retry
        async def select_executor():
            elements = await self._get_elements_by_selector(selector_to_use)
            if not elements:
                raise Exception(f"Element not found with selector: {selector_to_use}")
            element = elements[0]
            # select_option takes values (text or value of the option)
            await element.select_option(step.selectedText)

            msg = f"🔽 Selected '{step.selectedText}' in: {target_identifier or step.description or selector_to_use}"
            logger.info(msg)
            return ActionResult(extracted_content=msg, include_in_memory=True)

        async def select_verifier():
            return await self._verify_input_action(selector_to_use, step.selectedText, 'select')

        return await self._execute_with_verification_and_retry(select_executor, step, select_verifier)

    async def execute_key_press_step(self, step: KeyPressStep) -> ActionResult:
        """Execute key press step using semantic mapping."""
        page = await self.browser.get_current_page()

        # Try to find element using semantic mapping first (prioritize target_text)
        element_info = None
        target_identifier = None

        if hasattr(step, 'target_text') and step.target_text:
            target_identifier = step.target_text
            element_info = self._find_element_by_text(step.target_text)
        elif step.description:
            target_identifier = step.description
            element_info = self._find_element_by_text(step.description)

        # Fallback to original CSS selector if semantic mapping fails
        selector_to_use = None
        if element_info:
            selector_to_use = element_info['selectors']
            logger.info(f"Using semantic mapping: '{target_identifier}' -> {selector_to_use}")
        elif step.cssSelector:
            selector_to_use = step.cssSelector
            logger.info(f"Falling back to original CSS selector: {selector_to_use}")
        else:
            # Enhanced error message with debugging info
            available_texts = list(self.current_mapping.keys())[:10]  # Show first 10 available options
            error_msg = f"No selector available for key press step: {target_identifier or step.description}"
            error_msg += f"\nAvailable elements on page: {available_texts}"
            if len(self.current_mapping) > 10:
                error_msg += f" (and {len(self.current_mapping) - 10} more)"
            logger.error(error_msg)
            raise Exception(error_msg)

        # Wait for element using hierarchical fallback strategies
        fallback_selectors = []
        if element_info:
            # Add hierarchical selector as first fallback
            hierarchical_selector = element_info.get('hierarchical_selector')
            if hierarchical_selector and hierarchical_selector != selector_to_use:
                fallback_selectors.append(hierarchical_selector)

            # Add original fallback selector
            fallback_selector = element_info.get('fallback_selector')
            if fallback_selector and fallback_selector not in fallback_selectors:
                fallback_selectors.append(fallback_selector)

            # Add XPath selector as final fallback
            xpath_selector = element_info.get('text_xpath')
            if xpath_selector:
                fallback_selectors.append(f"xpath={xpath_selector}")

        success, actual_selector = await self._wait_for_element(selector_to_use, fallback_selectors=fallback_selectors)
        if not success:
            available_texts = list(self.current_mapping.keys())[:10]
            error_msg = f"Element not found with any selector for key press: '{target_identifier or step.description}'"
            error_msg += f"\nTried selectors: {[selector_to_use] + fallback_selectors}"
            error_msg += f"\nAvailable elements on page: {available_texts}"
            raise Exception(error_msg)

        # Use the selector that actually worked
        selector_to_use = actual_selector

        # Execute key press with verification and retry
        async def keypress_executor():
            elements = await self._get_elements_by_selector(selector_to_use)
            if not elements:
                raise Exception(f"Element not found with selector: {selector_to_use}")
            element = elements[0]
            await self._element_press_key(element, step.key)

            msg = f"🔑 Pressed key '{step.key}' on: {target_identifier or step.description or selector_to_use}"
            logger.info(msg)
            return ActionResult(extracted_content=msg, include_in_memory=True)

        async def keypress_verifier():
            # For key presses, just verify the element is still accessible
            # (More specific verification could be added based on the key and context)
            try:
                elements = await self._get_elements_by_selector(selector_to_use)
                if not elements:
                    return False
                element = elements[0]
                return await self._element_is_visible(element)
            except:
                return False

        return await self._execute_with_verification_and_retry(keypress_executor, step, keypress_verifier)

    async def execute_scroll_step(self, step: ScrollStep) -> ActionResult:
        """Execute scroll step."""
        page = await self.browser.get_current_page()
        await page.evaluate(f"() => window.scrollBy({step.scrollX}, {step.scrollY})")

        msg = f"📜 Scrolled by ({step.scrollX}, {step.scrollY})"
        logger.info(msg)
        return ActionResult(extracted_content=msg, include_in_memory=True)

    async def execute_button_step(self, step) -> ActionResult:
        """Execute button click step using semantic mapping."""
        # Button steps are essentially click steps but with button-specific metadata
        # Convert to click step format for execution
        click_step = ClickStep(
            type="button",  # Use button type for verification
            target_text=getattr(step, 'target_text', getattr(step, 'button_text', '')),
            description=step.description,
            cssSelector=getattr(step, 'cssSelector', ''),
            xpath=getattr(step, 'xpath', '')
        )

        # Execute with button-specific verification
        result = await self.execute_click_step(click_step)

        # Update the message to indicate it was a button click
        button_text = getattr(step, 'button_text', getattr(step, 'target_text', 'button'))
        button_type = getattr(step, 'button_type', 'button')
        msg = f"🔘 Clicked {button_type} button: {button_text}"
        logger.info(msg)

        return ActionResult(extracted_content=msg, include_in_memory=True)

    def set_workflow_context(self, workflow_steps: list):
        """Set the current workflow steps for context-aware verification."""
        self._current_workflow_steps = workflow_steps

    async def execute_step(self, step: WorkflowStep) -> ActionResult:
        """Execute a single workflow step."""
        # Always refresh semantic mapping before each step to avoid stale selectors
        await self._refresh_semantic_mapping()

        if isinstance(step, NavigationStep):
            return await self.execute_navigation_step(step)
        elif isinstance(step, ClickStep):
            return await self.execute_click_step(step)
        elif isinstance(step, InputStep):
            return await self.execute_input_step(step)
        elif isinstance(step, SelectChangeStep):
            return await self.execute_select_step(step)
        elif isinstance(step, KeyPressStep):
            return await self.execute_key_press_step(step)
        elif isinstance(step, ScrollStep):
            return await self.execute_scroll_step(step)
        elif step.type == 'button':
            return await self.execute_button_step(step)
        elif isinstance(step, ExtractStep):
            return await self.execute_extract_step(step)
        else:
            raise Exception(f"Unsupported step type: {step.type}")

    async def print_semantic_mapping(self) -> None:
        """Print current semantic mapping for debugging."""
        if not self.current_mapping:
            await self._refresh_semantic_mapping()

        logger.info("=== Current Semantic Mapping ===")
        for text, element_info in self.current_mapping.items():
            logger.info(f"'{text}' -> {element_info['deterministic_id']} ({element_info['selectors']})")
        logger.info("=== End Semantic Mapping ===")

    async def _execute_with_verification_and_retry(self, step_executor, step, verification_method):
        """Execute a step with verification and retry logic."""
        # Check if we've hit global failure limits before starting
        if self.global_failure_count >= self.max_global_failures:
            error_msg = f"❌ Global failure limit reached ({self.global_failure_count}/{self.max_global_failures}). Workflow appears to be encountering systematic issues."
            logger.error(error_msg)
            raise Exception(error_msg)

        if self.consecutive_failures >= 3:
            error_msg = f"❌ Too many consecutive failures ({self.consecutive_failures}). Form may have unexpected changes or invalid input data."
            logger.error(error_msg)
            raise Exception(error_msg)

        if self.consecutive_verification_failures >= self.max_verification_failures:
            error_msg = f"❌ Too many consecutive verification failures ({self.consecutive_verification_failures}). Steps are executing but not achieving expected results."
            logger.error(error_msg)
            raise Exception(error_msg)

        last_exception = None
        last_result = None

        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                if attempt > 0:
                    logger.info(f"🔄 Retry attempt {attempt}/{self.max_retries} for step: {step.description}")
                    # Refresh semantic mapping before retry
                    await self._refresh_semantic_mapping()
                    # Small delay before retry
                    await asyncio.sleep(1)

                # Execute the step
                result = await step_executor()
                last_result = result

                # Check for validation errors immediately after execution
                validation_errors = await self._detect_form_validation_errors()
                if validation_errors:
                    logger.warning(f"⚠️ Form validation errors detected after step execution: {validation_errors}")
                    if attempt < self.max_retries:
                        logger.warning(f"⚠️ Step caused validation errors, will retry...")
                        continue
                    else:
                        logger.error(f"❌ Step caused validation errors after {self.max_retries} retries")
                        # Don't break here, let it continue to verification

                # Verify the step was successful
                verification_passed = await verification_method()

                if verification_passed and not validation_errors:
                    if attempt > 0:
                        logger.info(f"✅ Step succeeded on retry {attempt}")

                    # Reset all failure counters on success
                    self.consecutive_failures = 0
                    self.consecutive_verification_failures = 0
                    self.last_successful_step = step.description if hasattr(step, 'description') else str(step.type)
                    return result
                else:
                    # Track verification failures separately from execution failures
                    if not validation_errors and not verification_passed:
                        # This is a pure verification failure (step executed but didn't achieve expected result)
                        pass  # We'll increment this counter after all retries are exhausted

                    if attempt < self.max_retries:
                        if validation_errors:
                            logger.warning(f"⚠️ Step caused validation errors, will retry...")
                        else:
                            logger.warning(f"⚠️ Step verification failed, will retry...")
                        continue
                    else:
                        # This is the final attempt and it failed
                        if validation_errors:
                            last_exception = Exception(f"Step caused form validation errors: {list(validation_errors.values())}")
                        else:
                            # For verification failures, increment the counter immediately
                            self.consecutive_verification_failures += 1
                            last_exception = Exception("Step verification failed")

                            # Check if we should stop due to verification failures
                            if self.consecutive_verification_failures >= self.max_verification_failures:
                                raise Exception(f"Too many consecutive verification failures ({self.consecutive_verification_failures}). Steps are executing but not achieving expected results.")
                        break

            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Check for specific error patterns that indicate systematic issues
                    error_str = str(e).lower()
                    if any(pattern in error_str for pattern in [
                        'element not found', 'timeout', 'selector failed',
                        'no such element', 'element is not attached'
                    ]):
                        logger.warning(f"⚠️ Element detection failed (attempt {attempt + 1}): {e}")
                    else:
                        logger.warning(f"⚠️ Step execution failed (attempt {attempt + 1}): {e}")
                    continue
                else:
                    logger.error(f"❌ Step execution failed after {self.max_retries} retries: {e}")
                    break

        # If we get here, the step failed after all retries are exhausted
        self.global_failure_count += 1
        self.consecutive_failures += 1

        # Determine failure type and update appropriate counters
        failure_type = "execution"
        if last_exception and "verification failed" in str(last_exception).lower():
            self.consecutive_verification_failures += 1
            failure_type = "verification"
        elif last_exception and "validation errors" in str(last_exception).lower():
            failure_type = "validation"
        else:
            failure_type = "execution"

        # Enhanced error reporting
        error_context = {
            'step_type': step.type if hasattr(step, 'type') else 'unknown',
            'description': step.description if hasattr(step, 'description') else 'No description',
            'target_text': getattr(step, 'target_text', None),
            'value': getattr(step, 'value', None),
            'failure_type': failure_type,
            'global_failures': self.global_failure_count,
            'consecutive_failures': self.consecutive_failures,
            'consecutive_verification_failures': self.consecutive_verification_failures,
            'last_successful_step': self.last_successful_step
        }

        logger.error(f"❌ Step failed completely after {self.max_retries + 1} attempts. Context: {error_context}")

        # Provide specific guidance based on failure patterns
        if self.consecutive_verification_failures >= 2:
            logger.warning("⚠️  Multiple consecutive verification failures detected. This may indicate:")
            logger.warning("   • Steps are executing but not achieving expected results")
            logger.warning("   • Form behavior has changed (validation rules, navigation flow)")
            logger.warning("   • Data being entered is causing unexpected form states")
            logger.warning("   • Page interactions are not waiting long enough for effects")
        elif self.consecutive_failures >= 2:
            logger.warning("⚠️  Multiple consecutive execution failures detected. This may indicate:")
            logger.warning("   • Form structure has changed")
            logger.warning("   • Invalid input data for current form state")
            logger.warning("   • Element selectors are outdated")
            logger.warning("   • Form validation is rejecting inputs")

        # Raise the last exception that occurred
        if last_exception:
            raise last_exception
        else:
            raise Exception(f"Step failed after {self.max_retries + 1} attempts. Global failures: {self.global_failure_count}")

        return last_result

    async def _detect_form_validation_errors(self) -> Dict[str, str]:
        """Detect form validation errors that might indicate invalid input data."""
        page = await self.browser.get_current_page()
        validation_errors = {}

        try:
            # Common error message selectors
            error_selectors = [
                '.error', '.error-message', '.validation-error', '.field-error',
                '[role="alert"]', '.alert-danger', '.text-red', '.text-error',
                '.invalid-feedback', '.form-error', '.help-block.error'
            ]

            for selector in error_selectors:
                try:
                    error_elements = await page.get_elements_by_css_selector(selector)
                    for i, element in enumerate(error_elements):
                        if await self._element_is_visible(element):
                            error_text = await self._element_text_content(element)
                            if error_text and error_text.strip():
                                # Filter out browser internal scripts and long technical content
                                clean_text = error_text.strip()

                                # Skip if it looks like browser internal code
                                if any(pattern in clean_text for pattern in [
                                    'document.getElementById', 'function addPageBinding',
                                    'serializeAsCallArgument', '__next_f', 'globalThis',
                                    'self.__next_f', 'serializeAsCallArgument'
                                ]):
                                    continue

                                # Skip very long messages (likely technical content)
                                if len(clean_text) > 200:
                                    continue

                                # Only include messages that look like actual validation errors
                                if any(pattern in clean_text.lower() for pattern in [
                                    'required', 'invalid', 'error', 'must', 'cannot', 'please',
                                    'missing', 'incorrect', 'format', 'valid', 'enter', 'provide',
                                    'field', 'complete', 'fill'
                                ]):
                                    validation_errors[f"{selector}_{i}"] = clean_text
                except:
                    continue

            # Check for common validation patterns in text
            if validation_errors:
                logger.warning(f"🚨 Form validation errors detected: {validation_errors}")

        except Exception as e:
            logger.debug(f"Error checking for validation messages: {e}")

        return validation_errors

    async def _detect_form_submission_failure(self, expected_progress_indicators: list = None) -> bool:
        """Detect if a form submission failed by checking for common failure indicators."""
        page = await self.browser.get_current_page()

        try:
            # Check if we're still on the same form step/page when we should have progressed
            # Note: text= selector is not supported in CDP, skipping this check
            # if expected_progress_indicators:
            #     for indicator in expected_progress_indicators:
            #         try:
            #             elements = await page.query_selector_all(f"text={indicator}")
            #             if elements:
            #                 logger.warning(f"Form submission may have failed: still showing '{indicator}'")
            #                 return True
            #         except:
            #             continue

            # Check for common submission failure indicators
            failure_indicators = [
                'form-error', 'submission-error', 'error-summary',
                'alert-error', 'error-container'
            ]

            for indicator in failure_indicators:
                try:
                    elements = await page.get_elements_by_css_selector(f".{indicator}")
                    for element in elements:
                        if await self._element_is_visible(element):
                            error_text = await self._element_text_content(element)
                            if error_text and error_text.strip():
                                logger.warning(f"Form submission failure detected: {error_text.strip()}")
                                return True
                except:
                    continue

            return False

        except Exception as e:
            logger.debug(f"Error checking for form submission failure: {e}")
            return False

    async def _verify_navigation_success_by_next_step(self, current_step) -> bool:
        """Verify navigation success by checking if next step elements are available."""
        if not current_step or not hasattr(current_step, '__dict__'):
            return False

        try:
            # Get workflow context to find the next step
            workflow_steps = getattr(self, '_current_workflow_steps', None)
            if not workflow_steps:
                return False

            # Find current step index
            current_step_desc = getattr(current_step, 'description', '')
            current_index = -1

            for i, step in enumerate(workflow_steps):
                if step.get('description') == current_step_desc:
                    current_index = i
                    break

            if current_index == -1 or current_index >= len(workflow_steps) - 1:
                return False

            # Get next step
            next_step = workflow_steps[current_index + 1]
            next_step_type = next_step.get('type', '')

            # Skip non-interactive steps (scroll, etc.)
            step_offset = 1
            while (current_index + step_offset < len(workflow_steps) and
                   workflow_steps[current_index + step_offset].get('type') in ['scroll', 'navigation']):
                step_offset += 1

            if current_index + step_offset >= len(workflow_steps):
                return False

            target_step = workflow_steps[current_index + step_offset]
            target_text = target_step.get('target_text')

            if not target_text:
                return False

            # Refresh semantic mapping to check for next step elements
            await self._refresh_semantic_mapping()

            # Check if the target element for the next step is now available
            element_info = self._find_element_by_text(target_text)
            if element_info:
                logger.info(f"Verification: Found next step element '{target_text}' - navigation successful")
                return True

            # Also check if target_text is a direct selector that exists
            try:
                page = await self.browser.get_current_page()
                direct_selector = await self._try_direct_selector(target_text)
                if direct_selector:
                    await page.wait_for_selector(direct_selector, timeout=2000, state="visible")
                    logger.info(f"Verification: Found next step element by direct selector '{target_text}' - navigation successful")
                    return True
            except Exception:
                pass

            logger.debug(f"Verification: Next step element '{target_text}' not found - navigation may have failed")
            return False

        except Exception as e:
            logger.debug(f"Error verifying navigation by next step: {e}")
            return False

    async def _analyze_failure_context(self, step, error: Exception) -> str:
        """Analyze the context of a step failure to provide better error messages."""
        context_info = []

        try:
            # Check current page state
            page = await self.browser.get_current_page()
            current_url = await page.get_url()
            page_title = await page.get_title()

            context_info.append(f"URL: {current_url}")
            context_info.append(f"Page Title: {page_title}")

            # Check for validation errors
            validation_errors = await self._detect_form_validation_errors()
            if validation_errors:
                context_info.append(f"Validation Errors: {list(validation_errors.values())}")

            # Check if expected elements are present on page
            if hasattr(step, 'target_text') and step.target_text:
                element_count = len(self.current_mapping)
                has_target = step.target_text in self.current_mapping
                context_info.append(f"Elements on page: {element_count}, Target '{step.target_text}' found: {has_target}")

                if not has_target:
                    # Find similar elements
                    similar_elements = []
                    target_lower = step.target_text.lower()
                    for text in self.current_mapping.keys():
                        if target_lower in text.lower() or text.lower() in target_lower:
                            similar_elements.append(text)

                    if similar_elements:
                        context_info.append(f"Similar elements found: {similar_elements[:3]}")

        except Exception as e:
            context_info.append(f"Context analysis failed: {e}")

        return " | ".join(context_info)

    async def _verify_click_action(self, selector: str, target_text: str, step_type: str = "click", current_step=None, element_info: Dict = None) -> bool:
        """Verify that a click action had the expected effect."""
        try:
            page = await self.browser.get_current_page()

            # Small delay to let the click effect take place
            await asyncio.sleep(0.5)

            # Check for validation errors first - if there are validation errors after a button click,
            # it usually means the click didn't achieve its intended purpose
            validation_errors = await self._detect_form_validation_errors()
            if validation_errors:
                logger.warning(f"Verification failed: Form validation errors after click: {validation_errors}")
                return False

            # For radio buttons and checkboxes, verify they are checked/selected
            # Check element_info first, then fallback to selector/step_type detection
            is_radio_or_checkbox = False
            element_type = None

            if element_info and element_info.get('element_type') in ['radio', 'checkbox']:
                is_radio_or_checkbox = True
                element_type = element_info.get('element_type')
                logger.info(f"Detected {element_type} from element_info")
            elif "radio" in selector.lower() or "checkbox" in selector.lower() or step_type in ["radio", "checkbox"]:
                is_radio_or_checkbox = True
                element_type = "radio" if "radio" in selector.lower() or step_type == "radio" else "checkbox"

            if is_radio_or_checkbox:
                # Try to find the actual input element to verify it's checked
                input_checked = False

                # First, try the selector directly
                elements = await self._get_elements_by_selector(selector)
                if elements:
                    element = elements[0]
                    tag_name = await self._element_get_property(element, 'tagName')
                    role = await self._element_get_property(element, 'role')
                    tag_name = tag_name.lower() if tag_name else ''
                    role = role.lower() if role else ''

                    # Handle ARIA radio buttons (button with role="radio")
                    if tag_name == 'button' and role == 'radio':
                        aria_checked = await self._element_get_property(element, 'ariaChecked')
                        input_checked = aria_checked == 'true' or aria_checked == True
                        logger.info(f"Verification: ARIA radio button (aria-checked={aria_checked}) {'is' if input_checked else 'is not'} checked")
                        return input_checked
                    elif tag_name == 'input':
                        # Direct input element
                        input_checked = await self._element_is_checked(element)
                        logger.info(f"Verification: {element_type} input {'is' if input_checked else 'is not'} checked")
                        return input_checked
                    else:
                        # Container element, need to find the radio control inside
                        logger.info(f"Verification: Selector points to {tag_name}, searching for radio control inside to verify")

                        # Strategy 1: Look for ARIA radio button
                        aria_radio_selector = f"{selector} button[role='radio']"
                        try:
                            aria_radio_elements = await self._get_elements_by_selector(aria_radio_selector)
                            if aria_radio_elements:
                                aria_checked = await self._element_get_property(aria_radio_elements[0], 'ariaChecked')
                                input_checked = aria_checked == 'true' or aria_checked == True
                                logger.info(f"Verification: ARIA radio button inside container (aria-checked={aria_checked}) {'is' if input_checked else 'is not'} checked")
                                return input_checked
                        except Exception as e:
                            logger.debug(f"Failed to verify ARIA radio button: {e}")

                        # Strategy 2: Look for traditional input
                        input_selector = f"{selector} input[type='{element_type}']"
                        try:
                            input_elements = await self._get_elements_by_selector(input_selector)
                            if input_elements:
                                input_checked = await self._element_is_checked(input_elements[0])
                                logger.info(f"Verification: {element_type} input inside container {'is' if input_checked else 'is not'} checked")
                                return input_checked
                            else:
                                logger.warning(f"Verification: Could not find {element_type} input inside container")
                                # Fallback: assume click on container was successful
                                return True
                        except Exception as e:
                            logger.warning(f"Verification: Error checking {element_type} input: {e}")
                            # Fallback: assume success
                            return True
                else:
                    logger.warning(f"Verification: {element_type} element not found")
                    return False

            # For buttons, verify the click had some effect
            elif step_type == "button" or "button" in selector.lower() or any(keyword in target_text.lower() for keyword in ['submit', 'next', 'continue', 'save', 'finish']):
                # Wait a bit for any page changes
                await asyncio.sleep(1)

                # Check for validation errors again after waiting (some forms show errors after delay)
                validation_errors = await self._detect_form_validation_errors()
                if validation_errors:
                    logger.warning(f"Verification failed: Form validation errors after button click: {validation_errors}")
                    return False

                # Try to find the button using the target_text we have
                element = None
                try:
                    # First try the original selector (only if it's not an xpath)
                    button_exists = False
                    if not selector.startswith('xpath='):
                        elements = await self._get_elements_by_selector(selector)
                        if elements:
                            element = elements[0]
                            button_exists = True

                    # If button doesn't exist with original selector, try finding by text using semantic mapping
                    if not button_exists and target_text:
                        # Try to find the button by its text using semantic mapping
                        element_info = self._find_element_by_text(target_text)
                        if element_info and element_info.get('selectors'):
                            for sel in element_info['selectors']:
                                if not sel.startswith('xpath='):
                                    elements = await self._get_elements_by_selector(sel)
                                    if elements:
                                        element = elements[0]
                                        button_exists = True
                                        break

                    # For navigation/submit buttons, check if we moved to a different section or page
                    if any(keyword in target_text.lower() for keyword in ['next', 'continue', 'submit', 'finish']):
                        # Get current URL to see if page changed
                        current_url = await page.get_url()
                        page_title = await page.get_title()
                        logger.info(f"Verification: After '{target_text}' click - URL: {current_url}, Title: {page_title}")

                        # Try to verify by checking if expected next step elements are available
                        if await self._verify_navigation_success_by_next_step(current_step):
                            logger.info(f"Verification: Navigation successful - next step elements found")
                            return True

                        # Fallback: If URL changed or title changed, likely successful navigation
                        # This is a more reliable indicator than button state for navigation buttons
                        return True

                    # If button still exists after click, verify it's clickable
                    if button_exists and element:
                        is_visible = await self._element_is_visible(element)
                        # For enabled check, we need to use CDP
                        is_enabled = not (await self._element_get_property(element, 'disabled'))
                        logger.info(f"Verification: Button '{target_text}' still exists and clickable: visible={is_visible}, enabled={is_enabled}")
                        return is_visible and is_enabled

                    # If button disappeared, this is often a sign of successful interaction
                    # (navigation, form submission, modal close, etc.)
                    else:
                        logger.info(f"Verification: Button '{target_text}' disappeared after click - likely successful interaction")
                        return True

                except Exception as e:
                    logger.info(f"Verification: Button verification had issues, assuming success: {e}")
                    return True

            # For generic clicks, just verify element is still accessible
            else:
                elements = await self._get_elements_by_selector(selector)
                if len(elements) > 0:
                    logger.info(f"Verification: Click target still exists and accessible")
                    return True
                else:
                    # Element might have disappeared due to click (like dropdown items), which could be success
                    logger.info(f"Verification: Click target disappeared (may be expected)")
                    return True

        except Exception as e:
            logger.warning(f"Click verification failed: {e}")
            return False

    async def _verify_input_action(self, selector: str, expected_value: str, input_type: str = "text") -> bool:
        """Verify that an input action succeeded by checking the element's value."""
        try:
            page = await self.browser.get_current_page()

            # Small delay to let the input effect take place
            await asyncio.sleep(0.3)

            elements = await self._get_elements_by_selector(selector)

            if elements:
                element = elements[0]
                # For radio buttons and checkboxes, check if they're selected/checked
                if input_type in ['radio', 'checkbox'] or 'radio' in selector.lower() or 'checkbox' in selector.lower():
                    is_checked = await self._element_is_checked(element)
                    expected_checked = expected_value.lower() in ['true', '1', 'on', 'yes', 'checked']
                    matches = is_checked == expected_checked
                    logger.info(f"Verification: Radio/checkbox expected checked={expected_checked}, actual checked={is_checked}, match: {matches}")
                    return matches

                # For select elements, check selected option
                elif input_type == 'select':
                    try:
                        # Check if it's a SELECT element
                        tag_name = await self._element_get_property(element, 'tagName')
                        if tag_name and tag_name.upper() == 'SELECT':
                            selected_text = await self._element_evaluate(element, '(function() { return this.options[this.selectedIndex]?.text || ""; })')
                            matches = selected_text.strip() == expected_value.strip()
                            logger.info(f"Verification: Select expected '{expected_value}', got '{selected_text}', match: {matches}")
                            return matches
                    except:
                        pass
                    # Fallback to value comparison
                    actual_value = await self._element_input_value(element)
                    matches = actual_value.strip() == expected_value.strip()
                    logger.info(f"Verification: Select (by value) expected '{expected_value}', got '{actual_value}', match: {matches}")
                    return matches

                # For text inputs and other input types
                else:
                    actual_value = await self._element_input_value(element)
                    matches = actual_value.strip() == expected_value.strip()
                    logger.info(f"Verification: Input expected '{expected_value}', got '{actual_value}', match: {matches}")
                    return matches
            else:
                logger.warning(f"Verification: Input element not found with selector {selector}")
                return False
        except Exception as e:
            logger.warning(f"Input verification failed: {e}")
            return False

    async def _verify_navigation_action(self, expected_url: str) -> bool:
        """Verify that navigation succeeded by checking current URL."""
        try:
            page = await self.browser.get_current_page()
            current_url = await page.get_url()

            # Normalize URLs for comparison
            def normalize_url(url: str) -> str:
                if not url:
                    return ""
                if '#' in url:
                    url = url.split('#')[0]
                return url.rstrip('/')

            current_normalized = normalize_url(current_url)
            expected_normalized = normalize_url(expected_url)

            matches = current_normalized == expected_normalized
            logger.info(f"Verification: Current URL '{current_url}' {'matches' if matches else 'does not match'} expected '{expected_url}'")
            return matches
        except Exception as e:
            logger.warning(f"Navigation verification failed: {e}")
            return False

    async def execute_extract_step(self, step: ExtractStep) -> ActionResult:
        """Execute AI extraction step using LLM for intelligent content extraction."""
        page = await self.browser.get_current_page()

        try:
            if not self.page_extraction_llm:
                # Fallback to basic extraction if no LLM is available
                logger.warning("No page_extraction_llm provided - using basic content extraction")
                page_text = await page.evaluate('() => document.body.innerText')
                extracted_data = {
                    "extraction_goal": step.extractionGoal,
                    "page_url": await page.get_url(),
                    "page_title": await page.get_title(),
                    "page_text_preview": page_text[:1000] + "..." if len(page_text) > 1000 else page_text,
                    "note": "Basic extraction - no LLM available for intelligent extraction"
                }

                msg = f"🤖 Basic extraction: {step.extractionGoal}"
                logger.info(msg)
                return ActionResult(
                    extracted_content=msg,
                    include_in_memory=True,
                    extracted_data=extracted_data
                )

            # AI-powered extraction using LLM
            import markdownify

            logger.info(f"🤖 Starting AI extraction: {step.extractionGoal}")

            # Convert page HTML to clean markdown, removing unnecessary elements
            strip_tags = ['a', 'img', 'script', 'style', 'nav', 'header', 'footer']
            # Get page HTML content using CDP evaluate
            html_content = await page.evaluate('() => document.documentElement.outerHTML')
            markdown_content = markdownify.markdownify(html_content, strip=strip_tags)

            # Note: iframe content extraction is not yet supported in CDP-based implementation
            # TODO: Implement iframe content extraction using CDP

            # Limit content size to avoid token limits (keep most relevant content)
            max_content_length = 50000  # Adjust based on your LLM's context window
            if len(markdown_content) > max_content_length:
                # Try to keep the beginning and end, which often contain the most relevant info
                content_start = markdown_content[:max_content_length // 2]
                content_end = markdown_content[-(max_content_length // 2):]
                markdown_content = content_start + "\n\n... [CONTENT TRUNCATED] ...\n\n" + content_end
                logger.info(f"Content truncated to {max_content_length} characters for LLM processing")

            # Create extraction prompt
            extraction_prompt = """You are an expert at extracting structured information from web pages.

Your task is to analyze the provided page content and extract information based on the specific goal.

EXTRACTION GOAL: {goal}

PAGE URL: {url}
PAGE TITLE: {title}

PAGE CONTENT:
{content}

Instructions:
1. Focus specifically on the extraction goal provided
2. Extract all relevant information that matches the goal
3. Structure the information clearly and logically
4. If the goal asks for specific data formats (JSON, tables, lists), provide that format
5. If no relevant information is found, clearly state that
6. Be comprehensive but concise
7. Include any relevant context or metadata that would be useful

EXTRACTED INFORMATION:"""

            # Format the prompt with page data
            formatted_prompt = extraction_prompt.format(
                goal=step.extractionGoal,
                url=await page.get_url(),
                title=await page.get_title(),
                content=markdown_content
            )

            # Call LLM for extraction
            logger.info("Sending extraction request to LLM...")
            try:
                llm_response = await self.page_extraction_llm.ainvoke(formatted_prompt)
                extracted_content = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)

                # Create structured extracted data
                extracted_data = {
                    "extraction_goal": step.extractionGoal,
                    "page_url": await page.get_url(),
                    "page_title": await page.get_title(),
                    "extracted_content": extracted_content,
                    "content_length": len(markdown_content),
                    "timestamp": asyncio.get_event_loop().time(),
                    "extraction_method": "AI-powered"
                }

                msg = f"🤖 AI Extraction Complete: {step.extractionGoal}\n\nExtracted Information:\n{extracted_content}"
                logger.info(f"✅ AI extraction successful for goal: {step.extractionGoal}")

                # Log a summary of what was extracted for visibility
                content_preview = extracted_content#[:200] + "..." if len(extracted_content) > 200 else extracted_content
                logger.info(f"📋 Extracted content preview: {content_preview}")

                return ActionResult(
                    extracted_content=msg,
                    include_in_memory=True,
                    extracted_data=extracted_data
                )

            except Exception as llm_error:
                logger.error(f"LLM extraction failed: {llm_error}")
                # Fallback to providing raw content if LLM fails
                fallback_data = {
                    "extraction_goal": step.extractionGoal,
                    "page_url": await page.get_url(),
                    "page_title": await page.get_title(),
                    "raw_content": markdown_content[:2000] + "..." if len(markdown_content) > 2000 else markdown_content,
                    "error": f"LLM extraction failed: {str(llm_error)}",
                    "extraction_method": "fallback"
                }

                msg = f"🤖 Extraction Goal: {step.extractionGoal}\n\nLLM extraction failed, providing raw content:\n{fallback_data['raw_content']}"
                logger.warning(f"⚠️ LLM extraction failed, using fallback for: {step.extractionGoal}")

                return ActionResult(
                    extracted_content=msg,
                    include_in_memory=True,
                    extracted_data=fallback_data
                )

        except Exception as e:
            logger.error(f"Failed to execute extraction step: {e}")
            error_data = {
                "extraction_goal": step.extractionGoal,
                "page_url": await page.get_url(),
                "error": str(e),
                "extraction_method": "failed"
            }

            return ActionResult(
                extracted_content=f"❌ Extraction failed: {step.extractionGoal}\nError: {str(e)}",
                include_in_memory=True,
                extracted_data=error_data
            )

    async def find_element_with_context(self, target_text: str, context_hints: List[str] = None) -> Optional[Dict]:
        """Public method to find elements using hierarchical context.

        This method demonstrates how to use the enhanced hierarchical selection capabilities.

        Args:
            target_text: The text of the element to find
            context_hints: List of context hints to help disambiguate repeated elements
                          Examples: ['form', 'contact'], ['section', 'billing'], ['table', 'row 2']

        Returns:
            Element info dict if found, None otherwise

        Examples:
            # Basic usage - finds first "Submit" button
            element = await executor.find_element_with_context("Submit")

            # With context - finds "Submit" button specifically in contact form
            element = await executor.find_element_with_context("Submit", ["contact", "form"])

            # Table/list context - finds specific item in a list
            element = await executor.find_element_with_context("Edit", ["item 2 of 5"])

            # Hierarchical context - finds element in specific container
            element = await executor.find_element_with_context("First Name", ["billing", "section"])
        """
        if not self.current_mapping:
            await self._refresh_semantic_mapping()

        if context_hints:
            return self.semantic_extractor.find_element_by_hierarchy(
                self.current_mapping, target_text, context_hints
            )
        else:
            return self._find_element_by_text(target_text, context_hints)

    async def find_element_in_container(self, target_text: str, container_selector: str = None, container_text: str = None) -> Optional[Dict]:
        """Find an element within a specific container by first locating the container.

        This is more reliable than complex CSS selectors for nested elements.

        Args:
            target_text: The text of the element to find (e.g., "Edit", "Submit")
            container_selector: CSS selector for the container (e.g., "#user-table tr:nth-of-type(2)")
            container_text: Text content to identify the container (e.g., "John Doe")

        Returns:
            Element info dict with dynamically generated selector
        """
        if not self.current_mapping:
            await self._refresh_semantic_mapping()

        page = await self.browser.get_current_page()

        try:
            # Step 1: Find the container
            container_element = None

            if container_selector:
                # Use provided selector
                container_elements = await page.query_selector_all(container_selector)
                if container_elements:
                    container_element = container_elements[0]
                    logger.info(f"Found container using selector: {container_selector}")

            elif container_text:
                # Find container by text content using XPath
                xpath_query = f"xpath=//*[contains(text(), '{container_text}')]/ancestor-or-self::tr | //*[contains(text(), '{container_text}')]/ancestor-or-self::section | //*[contains(text(), '{container_text}')]/ancestor-or-self::form"
                container_element = await page.query_selector(xpath_query)
                if container_element:
                    logger.info(f"Found container containing text: {container_text}")

            if not container_element:
                logger.warning(f"Could not find container for {target_text}")
                return None

            # Step 2: Find the target element within the container
            target_elements = await container_element.query_selector_all(f"button, input, select, a, [role='button']")

            for element in target_elements:
                element_text = await element.text_content()
                if element_text and target_text.lower() in element_text.lower().strip():
                    # Generate a dynamic selector for this element
                    element_id = await element.get_attribute('id')
                    element_class = await element.get_attribute('class')
                    element_tag_upper = await self._element_get_property(element, 'tagName')
                    element_tag = element_tag_upper.lower() if element_tag_upper else 'unknown'

                    # Build selector
                    if element_id:
                        dynamic_selector = f"#{element_id}"
                    elif element_class:
                        classes = element_class.split()[0] if element_class.split() else ''
                        dynamic_selector = f"{element_tag}.{classes}" if classes else element_tag
                    else:
                        dynamic_selector = element_tag

                    # Make it specific to the container
                    if container_selector:
                        final_selector = f"{container_selector} {dynamic_selector}"
                    else:
                        # Generate container selector on the fly
                        container_id = await container_element.get_attribute('id')
                        container_class = await container_element.get_attribute('class')
                        container_tag_upper = await self._element_get_property(container_element, 'tagName')
                        container_tag = container_tag_upper.lower() if container_tag_upper else 'unknown'

                        if container_id:
                            container_sel = f"#{container_id}"
                        elif container_class:
                            first_class = container_class.split()[0] if container_class.split() else ''
                            container_sel = f"{container_tag}.{first_class}" if first_class else container_tag
                        else:
                            container_sel = container_tag

                        final_selector = f"{container_sel} {dynamic_selector}"

                    logger.info(f"Found '{target_text}' in container: {final_selector}")

                    # Return element info in the same format as semantic mapping
                    return {
                        'selectors': final_selector,
                        'hierarchical_selector': final_selector,
                        'fallback_selector': dynamic_selector,
                        'text_xpath': f"//*[contains(text(), '{target_text}')]",
                        'element_type': 'button',
                        'original_text': element_text.strip(),
                        'class': element_class or '',
                        'id': element_id or ''
                    }

            logger.warning(f"Could not find '{target_text}' within the container")
            return None

        except Exception as e:
            logger.error(f"Error in find_element_in_container: {e}")
            return None

    async def list_available_elements_with_context(self) -> Dict[str, Dict]:
        """List all available elements showing their hierarchical context.

        This helps debug issues with repeated text by showing the context added to each element.

        Returns:
            Dictionary mapping display text -> element info, showing how duplicates are resolved
        """
        if not self.current_mapping:
            await self._refresh_semantic_mapping()

        logger.info("=== Available Elements with Hierarchical Context ===")
        for text, element_info in self.current_mapping.items():
            original_text = element_info.get('original_text', text)
            container_context = element_info.get('container_context', {})
            sibling_context = element_info.get('sibling_context', {})

            context_parts = []
            if container_context:
                container_type = container_context.get('type', '')
                container_text = container_context.get('text', '')
                if container_text:
                    context_parts.append(f"in {container_text}")
                elif container_type:
                    context_parts.append(f"in {container_type}")

            if sibling_context and sibling_context.get('total', 0) > 1:
                pos = sibling_context.get('position', 0) + 1
                total = sibling_context.get('total', 0)
                context_parts.append(f"item {pos} of {total}")

            context_desc = ", ".join(context_parts) if context_parts else "no context"
            logger.info(f"  '{text}' -> {element_info.get('selectors', 'N/A')} ({context_desc})")

        return self.current_mapping

    async def select_calendar_date(self, date_value: str, calendar_type: str = "departure") -> Optional[Dict]:
        """Select a date from a calendar widget.

        Args:
            date_value: The date to select (format: YYYY-MM-DD, MM/DD/YYYY, or natural language)
            calendar_type: Type of calendar - "departure", "return", or "general"

        Returns:
            Element info if successful, None otherwise
        """
        if not self.current_mapping:
            await self._refresh_semantic_mapping()

        page = await self.browser.get_current_page()

        try:
            # First, try to find calendar elements with the specific date
            for text, element_info in self.current_mapping.items():
                container_context = element_info.get('container_context', {})
                widget_data = element_info.get('widget_data', {})

                # Check if this is a calendar element
                if container_context.get('widget_type') == 'calendar':
                    # Check if date matches
                    element_date = widget_data.get('date_value') or element_info.get('text_content', '')

                    if self._date_matches(date_value, element_date):
                        # Check if it's the right calendar type
                        date_type = container_context.get('date_type', 'general')
                        if calendar_type == "general" or date_type == calendar_type:
                            logger.info(f"Found calendar date: {date_value} in {calendar_type} calendar")
                            return element_info

            # Fallback: Try to find by aria-label or text content
            date_patterns = self._generate_date_patterns(date_value)
            for pattern in date_patterns:
                # Look for elements with matching aria-label or text
                calendar_element = await page.query_selector(
                    f'[role="gridcell"][aria-label*="{pattern}"], '
                    f'[data-date*="{pattern}"], '
                    f'.calendar-day:has-text("{pattern}"), '
                    f'.day:has-text("{pattern}")'
                )

                if calendar_element:
                    # Generate dynamic element info
                    element_id = await calendar_element.get_attribute('id')
                    element_class = await calendar_element.get_attribute('class')

                    selector = f"#{element_id}" if element_id else f".{element_class.split()[0]}" if element_class else "[role='gridcell']"

                    return {
                        'selectors': selector,
                        'hierarchical_selector': selector,
                        'fallback_selector': f'[aria-label*="{pattern}"]',
                        'element_type': 'calendar',
                        'date_value': date_value,
                        'calendar_type': calendar_type
                    }

            logger.warning(f"Could not find calendar date: {date_value}")
            return None

        except Exception as e:
            logger.error(f"Error selecting calendar date: {e}")
            return None

    async def select_dropdown_option(self, option_text: str, dropdown_context: str = None) -> Optional[Dict]:
        """Select an option from a dropdown menu.

        Args:
            option_text: The text of the option to select
            dropdown_context: Context to identify the specific dropdown (e.g., "travelers", "cabin class")

        Returns:
            Element info if successful, None otherwise
        """
        if not self.current_mapping:
            await self._refresh_semantic_mapping()

        page = await self.browser.get_current_page()

        try:
            # First, try to find dropdown options in semantic mapping
            for text, element_info in self.current_mapping.items():
                container_context = element_info.get('container_context', {})

                # Check if this is a dropdown element
                if container_context.get('widget_type') == 'dropdown':
                    # Check if option text matches
                    if option_text.lower() in text.lower():
                        # Check dropdown context if specified
                        if dropdown_context:
                            dropdown_purpose = container_context.get('dropdown_purpose', '')
                            if dropdown_context.lower() not in dropdown_purpose.lower():
                                continue

                        logger.info(f"Found dropdown option: {option_text}")
                        return element_info

            # Fallback: Try to find dropdown options directly
            option_selectors = [
                f'[role="option"]:has-text("{option_text}")',
                f'[role="menuitem"]:has-text("{option_text}")',
                f'.option:has-text("{option_text}")',
                f'.menu-item:has-text("{option_text}")',
                f'[data-value*="{option_text.lower()}"]'
            ]

            for selector in option_selectors:
                try:
                    option_element = await page.query_selector(selector)
                    if option_element:
                        return {
                            'selectors': selector,
                            'hierarchical_selector': selector,
                            'fallback_selector': f':has-text("{option_text}")',
                            'element_type': 'dropdown',
                            'option_text': option_text,
                            'dropdown_context': dropdown_context
                        }
                except:
                    continue

            logger.warning(f"Could not find dropdown option: {option_text}")
            return None

        except Exception as e:
            logger.error(f"Error selecting dropdown option: {e}")
            return None

    async def select_flight_option(self, criteria: Dict) -> Optional[Dict]:
        """Select a flight option based on criteria.

        Args:
            criteria: Dictionary with flight selection criteria
                     e.g., {"price_range": "200-300", "airline": "Southwest", "time": "morning"}

        Returns:
            Element info if successful, None otherwise
        """
        if not self.current_mapping:
            await self._refresh_semantic_mapping()

        try:
            # Find flight/booking elements
            flight_options = []

            for text, element_info in self.current_mapping.items():
                container_context = element_info.get('container_context', {})

                # Check if this is a booking element
                if container_context.get('widget_type') == 'booking':
                    flight_options.append((text, element_info, container_context))

            # Score flight options based on criteria
            best_option = None
            best_score = 0

            for text, element_info, context in flight_options:
                score = self._score_flight_option(criteria, context, text)
                if score > best_score:
                    best_score = score
                    best_option = element_info

            if best_option:
                logger.info(f"Selected flight option with score: {best_score}")
                return best_option

            logger.warning("Could not find suitable flight option")
            return None

        except Exception as e:
            logger.error(f"Error selecting flight option: {e}")
            return None

    async def handle_dynamic_content_loading(self, trigger_element: Dict, expected_content: str, timeout: int = 10000) -> bool:
        """Handle dynamic content loading after triggering an action.

        Args:
            trigger_element: Element that triggers content loading
            expected_content: Text or selector that should appear after loading
            timeout: Maximum time to wait in milliseconds

        Returns:
            True if content loaded successfully, False otherwise
        """
        page = await self.browser.get_current_page()

        try:
            # Click the trigger element
            selector = trigger_element.get('selectors')
            if not selector:
                return False

            # Click the element to trigger dynamic content loading
            elements = await self._get_elements_by_selector(selector)
            if elements:
                await elements[0].click()
                logger.info(f"Triggered dynamic content loading with: {selector}")
            else:
                logger.warning(f"Trigger element not found: {selector}")
                return False

            # Wait for expected content to appear
            try:
                # Try multiple strategies to detect content loading
                await page.wait_for_selector(
                    f':has-text("{expected_content}")',
                    timeout=timeout
                )
                logger.info(f"Dynamic content loaded: {expected_content}")
                return True

            except:
                # Wait for dynamic content to load
                await asyncio.sleep(timeout / 1000)  # Convert ms to seconds
                logger.info("Dynamic content loading completed (timeout-based)")
                return True

        except Exception as e:
            logger.error(f"Error handling dynamic content loading: {e}")
            return False

    def _date_matches(self, target_date: str, element_date: str) -> bool:
        """Check if two date strings match allowing for different formats."""
        import re
        from datetime import datetime

        try:
            # Normalize both dates
            target_normalized = self._normalize_date(target_date)
            element_normalized = self._normalize_date(element_date)

            return target_normalized == element_normalized
        except:
            # Fallback to string matching
            return target_date.lower() in element_date.lower() or element_date.lower() in target_date.lower()

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to YYYY-MM-DD format."""
        import re
        from datetime import datetime

        # Remove extra whitespace and common words
        date_str = re.sub(r'\b(day|date|select)\b', '', date_str.lower()).strip()

        # Try common date formats
        formats = [
            '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y',
            '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y'
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except:
                continue

        return date_str

    def _generate_date_patterns(self, date_value: str) -> List[str]:
        """Generate different patterns for finding a date."""
        patterns = [date_value]

        try:
            from datetime import datetime

            # Try to parse the date and generate alternative formats
            dt = datetime.strptime(date_value, '%Y-%m-%d')
            patterns.extend([
                dt.strftime('%m/%d/%Y'),
                dt.strftime('%d/%m/%Y'),
                dt.strftime('%B %d, %Y'),
                dt.strftime('%b %d, %Y'),
                dt.strftime('%d %B %Y'),
                dt.strftime('%d'),  # Just the day
                dt.strftime('%B'),  # Just the month
            ])
        except:
            pass

        return patterns

    def _score_flight_option(self, criteria: Dict, context: Dict, text: str) -> int:
        """Score a flight option based on selection criteria."""
        score = 0

        # Price scoring
        if 'price_range' in criteria:
            price_range = criteria['price_range']
            context_price = context.get('price', '')
            if self._price_in_range(context_price, price_range):
                score += 3

        # Airline scoring
        if 'airline' in criteria:
            airline = criteria['airline'].lower()
            context_airline = context.get('airline', '').lower()
            if airline in context_airline:
                score += 2

        # Time preference scoring
        if 'time' in criteria:
            time_pref = criteria['time'].lower()
            context_time = context.get('time_info', '').lower()
            if time_pref in context_time:
                score += 2

        # Selection button priority
        if 'select' in text.lower():
            score += 1

        return score

    def _price_in_range(self, price_str: str, price_range: str) -> bool:
        """Check if price falls within specified range."""
        import re

        try:
            # Extract numeric price
            price_match = re.search(r'\$?(\d+)', price_str)
            if not price_match:
                return False

            price = int(price_match.group(1))

            # Parse range
            range_parts = price_range.split('-')
            if len(range_parts) == 2:
                min_price = int(range_parts[0])
                max_price = int(range_parts[1])
                return min_price <= price <= max_price
        except:
            pass

        return False
