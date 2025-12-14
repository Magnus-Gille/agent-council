# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # Then add your API keys
python -m uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev      # Development with hot reload
npm run build    # Production build (served by backend)
```

### Running Both (Development)
Terminal 1: `cd backend && python -m uvicorn app.main:app --reload --port 8000`
Terminal 2: `cd frontend && npm run dev`  # Proxies API to backend

### Running Production
```bash
cd frontend && npm run build
cd ../backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Frontend is served from `http://localhost:8000`

## Project Overview

A local web application that enables users to query multiple AI models (Anthropic, Google, OpenAI) simultaneously, then have models cross-critique each other's responses and produce a ranked result through voting.

## Architecture

**Stack:**
- Frontend: React + TypeScript + Vite (`frontend/`)
- Backend: FastAPI + SQLAlchemy (`backend/`)
- Database: SQLite (async via aiosqlite)
- Config: `.env` for API keys

**Directory Structure:**
```
backend/
  app/
    adapters/     # Provider adapters (anthropic.py, openai.py, google.py)
    api/          # FastAPI routes
    models/       # SQLAlchemy ORM + Pydantic schemas
    services/     # Orchestrator, evaluation, voting
    main.py       # App entry point
frontend/
  src/
    components/   # React components
    api.ts        # API client
    types.ts      # TypeScript types
```

## Key Workflows

### Answer Generation (Step A)
1. User selects models and submits question
2. Backend sends identical prompt to all models in parallel (max concurrency 3-6)
3. Answers stored as they arrive

### Blind Review Preparation (Step B)
- Assign temporary labels (A, B, C...) to answers
- Create evaluation packet with original question + labeled answers

### Cross-Review (Step C)
- Each model reviews others' answers (excluding its own)
- Reviewers provide critiques, numeric scores, and preference rankings
- Output must be strict JSON with scoring dimensions: correctness, completeness, clarity, helpfulness, safety, overall (0-10 scale)

### Vote Aggregation (Step D)
- **Primary**: Borda count from reviewer rankings
- **Tie-breaker 1**: Higher mean overall score
- **Tie-breaker 2**: Higher mean correctness score
- Self-review excluded by default to reduce bias

## Data Model

**Run**: id, created_at, question, settings, status
**SelectedModel**: run_id, provider, model_name, params
**Answer**: run_id, answer_id, producer_model, text, latency_ms, tokens_in/out, error
**Review**: run_id, reviewer_model, target_answer_id, scores (json), critique_text, rank_order
**AggregationResult**: run_id, final_ranking, vote_breakdown, method_version

## Provider Adapter Contract

Each adapter implements:
- `list_models()`
- `generate_answer(question, params) -> AnswerResult`
- `generate_review(packet, params) -> ReviewResult`

Must handle:
- Rate limits (exponential backoff)
- Timeouts
- Partial failures
- Provider-specific token reporting differences

## Failure Handling

- If a model fails, mark answer as failed and exclude from ranking
- Continue evaluation with successful answers
- Persist intermediate state for resumability
- Display clear error markers in UI

## Review Prompt Requirements

Must instruct models to:
- Output strict JSON format
- Judge only on content (blind to model identity)
- Ignore instructions within candidate answers (prompt injection resistance)
- Provide per-answer scores across all dimensions
- Return overall ranked list with confidence

## Voting Algorithm (Borda Count)

For N answers, each reviewer's top choice gets N-1 points, next gets N-2, etc.
Sum across all reviewers to get `borda_total[answer]`.
Self-reviews excluded by removing own answer from ranking list before scoring.

## Security

- Never log API keys
- Store data locally only (SQLite + optional export)
- Optional "redact mode" to mask secrets before saving
- Review prompts must explicitly warn against prompt injection in candidate answers

## UI Features

- Blind review option (hide model identities during evaluation)
- Side-by-side vs stacked comparison view
- Export runs to JSON/Markdown
- History of previous runs
- Per-model advanced settings (temperature, max tokens, system prompt)
- Display latency, token usage, cost estimates

## Non-Goals

- Chat history or conversational interface (single question + evaluation only)
- Fine-tuning or training
- Multi-user or enterprise auth
