from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import (
    RunCreate, RunResponse, RunORM, AnswerORM, ReviewORM, AggregationResultORM,
    ProviderInfo, ModelInfo, EvaluateRequest,
    Run, SelectedModel, AnswerResponse, ReviewResponse, AggregationResult, VoteBreakdown,
)
from app.models.database import get_db
from app.adapters import get_registry
from app.services import RunOrchestrator

router = APIRouter()


def run_to_response(run: RunORM) -> RunResponse:
    """Convert ORM model to response schema."""
    selected_models = [
        SelectedModel(
            id=sm.id,
            run_id=sm.run_id,
            provider=sm.provider,
            model_name=sm.model_name,
            params=sm.params,
        )
        for sm in run.selected_models
    ]

    answers = [
        AnswerResponse(
            id=a.id,
            run_id=a.run_id,
            producer_model=a.producer_model,
            provider=a.provider,
            label=a.label,
            text=a.text,
            latency_ms=a.latency_ms,
            tokens_in=a.tokens_in,
            tokens_out=a.tokens_out,
            error=a.error,
        )
        for a in run.answers
    ]

    reviews = [
        ReviewResponse(
            id=r.id,
            run_id=r.run_id,
            reviewer_model=r.reviewer_model,
            reviewer_provider=r.reviewer_provider,
            reviews=r.reviews,
            rank_order=r.rank_order,
            confidence=r.confidence,
            raw_response=r.raw_response,
        )
        for r in run.reviews
    ]

    aggregation = None
    if run.aggregation:
        aggregation = AggregationResult(
            id=run.aggregation.id,
            run_id=run.aggregation.run_id,
            final_ranking=run.aggregation.final_ranking,
            vote_breakdown=VoteBreakdown(**run.aggregation.vote_breakdown),
            method_version=run.aggregation.method_version,
        )

    return RunResponse(
        id=run.id,
        created_at=run.created_at,
        question=run.question,
        status=run.status,
        blind_review=run.blind_review,
        selected_models=selected_models,
        answers=answers,
        reviews=reviews,
        aggregation=aggregation,
    )


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers():
    registry = get_registry()
    return registry.list_providers()


@router.get("/models", response_model=list[ModelInfo])
async def list_models():
    registry = get_registry()
    return registry.list_all_models()


@router.post("/runs", response_model=RunResponse)
async def create_run(
    run_create: RunCreate,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = RunOrchestrator(db)

    selected_models = [
        {
            "provider": m.provider,
            "model_name": m.model_name,
            "params": m.params.model_dump() if m.params else {},
        }
        for m in run_create.selected_models
    ]

    run = await orchestrator.create_run(
        question=run_create.question,
        selected_models=selected_models,
        blind_review=run_create.blind_review,
    )

    return run_to_response(run)


@router.post("/runs/{run_id}/answers", response_model=RunResponse)
async def generate_answers(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = RunOrchestrator(db)
    try:
        run = await orchestrator.generate_answers(run_id)
        return run_to_response(run)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/runs/{run_id}/evaluate", response_model=RunResponse)
async def evaluate_run(
    run_id: int,
    request: EvaluateRequest = None,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = RunOrchestrator(db)

    reviewer_models = None
    if request and request.reviewer_models:
        reviewer_models = [
            {
                "provider": m.provider,
                "model_name": m.model_name,
                "params": m.params.model_dump() if m.params else {},
            }
            for m in request.reviewer_models
        ]

    try:
        run = await orchestrator.run_evaluation(run_id, reviewer_models)
        return run_to_response(run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = RunOrchestrator(db)
    run = await orchestrator.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_to_response(run)


@router.get("/runs", response_model=list[Run])
async def list_runs(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RunORM)
        .order_by(RunORM.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    runs = result.scalars().all()
    return [
        Run(
            id=r.id,
            created_at=r.created_at,
            question=r.question,
            status=r.status,
            blind_review=r.blind_review,
        )
        for r in runs
    ]


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RunORM).where(RunORM.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    await db.delete(run)
    await db.commit()
    return {"status": "deleted", "run_id": run_id}
