# Phase 2: Standalone Chrome Extension Dashboard

## Status: Phase 2a COMPLETE
**Started:** 2026-03-16
**Phase 2a Completed:** 2026-03-16
**Current Phase:** 2b — Dashboard & Workflow Management (ready to start)

---

## Problem Statement

The current recording flow launches a **separate Playwright Chromium instance** with the extension pre-loaded. This means:
- User's credentials/cookies are NOT available (no LinkedIn Recruiter, no logged-in sessions)
- Risk of getting banned on sites that detect automation
- Poor UX — separate browser window, no integration with user's workflow

## Solution

Run the extension **directly in the user's own Chrome browser**, communicating with the existing Python backend via HTTP. No Playwright needed for recording.

```
Current:  Playwright Chromium (isolated) → extension → temp server :7331
Phase 2:  USER'S Chrome (with credentials) → extension → main backend :8000
```

---

## Architecture Overview

### Communication Flow (Phase 2)
```
User's Chrome (extension)
  content.ts  ─── chrome.runtime.sendMessage ──→  background.ts
                                                      │
                                                      ├── HTTP POST :8000/api/recorder/event    (recording events)
                                                      ├── GET  :8000/api/workflows               (list workflows)
                                                      ├── POST :8000/api/workflows               (save recorded workflow)
                                                      ├── POST :8000/api/workflows/{id}/execute  (run workflow)
                                                      └── GET  :8000/api/config                  (LLM settings)

  sidepanel ←── chrome.runtime messages ←── background.ts
```

### Key Design Decisions
- **Sidepanel** (not popup) — stays open while user browses, essential for recording
- **All API calls go through background.ts** — centralizes error handling, avoids CORS issues
- **Execution still uses Playwright** initially — extension records and manages, backend executes
- **Backend must be running** — extension shows a clear connection indicator

---

## Reusability Assessment

| Component | Status | Notes |
|-----------|--------|-------|
| `content.ts` (DOM event capture) | 100% reusable | All handlers, semantic extraction, selectors work as-is |
| `background.ts` (event aggregation) | ~90% reusable | Make endpoint configurable, add dashboard message types |
| Sidepanel views (Recording/Stopped/EventViewer) | ~80% reusable | Add tab navigation wrapper |
| Types (`lib/types.ts`, `lib/workflow-types.ts`) | 100% reusable | Independent of browser launch method |
| UI components (`components/ui/`) | 100% reusable | Shadcn primitives |
| WXT config, Tailwind, build pipeline | 100% reusable | No changes needed |
| Backend routers/services | Reusable + additions | Need recording endpoints on :8000 |

---

## Phase Breakdown

### Phase 2a — Extension Independence (CURRENT)

**Goal:** Extension works standalone in user's Chrome, saves workflows to backend.

#### Tasks:
1. [x] Add recording endpoints to main backend (:8000)
   - `POST /api/recorder/event` — accepts RecorderEvent (same as :7331)
   - `POST /api/recorder/start` — initializes recording session
   - `POST /api/recorder/stop` — finalizes and saves workflow
   - `GET /api/recorder/status` — check if recording is active

2. [x] Make extension server endpoint configurable
   - Replace hardcoded `http://127.0.0.1:7331/event` in background.ts
   - Default to `http://127.0.0.1:8000/api/recorder/event`
   - Store in `chrome.storage.sync`

3. [x] Update extension manifest permissions
   - Add `storage` permission
   - Update `host_permissions` for :8000

4. [x] Update StoppedView to save workflow to backend
   - POST workflow to backend API instead of just downloading JSON
   - Show success/error feedback

5. [x] Add CORS support for Chrome extension origin in backend

#### Files Modified:
- `workflows/workflow_use/backend/routers.py` — new recording endpoints
- `extension/src/entrypoints/background.ts` — configurable endpoint
- `extension/wxt.config.ts` — manifest permissions
- `extension/src/entrypoints/sidepanel/views/StoppedView.tsx` — save to backend

### Phase 2b — Dashboard & Workflow Management

**Goal:** Full dashboard UI in the extension sidepanel.

#### Tasks:
5. Add tab navigation to sidepanel: Dashboard | Record | Settings
6. Dashboard view — list saved workflows with Run/Edit/Delete
7. Execution status tracking — progress indicator when workflow runs

#### New Files:
- `extension/src/entrypoints/sidepanel/views/DashboardView.tsx`
- `extension/src/entrypoints/sidepanel/components/WorkflowCard.tsx`
- `extension/src/entrypoints/sidepanel/components/TabNavigation.tsx`

### Phase 2c — Settings & LLM Configuration

**Goal:** Configure the backend's LLM from the extension UI.

#### Tasks:
8. Settings view — backend URL, LLM provider dropdown, model name, "Test Connection"
9. Backend config API (`GET/PUT /api/config`) for runtime LLM changes

#### New Files:
- `extension/src/entrypoints/sidepanel/views/SettingsView.tsx`
- `workflows/workflow_use/backend/config_router.py`

### Phase 2d — Natural Language Features

**Goal:** Talk in plain English to create and configure workflows.

#### Tasks:
10. Natural language step input during recording
11. "Generate workflow from description" in Dashboard
12. Chat-like interface for workflow configuration

---

## Technical Notes

### CORS for Chrome Extensions
Chrome extension background scripts making `fetch()` requests are NOT subject to CORS.
However, if sidepanel components make direct fetch calls, the backend needs:
```python
allow_origins=["chrome-extension://<extension-id>"]
```
Best practice: route all API calls through background.ts.

### Backend Must Be Running
The extension depends on the backend being up. Need:
- Connection status indicator in sidepanel header
- Clear error messages when backend is unreachable
- Auto-reconnect logic

### Recording Server Port Conflict
The old :7331 recording server (from Playwright flow) and the new :8000 endpoints can coexist.
The CLI `create-workflow` command still works with Playwright for users who prefer it.

### State Synchronization
If user has both the React UI (:5173) and extension open:
- Both hit the same backend API
- React UI polls, so changes from extension appear on refresh
- No WebSocket needed initially

---

## Port Reference
| Service | Port |
|---------|------|
| FastAPI backend | 8000 |
| Recording server (legacy) | 7331 |
| Vite UI dev | 5173 |
| LM Studio (local LLM) | 1234 |
