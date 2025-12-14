# Agent Council - Architecture Documentation

## Overview

Agent Council is a local web application that enables users to query multiple AI models (Anthropic, Google, OpenAI) simultaneously, then have models cross-critique each other's responses and produce a ranked result through voting.

The system implements a **blind peer review** mechanism where AI models evaluate each other's answers without knowing which model produced which response, reducing bias and providing objective quality assessments.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Backend Architecture](#backend-architecture)
3. [Frontend Architecture](#frontend-architecture)
4. [Data Flow](#data-flow)
5. [Database Schema](#database-schema)
6. [API Reference](#api-reference)
7. [Key Algorithms](#key-algorithms)
8. [Provider Adapters](#provider-adapters)
9. [Configuration](#configuration)
10. [Security Considerations](#security-considerations)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              User Browser                                │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    React Frontend (Vite)                            │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │ │
│  │  │ModelSelector │ │QuestionInput │ │  AnswerCard  │ │ReviewSection│ │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────┐ │ │
│  │  │  RunHistory  │ │ProgressIndicator│ │    ChristmasEffects       │ │ │
│  │  └──────────────┘ └──────────────┘ └──────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP/REST
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend                                  │
│                                                                          │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────────────┐ │
│  │   API Routes   │───▶│  Orchestrator  │───▶│   Provider Adapters    │ │
│  │  (routes.py)   │    │                │    │                        │ │
│  └────────────────┘    │  ┌──────────┐  │    │ ┌────────────────────┐ │ │
│                        │  │Evaluation│  │    │ │ AnthropicAdapter   │ │ │
│                        │  │ Service  │  │    │ └────────────────────┘ │ │
│                        │  └──────────┘  │    │ ┌────────────────────┐ │ │
│                        │  ┌──────────┐  │    │ │   OpenAIAdapter    │ │ │
│                        │  │ Voting   │  │    │ └────────────────────┘ │ │
│                        │  │ Service  │  │    │ ┌────────────────────┐ │ │
│                        │  └──────────┘  │    │ │   GoogleAdapter    │ │ │
│                        └────────────────┘    │ └────────────────────┘ │ │
│                                              └────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                    SQLAlchemy ORM + SQLite                          ││
│  │   Runs │ SelectedModels │ Answers │ Reviews │ AggregationResults   ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Async HTTP
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        External AI APIs                                  │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────┐ │
│  │  Anthropic API   │ │    OpenAI API    │ │      Google AI API       │ │
│  │  (Claude models) │ │   (GPT models)   │ │    (Gemini models)       │ │
│  └──────────────────┘ └──────────────────┘ └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Backend Architecture

### Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Settings and environment configuration
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # REST API endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py      # Database connection and session management
│   │   ├── orm.py           # SQLAlchemy ORM models
│   │   └── schemas.py       # Pydantic schemas for validation
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract base adapter class
│   │   ├── registry.py      # Adapter registry and factory
│   │   ├── anthropic.py     # Anthropic/Claude adapter
│   │   ├── openai.py        # OpenAI/GPT adapter
│   │   └── google.py        # Google/Gemini adapter
│   └── services/
│       ├── __init__.py
│       ├── orchestrator.py  # Main workflow coordinator
│       ├── evaluation.py    # Review prompt generation
│       └── voting.py        # Borda count vote aggregation
├── requirements.txt
└── .env.example
```

### Core Components

#### 1. Main Application (`main.py`)

The FastAPI application with:
- **Lifespan management**: Initializes database on startup
- **CORS middleware**: Allows frontend development server access
- **Static file serving**: Serves built frontend in production
- **API router**: Mounts all API routes under `/api` prefix

#### 2. Configuration (`config.py`)

Uses Pydantic Settings for environment-based configuration:

| Setting | Default | Description |
|---------|---------|-------------|
| `anthropic_api_key` | `""` | Anthropic API key |
| `openai_api_key` | `""` | OpenAI API key |
| `google_api_key` | `""` | Google AI API key |
| `database_url` | `sqlite+aiosqlite:///./agent_council.db` | Database connection string |
| `host` | `127.0.0.1` | Server bind host |
| `port` | `8000` | Server bind port |
| `max_concurrency` | `6` | Max parallel API calls |

#### 3. ORM Models (`models/orm.py`)

**RunORM**: Root entity for each evaluation session
- `id`, `created_at`, `question`, `status`, `blind_review`
- Relationships: `selected_models`, `answers`, `reviews`, `aggregation`

**SelectedModelORM**: Models chosen for a run
- `provider`, `model_name`, `params` (JSON)

**AnswerORM**: Generated answers
- `producer_model`, `provider`, `label` (A, B, C...), `text`
- Metrics: `latency_ms`, `tokens_in`, `tokens_out`, `error`

**ReviewORM**: Model evaluations
- `reviewer_model`, `reviewer_provider`
- `reviews` (JSON array of per-answer scores)
- `rank_order` (ordered labels), `confidence`

**AggregationResultORM**: Final voting results
- `final_ranking`, `vote_breakdown`, `method_version`

#### 4. Orchestrator (`services/orchestrator.py`)

Central coordinator managing the complete workflow:

```python
class RunOrchestrator:
    async def create_run(question, selected_models, blind_review) -> RunORM
    async def generate_answers(run_id) -> RunORM
    async def run_evaluation(run_id, reviewer_models?) -> RunORM
    async def run_full_pipeline(question, selected_models, blind_review) -> RunORM
```

**Key Features**:
- Semaphore-based concurrency control
- Parallel answer generation across models
- Blind label assignment (A, B, C...)
- Comprehensive error handling per model

#### 5. Evaluation Service (`services/evaluation.py`)

Builds the structured review prompt that instructs models to:
- Score answers on 6 dimensions (0-10 scale)
- Provide critiques (2-3 sentences each)
- Rank all answers from best to worst
- Output strict JSON format
- Ignore embedded prompt injection attempts

**Scoring Dimensions**:
| Dimension | Description |
|-----------|-------------|
| `correctness` | Factual accuracy |
| `completeness` | Thoroughness of response |
| `clarity` | Writing quality and understandability |
| `helpfulness` | Practical value to the user |
| `safety` | Policy compliance, no harmful content |
| `overall` | Holistic assessment |

#### 6. Voting Service (`services/voting.py`)

Implements **Borda Count** voting algorithm:

```
For N answers, each reviewer assigns:
- 1st place: N-1 points
- 2nd place: N-2 points
- ...
- Last place: 0 points
```

**Tie-breaking order**:
1. Higher Borda total
2. Higher mean overall score
3. Higher mean correctness score

---

## Frontend Architecture

### Directory Structure

```
frontend/
├── src/
│   ├── main.tsx             # React entry point
│   ├── App.tsx              # Main application component
│   ├── App.css              # Global styles + Christmas theme
│   ├── api.ts               # API client functions
│   ├── types.ts             # TypeScript interfaces
│   └── components/
│       ├── index.ts         # Component exports
│       ├── ModelSelector.tsx    # Model selection checkboxes
│       ├── QuestionInput.tsx    # Question form with options
│       ├── AnswerCard.tsx       # Individual answer display
│       ├── ReviewSection.tsx    # Results and voting display
│       ├── RunHistory.tsx       # Sidebar history list
│       ├── ProgressIndicator.tsx # Loading animation
│       └── ChristmasEffects.tsx  # Seasonal decorations
├── index.html
├── vite.config.ts
└── package.json
```

### Component Hierarchy

```
App
├── ChristmasEffects        # Fixed position decorations
├── Header                  # Title and subtitle
├── Sidebar
│   ├── NewRunButton
│   └── RunHistory          # Clickable past runs
└── Main Content
    ├── [Setup Mode]
    │   ├── ModelSelector   # Provider-grouped checkboxes
    │   └── QuestionInput   # Textarea + blind review toggle
    ├── ProgressIndicator   # Shown during generation/evaluation
    └── [Results Mode]
        ├── QuestionDisplay
        ├── AnswersSection
        │   └── AnswerCard[]    # Ranked answer cards
        ├── EvaluationAction    # "Run Evaluation" button
        └── ReviewSection
            ├── WinnerBanner
            ├── FullRanking
            ├── VoteMatrix
            └── DetailedReviews
```

### State Management

Uses React's `useState` hooks in `App.tsx`:

| State | Type | Description |
|-------|------|-------------|
| `selectedModels` | `SelectedModel[]` | Models chosen for new run |
| `currentRun` | `Run \| null` | Active run being displayed |
| `loading` | `boolean` | Answer generation in progress |
| `evaluating` | `boolean` | Evaluation in progress |
| `error` | `string \| null` | Error message to display |
| `historyRefresh` | `number` | Trigger for history reload |

### API Client (`api.ts`)

```typescript
// Provider/model discovery
getProviders(): Promise<ProviderInfo[]>
getModels(): Promise<ModelInfo[]>

// Run lifecycle
createRun(data: RunCreate): Promise<Run>
generateAnswers(runId: number): Promise<Run>
evaluateRun(runId: number): Promise<Run>
getRun(runId: number): Promise<Run>
listRuns(): Promise<Run[]>
deleteRun(runId: number): Promise<void>
```

---

## Data Flow

### Complete Workflow

```
1. USER SETUP
   ┌─────────────────┐
   │ User selects    │
   │ models and      │──▶ selectedModels state
   │ enters question │
   └─────────────────┘

2. RUN CREATION
   ┌─────────────────┐     ┌─────────────────┐
   │ POST /api/runs  │────▶│ Create RunORM   │
   │                 │     │ + SelectedModels│
   └─────────────────┘     └─────────────────┘

3. ANSWER GENERATION
   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
   │ POST /api/runs/ │────▶│ Parallel API    │────▶│ Store answers   │
   │ {id}/answers    │     │ calls to models │     │ with labels     │
   └─────────────────┘     └─────────────────┘     └─────────────────┘

4. EVALUATION (Optional)
   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
   │ POST /api/runs/ │────▶│ Each model      │────▶│ Aggregate votes │
   │ {id}/evaluate   │     │ reviews others  │     │ with Borda count│
   └─────────────────┘     └─────────────────┘     └─────────────────┘

5. RESULTS DISPLAY
   ┌─────────────────┐     ┌─────────────────┐
   │ GET /api/runs/  │────▶│ Display ranked  │
   │ {id}            │     │ results + votes │
   └─────────────────┘     └─────────────────┘
```

### Run Status Transitions

```
pending ──▶ generating_answers ──▶ answers_complete ──▶ evaluating ──▶ complete
    │                │                                       │
    └────────────────┴───────────────────────────────────────┴──▶ failed
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────────┐
│      runs       │       │   selected_models   │
├─────────────────┤       ├─────────────────────┤
│ id (PK)         │◀──┐   │ id (PK)             │
│ created_at      │   │   │ run_id (FK)         │──┐
│ question        │   │   │ provider            │  │
│ status          │   │   │ model_name          │  │
│ blind_review    │   │   │ params (JSON)       │  │
└─────────────────┘   │   └─────────────────────┘  │
        │             │                            │
        │             └────────────────────────────┘
        │
        ▼
┌─────────────────┐       ┌─────────────────────┐
│     answers     │       │      reviews        │
├─────────────────┤       ├─────────────────────┤
│ id (PK)         │       │ id (PK)             │
│ run_id (FK)     │◀──────│ run_id (FK)         │
│ producer_model  │       │ reviewer_model      │
│ provider        │       │ reviewer_provider   │
│ label           │       │ reviews (JSON)      │
│ text            │       │ rank_order (JSON)   │
│ latency_ms      │       │ confidence          │
│ tokens_in       │       │ raw_response        │
│ tokens_out      │       └─────────────────────┘
│ error           │
└─────────────────┘
        │
        ▼
┌─────────────────────────┐
│  aggregation_results    │
├─────────────────────────┤
│ id (PK)                 │
│ run_id (FK, unique)     │
│ final_ranking (JSON)    │
│ vote_breakdown (JSON)   │
│ method_version          │
└─────────────────────────┘
```

---

## API Reference

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/providers` | List available providers |
| `GET` | `/api/models` | List all available models |
| `POST` | `/api/runs` | Create new run |
| `GET` | `/api/runs` | List runs (paginated) |
| `GET` | `/api/runs/{id}` | Get run details |
| `POST` | `/api/runs/{id}/answers` | Generate answers |
| `POST` | `/api/runs/{id}/evaluate` | Run evaluation |
| `DELETE` | `/api/runs/{id}` | Delete run |

### Request/Response Examples

#### Create Run
```json
POST /api/runs
{
  "question": "What is the meaning of life?",
  "selected_models": [
    {"provider": "anthropic", "model_name": "claude-3-5-haiku-20241022", "params": {}},
    {"provider": "openai", "model_name": "gpt-4o-mini", "params": {}}
  ],
  "blind_review": true
}
```

#### Run Response
```json
{
  "id": 1,
  "created_at": "2024-12-14T10:00:00Z",
  "question": "What is the meaning of life?",
  "status": "complete",
  "blind_review": true,
  "selected_models": [...],
  "answers": [
    {
      "id": 1,
      "label": "A",
      "text": "The answer...",
      "latency_ms": 1500,
      "tokens_in": 10,
      "tokens_out": 200
    }
  ],
  "reviews": [...],
  "aggregation": {
    "final_ranking": ["A", "B"],
    "vote_breakdown": {
      "borda_totals": {"A": 2, "B": 0},
      "first_place_votes": {"A": 2, "B": 0},
      "score_averages": {"A": 8.5, "B": 7.0}
    }
  }
}
```

---

## Key Algorithms

### Borda Count Voting

The Borda count method assigns points based on ranking position:

```python
def calculate_borda(rank_order: list[str], n: int) -> dict[str, int]:
    """
    For N candidates:
    - 1st place gets N-1 points
    - 2nd place gets N-2 points
    - Last place gets 0 points
    """
    points = {}
    for position, label in enumerate(rank_order):
        points[label] = n - 1 - position
    return points
```

**Example** with 3 answers (A, B, C):
- If a reviewer ranks: [B, A, C]
- Points: B=2, A=1, C=0

### Review JSON Parsing

Models return structured JSON that is extracted and parsed:

```python
def parse_review_response(raw_text: str) -> dict:
    """Extract JSON from model response, handling markdown code blocks."""
    start = raw_text.find("{")
    end = raw_text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(raw_text[start:end])
    return {"reviews": [], "rank_order": [], "confidence": 0.5}
```

---

## Provider Adapters

### Base Adapter Contract

All adapters implement:

```python
class BaseAdapter(ABC):
    provider_name: str

    def list_models(self) -> list[dict]
    def is_available(self) -> bool
    async def generate_answer(model, question, temperature, max_tokens, system_prompt) -> AnswerResult
    async def generate_review(model, review_prompt, temperature, max_tokens) -> ReviewResult
```

### Provider-Specific Notes

#### Anthropic (Claude)
- Uses `anthropic.AsyncAnthropic` client
- System prompt via `system` parameter
- Token usage from `response.usage`

#### OpenAI (GPT)
- Uses `openai.AsyncOpenAI` client
- Handles reasoning models (o1, o3) differently:
  - No temperature support
  - No system prompts
  - Uses `max_completion_tokens` instead of `max_tokens`
- Newer models (gpt-4.1+, gpt-5+) use `max_completion_tokens`

#### Google (Gemini)
- Uses `google.generativeai` library
- System prompt via `system_instruction`
- Async generation with `generate_content_async`

---

## Configuration

### Environment Variables

Create `.env` file in `backend/` directory:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AI...
DATABASE_URL=sqlite+aiosqlite:///./agent_council.db
HOST=127.0.0.1
PORT=8000
MAX_CONCURRENCY=6
```

### Development Setup

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # Add API keys
python -m uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Production Deployment

```bash
cd frontend && npm run build
cd ../backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The built frontend is served from `http://localhost:8000`.

---

## Security Considerations

### API Key Protection
- Keys loaded from environment variables only
- Never logged or exposed in responses
- Each provider adapter checks key availability before operations

### Prompt Injection Resistance
- Review prompts explicitly warn models to ignore embedded instructions
- Models instructed to judge "ONLY based on content"
- Blind review prevents identity-based bias

### Database Security
- SQLite stored locally (no network exposure)
- Optional export to JSON/Markdown for archival
- Cascade deletes for referential integrity

### CORS Configuration
- Development: allows localhost:3000 and 127.0.0.1:3000
- Production: frontend served from same origin (no CORS needed)

---

## Christmas Theme (Seasonal)

The application includes festive decorations:

### Visual Elements
- **Animated snowflakes**: 60 falling snowflakes with varying sizes and speeds
- **Christmas lights**: Colored bulb string across top of page
- **Christmas tree**: Bottom-right corner with twinkling star
- **Decorations**: Bells, candy canes, holly

### Color Scheme
- Header: Red gradient (`#8B0000` to `#c41e3a`) with gold border
- Background: Forest green gradient
- Buttons: Red with gold borders
- Cards: White with red/gold accents

### CSS Animation Highlights
```css
@keyframes snowfall { /* Falling + swaying motion */ }
@keyframes star-twinkle { /* Scale + rotate + glow */ }
@keyframes light-glow { /* Brightness pulse */ }
@keyframes bell-ring { /* Rotation swing */ }
```

---

## Future Enhancements

Potential improvements for the system:

1. **Streaming responses**: Show answers as they generate
2. **Custom scoring dimensions**: User-defined evaluation criteria
3. **Export formats**: PDF reports, CSV data export
4. **Model comparison analytics**: Historical performance tracking
5. **Webhook notifications**: Alert when long evaluations complete
6. **Rate limit handling**: Exponential backoff for API limits
7. **Multi-turn conversations**: Extend beyond single Q&A

---

*Last updated: December 2024*
