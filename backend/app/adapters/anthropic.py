import json
import time
from typing import Optional

import anthropic

from .base import BaseAdapter, AnswerResult, ReviewResult


class AnthropicAdapter(BaseAdapter):
    provider_name = "anthropic"

    MODELS = [
        {"id": "claude-sonnet-4-5-20250929", "display_name": "Claude Sonnet 4.5"},
        {"id": "claude-opus-4-20250514", "display_name": "Claude Opus 4"},
        {"id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4"},
        {"id": "claude-3-5-sonnet-20241022", "display_name": "Claude 3.5 Sonnet"},
        {"id": "claude-3-5-haiku-20241022", "display_name": "Claude 3.5 Haiku"},
    ]

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else None

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
                error="Anthropic API key not configured",
            )

        start_time = time.perf_counter()
        try:
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": question}],
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = await self.client.messages.create(**kwargs)
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            return AnswerResult(
                text=response.content[0].text,
                latency_ms=latency_ms,
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
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
                error="Anthropic API key not configured",
            )

        start_time = time.perf_counter()
        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": review_prompt}],
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            raw_text = response.content[0].text

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
