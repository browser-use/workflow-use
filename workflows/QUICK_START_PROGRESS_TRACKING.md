# Quick Start: Progress Tracking

## 5-Minute Integration Guide

### Step 1: Update Your Code (Add 6 Lines)

**Before:**
```python
async def generate_without_tracking():
    return await healing_service.generate_workflow_from_prompt(
        prompt="Search for Python",
        agent_llm=llm,
        extraction_llm=llm,
    )
```

**After:**
```python
# Add these callback functions (2 lines)
def step_cb(data): print(f"Step {data['step_number']}: {data['description']}")
def status_cb(status): print(f"Status: {status}")

# Add callbacks to method call (2 parameters)
async def generate_with_tracking():
    return await healing_service.generate_workflow_from_prompt(
        prompt="Search for Python",
        agent_llm=llm,
        extraction_llm=llm,
        on_step_recorded=step_cb,    # NEW
        on_status_update=status_cb,  # NEW
    )
```

**That's it!** You now have real-time progress tracking.

---

## Step 2: For Database Storage (Browser-Use Cloud)

```python
import asyncio

# Application-specific dependencies: replace these imports with your database
# session factory and workflow query helper.
from your_app.database import database, get_workflow

workflow_id = "your-workflow-id"

async def step_callback(step_data: dict):
    """Store step in database for real-time display."""
    async with await database.get_session() as session:
        workflow = await get_workflow(session, workflow_id)
        workflow.generation_metadata['steps'].append(step_data)
        await session.commit()

pending_tasks: list[asyncio.Task[None]] = []

def schedule_step(step_data: dict) -> None:
    """Schedule the async write while satisfying the callback's None return type."""
    pending_tasks.append(asyncio.create_task(step_callback(step_data)))

async def main():
    await healing_service.generate_workflow_from_prompt(
        prompt=task_prompt,
        agent_llm=llm,
        extraction_llm=llm,
        on_step_recorded=schedule_step,
    )
    if pending_tasks:
        await asyncio.gather(*pending_tasks)

asyncio.run(main())
```

---

## Step 3: Create Polling Endpoint

```python
# Application-specific dependencies: `router`, `database`, and `get_workflow`
# must come from your web and persistence layers.
@router.get("/workflows/{workflow_id}/progress")
async def get_progress(workflow_id: str):
    async with await database.get_session() as session:
        workflow = await get_workflow(session, workflow_id)
        metadata = workflow.generation_metadata or {}

        return {
            "steps_recorded": len(metadata.get('steps', [])),
            "latest_step": metadata.get('steps', [])[-1] if metadata.get('steps') else None,
            "is_complete": workflow.status == 'completed'
        }
```

---

## Step 4: Frontend (Poll Every 2 Seconds)

```typescript
const { data } = useQuery(
  ['workflow-progress', workflowId],
  () => fetch(`/workflows/${workflowId}/progress`).then(r => r.json()),
  { refetchInterval: 2000 }
);

return (
  <div>
    <p>Steps recorded: {data?.steps_recorded}</p>
    <p>Latest: {data?.latest_step?.description}</p>
  </div>
);
```

---

## Complete Example

```python
from workflow_use.healing.service import HealingService
from browser_use.llm import ChatBrowserUse
import asyncio

# Simple console logging
def log_step(data):
    print(f"📍 Step {data['step_number']}: {data['description']}")
    print(f"   Type: {data['action_type']}, URL: {data['url']}")

def log_status(status):
    print(f"🔄 {status}")

async def main():
    # Initialize
    llm = ChatBrowserUse(model='bu-latest')
    service = HealingService(llm=llm, use_deterministic_conversion=True)

    # Generate with tracking
    workflow = await service.generate_workflow_from_prompt(
        prompt="Go to example.com and extract the title",
        agent_llm=llm,
        extraction_llm=llm,
        on_step_recorded=log_step,
        on_status_update=log_status,
    )

    print(f"✅ Done! Generated {len(workflow.steps)} steps")

if __name__ == "__main__":
    asyncio.run(main())
```

**Output:**
```
🔄 Initializing browser...
🔄 Creating browser agent...
🔄 Recording workflow steps...
📍 Step 1: Navigate to https://example.com
   Type: navigation, URL: https://example.com
📍 Step 2: Extract page content
   Type: extract, URL: https://example.com
🔄 Completed recording 2 steps
🔄 Converting steps to workflow (deterministic)...
🔄 Post-processing workflow (variable identification & cleanup)...
🔄 Workflow generation complete!
✅ Done! Generated 2 steps
```

---

## Callback Data Reference

### `on_step_recorded` receives:
```python
{
    'step_number': 1,
    'action_type': 'click',
    'description': 'Click on "Search"',
    'url': 'https://example.com',
    'selector': '//button[@id="search"]',
    'target_text': 'Search',
    'timestamp': '2025-01-19T10:30:45.123456+00:00',
    'extracted_data': None  # Only for extract steps
}
```

### `on_status_update` receives:
```python
"Initializing browser..."
"Creating browser agent..."
"Recording workflow steps..."
"Completed recording N steps"
"Converting steps to workflow..."
"Workflow generation complete!"
```

---

## Key Points

✅ **Optional** - Works without callbacks (backward compatible)
✅ **Real-time** - Fires during browser actions, not after
✅ **Safe** - Callback errors won't break workflow generation
✅ **Flexible** - Use for logging, database, UI, anything
✅ **Fast** - Minimal overhead (~1-5ms per step)

---

## Common Patterns

### Pattern 1: Store in List
```python
steps = []

async def generate():
    return await service.generate_workflow_from_prompt(
        ...,
        on_step_recorded=lambda d: steps.append(d)
    )
```

### Pattern 2: Async Database Write
```python
def schedule_db_write(data: dict) -> None:
    asyncio.create_task(store_in_db(data))

async def generate():
    return await service.generate_workflow_from_prompt(
        ...,
        on_step_recorded=schedule_db_write,
    )
```

### Pattern 3: Progress Bar
```python
def show_progress(data):
    bar = "█" * data["step_number"] + "░" * (10 - data["step_number"])
    print(f"\r[{bar}] {data['description'][:40]}...", end="")

async def generate():
    return await service.generate_workflow_from_prompt(
        ...,
        on_step_recorded=show_progress
    )
```

---

## Need More Details?

- 📖 Full guide: `docs/PROGRESS_TRACKING.md`
- 💡 Examples: `examples/progress_tracking_example.py`
- 🧪 Tests: `tests/test_progress_tracking.py`
- 📋 Summary: `IMPLEMENTATION_SUMMARY.md`

---

## Troubleshooting

**Problem:** Callback not firing
**Solution:** Pass function reference, not function call
```python
# ✅ Correct
on_step_recorded=my_callback

# ❌ Wrong
on_step_recorded=my_callback()
```

**Problem:** Async callback blocking workflow
**Solution:** Wrap in `asyncio.create_task()`
```python
def schedule_callback(data: dict) -> None:
    asyncio.create_task(async_callback(data))

on_step_recorded=schedule_callback
```

**Problem:** Steps missing from database
**Solution:** Ensure you `await session.commit()`

---

**That's all you need to get started!** 🚀
