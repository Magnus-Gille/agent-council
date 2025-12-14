import asyncio
import logging
from collections import Counter, defaultdict
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.adapters import get_registry, AnswerResult, ReviewResult
from app.models import (
    RunORM, SelectedModelORM, AnswerORM, ReviewORM, AggregationResultORM,
    RunStatus,
)
from app.config import get_settings
from .evaluation import EvaluationService, build_review_prompt
from .voting import VotingService


class RunOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.registry = get_registry()
        self.settings = get_settings()
        self.evaluation_service = EvaluationService()
        self.voting_service = VotingService()

    def _compute_instance_labels(self, models: list[SelectedModelORM]) -> dict[int, str]:
        """Ensure every selected model has a stable, unique instance label."""
        duplicates = Counter((m.provider, m.model_name) for m in models)
        per_model_counts: dict[tuple[str, str], int] = defaultdict(int)
        label_usage: dict[str, int] = defaultdict(int)
        label_map: dict[int, str] = {}

        for model in models:
            key = (model.provider, model.model_name)
            per_model_counts[key] += 1
            params = model.params or {}

            label = params.get("instance_label")
            if not label:
                label = model.model_name
                if duplicates[key] > 1:
                    label = f"{model.model_name} #{per_model_counts[key]}"

            label_usage[label] += 1
            if label_usage[label] > 1:
                label = f"{label} #{label_usage[label]}"

            params["instance_label"] = label
            model.params = params
            label_map[model.id] = label

        return label_map

    async def get_run(self, run_id: int) -> Optional[RunORM]:
        result = await self.db.execute(
            select(RunORM)
            .options(
                selectinload(RunORM.selected_models),
                selectinload(RunORM.answers),
                selectinload(RunORM.reviews),
                selectinload(RunORM.aggregation),
            )
            .where(RunORM.id == run_id)
        )
        return result.scalar_one_or_none()

    async def create_run(
        self,
        question: str,
        selected_models: list[dict],
        blind_review: bool = True,
    ) -> RunORM:
        run = RunORM(
            question=question,
            status=RunStatus.PENDING.value,
            blind_review=blind_review,
        )
        self.db.add(run)
        await self.db.flush()

        duplicates = Counter((m["provider"], m["model_name"]) for m in selected_models)
        per_model_counts: dict[tuple[str, str], int] = defaultdict(int)
        label_usage: dict[str, int] = defaultdict(int)

        for model_config in selected_models:
            key = (model_config["provider"], model_config["model_name"])
            per_model_counts[key] += 1

            params = model_config.get("params", {}) or {}
            label = params.get("instance_label")

            if not label:
                label = model_config["model_name"]
                if duplicates[key] > 1:
                    label = f"{model_config['model_name']} #{per_model_counts[key]}"

            label_usage[label] += 1
            if label_usage[label] > 1:
                label = f"{label} #{label_usage[label]}"

            params["instance_label"] = label

            selected = SelectedModelORM(
                run_id=run.id,
                provider=model_config["provider"],
                model_name=model_config["model_name"],
                params=params,
            )
            self.db.add(selected)

        await self.db.commit()
        return await self.get_run(run.id)

    async def generate_answers(self, run_id: int) -> RunORM:
        run = await self.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        run.status = RunStatus.GENERATING_ANSWERS.value
        await self.db.commit()

        instance_labels = self._compute_instance_labels(run.selected_models)
        semaphore = asyncio.Semaphore(self.settings.max_concurrency)

        async def generate_one(model_config: SelectedModelORM) -> AnswerResult:
            async with semaphore:
                adapter = self.registry.get_adapter(model_config.provider)
                params = model_config.params or {}
                return await adapter.generate_answer(
                    model=model_config.model_name,
                    question=run.question,
                    temperature=params.get("temperature", 0.7),
                    max_tokens=params.get("max_tokens", 2048),
                    system_prompt=params.get("system_prompt"),
                )

        tasks = [generate_one(m) for m in run.selected_models]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i, (model_config, result) in enumerate(zip(run.selected_models, results)):
            if isinstance(result, Exception):
                result = AnswerResult(text="", latency_ms=0, error=str(result))

            label = labels[i] if i < len(labels) else f"Z{i - 25}"
            producer_label = instance_labels.get(model_config.id, model_config.model_name)

            answer = AnswerORM(
                run_id=run.id,
                producer_model=producer_label,
                provider=model_config.provider,
                label=label,
                text=result.text,
                latency_ms=result.latency_ms,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                error=result.error,
            )
            self.db.add(answer)

        run.status = RunStatus.ANSWERS_COMPLETE.value
        await self.db.commit()
        return await self.get_run(run_id)

    async def run_evaluation(
        self,
        run_id: int,
        reviewer_models: Optional[list[dict]] = None,
    ) -> RunORM:
        run = await self.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        run.status = RunStatus.EVALUATING.value
        await self.db.commit()
        instance_labels = self._compute_instance_labels(run.selected_models)

        # Get successful answers
        answers = [
            {
                "label": a.label,
                "text": a.text,
                "provider": a.provider,
                "producer_model": a.producer_model,
            }
            for a in run.answers
            if not a.error
        ]

        if len(answers) < 2:
            run.status = RunStatus.FAILED.value
            await self.db.commit()
            raise ValueError("Need at least 2 successful answers to evaluate")

        label_to_model = self.evaluation_service.get_label_mapping(answers)
        model_to_label = self.evaluation_service.get_reverse_mapping(answers)

        # Use specified reviewers or default to the answering models
        if reviewer_models:
            reviewers = reviewer_models
            duplicates = Counter((r["provider"], r["model_name"]) for r in reviewers)
            per_model_counts: dict[tuple[str, str], int] = defaultdict(int)
            label_usage: dict[str, int] = defaultdict(int)

            for reviewer in reviewers:
                key = (reviewer["provider"], reviewer["model_name"])
                per_model_counts[key] += 1

                params = reviewer.get("params", {}) or {}
                label = reviewer.get("instance_label") or params.get("instance_label")

                if not label:
                    label = reviewer["model_name"]
                    if duplicates[key] > 1:
                        label = f"{reviewer['model_name']} #{per_model_counts[key]}"

                label_usage[label] += 1
                if label_usage[label] > 1:
                    label = f"{label} #{label_usage[label]}"

                params["instance_label"] = label
                reviewer["params"] = params
                reviewer["instance_label"] = label
        else:
            reviewers = [
                {
                    "provider": m.provider,
                    "model_name": m.model_name,
                    "params": m.params,
                    "instance_label": instance_labels.get(m.id, m.model_name),
                }
                for m in run.selected_models
            ]

        semaphore = asyncio.Semaphore(self.settings.max_concurrency)

        async def review_one(reviewer: dict) -> tuple[dict, ReviewResult]:
            async with semaphore:
                adapter = self.registry.get_adapter(reviewer["provider"])

                # With blind review, models see all answers (including their own)
                # and don't know which one is theirs
                prompt = build_review_prompt(
                    question=run.question,
                    answers=answers,
                    exclude_label=None,  # Don't exclude any answers - blind review
                )

                result = await adapter.generate_review(
                    model=reviewer["model_name"],
                    review_prompt=prompt,
                    temperature=0.3,
                    max_tokens=4096,
                )
                return reviewer, result

        logger.info(f"Starting evaluation with {len(reviewers)} reviewers")
        tasks = [review_one(r) for r in reviewers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        review_data = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Review exception: {result}")
                continue
            reviewer, review_result = result
            logger.info(f"Review from {reviewer['provider']}:{reviewer['model_name']} - error: {review_result.error}, rank_order: {review_result.rank_order}, parsed_reviews count: {len(review_result.parsed_reviews)}")
            if review_result.error:
                logger.error(f"Review error: {review_result.error}")
                continue

            reviewer_label = (
                reviewer.get("instance_label")
                or reviewer.get("params", {}).get("instance_label")
                or reviewer["model_name"]
            )

            review_orm = ReviewORM(
                run_id=run.id,
                reviewer_model=reviewer_label,
                reviewer_provider=reviewer["provider"],
                reviews=[r for r in review_result.parsed_reviews],
                rank_order=review_result.rank_order,
                confidence=review_result.confidence,
                raw_response=review_result.raw_response,
            )
            self.db.add(review_orm)

            review_data.append({
                "reviewer_model": reviewer_label,
                "reviewer_provider": reviewer["provider"],
                "reviews": review_result.parsed_reviews,
                "rank_order": review_result.rank_order,
            })

        await self.db.flush()

        # Aggregate votes
        if review_data:
            aggregation = self.voting_service.aggregate_votes(
                reviews=review_data,
                label_to_model=label_to_model,
            )

            agg_orm = AggregationResultORM(
                run_id=run.id,
                final_ranking=aggregation.final_ranking,
                vote_breakdown={
                    "borda_totals": aggregation.vote_breakdown.borda_totals,
                    "first_place_votes": aggregation.vote_breakdown.first_place_votes,
                    "score_averages": aggregation.vote_breakdown.score_averages,
                },
                method_version="borda_v1",
            )
            self.db.add(agg_orm)

        run.status = RunStatus.COMPLETE.value
        await self.db.commit()
        return await self.get_run(run_id)

    async def run_full_pipeline(
        self,
        question: str,
        selected_models: list[dict],
        blind_review: bool = True,
    ) -> RunORM:
        """Create a run, generate answers, and evaluate them."""
        run = await self.create_run(question, selected_models, blind_review)
        run = await self.generate_answers(run.id)
        run = await self.run_evaluation(run.id)
        return run
