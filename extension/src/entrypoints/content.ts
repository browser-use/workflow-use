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

  // Add the stop function to window for potenti
  // --- End CSS Selector Helper --- al manual cleanup
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

// --- Custom Click Handler ---
function handleCustomClick(event: MouseEvent) {
  if (!isRecordingActive) return;
  const targetElement = event.target as HTMLElement;
  if (!targetElement) return;

  try {
    const xpath = getXPath(targetElement);
    const clickData = {
      timestamp: Date.now(),
      url: document.location.href, // Use document.location for main page URL
      frameUrl: window.location.href, // URL of the frame where the event occurred
      xpath: xpath,
      cssSelector: getEnhancedCSSSelector(targetElement, xpath),
      elementTag: targetElement.tagName,
      elementText: targetElement.textContent?.trim().slice(0, 200) || "",
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
// --- End Custom Click Handler ---

// --- Custom Input Handler ---
function handleInput(event: Event) {
  if (!isRecordingActive) return;
  const targetElement = event.target as HTMLElement;
  if (!targetElement) return;

  const isInput =
    targetElement instanceof HTMLInputElement ||
    targetElement instanceof HTMLTextAreaElement;
  const isContentEditable =
    targetElement.isContentEditable === true ||
    targetElement.getAttribute("contenteditable") === "true";

  if (!isInput && !isContentEditable) return;

  let value: string;
  if (isInput) {
    const inputEl = targetElement as HTMLInputElement | HTMLTextAreaElement;
    value =
      inputEl instanceof HTMLInputElement && inputEl.type === "password"
        ? "********"
        : inputEl.value;
  } else if (isContentEditable) {
    value = targetElement.textContent?.slice(0, 1000) || "";
  } else {
    return;
  }

  try {
    const xpath = getXPath(targetElement);
    const inputData = {
      timestamp: Date.now(),
      url: document.location.href,
      frameUrl: window.location.href,
      xpath: xpath,
      cssSelector: getEnhancedCSSSelector(targetElement, xpath),
      elementTag: targetElement.tagName,
      value: value
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
    const selectData = {
      timestamp: Date.now(),
      url: document.location.href,
      frameUrl: window.location.href,
      xpath: xpath,
      cssSelector: getEnhancedCSSSelector(targetElement, xpath),
      elementTag: targetElement.tagName,
      selectedValue: targetElement.value,
      selectedText: selectedOption ? selectedOption.text : "", // Get selected option text
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
function handleMouseOut(event: MouseEvent) {
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
function handleBlur(event: FocusEvent) {
  if (!isRecordingActive) return;
  if (currentFocusOverlay) {
    currentFocusOverlay.remove();
    currentFocusOverlay = null;
  }
}

export default defineContentScript({
  matches: ["<all_urls>"],
  main(ctx) {
    // Listener for status updates from the background script
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
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
