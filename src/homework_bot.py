import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, TelegramObject
from aiogram.utils.chat_action import ChatActionSender

from assistant import HomeworkAssistant
from config import ALLOWED_USER_IDS, TELEGRAM_TOKEN
from formatting import html_to_plain, sanitize_html, split_html, split_plain

logger = logging.getLogger(__name__)
router = Router()

ACCESS_DENIED_TEXT = (
    "Доступ к этому боту ограничен. Если вы хотите получить доступ — свяжитесь с разработчиком."
)


class AccessMiddleware(BaseMiddleware):
    """Пропускает только пользователей из ALLOWED_USER_IDS."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id not in ALLOWED_USER_IDS:
            logger.info("Отказ в доступе: user_id=%s", user.id if user else None)
            if isinstance(event, Message):
                await event.answer(ACCESS_DENIED_TEXT)
            return None
        return await handler(event, data)


async def send_answer(message: Message, text: str) -> None:
    """Отправляет ответ модели: очищенный HTML частями, а при ошибке разметки — простым текстом."""
    for chunk in split_html(sanitize_html(text)):
        try:
            await message.answer(chunk)
        except TelegramBadRequest:
            logger.warning("Telegram отклонил HTML, отправляю простым текстом.", exc_info=True)
            for plain in split_plain(html_to_plain(chunk)):
                await message.answer(plain, parse_mode=None)


async def run_with_status(message: Message, bot: Bot, status_text: str, job: Awaitable[str]) -> None:
    """Показывает статус и «печатает…», пока модель думает, затем отправляет ответ."""
    status_msg = await message.reply(status_text)
    try:
        async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
            result = await job
        await send_answer(message, result)
    except Exception:
        logger.exception("Bot Error while handling message.")
        await message.answer(
            "⚠️ Произошла ошибка. Попробуйте ещё раз или пришлите другое фото.", parse_mode=None
        )
    finally:
        try:
            await status_msg.delete()
        except TelegramBadRequest:
            pass


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я помогаю родителям проверять домашние задания.\n\n"
        "📸 Пришлите фото задания — я переведу, решу и дам ответы для проверки.\n"
        "💬 Потом можно задать текстовый вопрос по заданию, и я объясню непонятные моменты."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Как пользоваться ботом:\n\n"
        "1️⃣ Пришлите фото страницы с заданием (можно файлом — так лучше читается почерк). "
        "В подписи к фото можно уточнить, что именно проверить.\n"
        "2️⃣ Я переведу задание, решу его и дам готовые ответы для проверки.\n"
        "3️⃣ Если что-то непонятно — напишите вопрос текстом, я помню последнее задание.\n\n"
        "Новое фото начинает новый разговор."
    )


@router.message(F.photo | F.document.mime_type.startswith("image/"))
async def handle_image(message: Message, bot: Bot, assistant: HomeworkAssistant) -> None:
    if message.photo:
        file, mime_type = message.photo[-1], "image/jpeg"
    else:
        file, mime_type = message.document, message.document.mime_type

    image = await bot.download(file)
    job = assistant.solve_image(message.chat.id, image.read(), mime_type, message.caption)
    await run_with_status(message, bot, "⏳ Решаю...", job)


@router.message(F.text)
async def handle_text(message: Message, bot: Bot, assistant: HomeworkAssistant) -> None:
    job = assistant.ask(message.chat.id, message.text)
    await run_with_status(message, bot, "⏳ Думаю над ответом...", job)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if not ALLOWED_USER_IDS:
        logger.warning("ALLOWED_USER_IDS пуст — бот никому не будет отвечать.")

    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(assistant=HomeworkAssistant())
    dp.message.outer_middleware(AccessMiddleware())
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
