"""
LLM Configuration utility for workflow-use.
Handles loading environment variables and creating LLM instances based on provider configuration.
"""

import os
from typing import Optional, Tuple
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel


def load_env_config() -> None:
    """Load environment variables from .env file."""
    # Load from the workflows directory .env file
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(env_path)


def get_llm_provider() -> str:
    """Get the configured LLM provider."""
    return os.getenv('LLM_PROVIDER', 'openai').lower()


def create_openai_llm(model_name: Optional[str] = None, **kwargs) -> BaseChatModel:
    """Create OpenAI LLM instance with configuration from environment."""
    from langchain_openai import ChatOpenAI
    
    model = model_name or os.getenv('OPENAI_MODEL', 'gpt-4o')
    temperature = float(os.getenv('OPENAI_TEMPERATURE', '0.1'))
    max_tokens = int(os.getenv('OPENAI_MAX_TOKENS', '4096'))
    api_key = os.getenv('OPENAI_API_KEY')
    base_url = os.getenv('OPENAI_BASE_URL')
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    llm_kwargs = {
        'model': model,
        'temperature': temperature,
        'max_tokens': max_tokens,
        'api_key': api_key,
        **kwargs
    }
    
    if base_url:
        llm_kwargs['base_url'] = base_url
    
    return ChatOpenAI(**llm_kwargs)


def create_anthropic_llm(model_name: Optional[str] = None, **kwargs) -> BaseChatModel:
    """Create Anthropic LLM instance with configuration from environment."""
    from langchain_anthropic import ChatAnthropic
    
    model = model_name or os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')
    temperature = float(os.getenv('ANTHROPIC_TEMPERATURE', '0.1'))
    max_tokens = int(os.getenv('ANTHROPIC_MAX_TOKENS', '4096'))
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    return ChatAnthropic(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        **kwargs
    )


def create_google_llm(model_name: Optional[str] = None, **kwargs) -> BaseChatModel:
    """Create Google LLM instance with configuration from environment."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    model = model_name or os.getenv('GOOGLE_MODEL', 'gemini-1.5-pro')
    temperature = float(os.getenv('GOOGLE_TEMPERATURE', '0.1'))
    max_tokens = int(os.getenv('GOOGLE_MAX_TOKENS', '4096'))
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        max_output_tokens=max_tokens,
        google_api_key=api_key,
        **kwargs
    )


def create_llm(model_name: Optional[str] = None, provider: Optional[str] = None, **kwargs) -> BaseChatModel:
    """
    Create LLM instance based on configured provider.
    
    Args:
        model_name: Override default model name
        provider: Override default provider
        **kwargs: Additional arguments passed to the LLM constructor
        
    Returns:
        BaseChatModel instance
        
    Raises:
        ValueError: If provider is not supported or API key is missing
    """
    provider = provider or get_llm_provider()
    
    if provider == 'openai':
        return create_openai_llm(model_name, **kwargs)
    elif provider == 'anthropic':
        return create_anthropic_llm(model_name, **kwargs)
    elif provider == 'google':
        return create_google_llm(model_name, **kwargs)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def create_llm_pair() -> Tuple[BaseChatModel, BaseChatModel]:
    """
    Create a pair of LLM instances: main LLM and page extraction LLM.
    
    Returns:
        Tuple of (main_llm, page_extraction_llm)
    """
    provider = get_llm_provider()
    
    if provider == 'openai':
        main_model = os.getenv('OPENAI_MODEL', 'gpt-4o')
        page_model = os.getenv('OPENAI_PAGE_EXTRACTION_MODEL', 'gpt-4o-mini')
        main_llm = create_openai_llm(main_model)
        page_llm = create_openai_llm(page_model)
    elif provider == 'anthropic':
        main_model = os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')
        page_model = os.getenv('ANTHROPIC_PAGE_EXTRACTION_MODEL', 'claude-3-haiku-20240307')
        main_llm = create_anthropic_llm(main_model)
        page_llm = create_anthropic_llm(page_model)
    elif provider == 'google':
        main_model = os.getenv('GOOGLE_MODEL', 'gemini-1.5-pro')
        page_model = os.getenv('GOOGLE_PAGE_EXTRACTION_MODEL', 'gemini-1.5-flash')
        main_llm = create_google_llm(main_model)
        page_llm = create_google_llm(page_model)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    
    return main_llm, page_llm


# Initialize environment configuration when module is imported
load_env_config()