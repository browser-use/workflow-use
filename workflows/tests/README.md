# Semantic-Only Workflow System - Unit Tests

Comprehensive unit test suite for the semantic-only multi-strategy workflow system.

## Test Coverage

### ✅ 39 Total Tests Across 3 Components

1. **SelectorGenerator** (14 tests) - `test_selector_generator.py`
2. **ElementFinder** (14 tests) - `test_element_finder.py`
3. **Workflow Execution** (11 tests) - `test_workflow_execution.py`

## Running Tests

### Run All Tests
```bash
uv run python tests/run_all_tests.py
```

### Run Individual Test Modules
```bash
# Test SelectorGenerator
uv run python tests/test_selector_generator.py

# Test ElementFinder
uv run python tests/test_element_finder.py

# Test Workflow Execution
uv run python tests/test_workflow_execution.py
```

## Test Descriptions

### 1. SelectorGenerator Tests (`test_selector_generator.py`)

**Purpose**: Validate that `SelectorGenerator` creates ONLY semantic strategies (no CSS/xpath/id).

**Key Tests**:
- ✅ Button with text generates semantic strategies (text_exact, role_text, text_fuzzy)
- ✅ NO CSS/xpath/id strategies are generated (semantic-only validation)
- ✅ ARIA label strategy generation
- ✅ Placeholder strategy for inputs
- ✅ Title attribute strategy
- ✅ Alt text strategy for images
- ✅ Role inference for common tags (button, link, input, etc.)
- ✅ Explicit role attribute takes precedence
- ✅ Strategy priority ordering (lower number = higher priority)
- ✅ No strategies for elements without semantic data
- ✅ `generate_strategies_dict()` returns JSON-serializable dicts
- ✅ Fuzzy text match only for meaningful text (>3 chars)
- ✅ `SelectorStrategy.to_dict()` and `from_dict()` serialization
- ✅ `get_summary()` returns human-readable output

**Coverage**:
- All 7 semantic strategy types
- Priority ordering
- Role inference logic
- Serialization/deserialization
- Edge cases (empty data, short text)

---

### 2. ElementFinder Tests (`test_element_finder.py`)

**Purpose**: Validate that `ElementFinder` correctly searches browser-use's DOM state using semantic strategies and returns element indices.

**Key Tests**:
- ✅ Find element by `text_exact` strategy
- ✅ Find element by `role_text` strategy
- ✅ Find element by `aria_label` strategy
- ✅ Find element by `placeholder` strategy
- ✅ Find element by `title` strategy
- ✅ Find element by `alt_text` strategy
- ✅ Fuzzy text matching with threshold
- ✅ Multiple strategies fallback (priority order)
- ✅ No match returns `None`
- ✅ Empty strategies list returns `None`
- ✅ No DOM state returns `None`
- ✅ Empty selector_map returns `None`
- ✅ Fuzzy matching threshold validation
- ✅ Case insensitivity in fuzzy matching

**Coverage**:
- All 7 semantic strategy matching algorithms
- Priority-based fallback
- Edge cases (no DOM, no match, empty strategies)
- Fuzzy matching logic with thresholds

---

### 3. Workflow Execution Tests (`test_workflow_execution.py`)

**Purpose**: Validate the fixes for `go_back`/`go_forward` (empty action models) and deterministic execution.

**Key Tests**:
- ✅ `go_back` action uses `None` params (not `{}`)
- ✅ `go_forward` action uses `None` params
- ✅ Other actions preserve their params
- ✅ Action model format for empty actions (`{action_name: None}`)
- ✅ NavigationStep schema validation
- ✅ Click actions use multi-strategy finding
- ✅ Input actions use multi-strategy finding
- ✅ Actions without strategies skip multi-strategy
- ✅ Element index injection after multi-strategy finding
- ✅ Semantic strategies format validation
- ✅ Actions requiring wait after execution

**Coverage**:
- Empty action handling (go_back/go_forward fix)
- Multi-strategy integration with workflow execution
- Element index injection
- Action-specific logic
- Schema validation

---

## Test Architecture

### No External Dependencies
- Tests use **mocks** instead of real browser/LLM instances
- Fast execution (< 1 second total)
- No network calls or external services
- Can run in CI/CD pipelines

### Async Test Support
Tests handle both sync and async methods seamlessly using `asyncio.run()`.

### Clear Output
Each test provides:
- ✅ PASS/❌ FAIL status
- Descriptive test names
- Assertion messages explaining failures
- Summary at the end

---

## What These Tests Validate

### 1. Semantic-Only Architecture
- **Zero CSS selectors** - No brittle `#submit-btn` or `.btn-primary`
- **Zero XPath** - No fragile `/html/body/div[3]/button[2]`
- **Zero ID selectors** - No `id` attribute dependencies
- **100% semantic** - Only text, role, ARIA, placeholder, title, alt

### 2. Multi-Strategy Fallback System
- **7 prioritized strategies** per element
- **Automatic fallback** if higher-priority strategies fail
- **Fuzzy matching** as fallback for typos/variations
- **Browser-use integration** - Returns indices, not Playwright handles

### 3. Deterministic Execution Fixes
- **Empty actions** (`go_back`, `go_forward`) use `None` params
- **No Pydantic validation errors** on empty action models
- **Multi-strategy optimization** - Fast path for semantic finding
- **Element index injection** - Seamless controller integration

---

## CI/CD Integration

Add to your CI pipeline:

```yaml
- name: Run Semantic Workflow Tests
  run: |
    cd workflows
    uv run python tests/run_all_tests.py
```

Exit code:
- `0` = All tests passed ✅
- `1` = Some tests failed ❌

---

## Test Maintenance

### Adding New Tests

1. Create test method with `test_` prefix
2. Add assertions with clear failure messages
3. Run `uv run python tests/run_all_tests.py` to verify

Example:
```python
def test_new_feature(self):
    """Test description"""
    result = some_function()
    assert result == expected, f"Expected {expected}, got {result}"
```

### Debugging Failures

Each test file can be run individually for detailed output:
```bash
uv run python tests/test_selector_generator.py
```

---

## Summary

| Component | Tests | Status |
|-----------|-------|--------|
| SelectorGenerator | 14 | ✅ All Pass |
| ElementFinder | 14 | ✅ All Pass |
| Workflow Execution | 11 | ✅ All Pass |
| **TOTAL** | **39** | **✅ All Pass** |

**Test Suite Status**: 🟢 100% Passing

---

## Related Documentation

- **[Semantic-Only Refactor Plan](../SEMANTIC_ONLY_REFACTOR_PLAN.md)** - Architecture overview
- **[Deterministic Workflows](../docs/DETERMINISTIC.md)** - Deterministic conversion guide
- **[README](../README.md)** - Project overview

---

## Contact

For questions or issues with tests, please refer to the main project README or open an issue.
