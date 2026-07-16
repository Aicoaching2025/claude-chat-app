# Claude Chat App

A small deployable chat app built on the Claude API, demonstrating the
architecture where **one server-side API key serves every user** — nobody
who uses the deployed app needs (or sees) an Anthropic key of their own.

```
Browser (frontend/)  →  Your backend (backend/, holds ANTHROPIC_API_KEY)  →  Anthropic API
```

The backend runs the tool-use loop per chat turn: a custom `calculator` tool
(executed locally, safely — no `eval()`) and Anthropic's server-side
`web_search` tool (executed by Anthropic, not by this server). The frontend
only ever sees plain user/assistant text — all tool-call bookkeeping stays
server-side and is thrown away once a turn finishes producing its answer.

## Project layout

```
backend/          FastAPI app — the only thing that holds the API key
  main.py           HTTP routes (/api/chat, /api/health)
  agent_loop.py      the tool-use loop
  tools.py           the calculator tool (AST-based, no eval())
  rate_limit.py      per-IP request cap (protects your API budget)
  config.py          reads environment variables
frontend/          Static HTML/CSS/JS — no build step, no key, no server code
Dockerfile          Container build for the backend
.env.example        Template for local secrets (copy to .env, never commit .env)
```

## Local development

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env   # then edit ../.env and set your real ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

**Frontend** (any static file server works — the app is plain HTML/JS):

```bash
cd frontend
python -m http.server 5500
# then open http://localhost:5500
```

Or use VS Code's "Live Server" extension on `frontend/index.html`. The
default `ALLOWED_ORIGINS` in `.env.example` already includes
`http://localhost:5500`.

Open the page, send a message — the browser talks to `localhost:8000`,
which is the only thing that ever talks to Anthropic.

## Deploying

**Backend** — build from the `Dockerfile` and deploy it to any container
host (Render, Fly.io, Railway, a VPS, AWS/GCP/Azure). The important part is
setting environment variables **in that platform's dashboard/secrets
manager**, not in a committed file:

- `ANTHROPIC_API_KEY` — your real key
- `ALLOWED_ORIGINS` — the URL(s) your deployed frontend will be served from
- `CLAUDE_MODEL`, `RATE_LIMIT_MAX_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS` — optional, sensible defaults apply

**Frontend** — it's static files, so host it anywhere that serves static
files (Netlify, Vercel, GitHub Pages, S3+CloudFront, or the same host as the
backend). Before deploying, point it at your live backend by editing the
inline script in `index.html`:

```html
<script>
  window.API_BASE = "https://your-backend.example.com";
</script>
```

## Cost and abuse protection

Because one key serves everyone, a public deployment is a public route to
your Anthropic bill. This scaffold includes a basic in-memory per-IP rate
limiter (`backend/rate_limit.py`) as a first line of defense, but it's
demo-grade: it resets on restart and doesn't coordinate across multiple
server instances. Before a real public launch, consider:

- A shared rate-limit store (Redis) if you run more than one backend instance
- Basic auth or invite-only access if this isn't meant to be fully public
- Anthropic-side usage alerts/limits on the API key itself

## Why no per-user API keys

Users of the deployed app never need their own Anthropic key — that's the
whole point of routing every request through your backend. The only key
that exists lives in your hosting provider's environment variables, never
in a browser, never in git history, and never on your local machine once
it's deployed.
