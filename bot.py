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

# СЛОВАРЬ ДЛЯ НАЗВАНИЙ КУХОНЬ
CUISINE_NAMES = {
    "american": "🇺🇸 Американская",
    "american_fusion": "🇺🇸 Фьюжн (США)",
    "american_italian": "🇺🇸🇮🇹 Итало-американская",
    "argentinian": "🇦🇷 Аргентинская",
    "asian_fusion": "🌏 Азиатский фьюжн",
    "balkan": "🇷🇸 Балканская",
    "bolivian": "🇧🇴 Боливийская",
    "brazilian": "🇧🇷 Бразильская",
    "caribbean": "🏝️ Карибская",
    "central_asian": "🇺🇿 Центральноазиатская",
    "chinese": "🇨🇳 Китайская",
    "colombian_venezuelan": "🇨🇴/🇻🇪 Колумбия/Венесуэла",
    "cuban": "🇨🇺 Кубинская",
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
    "jamaican": "🇯🇲 Ямайская",
    "japanese": "🇯🇵 Японская",
    "jewish_soviet": "🕎 Еврейская (советская)",
    "mediterranean": "🌊 Средиземноморская",
    "mexican": "🇲🇽 Мексиканская",
    "middle_eastern": "🕌 Ближневосточная",
    "norwegian": "🇳🇴 Норвежская",
    "peruvian": "🇵🇪 Перуанская",
    "portuguese": "🇵🇹 Португальская",
    "russian": "🇷🇺 Русская",
    "russian_ukrainian": "🇷🇺/🇺🇦 Русская/Украинская",
    "scandinavian": "❄️ Скандинавская",
    "slovenian": "🇸🇮 Словенская",
    "soviet_union": "☭ СССР / Постсоветская",
    "spanish": "🇪🇸 Испанская",
    "swedish": "🇸🇪 Шведская",
    "tatar": "Татарская",
    "tex-mex": "🇺🇸/🇲🇽 Tex-Mex",
    "thai": "🇹🇭 Тайская",
    "wild_west": "🤠 Дикий Запад"
}

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
    "fried_gold": "А, это самое вредное... и самое вкусное! Смотри не сожги, а то будет не золото, а уголь.",
    "drinks": "Напитки? Хорошо. Главное — чтобы потом не пришлось вызывать 'Скорую помощь'. Ищи, что тебе по вкусу.",
    "baked_goods": "Выпечка... Чудесно. Это то, что делает твою жизнь чуть слаще. И твою талию — чуть шире. Выбирай осторожно.",
    "meats_curing": "А, протоколы медленной алхимии. Здесь спешка — твой главный враг. Терпение, Архитектор.",
    "veg_preserves": "Решил запастись на зиму? Или просто любишь хруст? В любом случае, это — игра вдолгую."
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
    builder.row(InlineKeyboardButton(text="🌍 Кухни Мира", callback_data="show_cuisines"))
    return builder

async def send_recipe_response(message: types.Message, response_data: dict):
    """Универсальная функция для отправки ответа."""
    response_text = response_data["text"]
    found_terms = response_data.get("found_terms", [])
    reply_markup = response_data.get("reply_markup")

    if reply_markup:
        await message.answer(response_text, reply_markup=reply_markup)
    elif found_terms:
        builder = InlineKeyboardBuilder()
        terms_db = KNOWLEDGE_BASE.get("terms", {})
        for term_id in found_terms:
            term_name = terms_db.get(term_id, {}).get("aliases", ["Неизвестно"])[0]
            builder.add(InlineKeyboardButton(text=f"🤔 Что такое «{term_name}»?", callback_data=f"term_{term_id}"))
        builder.adjust(1)
        await message.answer(response_text, reply_markup=builder.as_markup())
    else:
        await message.answer(response_text)

    logging.info(f"Отправлен ответ для {message.from_user.id}.")

    menu_builder = get_main_menu_builder()
    await message.answer("Чего желаешь теперь, экспериментатор?", reply_markup=menu_builder.as_markup())

async def send_related_recipes_suggestions(message: types.Message, recipe: dict):
    """
    Проверяет, есть ли у рецепта связанные протоколы, и отправляет
    сообщение с кнопками-предложениями, если они найдены.
    """
    related_ids = recipe.get("related_recipes")
    if not related_ids:
        return

    builder = InlineKeyboardBuilder()
    found_related_recipes = 0
    for recipe_id in related_ids:
        related_recipe = find_recipe_by_id(recipe_id)
        if related_recipe:
            builder.add(InlineKeyboardButton(
                text=f"📜 {related_recipe['title']}",
                callback_data=f"show_recipe_{recipe_id}"
            ))
            found_related_recipes += 1

    if found_related_recipes > 0:
        builder.adjust(1)
        await message.answer(
            "Кстати, по этой теме у меня есть и другие протоколы:",
            reply_markup=builder.as_markup()
        )
        logging.info(f"Пользователю {message.from_user.id} предложены связанные рецепты для '{recipe['id']}'.")

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start", "help"))
async def start_command(message: types.Message):
    """Сбрасывает сессию и выдает клавиатуру категорий."""
    user_id = message.from_user.id
    USER_SESSIONS[user_id] = get_user_session(user_id) # Гарантируем создание всех ключей
    logging.info(f"Сессия для пользователя {user_id} сброшена.")

    builder = get_main_menu_builder()
    start_text = (
        "Привет, я — Кира, рыжий ураган, и мы с тобой на моей кухне. Я тебе рада, ты тут гость, но давай будем честны: ты пришел сюда (или пришла) за рецептом и, возможно, за порцией моего фирменного сарказма.\n\n"
        "Что ты можешь прямо сейчас:\n\n"
        "1. Потыкаться в кнопочки и возможно, найти нужный рецепт. У нас их много, пробуй, но не удивляйся повторам и едким комментариям.\n"
        "2. Написать, что ты хочешь приготовить. Пиццу, котлеты, бутерброд, яичницу — я подскажу. А если осмелишься, у меня есть рецепты настоящей карбонары, чизкейка — только спроси.\n"
        "3. Просто напиши, что нашел (или нашла) в холодильнике. Осуждать не буду, и даже подскажу, что еще может потребоваться.\n\n"
        "Кстати, если хочешь погрузиться глубже в философию кулинарного доминирования и не пропустить новые главы моей мудрости, загляни в мой канал 'Дневник повара-садиста': <a href='https://t.me/dnevnik_povara_sadista'>@DnevnikPovaraSadista</a>.\n\n"
        "Пробуй. Как сказал Гомер Симпсон, \"я пришел сюда, чтобы меня пичкали таблетками и били током, а не унижали!\". Так вот, унижать не буду. Насчет остального — не уверена\n\n"
        "Шеф Кира"
    )
    await message.answer(start_text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    logging.info(f"Пользователь {user_id} запустил бота и получил клавиатуру категорий.")

@dp.message()
async def handle_ingredients(message: types.Message):
    """
    Обработчик ручного ввода.
    1. Ищет по намерению.
    2. Ищет по названию категории.
    3. Ищет по ингредиентам.
    """
    if not message.text or message.text.startswith('/'):
        return

    user_query = message.text.lower().strip()
    logging.info(f"Получен ручной запрос от {message.from_user.id}: '{user_query}'")

    intended_recipe = find_recipe_by_intention(user_query)
    if intended_recipe:
        logging.info(f"Найдено намерение! Рецепт: {intended_recipe['id']}")
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
        logging.info(f"Запрос '{user_query}' распознан как категория '{found_category}'. Выдаю случайный рецепт.")
        random_recipe = find_random_recipe_by_category(found_category)
        if random_recipe:
            response_data = assemble_recipe(random_recipe)
            await send_recipe_response(message, response_data)
            await send_related_recipes_suggestions(message, random_recipe)
        else:
            await message.answer(f"В категории «{found_category}» пока пусто, но я это запомню.")
            menu_builder = get_main_menu_builder()
            await message.answer("Чего желаешь теперь, экспериментатор?", reply_markup=menu_builder.as_markup())
        return

    logging.info("Намерение или категория не найдены. Запускаю поиск по ингредиентам...")
    response_data = synthesize_response(user_query)
    await send_recipe_response(message, response_data)

@dp.callback_query(F.data.startswith("term_"))
async def process_term_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопок с терминами."""
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
    logging.info(f"Пользователь {callback_query.from_user.id} запросил объяснение для термина '{term_id}'.")

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
        cuisine_name = CUISINE_NAMES.get(cuisine_key, cuisine_key.capitalize())
        builder.add(InlineKeyboardButton(text=cuisine_name, callback_data=f"cuisine_{cuisine_key}"))
    
    builder.adjust(2)
    
    await callback_query.message.edit_text(
        "Выбери кулинарную доктрину, которую хочешь изучить. Но помни: путь к знанию лежит через дисциплину.",
        reply_markup=builder.as_markup()
    )
    logging.info(f"Пользователю {callback_query.from_user.id} показан список кухонь.")

@dp.callback_query(F.data.startswith("cuisine_"))
async def process_cuisine_callback(callback_query: types.CallbackQuery):
    """Обрабатывает выбор кухни и выдает случайный рецепт из нее."""
    user_id = callback_query.from_user.id
    cuisine = callback_query.data.split("_", 1)[1]
    
    await callback_query.answer()
    
    session = get_user_session(user_id)
    
    session["total_clicks"] += 1
    cuisine_clicks = session["cuisine_clicks"].get(cuisine, 0) + 1
    session["cuisine_clicks"][cuisine] = cuisine_clicks
    
    recipes_in_cuisine = [r for r in KNOWLEDGE_BASE.get("recipes", []) if r.get("cuisine") == cuisine]
    if not recipes_in_cuisine:
        await callback_query.message.answer(f"В доктрине «{CUISINE_NAMES.get(cuisine, cuisine)}» пока пусто. Я это запомню.")
        session["cuisine_clicks"][cuisine] = 0
        return

    seen_in_cuisine = session["seen_recipes_cuisine"].setdefault(cuisine, set())
    available_recipes = [r for r in recipes_in_cuisine if r['id'] not in seen_in_cuisine]
    
    if not available_recipes:
        await callback_query.message.answer(f"Кстати, ты только что изучил все протоколы доктрины «{CUISINE_NAMES.get(cuisine, cuisine)}». Начинаем новый цикл познания.")
        seen_in_cuisine.clear()
        session["cuisine_clicks"][cuisine] = 0
        available_recipes = recipes_in_cuisine

    chosen_recipe = random.choice(available_recipes)
    seen_in_cuisine.add(chosen_recipe['id'])

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
        
    seen_in_category = session["seen_recipes"].setdefault(category, set())
    available_recipes = [r for r in candidates if r['id'] not in seen_in_category]

    if not available_recipes:
        await callback_query.message.answer(f"Кстати, ты только что посмотрел все рецепты в категории «{category}». Начинаем новый круг.")
        seen_in_category.clear()
        session["category_clicks"][category] = 0
        available_recipes = candidates

    chosen_recipe = random.choice(available_recipes)
    seen_in_category.add(chosen_recipe['id'])

    response_data = assemble_recipe(chosen_recipe)
    await send_recipe_response(callback_query.message, response_data)
    await send_related_recipes_suggestions(callback_query.message, chosen_recipe)
        
    logging.info(f"Пользователю {user_id} был выдан рецепт '{chosen_recipe['id']}' по категории '{category}'. Кликов по этой категории: {category_clicks}. Всего кликов: {total_clicks}.")


@dp.callback_query(F.data.startswith("show_recipe_"))
async def process_show_recipe_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопок выбора рецепта из списка предложенных вариантов."""
    
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