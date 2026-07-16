# Claude Chat App

A small deployable chat app built on the Claude API, demonstrating the
architecture where **one server-side API key serves every user** — nobody
who uses the deployed app needs (or sees) an Anthropic key of their own.
Access is gated by a shared access code, so this isn't open to the public —
only people you give the code to can use it.

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
cp ../.env.example ../.env   # then edit ../.env: set ANTHROPIC_API_KEY and APP_ACCESS_CODE
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

Open the page, enter the `APP_ACCESS_CODE` you set in `.env`, then send a
message — the browser talks to `localhost:8000`, which is the only thing
that ever talks to Anthropic.

## Deploying

**Backend** — build from the `Dockerfile` and deploy it to any container
host (Render, Fly.io, Railway, a VPS, AWS/GCP/Azure). The important part is
setting environment variables **in that platform's dashboard/secrets
manager**, not in a committed file:

- `ANTHROPIC_API_KEY` — your real key
- `APP_ACCESS_CODE` — a long random string; the server refuses all chat requests without this set
- `ALLOWED_ORIGINS` — the URL(s) your deployed frontend will be served from
- `CLAUDE_MODEL`, `RATE_LIMIT_MAX_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS` — optional, sensible defaults apply

Share the access code with whoever you want using the app (text, DM, whatever
out-of-band channel) — it's a lock on the front door, not a login system.
Rotate it any time by changing the environment variable and redeploying;
existing sessions will be prompted for the new code on their next message.

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

Because one key serves everyone, an unprotected deployment is a public route
to your Anthropic bill. Two layers guard against that here:

- **Access code** (`backend/main.py` → `_check_access_code`) — every
  `/api/chat` request must carry a matching `X-Access-Code` header, checked
  with a constant-time comparison. Without the right code, no request reaches
  Anthropic at all.
- **Per-IP rate limit** (`backend/rate_limit.py`) — applied *before* the
  access-code check, so it also throttles someone trying to guess the code,
  not just legitimate traffic.

Both are demo-grade: the rate limiter is in-memory (resets on restart, and
each instance tracks its own counts if you run more than one), and the
access code is a single shared secret rather than per-user accounts —
anyone who has the code can use it as themselves, and revoking access for
one person means rotating the code for everyone. That's the right tradeoff
for "share this with a few people," which is what this scaffold is built
for. Before a wider or higher-stakes launch, consider:

- A shared rate-limit store (Redis) if you run more than one backend instance
- Real per-user accounts if you need to tell users apart or revoke individually
- Anthropic-side usage alerts/limits on the API key itself

## Why no per-user API keys

Users of the deployed app never need their own Anthropic key — that's the
whole point of routing every request through your backend. The only key
that exists lives in your hosting provider's environment variables, never
in a browser, never in git history, and never on your local machine once
it's deployed.
