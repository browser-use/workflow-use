# Resume Instructions for Claude Code

## Quick Context

This is a browser automation project (workflow-use). We're building a Chrome extension that:
1. **Records** user actions in their own Chrome browser (DONE - working)
2. **Replays** those actions in the SAME browser (IN PROGRESS)
3. **Self-heals** when steps fail using a local LLM (PLANNED)

## How to Resume Work

### Step 1: Read the Architecture
```
Read these files first:
- /Users/SZ/Desktop/Claude_APPS/workflow-use/CLAUDE.md (project overview)
- /Users/SZ/Desktop/Claude_APPS/workflow-use/docs/PHASE2_PLAN.md (overall plan)
- /Users/SZ/Desktop/Claude_APPS/workflow-use/docs/PHASE2B_BROWSER_EXECUTION.md (current work)
- /Users/SZ/Desktop/Claude_APPS/workflow-use/docs/SESSION_LOG.md (what's been done)
```

### Step 2: Start Services
```bash
# 1. Start the Python backend
cd /Users/SZ/Desktop/Claude_APPS/workflow-use/workflows
source .venv/bin/activate
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --log-level info &

# 2. Verify backend is running
curl http://127.0.0.1:8000/api/recorder/health

# 3. LM Studio (only if testing self-healing)
# Load bu-30b-a3b-preview model, server on port 1234
```

### Step 3: Build & Load Extension
```bash
# Build the extension
cd /Users/SZ/Desktop/Claude_APPS/workflow-use/extension
npm run build

# Then in Chrome:
# 1. Go to chrome://extensions/
# 2. Enable Developer Mode
# 3. Click "Load unpacked" → select extension/.output/chrome-mv3/
#    (use Cmd+Shift+. in Finder to show hidden .output folder)
# 4. Click the extension icon to open sidepanel
```

### Step 4: Current Task — Build In-Browser Execution

**What's next:** Building the content-executor.ts and ExecutionEngine so recorded workflows replay IN the user's Chrome browser (not Playwright).

**Key files to work with:**
- `extension/src/entrypoints/content-executor.ts` — NEW: executes steps on the page
- `extension/src/entrypoints/background.ts` — ADD: ExecutionEngine class
- `extension/src/entrypoints/sidepanel/components/dashboard-view.tsx` — ADD: "Run in Browser" button
- `workflows/backend/ext_execution_router.py` — NEW: healing API for extension execution

**Architecture summary:**
1. `content-executor.ts` finds elements (target_text → CSS → XPath) and executes actions (click, input, keypress)
2. `background.ts` ExecutionEngine orchestrates: sends steps one-by-one, handles navigation, re-injects content script
3. Backend only involved for self-healing (screenshot → LLM → corrected selectors)

**Critical design points:**
- Content script DIES on page navigation — background must re-inject it
- Element finding: target_text (semantic) is primary, CSS/XPath are fallbacks
- Real DOM events needed (not just element.click()) to trigger React/Vue handlers
- Tab/window tracking: extension captures tabId+windowId during recording, uses same at replay
- Service worker may sleep after 30s idle in MV3 — keep alive during execution

**Reusable code from content.ts:**
- `extractSemanticInfo()` — extract labels/text from elements (use in REVERSE for finding)
- `getXPath()` — XPath generation
- `getEnhancedCSSSelector()` — CSS selector generation
- Overlay highlighting code from mouseover handler

## Project Structure (Key Paths)

```
/Users/SZ/Desktop/Claude_APPS/workflow-use/
├── CLAUDE.md                          # Project instructions
├── docs/                              # Architecture docs (read these!)
│   ├── PHASE2_PLAN.md
│   ├── PHASE2B_BROWSER_EXECUTION.md
│   ├── SESSION_LOG.md
│   └── RESUME_INSTRUCTIONS.md         # This file
├── extension/                          # Chrome Extension (WXT + React)
│   ├── src/entrypoints/
│   │   ├── background.ts              # Service worker (orchestrator)
│   │   ├── content.ts                 # Recording content script
│   │   ├── content-executor.ts        # NEW: Execution content script
│   │   └── sidepanel/                 # React UI
│   │       ├── index.tsx              # Tab navigation (Dashboard|Record|Settings)
│   │       ├── components/
│   │       │   ├── dashboard-view.tsx # Workflow list
│   │       │   ├── settings-view.tsx  # Backend config
│   │       │   ├── stopped-view.tsx   # Save workflow
│   │       │   └── tab-navigation.tsx # Tab bar
│   │       └── context/
│   │           └── workflow-provider.tsx
│   ├── wxt.config.ts                  # Manifest config
│   └── .output/chrome-mv3/           # Built extension (load this in Chrome)
├── workflows/                         # Python Backend
│   ├── .env                           # LLM config (LM Studio)
│   ├── backend/
│   │   ├── api.py                     # FastAPI app + CORS
│   │   ├── routers.py                 # Workflow CRUD + execute endpoints
│   │   ├── recorder_router.py         # Recording event endpoints
│   │   └── service.py                 # Workflow execution service
│   └── workflow_use/
│       ├── healing/step_healer.py     # LLM self-healing
│       ├── recorder/service.py        # Old Playwright recorder (legacy)
│       └── workflow/service.py        # Workflow execution
└── ui/                                # React UI (Vite :5173)
```

## .env Configuration
```
LLM_PROVIDER=local
LLM_BASE_URL=http://192.168.1.15:1234/v1
LLM_API_KEY=not-needed
LLM_MODEL=bu-30b-a3b-preview
LLM_HEALING_MODEL=bu-30b-a3b-preview
```

## Ports
| Service | Port |
|---------|------|
| FastAPI backend | 8000 |
| Recording server (legacy) | 7331 |
| Vite UI dev | 5173 |
| LM Studio (local LLM) | 1234 |
