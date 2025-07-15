import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import google.generativeai as genai

from utils.google_ai_requests import generate_recipe
from utils.recipe_formatter import format_recipe
from utils.error_handlers import register_error_handlers
from utils.middlewares.throttling import ThrottlingMiddleware

# Создаем папку для логов ПЕРЕД тем, как пытаемся в нее писать.
os.makedirs("logs", exist_ok=True)

# Аскетичное логирование без цвета
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/chef_sadist.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiogram").setLevel(logging.WARNING)

# load_dotenv() попытается загрузить .env локально, но не вызовет ошибку на сервере
load_dotenv() 

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    GOOGLE_AI_KEY = os.getenv("GOOGLE_AI_KEY")

if not Config.TELEGRAM_TOKEN or not Config.GOOGLE_AI_KEY:
    raise ValueError("Ключевые переменные (TELEGRAM_TOKEN, GOOGLE_AI_KEY) не найдены!")

async def check_tokens(bot_instance: Bot, google_key: str) -> bool:
    logging.info("Начинаю предполетную проверку токенов...")
    try:
        me = await bot_instance.get_me()
        logging.info(f"✅ Токен Telegram валиден. Бот: @{me.username}")
    except Exception as e:
        logging.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Токен Telegram НЕВАЛИДЕН или нет связи с API. Ошибка: {e}")
        return False
    
    try:
        genai.configure(api_key=google_key)
        _ = genai.get_model('models/gemini-1.5-pro-latest')
        logging.info("✅ Ключ Google AI валиден и имеет доступ к глобальной модели.")
    except Exception as e:
        logging.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Ключ Google AI НЕВАЛИДЕН или нет доступа к API. Ошибка: {e}")
        return False
    return True

bot = Bot(token=Config.TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "Я — Шеф. А ты — жалкое ничтожество..." # и так далее
    )
    logging.info(f"Пользователь {message.from_user.id} запустил бота.")

@dp.message()
async def handle_ingredients(message: types.Message):
    user_id = message.from_user.id
    if not message.text or message.text.startswith('/'): return
    logging.info(f"Получен запрос от {user_id}: '{message.text[:50]}...'")
    if len(message.text.split(',')) < 2:
        await message.answer("Ты издеваешься? Мне нужно как минимум два ингредиента...")
        return
    
    processing_message = await message.answer("🔪 Анализирую твои помои... Жди.")
    try:
        raw_recipe = await generate_recipe(message.text, Config.GOOGLE_AI_KEY)
        if raw_recipe.startswith("⚠️"):
            await message.answer(raw_recipe)
        else:
            formatted_recipe = format_recipe(raw_recipe)
            await message.answer(formatted_recipe)
    except Exception as e:
        logging.error(f"Критическая ошибка в handle_ingredients для {user_id}: {e}", exc_info=True)
        await message.answer("Что-то сломалось в моей голове.")
    finally:
        await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)

async def main():
    if not await check_tokens(bot, Config.GOOGLE_AI_KEY):
        return
    dp.message.middleware(ThrottlingMiddleware(throttle_time_sec=5))
    register_error_handlers(dp)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Шеф-садист (на движке Google AI) входит в чат...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.info("Запуск серверной версии...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Завершаю работу...")