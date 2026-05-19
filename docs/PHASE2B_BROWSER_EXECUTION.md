# Phase 2b: In-Browser Workflow Execution

## Status: STARTING
**Date:** 2026-03-17

## Problem
Workflow execution via Playwright launches a SEPARATE Chromium browser with no cookies/sessions.
This defeats the purpose for sites requiring auth (LinkedIn Recruiter, etc.) and triggers bot detection.

## Solution
The Chrome extension itself replays workflow steps in the SAME browser where they were recorded.
No Playwright needed. Same cookies, same sessions, same everything.

## Architecture

```
YOUR Chrome (same browser, same cookies, same session)
┌─────────────────────────────────────────────────────────┐
│  background.ts (ExecutionEngine - orchestrator)          │
│  - Manages step queue & state machine                    │
│  - Survives page navigations (service worker)            │
│  - Sends one step at a time to content script            │
│  - Re-injects content script after navigation            │
│  - Captures screenshots for self-healing                 │
│                                                          │
│  content-executor.ts (NEW - executes steps on page)      │
│  - Finds elements: target_text → CSS → XPath             │
│  - Executes: click(), fill(), keypress via real DOM       │
│  - Reports success/failure back to background             │
│  - Highlights element being acted on                     │
│                                                          │
│  sidepanel (execution progress UI)                       │
│  - "Run in Browser" button                               │
│  - Step-by-step progress with status indicators           │
└─────────────────────────────────────────────────────────┘
         │ HTTP (only when healing needed)
         ▼
┌─────────────────────────────────────────────────────────┐
│  Python Backend (:8000)                                  │
│  POST /api/ext-execute/heal                              │
│  - Receives screenshot + failed step                     │
│  - LLM diagnoses what changed on the page                │
│  - Returns corrected selectors                           │
└─────────────────────────────────────────────────────────┘
```

## Tab/Window Tracking

The user may have multiple browsers open (2 Chrome, Firefox, Safari).
- The extension ONLY sees its own Chrome instance
- During recording, every event captures `tabId` and `windowId`
- At replay: check if original tab exists → use it. Original window? → find matching tab. Otherwise → ask user.
- `windowId` distinguishes between multiple Chrome windows

## Execution Flow

### Step-by-Step:
1. User clicks "Run in Browser" in sidepanel
2. Background resolves target tab (recorded tabId/windowId or active tab)
3. For each step in workflow:
   a. **navigation**: `chrome.tabs.update(tabId, {url})` → wait for load → inject executor
   b. **click/input/key_press**: send step to content-executor → wait for result
   c. **scroll**: send to content-executor → `window.scrollTo()`
4. After each step that might cause navigation:
   - Monitor `chrome.tabs.onUpdated` for URL change
   - Wait for `status: "complete"` → re-inject executor → `EXECUTOR_READY` handshake
5. On step failure: capture screenshot → send to backend heal endpoint → retry with corrected selectors

### State Machine:
```
IDLE → LOADING → EXECUTING → WAITING_FOR_NAV → HEALING → COMPLETED/FAILED
```

## Content Executor: Element Finding

Priority order (same as recording, but in reverse):
1. **target_text (semantic)**: Scan interactive elements, match by textContent/aria-label/placeholder/label
2. **cssSelector**: `document.querySelector(cssSelector)`
3. **xpath**: `document.evaluate(xpath)`

### Action Execution (Real DOM Events):
- **click**: `element.focus()` → `element.click()` (or full MouseEvent sequence for React/Vue)
- **input**: Native value setter → InputEvent → change event
- **key_press**: KeyboardEvent('keydown') + ('keyup')
- **scroll**: `window.scrollTo(x, y)`

## Navigation Handling (Critical)

When a click causes page navigation:
1. Content script on old page DIES (Chrome destroys it)
2. Background service worker SURVIVES — it monitors `chrome.tabs.onUpdated`
3. New page finishes loading → background re-injects content-executor.ts
4. Content script sends `EXECUTOR_READY` → background sends next step

## Self-Healing Integration

When a step fails:
1. Content-executor reports failure with error to background
2. Background captures screenshot via `chrome.tabs.captureVisibleTab()`
3. Background POSTs screenshot + step context to `POST /api/ext-execute/heal`
4. Backend runs StepHealer LLM diagnosis → returns corrected selectors
5. Background sends corrected step to content-executor for retry
6. Max 3 retries before marking step as failed

## Implementation Order

### Phase 1: Content Executor
- [ ] Create `content-executor.ts` with element finding + step execution
- [ ] Register in wxt.config.ts
- [ ] Message protocol: EXECUTE_STEP / STEP_RESULT / EXECUTOR_READY

### Phase 2: Background ExecutionEngine
- [ ] Add ExecutionEngine class to background.ts
- [ ] Step queue, state machine, tab tracking
- [ ] Navigation detection + content script re-injection
- [ ] Screenshot capture for healing

### Phase 3: Backend Healing API
- [ ] Create ext_execution_router.py
- [ ] Adapt StepHealer to accept pre-captured screenshots
- [ ] Wire up in api.py

### Phase 4: Sidepanel UI
- [ ] Execution progress view
- [ ] "Run in Browser" button in dashboard
- [ ] Tab/window selector

### Phase 5: Edge Cases
- [ ] Dynamic content waits (MutationObserver)
- [ ] iframes
- [ ] New tabs/popups during execution
- [ ] Service worker sleep prevention (MV3 30s idle timeout)

## Key Files
- `extension/src/entrypoints/content.ts` — Has reusable functions: extractSemanticInfo(), getXPath(), getEnhancedCSSSelector()
- `extension/src/entrypoints/background.ts` — Orchestrator to extend
- `extension/src/lib/workflow-types.ts` — Step type definitions
- `workflows/workflow_use/healing/step_healer.py` — Self-healing to adapt
- `workflows/backend/recorder_router.py` — Pattern for new execution router
