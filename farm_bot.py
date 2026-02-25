import random
import telebot
from config import bot
from database import get_or_create_user, update_fural, can_farm, get_time_until_next_farm, get_top_players, \
    get_user_balance

# Словарь для хранения временных данных дропов
# Формат: {user_id: {"attempts_left": 4, "current_drop": None}}
temp_drops = {}


# Функция для получения случайного дропа
def get_starr_drop():
    # 4 уровня редкости
    rarities = [
        {"name": "Обычный", "chance": 0.50, "min": 1, "max": 5, "value": 1},  # 50% шанс
        {"name": "Редкий", "chance": 0.30, "min": 5, "max": 15, "value": 2},  # 30% шанс
        {"name": "Эпический", "chance": 0.15, "min": 15, "max": 30, "value": 3},  # 15% шанс
        {"name": "Легендарный", "chance": 0.05, "min": 30, "max": 50, "value": 4}  # 5% шанс
    ]

    # Выбираем редкость на основе шансов
    roll = random.random()
    cumulative_chance = 0

    for rarity in rarities:
        cumulative_chance += rarity["chance"]
        if roll <= cumulative_chance:
            amount = random.randint(rarity["min"], rarity["max"])
            return {
                "amount": amount,
                "rarity": rarity["name"],
                "rarity_value": rarity["value"]
            }

    # На всякий случай (если сумма шансов не 1)
    return {"amount": random.randint(1, 5), "rarity": "Обычный", "rarity_value": 1}


# Функция для склонения слова "фураль"
def get_fural_word(amount):
    if 11 <= amount % 100 <= 19:
        return "фуралей"
    elif amount % 10 == 1:
        return "фураль"
    elif 2 <= amount % 10 <= 4:
        return "фурали"
    else:
        return "фуралей"


# Функция для создания инлайн клавиатуры
def create_drop_keyboard(user_id, show_try=True, show_claim=False):
    keyboard = telebot.types.InlineKeyboardMarkup()

    if show_try and user_id in temp_drops and temp_drops[user_id]["attempts_left"] > 0:
        button = telebot.types.InlineKeyboardButton(
            text=f"додеп ({temp_drops[user_id]['attempts_left']}/4)",
            callback_data="try_again"
        )
        keyboard.add(button)

    if show_claim:
        claim_button = telebot.types.InlineKeyboardButton(
            text="забрать",
            callback_data="claim_drop"
        )
        keyboard.add(claim_button)

    return keyboard


# Регистрируем все обработчики для фарма
def register_farm_handlers():
    @bot.message_handler(func=lambda message: message.text and message.text.lower().strip() == "фураль")
    def farm_fural(message):
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name

        # Получаем или создаем пользователя
        get_or_create_user(user_id, username, first_name)

        # Проверяем, можно ли фармить
        if not can_farm(user_id):
            wait_time = get_time_until_next_farm(user_id)
            minutes = wait_time // 60
            seconds = wait_time % 60
            if minutes > 0:
                time_text = f"{minutes} мин {seconds} сек"
            else:
                time_text = f"{seconds} сек"
            bot.reply_to(message, f"{first_name}, фарма доступна раз в 30 минут. Подожди ещё {time_text}")
            return

        # Получаем первый дроп
        current_drop = get_starr_drop()

        # Инициализируем временные данные для дропа
        temp_drops[user_id] = {
            "attempts_left": 3,  # Осталось попыток (первая уже использована)
            "current_drop": current_drop,
            "first_name": first_name
        }

        # Формируем сообщение с текущим дропом
        word = get_fural_word(current_drop['amount'])
        drop_info = f"{first_name}, текущий дроп: {current_drop['amount']} {word} ({current_drop['rarity']})"

        # Определяем, показывать кнопку додеп или сразу забрать
        if current_drop["rarity"] == "Легендарный":
            # Если легендарный с первой попытки - сразу кнопка забрать
            keyboard = create_drop_keyboard(user_id, show_try=False, show_claim=True)
        else:
            # Иначе показываем кнопку додеп
            keyboard = create_drop_keyboard(user_id, show_try=True, show_claim=False)

        bot.send_message(message.chat.id, drop_info, reply_markup=keyboard)

    @bot.message_handler(func=lambda message: message.text and message.text.lower().strip() == "топ")
    def show_top(message):
        top_players = get_top_players(10)

        if not top_players:
            bot.reply_to(message, "Пока никто не фармил фурали")
            return

        response = "ТОП-10 ФАРМЕРОВ ФУРАЛЕЙ:\n"

        for i, (first_name, username, fural) in enumerate(top_players, 1):
            if username:
                name_display = f"@{username}"
            else:
                name_display = first_name

            word = get_fural_word(fural)
            response += f"{i}. {name_display} - {fural} {word}\n"

        bot.reply_to(message, response)

    @bot.message_handler(commands=['balance'])
    def check_balance(message):
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name

        # Получаем или создаем пользователя
        get_or_create_user(user_id, username, first_name)

        # Получаем баланс
        balance = get_user_balance(user_id)
        word = get_fural_word(balance)
        response = f"{first_name}, у тебя {balance} {word}"
        bot.reply_to(message, response)

    @bot.callback_query_handler(func=lambda call: call.data == "try_again" or call.data == "claim_drop")
    def handle_callback(call):
        user_id = call.from_user.id

        if user_id not in temp_drops:
            bot.answer_callback_query(call.id, "Сессия дропа истекла. Начни заново командой 'фураль'")
            return

        if call.data == "try_again":
            # Проверяем, остались ли попытки
            if temp_drops[user_id]["attempts_left"] <= 0:
                bot.answer_callback_query(call.id, "У тебя больше нет попыток!")
                return

            # Получаем новый дроп
            current_drop = get_starr_drop()
            old_drop = temp_drops[user_id]["current_drop"]

            # Сравниваем редкость
            if current_drop["rarity_value"] > old_drop["rarity_value"]:
                # Улучшилась редкость - обновляем дроп
                temp_drops[user_id]["current_drop"] = current_drop
                if current_drop["rarity"] == "Легендарный":
                    result_message = f"ЛЕГЕНДАРНЫЙ ДРОП! {current_drop['amount']} {get_fural_word(current_drop['amount'])}"
                else:
                    result_message = f"УЛУЧШЕНО ДО {current_drop['rarity']}!"
            elif current_drop["rarity_value"] == old_drop["rarity_value"]:
                # Та же редкость - сравниваем количество
                if current_drop["amount"] > old_drop["amount"]:
                    temp_drops[user_id]["current_drop"] = current_drop
                    result_message = f"УЛУЧШЕНО! {current_drop['amount']} {get_fural_word(current_drop['amount'])}"
                else:
                    result_message = f"Не повезло, {current_drop['amount']} {get_fural_word(current_drop['amount'])}"
            else:
                # Хуже редкость
                result_message = f"Не повезло, {current_drop['amount']} {get_fural_word(current_drop['amount'])}"

            # Уменьшаем счетчик попыток
            temp_drops[user_id]["attempts_left"] -= 1

            # Получаем текущий дроп
            best_drop = temp_drops[user_id]["current_drop"]

            # Формируем сообщение (только текущий дроп)
            word = get_fural_word(best_drop['amount'])
            drop_info = f"{temp_drops[user_id]['first_name']}, текущий дроп: {best_drop['amount']} {word} ({best_drop['rarity']})"

            # Определяем, какие кнопки показывать
            if best_drop["rarity"] == "Легендарный":
                # Если выпал легендарный - сразу показываем кнопку забрать
                keyboard = create_drop_keyboard(user_id, show_try=False, show_claim=True)
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=drop_info,
                    reply_markup=keyboard
                )
                bot.answer_callback_query(call.id, "Легендарный дроп! Можно забрать")
            elif temp_drops[user_id]["attempts_left"] <= 0:
                # Если попытки закончились - показываем кнопку забрать
                keyboard = create_drop_keyboard(user_id, show_try=False, show_claim=True)
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=drop_info,
                    reply_markup=keyboard
                )
                bot.answer_callback_query(call.id, "Попытки закончились. Можно забрать дроп")
            else:
                # Иначе показываем кнопку додеп
                keyboard = create_drop_keyboard(user_id, show_try=True, show_claim=False)
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=drop_info,
                    reply_markup=keyboard
                )
                bot.answer_callback_query(call.id, "Попытка использована")

        elif call.data == "claim_drop":
            # Забираем текущий дроп
            final_drop = temp_drops[user_id]["current_drop"]
            first_name = temp_drops[user_id]["first_name"]

            # Обновляем баланс
            update_fural(user_id, final_drop["amount"])

            # Получаем обновленное количество
            balance = get_user_balance(user_id)

            # Формируем финальное сообщение с правильным склонением
            word = get_fural_word(final_drop['amount'])
            total_word = get_fural_word(balance)

            if final_drop["rarity"] == "Легендарный":
                final_message = f"{first_name}, ТЕБЕ ВЫПАЛ ЛЕГЕНДАРНЫЙ ДРОП! Ты получил {final_drop['amount']} {word}! Всего: {balance} {total_word}"
            elif final_drop["rarity"] == "Эпический":
                final_message = f"{first_name}, Эпический дроп! Ты получил {final_drop['amount']} {word}. Всего: {balance} {total_word}"
            else:
                final_message = f"{first_name}, ты получил {final_drop['amount']} {word} ({final_drop['rarity']} дроп). Всего: {balance} {total_word}"

            # Удаляем временные данные
            del temp_drops[user_id]

            # Обновляем сообщение (без клавиатуры)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=final_message
            )

            bot.answer_callback_query(call.id, "Дроп получен!")