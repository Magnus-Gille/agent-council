# Agent Council

Local web app to ask the same question to multiple AI models (Anthropic, OpenAI, Google), have them blind-review each other, and aggregate votes to surface the best answer.

## Quick Start
- Backend (FastAPI):
  ```bash
  cd backend
  cp .env.example .env  # add your API keys
  pip install -r requirements.txt
  python -m uvicorn app.main:app --reload
  ```
- Frontend (Vite + React):
  ```bash
  cd frontend
  npm install
  npm run dev
  ```
- Production: `cd frontend && npm run build`, then run the backend; it will serve `frontend/dist`.

## How It Works
- Create a run with a question and at least two models.
- Models generate answers in parallel.
- Models review all answers (blind to authorship) and return scored rankings.
- Votes are aggregated with Borda count; final ranking plus reviews are shown in the UI.

## API (high level)
- `POST /api/runs` create run
- `POST /api/runs/{id}/answers` generate answers
- `POST /api/runs/{id}/evaluate` run cross-reviews and voting
- `GET /api/runs/{id}` fetch run with answers/reviews/results
- `GET /api/models` list available models, `GET /api/providers` list providers

## Configuration
- Backend config via `backend/.env` (see `.env.example`):
  - `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`
  - `DATABASE_URL` (defaults to local SQLite)
  - `MAX_CONCURRENCY`, `HOST`, `PORT`

## Repo Structure
- `backend/`: FastAPI app, provider adapters, orchestrator, SQLite models.
- `frontend/`: React UI, Vite config, seasonal styling.
- `ARCHITECTURE.md`: Full system and data-flow reference.

## Notes
- Database defaults to local SQLite (`backend/agent_council.db`).
- Ensure API keys are set before running generation/evaluation.
