import * as rrweb from "rrweb";
import { EventType, IncrementalSource } from "@rrweb/types";

let stopRecording: (() => void) | undefined = undefined;
let isRecordingActive = true; // Content script's local state
let scrollTimeout: ReturnType<typeof setTimeout> | null = null;
let lastScrollY: number | null = null;
let lastDirection: "up" | "down" | null = null;
const DEBOUNCE_MS = 500; // Wait 500ms after scroll stops

// --- Helper function to generate XPath ---
function getXPath(element: HTMLElement): string {
  if (element.id !== "") {
    return `id("${element.id}")`;
  }
  if (element === document.body) {
    return element.tagName.toLowerCase();
  }

  let ix = 0;
  const siblings = element.parentNode?.children;
  if (siblings) {
    for (let i = 0; i < siblings.length; i++) {
      const sibling = siblings[i];
      if (sibling === element) {
        return `${getXPath(
          element.parentElement as HTMLElement
        )}/${element.tagName.toLowerCase()}[${ix + 1}]`;
      }
      if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
        ix++;
      }
    }
  }
  // Fallback (should not happen often)
  return element.tagName.toLowerCase();
}
// --- End Helper ---

// --- Helper function to generate CSS Selector ---
// Expanded set of safe attributes (similar to Python)
const SAFE_ATTRIBUTES = new Set([
  "id",
  "name",
  "type",
  "placeholder",
  "aria-label",
  "aria-labelledby",
  "aria-describedby",
  "role",
  "for",
  "autocomplete",
  "required",
  "readonly",
  "alt",
  "title",
  "src",
  "href",
  "target",
  // Add common data attributes if stable
  "data-id",
  "data-qa",
  "data-cy",
  "data-testid",
]);

function getEnhancedCSSSelector(element: HTMLElement, xpath: string): string {
  try {
    // Base selector from simplified XPath or just tagName
    let cssSelector = element.tagName.toLowerCase();

    // Handle class attributes
    if (element.classList && element.classList.length > 0) {
      const validClassPattern = /^[a-zA-Z_][a-zA-Z0-9_-]*$/;
      element.classList.forEach((className) => {
        if (className && validClassPattern.test(className)) {
          cssSelector += `.${CSS.escape(className)}`;
        }
      });
    }

    // Handle other safe attributes
    for (const attr of element.attributes) {
      const attrName = attr.name;
      const attrValue = attr.value;

      if (attrName === "class") continue;
      if (!attrName.trim()) continue;
      if (!SAFE_ATTRIBUTES.has(attrName)) continue;

      const safeAttribute = CSS.escape(attrName);

      if (attrValue === "") {
        cssSelector += `[${safeAttribute}]`;
      } else {
        const safeValue = attrValue.replace(/"/g, '"');
        if (/["'<>`\s]/.test(attrValue)) {
          cssSelector += `[${safeAttribute}*="${safeValue}"]`;
        } else {
          cssSelector += `[${safeAttribute}="${safeValue}"]`;
        }
      }
    }
    return cssSelector;
  } catch (error) {
    console.error("Error generating enhanced CSS selector:", error);
    return `${element.tagName.toLowerCase()}[xpath="${xpath.replace(
      /"/g,
      '"'
    )}"]`;
  }
}

function startRecorder() {
  if (stopRecording) {
    console.log("Recorder already running.");
    return; // Already running
  }
  console.log("Starting rrweb recorder for:", window.location.href);
  isRecordingActive = true;
  stopRecording = rrweb.record({
    emit(event) {
      if (!isRecordingActive) return;

      // Handle scroll events with debouncing and direction detection
      if (
        event.type === EventType.IncrementalSnapshot &&
        event.data.source === IncrementalSource.Scroll
      ) {
        const scrollData = event.data as { id: number; x: number; y: number };
        const currentScrollY = scrollData.y;

        // Round coordinates
        const roundedScrollData = {
          ...scrollData,
          x: Math.round(scrollData.x),
          y: Math.round(scrollData.y),
        };

        // Determine scroll direction
        let currentDirection: "up" | "down" | null = null;
        if (lastScrollY !== null) {
          currentDirection = currentScrollY > lastScrollY ? "down" : "up";
        }

        // Record immediately if direction changes
        if (
          lastDirection !== null &&
          currentDirection !== null &&
          currentDirection !== lastDirection
        ) {
          if (scrollTimeout) {
            clearTimeout(scrollTimeout);
            scrollTimeout = null;
          }
          chrome.runtime.sendMessage({
            type: "RRWEB_EVENT",
            payload: {
              ...event,
              data: roundedScrollData, // Use rounded coordinates
            },
          });
          lastDirection = currentDirection;
          lastScrollY = currentScrollY;
          return;
        }

        // Update direction and position
        lastDirection = currentDirection;
        lastScrollY = currentScrollY;

        // Debouncer
        if (scrollTimeout) {
          clearTimeout(scrollTimeout);
        }
        scrollTimeout = setTimeout(() => {
          chrome.runtime.sendMessage({
            type: "RRWEB_EVENT",
            payload: {
              ...event,
              data: roundedScrollData, // Use rounded coordinates
            },
          });
          scrollTimeout = null;
          lastDirection = null; // Reset direction for next scroll
        }, DEBOUNCE_MS);
      } else {
        // Pass through non-scroll events unchanged
        chrome.runtime.sendMessage({ type: "RRWEB_EVENT", payload: event });
      }
    },
    maskInputOptions: {
      password: true,
    },
    checkoutEveryNms: 10000,
    checkoutEveryNth: 200,
  });

  // Add the stop function to window for potential manual cleanup
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).rrwebStop = stopRecorder;

  // --- Attach Custom Event Listeners Permanently ---
  // These listeners are always active, but the handlers check `isRecordingActive`
  document.addEventListener("click", handleCustomClick, true);
  document.addEventListener("input", handleInput, true);
  document.addEventListener("change", handleSelectChange, true);
  document.addEventListener("keydown", handleKeydown, true);
  document.addEventListener("mouseover", handleMouseOver, true);
  document.addEventListener("mouseout", handleMouseOut, true);
  document.addEventListener("focus", handleFocus, true);
  document.addEventListener("blur", handleBlur, true);
  console.log("Permanently attached custom event listeners.");
}

function stopRecorder() {
  if (stopRecording) {
    console.log("Stopping rrweb recorder for:", window.location.href);
    stopRecording();
    stopRecording = undefined;
    isRecordingActive = false;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).rrwebStop = undefined; // Clean up window property
    // Remove custom listeners when recording stops
    document.removeEventListener("click", handleCustomClick, true);
    document.removeEventListener("input", handleInput, true);
    document.removeEventListener("change", handleSelectChange, true); // Remove change listener
    document.removeEventListener("keydown", handleKeydown, true); // Remove keydown listener
    document.removeEventListener("mouseover", handleMouseOver, true);
    document.removeEventListener("mouseout", handleMouseOut, true);
    document.removeEventListener("focus", handleFocus, true);
    document.removeEventListener("blur", handleBlur, true);
  } else {
    console.log("Recorder not running, cannot stop.");
  }
}

// --- Helper function to extract semantic information ---
function extractSemanticInfo(element: HTMLElement) {
  // Get associated label text using multiple strategies
  let labelText = '';
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const elementType = (element as any).type?.toLowerCase() || '';
  const elementTag = element.tagName.toLowerCase();
  
  // Special handling for radio buttons and checkboxes
  if ((elementTag === 'input' && (elementType === 'radio' || elementType === 'checkbox')) || 
      (elementTag === 'button' && element.getAttribute('role') === 'radio')) {
    
    let fieldName = ''; // The group/field name (e.g., "Marital Status")
    let optionValue = ''; // The specific option (e.g., "Married")
    const allOptions: string[] = []; // All possible values in the group
    
    // First, get the individual option value/label
    // Strategy 1: Direct label[for="id"] association (most reliable for radio buttons)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if ((element as any).id) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const label = document.querySelector(`label[for="${(element as any).id}"]`);
      if (label) {
        optionValue = label.textContent?.trim() || '';
      }
    }
    
    // Strategy 2: Look for immediate parent label (common pattern)
    if (!optionValue) {
      const parent = element.parentElement;
      if (parent && parent.tagName.toLowerCase() === 'label') {
        optionValue = parent.textContent?.trim() || '';
      }
    }
    
    // Strategy 3: Look for adjacent text nodes or spans (common in custom radio buttons)
    if (!optionValue) {
      // Check next sibling for text
      let sibling = element.nextElementSibling;
      while (sibling && !optionValue) {
        const siblingText = sibling.textContent?.trim() || '';
        if (siblingText && siblingText.length < 50 && siblingText.length > 1) {
          optionValue = siblingText;
          break;
        }
        sibling = sibling.nextElementSibling;
      }
      
      // If no next sibling, check previous sibling
      if (!optionValue) {
        sibling = element.previousElementSibling;
        while (sibling && !optionValue) {
          const siblingText = sibling.textContent?.trim() || '';
          if (siblingText && siblingText.length < 50 && siblingText.length > 1) {
            optionValue = siblingText;
            break;
          }
          sibling = sibling.previousElementSibling;
        }
      }
    }
    
    // Strategy 4: Use value attribute for radio buttons if no label found
    if (!optionValue && elementType === 'radio') {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const value = (element as any).value || '';
      if (value && value.length < 30) {
        optionValue = value;
      }
    }
    
    // Now find the field name and all options for radio button groups
    if (elementType === 'radio') {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const radioName = (element as any).name || '';
      
      // Find the field group name by looking for fieldset legend or group labels
      let container = element.parentElement;
      while (container && container !== document.body) {
        // Check for fieldset with legend
        if (container.tagName.toLowerCase() === 'fieldset') {
          const legend = container.querySelector('legend');
          if (legend) {
            fieldName = legend.textContent?.trim() || '';
            break;
          }
        }
        
        // Check for group labels (like div with a label or heading)
        const possibleLabels = container.querySelectorAll('label, h1, h2, h3, h4, h5, h6, .label, .form-label, .field-label');
        for (const possibleLabel of possibleLabels) {
          const labelText = possibleLabel.textContent?.trim() || '';
          // Check if this label doesn't belong to a specific input (not associated with any radio button value)
          const isGeneralLabel = !Array.from(container.querySelectorAll('input[type="radio"]')).some(radio => {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const radioValue = (radio as any).value || '';
            const radioLabel = radio.closest('label')?.textContent?.trim() || '';
            return labelText.includes(radioValue) || labelText.includes(radioLabel);
          });
          
          if (labelText && labelText.length > 2 && labelText.length < 100 && isGeneralLabel) {
            fieldName = labelText;
            break;
          }
        }
        
        if (fieldName) break;
        container = container.parentElement;
      }
      
      // Collect all options in the same radio group
      if (radioName) {
        const radioGroup = document.querySelectorAll(`input[type="radio"][name="${radioName}"]`);
        radioGroup.forEach((radio) => {
          // Get the label for each radio button
          let radioOptionText = '';
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const radioId = (radio as any).id;
          if (radioId) {
            const radioLabel = document.querySelector(`label[for="${radioId}"]`);
            if (radioLabel) {
              radioOptionText = radioLabel.textContent?.trim() || '';
            }
          }
          
          if (!radioOptionText) {
            const radioParent = radio.parentElement;
            if (radioParent && radioParent.tagName.toLowerCase() === 'label') {
              radioOptionText = radioParent.textContent?.trim() || '';
            }
          }

          if (!radioOptionText) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            radioOptionText = (radio as any).value || '';
          }
          
          if (radioOptionText && !allOptions.includes(radioOptionText)) {
            allOptions.push(radioOptionText);
          }
        });
      }
    }
    
    // Create meaningful labelText combining field name and option
    if (fieldName && optionValue) {
      labelText = `${fieldName}: ${optionValue}`;
    } else if (optionValue) {
      labelText = optionValue;
    } else if (fieldName) {
      labelText = fieldName;
    }

    // Store additional radio button info for later use
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (element as any)._radioButtonInfo = {
      fieldName,
      optionValue,
      allOptions
    };
    
    // Fallback: Look in immediate parent container but filter out other radio button text
    if (!labelText) {
      const parent = element.parentElement;
      if (parent) {
        // Get all radio buttons in the same group
        const radioButtons = parent.querySelectorAll('input[type="radio"], button[role="radio"]');
        const parentText = parent.textContent?.trim() || '';
        
        if (parentText && parentText.length < 100) {
          // Try to extract just this radio button's text by removing other radio button values
          let cleanedText = parentText;
          radioButtons.forEach((radio) => {
            if (radio !== element) {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const radioValue = (radio as any).value || '';
              const radioText = radio.textContent?.trim() || '';
              if (radioValue) cleanedText = cleanedText.replace(radioValue, '').trim();
              if (radioText) cleanedText = cleanedText.replace(radioText, '').trim();
            }
          });
          
          if (cleanedText && cleanedText.length > 1 && cleanedText.length < 50) {
            labelText = cleanedText;
          }
        }
      }
    }
  } else {
    // Standard label extraction for non-radio elements
    
    // Special handling for buttons - use direct text content
    if (elementTag === 'button' || 
        (elementTag === 'input' && ['button', 'submit'].includes(elementType))) {
      // For buttons, prioritize the element's own text content
      labelText = element.textContent?.trim() || '';
      
      // If no direct text, try aria-label or value
      if (!labelText) {
        labelText = element.getAttribute('aria-label') ||
                   // eslint-disable-next-line @typescript-eslint/no-explicit-any
                   (element as any).value ||
                   element.title || '';
      }
    } else {
      // Strategy 1: Direct label[for="id"] association
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      if ((element as any).id) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const label = document.querySelector(`label[for="${(element as any).id}"]`);
        if (label) {
          labelText = label.textContent?.trim() || '';
        }
      }
      
      // Strategy 2: Find parent label element
      if (!labelText) {
        let parent = element.parentElement;
        while (parent && parent !== document.body) {
          if (parent.tagName.toLowerCase() === 'label') {
            labelText = parent.textContent?.trim() || '';
            break;
          }
          parent = parent.parentElement;
        }
      }
    }
    
    // Strategy 3: Look for associated text in immediate siblings or parent containers
    if (!labelText) {
      const parent = element.parentElement;
      if (parent) {
        // Check for text in the same container
        const parentText = parent.textContent?.trim() || '';
        // Extract meaningful text that's not just the element's own value/placeholder
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const elementOwnText = ((element as any).value || (element as any).placeholder || element.textContent || '').trim();
        
        if (parentText && parentText !== elementOwnText && parentText.length < 200) {
          // Try to extract the label part by removing element's own text
          let cleanedText = parentText;
          if (elementOwnText) {
            cleanedText = parentText.replace(elementOwnText, '').trim();
          }
          
          // If we have meaningful text, use it
          if (cleanedText && cleanedText.length > 2) {
            labelText = cleanedText;
          } else if (parentText.length < 100) {
            // Use the full parent text if it's reasonable length
            labelText = parentText;
          }
        }
      }
    }
    
    // Strategy 4: Look for preceding text nodes or elements
    if (!labelText) {
      let sibling = element.previousElementSibling;
      while (sibling && !labelText) {
        const siblingText = sibling.textContent?.trim() || '';
        if (siblingText && siblingText.length < 100 && siblingText.length > 2) {
          labelText = siblingText;
          break;
        }
        sibling = sibling.previousElementSibling;
      }
    }
    
    // Strategy 5: Check aria-labelledby references
    if (!labelText) {
      const ariaLabelledBy = element.getAttribute('aria-labelledby');
      if (ariaLabelledBy) {
        const referencedElement = document.getElementById(ariaLabelledBy);
        if (referencedElement) {
          labelText = referencedElement.textContent?.trim() || '';
        }
      }
    }
  }
  
  // Get parent context for additional semantic information
  let parentText = '';
  let parent = element.parentElement;
  while (parent && !parentText && parent !== document.body) {
    const text = parent.textContent?.trim() || '';
    if (text && text.length < 100) {
      parentText = text;
    }
    parent = parent.parentElement;
  }

  // Get radio button info if available
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const radioButtonInfo = (element as any)._radioButtonInfo || null;

  return {
    labelText,
    textContent: element.textContent?.trim().slice(0, 200) || "",
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    placeholder: (element as any).placeholder || "",
    title: element.title || "",
    ariaLabel: element.getAttribute('aria-label') || "",
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    value: (element as any).value || "",
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    name: (element as any).name || "",
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    id: (element as any).id || "",
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    type: (element as any).type || "",
    parentText,
    // Radio button specific info
    radioButtonInfo
  };
}

// --- Custom Click Handler ---
function handleCustomClick(event: MouseEvent) {
  if (!isRecordingActive) return;
  const targetElement = event.target as HTMLElement;
  if (!targetElement) return;

  try {
    const xpath = getXPath(targetElement);
    const semanticInfo = extractSemanticInfo(targetElement);
    
    // Determine the best target_text for semantic targeting
    // For buttons, prioritize direct text content over label text to avoid confusion
    let targetText = "";
    if (targetElement.tagName.toLowerCase() === 'button' ||
        (targetElement.tagName.toLowerCase() === 'input' &&
         // eslint-disable-next-line @typescript-eslint/no-explicit-any
         ['button', 'submit'].includes((targetElement as any).type?.toLowerCase()))) {
      // For buttons, use the most specific text available
      targetText = semanticInfo.textContent?.trim() ||
                   semanticInfo.ariaLabel ||
                   // eslint-disable-next-line @typescript-eslint/no-explicit-any
                   (targetElement as any).value ||
                   semanticInfo.title ||
                   "";
    } else {
      // For other elements, use the standard priority order
      targetText = semanticInfo.labelText || 
                   semanticInfo.textContent || 
                   semanticInfo.placeholder || 
                   semanticInfo.ariaLabel || 
                   semanticInfo.name || 
                   semanticInfo.id || 
                   "";
    }

    // Smart filtering: Skip capturing clicks on elements that are likely redundant
    if (shouldSkipClickEvent(targetElement, semanticInfo, targetText)) {
      console.log("Skipping redundant click event on:", targetElement.tagName, targetText);
      return;
    }

    // Capture element state information for inputs
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const elementType = (targetElement as any).type?.toLowerCase() || '';
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let elementState: Record<string, any> = {};
    
    if (targetElement.tagName.toLowerCase() === 'input') {
      if (elementType === 'checkbox') {
        elementState = {
          checked: (targetElement as HTMLInputElement).checked,
          elementType: 'checkbox'
        };
      } else if (elementType === 'radio') {
        elementState = {
          checked: (targetElement as HTMLInputElement).checked,
          elementType: 'radio'
        };
      } else {
        elementState = {
          elementType: elementType
        };
      }
    }
    
    const clickData = {
      timestamp: Date.now(),
      url: document.location.href, // Use document.location for main page URL
      frameUrl: window.location.href, // URL of the frame where the event occurred
      xpath: xpath,
      cssSelector: getEnhancedCSSSelector(targetElement, xpath),
      elementTag: targetElement.tagName,
      elementText: semanticInfo.textContent,
      elementType: elementType, // Add element type for processing
      ...elementState, // Spread element state (checked status for checkboxes/radios)
      // Semantic information for target_text based workflows
      targetText: targetText,
      semanticInfo: semanticInfo,
      // Enhanced radio button information
      radioButtonInfo: semanticInfo.radioButtonInfo,
    };
    console.log("Sending CUSTOM_CLICK_EVENT:", clickData);
    chrome.runtime.sendMessage({
      type: "CUSTOM_CLICK_EVENT",
      payload: clickData,
    });
  } catch (error) {
    console.error("Error capturing click data:", error);
  }
}

// Helper function to determine if we should skip capturing this click event
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function shouldSkipClickEvent(element: HTMLElement, _semanticInfo: Record<string, any>, targetText: string): boolean {
  const tagName = element.tagName.toLowerCase();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const elementType = (element as any).type?.toLowerCase() || '';
  
  // Skip hidden input elements (they often fire alongside visible elements)
  if (tagName === 'input' && elementType === 'radio' && !isElementVisible(element)) {
    return true;
  }
  
  // Skip button elements that have no meaningful text and are likely part of a composite component
  if (tagName === 'button' && 
      element.getAttribute('role') === 'radio' && 
      !targetText.trim()) {
    return true;
  }
  
  // Skip clicks on elements that have no semantic value and are very generic
  if (!targetText.trim() && 
      tagName === 'input' && 
      elementType === 'radio' &&
      element.style.display === 'none') {
    return true;
  }
  
  return false;
}

// Helper function to check if an element is visible
function isElementVisible(element: HTMLElement): boolean {
  const style = window.getComputedStyle(element);
  return style.display !== 'none' && 
         style.visibility !== 'hidden' && 
         style.opacity !== '0' &&
         element.offsetWidth > 0 && 
         element.offsetHeight > 0;
}
// --- End Custom Click Handler ---

// --- Custom Input Handler ---
function handleInput(event: Event) {
  if (!isRecordingActive) return;
  const targetElement = event.target as HTMLInputElement | HTMLTextAreaElement;
  if (!targetElement || !("value" in targetElement)) return;
  const isPassword = targetElement.type === "password";

  try {
    const xpath = getXPath(targetElement);
    const semanticInfo = extractSemanticInfo(targetElement as HTMLElement);
    
    // Determine the best target_text for semantic targeting
    // For inputs, prioritize labelText and placeholder over textContent
    const targetText = semanticInfo.labelText || 
                      semanticInfo.placeholder || 
                      semanticInfo.ariaLabel || 
                      semanticInfo.name || 
                      semanticInfo.id || 
                      "";
    
    const inputData = {
      timestamp: Date.now(),
      url: document.location.href,
      frameUrl: window.location.href,
      xpath: xpath,
      cssSelector: getEnhancedCSSSelector(targetElement, xpath),
      elementTag: targetElement.tagName,
      value: isPassword ? "********" : targetElement.value,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      inputType: (targetElement as any).type?.toLowerCase() || 'text', // Input type (text, password, email, etc.)
      // Semantic information for target_text based workflows
      targetText: targetText,
      semanticInfo: semanticInfo,
    };
    console.log("Sending CUSTOM_INPUT_EVENT:", inputData);
    chrome.runtime.sendMessage({
      type: "CUSTOM_INPUT_EVENT",
      payload: inputData,
    });
  } catch (error) {
    console.error("Error capturing input data:", error);
  }
}
// --- End Custom Input Handler ---

// --- Custom Select Change Handler ---
function handleSelectChange(event: Event) {
  if (!isRecordingActive) return;
  const targetElement = event.target as HTMLSelectElement;
  // Ensure it's a select element
  if (!targetElement || targetElement.tagName !== "SELECT") return;

  try {
    const xpath = getXPath(targetElement);
    const selectedOption = targetElement.options[targetElement.selectedIndex];
    
    // Extract all available options
    const allOptions: Array<{text: string, value: string}> = [];
    for (let i = 0; i < targetElement.options.length; i++) {
      const option = targetElement.options[i];
      allOptions.push({
        text: option.text.trim(),
        value: option.value
      });
    }
    
    // Get semantic info for the select element
    const semanticInfo = extractSemanticInfo(targetElement);
    const fieldName = semanticInfo.labelText || semanticInfo.name || 
                     semanticInfo.ariaLabel || targetElement.name || '';
    
    const selectData = {
      timestamp: Date.now(),
      url: document.location.href,
      frameUrl: window.location.href,
      xpath: xpath,
      cssSelector: getEnhancedCSSSelector(targetElement, xpath),
      elementTag: targetElement.tagName,
      selectedValue: targetElement.value,
      selectedText: selectedOption ? selectedOption.text : "", // Get selected option text
      allOptions: allOptions, // Include all available options
      fieldName: fieldName, // Field name/label
      targetText: semanticInfo.labelText || fieldName,
      semanticInfo: semanticInfo
    };
    console.log("Sending CUSTOM_SELECT_EVENT:", selectData);
    chrome.runtime.sendMessage({
      type: "CUSTOM_SELECT_EVENT",
      payload: selectData,
    });
  } catch (error) {
    console.error("Error capturing select change data:", error);
  }
}
// --- End Custom Select Change Handler ---

// --- Custom Keydown Handler ---
// Set of keys we want to capture explicitly
const CAPTURED_KEYS = new Set([
  "Enter",
  "Tab",
  "Escape",
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "Home",
  "End",
  "PageUp",
  "PageDown",
  "Backspace",
  "Delete",
]);

function handleKeydown(event: KeyboardEvent) {
  if (!isRecordingActive) return;

  const key = event.key;
  let keyToLog = "";

  // Check if it's a key we explicitly capture
  if (CAPTURED_KEYS.has(key)) {
    keyToLog = key;
  }
  // Check for common modifier combinations (Ctrl/Cmd + key)
  else if (
    (event.ctrlKey || event.metaKey) &&
    key.length === 1 &&
    /[a-zA-Z0-9]/.test(key)
  ) {
    // Use 'CmdOrCtrl' to be cross-platform friendly in logs
    keyToLog = `CmdOrCtrl+${key.toUpperCase()}`;
  }
  // You could add more specific checks here (Alt+, Shift+, etc.) if needed

  // If we have a key we want to log, send the event
  if (keyToLog) {
    const targetElement = event.target as HTMLElement;
    let xpath = "";
    let cssSelector = "";
    let elementTag = "document"; // Default if target is not an element
    if (targetElement && typeof targetElement.tagName === "string") {
      try {
        xpath = getXPath(targetElement);
        cssSelector = getEnhancedCSSSelector(targetElement, xpath);
        elementTag = targetElement.tagName;
      } catch (e) {
        console.error("Error getting selector for keydown target:", e);
      }
    }

    try {
      const keyData = {
        timestamp: Date.now(),
        url: document.location.href,
        frameUrl: window.location.href,
        key: keyToLog, // The key or combination pressed
        xpath: xpath, // XPath of the element in focus (if any)
        cssSelector: cssSelector, // CSS selector of the element in focus (if any)
        elementTag: elementTag, // Tag name of the element in focus
      };
      console.log("Sending CUSTOM_KEY_EVENT:", keyData);
      chrome.runtime.sendMessage({
        type: "CUSTOM_KEY_EVENT",
        payload: keyData,
      });
    } catch (error) {
      console.error("Error capturing keydown data:", error);
    }
  }
}
// --- End Custom Keydown Handler ---

// Store the current overlay to manage its lifecycle
let currentOverlay: HTMLDivElement | null = null;
let currentFocusOverlay: HTMLDivElement | null = null;

// Handle mouseover to create overlay
function handleMouseOver(event: MouseEvent) {
  if (!isRecordingActive) return;
  const targetElement = event.target as HTMLElement;
  if (!targetElement) return;

  // Remove any existing overlay to avoid duplicates
  if (currentOverlay) {
    // console.log('Removing existing overlay');
    currentOverlay.remove();
    currentOverlay = null;
  }

  try {
    const xpath = getXPath(targetElement);
    // console.log('XPath of target element:', xpath);
    let elementToHighlight: HTMLElement | null = document.evaluate(
      xpath,
      document,
      null,
      XPathResult.FIRST_ORDERED_NODE_TYPE,
      null
    ).singleNodeValue as HTMLElement | null;
    if (!elementToHighlight) {
      const enhancedSelector = getEnhancedCSSSelector(targetElement, xpath);
      console.log("CSS Selector:", enhancedSelector);
      const elements = document.querySelectorAll<HTMLElement>(enhancedSelector);

      // Try to find the element under the mouse
      for (const el of elements) {
        const rect = el.getBoundingClientRect();
        if (
          event.clientX >= rect.left &&
          event.clientX <= rect.right &&
          event.clientY >= rect.top &&
          event.clientY <= rect.bottom
        ) {
          elementToHighlight = el;
          break;
        }
      }
    }
    if (elementToHighlight) {
      const rect = elementToHighlight.getBoundingClientRect();
      const highlightOverlay = document.createElement("div");
      highlightOverlay.className = "highlight-overlay";
      Object.assign(highlightOverlay.style, {
        position: "absolute",
        top: `${rect.top + window.scrollY}px`,
        left: `${rect.left + window.scrollX}px`,
        width: `${rect.width}px`,
        height: `${rect.height}px`,
        border: "2px solid lightgreen",
        backgroundColor: "rgba(144, 238, 144, 0.05)", // lightgreen tint
        pointerEvents: "none",
        zIndex: "2147483000",
      });
      document.body.appendChild(highlightOverlay);
      currentOverlay = highlightOverlay;
    } else {
      console.warn("No element found to highlight for xpath:", xpath);
    }
  } catch (error) {
    console.error("Error creating highlight overlay:", error);
  }
}

// Handle mouseout to remove overlay
function handleMouseOut(_event: MouseEvent) {
  if (!isRecordingActive) return;
  if (currentOverlay) {
    currentOverlay.remove();
    currentOverlay = null;
  }
}

// Handle focus to create red overlay for input elements
function handleFocus(event: FocusEvent) {
  if (!isRecordingActive) return;
  const targetElement = event.target as HTMLElement;
  if (
    !targetElement ||
    !["INPUT", "TEXTAREA", "SELECT"].includes(targetElement.tagName)
  )
    return;

  // Remove any existing focus overlay to avoid duplicates
  if (currentFocusOverlay) {
    currentFocusOverlay.remove();
    currentFocusOverlay = null;
  }

  try {
    const xpath = getXPath(targetElement);
    let elementToHighlight: HTMLElement | null = document.evaluate(
      xpath,
      document,
      null,
      XPathResult.FIRST_ORDERED_NODE_TYPE,
      null
    ).singleNodeValue as HTMLElement | null;
    if (!elementToHighlight) {
      const enhancedSelector = getEnhancedCSSSelector(targetElement, xpath);
      elementToHighlight = document.querySelector(enhancedSelector);
    }
    if (elementToHighlight) {
      const rect = elementToHighlight.getBoundingClientRect();
      const focusOverlay = document.createElement("div");
      focusOverlay.className = "focus-overlay";
      Object.assign(focusOverlay.style, {
        position: "absolute",
        top: `${rect.top + window.scrollY}px`,
        left: `${rect.left + window.scrollX}px`,
        width: `${rect.width}px`,
        height: `${rect.height}px`,
        border: "2px solid red",
        backgroundColor: "rgba(255, 0, 0, 0.05)", // Red tint
        pointerEvents: "none",
        zIndex: "2147483100", // Higher than mouseover overlay (2147483000)
      });
      document.body.appendChild(focusOverlay);
      currentFocusOverlay = focusOverlay;
    } else {
      console.warn("No element found to highlight for focus, xpath:", xpath);
    }
  } catch (error) {
    console.error("Error creating focus overlay:", error);
  }
}

// Handle blur to remove focus overlay
function handleBlur(_event: FocusEvent) {
  if (!isRecordingActive) return;
  if (currentFocusOverlay) {
    currentFocusOverlay.remove();
    currentFocusOverlay = null;
  }
}

export default defineContentScript({
  matches: ["<all_urls>"],
  main(_ctx) {
    // Listener for status updates from the background script
    chrome.runtime.onMessage.addListener((message, _sender, _sendResponse) => {
      if (message.type === "SET_RECORDING_STATUS") {
        const shouldBeRecording = message.payload;
        console.log(`Received recording status update: ${shouldBeRecording}`);
        if (shouldBeRecording && !isRecordingActive) {
          startRecorder();
        } else if (!shouldBeRecording && isRecordingActive) {
          stopRecorder();
        }
      }
      // If needed, handle other message types here
    });

    // Request initial status when the script loads
    console.log(
      "Content script loaded, requesting initial recording status..."
    );
    chrome.runtime.sendMessage(
      { type: "REQUEST_RECORDING_STATUS" },
      (response) => {
        if (chrome.runtime.lastError) {
          console.error(
            "Error requesting initial status:",
            chrome.runtime.lastError.message
          );
          // Handle error - maybe default to not recording?
          return;
        }
        if (response && response.isRecordingEnabled) {
          console.log("Initial status: Recording enabled.");
          startRecorder();
        } else {
          console.log("Initial status: Recording disabled.");
          // Ensure recorder is stopped if it somehow started
          stopRecorder();
        }
      }
    );

    // Optional: Clean up recorder if the page is unloading
    window.addEventListener("beforeunload", () => {
      // Also remove permanent listeners on unload?
      // Might not be strictly necessary as the page context is destroyed,
      // but good practice if the script could somehow persist.
      document.removeEventListener("click", handleCustomClick, true);
      document.removeEventListener("input", handleInput, true);
      document.removeEventListener("change", handleSelectChange, true);
      document.removeEventListener("keydown", handleKeydown, true);
      document.removeEventListener("mouseover", handleMouseOver, true);
      document.removeEventListener("mouseout", handleMouseOut, true);
      document.removeEventListener("focus", handleFocus, true);
      document.removeEventListener("blur", handleBlur, true);
      stopRecorder(); // Ensure rrweb is stopped
    });

    // Optional: Log when the content script is injected
    // console.log("rrweb recorder injected into:", window.location.href);

    // Listener for potential messages from popup/background if needed later
    // chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    //   if (msg.type === 'GET_EVENTS') {
    //     sendResponse(events);
    //   }
    //   return true; // Keep the message channel open for asynchronous response
    // });
  },
});
