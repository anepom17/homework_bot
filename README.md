# Homework Bot

Telegram bot for parents in Israel to help check their children's homework using Google Gemini and image-based input.

## Features

- Receives photos of homework pages via Telegram.
- Uses Google Gemini (multi-modal) to:
  - detect the subject and context,
  - translate Hebrew instructions to Russian,
  - solve the task and provide clear answers in HTML.
- Supports follow-up text questions from the parent to clarify the previous answer.
- Access control by allowed Telegram user IDs (configured via environment variables).

## Configuration

Environment variables (via `.env` in local dev or Coolify env vars in production):

- `TELEGRAM_TOKEN` – Telegram bot token.
- `GEMINI_API_KEY` – Google Gemini API key.
- `MODEL_NAME` – Gemini model to use (e.g. `gemini-3-flash-preview`).
- `ALLOWED_USER_IDS` – comma-separated list of allowed Telegram user IDs.

## Local run

```bash
python src/homework_bot.py
```

## Check available Gemini models

```bash
python scripts/check_models.py
```

## Docker

The project includes a simple `Dockerfile` compatible with Coolify:

```bash
docker build -t homework-bot .
docker run --env-file .env homework-bot
```

