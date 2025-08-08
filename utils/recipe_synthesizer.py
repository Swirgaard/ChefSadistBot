import json
import random
import re
import logging
import os
from typing import Dict, List, Optional, Any

KNOWLEDGE_BASE: Dict[str, Any] = {}

def load_knowledge_base():
    """Загружает все JSON файлы из папки data, агрегируя модульные базы."""
    global KNOWLEDGE_BASE
    data_path = "data/"
    try:
        KNOWLEDGE_BASE["ingredients"] = {}
        ingredient_files = [f for f in os.listdir(data_path) if f.endswith("_ingredients.json")]
        for filename in ingredient_files:
            with open(os.path.join(data_path, filename), "r", encoding="utf-8") as f:
                KNOWLEDGE_BASE["ingredients"].update(json.load(f))

        KNOWLEDGE_BASE["recipes"] = []
        recipe_files = [f for f in os.listdir(data_path) if f.endswith("_recipes.json")]
        for filename in recipe_files:
            with open(os.path.join(data_path, filename), "r", encoding="utf-8") as f:
                KNOWLEDGE_BASE["recipes"].extend(json.load(f))
        
        with open(os.path.join(data_path, "phrases.json"), "r", encoding="utf-8") as f:
            KNOWLEDGE_BASE["phrases"] = json.load(f)

        with open(os.path.join(data_path, "terms.json"), "r", encoding="utf-8") as f:
            terms_list = json.load(f)
            KNOWLEDGE_BASE["terms"] = {term["term_id"]: term for term in terms_list}
        
        if not KNOWLEDGE_BASE["recipes"]:
             raise FileNotFoundError("Не найдено ни одного файла с рецептами")
        if not KNOWLEDGE_BASE["ingredients"]:
             raise FileNotFoundError("Не найдено ни одного файла с ингредиентами")
        if not KNOWLEDGE_BASE["terms"]:
             logging.warning("Файл terms.json пуст или не найден.")

        logging.info("База знаний успешно загружена и агрегирована.")
    except Exception as e:
        logging.critical(f"Критическая ошибка загрузки базы знаний: {e}", exc_info=True)
        raise

# Новая вспомогательная функция для нормализации текста
def normalize_text(text: str) -> str:
    """Нормализует текст: переводит в нижний регистр, заменяет 'ё' на 'е'."""
    return text.lower().replace('ё', 'е')

def parse_user_query(text: str) -> List[str]:
    """Извлекает и нормализует ключи ингредиентов из запроса пользователя,
    приоритизируя многословные алиасы и предотвращая некорректные совпадения."""
    
    cleaned_text = normalize_text(text)
    found_keys = set()
    ingredients_db = KNOWLEDGE_BASE.get("ingredients", {})
    
    # Шаг 1: Создаем список всех возможных поисковых терминов
    # в формате (normalized_alias, original_ingredient_key)
    all_search_terms = []
    for key, data in ingredients_db.items():
        aliases = data.get("aliases", [])
        aliases.append(key) # Добавляем сам ключ как поисковый термин
        for alias in aliases:
            all_search_terms.append((normalize_text(alias), key))
    
    # Шаг 2: Сортируем список от самых длинных алиасов к самым коротким
    # Это гарантирует, что "сливочное масло" будет проверено раньше, чем "масло"
    all_search_terms.sort(key=lambda x: len(x[0]), reverse=True)
    
    # Шаг 3: Проходим по отсортированным терминам и ищем совпадения.
    # Используем временный текст, из которого будем "удалять" найденные фразы,
    # чтобы избежать повторных или неправильных совпадений.
    # Добавляем пробелы в начале и конце, чтобы '\b' работал корректно для начала/конца строки.
    temp_text = " " + cleaned_text + " " 

    for term_alias, ingredient_key in all_search_terms:
        # Строим паттерн для поиска целого слова или фразы (с пробелами по краям)
        # re.escape() экранирует специальные символы в term_alias
        pattern = r'\b' + re.escape(term_alias) + r'\b'
        
        match = re.search(pattern, temp_text)
        if match:
            found_keys.add(ingredient_key)
            # "Потребляем" найденную часть строки, заменяя ее на пробелы.
            # Это предотвращает повторное нахождение более коротких алиасов
            # внутри уже найденного (например, "масло" внутри "сливочное масло", если они для РАЗНЫХ ингредиентов).
            start_index, end_index = match.span()
            temp_text = temp_text[:start_index] + ' ' * (end_index - start_index) + temp_text[end_index:]
            
    logging.info(f"Парсер нашел следующие ключи: {list(found_keys)}")
    return list(found_keys)

def find_matching_recipe(found_ingredients_keys: List[str]) -> Dict[str, Any]:
    """
    Находит НАИБОЛЕЕ подходящие рецепты, анализируя ВСЕ варианты
    и выбирая лучшие по новой метрике релевантности.
    Возвращает список кандидатов или лучший идеальный матч.
    """
    recipes_db = KNOWLEDGE_BASE.get("recipes", [])
    found_set = set(found_ingredients_keys)
    
    perfect_matches = []
    partial_candidates = [] # Список для всех частичных совпадений, которые мы будем анализировать

    for recipe in recipes_db:
        trigger_keys = set(recipe.get("trigger_keys", []))
        if not trigger_keys:
            continue

        matching_keys = found_set.intersection(trigger_keys)
        missing_keys = trigger_keys - found_set
        excess_keys = found_set - trigger_keys # Ингредиенты пользователя, которые не нужны рецепту
        
        # Если все ключи на месте — это идеальный кандидат
        if not missing_keys:
            perfect_matches.append(recipe)
            continue

        # Если есть хотя бы одно совпадение, но не все — это частичный кандидат
        # Добавляем условие, что не хватать должно не более 2-х ингредиентов (старое правило)
        if matching_keys and len(missing_keys) <= 2:
            # Новая метрика релевантности:
            # Приоритет:
            # 1. Больше совпадений (match_count)
            # 2. Меньше недостающих ингредиентов (len(missing_keys))
            # 3. Меньше лишних ингредиентов (len(excess_keys))
            # 4. Выше приоритет рецепта (recipe.get("priority"))
            relevance_score = (
                len(matching_keys),
                -len(missing_keys), # Минусы, потому что мы хотим МЕНЬШЕ недостающих
                -len(excess_keys),  # Минусы, потому что мы хотим МЕНЬШЕ лишних
                recipe.get("priority", 0)
            )

            partial_candidates.append({
                "recipe": recipe,
                "match_count": len(matching_keys),
                "missing_keys": list(missing_keys),
                "excess_keys": list(excess_keys), # Добавлено для отладки
                "score": relevance_score # Новое поле для сортировки
            })

    # Сначала всегда отдаем предпочтение идеальным совпадениям
    if perfect_matches:
        best_candidate = sorted(perfect_matches, key=lambda r: r.get("priority", 0), reverse=True)[0]
        logging.info(f"Найдено идеальное совпадение: '{best_candidate.get('id')}'")
        return {"status": "perfect", "recipe": best_candidate, "options": [], "missing_keys": []}

    # Если идеальных нет, ищем ЛУЧШЕЕ из частичных или несколько лучших
    if partial_candidates:
        # Сортируем по новой метрике релевантности
        partial_candidates.sort(key=lambda p: p["score"], reverse=True)
        
        # Возвращаем до 3-х лучших вариантов, если они достаточно "хороши"
        # "Хорошесть" определяется, например, минимальным количеством совпадений (например, > 1)
        # и максимальным количеством лишних (например, не более 5-ти)
        top_options = []
        for p_info in partial_candidates:
            # Добавим минимальный порог совпадений, чтобы не предлагать слишком плохие варианты
            if p_info["match_count"] > 0: # Должно быть хотя бы одно совпадение
                top_options.append(p_info)
            if len(top_options) >= 3: # Ограничиваем до 3 вариантов
                break

        if top_options:
            logging.info(f"Найдено {len(top_options)} частичных совпадений. Лучшие: {[p['recipe'].get('id') for p in top_options]}")
            return {"status": "partial_options", "options": top_options, "recipe": None, "missing_keys": []}

    logging.warning(f"Для набора {found_ingredients_keys} не найдено ни идеальных, ни частичных совпадений.")
    return {"status": "none", "recipe": None, "options": [], "missing_keys": []}

def find_terms_in_text(text: str) -> List[str]:
    """Сканирует текст и возвращает список ID найденных терминов."""
    found_term_ids = set()
    terms_db = KNOWLEDGE_BASE.get("terms", {})
    
    for term_id, term_data in terms_db.items():
        aliases = term_data.get("aliases", [])
        for alias in aliases:
            if re.search(r'\b' + re.escape(alias.lower()) + r'\b', text.lower()):
                found_term_ids.add(term_id)
                break
                
    return list(found_term_ids)

def find_random_recipe_by_category(category: str) -> Optional[Dict[str, Any]]:
    """Находит случайный рецепт по заданной категории."""
    recipes_db = KNOWLEDGE_BASE.get("recipes", [])
    
    candidates = [
        recipe for recipe in recipes_db 
        if recipe.get("category") == category
    ]
    
    if not candidates:
        logging.warning(f"Для категории '{category}' не найдено ни одного рецепта.")
        return None
    
    chosen_recipe = random.choice(candidates)
    logging.info(f"По категории '{category}' был случайно выбран рецепт '{chosen_recipe.get('id')}'.")
    
    return chosen_recipe

def assemble_recipe(recipe_template: Dict) -> Dict[str, Any]:
    """Собирает финальный текст рецепта и СПИСОК НАЙДЕННЫХ ТЕРМИНОВ."""
    phrases = KNOWLEDGE_BASE.get("phrases", {})
    ingredients_db = KNOWLEDGE_BASE.get("ingredients", {})
    
    # ИЗМЕНЕНИЕ: Берем статичный заголовок
    title = recipe_template.get("title", "Эксперимент без названия")

    templates = recipe_template.get("templates", {})
    
    def replacer(match):
        full_placeholder = match.group(0)
        key = match.group(1)
        form = match.group(2) if match.group(2) else "nom_sg"
        if key.lower() == "sarcasticcomment":
            return random.choice(phrases.get("sarcastic_comments", [""]))
        if key in ingredients_db:
            if form == "scientific_name":
                return ingredients_db[key].get("scientific_name", key)
            return ingredients_db[key].get("name_forms", {}).get(form, key)
        return full_placeholder

    reagents = re.sub(r'{(\w+):?(\w+)?}', replacer, templates.get("reagents", ""))
    effects = re.sub(r'{(\w+):?(\w+)?}', replacer, templates.get("effects", ""))

    procedure_steps = templates.get("procedure", [])
    formatted_steps = []
    
    if isinstance(procedure_steps, list):
        for i, step in enumerate(procedure_steps, 1):
            processed_step = re.sub(r'{(\w+):?(\w+)?}', replacer, step)
            formatted_steps.append(f"👨‍🍳 Шаг {i}: {processed_step}")
        procedure = "\n\n".join(formatted_steps)
    else:
        procedure = re.sub(r'{(\w+):?(\w+)?}', replacer, str(procedure_steps))
    
    final_text = f"<b>{title}</b>\n\n{reagents}\n\n{procedure}\n\n{effects}"
    found_terms = find_terms_in_text(final_text)

    return {"text": final_text, "found_terms": found_terms}

def find_recipe_by_intention(query: str) -> dict | None:
    """
    Ищет рецепт по прямому совпадению в 'intention_aliases'.
    Возвращает полный объект рецепта или None, если ничего не найдено.
    """
    # Приводим запрос пользователя к нижнему регистру для корректного сравнения
    normalized_query = query.lower()
    
    recipes = KNOWLEDGE_BASE.get("recipes", [])
    
    for recipe in recipes:
        # Проверяем, есть ли у рецепта вообще ключ intention_aliases
        if "intention_aliases" in recipe:
            for alias in recipe["intention_aliases"]:
                # Если какой-либо из алиасов содержится в запросе пользователя
                if alias in normalized_query:
                    # Нашли! Возвращаем весь объект рецепта.
                    return recipe
                    
    # Если прошли весь цикл и ничего не нашли
    return None

def synthesize_response(user_query: str) -> Dict[str, Any]:
    """Главная управляющая функция. Возвращает СЛОВАРЬ с текстом и терминами."""
    found_ingredients = parse_user_query(user_query)
    phrases = KNOWLEDGE_BASE.get("phrases", {})
    ingredients_db = KNOWLEDGE_BASE.get("ingredients", {})
    
    if not found_ingredients:
        return {
            "text": phrases.get("rejection_phrases", {}).get("no_ingredients_found", "Ошибка."),
            "found_terms": []
        }

    match_result = find_matching_recipe(found_ingredients)

    if match_result["status"] == "perfect":
        return assemble_recipe(match_result["recipe"])
    
    elif match_result["status"] == "partial":
        recipe_name = match_result["recipe"].get("title", "Некий Эксперимент")

        missing_names = []
        for key in match_result["missing_keys"]:
            missing_names.append(ingredients_db.get(key, {}).get("name_forms", {}).get("acc_sg", key))
        missing_ingredients_str = ", ".join(missing_names)

        template = phrases.get("rejection_phrases", {}).get("partial_match_found", "Ошибка. Шаблон не найден.")
        
        return {
            "text": template.format(RecipeName=recipe_name, MissingIngredients=missing_ingredients_str),
            "found_terms": []
        }

    else: # status == "none"
        return {
            "text": phrases.get("rejection_phrases", {}).get("no_recipe_found", "Ошибка."),
            "found_terms": []
        }