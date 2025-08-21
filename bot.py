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
    # --- НОВЫЕ ИМПОРТЫ ---
    get_all_cuisines,
    find_random_recipe_by_cuisine,
    # -----------------------
    assemble_recipe,
    find_recipe_by_intention,
    find_recipe_by_id
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

# СЛОВАРЬ ДЛЯ РАСПОЗНАВАНИЯ КАТЕГОРИЙ В ТЕКСТЕ
CATEGORY_ALIASES = {
    "hot_dishes": ["горячее", "основное блюдо"],
    "soups": ["суп", "супы", "похлебка"],
    "pasta": ["паста", "макароны"],
    "salads": ["салат", "салаты"],
    "garnishes": ["гарнир", "гарниры"],
    "breakfasts": ["завтрак", "завтраки"],
    "sandwiches": ["бутерброд", "бутерброды", "сэндвич"],
    "fried_gold": ["жареное", "фритюр"],
    "baked_goods": ["выпечка", "пирог", "пироги"],
    "desserts": ["десерт", "десерты", "сладкое"],
    "sauces": ["соус", "соусы"],
    "drinks": ["напиток", "напитки", "пить"],
    "meats_curing": ["вяление", "посол", "вяленое мясо", "соленая рыба"],
    "veg_preserves": ["консервация", "соленья", "маринование", "заготовки"]
}

# --- НОВЫЙ СЛОВАРЬ ДЛЯ НАЗВАНИЙ КУХОНЬ ---
CUISINE_NAMES = {
    "american": "🇺🇸 Американская",
    "american_fusion": "🇺🇸 Фьюжн (США)",
    "american_italian": "🇺🇸🇮🇹 Итало-американская",
    "asian_fusion": "🌏 Азиатский фьюжн",
    "balkan": "🇷🇸 Балканская",
    "brazilian": "🇧🇷 Бразильская",
    "central_asian": "🇺🇿 Центральноазиатская",
    "chinese": "🇨🇳 Китайская",
    "czech": "🇨🇿 Чешская",
    "danish": "🇩🇰 Датская",
    "eastern_european": "🇪🇺 Восточноевропейская",
    "egyptian": "🇪🇬 Египетская",
    "european_classic": "🇪🇺 Европейская классика",
    "finnish": "🇫🇮 Финская",
    "french": "🇫🇷 Французская",
    "fusion": "🌀 Фьюжн",
    "georgian": "🇬🇪 Грузинская",
    "german": "🇩🇪 Немецкая",
    "greek": "🇬🇷 Греческая",
    "hungarian": "🇭🇺 Венгерская",
    "icelandic": "🇮🇸 Исландская",
    "international": "🌍 Интернациональная",
    "irish": "🇮🇪 Ирландская",
    "italian": "🇮🇹 Итальянская",
    "italian_fusion": "🇮🇹 Фьюжн (Италия)",
    "japanese": "🇯🇵 Японская",
    "jewish_soviet": "🕎 Еврейская (советская)",
    "mediterranean": "🌊 Средиземноморская",
    "middle_eastern": "🕌 Ближневосточная",
    "norwegian": "🇳🇴 Норвежская",
    "portuguese": "🇵🇹 Португальская",
    "russian": "🇷🇺 Русская",
    "russian_ukrainian": "🇷🇺🇺🇦 Русская/Украинская",
    "scandinavian": "❄️ Скандинавская",
    "slovenian": "🇸🇮 Словенская",
    "soviet_union": "☭ СССР / Постсоветская",
    "spanish": "🇪🇸 Испанская",
    "swedish": "🇸🇪 Шведская",
    "tatar": " Tatar",
    "thai": "🇹🇭 Тайская",
    "ukrainian": "🇺🇦 Украинская",
    "wild_west": "🤠 Дикий Запад"
}

# Словарь для контекстных реакций на категории
CATEGORY_REACTIONS = {
    # ... (остается без изменений)
}


# --- СЛУЖЕБНЫЕ ФУНКЦИИ ---

def get_user_session(user_id: int) -> dict:
    """Гарантированно получает или создает сессию для пользователя."""
    session = USER_SESSIONS.setdefault(user_id, {})
    session.setdefault("category_clicks", {})
    session.setdefault("seen_recipes", {})
    # --- НОВЫЕ ПОЛЯ ДЛЯ СЕССИИ ---
    session.setdefault("cuisine_clicks", {})
    session.setdefault("seen_recipes_cuisine", {})
    # -------------------------------
    session.setdefault("total_clicks", 0)
    return session

def get_main_menu_builder() -> InlineKeyboardBuilder:
    """Собирает и возвращает билдер для главного меню."""
    builder = InlineKeyboardBuilder()
    categories = [
        ("🔥 Горячее", "hot_dishes"),
        ("🥣 Супы", "soups"),
        ("🍝 Паста", "pasta"),
        ("🥗 Салаты", "salads"),
        ("🥔 Гарниры", "garnishes"),
        ("🍳 Завтраки", "breakfasts"),
        ("🥪 Бутерброды", "sandwiches"),
        ("✨ Жареное Золото", "fried_gold"),
        ("🥧 Выпечка", "baked_goods"),
        ("🍰 Десерты", "desserts"),
        ("🌶️ Соусы", "sauces"),
        ("🍸 Напитки", "drinks"),
        ("🥩 Вяление/Посол", "meats_curing"),
        ("🥒 Консервация", "veg_preserves")
    ]
    for text, category_key in categories:
        builder.add(InlineKeyboardButton(text=text, callback_data=f"category_{category_key}"))

    builder.adjust(2)
    # --- НОВАЯ КНОПКА ---
    builder.row(InlineKeyboardButton(text="🌍 Кухни Мира", callback_data="show_cuisines"))
    # ----------------------
    return builder

# ... (функции send_recipe_response и send_related_recipes_suggestions остаются без изменений) ...


# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start", "help"))
# ... (остается без изменений) ...

@dp.message()
# ... (остается без изменений) ...

@dp.callback_query(F.data.startswith("term_"))
# ... (остается без изменений) ...

# --- НОВЫЙ ОБРАБОТЧИК ДЛЯ ПОКАЗА КУХОНЬ ---
@dp.callback_query(F.data == "show_cuisines")
async def show_cuisines_callback(callback_query: types.CallbackQuery):
    """Отображает клавиатуру со списком доступных кухонь мира."""
    await callback_query.answer()
    
    cuisines = get_all_cuisines()
    if not cuisines:
        await callback_query.message.edit_text("Пока что я не каталогизировала ни одной кухни мира. Странно.")
        return

    builder = InlineKeyboardBuilder()
    for cuisine_key in cuisines:
        # Используем наш словарь для красивых названий
        cuisine_name = CUISINE_NAMES.get(cuisine_key, cuisine_key.capitalize())
        builder.add(InlineKeyboardButton(text=cuisine_name, callback_data=f"cuisine_{cuisine_key}"))
    
    builder.adjust(2)
    
    await callback_query.message.edit_text(
        "Выбери кулинарную доктрину, которую хочешь изучить. Но помни: путь к знанию лежит через дисциплину.",
        reply_markup=builder.as_markup()
    )
    logging.info(f"Пользователю {callback_query.from_user.id} показан список кухонь.")

# --- НОВЫЙ ОБРАБОТЧИК ДЛЯ ВЫБОРА КОНКРЕТНОЙ КУХНИ ---
@dp.callback_query(F.data.startswith("cuisine_"))
async def process_cuisine_callback(callback_query: types.CallbackQuery):
    """Обрабатывает выбор кухни и выдает случайный рецепт из нее."""
    user_id = callback_query.from_user.id
    cuisine = callback_query.data.split("_", 1)[1]
    
    await callback_query.answer()
    
    session = get_user_session(user_id)
    
    # Логика против закликивания (аналогично категориям)
    session["total_clicks"] += 1
    cuisine_clicks = session["cuisine_clicks"].get(cuisine, 0) + 1
    session["cuisine_clicks"][cuisine] = cuisine_clicks
    
    chosen_recipe = find_random_recipe_by_cuisine(cuisine)
    
    if not chosen_recipe:
        await callback_query.message.answer(f"В доктрине «{CUISINE_NAMES.get(cuisine, cuisine)}» пока пусто. Я это запомню.")
        session["cuisine_clicks"][cuisine] = 0
        return

    # Логика отслеживания просмотренных рецептов (аналогично категориям)
    seen_in_cuisine = session["seen_recipes_cuisine"].setdefault(cuisine, set())
    
    # Проверка, не является ли это последним непросмотренным рецептом
    recipes_in_cuisine = [r for r in KNOWLEDGE_BASE.get("recipes", []) if r.get("cuisine") == cuisine]

    if chosen_recipe['id'] in seen_in_cuisine and len(seen_in_cuisine) < len(recipes_in_cuisine):
        # Если рецепт уже видели, но есть и другие, ищем новый
        available_recipes = [r for r in recipes_in_cuisine if r['id'] not in seen_in_cuisine]
        if available_recipes:
            chosen_recipe = random.choice(available_recipes)
        # Если вдруг все доступные уже видели (маловероятно, но возможно), сбрасываем
        else:
            seen_in_cuisine.clear()

    seen_in_cuisine.add(chosen_recipe['id'])

    if len(seen_in_cuisine) == len(recipes_in_cuisine):
        await callback_query.message.answer(f"Кстати, ты только что изучил все протоколы доктрины «{CUISINE_NAMES.get(cuisine, cuisine)}». Начинаем новый цикл познания.")
        seen_in_cuisine.clear()
        session["cuisine_clicks"][cuisine] = 0

    response_data = assemble_recipe(chosen_recipe)
    await send_recipe_response(callback_query.message, response_data)
    await send_related_recipes_suggestions(callback_query.message, chosen_recipe)
        
    logging.info(f"Пользователю {user_id} был выдан рецепт '{chosen_recipe['id']}' по кухне '{cuisine}'.")

@dp.callback_query(F.data.startswith("category_"))
async def process_category_callback(callback_query: types.CallbackQuery):
    """V3.1 - Реализует 'Многоуровневую Агрессию'."""
    user_id = callback_query.from_user.id
    category = callback_query.data.split("_", 1)[1]
    
    session = get_user_session(user_id)
    
    session["total_clicks"] += 1
    category_clicks = session["category_clicks"].get(category, 0) + 1
    session["category_clicks"][category] = category_clicks
    total_clicks = session["total_clicks"]

    if total_clicks > 50:
        await callback_query.answer("Это не кликер, угомонись!", show_alert=True)
        return
    elif total_clicks > 40:
        await callback_query.answer("Хватит кликать, пожалей мышку.", show_alert=True)
        return

    REACTION_THRESHOLD = 15
    if category_clicks == REACTION_THRESHOLD:
        reaction_text = CATEGORY_REACTIONS.get(category, "У тебя какой-то особый интерес к этой категории...")
        await callback_query.answer(reaction_text, show_alert=True)
        session["category_clicks"][category] = 0
        logging.info(f"Для пользователя {user_id} сработала реакция на категорию '{category}'.")
    else:
        await callback_query.answer()

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

    response_data = assemble_recipe(chosen_recipe)
    await send_recipe_response(callback_query.message, response_data)
    await send_related_recipes_suggestions(callback_query.message, chosen_recipe)
        
    logging.info(f"Пользователю {user_id} был выдан рецепт '{chosen_recipe['id']}' по категории '{category}'. Кликов по этой категории: {category_clicks}. Всего кликов: {total_clicks}.")


@dp.callback_query(F.data.startswith("show_recipe_"))
async def process_show_recipe_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопок выбора рецепта из списка предложенных вариантов. V2.0 - Исправлена логика парсинга ID."""
    
    recipe_id = callback_query.data.removeprefix("show_recipe_")
    
    await callback_query.answer()
    
    chosen_recipe = find_recipe_by_id(recipe_id)

    if chosen_recipe:
        response_data = assemble_recipe(chosen_recipe)
        await send_recipe_response(callback_query.message, response_data)
        await send_related_recipes_suggestions(callback_query.message, chosen_recipe)
        logging.info(f"Пользователь {callback_query.from_user.id} выбрал рецепт '{recipe_id}' из списка опций.")
    else:
        logging.error(f"КРИТИЧЕСКАЯ ОШИБКА: Не найден рецепт с ID '{recipe_id}', хотя на него была сгенерирована ссылка!")
        await callback_query.message.answer("Извини, этот рецепт куда-то пропал из моей памяти. Попробуй выбрать что-то другое.")
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