# Deterministic Workflow Generation

## Quick Start

Generate workflows **without LLM for step creation** - directly map browser actions to semantic steps:

```python
from workflow_use.healing.service import HealingService
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model_name="claude-3-5-sonnet-20241022")

service = HealingService(llm=llm, use_deterministic_conversion=True)

workflow = await service.generate_workflow_from_prompt(
    prompt="Go to GitHub, search for browser-use, get star count",
    agent_llm=llm,
    extraction_llm=llm
)
```

## Test It

```bash
cd examples
python run_complete_test.py
```

Expected: "✅ TEST PASSED - Pure semantic workflow (0 agent steps)"

## How It Works

Direct action-to-step mapping (no LLM):

```
input_text      →  input step with target_text
click_element   →  click step with target_text
send_keys       →  keypress step
navigate        →  navigation step
```

## Benefits

| Metric | Deterministic | LLM-Based |
|--------|---------------|-----------|
| Generation Speed | ⚡ 5-10s | 🐌 20-40s |
| Cost per Generation | 💰 $0.01-0.05 | 💸 $0.10-0.30 |
| Agent Steps | ✅ 0 guaranteed | ❌ Variable |
| Execution Speed | ⚡ Instant | 🐌 5-45s |
| Execution Cost | 💰 $0/run | 💸 $0.03-0.30/run |

## Files

**Core:**
- `workflow_use/healing/deterministic_converter.py` - Converter
- `workflow_use/healing/service.py` - Integration (added `use_deterministic_conversion` flag)

**Examples:**
- `examples/run_complete_test.py` - Full validation test
- `examples/create_deterministic_workflow.py` - Simple example
- `examples/test_custom_task.py` - Test your own task

## Running Workflows

```bash
cd /path/to/workflow-use/workflows
python cli.py run-workflow-no-ai my_workflow.json

# If the workflow has variables, the CLI will prompt you interactively:
# Enter value for repo_name (required, type: string): browser-use
```

## Validation

Workflows should have:
- ✅ Zero `agent` type steps
- ✅ Only: `navigation`, `input`, `click`, `keypress`, `extract_page_content`
- ✅ Non-empty `target_text` in click/input steps

## When to Use

**Use Deterministic (recommended):**
- ✅ Straightforward interactions (search, click, input, navigate)
- ✅ Need guaranteed semantic steps
- ✅ Want fast, cheap generation

**Use LLM-Based:**
- Complex, context-dependent workflows
- Need LLM to optimize/refactor steps

## Troubleshooting

**Import error:**
```bash
cd /path/to/workflow-use/workflows
python examples/run_complete_test.py
```

**Still getting agent steps:**
Check `service.py` has the routing logic:
```python
if self.use_deterministic_conversion:
    workflow_definition = await self._create_workflow_deterministically(...)
```
