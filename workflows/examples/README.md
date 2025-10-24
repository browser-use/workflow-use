# Workflow Examples

## Quick Start

### Test Deterministic Workflow Generation
```bash
python run_complete_test.py
```
Expected: "✅ TEST PASSED - Pure semantic workflow generated!"

---

## Files

### 🆕 Deterministic Workflow Generation (NEW!)
- **`run_complete_test.py`** ⭐ - Complete validation test
- **`create_deterministic_workflow.py`** - Simple creation example  
- **`test_deterministic_workflow.py`** - Compare deterministic vs LLM-based
- **`test_custom_task.py`** - Test with your own task
- **`auto_generate_workflow.py`** - Auto-generate from task description

### 🎯 Variables
- **`create_workflow_with_variables.py`** - Create workflows with variables
- **`run_workflow_with_variables.py`** - Run workflows with different inputs
- **`github_stars_parameterized.workflow.json`** - Example parameterized workflow

### 📚 Other Demos
- **`generation_mode_demo.py`** - Workflow generation modes
- **`cloud_browser_demo.py`** - Cloud browser usage
- **`semantic_extraction_demo.py`** - Semantic data extraction
- **`hierarchical_selection_demo.py`** - Complex hierarchical selections
- **`travel_booking_demo.py`** - Travel booking workflow
- **`runner.py`** - Generic workflow runner

### 📄 Example Workflows
- **`example.workflow.json`** - Basic workflow example
- **`pure_semantic.workflow.json`** - Pure semantic workflow
- **`semantic_form_fill.workflow.json`** - Semantic form filling

---

## Key Concepts

### 1. Deterministic Conversion (NEW!)
```python
service = HealingService(llm=llm, use_deterministic_conversion=True)
workflow = await service.generate_workflow_from_prompt(...)
```

**Benefits:** ⚡ 10-100x faster | 💰 90% cheaper | ✅ 0 agent steps

### 2. Variables in Workflows
```json
{
  "input_schema": [{"name": "repo_name", "type": "string", "required": true}],
  "steps": [
    {"type": "input", "target_text": "Search", "value": "{repo_name}"}
  ]
}
```

---

## Documentation
- **`../README_DETERMINISTIC.md`** - Deterministic workflow generation
- **`../README_VARIABLES.md`** - Variables guide
- **`../README.md`** - Main documentation
