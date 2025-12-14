import json
import time
from typing import Optional

import google.generativeai as genai

from .base import BaseAdapter, AnswerResult, ReviewResult


class GoogleAdapter(BaseAdapter):
    provider_name = "google"

    MODELS = [
        {"id": "gemini-2.0-flash-exp", "display_name": "Gemini 2.0 Flash"},
        {"id": "gemini-1.5-pro", "display_name": "Gemini 1.5 Pro"},
        {"id": "gemini-1.5-flash", "display_name": "Gemini 1.5 Flash"},
    ]

    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)

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
        if not self.api_key:
            return AnswerResult(
                text="",
                latency_ms=0,
                error="Google API key not configured",
            )

        start_time = time.perf_counter()
        try:
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            model_instance = genai.GenerativeModel(
                model_name=model,
                generation_config=generation_config,
                system_instruction=system_prompt if system_prompt else None,
            )

            response = await model_instance.generate_content_async(question)
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            tokens_in = None
            tokens_out = None
            if hasattr(response, "usage_metadata"):
                tokens_in = getattr(response.usage_metadata, "prompt_token_count", None)
                tokens_out = getattr(response.usage_metadata, "candidates_token_count", None)

            return AnswerResult(
                text=response.text,
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
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
        if not self.api_key:
            return ReviewResult(
                raw_response="",
                parsed_reviews=[],
                rank_order=[],
                confidence=0,
                latency_ms=0,
                error="Google API key not configured",
            )

        start_time = time.perf_counter()
        try:
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            model_instance = genai.GenerativeModel(
                model_name=model,
                generation_config=generation_config,
            )

            response = await model_instance.generate_content_async(review_prompt)
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            raw_text = response.text

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
