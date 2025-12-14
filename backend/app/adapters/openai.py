import json
import time
from typing import Optional

import openai

from .base import BaseAdapter, AnswerResult, ReviewResult


class OpenAIAdapter(BaseAdapter):
    provider_name = "openai"

    MODELS = [
        {"id": "gpt-5.2", "display_name": "GPT-5.2"},
        {"id": "gpt-5.2-pro", "display_name": "GPT-5.2 Pro"},
        {"id": "gpt-5.1", "display_name": "GPT-5.1"},
        {"id": "gpt-5-pro", "display_name": "GPT-5 Pro"},
        {"id": "gpt-5-mini", "display_name": "GPT-5 Mini"},
        {"id": "gpt-5-nano", "display_name": "GPT-5 Nano"},
        {"id": "gpt-4.1", "display_name": "GPT-4.1"},
        {"id": "gpt-4.1-mini", "display_name": "GPT-4.1 Mini"},
        {"id": "gpt-4.1-nano", "display_name": "GPT-4.1 Nano"},
        {"id": "gpt-4o", "display_name": "GPT-4o"},
        {"id": "gpt-4o-mini", "display_name": "GPT-4o Mini"},
        {"id": "o3", "display_name": "o3"},
        {"id": "o3-mini", "display_name": "o3 Mini"},
        {"id": "o1", "display_name": "o1"},
        {"id": "o1-mini", "display_name": "o1 Mini"},
    ]

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = openai.AsyncOpenAI(api_key=api_key) if api_key else None

    def list_models(self) -> list[dict]:
        return self.MODELS

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate_answer(
        self,
        model: str,
        question: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> AnswerResult:
        if not self.client:
            return AnswerResult(
                text="",
                latency_ms=0,
                error="OpenAI API key not configured",
            )

        start_time = time.perf_counter()
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": question})

            # o-series reasoning models don't support temperature or system prompts
            is_reasoning = model.startswith("o1") or model.startswith("o3")
            # Newer models (gpt-4.1+, gpt-5+) use max_completion_tokens instead of max_tokens
            uses_new_api = model.startswith("gpt-4.1") or model.startswith("gpt-5")

            kwargs = {
                "model": model,
                "messages": messages if not is_reasoning else [{"role": "user", "content": question}],
            }
            if is_reasoning:
                kwargs["max_completion_tokens"] = max_tokens
            elif uses_new_api:
                kwargs["temperature"] = temperature
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["temperature"] = temperature
                kwargs["max_tokens"] = max_tokens

            response = await self.client.chat.completions.create(**kwargs)
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            return AnswerResult(
                text=response.choices[0].message.content,
                latency_ms=latency_ms,
                tokens_in=response.usage.prompt_tokens if response.usage else None,
                tokens_out=response.usage.completion_tokens if response.usage else None,
            )
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return AnswerResult(
                text="",
                latency_ms=latency_ms,
                error=str(e),
            )

    async def generate_review(
        self,
        model: str,
        review_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> ReviewResult:
        if not self.client:
            return ReviewResult(
                raw_response="",
                parsed_reviews=[],
                rank_order=[],
                confidence=0,
                latency_ms=0,
                error="OpenAI API key not configured",
            )

        start_time = time.perf_counter()
        try:
            is_reasoning = model.startswith("o1") or model.startswith("o3")
            uses_new_api = model.startswith("gpt-4.1") or model.startswith("gpt-5")

            kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": review_prompt}],
            }
            if is_reasoning:
                kwargs["max_completion_tokens"] = max_tokens
            elif uses_new_api:
                kwargs["temperature"] = temperature
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["temperature"] = temperature
                kwargs["max_tokens"] = max_tokens

            response = await self.client.chat.completions.create(**kwargs)
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            raw_text = response.choices[0].message.content

            parsed = self._parse_review_response(raw_text)

            return ReviewResult(
                raw_response=raw_text,
                parsed_reviews=parsed.get("reviews", []),
                rank_order=parsed.get("rank_order", []),
                confidence=parsed.get("confidence", 0.5),
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return ReviewResult(
                raw_response="",
                parsed_reviews=[],
                rank_order=[],
                confidence=0,
                latency_ms=latency_ms,
                error=str(e),
            )

    def _parse_review_response(self, raw_text: str) -> dict:
        try:
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = raw_text[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        return {"reviews": [], "rank_order": [], "confidence": 0.5}
