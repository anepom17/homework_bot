import asyncio
import logging
from collections import OrderedDict

from google import genai
from google.genai import chats, types

from config import (
    GEMINI_API_KEY,
    GEMINI_TIMEOUT_SECONDS,
    MAX_CHAT_SESSIONS,
    MODEL_NAME,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

IMAGE_PROMPT = "Реши задание с фото. Ответ по-русски, в HTML по правилам из системных инструкций."


class HomeworkAssistant:
    """Обёртка над Gemini: одна чат-сессия на Telegram-чат, новое фото начинает новую сессию."""

    def __init__(self) -> None:
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.4,  # Делаем ответы более четкими
        )
        self._sessions: OrderedDict[int, chats.AsyncChat] = OrderedDict()

    def _new_session(self, chat_id: int) -> chats.AsyncChat:
        session = self.client.aio.chats.create(model=MODEL_NAME, config=self.config)
        self._sessions[chat_id] = session
        self._sessions.move_to_end(chat_id)
        while len(self._sessions) > MAX_CHAT_SESSIONS:
            self._sessions.popitem(last=False)
        return session

    def _get_session(self, chat_id: int) -> chats.AsyncChat:
        session = self._sessions.get(chat_id)
        if session is None:
            return self._new_session(chat_id)
        self._sessions.move_to_end(chat_id)
        return session

    async def _send(self, session: chats.AsyncChat, message: list[types.Part | str]) -> str:
        try:
            response = await asyncio.wait_for(
                session.send_message(message), timeout=GEMINI_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.warning("Gemini не ответил за %s с.", GEMINI_TIMEOUT_SECONDS)
            return "⚠️ Модель слишком долго думает. Попробуйте ещё раз чуть позже."
        except Exception:
            logger.exception("Gemini API Error.")
            return "⚠️ Ошибка при обращении к модели. Попробуйте ещё раз чуть позже."
        return response.text or "⚠️ Пустой ответ. Попробуйте прислать фото ещё раз."

    async def solve_image(
        self, chat_id: int, image: bytes, mime_type: str, caption: str | None = None
    ) -> str:
        prompt = IMAGE_PROMPT
        if caption:
            prompt += f"\n\nКомментарий родителя к фото: {caption}"
        session = self._new_session(chat_id)
        return await self._send(session, [types.Part.from_bytes(data=image, mime_type=mime_type), prompt])

    async def ask(self, chat_id: int, question: str) -> str:
        """Уточняющий вопрос в контексте последнего фото (или отдельный вопрос, если фото не было)."""
        return await self._send(self._get_session(chat_id), [question])
