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
| GitHub Integration | PyGitHub (auto PR creation) |
| Containers | Docker + Docker Compose |

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
source .venv/bin/activate        # Windows WSL: same command
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

## Quick Start — Docker

> Requires [Docker Desktop](https://www.docker.com/products/docker-desktop) with WSL2 integration enabled.

```bash
# 1. Fill in backend/.env (GROQ_API_KEY is required)
cp backend/.env.example backend/.env
# edit backend/.env

# 2. Start everything
sudo docker compose up --build
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
5. Shadow Runner scores before vs after — auto-promotes if improvement ≥10%

Click any card to expand it: root cause, trace evidence, linked patch with PR URL, and shadow scores are all shown inline.

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

Every failed LangSmith run now flows into TraceGuard automatically.

---

## Production Deployment

### Backend → Railway

1. [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo** → select `traceguard-ai`
2. Railway auto-detects the root `Dockerfile`
3. Add a **PostgreSQL** plugin: Railway injects `DATABASE_URL` automatically
4. Set these **Variables** in Railway:

| Variable | Value |
|---|---|
| `GROQ_API_KEY` | your Groq key |
| `LANGCHAIN_API_KEY` | your LangSmith key |
| `LANGCHAIN_PROJECT` | `traceguard-ai` |
| `SECRET_KEY` | any random string (`openssl rand -hex 32`) |
| `CORS_ORIGINS` | your Vercel frontend URL |

5. Railway gives you a public URL like `https://traceguard-ai-production.up.railway.app`

### Frontend → Vercel

1. [vercel.com](https://vercel.com) → **Add New Project** → import `traceguard-ai`
2. Set **Root Directory** to `frontend`
3. Add environment variable: `VITE_API_URL=https://your-railway-url`
4. Deploy

---

## Project Structure

```
traceguard-ai/
├── .github/workflows/ci.yml     # GitHub Actions — backend + frontend CI
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point + WebSocket
│   │   ├── config.py            # Settings (Groq key, model, DB URL…)
│   │   ├── api/
│   │   │   ├── webhook.py       # /simulate + /langsmith endpoints
│   │   │   ├── failures.py      # GET /api/failures
│   │   │   ├── patches.py       # GET/POST /api/patches (approve/reject)
│   │   │   ├── evals.py         # GET /api/evals
│   │   │   └── ws.py            # WebSocket broadcaster
│   │   ├── classifier/
│   │   │   └── classifier.py    # Groq-powered failure taxonomy
│   │   ├── agents/
│   │   │   └── patch_bot.py     # LangGraph: fetch_code → generate_fix → open_pr
│   │   ├── eval_writer/
│   │   │   └── eval_synthesizer.py
│   │   ├── shadow_runner/
│   │   │   └── shadow_runner.py # A/B eval scoring + auto-promote logic
│   │   ├── models/              # SQLAlchemy ORM: Failure, Patch, EvalCase
│   │   └── db/database.py
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
│   │   └── lib/api.ts           # Typed API calls (axios)
│   ├── vite.config.ts           # Proxy config (BACKEND_URL env var)
│   └── Dockerfile
├── scripts/
│   └── run_demo_agent.py        # Fires all 5 failure types in sequence
├── docker-compose.yml
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/failures` | List all failures |
| `GET` | `/api/failures/{id}` | Get one failure |
| `GET` | `/api/patches` | List all patches |
| `POST` | `/api/patches/{id}/approve` | Approve a patch |
| `POST` | `/api/patches/{id}/reject` | Reject a patch |
| `GET` | `/api/evals` | List all eval cases |
| `POST` | `/api/webhook/langsmith` | Real LangSmith Engine webhook |
| `POST` | `/api/webhook/simulate` | Inject a demo failure |
| `WS` | `/ws` | Live event stream |

### Simulate via curl
```bash
curl -X POST http://localhost:8000/api/webhook/simulate \
  -H "Content-Type: application/json" \
  -d '{"failure_hint": "hallucination"}'
```

---

## Groq Model Options

Set `GROQ_MODEL` in `backend/.env`:

| Model | Speed | Best for |
|---|---|---|
| `llama-3.3-70b-versatile` | Fast | Default — best quality |
| `llama3-8b-8192` | Fastest | High-volume / testing |
| `llama-3.1-8b-instant` | Instant | Demo / low latency |

---

## Known Issues & Fixes Applied

| Issue | Fix |
|---|---|
| Missing `__init__.py` in all `backend/app/` packages | Added 8 empty `__init__.py` files — Python wouldn't recognize packages without them |
| `process_trace` background task received a closed DB session | Function now opens its own `SessionLocal()` instead of using the request-scoped session |
| `langchain-core` version conflict in `requirements.txt` | Loosened strict pin (`==0.3.10`) to `>=0.3.12` to allow pip to resolve compatible versions |
| Frontend `package.json` missing half its dependencies | Added `@tanstack/react-query`, `axios`, `react-router-dom`, `lucide-react`, `@tailwindcss/vite`, `tailwindcss` |
| TypeScript `erasableSyntaxOnly` unknown in TS 5.7 | Removed from both `tsconfig.app.json` and `tsconfig.node.json` (it's a TS 5.8+ option) |
| Docker: frontend proxy `ECONNREFUSED` to backend | Vite proxy target now reads `BACKEND_URL` env var; docker-compose sets `BACKEND_URL=http://backend:8000` so containers talk to each other correctly |
| Docker: `permission denied` on Docker socket in WSL2 | `sudo usermod -aG docker $USER`, then reopen WSL terminal |
| OpenAI dependency | Swapped to Groq (`langchain-groq`) — faster, free tier available, no credit card needed for dev |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, coding guidelines, and how to add a new failure type.

## License

[MIT](LICENSE)
