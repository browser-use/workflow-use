# Workflow-Use

Semantic browser automation with deterministic workflow generation and variables.

## Quick Start

### 1. Test Deterministic Workflow Generation (NEW!)
```bash
python examples/scripts/deterministic/run_complete_test.py
```

Generate workflows **without LLM for step creation** - 10-100x faster, guaranteed semantic steps.

### 2. Create Your Own Workflow
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

### 3. Run a Workflow
```bash
cd /path/to/workflow-use/workflows
python cli.py run-workflow-no-ai my_workflow.json

# If the workflow has variables, the CLI will prompt you interactively:
# Enter value for repo_name (required, type: string): browser-use
```

---

## Key Features

### 🚀 Deterministic Workflow Generation
- **Direct Action Mapping**: `input_text` → `input` step (no LLM)
- **Guaranteed Semantic Steps**: 0 agent steps (instant execution, $0/run)
- **10-100x Faster**: 5-10s vs 20-40s for LLM-based
- **90% Cheaper**: Minimal LLM usage

### 🎯 Variables in Workflows
- **Reusable Workflows**: Parameterize dynamic values
- **Semantic Targeting**: Use `{variable}` in `target_text`
- **Auto-Extraction**: LLM suggests variables automatically

---

## Documentation

- **[docs/DETERMINISTIC.md](docs/DETERMINISTIC.md)** - Deterministic workflow generation
- **[docs/VARIABLES.md](docs/VARIABLES.md)** - Variables guide
- **[examples/README.md](examples/README.md)** - Example scripts

---

## Project Structure

```
workflows/
├── workflow_use/              # Main package
│   ├── healing/              # Workflow generation & healing
│   │   ├── deterministic_converter.py   # NEW: Deterministic conversion
│   │   ├── variable_extractor.py        # Auto variable detection
│   │   └── service.py                   # Main workflow generation
│   ├── workflow/             # Workflow execution
│   │   └── semantic_executor.py         # Semantic step execution
│   ├── controller/           # Workflow controller
│   ├── recorder/             # Workflow recording
│   ├── storage/              # Storage logic
│   ├── mcp/                  # MCP integration
│   ├── schema/               # Schema definitions
│   └── builder/              # Workflow builder
│
├── backend/                  # FastAPI backend service
│   ├── api.py               # API entry point
│   ├── routers.py           # API routes
│   └── service.py           # Business logic
│
├── examples/                 # Examples organized by feature
│   ├── scripts/
│   │   ├── deterministic/   # Deterministic workflow examples
│   │   │   ├── run_complete_test.py        # ⭐ Test deterministic generation
│   │   │   └── create_deterministic_workflow.py
│   │   ├── variables/       # Variable feature examples
│   │   ├── demos/           # Advanced demos
│   │   └── runner.py        # Generic workflow runner
│   └── workflows/           # Example workflow JSON files
│       ├── basic/           # Basic workflow examples
│       ├── form_filling/    # Form filling examples
│       ├── parameterized/   # Parameterized workflows
│       └── advanced/        # Advanced workflows
│
├── tests/                    # Test files
│   ├── test_button_click.py
│   └── test_recorded_workflow.py
│
├── docs/                     # Documentation
│   ├── DETERMINISTIC.md     # Deterministic workflows
│   └── VARIABLES.md         # Variables guide
│
├── data/                     # Runtime & test data
│   └── test_data/           # Test data (tracked in git)
│       ├── form-filling/
│       └── flight-test/
│
├── cli.py                   # CLI entry point
├── pyproject.toml          # Project configuration
└── README.md               # This file
```

---

## Comparison: Deterministic vs LLM-Based

| Feature | Deterministic | LLM-Based |
|---------|---------------|-----------|
| Generation Speed | ⚡ 5-10s | 🐌 20-40s |
| Generation Cost | 💰 $0.01-0.05 | 💸 $0.10-0.30 |
| Agent Steps | ✅ 0 guaranteed | ❌ Variable |
| Deterministic | ✅ Yes | ❌ No |
| Execution Speed | ⚡ Instant | 🐌 5-45s |
| Execution Cost | 💰 $0/run | 💸 $0.03-0.30/run |

**Recommendation**: Use deterministic for most workflows (search, click, input, navigate).

---

## Testing

```bash
# Test deterministic generation
python examples/scripts/deterministic/run_complete_test.py

# Test variables
python examples/scripts/variables/create_workflow_with_variables.py

# Compare approaches
python examples/scripts/deterministic/test_deterministic_workflow.py
```

---

## Next Steps

1. ✅ Run `examples/run_complete_test.py`
2. ✅ Review the generated workflow JSON
3. ✅ Try creating your own workflow
4. ✅ Add variables to make it reusable
