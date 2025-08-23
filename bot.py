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
    get_all_cuisines,
    find_random_recipe_by_cuisine,
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
    "hot_dishes": ["горячее", "основное блюдо"], "soups": ["суп", "супы", "похлебка"],
    "pasta": ["паста", "макароны"], "salads": ["салат", "салаты"],
    "garnishes": ["гарнир", "гарниры"], "breakfasts": ["завтрак", "завтраки"],
    "sandwiches": ["бутерброд", "бутерброды", "сэндвич"], "fried_gold": ["жареное", "фритюр"],
    "baked_goods": ["выпечка", "пирог", "пироги"], "desserts": ["десерт", "десерты", "сладкое"],
    "sauces": ["соус", "соусы"], "drinks": ["напиток", "напитки", "пить"],
    "meats_curing": ["вяление", "посол", "вяленое мясо", "соленая рыба"],
    "veg_preserves": ["консервация", "соленья", "маринование", "заготовки"]
}

# СЛОВАРЬ ДЛЯ НАЗВАНИЙ КУХОНЬ
CUISINE_NAMES = {
    "american": "🇺🇸 Американская", "american_fusion": "🇺🇸 Фьюжн (США)", "american_italian": "🇺🇸🇮🇹 Итало-американская",
    "argentinian": "🇦🇷 Аргентинская", "asian_fusion": "🌏 Азиатский фьюжн", "balkan": "🇷🇸 Балканская",
    "bolivian": "🇧🇴 Боливийская", "brazilian": "🇧🇷 Бразильская", "caribbean": "🏝️ Карибская",
    "central_asian": "🇺🇿 Центральноазиатская", "chinese": "🇨🇳 Китайская", "colombian_venezuelan": "🇨🇴/🇻🇪 Колумбия/Венесуэла",
    "cuban": "🇨🇺 Кубинская", "czech": "🇨🇿 Чешская", "danish": "🇩🇰 Датская",
    "eastern_european": "🇪🇺 Восточноевропейская", "egyptian": "🇪🇬 Египетская", "european_classic": "🇪🇺 Европейская классика",
    "finnish": "🇫🇮 Финская", "french": "🇫🇷 Французская", "fusion": "🌀 Фьюжн",
    "georgian": "🇬🇪 Грузинская", "german": "🇩🇪 Немецкая", "greek": "🇬🇷 Греческая",
    "hungarian": "🇭🇺 Венгерская", "icelandic": "🇮🇸 Исландская", "international": "🌍 Интернациональная",
    "irish": "🇮🇪 Ирландская", "italian": "🇮🇹 Итальянская", "italian_fusion": "🇮🇹 Фьюжн (Италия)",
    "jamaican": "🇯🇲 Ямайская", "japanese": "🇯🇵 Японская", "jewish_soviet": "🕎 Еврейская (советская)",
    "mediterranean": "🌊 Средиземноморская", "mexican": "🇲🇽 Мексиканская", "middle_eastern": "🕌 Ближневосточная",
    "norwegian": "🇳🇴 Норвежская", "peruvian": "🇵🇪 Перуанская", "portuguese": "🇵🇹 Португальская",
    "russian": "🇷🇺 Русская", "russian_ukrainian": "🇷🇺/🇺🇦 Русская/Украинская", "scandinavian": "❄️ Скандинавская",
    "slovenian": "🇸🇮 Словенская", "soviet_union": "☭ СССР / Постсоветская", "spanish": "🇪🇸 Испанская",
    "swedish": "🇸🇪 Шведская", "tatar": "Татарская", "tex-mex": "🇺🇸/🇲🇽 Tex-Mex", "thai": "🇹🇭 Тайская"
}

# Словарь для контекстных реакций на категории
CATEGORY_REACTIONS = {
    "hot_dishes": "Только не съешь все сразу. Особенно на ночь."
}


# --- СЛУЖЕБНЫЕ ФУНКЦИИ ---

def get_user_session(user_id: int) -> dict:
    """Гарантированно получает или создает сессию для пользователя."""
    session = USER_SESSIONS.setdefault(user_id, {})
    session.setdefault("category_clicks", {})
    session.setdefault("seen_recipes", {})
    session.setdefault("cuisine_clicks", {})
    session.setdefault("seen_recipes_cuisine", {})
    session.setdefault("total_clicks", 0)
    session.setdefault("last_menu", "main")
    return session

def get_main_menu_builder() -> InlineKeyboardBuilder:
    """Собирает и возвращает билдер для главного меню (категорий)."""
    builder = InlineKeyboardBuilder()
    categories = [
        ("🔥 Горячее", "hot_dishes"), ("🥣 Супы", "soups"), ("🍝 Паста", "pasta"),
        ("🥗 Салаты", "salads"), ("🥔 Гарниры", "garnishes"), ("🍳 Завтраки", "breakfasts"),
        ("🥪 Бутерброды", "sandwiches"), ("✨ Жареное Золото", "fried_gold"), ("🥧 Выпечка", "baked_goods"),
        ("🍰 Десерты", "desserts"), ("🌶️ Соусы", "sauces"), ("🍸 Напитки", "drinks"),
        ("🥩 Вяление/Посол", "meats_curing"), ("🥒 Консервация", "veg_preserves")
    ]
    for text, category_key in categories:
        builder.add(InlineKeyboardButton(text=text, callback_data=f"category_{category_key}"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🌍 Кухни Мира", callback_data="show_cuisines"))
    return builder

def get_cuisines_menu_builder() -> InlineKeyboardBuilder:
    """Собирает и возвращает билдер для меню кухонь мира."""
    builder = InlineKeyboardBuilder()
    cuisines = get_all_cuisines()
    for cuisine_key in cuisines:
        cuisine_name = CUISINE_NAMES.get(cuisine_key, cuisine_key.capitalize())
        builder.add(InlineKeyboardButton(text=cuisine_name, callback_data=f"cuisine_{cuisine_key}"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="↩️ Главное Меню", callback_data="back_to_main"))
    return builder

async def send_recipe_response(message_or_callback: types.Message | types.CallbackQuery, response_data: dict):
    """Универсальная функция для отправки ответа с контекстной кнопкой 'Назад'."""
    user_id = message_or_callback.from_user.id
    target_message = message_or_callback if isinstance(message_or_callback, types.Message) else message_or_callback.message
    
    response_text = response_data["text"]
    found_terms = response_data.get("found_terms", [])
    reply_markup = response_data.get("reply_markup")

    if reply_markup:
        await target_message.answer(response_text, reply_markup=reply_markup)
        return

    builder = InlineKeyboardBuilder()
    if found_terms:
        terms_db = KNOWLEDGE_BASE.get("terms", {})
        for term_id in found_terms:
            term_name = terms_db.get(term_id, {}).get("aliases", ["Неизвестно"])[0]
            builder.add(InlineKeyboardButton(text=f"🤔 Что такое «{term_name}»?", callback_data=f"term_{term_id}"))
        builder.adjust(1)
    
    session = get_user_session(user_id)
    last_menu_context = session.get("last_menu", "main")
    
    if last_menu_context == 'cuisines':
        builder.row(InlineKeyboardButton(text="↩️ К списку кухонь", callback_data="show_cuisines"))
    else:
        builder.row(InlineKeyboardButton(text="↩️ К категориям", callback_data="back_to_main"))

    await target_message.answer(response_text, reply_markup=builder.as_markup())
    logging.info(f"Отправлен рецепт для {user_id} с контекстной кнопкой '{last_menu_context}'.")

async def send_related_recipes_suggestions(message_or_callback: types.Message | types.CallbackQuery, recipe: dict):
    related_ids = recipe.get("related_recipes")
    if not related_ids: return
    
    target_message = message_or_callback if isinstance(message_or_callback, types.Message) else message_or_callback.message
    builder = InlineKeyboardBuilder()
    found_related_recipes = 0
    for recipe_id in related_ids:
        related_recipe = find_recipe_by_id(recipe_id)
        if related_recipe:
            builder.add(InlineKeyboardButton(text=f"📜 {related_recipe['title']}", callback_data=f"show_recipe_{recipe_id}"))
            found_related_recipes += 1
    if found_related_recipes > 0:
        builder.adjust(1)
        await target_message.answer("Кстати, по этой теме у меня есть и другие протоколы:", reply_markup=builder.as_markup())
        logging.info(f"Пользователю {message_or_callback.from_user.id} предложены связанные рецепты.")

# --- ОБРАБОТЧИКИ ---

async def show_main_menu(message_or_callback: types.Message | types.CallbackQuery, text: str):
    user_id = message_or_callback.from_user.id
    session = get_user_session(user_id)
    session['last_menu'] = 'main'
    builder = get_main_menu_builder()
    target_message = message_or_callback if isinstance(message_or_callback, types.Message) else message_or_callback.message

    if isinstance(message_or_callback, types.CallbackQuery):
        if message_or_callback.message.text != text or message_or_callback.message.reply_markup != builder.as_markup():
            await target_message.edit_text(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    else:
        await target_message.answer(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    logging.info(f"Пользователю {user_id} показано главное меню.")

async def show_cuisines_menu(callback_query: types.CallbackQuery, text: str):
    user_id = callback_query.from_user.id
    session = get_user_session(user_id)
    session['last_menu'] = 'cuisines'
    builder = get_cuisines_menu_builder()
    await callback_query.message.edit_text(text, reply_markup=builder.as_markup())
    logging.info(f"Пользователю {user_id} показано меню кухонь.")

@dp.message(Command("start", "help"))
async def start_command(message: types.Message):
    USER_SESSIONS[message.from_user.id] = get_user_session(message.from_user.id)
    logging.info(f"Сессия для пользователя {message.from_user.id} сброшена.")
    start_text = (
        "Привет, я — Кира... (текст без изменений)"
    )
    await show_main_menu(message, start_text)
    logging.info(f"Пользователь {message.from_user.id} запустил бота.")

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback_query: types.CallbackQuery):
    await callback_query.answer()
    await show_main_menu(callback_query, "Выбор за тобой, Архитектор. Не заставляй меня ждать.")

@dp.callback_query(F.data == "show_cuisines")
async def show_cuisines_callback(callback_query: types.CallbackQuery):
    await callback_query.answer()
    await show_cuisines_menu(callback_query, "Выбери кулинарную доктрину, которую хочешь изучить.")

@dp.message()
async def handle_ingredients(message: types.Message):
    if not message.text or message.text.startswith('/'): return
    user_id = message.from_user.id
    user_query = message.text.lower().strip()
    logging.info(f"Получен ручной запрос от {user_id}: '{user_query}'")
    get_user_session(user_id)['last_menu'] = 'main'

    intended_recipe = find_recipe_by_intention(user_query)
    if intended_recipe:
        response_data = assemble_recipe(intended_recipe)
        await send_recipe_response(message, response_data)
        await send_related_recipes_suggestions(message, intended_recipe)
        return

    found_category = None
    for category_key, aliases in CATEGORY_ALIASES.items():
        if user_query in aliases:
            found_category = category_key
            break
    
    if found_category:
        random_recipe = find_random_recipe_by_category(found_category)
        if random_recipe:
            response_data = assemble_recipe(random_recipe)
            await send_recipe_response(message, response_data)
            await send_related_recipes_suggestions(message, random_recipe)
        else:
            await message.answer(f"В категории «{found_category}» пока пусто.")
        return

    response_data = synthesize_response(user_query)
    await send_recipe_response(message, response_data)

@dp.callback_query(F.data.startswith("term_"))
async def process_term_callback(callback_query: types.CallbackQuery):
    term_id = callback_query.data.split("_", 1)[1]
    terms_db = KNOWLEDGE_BASE.get("terms", {})
    term_data = terms_db.get(term_id)
    await callback_query.answer()
    if term_data:
        explanation = term_data.get("explanation", "Объяснение потерялось...")
        sarcastic_comment = random.choice(term_data.get("sarcastic_comments", ["..."]))
        term_name = term_data.get("aliases", ["Неизвестно"])[0].capitalize()
        response_text = (f"<b>🎓 Ликбез по теме «{term_name}»</b>\n\n{explanation}\n\n<i><b>Мой комментарий:</b> {sarcastic_comment}</i>")
        await callback_query.message.answer(response_text)
    else:
        await callback_query.message.answer("Упс... Я забыла, что это значит. Бывает.")

@dp.callback_query(F.data.startswith("cuisine_"))
async def process_cuisine_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    cuisine = callback_query.data.split("_", 1)[1]
    await callback_query.answer()
    session = get_user_session(user_id)
    session['last_menu'] = 'cuisines'

    recipes_in_cuisine = [r for r in KNOWLEDGE_BASE.get("recipes", []) if r.get("cuisine") == cuisine]
    if not recipes_in_cuisine:
        await callback_query.message.edit_text(f"В доктрине «{CUISINE_NAMES.get(cuisine, cuisine)}» пока пусто. Я это запомню.")
        return

    seen_in_cuisine = session["seen_recipes_cuisine"].setdefault(cuisine, set())
    available_recipes = [r for r in recipes_in_cuisine if r['id'] not in seen_in_cuisine]
    
    if not available_recipes:
        await callback_query.message.answer(f"Кстати, ты только что изучил все протоколы доктрины «{CUISINE_NAMES.get(cuisine, cuisine)}». Начинаем новый цикл познания.")
        seen_in_cuisine.clear()
        available_recipes = recipes_in_cuisine

    chosen_recipe = random.choice(available_recipes)
    seen_in_cuisine.add(chosen_recipe['id'])

    response_data = assemble_recipe(chosen_recipe)
    await send_recipe_response(callback_query, response_data)
    await send_related_recipes_suggestions(callback_query, chosen_recipe)

@dp.callback_query(F.data.startswith("category_"))
async def process_category_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    category = callback_query.data.split("_", 1)[1]
    session = get_user_session(user_id)
    session['last_menu'] = 'main'
    await callback_query.answer()

    recipes_db = KNOWLEDGE_BASE.get("recipes", [])
    candidates = [recipe for recipe in recipes_db if recipe.get("category") == category]
    
    if not candidates:
        await callback_query.message.edit_text(f"В категории «{category}» пока пусто.")
        return
        
    seen_in_category = session["seen_recipes"].setdefault(category, set())
    available_recipes = [r for r in candidates if r['id'] not in seen_in_category]

    if not available_recipes:
        await callback_query.message.answer(f"Кстати, ты только что посмотрел все рецепты в категории «{category}». Начинаем новый круг.")
        seen_in_category.clear()
        available_recipes = candidates

    chosen_recipe = random.choice(available_recipes)
    seen_in_category.add(chosen_recipe['id'])

    response_data = assemble_recipe(chosen_recipe)
    await send_recipe_response(callback_query, response_data)
    await send_related_recipes_suggestions(callback_query, chosen_recipe)

@dp.callback_query(F.data.startswith("show_recipe_"))
async def process_show_recipe_callback(callback_query: types.CallbackQuery):
    await callback_query.answer()
    recipe_id = callback_query.data.removeprefix("show_recipe_")
    chosen_recipe = find_recipe_by_id(recipe_id)

    if chosen_recipe:
        response_data = assemble_recipe(chosen_recipe)
        await send_recipe_response(callback_query, response_data)
        await send_related_recipes_suggestions(callback_query, chosen_recipe)
    else:
        logging.error(f"КРИТИЧЕСКАЯ ОШИБКА: Не найден рецепт с ID '{recipe_id}'!")
        await callback_query.message.answer("Извини, этот рецепт куда-то пропал из моей памяти.")
        await show_main_menu(callback_query, "Попробуй выбрать что-то другое.")

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