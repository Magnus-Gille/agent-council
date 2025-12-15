import asyncio
import logging
import time
from collections import Counter, defaultdict
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters import get_registry, AnswerResult, ReviewResult
from app.config import get_settings
from app.models import (
    RunORM, SelectedModelORM, AnswerORM, ReviewORM, AggregationResultORM,
    RunStatus,
)
from .evaluation import EvaluationService, build_review_prompt
from .voting import VotingService

logger = logging.getLogger(__name__)


def _format_duration(ms: float) -> str:
    """Format milliseconds into human-readable duration."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:
        return f"{ms/1000:.2f}s"
    else:
        return f"{ms/60000:.2f}min"


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
        phase_start = time.perf_counter()
        logger.info(f"[TIMING] generate_answers START for run {run_id}")

        run = await self.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        run.status = RunStatus.GENERATING_ANSWERS.value
        await self.db.commit()

        instance_labels = self._compute_instance_labels(run.selected_models)
        semaphore = asyncio.Semaphore(self.settings.max_concurrency)

        model_count = len(run.selected_models)
        logger.info(f"[TIMING] Generating answers from {model_count} models (max_concurrency={self.settings.max_concurrency})")

        async def generate_one(model_config: SelectedModelORM) -> tuple[AnswerResult, float, float]:
            model_label = instance_labels.get(model_config.id, model_config.model_name)
            wait_start = time.perf_counter()
            async with semaphore:
                semaphore_wait_ms = (time.perf_counter() - wait_start) * 1000
                adapter_start = time.perf_counter()
                logger.info(f"[TIMING] [{model_label}] Starting answer generation (waited {semaphore_wait_ms:.0f}ms for semaphore)")

                adapter = self.registry.get_adapter(model_config.provider)
                params = model_config.params or {}
                result = await adapter.generate_answer(
                    model=model_config.model_name,
                    question=run.question,
                    temperature=params.get("temperature", 0.7),
                    max_tokens=params.get("max_tokens", 2048),
                    system_prompt=params.get("system_prompt"),
                )

                adapter_duration_ms = (time.perf_counter() - adapter_start) * 1000
                logger.info(f"[TIMING] [{model_label}] Answer complete in {_format_duration(adapter_duration_ms)} (adapter reported: {_format_duration(result.latency_ms)})")
                return result, semaphore_wait_ms, adapter_duration_ms

        tasks = [generate_one(m) for m in run.selected_models]
        gather_start = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        gather_duration_ms = (time.perf_counter() - gather_start) * 1000
        logger.info(f"[TIMING] All {model_count} answer tasks completed in {_format_duration(gather_duration_ms)}")

        labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        timing_summary = []
        for i, (model_config, result) in enumerate(zip(run.selected_models, results)):
            if isinstance(result, Exception):
                answer_result = AnswerResult(text="", latency_ms=0, error=str(result))
                semaphore_wait_ms = 0
                adapter_duration_ms = 0
            else:
                answer_result, semaphore_wait_ms, adapter_duration_ms = result

            label = labels[i] if i < len(labels) else f"Z{i - 25}"
            producer_label = instance_labels.get(model_config.id, model_config.model_name)

            timing_summary.append({
                "model": producer_label,
                "semaphore_wait_ms": semaphore_wait_ms,
                "adapter_duration_ms": adapter_duration_ms,
                "reported_latency_ms": answer_result.latency_ms,
                "tokens_out": answer_result.tokens_out,
                "error": answer_result.error,
            })

            answer = AnswerORM(
                run_id=run.id,
                producer_model=producer_label,
                provider=model_config.provider,
                label=label,
                text=answer_result.text,
                latency_ms=answer_result.latency_ms,
                tokens_in=answer_result.tokens_in,
                tokens_out=answer_result.tokens_out,
                error=answer_result.error,
            )
            self.db.add(answer)

        # Log timing summary
        phase_duration_ms = (time.perf_counter() - phase_start) * 1000
        logger.info(f"[TIMING] generate_answers COMPLETE for run {run_id} in {_format_duration(phase_duration_ms)}")
        logger.info("[TIMING] Answer generation summary:")
        for t in timing_summary:
            status = "ERROR" if t["error"] else "OK"
            tokens = f", {t['tokens_out']} tokens" if t['tokens_out'] else ""
            logger.info(f"[TIMING]   {t['model']}: wait={t['semaphore_wait_ms']:.0f}ms, generation={_format_duration(t['adapter_duration_ms'])}{tokens} [{status}]")

        run.status = RunStatus.ANSWERS_COMPLETE.value
        await self.db.commit()
        return await self.get_run(run_id)

    async def run_evaluation(
        self,
        run_id: int,
        reviewer_models: Optional[list[dict]] = None,
    ) -> RunORM:
        phase_start = time.perf_counter()
        logger.info(f"[TIMING] run_evaluation START for run {run_id}")

        run = await self.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        run.status = RunStatus.EVALUATING.value
        await self.db.commit()
        instance_labels = self._compute_instance_labels(run.selected_models)
        reviewer_count = len(reviewer_models) if reviewer_models else len(run.selected_models)
        logger.info(f"[TIMING] Evaluation phase with {reviewer_count} reviewers (max_concurrency={self.settings.max_concurrency})")

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
        max_review_attempts = 2

        async def review_one(reviewer: dict) -> tuple[dict, ReviewResult, float, float, int]:
            reviewer_label = reviewer.get("instance_label") or reviewer["model_name"]
            wait_start = time.perf_counter()
            async with semaphore:
                semaphore_wait_ms = (time.perf_counter() - wait_start) * 1000
                adapter_start = time.perf_counter()
                logger.info(f"[TIMING] [{reviewer_label}] Starting review (waited {semaphore_wait_ms:.0f}ms for semaphore)")

                adapter = self.registry.get_adapter(reviewer["provider"])

                # With blind review, models see all answers (including their own)
                # and don't know which one is theirs
                prompt = build_review_prompt(
                    question=run.question,
                    answers=answers,
                    exclude_label=None,  # Don't exclude any answers - blind review
                )

                last_result: ReviewResult | None = None
                attempts_made = 0
                for attempt in range(max_review_attempts):
                    attempts_made = attempt + 1
                    attempt_start = time.perf_counter()
                    result = await adapter.generate_review(
                        model=reviewer["model_name"],
                        review_prompt=prompt,
                        temperature=0.3,
                        max_tokens=4096,
                    )
                    attempt_duration_ms = (time.perf_counter() - attempt_start) * 1000
                    if result.error:
                        logger.info(f"[TIMING] [{reviewer_label}] Review attempt {attempt + 1} failed in {_format_duration(attempt_duration_ms)}: {result.error}")
                    else:
                        logger.info(f"[TIMING] [{reviewer_label}] Review attempt {attempt + 1} succeeded in {_format_duration(attempt_duration_ms)}")
                    last_result = result
                    if not result.error:
                        break

                adapter_duration_ms = (time.perf_counter() - adapter_start) * 1000
                logger.info(f"[TIMING] [{reviewer_label}] Review complete in {_format_duration(adapter_duration_ms)} ({attempts_made} attempt(s))")
                return reviewer, last_result, semaphore_wait_ms, adapter_duration_ms, attempts_made  # type: ignore[arg-type]

        logger.info(f"[TIMING] Starting {len(reviewers)} review tasks")
        tasks = [review_one(r) for r in reviewers]
        gather_start = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        gather_duration_ms = (time.perf_counter() - gather_start) * 1000
        logger.info(f"[TIMING] All {len(reviewers)} review tasks completed in {_format_duration(gather_duration_ms)}")

        review_data = []
        review_failures: list[str] = []
        timing_summary = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Review exception: {result}")
                review_failures.append(str(result))
                continue
            reviewer, review_result, semaphore_wait_ms, adapter_duration_ms, attempts_made = result
            reviewer_label = reviewer.get("instance_label") or reviewer["model_name"]
            timing_summary.append({
                "reviewer": reviewer_label,
                "semaphore_wait_ms": semaphore_wait_ms,
                "adapter_duration_ms": adapter_duration_ms,
                "attempts": attempts_made,
                "error": review_result.error,
            })
            logger.info(f"Review from {reviewer['provider']}:{reviewer['model_name']} - error: {review_result.error}, rank_order: {review_result.rank_order}, parsed_reviews count: {len(review_result.parsed_reviews)}")
            if review_result.error:
                logger.error(f"Review error: {review_result.error}")
                review_failures.append(f"{reviewer.get('instance_label') or reviewer['model_name']}: {review_result.error}")
                continue

            rank_order = review_result.rank_order or []
            if not rank_order and review_result.parsed_reviews:
                # Derive ranking from scores if the model omitted rank_order
                try:
                    ranked = sorted(
                        review_result.parsed_reviews,
                        key=lambda r: (
                            r.get("scores", {}).get("overall", 0),
                            r.get("scores", {}).get("correctness", 0),
                        ),
                        reverse=True,
                    )
                    rank_order = [r.get("label") for r in ranked if r.get("label")]
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning(f"Could not derive rank_order: {exc}")

            if not rank_order:
                fallback_labels = [a["label"] for a in answers if a.get("label")]
                if len(fallback_labels) >= 2:
                    rank_order = fallback_labels
                    logger.warning(
                        f"Using fallback rank order for {reviewer['provider']}:{reviewer.get('instance_label') or reviewer.get('model_name')} -> {rank_order}"
                    )
                else:
                    logger.warning(
                        f"Skipping review from {reviewer['provider']}:{reviewer.get('instance_label') or reviewer.get('model_name')} due to empty rank_order"
                    )
                    review_failures.append(f"{reviewer.get('instance_label') or reviewer['model_name']}: empty rank_order")
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
                rank_order=rank_order,
                confidence=review_result.confidence,
                raw_response=review_result.raw_response,
            )
            self.db.add(review_orm)

            review_data.append({
                "reviewer_model": reviewer_label,
                "reviewer_provider": reviewer["provider"],
                "reviews": review_result.parsed_reviews,
                "rank_order": rank_order,
            })

        await self.db.flush()

        # Aggregate votes
        if not review_data or len(review_data) < len(reviewers):
            run.status = RunStatus.FAILED.value
            await self.db.commit()
            detail = "No valid reviews returned" if not review_data else "Some reviewers failed"
            if review_failures:
                detail += f": {', '.join(review_failures)}"
            raise ValueError(detail)

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

        # Log timing summary
        phase_duration_ms = (time.perf_counter() - phase_start) * 1000
        logger.info(f"[TIMING] run_evaluation COMPLETE for run {run_id} in {_format_duration(phase_duration_ms)}")
        logger.info("[TIMING] Evaluation summary:")
        for t in timing_summary:
            status = "ERROR" if t["error"] else "OK"
            logger.info(f"[TIMING]   {t['reviewer']}: wait={t['semaphore_wait_ms']:.0f}ms, review={_format_duration(t['adapter_duration_ms'])}, attempts={t['attempts']} [{status}]")

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
