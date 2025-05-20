import os

from langchain_openai import ChatOpenAI
from pydantic import SecretStr


class ChatOpenRouter(ChatOpenAI):
	def __init__(
		self,
		model: str,
		openai_api_key: str | None = None,
		openai_api_base: str = 'https://openrouter.ai/api/v1',
		**kwargs,
	):
		key = openai_api_key or os.getenv('OPENROUTER_API_KEY')
		super().__init__(
			openai_api_base=openai_api_base,
			openai_api_key=SecretStr(key) if key else None,
			model_name=model,
			**kwargs,
		)
