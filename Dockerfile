FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend

# ANTHROPIC_API_KEY, CLAUDE_MODEL, ALLOWED_ORIGINS, etc. are supplied by the
# host platform's environment/secrets settings at deploy time — not baked
# into the image and not read from a .env file here.
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
