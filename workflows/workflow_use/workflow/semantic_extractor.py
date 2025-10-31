import asyncio
import logging
import re
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import aiofiles

if TYPE_CHECKING:
	from browser_use.actor.page import Page

logger = logging.getLogger(__name__)


class SemanticExtractor:
	"""Extracts semantic mappings from HTML pages by mapping visible text to deterministic selectors."""

	def __init__(self):
		self.element_counters = {'input': 0, 'button': 0, 'select': 0, 'textarea': 0, 'a': 0, 'radio': 0, 'checkbox': 0}

	def _reset_counters(self):
		"""Reset element counters for a new page."""
		self.element_counters = {'input': 0, 'button': 0, 'select': 0, 'textarea': 0, 'a': 0, 'radio': 0, 'checkbox': 0}

	def _get_element_type_and_id(self, element_info: Dict) -> Tuple[str, str]:
		"""Determine element type and generate deterministic ID."""
		tag = element_info.get('tag', '').lower()
		input_type = element_info.get('type', '').lower()
		role = element_info.get('role', '').lower()

		# Determine element type
		# Check role-based types first (ARIA widgets can use any tag)
		if role == 'radio':
			element_type = 'radio'
		elif role == 'checkbox':
			element_type = 'checkbox'
		elif tag == 'input':
			if input_type in ['radio']:
				element_type = 'radio'
			elif input_type in ['checkbox']:
				element_type = 'checkbox'
			else:
				element_type = 'input'
		elif tag == 'button' or role == 'button':
			element_type = 'button'
		elif tag == 'select':
			element_type = 'select'
		elif tag == 'textarea':
			element_type = 'textarea'
		elif tag == 'a':
			element_type = 'a'
		else:
			element_type = 'input'  # fallback

		# Generate ID
		self.element_counters[element_type] += 1
		element_id = f'{element_type}_{self.element_counters[element_type]}'

		return element_type, element_id

	def _normalize_text(self, text: str) -> str:
		"""Normalize text for consistent mapping."""
		if not text:
			return ''
		# Remove extra whitespace and normalize
		return re.sub(r'\s+', ' ', text.strip())

	def _get_element_text(self, element_info: Dict) -> str:
		"""Extract meaningful text from element information."""
		# Priority order for text extraction
		text_sources = [
			element_info.get('label_text', ''),
			element_info.get('text_content', ''),
			element_info.get('placeholder', ''),
			element_info.get('title', ''),
			element_info.get('aria_label', ''),
			element_info.get('value', ''),
			element_info.get('name', ''),
			element_info.get('id', ''),
		]

		for text in text_sources:
			if text and text.strip():
				return self._normalize_text(text)

		return ''

	def _create_fallback_text(self, element_info: Dict, element_type: str, element_id: str) -> str:
		"""Create fallback text for elements without meaningful text."""
		tag = element_info.get('tag', '').lower()

		if tag == 'button' or element_type == 'button':
			return '[Button]'
		elif element_type == 'input':
			input_type = element_info.get('type', 'text').lower()
			return f'[Input Field - {input_type}]'
		elif element_type == 'select':
			return '[Dropdown]'
		elif element_type == 'textarea':
			return '[Text Area]'
		elif element_type == 'radio':
			return '[Radio Button]'
		elif element_type == 'checkbox':
			return '[Checkbox]'
		else:
			return f'[{tag.upper()} Element]'

	def _get_hierarchical_context(self, element_info: Dict) -> List[str]:
		"""Extract hierarchical context for better duplicate handling."""
		contexts = []

		# Add parent context with hierarchy levels
		parent_text = element_info.get('parent_text', '')
		if parent_text:
			# Truncate long parent text but keep meaningful parts
			if len(parent_text) > 50:
				parent_text = parent_text[:47] + '...'
			contexts.append(f'in {parent_text}')

		# Add container context (section, fieldset, div with meaningful class/id)
		container_info = element_info.get('container_context', {})
		if container_info:
			container_type = container_info.get('type', '')
			container_text = container_info.get('text', '')
			container_id = container_info.get('id', '')

			if container_text:
				context_desc = f'in {container_type}'
				if container_text and len(container_text) <= 30:
					context_desc = f'in {container_text}'
				elif container_id:
					context_desc = f'in {container_type}#{container_id}'
				contexts.append(context_desc)

		# Add sibling context (for elements in lists or tables)
		sibling_info = element_info.get('sibling_context', {})
		if sibling_info:
			sibling_position = sibling_info.get('position', 0)
			sibling_total = sibling_info.get('total', 0)
			if sibling_total > 1:
				contexts.append(f'item {sibling_position + 1} of {sibling_total}')

		# Add DOM position context
		dom_path = element_info.get('dom_path', '')
		if dom_path:
			# Extract meaningful parts of the DOM path
			path_parts = dom_path.split(' > ')
			if len(path_parts) > 3:
				# Keep first, last, and any parts with meaningful identifiers
				meaningful_parts = []
				for part in path_parts:
					if any(
						keyword in part.lower() for keyword in ['form', 'section', 'header', 'nav', 'main', 'aside', 'footer']
					):
						meaningful_parts.append(part)

				if meaningful_parts:
					contexts.append(f'in {" > ".join(meaningful_parts[-2:])}')

		return contexts

	def _handle_duplicate_text(self, text: str, existing_keys: set, element_info: Dict) -> str:
		"""Handle duplicate text by adding hierarchical context."""
		if text not in existing_keys:
			return text

		# Get hierarchical contexts
		contexts = self._get_hierarchical_context(element_info)

		# Try contexts in order of preference (most specific first)
		for context in contexts:
			candidate = f'{text} ({context})'
			if candidate not in existing_keys:
				return candidate

		# Fallback contexts if hierarchical ones don't work
		fallback_contexts = []

		# Add position-based context (less preferred but still useful)
		position = element_info.get('position', {})
		if position:
			fallback_contexts.append(f'at {position.get("x", 0)},{position.get("y", 0)}')

		# Add attribute context
		if element_info.get('id'):
			fallback_contexts.append(f'id:{element_info["id"]}')
		elif element_info.get('name'):
			fallback_contexts.append(f'name:{element_info["name"]}')
		elif element_info.get('class'):
			class_parts = element_info['class'].split()[:2]  # First two classes
			if class_parts:
				fallback_contexts.append(f'class:{".".join(class_parts)}')

		# Try fallback contexts
		for context in fallback_contexts:
			candidate = f'{text} ({context})'
			if candidate not in existing_keys:
				return candidate

		# Final fallback with index
		counter = 2
		while f'{text} ({counter})' in existing_keys:
			counter += 1

		return f'{text} ({counter})'

	async def extract_interactive_elements(self, page: 'Page') -> List[Dict]:
		"""Extract interactive elements with enhanced context for complex UI widgets."""

		# Add debugging flag
		debug_mode = False  # Set to True for debugging

		js_code = """
        (debugMode = false) => {
            const debugLog = [];
            
            function debugMessage(msg, data = null) {
                if (debugMode) {
                    console.log('[SEMANTIC_DEBUG]', msg, data);
                    debugLog.push({ message: msg, data: data, timestamp: Date.now() });
                }
            }
            
            debugMessage('Starting semantic extraction');
            
            // Enhanced selector for complex UI widgets
            const interactiveSelectors = [
                'button', 'input', 'select', 'textarea', 'a[href]',
                '[role="button"]', '[role="link"]', '[role="tab"]', '[role="menuitem"]',
                '[role="option"]', '[role="checkbox"]', '[role="radio"]',
                '[role="combobox"]', '[role="listbox"]', '[role="slider"]',
                '[role="spinbutton"]', '[role="searchbox"]', '[role="switch"]',
                '[onclick]', '[onchange]', '[onsubmit]',
                // Calendar and date picker elements
                '[role="gridcell"]', '[role="calendar"]', '[role="datepicker"]',
                '.calendar-day', '.date-picker', '.day', '.month', '.year',
                '[data-date]', '[data-day]', '[data-month]', '[data-year]',
                // Dropdown and menu elements
                '[role="menu"]', '[role="menubar"]', '[role="menuitem"]',
                '.dropdown', '.menu-item', '.option', '.select-option',
                '[data-value]', '[data-option]',
                // Dynamic content elements
                '[data-testid]', '[data-cy]', '[data-qa]',
                // Flight/travel specific elements
                '.flight-option', '.price', '.select-flight', '.book-now',
                '[data-flight]', '[data-price]', '.fare-option'
            ].join(', ');
            
            const elements = [];
            let allElements;
            
            try {
                allElements = document.querySelectorAll(interactiveSelectors);
                debugMessage(`Found ${allElements.length} potential interactive elements`);
            } catch (error) {
                debugMessage('Error selecting elements', error.message);
                return { elements: [], debugLog: debugLog, error: error.message };
            }
            
            // Enhanced context extraction functions with error handling
            function safeGetWidgetType(el) {
                try {
                    // Detect widget types based on various indicators
                    const role = el.getAttribute('role') || '';
                    const className = (el.className || '').toString().toLowerCase();
                    const tagName = el.tagName.toLowerCase();
                    const dataAttrs = Array.from(el.attributes || [])
                        .filter(attr => attr.name && attr.name.startsWith('data-'))
                        .map(attr => attr.name);
                    
                    // Calendar detection
                    if (role === 'gridcell' || role === 'calendar' || 
                        className.includes('calendar') || className.includes('date') ||
                        dataAttrs.some(attr => attr.includes('date') || attr.includes('day'))) {
                        return 'calendar';
                    }
                    
                    // Dropdown detection
                    if (role === 'option' || role === 'menuitem' || role === 'combobox' ||
                        className.includes('dropdown') || className.includes('option') ||
                        className.includes('menu')) {
                        return 'dropdown';
                    }
                    
                    // Flight/booking specific
                    if (className.includes('flight') || className.includes('select') ||
                        className.includes('book') || className.includes('fare') ||
                        dataAttrs.some(attr => attr.includes('flight') || attr.includes('price'))) {
                        return 'booking';
                    }
                    
                    // Form controls
                    if (tagName === 'input' || tagName === 'select' || tagName === 'textarea') {
                        return 'form';
                    }
                    
                    // Navigation/action buttons
                    if (tagName === 'button' || role === 'button' || tagName === 'a') {
                        return 'action';
                    }
                    
                    return 'generic';
                } catch (error) {
                    debugMessage('Error in safeGetWidgetType', { element: el.tagName, error: error.message });
                    return 'error';
                }
            }
            
            function safeGetCalendarContext(el) {
                try {
                    const context = {};
                    
                    // Try to find date information
                    const dateAttr = el.getAttribute('data-date') || 
                                   el.getAttribute('data-day') ||
                                   el.getAttribute('aria-label');
                    
                    if (dateAttr) {
                        context.date_value = dateAttr;
                    }
                    
                    // Find calendar container
                    const calendar = el.closest('[role="calendar"], .calendar, .date-picker, .datepicker');
                    if (calendar) {
                        context.calendar_type = calendar.className || 'calendar';
                        
                        // Try to determine if it's departure or return date
                        const calendarContainer = calendar.closest('[data-testid], [class*="depart"], [class*="return"]');
                        if (calendarContainer) {
                            const containerClass = (calendarContainer.className || '').toLowerCase();
                            if (containerClass.includes('depart')) {
                                context.date_type = 'departure';
                            } else if (containerClass.includes('return')) {
                                context.date_type = 'return';
                            }
                        }
                    }
                    
                    // Check for month/year context
                    const monthYear = el.closest('.month, .year, [data-month], [data-year]');
                    if (monthYear) {
                        context.period_context = monthYear.textContent?.trim() || monthYear.getAttribute('data-month') || monthYear.getAttribute('data-year');
                    }
                    
                    return context;
                } catch (error) {
                    debugMessage('Error in safeGetCalendarContext', error.message);
                    return {};
                }
            }
            
            function safeGetDropdownContext(el) {
                try {
                    const context = {};
                    
                    // Find dropdown container
                    const dropdown = el.closest('[role="listbox"], [role="menu"], .dropdown, .select-menu');
                    if (dropdown) {
                        context.dropdown_type = dropdown.className || 'dropdown';
                        
                        // Try to determine dropdown purpose
                        const label = dropdown.closest('label') || 
                                     document.querySelector(`label[for="${dropdown.id}"]`) ||
                                     dropdown.previousElementSibling;
                        
                        if (label) {
                            context.dropdown_purpose = label.textContent?.trim();
                        }
                    }
                    
                    // Get option value and text
                    const value = el.getAttribute('data-value') || el.getAttribute('value');
                    if (value) {
                        context.option_value = value;
                    }
                    
                    return context;
                } catch (error) {
                    debugMessage('Error in safeGetDropdownContext', error.message);
                    return {};
                }
            }
            
            function safeGetBookingContext(el) {
                try {
                    const context = {};
                    
                    // Find flight/booking container
                    const bookingContainer = el.closest('.flight-option, .booking-option, [data-flight]');
                    if (bookingContainer) {
                        // Extract flight details
                        const priceEl = bookingContainer.querySelector('.price, [data-price], .fare');
                        if (priceEl) {
                            context.price = priceEl.textContent?.trim();
                        }
                        
                        const airlineEl = bookingContainer.querySelector('.airline, .carrier');
                        if (airlineEl) {
                            context.airline = airlineEl.textContent?.trim();
                        }
                        
                        const timeEl = bookingContainer.querySelector('.time, .departure, .arrival');
                        if (timeEl) {
                            context.time_info = timeEl.textContent?.trim();
                        }
                        
                        // Try to determine if it's outbound or return flight
                        const flightType = bookingContainer.closest('[data-direction], [class*="outbound"], [class*="return"]');
                        if (flightType) {
                            const typeClass = (flightType.className || '').toLowerCase();
                            if (typeClass.includes('outbound')) {
                                context.flight_direction = 'outbound';
                            } else if (typeClass.includes('return')) {
                                context.flight_direction = 'return';
                            }
                        }
                    }
                    
                    return context;
                } catch (error) {
                    debugMessage('Error in safeGetBookingContext', error.message);
                    return {};
                }
            }
            
            // Helper functions that were missing (with error handling)
            function safeGetContainerContext(el) {
                try {
                    const context = {};
                    
                    // Find the closest meaningful container
                    const container = el.closest('section, form, fieldset, div[class], div[id], article, main, aside');
                    if (container) {
                        context.type = container.tagName.toLowerCase();
                        context.id = container.id || '';
                        context.className = container.className || '';
                        
                        // Get container text (first few words)
                        const containerText = container.textContent?.trim();
                        if (containerText) {
                            const words = containerText.split(/\\s+/).slice(0, 5).join(' ');
                            context.text = words.length < containerText.length ? words + '...' : words;
                        }
                    }
                    
                    return context;
                } catch (error) {
                    debugMessage('Error in safeGetContainerContext', error.message);
                    return {};
                }
            }
            
            function safeGetSiblingContext(el) {
                try {
                    const context = {};
                    const parent = el.parentElement;
                    
                    if (parent) {
                        const siblings = Array.from(parent.children).filter(child => 
                            child.tagName === el.tagName || 
                            child.getAttribute('role') === el.getAttribute('role')
                        );
                        
                        if (siblings.length > 1) {
                            context.position = siblings.indexOf(el);
                            context.total = siblings.length;
                        }
                    }
                    
                    return context;
                } catch (error) {
                    debugMessage('Error in safeGetSiblingContext', error.message);
                    return {};
                }
            }
            
            function safeGetDOMPath(el) {
                try {
                    const path = [];
                    let current = el;
                    
                    while (current && current !== document.body && path.length < 5) {
                        let selector = current.tagName.toLowerCase();
                        
                        if (current.id) {
                            selector += `#${current.id}`;
                            path.unshift(selector);
                            break;
                        } else if (current.className) {
                            const firstClass = (current.className || '').toString().split(' ')[0];
                            if (firstClass && firstClass.match(/^[a-zA-Z_-][a-zA-Z0-9_-]*$/)) {
                                selector += `.${firstClass}`;
                            }
                        }
                        
                        // Add nth-of-type if needed
                        const siblings = Array.from(current.parentElement?.children || [])
                            .filter(el => el.tagName === current.tagName);
                        if (siblings.length > 1) {
                            const index = siblings.indexOf(current) + 1;
                            selector += `:nth-of-type(${index})`;
                        }
                        
                        path.unshift(selector);
                        current = current.parentElement;
                    }
                    
                    return path.join(' > ');
                } catch (error) {
                    debugMessage('Error in safeGetDOMPath', error.message);
                    return '';
                }
            }
            
            function safeGetLabelText(el) {
                try {
                    // Try to find associated label
                    let labelText = '';
                    
                    if (el.id) {
                        const label = document.querySelector(`label[for="${el.id}"]`);
                        if (label) {
                            labelText = label.textContent?.trim() || '';
                        }
                    }
                    
                    if (!labelText) {
                        const label = el.closest('label');
                        if (label) {
                            labelText = label.textContent?.trim() || '';
                        }
                    }
                    
                    if (!labelText) {
                        const prevElement = el.previousElementSibling;
                        if (prevElement && (prevElement.tagName === 'LABEL' || prevElement.textContent)) {
                            labelText = prevElement.textContent?.trim() || '';
                        }
                    }

                    // IMPORTANT: Handle table structures where label is in previous <td>
                    if (!labelText) {
                        const parentCell = el.closest('td, th');
                        if (parentCell) {
                            const prevCell = parentCell.previousElementSibling;
                            if (prevCell && (prevCell.tagName === 'TD' || prevCell.tagName === 'TH')) {
                                const cellText = prevCell.textContent?.trim() || '';
                                // Only use if it looks like a label (short text, ends with colon, etc.)
                                if (cellText && cellText.length < 50) {
                                    labelText = cellText.replace(/[:：]\s*$/, '').trim();
                                }
                            }
                        }
                    }

                    return labelText;
                } catch (error) {
                    debugMessage('Error in safeGetLabelText', error.message);
                    return '';
                }
            }
            
            function safeGetParentText(el) {
                try {
                    const parent = el.parentElement;
                    if (!parent) return '';
                    
                    // Get direct text content of parent (not including children)
                    const parentText = Array.from(parent.childNodes)
                        .filter(node => node.nodeType === Node.TEXT_NODE)
                        .map(node => node.textContent?.trim())
                        .filter(text => text)
                        .join(' ');
                    
                    return parentText;
                } catch (error) {
                    debugMessage('Error in safeGetParentText', error.message);
                    return '';
                }
            }
            
            function safeGetEnhancedContainerContext(el) {
                try {
                    const context = safeGetContainerContext(el);
                    
                    // Add widget-specific context
                    const widgetType = safeGetWidgetType(el);
                    context.widget_type = widgetType;
                    
                    switch (widgetType) {
                        case 'calendar':
                            Object.assign(context, safeGetCalendarContext(el));
                            break;
                        case 'dropdown':
                            Object.assign(context, safeGetDropdownContext(el));
                            break;
                        case 'booking':
                            Object.assign(context, safeGetBookingContext(el));
                            break;
                    }
                    
                    return context;
                } catch (error) {
                    debugMessage('Error in safeGetEnhancedContainerContext', { element: el.tagName, error: error.message });
                    return { widget_type: 'error' };
                }
            }
            
            function safeGetInteractionHints(el) {
                try {
                    const hints = [];
                    const widgetType = safeGetWidgetType(el);
                    
                    switch (widgetType) {
                        case 'calendar':
                            hints.push('click_date');
                            if (el.getAttribute('aria-selected') === 'true') {
                                hints.push('selected_date');
                            }
                            break;
                        case 'dropdown':
                            hints.push('select_option');
                            if (el.getAttribute('aria-expanded') === 'true') {
                                hints.push('expanded');
                            }
                            break;
                        case 'booking':
                            hints.push('select_flight');
                            if (el.textContent?.toLowerCase().includes('select')) {
                                hints.push('selection_button');
                            }
                            break;
                    }
                    
                    return hints;
                } catch (error) {
                    debugMessage('Error in safeGetInteractionHints', error.message);
                    return [];
                }
            }
            
            // Process each element with enhanced context and error handling
            let processedCount = 0;
            let errorCount = 0;
            
            Array.from(allElements).forEach((el, index) => {
                try {
                    const rect = el.getBoundingClientRect();
                    
                    // Skip hidden elements
                    if (rect.width === 0 || rect.height === 0 || 
                        getComputedStyle(el).visibility === 'hidden' ||
                        getComputedStyle(el).display === 'none') {
                        return;
                    }
                    
                    // Get enhanced context with error handling
                    const containerContext = safeGetEnhancedContainerContext(el);
                    const interactionHints = safeGetInteractionHints(el);
                    
                    // Generate selector with error handling
                    let selector = '';
                    let hierarchicalSelector = '';
                    
                    try {
                        if (el.id) {
                            selector = `#${el.id}`;
                        } else {
                            selector = el.tagName.toLowerCase();

                            // Add specific attributes based on widget type
                            const widgetType = containerContext.widget_type;
                            if (widgetType === 'calendar' && el.getAttribute('data-date')) {
                                selector += `[data-date="${el.getAttribute('data-date')}"]`;
                            } else if (widgetType === 'dropdown' && el.getAttribute('data-value')) {
                                selector += `[data-value="${el.getAttribute('data-value')}"]`;
                            } else if (el.getAttribute('data-testid')) {
                                selector += `[data-testid="${el.getAttribute('data-testid')}"]`;
                            }

                            // Add other attributes
                            if (el.name) selector += `[name="${el.name}"]`;
                            if (el.type && el.type !== 'submit' && el.type !== 'button' && el.type !== '') {
                                selector += `[type="${el.type}"]`;
                            }
                        }
                        
                        hierarchicalSelector = safeGetDOMPath(el);
                    } catch (error) {
                        debugMessage('Error generating selector', { element: el.tagName, error: error.message });
                        selector = el.tagName.toLowerCase();
                        hierarchicalSelector = selector;
                    }
                    
                    // Enhanced text extraction
                    let elementText = '';
                    try {
                        elementText = el.textContent?.trim() || '';
                        if (!elementText && el.getAttribute('aria-label')) {
                            elementText = el.getAttribute('aria-label');
                        } else if (!elementText && el.getAttribute('title')) {
                            elementText = el.getAttribute('title');
                        } else if (!elementText && el.getAttribute('placeholder')) {
                            elementText = el.getAttribute('placeholder');
                        }
                    } catch (error) {
                        debugMessage('Error extracting text', error.message);
                    }
                    
                    const elementData = {
                        tag: el.tagName,
                        type: el.type || '',
                        role: el.getAttribute('role') || '',
                        id: el.id || '',
                        name: el.name || '',
                        class: el.className || '',
                        text_content: elementText,
                        placeholder: el.placeholder || '',
                        title: el.title || '',
                        aria_label: el.getAttribute('aria-label') || '',
                        value: el.value || '',
                        label_text: safeGetLabelText(el),
                        parent_text: safeGetParentText(el),
                        css_selector: selector,
                        hierarchical_selector: hierarchicalSelector,
                        fallback_selector: el.tagName.toLowerCase(),
                        text_xpath: elementText ? `//${el.tagName.toLowerCase()}[contains(text(), "${elementText}")]` : '',
                        dom_path: hierarchicalSelector,
                        container_context: containerContext,
                        sibling_context: safeGetSiblingContext(el),
                        interaction_hints: interactionHints,
                        widget_data: {
                            date_value: el.getAttribute('data-date'),
                            option_value: el.getAttribute('data-value'),
                            test_id: el.getAttribute('data-testid'),
                            flight_data: el.getAttribute('data-flight'),
                            price_data: el.getAttribute('data-price')
                        },
                        position: {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        }
                    };
                    
                    elements.push(elementData);
                    processedCount++;
                    
                } catch (error) {
                    errorCount++;
                    debugMessage('Error processing element', { 
                        index: index, 
                        element: el.tagName, 
                        error: error.message 
                    });
                }
            });
            
            debugMessage('Extraction complete', { 
                processed: processedCount, 
                errors: errorCount,
                total: allElements.length 
            });
            
            return {
                elements: elements,
                debugLog: debugLog,
                stats: {
                    processed: processedCount,
                    errors: errorCount,
                    total: allElements.length
                }
            };
        }
        """

		try:
			result_str = await page.evaluate(js_code, debug_mode)

			# Parse the JSON result
			import json

			result = json.loads(result_str) if isinstance(result_str, str) else result_str

			if debug_mode and 'debugLog' in result:
				# Save debug information to file
				debug_file = f'semantic_extraction_debug_{int(asyncio.get_event_loop().time())}.json'
				import json

				async with aiofiles.open(debug_file, 'w') as f:
					await f.write(json.dumps(result, indent=2))
				logger.info(f'Debug information saved to: {debug_file}')

				# Print debug stats
				stats = result.get('stats', {})
				logger.info(f'Extraction stats: {stats}')

				if 'error' in result:
					logger.error(f'JavaScript extraction error: {result["error"]}')

			return result.get('elements', [])

		except Exception as e:
			logger.error(f'Failed to extract interactive elements: {e}')
			# Save error information for debugging
			if debug_mode:
				error_file = f'semantic_extraction_error_{int(asyncio.get_event_loop().time())}.txt'
				async with aiofiles.open(error_file, 'w') as f:
					await f.write(f'Error: {str(e)}\n')
					await f.write(f'URL: {await page.get_url()}\n')
					await f.write(f'Timestamp: {asyncio.get_event_loop().time()}\n')
				logger.info(f'Error information saved to: {error_file}')

			return []

	async def extract_semantic_mapping(self, page: 'Page') -> Dict[str, Dict]:
		"""Extract semantic mapping from the current page.

		Returns mapping: visible_text -> {"class": "", "id": "", "selectors": ""}
		"""
		self._reset_counters()

		# Get all interactive elements with enhanced context
		elements = await self.extract_interactive_elements(page)

		mapping = {}
		existing_keys = set()

		for element_info in elements:
			# Determine element type and generate ID
			element_type, element_id = self._get_element_type_and_id(element_info)

			# Get meaningful text
			text = self._get_element_text(element_info)

			# Use fallback if no meaningful text found
			if not text:
				text = self._create_fallback_text(element_info, element_type, element_id)

			# Handle duplicates with hierarchical context
			final_text = self._handle_duplicate_text(text, existing_keys, element_info)
			existing_keys.add(final_text)

			# Store mapping with enhanced selector options
			mapping[final_text] = {
				'class': element_info.get('class', ''),
				'id': element_info.get('id', ''),
				'selectors': element_info['css_selector'],
				'hierarchical_selector': element_info.get('hierarchical_selector', element_info['css_selector']),
				'fallback_selector': element_info.get('fallback_selector', element_info['css_selector']),
				'text_xpath': element_info.get('text_xpath', ''),
				# Additional info for internal use
				'element_type': element_type,
				'deterministic_id': element_id,
				'original_text': text,
				'label_text': element_info.get('label_text', ''),  # IMPORTANT: Include label text for input field matching
				'dom_path': element_info.get('dom_path', ''),
				'container_context': element_info.get('container_context', {}),
				'sibling_context': element_info.get('sibling_context', {}),
				'position': element_info.get('position', {}),
			}

			logger.debug(f"Mapped '{final_text}' -> {element_info['css_selector']}")

		return mapping

	def find_element_by_text(self, mapping: Dict[str, Dict], target_text: str) -> Optional[Dict]:
		"""Find element by text with intelligent fuzzy matching and hierarchical context understanding."""
		if not target_text or not mapping:
			return None

		target_lower = target_text.lower().strip()

		# Strategy 1: Exact match (case-insensitive)
		for text, element_info in mapping.items():
			if text.lower() == target_lower:
				logger.debug(f"Exact match found: '{target_text}' -> '{text}'")
				return element_info

		# Strategy 2: Check if target looks like an element ID or name attribute
		if target_text.replace('_', '').replace('-', '').isalnum():
			for text, element_info in mapping.items():
				selectors = element_info.get('selectors', '')
				# Check if the selector contains the target as an ID or name
				if (
					f'#{target_text}' in selectors
					or f'[name="{target_text}"]' in selectors
					or f'[id="{target_text}"]' in selectors
				):
					logger.debug(f"ID/name match found: '{target_text}' -> '{text}' (selector: {selectors})")
					return element_info

		# Strategy 3: Hierarchical context matching
		# If target contains context information like "Submit (in Contact Form)", parse it
		if '(' in target_text and target_text.endswith(')'):
			base_text = target_text.split('(')[0].strip()
			context_part = target_text.split('(')[1].rstrip(')').strip()

			# Look for elements that match both the base text and context
			candidates = []
			for text, element_info in mapping.items():
				if base_text.lower() in text.lower():
					# Check if the context matches
					if context_part.lower() in text.lower():
						candidates.append((text, element_info, 1.0))  # High score for full context match
					else:
						# Check if context matches container or DOM path
						container_context = element_info.get('container_context', {})
						dom_path = element_info.get('dom_path', '')

						context_match = False
						if container_context and context_part.lower() in str(container_context).lower():
							context_match = True
						elif context_part.lower() in dom_path.lower():
							context_match = True

						if context_match:
							candidates.append((text, element_info, 0.8))  # Good score for context match

			if candidates:
				# Return the best candidate
				candidates.sort(key=lambda x: x[2], reverse=True)
				best_text, best_element, best_score = candidates[0]
				logger.debug(f"Hierarchical context match found: '{target_text}' -> '{best_text}' (score: {best_score:.2f})")
				return best_element

		# Strategy 4: Enhanced fuzzy text matching with hierarchical scoring
		best_match = None
		best_score = 0.0
		best_text = ''

		for text, element_info in mapping.items():
			text_lower = text.lower()
			original_text = element_info.get('original_text', '').lower()

			# Calculate different types of matches
			scores = []

			# Substring match (both directions)
			if target_lower in text_lower:
				scores.append(len(target_lower) / len(text_lower))
			if text_lower in target_lower:
				scores.append(len(text_lower) / len(target_lower))

			# Also check against original text (before context was added)
			if original_text:
				if target_lower in original_text:
					scores.append(len(target_lower) / len(original_text))
				if original_text in target_lower:
					scores.append(len(original_text) / len(target_lower))

			# Word-based matching
			target_words = set(target_lower.split())
			text_words = set(text_lower.split())
			original_words = set(original_text.split()) if original_text else set()

			# Check against both full text and original text
			for word_set in [text_words, original_words]:
				if target_words and word_set:
					# Calculate Jaccard similarity (intersection over union)
					intersection = len(target_words & word_set)
					union = len(target_words | word_set)
					if union > 0:
						jaccard_score = intersection / union
						scores.append(jaccard_score)

					# Calculate word overlap score
					if len(target_words) > 0 and len(word_set) > 0:
						overlap_score = intersection / max(len(target_words), len(word_set))
						scores.append(overlap_score)

			# Take the best score for this element
			if scores:
				element_score = max(scores)
				if element_score > best_score and element_score > 0.3:  # Minimum threshold
					best_match = element_info
					best_score = element_score
					best_text = text

		if best_match:
			logger.debug(f"Fuzzy match found: '{target_text}' -> '{best_text}' (score: {best_score:.2f})")
			return best_match

		# Strategy 5: Pattern matching with camelCase/snake_case handling
		target_words = target_lower.split()
		if len(target_words) == 1:  # Single word target
			word = target_words[0]

			for text, element_info in mapping.items():
				text_lower = text.lower()
				original_text = element_info.get('original_text', '').lower()

				# Check both full text and original text for pattern matching
				for check_text in [text_lower, original_text]:
					if not check_text:
						continue

					# Split camelCase or snake_case
					word_parts = re.findall(r'[a-z]+|[A-Z][a-z]*', word)
					word_parts = [part.lower() for part in word_parts if part]

					if word_parts:
						# Check if all parts of the target word appear in the element text
						parts_found = sum(1 for part in word_parts if part in check_text)
						if parts_found >= len(word_parts) * 0.7:  # At least 70% of parts match
							score = parts_found / len(word_parts)
							if score > best_score:
								best_match = element_info
								best_score = score
								best_text = text

		if best_match:
			logger.debug(f"Pattern match found: '{target_text}' -> '{best_text}' (score: {best_score:.2f})")
			return best_match

		logger.debug(f"No match found for: '{target_text}'")
		return None

	def find_element_by_hierarchy(
		self, mapping: Dict[str, Dict], target_text: str, context_hints: List[str] = None
	) -> Optional[Dict]:
		"""Find element using hierarchical context hints.

		Args:
		    mapping: The semantic mapping
		    target_text: The text to find
		    context_hints: List of context hints like ['form', 'contact', 'personal info']
		"""
		if not target_text or not mapping:
			return None

		if not context_hints:
			return self.find_element_by_text(mapping, target_text)

		target_lower = target_text.lower().strip()
		context_lower = [hint.lower() for hint in context_hints]

		candidates = []

		for text, element_info in mapping.items():
			text_lower = text.lower()
			original_text = element_info.get('original_text', '').lower()

			# Check if the base text matches
			base_match_score = 0
			if text_lower == target_lower or original_text == target_lower:
				base_match_score = 1.0
			elif target_lower in text_lower or target_lower in original_text:
				base_match_score = 0.8
			elif any(word in text_lower or word in original_text for word in target_lower.split()):
				base_match_score = 0.6

			if base_match_score > 0:
				# Calculate context match score
				context_score = 0
				total_context_checks = 0

				# Check container context
				container_context = element_info.get('container_context', {})
				for hint in context_lower:
					total_context_checks += 1
					if container_context:
						container_text = container_context.get('text', '').lower()
						container_id = container_context.get('id', '').lower()
						if hint in container_text or hint in container_id:
							context_score += 1

				# Check DOM path
				dom_path = element_info.get('dom_path', '').lower()
				for hint in context_lower:
					if hint in dom_path:
						context_score += 0.5  # DOM path matches are less strong

				# Check full text (including added context)
				for hint in context_lower:
					if hint in text_lower:
						context_score += 0.3

				# Calculate final score
				context_match_ratio = context_score / max(len(context_lower), 1)
				final_score = base_match_score * 0.7 + context_match_ratio * 0.3

				candidates.append((text, element_info, final_score))

		if candidates:
			# Sort by score and return the best match
			candidates.sort(key=lambda x: x[2], reverse=True)
			best_text, best_element, best_score = candidates[0]

			if best_score > 0.5:  # Minimum threshold for hierarchical matching
				logger.debug(
					f"Hierarchical match found: '{target_text}' with context {context_hints} -> '{best_text}' (score: {best_score:.2f})"
				)
				return best_element

		# Fallback to regular text matching
		return self.find_element_by_text(mapping, target_text)
