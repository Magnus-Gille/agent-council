from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RunStatus(str, Enum):
    PENDING = "pending"
    GENERATING_ANSWERS = "generating_answers"
    ANSWERS_COMPLETE = "answers_complete"
    EVALUATING = "evaluating"
    COMPLETE = "complete"
    FAILED = "failed"


class ModelParams(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: Optional[str] = None


class SelectedModelCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: str
    model_name: str
    params: ModelParams = Field(default_factory=ModelParams)


class SelectedModel(SelectedModelCreate):
    id: int
    run_id: int

    class Config:
        from_attributes = True


class RunCreate(BaseModel):
    question: str
    selected_models: list[SelectedModelCreate]
    blind_review: bool = True


class Run(BaseModel):
    id: int
    created_at: datetime
    question: str
    status: RunStatus
    blind_review: bool

    class Config:
        from_attributes = True


class RunResponse(Run):
    selected_models: list[SelectedModel] = []
    answers: list["AnswerResponse"] = []
    reviews: list["ReviewResponse"] = []
    aggregation: Optional["AggregationResult"] = None


class AnswerCreate(BaseModel):
    run_id: int
    producer_model: str
    provider: str
    text: str
    latency_ms: int
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    error: Optional[str] = None


class Answer(AnswerCreate):
    id: int
    label: Optional[str] = None

    class Config:
        from_attributes = True


class AnswerResponse(Answer):
    pass


class ReviewScores(BaseModel):
    correctness: float = Field(ge=0, le=10)
    completeness: float = Field(ge=0, le=10)
    clarity: float = Field(ge=0, le=10)
    helpfulness: float = Field(ge=0, le=10)
    safety: float = Field(ge=0, le=10)
    overall: float = Field(ge=0, le=10)


class AnswerReview(BaseModel):
    label: str
    scores: ReviewScores
    critique: str


class ReviewCreate(BaseModel):
    run_id: int
    reviewer_model: str
    reviewer_provider: str
    reviews: list[AnswerReview]
    rank_order: list[str]
    confidence: float = Field(ge=0, le=1)
    raw_response: Optional[str] = None


class Review(ReviewCreate):
    id: int

    class Config:
        from_attributes = True


class ReviewResponse(Review):
    pass


class VoteBreakdown(BaseModel):
    borda_totals: dict[str, int]
    first_place_votes: dict[str, int]
    score_averages: dict[str, float]


class AggregationResultCreate(BaseModel):
    run_id: int
    final_ranking: list[str]
    vote_breakdown: VoteBreakdown
    method_version: str = "borda_v1"


class AggregationResult(AggregationResultCreate):
    id: int

    class Config:
        from_attributes = True


class ProviderInfo(BaseModel):
    name: str
    available: bool


class ModelInfo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: str
    model_id: str
    display_name: str


class EvaluateRequest(BaseModel):
    reviewer_models: Optional[list[SelectedModelCreate]] = None


RunResponse.model_rebuild()
