"""FastAPI backend. Holds the one Anthropic API key; the frontend and its
users never see it — every request is proxied through here.

Run locally:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import secrets
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import config
from .agent_loop import AgentError, run_agent_turn
from .rate_limit import rate_limiter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("main")

app = FastAPI(title="Claude Chat App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)


class ChatResponse(BaseModel):
    reply: str


def _check_access_code(x_access_code: str | None) -> None:
    if not config.ACCESS_CODE:
        # Fail closed: an unset code means "not configured", not "open to all".
        raise HTTPException(
            status_code=500,
            detail="Server is missing APP_ACCESS_CODE. Set it in the environment (see .env.example).",
        )
    if not x_access_code or not secrets.compare_digest(x_access_code, config.ACCESS_CODE):
        raise HTTPException(status_code=401, detail="Invalid or missing access code.")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    request: Request,
    x_access_code: str | None = Header(default=None),
) -> ChatResponse:
    # Rate limit before checking the access code, so failed/guessed codes
    # count against the same per-IP budget as legitimate use — otherwise an
    # attacker could brute-force the code with unlimited 401s.
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = rate_limiter.check(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after}s.",
        )

    _check_access_code(x_access_code)

    if not config.ANTHROPIC_API_KEY:
        # Fails loudly rather than silently proxying a request that will 401.
        raise HTTPException(
            status_code=500,
            detail="Server is missing ANTHROPIC_API_KEY. Set it in the environment (see .env.example).",
        )

    if req.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="The last message must be from the user.")

    history = [m.model_dump() for m in req.messages]

    try:
        reply = run_agent_turn(history)
    except AgentError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        log.exception("agent turn failed")
        raise HTTPException(status_code=500, detail="Something went wrong processing that message.")

    return ChatResponse(reply=reply)
