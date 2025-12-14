from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AnswerResult:
    text: str
    latency_ms: int
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    error: Optional[str] = None


@dataclass
class ReviewResult:
    raw_response: str
    parsed_reviews: list[dict]
    rank_order: list[str]
    confidence: float
    latency_ms: int
    error: Optional[str] = None


class BaseAdapter(ABC):
    provider_name: str

    @abstractmethod
    def __init__(self, api_key: str):
        pass

    @abstractmethod
    def list_models(self) -> list[dict]:
        """Return list of available models with id and display_name."""
        pass

    @abstractmethod
    async def generate_answer(
        self,
        model: str,
        question: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> AnswerResult:
        """Generate an answer for the given question."""
        pass

    @abstractmethod
    async def generate_review(
        self,
        model: str,
        review_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> ReviewResult:
        """Generate a review based on the evaluation packet."""
        pass

    def is_available(self) -> bool:
        """Check if the adapter has valid credentials."""
        return True
