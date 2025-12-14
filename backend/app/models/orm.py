from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class RunORM(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    blind_review: Mapped[bool] = mapped_column(Boolean, default=True)

    selected_models: Mapped[list["SelectedModelORM"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    answers: Mapped[list["AnswerORM"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["ReviewORM"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    aggregation: Mapped["AggregationResultORM"] = relationship(
        back_populates="run", cascade="all, delete-orphan", uselist=False
    )


class SelectedModelORM(Base):
    __tablename__ = "selected_models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    provider: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(100))
    params: Mapped[dict] = mapped_column(JSON, default=dict)

    run: Mapped["RunORM"] = relationship(back_populates="selected_models")


class AnswerORM(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    producer_model: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50))
    label: Mapped[str | None] = mapped_column(String(10), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["RunORM"] = relationship(back_populates="answers")


class ReviewORM(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    reviewer_model: Mapped[str] = mapped_column(String(100))
    reviewer_provider: Mapped[str] = mapped_column(String(50))
    reviews: Mapped[dict] = mapped_column(JSON)
    rank_order: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["RunORM"] = relationship(back_populates="reviews")


class AggregationResultORM(Base):
    __tablename__ = "aggregation_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), unique=True)
    final_ranking: Mapped[list] = mapped_column(JSON)
    vote_breakdown: Mapped[dict] = mapped_column(JSON)
    method_version: Mapped[str] = mapped_column(String(50), default="borda_v1")

    run: Mapped["RunORM"] = relationship(back_populates="aggregation")
