# Workflow-Use

Semantic browser automation with deterministic workflow generation and variables.

## Quick Start

### 1. Test Deterministic Workflow Generation (NEW!)
```bash
cd examples
python run_complete_test.py
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

- **[README_DETERMINISTIC.md](README_DETERMINISTIC.md)** - Deterministic workflow generation
- **[README_VARIABLES.md](README_VARIABLES.md)** - Variables guide
- **[examples/README.md](examples/README.md)** - Example scripts

---

## Project Structure

```
workflows/
├── workflow_use/
│   ├── healing/
│   │   ├── deterministic_converter.py   # NEW: Deterministic conversion
│   │   ├── variable_extractor.py        # Auto variable detection
│   │   └── service.py                   # Main workflow generation
│   └── workflow/
│       └── semantic_executor.py         # Semantic step execution
├── examples/
│   ├── run_complete_test.py            # ⭐ Test deterministic generation
│   ├── create_deterministic_workflow.py # Simple example
│   └── test_variable_features.py       # Test variables
└── README.md                            # This file
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
cd examples

# Test deterministic generation
python run_complete_test.py

# Test variables
python create_workflow_with_variables.py

# Compare approaches
python test_deterministic_workflow.py
```

---

## Next Steps

1. ✅ Run `examples/run_complete_test.py`
2. ✅ Review the generated workflow JSON
3. ✅ Try creating your own workflow
4. ✅ Add variables to make it reusable
