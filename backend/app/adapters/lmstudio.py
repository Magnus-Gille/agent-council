import json
import time
from typing import Optional

import httpx
import openai

from .base import BaseAdapter, AnswerResult, ReviewResult


class LMStudioAdapter(BaseAdapter):
    provider_name = "lmstudio"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/") if base_url else ""
        client_base = f"{self.base_url}/v1" if self.base_url else ""
        self.client = (
            openai.AsyncOpenAI(api_key="lm-studio", base_url=client_base)
            if self.base_url
            else None
        )

    def list_models(self) -> list[dict]:
        if not self.base_url:
            return []
        try:
            resp = httpx.get(f"{self.base_url}/v1/models", timeout=10.0)
            resp.raise_for_status()
            payload = resp.json()
            models = []
            for model in payload.get("data", []):
                models.append({"id": model.get("id", ""), "display_name": model.get("id", "")})
            return models
        except Exception:
            return []

    def is_available(self) -> bool:
        return bool(self.base_url)

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
                error="LM Studio base URL not configured",
            )

        start_time = time.perf_counter()
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": question})

            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
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
                error="LM Studio base URL not configured",
            )

        start_time = time.perf_counter()
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": review_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
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
