# Contributing to TraceGuard AI

Thank you for your interest in contributing! This document covers how to set up a local dev environment, coding standards, and how to submit changes.

---

## Dev Environment Setup

### Requirements
- Python 3.12+
- Node.js 22+
- A [Groq API key](https://console.groq.com) (free tier works)

### Backend
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # then fill in GROQ_API_KEY
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

---

## Project Structure

```
backend/app/
├── classifier/     # LLM failure taxonomy (add new failure types here)
├── agents/         # LangGraph patch bot (extend nodes here)
├── eval_writer/    # Eval synthesizer
├── shadow_runner/  # A/B scoring logic
├── api/            # FastAPI routes
└── models/         # SQLAlchemy ORM models

frontend/src/
├── pages/          # Dashboard, PatchReview, EvalVault
├── components/     # LiveFeed (WebSocket ticker)
└── lib/api.ts      # All backend API calls
```

---

## How to Contribute

### Reporting Bugs
Open a GitHub Issue with:
- What you did
- What you expected
- What actually happened
- Logs / screenshots if applicable

### Suggesting Features
Open an Issue tagged `enhancement`. Describe the use case and proposed behavior.

### Submitting a PR

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Make your changes
3. Verify the backend imports: `python -c "from app.main import app"`
4. Verify the frontend builds: `npm run build`
5. Open a PR against `main` with a clear description of what changed and why

### PR Guidelines
- Keep PRs focused — one feature or fix per PR
- Don't commit `.env` or any file with real API keys
- Backend: add a new failure type in `classifier/classifier.py` → `TAXONOMY` dict
- Frontend: follow the existing Tailwind dark-theme pattern (gray-900 cards, teal accents)

---

## Adding a New Failure Type

1. Add it to `TAXONOMY` in [backend/app/classifier/classifier.py](backend/app/classifier/classifier.py)
2. Add a demo trace builder case in `_build_demo_trace()` in [backend/app/api/webhook.py](backend/app/api/webhook.py)
3. Add the button label to `DEMOS` in [frontend/src/pages/Dashboard.tsx](frontend/src/pages/Dashboard.tsx)
4. Optionally add a placeholder code snippet in `PLACEHOLDER_CODE` in [backend/app/agents/patch_bot.py](backend/app/agents/patch_bot.py)

---

## Code Style

- **Python**: standard library imports first, then third-party, then local. No type: ignore unless unavoidable.
- **TypeScript**: strict mode, no `any` in new code (existing `any` casts are pre-existing tech debt).
- **Comments**: only when the *why* is non-obvious — no narrating the what.

---

## Questions?

Open a Discussion on GitHub or file an Issue tagged `question`.
