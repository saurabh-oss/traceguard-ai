# TraceGuard AI

> **Autonomous Quality Firewall for LLM Agents — Powered by LangSmith**

TraceGuard AI sits one layer above [LangSmith Engine](https://smith.langchain.com) and acts as a self-healing immune system for your AI agents. When a failure is detected, it automatically classifies it, generates a targeted code fix, writes an evaluator, runs a shadow deployment, and opens a PR — all without human intervention until the final approval step.

> "LangSmith Engine gives you the smoke detector. TraceGuard AI is the automatic sprinkler system."

[![CI](https://github.com/saurabh-oss/traceguard-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/saurabh-oss/traceguard-ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)

---

## How It Works

```
LangSmith Engine
      │
      ▼  webhook  /  simulate endpoint
┌──────────────────────────────────────────────────┐
│                  TraceGuard AI                   │
│                                                  │
│  1. Classify    → maps trace to failure type     │
│  2. Patch Bot   → LangGraph agent generates PR   │
│  3. Eval Writer → auto-creates LangSmith eval    │
│  4. Shadow Run  → A/B score before vs after      │
│  5. Dashboard   → human approve / reject PR      │
└──────────────────────────────────────────────────┘
```

### Failure Taxonomy (10 types)

| Type | Description |
|---|---|
| `infinite_loop` | Agent cycles with no exit condition |
| `hallucination` | Fabricated facts not in context |
| `tool_misuse` | Wrong args, schema mismatch, wrong tool |
| `context_overflow` | Input exceeds model context window |
| `empty_response` | Agent returned null or empty output |
| `format_error` | Response didn't match required schema |
| `reasoning_failure` | Chain-of-thought broke down |
| `latency_regression` | Response time degraded from baseline |
| `tool_timeout` | External API timed out, no fallback |
| `unknown` | Unclassified failure |

---

## Dashboard

- **Stats bar** — total failures, counts by severity (critical / high / medium / low), total patches generated
- **Failure cards** — click any card to expand: root cause, trace evidence, auto-patch status, shadow eval score
- **Live feed** — WebSocket ticker in the nav shows events in real time
- **Simulate buttons** — inject any of the 5 failure types instantly for demo

---

## Tech Stack

| Layer | Tools |
|---|---|
| Agent Orchestration | LangGraph, LangChain Core |
| LLM Provider | Groq (`llama-3.3-70b-versatile`) |
| Backend API | FastAPI + Uvicorn, Python 3.12 |
| Database | SQLite (dev) → PostgreSQL (prod) |
| Real-time | WebSocket push |
| Frontend | React 19 + Vite + Tailwind CSS v4 |
| GitHub Integration | PyGitHub (auto PR creation + merge/close) |
| Containers | Docker + Docker Compose |

---

## Quick Start — Docker Hub (fastest)

> **Note:** Without `DATABASE_URL` the backend defaults to SQLite, which is lost when the container restarts. Set `DATABASE_URL` to a PostgreSQL connection string for persistent storage.

```bash
docker run -d \
  -e GROQ_API_KEY=gsk_... \
  -e LANGCHAIN_API_KEY=lsv2_... \
  -e LANGCHAIN_PROJECT=traceguard-ai \
  -e GITHUB_TOKEN=ghp_... \
  -e GITHUB_REPO=your-org/your-agent-repo \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  -e CORS_ORIGINS=https://your-frontend.vercel.app \
  -e API_KEY=your-secret-key \
  -p 8000:8000 \
  saurabh-oss/traceguard-ai:latest
```

Backend runs at `http://localhost:8000`. All config is via environment variables — no config files needed.

---

## Quick Start — Local Dev

### Prerequisites
- Python 3.12
- Node.js 22
- A [Groq API key](https://console.groq.com) (free tier is enough)

### 1. Clone
```bash
git clone https://github.com/saurabh-oss/traceguard-ai
cd traceguard-ai
```

### 2. Backend
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Open .env and set GROQ_API_KEY=gsk_...
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

---

## Quick Start — Docker Compose

> Requires [Docker Desktop](https://www.docker.com/products/docker-desktop) with WSL2 integration enabled.

```bash
# 1. Fill in backend/.env (GROQ_API_KEY is required)
cp backend/.env.example backend/.env
# edit backend/.env

# 2. Start everything
docker compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173

**WSL2 note:** If you get `permission denied while trying to connect to the Docker socket`, run:
```bash
sudo usermod -aG docker $USER
# then close and reopen your WSL terminal
```

---

## Demo Walkthrough

With both servers running, open the Dashboard and click any simulate button:

| Button | What it simulates |
|---|---|
| `+ infinite loop` | Agent hit iteration limit (12 tool calls) |
| `+ hallucination` | Fabricated citation with fake DOI |
| `+ tool misuse` | Raw LLM string passed to calculator |
| `+ context overflow` | 145K tokens against a 128K limit |
| `+ empty response` | Agent returned `{}` |

**What happens automatically after each click:**
1. Failure card appears — status `new`
2. Groq classifies it — severity badge and failure type appear
3. Patch Bot (LangGraph: fetch → fix → PR) runs — status `patched`
4. Eval Writer generates a LangSmith evaluator — visible in **Eval Vault**
5. Shadow Runner scores before vs after — auto-promotes if improvement ≥ 10%

Click any card to expand it: root cause, trace evidence, linked patch with PR URL, and shadow scores are all shown inline.

Go to **Patch Review** to approve or reject the generated PR. Approving squash-merges it on GitHub; rejecting closes it with a comment.

### Fire all 5 scenarios at once (demo agent)

Clone the companion repo and run it against your TraceGuard instance:

```bash
git clone https://github.com/saurabh-oss/traceguard-demo-agent
cd traceguard-demo-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export LANGCHAIN_API_KEY=lsv2_your-key
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_PROJECT=traceguard-ai
export GROQ_API_KEY=gsk_your-key
PYTHONPATH=. python scripts/run_failures.py
```

Traces appear in LangSmith; TraceGuard's poller picks them up within 60 s.

---

## Connecting Real LangSmith

### 1. Create a LangSmith account

Sign up free at [smith.langchain.com](https://smith.langchain.com), create a project named **`traceguard-ai`**, and generate an API key under **Settings → API Keys**.

### 2. Add the webhook

In LangSmith → your project → **Settings → Webhooks → Add Webhook**:

| Field | Value |
|---|---|
| URL | `https://your-backend-domain/api/webhook/langsmith` |
| Trigger | **Run Failed** |

Every failed LangSmith run now flows into TraceGuard automatically. This endpoint is intentionally auth-free — LangSmith webhooks cannot send custom headers.

---

## Production Deployment

### Backend → Railway

1. [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo** → select `traceguard-ai`
2. Railway auto-detects the root `Dockerfile`
3. Add a **PostgreSQL** plugin: Railway injects `DATABASE_URL` automatically — do not set it manually
4. Set these **Variables** in the Railway backend service:

| Variable | Value |
|---|---|
| `GROQ_API_KEY` | your Groq key |
| `LANGCHAIN_API_KEY` | your LangSmith key |
| `LANGCHAIN_PROJECT` | `traceguard-ai` |
| `GITHUB_TOKEN` | GitHub personal access token with `repo` scope |
| `GITHUB_REPO` | `your-org/your-agent-repo` |
| `SECRET_KEY` | any random string (`openssl rand -hex 32`) |
| `API_KEY` | strong random secret for write-endpoint auth |
| `CORS_ORIGINS` | your Vercel frontend URL |

5. Railway gives you a public URL like `https://traceguard-ai-production.up.railway.app`

### Frontend → Vercel

1. [vercel.com](https://vercel.com) → **Add New Project** → import `traceguard-ai`
2. Set **Root Directory** to `frontend`
3. Add environment variables:
   - `VITE_API_URL` → `https://your-railway-url`
   - `VITE_API_KEY` → same value as `API_KEY` in Railway
4. Deploy

---

## Project Structure

```
traceguard-ai/
├── .github/workflows/
│   ├── ci.yml               # Backend + frontend CI on every push
│   └── docker.yml           # Docker Hub publish on version tags (v*)
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entry point, WebSocket, lifespan startup
│   │   ├── config.py        # Settings (Pydantic, reads from env / .env)
│   │   ├── api/
│   │   │   ├── webhook.py   # POST /simulate + /langsmith, full pipeline
│   │   │   ├── failures.py  # GET /api/failures
│   │   │   ├── patches.py   # GET/POST /api/patches (approve / reject)
│   │   │   ├── evals.py     # GET /api/evals
│   │   │   ├── auth.py      # X-API-Key header dependency
│   │   │   └── ws.py        # WebSocket broadcaster
│   │   ├── classifier/
│   │   │   └── classifier.py    # Groq-powered failure taxonomy (10 types)
│   │   ├── agents/
│   │   │   └── patch_bot.py     # LangGraph: fetch_code → generate_fix → open_pr
│   │   ├── eval_writer/
│   │   │   └── eval_synthesizer.py  # Auto-generates LangSmith evaluator code
│   │   ├── shadow_runner/
│   │   │   └── shadow_runner.py     # LLM-as-judge A/B scoring + auto-promote
│   │   ├── langsmith_poller.py      # Background task: polls LangSmith every 60s
│   │   ├── models/                  # SQLAlchemy ORM: Failure, Patch, EvalCase
│   │   └── db/database.py           # Engine, SessionLocal, get_db
│   ├── alembic/             # Database migrations
│   ├── .env.example
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx    # Stats bar + expandable failure cards
│   │   │   ├── PatchReview.tsx  # Approve / reject patches with diff view
│   │   │   └── EvalVault.tsx    # Evaluator code + shadow scores
│   │   ├── components/
│   │   │   └── LiveFeed.tsx     # WebSocket live event ticker
│   │   └── lib/api.ts           # Typed API calls (axios + env-based base URL)
│   ├── .env.example
│   ├── vite.config.ts           # Proxy config (BACKEND_URL env var)
│   └── Dockerfile
├── scripts/
│   └── run_demo_agent.py        # Fires all 5 failure types in sequence
├── docker-compose.yml
├── Dockerfile                   # Root: used by Railway and Docker Hub
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

---

## API Reference

| Method | Endpoint | Auth required | Description |
|---|---|---|---|
| `GET` | `/health` | No | Health check |
| `GET` | `/api/failures` | No | List all failures |
| `GET` | `/api/failures/{id}` | No | Get one failure with full detail |
| `GET` | `/api/patches` | No | List all patches |
| `GET` | `/api/patches/{id}` | No | Get one patch |
| `POST` | `/api/patches/{id}/approve` | Yes | Squash-merge PR, mark resolved |
| `POST` | `/api/patches/{id}/reject` | Yes | Close PR, mark rejected |
| `GET` | `/api/evals` | No | List all eval cases with scores |
| `POST` | `/api/webhook/langsmith` | No | Real LangSmith webhook receiver |
| `POST` | `/api/webhook/simulate` | Yes | Inject a demo failure |
| `WS` | `/ws` | No | Live event stream |

### Authentication

Set `API_KEY` in your environment to enable auth. Write endpoints require:

```
X-API-Key: your-secret-key
```

`/api/webhook/langsmith` is intentionally auth-free — LangSmith cannot send custom request headers.

Leave `API_KEY` unset to run fully open (suitable for local dev and demos).

### Simulate via curl
```bash
# No auth (local dev)
curl -X POST http://localhost:8000/api/webhook/simulate \
  -H "Content-Type: application/json" \
  -d '{"failure_hint": "hallucination"}'

# With auth (production)
curl -X POST https://your-backend/api/webhook/simulate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"failure_hint": "hallucination"}'
```

Valid `failure_hint` values: `infinite_loop`, `hallucination`, `tool_misuse`, `context_overflow`, `empty_response`

---

## Groq Model Options

Set `GROQ_MODEL` in `backend/.env`:

| Model | Speed | Best for |
|---|---|---|
| `llama-3.3-70b-versatile` | Fast | Default — best quality |
| `llama3-8b-8192` | Fastest | High-volume / testing |
| `llama-3.1-8b-instant` | Instant | Demo / low latency |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, coding guidelines, and how to add a new failure type.

## License

[MIT](LICENSE)
