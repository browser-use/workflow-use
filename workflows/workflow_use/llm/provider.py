"""Configurable LLM provider for workflow-use.

Reads LLM configuration from environment variables (loaded from .env)
and returns the appropriate LLM instance. Supports local inference via
LM Studio / Ollama (OpenAI-compatible API) or the Browser Use cloud API.

Environment variables:
    LLM_PROVIDER    - "local" (default) or "browser_use"
    LLM_BASE_URL    - Base URL for local server (default: http://localhost:1234/v1)
    LLM_API_KEY     - API key (default: "not-needed" for local)
    LLM_MODEL       - Model name for general tasks (default: bu-30b-a3b-preview)
    LLM_HEALING_MODEL - Lighter model for healing/extraction (default: same as LLM_MODEL)
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

# Load .env from the workflows directory
load_dotenv()


def get_llm(purpose: str = 'default'):
	"""Returns a configured LLM instance based on .env settings.

	Args:
		purpose: One of "default", "healing", "extraction", "generation".
			"healing" and "extraction" use LLM_HEALING_MODEL (lighter model).
			"default" and "generation" use LLM_MODEL.

	Returns:
		A BaseChatModel instance (ChatOpenAI or ChatBrowserUse).
	"""
	provider = os.getenv('LLM_PROVIDER', 'local').lower()

	if provider == 'browser_use':
		from browser_use.llm import ChatBrowserUse
		return ChatBrowserUse(model='bu-latest')

	# Local provider (LM Studio, Ollama, or any OpenAI-compatible server)
	from langchain_openai import ChatOpenAI

	base_url = os.getenv('LLM_BASE_URL', 'http://localhost:1234/v1')
	api_key = os.getenv('LLM_API_KEY', 'not-needed')
	default_model = os.getenv('LLM_MODEL', 'bu-30b-a3b-preview')
	healing_model = os.getenv('LLM_HEALING_MODEL', default_model)

	if purpose in ('healing', 'extraction'):
		model = healing_model
	else:
		model = default_model

	return ChatOpenAI(
		model=model,
		base_url=base_url,
		api_key=api_key,
	)
