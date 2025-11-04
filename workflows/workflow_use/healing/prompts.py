from pathlib import Path

# Use __file__ to get absolute path relative to this file's location
_PROMPTS_DIR = Path(__file__).parent / '_agent'
HEALING_AGENT_SYSTEM_PROMPT = (_PROMPTS_DIR / 'agent_prompt.md').read_text()
