import os
from dotenv import load_dotenv
from google import genai

# Загружаем переменные из .env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
configured_model = os.getenv("MODEL_NAME", "gemini-3-flash-preview")

if not api_key:
    print("ОШИБКА: Ключ не найден в .env файле!")
else:
    print(f"Ключ найден: {api_key[:5]}... (проверяем доступные модели)")
    print(f"Текущая модель из конфигурации: {configured_model}")

    try:
        client = genai.Client(api_key=api_key)
        # Получаем список моделей
        print("\n--- ДОСТУПНЫЕ МОДЕЛИ (gemini*) ---")
        for model in client.models.list():
            if "gemini" in model.name:
                marker = " (ИСПОЛЬЗУЕТСЯ)" if model.name == configured_model else ""
                print(f"✅ {model.name}{marker}")

    except Exception as e:
        print(f"\n❌ Ошибка при запросе: {e}")

