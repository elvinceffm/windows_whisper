"""
Multi-provider API client supporting Groq (default) and OpenAI.

Uses the OpenAI SDK with different base_url for each provider.
"""

from dataclasses import dataclass
from typing import Optional
import os

from openai import OpenAI


@dataclass
class ProviderConfig:
    """Configuration for an AI provider."""
    
    name: str
    base_url: str
    api_key_env: str
    transcription_model: str
    llm_model: str
    
    def get_api_key(self) -> Optional[str]:
        """Get API key from environment or None if not set."""
        return os.environ.get(self.api_key_env)


# Provider configurations
PROVIDERS = {
    "groq": ProviderConfig(
        name="Groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        transcription_model="whisper-large-v3-turbo",
        llm_model="llama-3.3-70b-versatile",
    ),
    "openai": ProviderConfig(
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        transcription_model="whisper-1",
        llm_model="gpt-4o",
    ),
}

DEFAULT_PROVIDER = "groq"


class APIClient:
    """Wrapper around OpenAI client with provider switching."""
    
    def __init__(self, provider: str = DEFAULT_PROVIDER, api_key: Optional[str] = None):
        """
        Initialize the API client.
        
        Args:
            provider: Provider name ("groq" or "openai")
            api_key: Optional API key (overrides environment variable)
        """
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Choose from: {list(PROVIDERS.keys())}")
        
        self.provider_name = provider
        self.config = PROVIDERS[provider]
        
        # Use provided key or fall back to environment
        key = api_key or self.config.get_api_key()
        if not key:
            raise ValueError(
                f"No API key found for {provider}. "
                f"Set {self.config.api_key_env} environment variable or provide api_key parameter."
            )
        
        self._client = OpenAI(
            base_url=self.config.base_url,
            api_key=key,
        )
    
    @property
    def client(self) -> OpenAI:
        """Get the underlying OpenAI client."""
        return self._client
    
    @property
    def transcription_model(self) -> str:
        """Get the transcription model for current provider."""
        return self.config.transcription_model
    
    @property
    def llm_model(self) -> str:
        """Get the LLM model for current provider."""
        return self.config.llm_model


# Global client instance (lazily initialized)
_client: Optional[APIClient] = None


def get_client(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    force_new: bool = False
) -> APIClient:
    """
    Get or create the API client.
    
    Args:
        provider: Provider name (uses default if not specified)
        api_key: Optional API key
        force_new: Force creation of new client even if one exists
        
    Returns:
        APIClient instance
    """
    global _client
    
    if _client is None or force_new:
        _client = APIClient(
            provider=provider or DEFAULT_PROVIDER,
            api_key=api_key,
        )
    
    return _client


def set_client(provider: str, api_key: str) -> APIClient:
    """
    Set up a new client with specific provider and key.
    
    Args:
        provider: Provider name ("groq" or "openai")
        api_key: API key for the provider
        
    Returns:
        New APIClient instance
    """
    return get_client(provider=provider, api_key=api_key, force_new=True)
