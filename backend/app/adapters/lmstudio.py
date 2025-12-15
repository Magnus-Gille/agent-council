import json
import logging
import time
from typing import Optional

import httpx
import openai

from .base import BaseAdapter, AnswerResult, ReviewResult

logger = logging.getLogger(__name__)


def _format_duration(ms: float) -> str:
    """Format milliseconds into human-readable duration."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:
        return f"{ms/1000:.2f}s"
    else:
        return f"{ms/60000:.2f}min"


class LMStudioAdapter(BaseAdapter):
    provider_name = "lmstudio"

    # Cache model list for 60 seconds to avoid hammering LM Studio
    _models_cache: list[dict] | None = None
    _models_cache_time: float = 0
    _CACHE_TTL_SECONDS = 60.0

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/") if base_url else ""
        client_base = f"{self.base_url}/v1" if self.base_url else ""
        self.client = (
            openai.AsyncOpenAI(api_key="lm-studio", base_url=client_base)
            if self.base_url
            else None
        )
        logger.info(f"[TIMING] LMStudioAdapter initialized with base_url={self.base_url}")

    def list_models(self) -> list[dict]:
        if not self.base_url:
            return []

        # Return cached results if fresh
        now = time.time()
        if (
            LMStudioAdapter._models_cache is not None
            and (now - LMStudioAdapter._models_cache_time) < LMStudioAdapter._CACHE_TTL_SECONDS
        ):
            logger.debug("[TIMING] [LMStudio] Returning cached model list")
            return LMStudioAdapter._models_cache

        try:
            logger.info("[TIMING] [LMStudio] Fetching model list from server")
            resp = httpx.get(f"{self.base_url}/v1/models", timeout=10.0)
            resp.raise_for_status()
            payload = resp.json()
            models = []
            for model in payload.get("data", []):
                models.append({"id": model.get("id", ""), "display_name": model.get("id", "")})

            # Update cache
            LMStudioAdapter._models_cache = models
            LMStudioAdapter._models_cache_time = now
            return models
        except Exception as e:
            logger.warning(f"[TIMING] [LMStudio] Failed to fetch models: {e}")
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

        logger.info(f"[TIMING] [LMStudio] generate_answer START model={model}, max_tokens={max_tokens}, question_len={len(question)}")
        start_time = time.perf_counter()
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": question})

            api_start = time.perf_counter()
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            api_duration_ms = (time.perf_counter() - api_start) * 1000
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            tokens_in = response.usage.prompt_tokens if response.usage else None
            tokens_out = response.usage.completion_tokens if response.usage else None
            response_text = response.choices[0].message.content

            logger.info(f"[TIMING] [LMStudio] generate_answer COMPLETE model={model} api_call={_format_duration(api_duration_ms)}, total={_format_duration(latency_ms)}, tokens_in={tokens_in}, tokens_out={tokens_out}, response_len={len(response_text) if response_text else 0}")

            return AnswerResult(
                text=response_text,
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"[TIMING] [LMStudio] generate_answer FAILED model={model} after {_format_duration(latency_ms)}: {e}")
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

        logger.info(f"[TIMING] [LMStudio] generate_review START model={model}, prompt_len={len(review_prompt)}")
        start_time = time.perf_counter()
        try:
            adjusted_max_tokens = min(max_tokens, 2048)

            api_start = time.perf_counter()
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": review_prompt}],
                temperature=temperature,
                max_tokens=adjusted_max_tokens,
            )
            api_duration_ms = (time.perf_counter() - api_start) * 1000
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            raw_text = response.choices[0].message.content

            parse_start = time.perf_counter()
            parsed = self._parse_review_response(raw_text)
            parse_duration_ms = (time.perf_counter() - parse_start) * 1000

            tokens_in = response.usage.prompt_tokens if response.usage else None
            tokens_out = response.usage.completion_tokens if response.usage else None

            logger.info(f"[TIMING] [LMStudio] generate_review COMPLETE model={model} api_call={_format_duration(api_duration_ms)}, parse={_format_duration(parse_duration_ms)}, total={_format_duration(latency_ms)}, tokens_in={tokens_in}, tokens_out={tokens_out}, response_len={len(raw_text) if raw_text else 0}, parsed_reviews={len(parsed.get('reviews', []))}")

            return ReviewResult(
                raw_response=raw_text,
                parsed_reviews=parsed.get("reviews", []),
                rank_order=parsed.get("rank_order", []),
                confidence=parsed.get("confidence", 0.5),
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"[TIMING] [LMStudio] generate_review FAILED model={model} after {_format_duration(latency_ms)}: {e}")
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
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()

            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = cleaned[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        return {"reviews": [], "rank_order": [], "confidence": 0.5}
