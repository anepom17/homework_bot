import logging
import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"❌ Ошибка: не задана переменная окружения {name}")
    return value


def _parse_allowed_user_ids(raw: str | None) -> frozenset[int]:
    ids: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            logging.warning("Некорректный user id в ALLOWED_USER_IDS: %s", part)
    return frozenset(ids)


TELEGRAM_TOKEN: Final[str] = _require("TELEGRAM_TOKEN")
GEMINI_API_KEY: Final[str] = _require("GEMINI_API_KEY")
MODEL_NAME: Final[str] = os.getenv("MODEL_NAME", "gemini-3-flash-preview")

# Пустой список = доступ закрыт для всех (чтобы бот не тратил API-ключ на чужих).
ALLOWED_USER_IDS: Final[frozenset[int]] = _parse_allowed_user_ids(os.getenv("ALLOWED_USER_IDS"))

# Максимальное время ожидания ответа Gemini (с учётом Google Search).
GEMINI_TIMEOUT_SECONDS: Final[float] = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))

# Сколько чатов держать в памяти для уточняющих вопросов.
MAX_CHAT_SESSIONS: Final[int] = 50

SYSTEM_PROMPT: Final[str] = (
    Path(__file__).resolve().parent / "prompts" / "system_prompt.md"
).read_text(encoding="utf-8")
