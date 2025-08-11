import os
import asyncio
import logging
import random

# Импорты aiogram
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем ВСЕ необходимые функции и переменные из recipe_synthesizer
from utils.recipe_synthesizer import (
    KNOWLEDGE_BASE, 
    load_knowledge_base, 
    synthesize_response, 
    find_random_recipe_by_category,
    assemble_recipe,
    find_recipe_by_intention # <-- Теперь он точно здесь!
)

# --- БЛОК НАСТРОЙКИ ---

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/chef_sadist.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

from dotenv import load_dotenv
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_V2")

if not TELEGRAM_TOKEN:
    raise ValueError("Не найден токен TELEGRAM_TOKEN_V2 в .env файле!")

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ХРАНИЛИЩЕ СЕССИЙ
USER_SESSIONS = {}

# --- СЛУЖЕБНЫЕ ФУНКЦИИ ---

def get_user_session(user_id: int) -> dict:
    """Гарантированно получает или создает сессию для пользователя.
    Инициализирует все необходимые счетчики и словари."""
    session = USER_SESSIONS.setdefault(user_id, {})
    session.setdefault("category_clicks", {})
    session.setdefault("seen_recipes", {})
    session.setdefault("total_clicks", 0)
    return session

def get_main_menu_builder() -> InlineKeyboardBuilder:
    """Собирает и возвращает билдер для главного меню с категориями."""
    builder = InlineKeyboardBuilder()
    # Перестроенный список категорий для новой раскладки 5х2
    categories = [
        ("🔥 Горячее", "hot_dishes"), 
        ("🥣 Супы", "soups"), 
        ("🍝 Паста", "pasta"),
        ("🥗 Салаты", "salads"), 
        ("🥔 Гарниры", "garnishes"),
        ("🍳 Завтраки", "breakfasts"),
        ("🥪 Бутерброды", "sandwiches"),
        ("🍰 Десерты", "desserts"),
        ("🌶️ Соусы", "sauces"), # Ключ изменен на английский для единообразия
        ("🍕 Фастфуд", "fast_food")
    ]
    for text, category_key in categories:
        builder.add(InlineKeyboardButton(text=text, callback_data=f"category_{category_key}"))
    
    builder.adjust(2) # Раскладка 5х2
    return builder

async def send_recipe_response(message: types.Message, response_data: dict):
    """Универсальная функция для отправки ответа.
    Обрабатывает текст, кнопки терминов ИЛИ кнопки опций.
    Всегда отправляет главное меню после основного ответа."""
    
    response_text = response_data["text"]
    found_terms = response_data.get("found_terms", []) # Используем .get на случай, если их нет
    reply_markup = response_data.get("reply_markup") # Клавиатура для опций, если есть
    
    if reply_markup: # Если synthesize_response вернула клавиатуру (для опций)
        await message.answer(response_text, reply_markup=reply_markup)
    elif found_terms: # Если есть термины для пояснения
        builder = InlineKeyboardBuilder()
        terms_db = KNOWLEDGE_BASE.get("terms", {})
        for term_id in found_terms:
            term_name = terms_db.get(term_id, {}).get("aliases", ["Неизвестно"])[0]
            builder.add(InlineKeyboardButton(text=f"🤔 Что такое «{term_name}»?", callback_data=f"term_{term_id}"))
        builder.adjust(1)
        await message.answer(response_text, reply_markup=builder.as_markup())
    else: # Просто текст (рецепт, если нет терминов, или отказ)
        await message.answer(response_text)
        
    logging.info(f"Отправлен ответ для {message.from_user.id}.")

    # Главное меню всегда отправляется после основного ответа
    menu_builder = get_main_menu_builder()
    await message.answer("Чего желаешь теперь, экспериментатор?", reply_markup=menu_builder.as_markup())

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start", "help"))
async def start_command(message: types.Message):
    """Сбрасывает сессию и выдает клавиатуру категорий."""
    user_id = message.from_user.id
    USER_SESSIONS[user_id] = {"category_clicks": {}, "seen_recipes": {}, "total_clicks": 0}
    logging.info(f"Сессия для пользователя {user_id} сброшена.")

    builder = get_main_menu_builder()
    start_text = (
        "Привет, я — Кира, рыжий ураган, и мы с тобой на моей кухне. Я тебе рада, ты тут гость, но давай будем честны: ты пришел сюда (или пришла) за рецептом и, возможно, за порцией моего фирменного сарказма.\n\n"
        "Что ты можешь прямо сейчас:\n\n"
        "1. Потыкаться в кнопочки и возможно, найти нужный рецепт. У нас их много, пробуй, но не удивляйся повторам и едким комментариям.\n"
        "2. Написать, что ты хочешь приготовить. Пиццу, котлеты, бутерброд, яичницу — я подскажу. А если осмелишься, у меня есть рецепты настоящей карбонары, чизкейка — только спроси.\n"
        "3. Просто напиши, что нашел (или нашла) в холодильнике. Осуждать не буду, и даже подскажу, что еще может потребоваться.\n\n"
        "Кстати, если хочешь погрузиться глубже в философию кулинарного доминирования и не пропустить новые главы моей мудрости, загляни в мой канал 'Дневник повара-садиста': <a href='https://t.me/dnevnik_povara_sadista'>@DnevnikPovaraSadista</a>.\n\n" # <-- Исправлена двойная https://
        "Пробуй. Как сказал Гомер Симпсон, \"я пришел сюда, чтобы меня пичкали таблетками и били током, а не унижали!\". Так вот, унижать не буду. Насчет остального — не уверена\n\n"
        "Шеф Кира"
    )
    await message.answer(start_text, reply_markup=builder.as_markup())
    logging.info(f"Пользователь {user_id} запустил бота и получил клавиатуру категорий.")

# Словарь для контекстных реакций на категории
CATEGORY_REACTIONS = {
    "hot_dishes": "Только не съешь все сразу. Особенно на ночь.",
    "soups": "А, супы... Та самая жидкая, горячая (или холодная) субстанция, которая служит прелюдией к настоящей еде. Или заменяет ее, если ты на диете.",
    "pasta": "Мммм, макароны... Хороший антидепрессант. Если выбрать быстро.",
    "salads": "Овощи? Похвально. Но не думай, что у меня тут только трава. Покопайся, у нас и сытные, мясные салаты имеются. Ищи.",
    "garnishes": "Выбрать гарнир — это полдела. Не забудь про горячее, пустой гарнир обычно очень грустно есть. Добавь хотя бы соус.",
    "breakfasts": "Ты так долго выбираешь завтрак, что он скоро станет обедом.",
    "sandwiches": "А, бутерброды... Быстро, просто и почти всегда вкусно. Главное — не питаться только ими.",
    "desserts": "Не надо так налегать на сладкое. Бывший (или бывшая) этого не стоит.",
    "sauces": "Посмотри, повыбирай, я не давлю. Но не сожги мясо, пока ты тут ищешь.",
    "fast_food": "Сухомятка — не лучший выбор. Но если ты настолько голоден...",
}

@dp.message()
async def handle_ingredients(message: types.Message):
    """
    Обработчик ручного ввода. V2.0.
    Сначала пытается 'прочитать мысли' (поиск по намерению),
    и только потом ищет по ингредиентам.
    """
    if not message.text or message.text.startswith('/'):
        return

    user_query = message.text
    logging.info(f"Получен ручной запрос от {message.from_user.id}: '{user_query}'")

    # --- ЭТАП 1: ПОПЫТКА "ПРОЧИТАТЬ МЫСЛИ" ---
    # find_recipe_by_intention возвращает ТОЛЬКО ОДИН РЕЦЕПТ, если найдет
    intended_recipe = find_recipe_by_intention(user_query)
    
    if intended_recipe:
        logging.info(f"Найдено намерение! Рецепт: {intended_recipe['id']}")
        # Если нашли рецепт по намерению, сразу его собираем и отправляем
        response_data = assemble_recipe(intended_recipe)
        await send_recipe_response(message, response_data)
        return # Важно! Завершаем выполнение функции.

    # --- ЭТАП 2: ЕСЛИ МЫСЛИ НЕ ПРОЧИТАНЫ - ИЩЕМ ПО ИНГРЕДИЕНТАМ ---
    logging.info("Намерение не найдено. Запускаю поиск по ингредиентам...")
    # synthesize_response теперь может вернуть либо 1 рецепт, либо список опций с клавиатурой
    response_data = synthesize_response(user_query)
    await send_recipe_response(message, response_data)

@dp.callback_query(F.data.startswith("term_"))
async def process_term_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопок с терминами."""
    term_id = callback_query.data.split("_", 1)[1]
    terms_db = KNOWLEDGE_BASE.get("terms", {})
    term_data = terms_db.get(term_id)
    
    await callback_query.answer() # Убираем "часики"
    if term_data:
        explanation = term_data.get("explanation", "Объяснение потерялось...")
        sarcastic_comment = random.choice(term_data.get("sarcastic_comments", ["..."]))
        term_name = term_data.get("aliases", ["Неизвестно"])[0].capitalize()
        response_text = (f"<b>🎓 Ликбез по теме «{term_name}»</b>\n\n{explanation}\n\n<i><b>Мой комментарий:</b> {sarcastic_comment}</i>")
        await callback_query.message.answer(response_text)
    else:
        await callback_query.message.answer("Упс... Я забыла, что это значит. Бывает.")
    logging.info(f"Пользователь {callback_query.from_user.id} запросил объяснение для термина '{term_id}'.")

@dp.callback_query(F.data.startswith("category_"))
async def process_category_callback(callback_query: types.CallbackQuery):
    """V3.1 - Реализует 'Многоуровневую Агрессию'."""
    user_id = callback_query.from_user.id
    category = callback_query.data.split("_", 1)[1]
    
    session = get_user_session(user_id)
    
    # --- НОВАЯ ЛОГИКА: МНОГОУРОВНЕВАЯ АГРЕССИЯ ---
    
    # Инкрементируем счетчики
    session["total_clicks"] += 1
    category_clicks = session["category_clicks"].get(category, 0) + 1
    session["category_clicks"][category] = category_clicks
    
    total_clicks = session["total_clicks"]

# Уровень 3: Глобальная усталость (самый высокий приоритет)
    # Это не кликер - после 50 кликов
    if total_clicks > 50:
        await callback_query.answer("Это не кликер, угомонись!", show_alert=True)
        return # Прерываем выполнение
    # Пожалей мышку - после 40 кликов
    elif total_clicks > 40:
        await callback_query.answer("Хватит кликать, пожалей мышку.", show_alert=True)
        return # Прерываем выполнение

    # Уровень 2: Контекстная эмпатия
    REACTION_THRESHOLD = 15 # Поднимаем порог до 15 кликов по категории
    if category_clicks == REACTION_THRESHOLD:
        reaction_text = CATEGORY_REACTIONS.get(category, "У тебя какой-то особый интерес к этой категории...")
        await callback_query.answer(reaction_text, show_alert=True)
        session["category_clicks"][category] = 0 # Сбрасываем счетчик для этой категории
        logging.info(f"Для пользователя {user_id} сработала реакция на категорию '{category}'.")
    else:
        await callback_query.answer() # Убираем "часики", если никакой alert не сработал

    # Уровень 1: Логика рецептов
    recipes_db = KNOWLEDGE_BASE.get("recipes", [])
    candidates = [recipe for recipe in recipes_db if recipe.get("category") == category]
    
    if not candidates:
        await callback_query.message.answer(f"В категории «{category}» пока пусто.")
        session["category_clicks"][category] = 0
        return
        
    chosen_recipe = random.choice(candidates)
    
    seen_in_category = session["seen_recipes"].setdefault(category, set())

    if chosen_recipe['id'] in seen_in_category:
        await callback_query.message.answer(
            "Что, уже видел этот рецепт? Правильно, нечего на одни и те же кнопки постоянно давить. "
            "Напиши мне, что у тебя есть в холодильнике, и я предложу что-то более персональное, основанное на реальных данных, а не на слепом переборе."
        )
        seen_in_category.clear()
        session["category_clicks"][category] = 0
        logging.info(f"Пользователь {user_id} получил повтор в категории '{category}'. Память и счетчик сброшены.")
        return
        
    seen_in_category.add(chosen_recipe['id'])

    if len(seen_in_category) == len(candidates):
        await callback_query.message.answer(f"Кстати, ты только что посмотрел все рецепты в категории «{category}». Начинаем новый круг.")
        seen_in_category.clear()
        session["category_clicks"][category] = 0

    response_data = assemble_recipe(chosen_recipe) # assemble_recipe не возвращает reply_markup
    await send_recipe_response(callback_query.message, response_data)
        
    logging.info(f"Пользователю {user_id} был выдан рецепт '{chosen_recipe['id']}' по категории '{category}'. Кликов по этой категории: {category_clicks}. Всего кликов: {total_clicks}.")


@dp.callback_query(F.data.startswith("show_recipe_"))
async def process_show_recipe_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопок выбора рецепта из списка предложенных вариантов."""
    recipe_id = callback_query.data.split("_", 1)[1]
    
    await callback_query.answer() # Убираем "часики"
    
    recipes_db = KNOWLEDGE_BASE.get("recipes", [])
    chosen_recipe = None
    for recipe in recipes_db:
        if recipe.get("id") == recipe_id:
            chosen_recipe = recipe
            break

    if chosen_recipe:
        response_data = assemble_recipe(chosen_recipe) # Собираем рецепт и термины для него
        # send_recipe_response теперь умеет отправлять и текст, и кнопки терминов, и главное меню
        await send_recipe_response(callback_query.message, response_data)
        logging.info(f"Пользователь {callback_query.from_user.id} выбрал рецепт '{recipe_id}' из списка опций.")
    else:
        await callback_query.message.answer("Извини, этот рецепт куда-то пропал из моей памяти. Попробуй выбрать что-то другое.")
        # Если рецепт не найден, все равно отправляем главное меню
        menu_builder = get_main_menu_builder()
        await callback_query.message.answer("Чего желаешь теперь, экспериментатор?", reply_markup=menu_builder.as_markup())


# --- ЗАПУСК БОТА ---

async def main():
    try:
        load_knowledge_base()
    except Exception as e:
        logging.critical(f"Не удалось запустить бота: {e}", exc_info=True)
        return
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Шеф-садист (на атомном ядре) входит в чат...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.info("Запуск локальной версии...")
    asyncio.run(main())