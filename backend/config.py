"""Central place for environment-derived configuration.

Loads .env once (via python-dotenv) so every other module can just import
from here instead of touching os.environ directly.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")

# Shared secret gating access to /api/chat. Give this out only to the people
# you want using the app — it is not a per-user account system, just a
# lock on the front door. Required: if unset, the server refuses every
# chat request rather than defaulting to open access.
ACCESS_CODE = os.environ.get("APP_ACCESS_CODE", "")

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5500").split(",")
    if origin.strip()
]

PORT = int(os.environ.get("PORT", "8000"))

RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "300"))
