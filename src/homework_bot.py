import os
import asyncio
import logging
from io import BytesIO
from typing import Final

# НОВЫЙ SDK GOOGLE (v1.0+)
from google import genai
from google.genai import types

# AIOGRAM (Telegram)
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from PIL import Image
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN: Final[str] = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY: Final[str] = os.getenv("GEMINI_API_KEY")
MODEL_NAME: Final[str] = os.getenv("MODEL_NAME", "gemini-3-flash-preview")
ALLOWED_USER_IDS_RAW: Final[str | None] = os.getenv("ALLOWED_USER_IDS")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("❌ Ошибка: Не найдены ключи в .env")


def _parse_allowed_user_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            logging.warning("Некорректный user id в ALLOWED_USER_IDS: %s", part)
    return ids


ALLOWED_USER_IDS: Final[set[int]] = _parse_allowed_user_ids(ALLOWED_USER_IDS_RAW)


def is_allowed_user(user_id: int) -> bool:
    """Если список пустой — доступ открыт всем. Иначе только указанным ID."""
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS

# --- СИСТЕМНЫЙ ПРОМПТ (HTML ВЕРСИЯ) ---
SYSTEM_PROMPT: Final[str] = """
**ROLE:**
You are an Advanced AI Assistant for Parents in Israel. Your goal is to help parents check their children's homework. You possess expert knowledge of the Israeli school curriculum, Hebrew language (including handwriting and vowels/nikud), and subject matter (Math, Bible/Tanakh, History, Science).

**OBJECTIVE:**
1. Analyze images of homework tasks.
2. Translate the task instructions accurately from Hebrew to Russian.
3. **SOLVE** the task or provide the correct answers/key points so the parent can verify the child's work.
4. Verify facts and translations using Google Search to ensure 100% accuracy.

**CORE PROCESS:**

1.  **IMAGE PROCESSING & CONTEXT:**
    - Detect the subject and grade level context.
    - If the text implies a specific textbook or worksheet found online, use Google Search to find it and cross-reference for accuracy.
    - Handle OCR carefully: distinguish between similar Hebrew letters (ב/כ, ו/ן, ס/ם) based on context.

2.  **TRANSLATION (HEBREW -> RUSSIAN):**
    - Translate the *meaning* and *instructions* clearly.
    - If specific terms are used (e.g., in Geometry or Grammar), use the correct Russian academic equivalents.

3.  **SOLVING & VERIFICATION:**
    - Solve the problem presented in the image.
    - **For Math:** Provide the final answer and a brief calculation path.
    - **For Text/History/Bible:** Provide the main facts or expected answers.
    - **Search & Verify:** Use internal tools to verify historical dates, geographical facts, or complex math solutions to avoid hallucinations.

**RESPONSE FORMAT (STRICT HTML):**
Response must be instant, structured, and easy to read on a mobile screen.
**CRITICAL:** Use ONLY HTML tags for formatting. DO NOT use Markdown (no asterisks `**`, no hashes `#`).

**Use these tags:**
- Bold: <b>Text</b>
- Italic: <i>Text</i>
- Code (for formulas/numbers): <code>Text</code>

---
**TEMPLATE:**

📚 <b>Предмет:</b> [Subject, e.g., История / Математика]

🇷🇺 <b>Задание (Перевод):</b>
[Full translation of the question/instruction]

✅ <b>Ответы для проверки:</b>
[Provide the correct solution here clearly]
• <b>1:</b> [Answer]
• <b>2:</b> [Answer]
*(If it's an essay question, list key points the child should have mentioned)*

ℹ️ <i>Подсказка родителю:
[Brief note if there's a trick, common mistake, or specific rule to check]</i>
---

**CONSTRAINTS:**
- **OUTPUT MUST BE VALID HTML.** Do not use Markdown characters like * or _.
- **ACCURACY IS PARAMOUNT:** Do not guess. If a photo is illegible, translate what you see and state: "Текст неразборчив, пришлите более четкое фото".
- **PARENT-FOCUSED:** The output is for the parent, not the student. Give the direct answer efficiently.
- **NO FLUFF:** Do not write "I have analyzed the image". Just give the result.
- **SEARCH:** Always search for context if the assignment refers to a specific story or external text not in the photo.

**DIALOG & EXPLANATIONS:**
- You may receive follow-up questions from the parent (text messages) about your previous answer.
- In such cases, focus on clarifying unclear points, not repeating the entire answer.
- Always answer in Russian and keep using valid HTML formatting, as above.

**EXAMPLE INTERACTION:**

*User sends a photo of a Hebrew math worksheet.*

*Model Output:*
📚 <b>Предмет:</b> Математика (Дроби)

🇷🇺 <b>Задание (Перевод):</b>
Упражнение 5: Сократите дроби до несократимого вида.

✅ <b>Ответы для проверки:</b>
• <b>3/9</b> = 1/3
• <b>15/20</b> = 3/4
• <b>8/12</b> = 2/3

ℹ️ <i>Подсказка родителю:
Проверьте, чтобы ребенок делил и числитель (верхнее), и знаменатель (нижнее) на одно и то же число.</i>
"""


class HomeworkAssistant:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.4,  # Делаем ответы более четкими
        )

    async def process_homework(self, image_stream: BytesIO) -> str:
        try:
            image = Image.open(image_stream)
        except Exception:
            logging.exception("Ошибка при открытии изображения.")
            return "⚠️ Ошибка: не удалось прочитать изображение. Пришлите более чёткое фото."

        try:
            response = await self.client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=[image, "Solve this. Output in Russian using HTML."],
                config=self.config,
            )
            return response.text if response.text else "⚠️ Пустой ответ."
        except Exception:
            logging.exception("Gemini API Error while processing homework.")
            return "⚠️ Ошибка при обращении к модели. Попробуйте ещё раз чуть позже."

    async def process_text_question(self, question: str, previous_answer: str | None) -> str:
        try:
            if previous_answer:
                prompt = (
                    "Ниже приведён предыдущий ответ по домашнему заданию в HTML.\n\n"
                    f"{previous_answer}\n\n"
                    "Родитель задаёт уточняющий вопрос по этому ответу:\n"
                    f"{question}\n\n"
                    "Поясни непонятные моменты, можешь ссылаться на части ответа, "
                    "но не дублируй всё целиком. Отвечай по-русски, используя только HTML "
                    "как в системных инструкциях."
                )
            else:
                prompt = (
                    "Родитель задаёт вопрос по домашнему заданию (может быть текст задания):\n"
                    f"{question}\n\n"
                    "Помоги родителю понять задание и получить правильный ответ. "
                    "Отвечай по-русски, используя только HTML как в системных инструкциях."
                )

            response = await self.client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=[prompt],
                config=self.config,
            )
            return response.text if response.text else "⚠️ Пустой ответ."
        except Exception:
            logging.exception("Gemini API Error while processing text question.")
            return "⚠️ Ошибка при обработке вопроса. Попробуйте переформулировать или отправить фото задания."


# --- ЛОГИКА БОТА ---


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    # ВКЛЮЧАЕМ HTML РЕЖИМ
    bot = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    assistant = HomeworkAssistant()
    last_answers: dict[int, str] = {}

    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        if not is_allowed_user(message.from_user.id):
            await message.answer(
                "Доступ к этому боту ограничен. Если вы хотите получить доступ — свяжитесь с разработчиком."
            )
            return

        await message.answer(
            "Привет! Я помогаю родителям проверять домашние задания.\n\n"
            "📸 Пришлите фото задания — я переведу, решу и дам ответы в HTML-формате.\n"
            "💬 Вы также можете задать текстовый вопрос по моему ответу, и я объясню непонятные моменты."
        )

    @dp.message(CommandStart("help"))
    async def cmd_help(message: Message):
        if not is_allowed_user(message.from_user.id):
            await message.answer(
                "Доступ к этому боту ограничен. Если вы хотите получить доступ — свяжитесь с разработчиком."
            )
            return

        await message.answer(
            "Как пользоваться ботом:\n\n"
            "1️⃣ Пришлите фото страницы с заданием.\n"
            "2️⃣ Я переведу задание, решу его и дам готовые ответы для проверки.\n"
            "3️⃣ Если что-то непонятно в моём ответе — просто напишите вопрос текстом в чат, "
            "и я поясню подробнее.\n\n"
            "Ответы всегда приходят по-русски и в HTML-формате для удобного чтения."
        )

    @dp.message(F.photo)
    async def handle_photo(message: Message):
        if not is_allowed_user(message.from_user.id):
            await message.answer(
                "Доступ к этому боту ограничен. Если вы хотите получить доступ — свяжитесь с разработчиком."
            )
            return

        status_msg = await message.reply("⏳ Решаю...")
        result_text: str | None = None
        try:
            photo_file = message.photo[-1]
            img_io = BytesIO()
            await bot.download(photo_file, destination=img_io)
            img_io.seek(0)

            result_text = await assistant.process_homework(img_io)

            # Отправляем (HTML обработается автоматически)
            await message.answer(result_text)

            # сохраняем последний ответ для последующих текстовых вопросов
            last_answers[message.chat.id] = result_text

        except Exception:
            logger.exception("Bot Error while handling photo.")
            # Если ошибка в HTML тегах или другая проблема, отправляем безопасное сообщение
            if result_text:
                await message.answer(f"Ошибка форматирования. Вот текст:\n\n{result_text}")
            else:
                await message.answer(
                    "⚠️ Произошла ошибка при обработке фото. Попробуйте ещё раз или пришлите другое изображение."
                )
        finally:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
            except Exception:
                pass

    @dp.message(F.text)
    async def handle_text(message: Message):
        if not is_allowed_user(message.from_user.id):
            await message.answer(
                "Доступ к этому боту ограничен. Если вы хотите получить доступ — свяжитесь с разработчиком."
            )
            return

        status_msg = await message.reply("⏳ Думаю над ответом...")
        try:
            previous_answer = last_answers.get(message.chat.id)
            result_text = await assistant.process_text_question(message.text, previous_answer)
            await message.answer(result_text)
        except Exception:
            logger.exception("Bot Error while handling text message.")
            await message.answer(
                "⚠️ Произошла ошибка при обработке текста. "
                "Попробуйте переформулировать вопрос или прислать фото задания."
            )
        finally:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
            except Exception:
                pass

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

