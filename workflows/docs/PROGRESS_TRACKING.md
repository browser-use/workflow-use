# Real-time Progress Tracking for Workflow Generation

## Overview

The `HealingService.generate_workflow_from_prompt()` method now supports real-time progress tracking through two optional callback parameters:

1. **`on_step_recorded`**: Fired whenever a browser action is successfully recorded during workflow generation
2. **`on_status_update`**: Fired for general status updates during the workflow processing phases

## Why This Feature?

Previously, `generate_workflow_from_prompt()` was a black box - you called it with a prompt and waited for the complete workflow to be returned, with no visibility into what was happening during generation. This made it impossible to:

- Show users real-time progress during workflow generation
- Display steps as they're being recorded (not just after completion)
- Provide meaningful status updates ("Recording step 3...", "Extracting variables...", etc.)
- Debug generation failures with context about where it failed
- Build responsive UIs that show live progress

## API Reference

### Method Signature

```python
async def generate_workflow_from_prompt(
    self,
    prompt: str,
    agent_llm: BaseChatModel,
    extraction_llm: BaseChatModel,
    use_cloud: bool = False,
    on_step_recorded: Optional[StepRecordedCallback] = None,
    on_status_update: Optional[StatusUpdateCallback] = None,
) -> WorkflowDefinitionSchema
```

### Callback Parameters

#### `on_step_recorded: Optional[Callable[[Dict[str, Any]], None]]`

Called each time a workflow step is successfully recorded. Receives a dictionary with:

| Field | Type | Description |
|-------|------|-------------|
| `step_number` | `int` | 1-indexed step number |
| `action_type` | `str` | Action type: `'navigation'`, `'click'`, `'input_text'`, `'extract'`, `'keypress'`, `'scroll'`, etc. |
| `description` | `str` | Human-readable description (e.g., "Click on 'Search'") |
| `url` | `str` | Current page URL |
| `selector` | `Optional[str]` | CSS/XPath selector if applicable |
| `extracted_data` | `Optional[dict]` | Extracted data for extract steps |
| `timestamp` | `str` | ISO 8601 timestamp (UTC) |
| `target_text` | `Optional[str]` | Element text being interacted with |

**Example callback data:**
```python
{
    'step_number': 3,
    'action_type': 'click',
    'description': 'Click on "Search"',
    'url': 'https://example.com',
    'selector': '//button[@id="search-btn"]',
    'extracted_data': None,
    'timestamp': '2025-01-19T10:30:45.123456+00:00',
    'target_text': 'Search'
}
```

#### `on_status_update: Optional[Callable[[str], None]]`

Called for non-step status updates during workflow processing. Receives a string message.

**Status messages include:**
- `"Initializing browser..."`
- `"Creating browser agent..."`
- `"Recording workflow steps..."`
- `"Completed recording N steps"`
- `"Converting steps to workflow (deterministic)..."` or `"Analyzing workflow with AI..."`
- `"Validating workflow with AI..."` (if AI validation enabled)
- `"Post-processing workflow (variable identification & cleanup)..."`
- `"Workflow generation complete!"`

## Usage Examples

### Example 1: Simple Console Logging

```python
import asyncio

from browser_use.llm import ChatBrowserUse
from workflow_use.healing.service import HealingService

def step_callback(step_data: dict):
    print(f"Step {step_data['step_number']}: {step_data['description']}")
    print(f"  Type: {step_data['action_type']}")
    print(f"  URL: {step_data['url']}")

def status_callback(status: str):
    print(f"Status: {status}")

async def main():
    llm = ChatBrowserUse(model='bu-latest')
    healing_service = HealingService(llm=llm, use_deterministic_conversion=True)

    await healing_service.generate_workflow_from_prompt(
        prompt="Search for Python on Google",
        agent_llm=llm,
        extraction_llm=llm,
        on_step_recorded=step_callback,
        on_status_update=status_callback,
    )

if __name__ == "__main__":
    asyncio.run(main())
```

**Output:**
```
Status: Initializing browser...
Status: Creating browser agent...
Status: Recording workflow steps...
Step 1: Navigate to https://www.google.com
  Type: navigation
  URL: https://www.google.com
Step 2: Enter "Python" into Search
  Type: input_text
  URL: https://www.google.com
Step 3: Click on "Google Search"
  Type: click
  URL: https://www.google.com
Status: Completed recording 3 steps
Status: Converting steps to workflow (deterministic)...
Status: Post-processing workflow (variable identification & cleanup)...
Status: Workflow generation complete!
```

### Example 2: Database Storage Pattern (for Browser-Use Cloud)

```python
import asyncio
from datetime import datetime, timezone

async def step_callback(step_data: dict):
    """Store step immediately in database for real-time display."""
    async with await database.get_session() as session:
        workflow = await get_workflow(session, workflow_id)

        if workflow and workflow.generation_metadata:
            steps = workflow.generation_metadata.get('steps', [])
            steps.append(step_data)
            workflow.generation_metadata['steps'] = steps

            await session.commit()
            logger.info(f"Recorded step {step_data['step_number']}: {step_data['description']}")

async def status_callback(status: str):
    """Store status update in database."""
    async with await database.get_session() as session:
        workflow = await get_workflow(session, workflow_id)

        if workflow and workflow.generation_metadata:
            status_history = workflow.generation_metadata.get('status_history', [])
            status_history.append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message': status
            })
            workflow.generation_metadata['status_history'] = status_history

            await session.commit()

pending_tasks: list[asyncio.Task[None]] = []

def schedule_step(data: dict) -> None:
    pending_tasks.append(asyncio.create_task(step_callback(data)))

def schedule_status(status: str) -> None:
    pending_tasks.append(asyncio.create_task(status_callback(status)))

async def main():
    await healing_service.generate_workflow_from_prompt(
        prompt=task_prompt,
        agent_llm=llm,
        extraction_llm=llm,
        use_cloud=False,
        on_step_recorded=schedule_step,
        on_status_update=schedule_status,
    )
    if pending_tasks:
        await asyncio.gather(*pending_tasks)

if __name__ == "__main__":
    asyncio.run(main())
```

**Frontend polling (every 2 seconds):**
```python
@router.get("/workflows/{workflow_id}/progress")
async def get_workflow_progress(workflow_id: str):
    """Get real-time progress of workflow generation."""
    async with await database.get_session() as session:
        workflow = await get_workflow(session, workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        metadata = workflow.generation_metadata or {}

        return {
            "workflow_id": workflow_id,
            "status": workflow.status,
            "steps_recorded": len(metadata.get('steps', [])),
            "latest_step": metadata.get('steps', [])[-1] if metadata.get('steps') else None,
            "status_history": metadata.get('status_history', []),
            "is_complete": workflow.status == 'completed'
        }
```

### Example 3: Progress Bar

```python
import asyncio

def step_callback(step_data: dict):
    """Update progress bar as steps are recorded."""
    bar = "█" * step_data["step_number"] + "░" * (10 - step_data["step_number"])
    print(f"\rProgress: [{bar}] Step {step_data['step_number']}: {step_data['description'][:40]}...", end="")

def status_callback(status: str):
    print(f"\n\n{status}")

async def main():
    await healing_service.generate_workflow_from_prompt(
        prompt="Search for Python documentation",
        agent_llm=llm,
        extraction_llm=llm,
        on_step_recorded=step_callback,
        on_status_update=status_callback,
    )

if __name__ == "__main__":
    asyncio.run(main())
```

**Output:**
```
Status: Initializing browser...
Status: Recording workflow steps...
Progress: [███░░░░░░░] Step 3: Click on "Search"...
Status: Completed recording 5 steps
Status: Workflow generation complete!
```

## When Callbacks Are Fired

### `on_step_recorded` Timeline

The `on_step_recorded` callback fires **during browser action execution**, NOT during post-processing. This ensures real-time updates as the agent works:

```
Agent.run() starts
  ├─→ Action 1: Navigate to URL
  │   ├─→ Execute action
  │   └─→ 🔥 on_step_recorded(step_number=1, action_type='navigation', ...)
  │
  ├─→ Action 2: Click element
  │   ├─→ Execute action
  │   └─→ 🔥 on_step_recorded(step_number=2, action_type='click', ...)
  │
  └─→ Action 3: Input text
      ├─→ Execute action
      └─→ 🔥 on_step_recorded(step_number=3, action_type='input_text', ...)

Agent.run() completes
```

### `on_status_update` Timeline

The `on_status_update` callback fires at key phases:

```
generate_workflow_from_prompt() starts
  ├─→ 🔥 "Initializing browser..."
  ├─→ 🔥 "Creating browser agent..."
  ├─→ 🔥 "Recording workflow steps..."
  │    (on_step_recorded fires for each action here)
  ├─→ 🔥 "Completed recording N steps"
  ├─→ 🔥 "Converting steps to workflow..."
  ├─→ 🔥 "Validating workflow with AI..." (if enabled)
  ├─→ 🔥 "Post-processing workflow..."
  └─→ 🔥 "Workflow generation complete!"
```

## Callback Execution

### Synchronous Callbacks

Callbacks can be synchronous functions:

```python
import asyncio

def step_callback(step_data: dict):
    print(f"Step recorded: {step_data['description']}")

async def main():
    await healing_service.generate_workflow_from_prompt(
        ...,
        on_step_recorded=step_callback,
    )

asyncio.run(main())
```

### Asynchronous Callbacks

For async operations (database writes, API calls), wrap in `asyncio.create_task`:

```python
import asyncio

async def async_step_callback(step_data: dict):
    async with db_session() as session:
        await session.execute(...)

pending_tasks: list[asyncio.Task[None]] = []

def schedule_step(data: dict) -> None:
    pending_tasks.append(asyncio.create_task(async_step_callback(data)))

async def main():
    await healing_service.generate_workflow_from_prompt(
        ...,
        on_step_recorded=schedule_step,
    )
    if pending_tasks:
        await asyncio.gather(*pending_tasks)

asyncio.run(main())
```

## Error Handling

Both callback types are wrapped in try-except blocks to prevent callback errors from breaking workflow generation:

```python
# Step callbacks are isolated where each action is recorded.
try:
    self.on_step_recorded(callback_data)
except Exception as e:
    print(f'⚠️  Warning: Failed to fire step recorded callback: {e}')
    # Workflow generation continues normally

# Status callbacks use a shared exception-isolating helper.
_emit_status_update(on_status_update, 'Initializing browser...')
```

This ensures that even if your callback fails (e.g., database connection error), the workflow generation will complete successfully.

## Performance Considerations

### Callback Overhead

- **Synchronous callbacks**: Minimal overhead (~1-5ms per call)
- **Async callbacks with `create_task()`**: Non-blocking, no impact on generation speed
- **Blocking I/O**: Avoid synchronous database writes or API calls in callbacks

### Recommended Patterns

✅ **Good - Non-blocking async:**
```python
def schedule_store(data: dict) -> None:
    asyncio.create_task(store_in_db(data))

on_step_recorded=schedule_store
```

✅ **Good - Fast synchronous:**
```python
on_step_recorded=lambda data: in_memory_list.append(data)
```

❌ **Bad - Blocking synchronous:**
```python
def step_callback(data):
    requests.post('http://api.example.com', json=data)  # Blocks workflow generation!
```

## Backward Compatibility

The callbacks are **fully optional** and **backward compatible**. Existing code continues to work unchanged:

```python
import asyncio

# Old code - still works perfectly
async def main():
    await healing_service.generate_workflow_from_prompt(
        prompt="Search for Python",
        agent_llm=llm,
        extraction_llm=llm,
    )

    # New code - with callbacks
    await healing_service.generate_workflow_from_prompt(
        prompt="Search for Python",
        agent_llm=llm,
        extraction_llm=llm,
        on_step_recorded=my_callback,  # Optional
    )

asyncio.run(main())
```

## Debugging with Callbacks

### Example: Debug Logger

```python
import asyncio
import logging

logger = logging.getLogger(__name__)

def debug_step_callback(step_data: dict):
    """Log detailed step information for debugging."""
    logger.debug(f"Step {step_data['step_number']} executed:")
    logger.debug(f"  Action: {step_data['action_type']}")
    logger.debug(f"  Description: {step_data['description']}")
    logger.debug(f"  URL: {step_data['url']}")
    logger.debug(f"  Selector: {step_data.get('selector', 'N/A')}")
    logger.debug(f"  Target: {step_data.get('target_text', 'N/A')}")
    logger.debug(f"  Timestamp: {step_data['timestamp']}")

def debug_status_callback(status: str):
    logger.info(f"Status: {status}")

async def main():
    await healing_service.generate_workflow_from_prompt(
        prompt="Search for Python",
        agent_llm=llm,
        extraction_llm=llm,
        on_step_recorded=debug_step_callback,
        on_status_update=debug_status_callback,
    )

asyncio.run(main())
```

### Example: Failure Detection

```python
import asyncio

failure_detected = {'failed': False, 'last_step': None}

def detect_failure_callback(step_data: dict):
    """Track last successful step for failure debugging."""
    failure_detected['last_step'] = step_data

    # Detect potential issues
    if step_data['action_type'] == 'extract' and not step_data.get('extracted_data'):
        print(f"⚠️  Warning: Extraction at step {step_data['step_number']} returned no data")

async def main():
    try:
        await healing_service.generate_workflow_from_prompt(
            prompt="Complex task",
            agent_llm=llm,
            extraction_llm=llm,
            on_step_recorded=detect_failure_callback,
        )
    except Exception:
        print("❌ Workflow generation failed!")
        if failure_detected['last_step']:
            print(f"Last successful step: {failure_detected['last_step']['step_number']}")
            print(f"Last action: {failure_detected['last_step']['description']}")
            print(f"Last URL: {failure_detected['last_step']['url']}")

asyncio.run(main())
```

## Integration with Browser-Use Cloud

### Database Schema Addition

Add a `generation_metadata` JSON field to your workflow model:

```python
class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(String, primary_key=True)
    name = Column(String)
    status = Column(String)  # 'pending', 'generating', 'completed', 'failed'

    # NEW: Store real-time generation progress
    generation_metadata = Column(JSON, default=lambda: {
        'steps': [],
        'status_history': [],
        'started_at': None,
        'completed_at': None
    })
```

### Backend Implementation

```python
import asyncio
from datetime import datetime, timezone

async def generate_workflow_with_tracking(
    workflow_id: str,
    task_prompt: str,
    llm: BaseChatModel
):
    """Generate workflow with real-time progress tracking."""
    pending_tasks: list[asyncio.Task[None]] = []

    async def step_callback(step_data: dict):
        """Store step immediately in database."""
        async with await database.get_session() as session:
            workflow = await get_workflow(session, workflow_id)

            if workflow:
                if not workflow.generation_metadata:
                    workflow.generation_metadata = {'steps': [], 'status_history': []}

                workflow.generation_metadata['steps'].append(step_data)
                await session.commit()

    async def status_callback(status: str):
        """Store status updates."""
        async with await database.get_session() as session:
            workflow = await get_workflow(session, workflow_id)

            if workflow:
                if not workflow.generation_metadata:
                    workflow.generation_metadata = {'steps': [], 'status_history': []}

                workflow.generation_metadata['status_history'].append({
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'message': status
                })

                # Update workflow status
                if status == 'Workflow generation complete!':
                    workflow.status = 'completed'
                    workflow.generation_metadata['completed_at'] = datetime.now(timezone.utc).isoformat()

                await session.commit()

    # Set initial status
    async with await database.get_session() as session:
        workflow = await get_workflow(session, workflow_id)
        workflow.status = 'generating'
        workflow.generation_metadata = {
            'steps': [],
            'status_history': [],
            'started_at': datetime.now(timezone.utc).isoformat()
        }
        await session.commit()

    # Generate workflow with progress tracking
    healing_service = HealingService(llm=llm, use_deterministic_conversion=True)

    def schedule_step(data: dict) -> None:
        pending_tasks.append(asyncio.create_task(step_callback(data)))

    def schedule_status(status: str) -> None:
        pending_tasks.append(asyncio.create_task(status_callback(status)))

    workflow = await healing_service.generate_workflow_from_prompt(
        prompt=task_prompt,
        agent_llm=llm,
        extraction_llm=llm,
        use_cloud=False,
        on_step_recorded=schedule_step,
        on_status_update=schedule_status,
    )
    if pending_tasks:
        await asyncio.gather(*pending_tasks)

    return workflow
```

### Frontend Polling API

```python
@router.get("/api/workflows/{workflow_id}/progress")
async def get_workflow_progress(workflow_id: str):
    """Poll for real-time workflow generation progress."""
    async with await database.get_session() as session:
        workflow = await get_workflow(session, workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        metadata = workflow.generation_metadata or {}
        steps = metadata.get('steps', [])
        status_history = metadata.get('status_history', [])

        return {
            "workflow_id": workflow_id,
            "status": workflow.status,
            "started_at": metadata.get('started_at'),
            "completed_at": metadata.get('completed_at'),
            "steps_recorded": len(steps),
            "latest_step": steps[-1] if steps else None,
            "latest_status": status_history[-1] if status_history else None,
            "all_steps": steps,
            "status_history": status_history,
            "is_complete": workflow.status == 'completed',
            "is_generating": workflow.status == 'generating'
        }
```

### Frontend React Component

```typescript
// Poll every 2 seconds for updates
const { data, isLoading } = useQuery(
  ['workflow-progress', workflowId],
  () => fetch(`/api/workflows/${workflowId}/progress`).then(r => r.json()),
  {
    refetchInterval: (data) => data?.is_complete ? false : 2000,
    enabled: !!workflowId
  }
);

return (
  <div>
    <h2>Workflow Generation Progress</h2>

    <div className="status">
      {data?.latest_status?.message}
    </div>

    <div className="progress">
      {data?.steps_recorded} steps recorded
    </div>

    <div className="steps">
      {data?.all_steps?.map((step, i) => (
        <div key={i} className="step">
          <span className="step-number">{step.step_number}</span>
          <span className="step-description">{step.description}</span>
          <span className="step-time">{new Date(step.timestamp).toLocaleTimeString()}</span>
        </div>
      ))}
    </div>
  </div>
);
```

## Complete Example

See `examples/progress_tracking_example.py` for complete working examples including:
- Simple console logging
- Database storage pattern
- Progress bar
- Browser-Use Cloud backend integration pattern

## Migration Guide

### Before (No Progress Tracking)

```python
async def generate_without_tracking():
    workflow = await healing_service.generate_workflow_from_prompt(
        prompt="Search for Python",
        agent_llm=llm,
        extraction_llm=llm,
    )
    # Wait... no visibility into what's happening
    # Workflow returned when complete
    return workflow
```

### After (With Progress Tracking)

```python
def step_callback(step_data: dict):
    print(f"Recording step {step_data['step_number']}: {step_data['description']}")

def status_callback(status: str):
    print(f"Status: {status}")

async def generate_with_tracking():
    workflow = await healing_service.generate_workflow_from_prompt(
        prompt="Search for Python",
        agent_llm=llm,
        extraction_llm=llm,
        on_step_recorded=step_callback,  # NEW: Real-time step tracking
        on_status_update=status_callback,  # NEW: Status updates
    )
    # See each step as it's recorded!
    # Know exactly what's happening at each phase!
    return workflow
```

## FAQ

### Q: Do I need to use both callbacks?

No, both are optional. Use only the callbacks you need:
- Just steps: `on_step_recorded=callback`
- Just status: `on_status_update=callback`
- Both: `on_step_recorded=step_cb, on_status_update=status_cb`
- Neither: Leave both as `None` (default)

### Q: Will callbacks slow down workflow generation?

No, if implemented correctly:
- Synchronous callbacks: ~1-5ms overhead per call (negligible)
- Async callbacks with `create_task()`: Non-blocking, zero impact
- Only blocking I/O (sync database writes, API calls) will slow generation

### Q: What happens if my callback throws an exception?

The exception is caught and logged, but workflow generation continues normally. Your callback errors won't break the workflow generation process.

### Q: Can I store callbacks in the database?

No, callbacks are Python functions and must be passed at runtime. However, you can use callbacks to store their *data* in the database (see "Database Storage Pattern" example).

### Q: How do I test this locally?

See `examples/progress_tracking_example.py` for runnable examples. Uncomment the example you want to test and run:

```bash
cd workflow-use
python examples/progress_tracking_example.py
```

## Troubleshooting

### Callback Not Firing

**Problem:** Callback isn't being called

**Solution:** Ensure you're passing the callback correctly:
```python
# ✅ Correct
on_step_recorded=my_callback

# ❌ Incorrect (calling the function instead of passing it)
on_step_recorded=my_callback()
```

### Async Callback Blocking

**Problem:** Async callback is blocking workflow generation

**Solution:** Wrap in `asyncio.create_task()`:
```python
# ❌ Blocks workflow generation
on_step_recorded=async_callback

# ✅ Non-blocking
def schedule_callback(data: dict) -> None:
    asyncio.create_task(async_callback(data))

on_step_recorded=schedule_callback
```

### Missing Steps in Database

**Problem:** Some steps are missing from the database

**Solution:** Ensure your database writes are awaited and handle exceptions:
```python
async def step_callback(step_data: dict):
    try:
        async with db_session() as session:
            await session.execute(...)
            await session.commit()  # Don't forget to commit!
    except Exception as e:
        logger.error(f"Failed to store step: {e}")
        # Consider retrying or storing in a queue
```

## Support

For issues, questions, or feature requests related to progress tracking, please:
1. Check this documentation
2. Review `examples/progress_tracking_example.py`
3. Open an issue on GitHub with the `progress-tracking` label
