# Homework Bot

Telegram bot for parents in Israel to help check their children's homework using Google Gemini and image-based input.

## Features

- Receives photos of homework pages via Telegram (as a photo or as an image file; the caption is passed to the model).
- Uses Google Gemini (multi-modal, with Google Search) to:
  - detect the subject and context,
  - translate Hebrew instructions to Russian,
  - solve the task and provide clear answers formatted with Telegram HTML.
- Follow-up text questions are answered in the context of the last photo (one Gemini chat session per Telegram chat; a new photo starts a new session).
- Model output is sanitized to the HTML subset Telegram supports and split into ≤4096-char messages; if Telegram still rejects it, the answer is sent as plain text.
- Access control by allowed Telegram user IDs. **An empty list denies everyone.**

## Project structure

- `src/homework_bot.py` – Telegram handlers, access middleware, entry point.
- `src/assistant.py` – Gemini chat sessions.
- `src/formatting.py` – HTML sanitizing and message splitting for Telegram.
- `src/config.py` – environment configuration.
- `src/prompts/system_prompt.md` – system prompt for the model.

## Configuration

Environment variables (via `.env` in local dev or Coolify env vars in production):

- `TELEGRAM_TOKEN` – Telegram bot token.
- `GEMINI_API_KEY` – Google Gemini API key.
- `MODEL_NAME` – Gemini model to use (default `gemini-3-flash-preview`).
- `ALLOWED_USER_IDS` – comma-separated list of allowed Telegram user IDs.
- `GEMINI_TIMEOUT_SECONDS` – optional, max wait for a model answer (default `120`).

## Local run

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python src/homework_bot.py
```

Note: a local run with the production token conflicts with the deployed bot (Telegram allows only one polling client per token).

## Check available Gemini models

```bash
python scripts/check_models.py
```

## Docker

The `Dockerfile` is used by Coolify (auto-deploy on push to `master`):

```bash
docker build -t homework-bot .
docker run --env-file .env homework-bot
```
