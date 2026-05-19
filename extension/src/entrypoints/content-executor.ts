/**
 * Content Executor — Replays workflow steps in the user's Chrome browser.
 *
 * This is a SEPARATE content script from content.ts (recording).
 * It is injected programmatically by background.ts when execution starts.
 *
 * Element finding priority: target_text (semantic) → cssSelector → xpath
 * Actions use real DOM events to trigger React/Vue/Angular handlers.
 */

// --- Element Finding ---

/**
 * Find an element on the page using multiple strategies.
 * Returns the element or null if not found.
 */
function findElement(step: Record<string, unknown>): HTMLElement | null {
  const targetText = (step.target_text || step.targetText) as string | undefined;
  const cssSelector = step.cssSelector as string | undefined;
  const xpath = step.xpath as string | undefined;

  // Strategy 1: Semantic text matching (most reliable across page changes)
  if (targetText) {
    const found = findByTargetText(targetText, step);
    if (found) {
      console.log(`[Executor] Found by target_text: "${targetText}"`);
      return found;
    }
  }

  // Strategy 2: CSS selector
  if (cssSelector) {
    try {
      const found = document.querySelector(cssSelector) as HTMLElement | null;
      if (found && isElementVisible(found)) {
        console.log(`[Executor] Found by cssSelector: "${cssSelector}"`);
        return found;
      }
    } catch {
      // Invalid selector — skip
    }
  }

  // Strategy 3: XPath
  if (xpath) {
    try {
      const result = document.evaluate(
        xpath,
        document,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
      );
      const found = result.singleNodeValue as HTMLElement | null;
      if (found && isElementVisible(found)) {
        console.log(`[Executor] Found by xpath: "${xpath}"`);
        return found;
      }
    } catch {
      // Invalid xpath — skip
    }
  }

  return null;
}

/**
 * Find element by semantic target text.
 * Searches interactive elements for matching text content, labels, placeholders, etc.
 */
function findByTargetText(
  targetText: string,
  step: Record<string, unknown>
): HTMLElement | null {
  const stepType = step.type as string;
  const normalizedTarget = targetText.toLowerCase().trim();

  // Determine which elements to search based on step type
  let selector: string;
  if (stepType === "input") {
    selector =
      'input, textarea, select, [contenteditable="true"], [role="textbox"], [role="combobox"], [role="searchbox"]';
  } else if (stepType === "click") {
    selector =
      "a, button, input, select, textarea, label, [role], [onclick], [tabindex], summary, details, h1, h2, h3, h4, h5, h6, span, div, li, td, th, img";
  } else {
    selector =
      "a, button, input, select, textarea, label, [role], [onclick], [tabindex]";
  }

  const candidates = document.querySelectorAll(selector);
  let bestMatch: HTMLElement | null = null;
  let bestScore = 0;

  for (const el of candidates) {
    const element = el as HTMLElement;
    if (!isElementVisible(element)) continue;

    const score = getTextMatchScore(element, normalizedTarget);
    if (score > bestScore) {
      bestScore = score;
      bestMatch = element;
    }
  }

  // Require a minimum score to consider it a match
  if (bestScore >= 0.5) {
    return bestMatch;
  }

  return null;
}

/**
 * Score how well an element matches the target text.
 * Returns 0-1 where 1 is a perfect match.
 */
function getTextMatchScore(
  element: HTMLElement,
  normalizedTarget: string
): number {
  let maxScore = 0;

  // Check various text sources
  const sources: { text: string; weight: number }[] = [];

  // Direct text content
  const textContent = element.textContent?.trim().toLowerCase() || "";
  if (textContent) sources.push({ text: textContent, weight: 1.0 });

  // Aria label
  const ariaLabel = element.getAttribute("aria-label")?.toLowerCase() || "";
  if (ariaLabel) sources.push({ text: ariaLabel, weight: 1.0 });

  // Placeholder
  const placeholder =
    (element as HTMLInputElement).placeholder?.toLowerCase() || "";
  if (placeholder) sources.push({ text: placeholder, weight: 0.9 });

  // Title
  const title = element.title?.toLowerCase() || "";
  if (title) sources.push({ text: title, weight: 0.8 });

  // Value (for inputs)
  const value = (element as HTMLInputElement).value?.toLowerCase() || "";
  if (value) sources.push({ text: value, weight: 0.7 });

  // Name attribute
  const name = element.getAttribute("name")?.toLowerCase() || "";
  if (name) sources.push({ text: name, weight: 0.6 });

  // Associated label (label[for=id])
  const id = element.id;
  if (id) {
    const label = document.querySelector(`label[for="${id}"]`);
    if (label) {
      const labelText = label.textContent?.trim().toLowerCase() || "";
      if (labelText) sources.push({ text: labelText, weight: 1.0 });
    }
  }

  // Parent label
  const parentLabel = element.closest("label");
  if (parentLabel && parentLabel !== element) {
    const labelText = parentLabel.textContent?.trim().toLowerCase() || "";
    if (labelText) sources.push({ text: labelText, weight: 0.9 });
  }

  for (const source of sources) {
    let score = 0;

    // Exact match
    if (source.text === normalizedTarget) {
      score = 1.0 * source.weight;
    }
    // Text contains target
    else if (source.text.includes(normalizedTarget)) {
      score = 0.8 * source.weight;
    }
    // Target contains text (e.g., target has extra context)
    else if (normalizedTarget.includes(source.text) && source.text.length > 3) {
      score = 0.7 * source.weight;
    }
    // Fuzzy: significant word overlap
    else {
      const targetWords = new Set(
        normalizedTarget.split(/\s+/).filter((w) => w.length > 2)
      );
      const sourceWords = new Set(
        source.text.split(/\s+/).filter((w) => w.length > 2)
      );
      if (targetWords.size > 0 && sourceWords.size > 0) {
        let matchCount = 0;
        for (const word of targetWords) {
          if (sourceWords.has(word)) matchCount++;
        }
        const overlap = matchCount / Math.max(targetWords.size, 1);
        if (overlap >= 0.5) {
          score = overlap * 0.6 * source.weight;
        }
      }
    }

    maxScore = Math.max(maxScore, score);
  }

  return maxScore;
}

function isElementVisible(element: HTMLElement): boolean {
  if (!element) return false;
  const style = window.getComputedStyle(element);
  if (
    style.display === "none" ||
    style.visibility === "hidden" ||
    style.opacity === "0"
  )
    return false;
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

// --- Wait for Element ---

/**
 * Wait for an element to appear on the page (handles dynamic/SPA content).
 */
function waitForElement(
  step: Record<string, unknown>,
  timeoutMs: number = 10000
): Promise<HTMLElement | null> {
  return new Promise((resolve) => {
    // Try immediately first
    const immediate = findElement(step);
    if (immediate) {
      resolve(immediate);
      return;
    }

    let resolved = false;
    const timeout = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        observer.disconnect();
        // One final attempt
        resolve(findElement(step));
      }
    }, timeoutMs);

    const observer = new MutationObserver(() => {
      if (resolved) return;
      const found = findElement(step);
      if (found) {
        resolved = true;
        clearTimeout(timeout);
        observer.disconnect();
        resolve(found);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
    });
  });
}

// --- Action Execution ---

/**
 * Execute a click action with proper event dispatching for React/Vue compatibility.
 */
function executeClick(element: HTMLElement): void {
  // Scroll into view
  element.scrollIntoView({ behavior: "smooth", block: "center" });

  // Small delay after scroll
  setTimeout(() => {
    // Focus the element
    element.focus();

    // Get element center for realistic mouse events
    const rect = element.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;

    const eventOptions = {
      bubbles: true,
      cancelable: true,
      composed: true,
      clientX: x,
      clientY: y,
      view: window,
    };

    // Full mouse event sequence for React/Vue compatibility
    element.dispatchEvent(new MouseEvent("mousedown", eventOptions));
    element.dispatchEvent(new MouseEvent("mouseup", eventOptions));
    element.dispatchEvent(new MouseEvent("click", eventOptions));
  }, 100);
}

/**
 * Execute an input action using native value setter for React compatibility.
 */
function executeInput(element: HTMLElement, value: string): void {
  const inputEl = element as HTMLInputElement | HTMLTextAreaElement;

  // Focus
  element.focus();
  element.dispatchEvent(new FocusEvent("focus", { bubbles: true }));

  // Use the native value setter to bypass React's controlled component
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value"
  )?.set;
  const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype,
    "value"
  )?.set;

  const setter =
    element.tagName === "TEXTAREA"
      ? nativeTextAreaValueSetter
      : nativeInputValueSetter;

  if (setter) {
    setter.call(inputEl, value);
  } else {
    inputEl.value = value;
  }

  // Dispatch events that React/Vue listen to
  element.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
  element.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
}

/**
 * Execute a key press action.
 */
function executeKeyPress(element: HTMLElement | null, key: string): void {
  const target = element || document.activeElement || document.body;

  // Map common key names
  const keyMap: Record<string, { key: string; code: string; keyCode: number }> =
    {
      Enter: { key: "Enter", code: "Enter", keyCode: 13 },
      Tab: { key: "Tab", code: "Tab", keyCode: 9 },
      Escape: { key: "Escape", code: "Escape", keyCode: 27 },
      Backspace: { key: "Backspace", code: "Backspace", keyCode: 8 },
      ArrowDown: { key: "ArrowDown", code: "ArrowDown", keyCode: 40 },
      ArrowUp: { key: "ArrowUp", code: "ArrowUp", keyCode: 38 },
      ArrowLeft: { key: "ArrowLeft", code: "ArrowLeft", keyCode: 37 },
      ArrowRight: { key: "ArrowRight", code: "ArrowRight", keyCode: 39 },
      Space: { key: " ", code: "Space", keyCode: 32 },
    };

  const mapped = keyMap[key] || {
    key,
    code: `Key${key.toUpperCase()}`,
    keyCode: key.charCodeAt(0),
  };

  const eventOptions = {
    key: mapped.key,
    code: mapped.code,
    keyCode: mapped.keyCode,
    which: mapped.keyCode,
    bubbles: true,
    cancelable: true,
    composed: true,
  };

  target.dispatchEvent(new KeyboardEvent("keydown", eventOptions));
  target.dispatchEvent(new KeyboardEvent("keypress", eventOptions));
  target.dispatchEvent(new KeyboardEvent("keyup", eventOptions));
}

/**
 * Execute a scroll action.
 */
function executeScroll(scrollX: number, scrollY: number): void {
  window.scrollTo({
    left: scrollX,
    top: scrollY,
    behavior: "smooth",
  });
}

// --- Visual Feedback ---

let highlightOverlay: HTMLElement | null = null;

function highlightElement(element: HTMLElement): void {
  removeHighlight();

  const rect = element.getBoundingClientRect();
  highlightOverlay = document.createElement("div");
  highlightOverlay.style.cssText = `
    position: fixed;
    left: ${rect.left - 3}px;
    top: ${rect.top - 3}px;
    width: ${rect.width + 6}px;
    height: ${rect.height + 6}px;
    border: 3px solid #3B82F6;
    border-radius: 4px;
    background: rgba(59, 130, 246, 0.1);
    z-index: 999999;
    pointer-events: none;
    transition: all 0.2s ease;
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);
  `;
  document.body.appendChild(highlightOverlay);

  // Auto-remove after 2 seconds
  setTimeout(removeHighlight, 2000);
}

function removeHighlight(): void {
  if (highlightOverlay && highlightOverlay.parentNode) {
    highlightOverlay.parentNode.removeChild(highlightOverlay);
    highlightOverlay = null;
  }
}

// --- Main Step Executor ---

async function executeStep(
  step: Record<string, unknown>
): Promise<{ success: boolean; error?: string }> {
  const stepType = step.type as string;

  console.log(`[Executor] Executing step: ${stepType}`, step);

  try {
    // Handle navigation steps (background handles these via chrome.tabs.update)
    if (stepType === "navigation") {
      // Navigation is handled by background.ts — this shouldn't reach here
      // But if it does, navigate via window.location
      const url = step.url as string;
      if (url) {
        window.location.href = url;
        return { success: true };
      }
      return { success: false, error: "Navigation step has no URL" };
    }

    // Handle scroll steps
    if (stepType === "scroll") {
      const scrollX = (step.scrollX as number) || 0;
      const scrollY = (step.scrollY as number) || 0;
      executeScroll(scrollX, scrollY);
      return { success: true };
    }

    // For all other steps, find the target element
    const element = await waitForElement(step);

    if (!element) {
      const targetText = (step.target_text || step.targetText) as string;
      const cssSelector = step.cssSelector as string;
      return {
        success: false,
        error: `Element not found. target_text="${targetText || "none"}", cssSelector="${cssSelector || "none"}"`,
      };
    }

    // Highlight the element for visual feedback
    highlightElement(element);

    switch (stepType) {
      case "click":
        executeClick(element);
        return { success: true };

      case "input": {
        const value = step.value as string;
        if (value === undefined || value === null) {
          return { success: false, error: "Input step has no value" };
        }
        executeInput(element, value);
        return { success: true };
      }

      case "key_press": {
        const key = step.key as string;
        if (!key) {
          return { success: false, error: "Key press step has no key" };
        }
        executeKeyPress(element, key);
        return { success: true };
      }

      case "select_change": {
        const value = step.value as string;
        if (value !== undefined) {
          (element as HTMLSelectElement).value = value;
          element.dispatchEvent(
            new Event("change", { bubbles: true, composed: true })
          );
          return { success: true };
        }
        return { success: false, error: "Select step has no value" };
      }

      default:
        return { success: false, error: `Unknown step type: ${stepType}` };
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

// --- Message Listener ---

export default defineContentScript({
  matches: ["<all_urls>"],
  runAt: "document_idle",
  main() {
    console.log("[Executor] Content executor loaded on:", window.location.href);

    // Listen for step execution commands from background
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message.type === "EXECUTE_STEP") {
        const step = message.step;
        const stepIndex = message.stepIndex;

        console.log(`[Executor] Received step ${stepIndex}:`, step);

        // Execute async and send response
        executeStep(step).then((result) => {
          console.log(`[Executor] Step ${stepIndex} result:`, result);
          sendResponse({
            type: "STEP_RESULT",
            stepIndex,
            ...result,
          });
        });

        return true; // Keep channel open for async response
      }

      if (message.type === "EXECUTOR_PING") {
        sendResponse({ type: "EXECUTOR_PONG", url: window.location.href });
        return false;
      }

      return false;
    });

    // Notify background that executor is ready
    chrome.runtime.sendMessage({
      type: "EXECUTOR_READY",
      url: window.location.href,
    });
  },
});
