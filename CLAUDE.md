# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Workflow Use is a browser automation tool that records browser interactions and replays them as deterministic workflows, with LLM-powered self-healing when steps fail. It's a fork of `browser-use/workflow-use` with local LLM support and improved self-healing.

**Three-tier architecture:** Chrome Extension (recorder) → Python Backend (execution) → React UI (visualization)

## Build & Run Commands

### Python Backend (workflows/)
```bash
cd workflows
uv sync                          # Install dependencies (Python 3.11+, uses hatchling)
source .venv/bin/activate
playwright install chromium       # Browser engine
cp .env.example .env             # Configure LLM provider
python cli.py --help             # CLI entry point
python cli.py launch-gui         # Starts FastAPI (8000) + Vite (5173) + opens browser
```

### Chrome Extension (extension/)
```bash
cd extension
npm install && npm run build     # Build to .output/chrome-mv3/
npm run dev                      # Watch mode
```

### React UI (ui/)
```bash
cd ui
npm install                      # postinstall auto-generates types from backend OpenAPI
npm run dev                      # Dev server on port 5173
npm run type-gen-update          # Regenerate TS types from running backend
```

### Lint (all components)
```bash
./lint.sh                        # Runs ruff + ESLint + tsc for all three
# Or individually:
cd workflows && uv run ruff check && uv run ruff format --check
cd ui && npm run lint
cd extension && npm run lint
```

### Tests
```bash
cd workflows && uv run pytest tests/       # Run all tests
uv run pytest tests/test_wait_times.py     # Single test file
```

## Code Style

Python: Ruff with **tabs for indentation**, single quotes, 130 char line length. Rules: ASYNC, E, F, FAST, I, PLE (see pyproject.toml `[tool.ruff]`).

## Architecture

### Communication Flow
```
Extension content.ts → background.ts → HTTP POST :7331/event → RecordingService
UI (React :5173) → REST API :8000 → backend/routers.py → WorkflowService
Workflow execution: Workflow.run() → _execute_step() → controller actions → Playwright
```

### Key Modules (workflows/workflow_use/)

**`llm/provider.py`** — LLM factory. Reads `.env` for `LLM_PROVIDER` (local/browser_use), `LLM_BASE_URL`, `LLM_MODEL`, `LLM_HEALING_MODEL`. Returns `ChatOpenAI` for local (LM Studio/Ollama) or `ChatBrowserUse` for cloud. Entry point: `get_llm(purpose)`.

**`workflow/service.py`** — `Workflow` class. Main execution orchestrator. Loads from YAML, resolves variables, runs steps sequentially. On failure, delegates to `StepHealer` for vision-based repair. Key params: `enable_self_healing`, `debug` (captures screenshots).

**`healing/step_healer.py`** — Vision-based step repair. On failure: screenshot → LLM diagnosis → corrected selectors → retry. Tracks results in `logs/healing/healing_results.tsv`. Uses snapshot/revert pattern (saves YAML before healing, reverts if fix fails). Exponential backoff between retries.

**`healing/service.py`** — `HealingService`. Generates workflows from prompts by running a browser agent, capturing element mappings, then converting to deterministic steps. Two paths: LLM-based (`create_workflow_definition`) or deterministic (`_create_workflow_deterministically`). Post-processes with pattern-based variable identification.

**`schema/views.py`** — Pydantic models for workflow steps. `SelectorWorkflowSteps` has `target_text` (primary, semantic), `selectorStrategies` (fallback list), and legacy `cssSelector`/`xpath`. Step types: navigation, click, input, select_change, key_press, scroll, extract_page_content, agent.

**`recorder/service.py`** — Spawns Chromium with extension loaded, runs FastAPI on :7331 to receive events from extension. Extension captures clicks/inputs/keypresses with semantic text, XPath, CSS selectors.

**`controller/service.py`** — Maps workflow step types to browser-use actions. `controller/utils.py` has `get_best_element_handle()` with stable selector fallback generation.

**`workflow/element_finder.py`** — Multi-strategy element finding. Priority: semantic text strategies (exact, role, aria_label, placeholder, fuzzy) → XPath JavaScript evaluation. Returns element index or XPath string.

**`mcp/service.py`** — Exposes workflows as MCP tools via FastMCP. Dynamically generates function signatures from workflow input_schema.

**`storage/service.py`** — File-based CRUD. Workflows stored as `.workflow.yaml` in `storage/workflows/`. Metadata index at `storage/metadata.json`.

### Extension (extension/src/)
- `content.ts` — Injected into pages. Captures clicks, inputs, keypresses with semantic label extraction (aria-label, label[for], sibling text, etc.). Uses RRWeb for DOM recording.
- `background.ts` — Service worker. Stores events per tab, converts to semantic format, POSTs to Python server at :7331.
- `sidepanel/` — React UI for recording controls and live event viewer.

### CLI (workflows/cli.py)
95KB typer app. Key commands: `create-workflow`, `run-workflow`, `run-workflow-no-ai`, `run-workflow-csv`, `generate-workflow`, `launch-gui`, `mcp-server`. Module-level `get_llm()` initialization — if LLM server is down, CLI still loads but LLM-dependent commands will fail.

## Fork-Specific Details

- **Origin**: `github.com/Stefz29/workflow-use` (fork), **Upstream**: `github.com/browser-use/workflow-use`
- **LLM Provider**: Defaults to local LM Studio at `localhost:1234` instead of Browser Use cloud API
- **Self-Healing**: Added `StepHealer` with autoresearch-mlx patterns (snapshot/revert, TSV results tracking, exponential backoff, fail-fast checks)
- **Spec**: Full project roadmap in `~/Downloads/workflow-use-fork-instructions.md`

## Ports
| Service | Port |
|---------|------|
| FastAPI backend | 8000 |
| Recording server | 7331 |
| Vite UI dev | 5173 |
| LM Studio (local LLM) | 1234 |
