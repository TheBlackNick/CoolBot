from config import bot  # Добавляем этот импорт
from database import save_message, get_total_messages, get_messages_since, get_user_stats
import telebot
from datetime import datetime

# Словарь для временного хранения выбранного периода
temp_counter = {}


# Функция для создания клавиатуры с периодами
def create_period_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)

    btn_all = telebot.types.InlineKeyboardButton("За всё время", callback_data="period_all")
    btn_month = telebot.types.InlineKeyboardButton("За месяц", callback_data="period_month")
    btn_week = telebot.types.InlineKeyboardButton("За неделю", callback_data="period_week")
    btn_day = telebot.types.InlineKeyboardButton("За день", callback_data="period_day")
    btn_hour = telebot.types.InlineKeyboardButton("За час", callback_data="period_hour")

    keyboard.add(btn_all, btn_month)
    keyboard.add(btn_week, btn_day)
    keyboard.add(btn_hour)

    return keyboard


# Функция для получения статистики по выбранному периоду
def get_stats_by_period(period, user_id=None, chat_id=None):
    if period == "all":
        return get_total_messages(user_id, chat_id)
    elif period == "month":
        return get_messages_since(user_id, chat_id, days=30)
    elif period == "week":
        return get_messages_since(user_id, chat_id, days=7)
    elif period == "day":
        return get_messages_since(user_id, chat_id, hours=24)
    elif period == "hour":
        return get_messages_since(user_id, chat_id, hours=1)
    return 0


# Обработчик слова "счётчик" (должен быть зарегистрирован ДО обработчика всех сообщений)
def register_counter_handlers():
    @bot.message_handler(func=lambda message: message.text and message.text.lower().strip() == "счётчик")
    def show_counter_menu(message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        chat_type = message.chat.type

        # Сохраняем информацию о том, откуда вызван счётчик
        temp_counter[user_id] = {
            "chat_id": chat_id,
            "chat_type": chat_type,
            "message_id": message.message_id
        }

        if chat_type in ['group', 'supergroup']:
            text = f"{message.from_user.first_name}, выбери период для просмотра статистики сообщений в этом чате:"
        else:
            text = f"{message.from_user.first_name}, выбери период для просмотра статистики твоих сообщений:"

        bot.send_message(chat_id, text, reply_markup=create_period_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data.startswith("period_"))
    def handle_period_selection(call):
        user_id = call.from_user.id
        period = call.data.replace("period_", "")

        if user_id not in temp_counter:
            bot.answer_callback_query(call.id, "Сессия истекла. Начни заново командой 'счётчик'")
            return

        chat_id = temp_counter[user_id]["chat_id"]
        chat_type = temp_counter[user_id]["chat_type"]

        if chat_type in ['group', 'supergroup']:
            # Статистика по чату (БЕЗ ТОП-5 БОЛТУНОВ)
            total_msgs = get_stats_by_period(period, chat_id=chat_id)

            # Название периода
            period_names = {
                "all": "ВСЁ ВРЕМЯ",
                "month": "МЕСЯЦ",
                "week": "НЕДЕЛЮ",
                "day": "ДЕНЬ",
                "hour": "ЧАС"
            }

            response = f"Статистика чата за {period_names[period]}:\n"
            response += f"Всего сообщений: {total_msgs}"

        else:
            # Личная статистика пользователя
            stats = get_user_stats(user_id)

            period_counts = {
                "all": stats["total"],
                "month": stats["month"],
                "week": stats["week"],
                "day": stats["day"],
                "hour": 0  # За час нужно отдельно считать
            }

            if period == "hour":
                period_counts["hour"] = get_messages_since(user_id, hours=1)

            period_names = {
                "all": "ВСЁ ВРЕМЯ",
                "month": "МЕСЯЦ",
                "week": "НЕДЕЛЮ",
                "day": "ДЕНЬ",
                "hour": "ЧАС"
            }

            response = f"Твоя статистика за {period_names[period]}:\n"
            response += f"Сообщений: {period_counts[period]}"

        # Удаляем временные данные
        del temp_counter[user_id]

        # Редактируем сообщение с результатом
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=response
        )

        bot.answer_callback_query(call.id, "Статистика готова!")


# Обработчик для сохранения всех сообщений (должен быть зарегистрирован ПОСЛЕ)
def register_message_saver():
    @bot.message_handler(func=lambda message: True)
    def count_all_messages(message):
        # Игнорируем команду "счётчик" чтобы не было конфликтов
        if message.text and message.text.lower().strip() == "счётчик":
            return

        # Сохраняем каждое сообщение в базу данных
        chat_title = message.chat.title if message.chat.title else "Личные сообщения"
        save_message(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.chat.id,
            chat_title,
            message.text
        )