from functools import lru_cache

from app.config import get_settings
from .base import BaseAdapter
from .anthropic import AnthropicAdapter
from .openai import OpenAIAdapter
from .google import GoogleAdapter


class AdapterRegistry:
    def __init__(self):
        settings = get_settings()
        self._adapters: dict[str, BaseAdapter] = {
            "anthropic": AnthropicAdapter(settings.anthropic_api_key),
            "openai": OpenAIAdapter(settings.openai_api_key),
            "google": GoogleAdapter(settings.google_api_key),
        }

    def get_adapter(self, provider: str) -> BaseAdapter:
        adapter = self._adapters.get(provider)
        if not adapter:
            raise ValueError(f"Unknown provider: {provider}")
        return adapter

    def list_providers(self) -> list[dict]:
        return [
            {"name": name, "available": adapter.is_available()}
            for name, adapter in self._adapters.items()
        ]

    def list_all_models(self) -> list[dict]:
        models = []
        for provider, adapter in self._adapters.items():
            if adapter.is_available():
                for model in adapter.list_models():
                    models.append({
                        "provider": provider,
                        "model_id": model["id"],
                        "display_name": model["display_name"],
                    })
        return models


@lru_cache()
def get_registry() -> AdapterRegistry:
    return AdapterRegistry()
