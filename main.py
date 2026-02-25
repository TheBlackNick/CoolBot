import os
import telebot
import wikipedia
import re
import sqlite3
import random
from datetime import datetime, timedelta
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# ========== ТОКЕН БОТА ==========

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

# ========== БАЗА ДАННЫХ ==========
DB_PATH = 'users.db'


# Контекстный менеджер для работы с БД
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Создаем таблицы при запуске
def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        # Создаем таблицу пользователей для фарма
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            fural INTEGER DEFAULT 0,
            last_farm TIMESTAMP
        )
        ''')

        # Создаем таблицу для подсчета сообщений
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            chat_id INTEGER,
            chat_title TEXT,
            message_text TEXT,
            timestamp TIMESTAMP
        )
        ''')


# Инициализируем БД
init_db()


# ========== ФУНКЦИИ ДЛЯ ФАРМА (БАЗА ДАННЫХ) ==========

# Функция для получения или создания пользователя в базе
def get_or_create_user(user_id, username, first_name):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()

        if not user:
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, fural, last_farm) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, 0, None))
            return (user_id, username, first_name, 0, None)
        return user


# Функция для обновления количества фуралей
def update_fural(user_id, amount):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET fural = fural + ?, last_farm = ? 
            WHERE user_id = ?
        ''', (amount, datetime.now(), user_id))


# Функция для получения топ-10 игроков
def get_top_players(limit=10):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT first_name, username, fural 
            FROM users 
            WHERE fural > 0 
            ORDER BY fural DESC 
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()


# Функция для проверки времени последнего фарма
def can_farm(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT last_farm FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result or not result[0]:
            return True

        last_farm = datetime.fromisoformat(result[0])
        time_diff = datetime.now() - last_farm

        # Откат 30 минут (1800 секунд)
        return time_diff.total_seconds() > 1800


# Функция для получения времени до следующего фарма
def get_time_until_next_farm(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT last_farm FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result or not result[0]:
            return 0

        last_farm = datetime.fromisoformat(result[0])
        time_diff = datetime.now() - last_farm
        seconds_passed = time_diff.total_seconds()

        if seconds_passed >= 1800:
            return 0

        return int(1800 - seconds_passed)


# Функция для получения баланса пользователя
def get_user_balance(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT fural FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0


# ========== ФУНКЦИИ ДЛЯ СЧЁТЧИКА СООБЩЕНИЙ (БАЗА ДАННЫХ) ==========

# Функция для сохранения сообщения
def save_message(user_id, username, first_name, chat_id, chat_title, message_text):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (user_id, username, first_name, chat_id, chat_title, message_text, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, chat_id, chat_title, message_text, datetime.now()))
    except Exception as e:
        print(f"Ошибка при сохранении сообщения: {e}")


# Функция для подсчета сообщений за всё время
def get_total_messages(user_id=None, chat_id=None):
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT COUNT(*) FROM messages"
        params = []

        conditions = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if chat_id:
            conditions.append("chat_id = ?")
            params.append(chat_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        cursor.execute(query, params)
        return cursor.fetchone()[0]


# Функция для подсчета сообщений за определенный период
def get_messages_since(user_id=None, chat_id=None, hours=0, days=0):
    with get_db() as conn:
        cursor = conn.cursor()
        time_ago = datetime.now() - timedelta(hours=hours, days=days)

        query = "SELECT COUNT(*) FROM messages WHERE timestamp >= ?"
        params = [time_ago]

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if chat_id:
            query += " AND chat_id = ?"
            params.append(chat_id)

        cursor.execute(query, params)
        return cursor.fetchone()[0]


# Функция для получения статистики по конкретному пользователю
def get_user_stats(user_id, chat_id=None):
    with get_db() as conn:
        cursor = conn.cursor()

        # Базовый запрос
        base_query = "SELECT COUNT(*) FROM messages WHERE user_id = ?"
        params = [user_id]

        if chat_id:
            base_query += " AND chat_id = ?"
            params.append(chat_id)

        # За всё время
        cursor.execute(base_query, params)
        total = cursor.fetchone()[0]

        # За день
        day_ago = datetime.now() - timedelta(days=1)
        cursor.execute(base_query + " AND timestamp >= ?", params + [day_ago])
        day = cursor.fetchone()[0]

        # За неделю
        week_ago = datetime.now() - timedelta(weeks=1)
        cursor.execute(base_query + " AND timestamp >= ?", params + [week_ago])
        week = cursor.fetchone()[0]

        # За месяц
        month_ago = datetime.now() - timedelta(days=30)
        cursor.execute(base_query + " AND timestamp >= ?", params + [month_ago])
        month = cursor.fetchone()[0]

        return {"total": total, "day": day, "week": week, "month": month}


# ========== ФУНКЦИИ ДЛЯ ВИКИПЕДИИ ==========

# Устанавливаем русский язык в Wikipedia
wikipedia.set_lang("ru")


# Чистим текст статьи в Wikipedia и ограничиваем его тысячей символов
def getwiki(s):
    try:
        ny = wikipedia.page(s)

        # Получаем первую тысячу символов
        wikitext = ny.content[:1000]

        # Разделяем по точкам
        wikimas = wikitext.split('.')

        # Отбрасываем остальное после последней точки
        wikimas = wikimas[:-1]

        # Создаем пустую переменную для текста
        wikitext2 = ''

        # Проходимся по строкам, где нет знаков «равно» (то есть все, кроме заголовков)
        for x in wikimas:
            if not ('==' in x):
                # Если в строке осталось больше трех символов, добавляем ее к нашей переменной и возвращаем утерянные при разделении строк точки на место
                if len(x.strip()) > 3:
                    wikitext2 = wikitext2 + x + '.'
            else:
                break

        # Теперь при помощи регулярных выражений убираем разметку
        # Используем raw strings (r'...') для корректной обработки escape-последовательностей
        wikitext2 = re.sub(r'\([^()]*\)', '', wikitext2)
        wikitext2 = re.sub(r'\([^()]*\)', '', wikitext2)
        wikitext2 = re.sub(r'\{[^\{\}]*\}', '', wikitext2)

        # Если после очистки текст пустой или слишком короткий
        if len(wikitext2.strip()) < 10:
            return None

        # Возвращаем текстовую строку
        return wikitext2

    # Обрабатываем исключение, которое мог вернуть модуль wikipedia при запросе
    except Exception as e:
        return None


# ========== ФУНКЦИИ ДЛЯ ФАРМА ФУРАЛЕЙ ==========

# Словарь для хранения временных данных дропов
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


# Функция для создания инлайн клавиатуры для фарма
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


# ========== ФУНКЦИИ ДЛЯ СЧЁТЧИКА СООБЩЕНИЙ ==========

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


# ========== ОБРАБОТЧИКИ КОМАНД ==========

# Команда /start
@bot.message_handler(commands=["start"])
def start(m, res=False):
    bot.send_message(m.chat.id, 'Привет! Я бот-энциклопедия. Чтобы найти информацию, используй команду /searchw')


# Команда /searchw (поиск в Wikipedia)
@bot.message_handler(commands=["searchw"])
def search_wikipedia(message):
    # Получаем текст после команды /searchw
    command_parts = message.text.split(maxsplit=1)

    # Проверяем, ввел ли пользователь запрос
    if len(command_parts) > 1:
        search_query = command_parts[1]

        # Отправляем первое сообщение
        sent_message = bot.send_message(
            message.chat.id,
            f'Ищу информацию о {search_query}'
        )

        # Ищем информацию
        result = getwiki(search_query)

        # Проверяем результат
        if result:
            # Добавляем информацию о том, кто запросил (для групповых чатов)
            if message.chat.type in ['group', 'supergroup']:
                result = f"Запрос от {message.from_user.first_name}:\n\n{result}"

            # Обновляем сообщение с результатом
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=sent_message.message_id,
                text=result
            )
        else:
            # Добавляем информацию о том, кто запросил (для групповых чатов)
            if message.chat.type in ['group', 'supergroup']:
                not_found_text = f"{message.from_user.first_name}, информация не найдена"
            else:
                not_found_text = 'Информация не найдена'

            # Обновляем сообщение, что информация не найдена
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=sent_message.message_id,
                text=not_found_text
            )
    else:
        # Проверяем тип чата для персонализированного ответа
        if message.chat.type in ['group', 'supergroup']:
            bot.send_message(
                message.chat.id,
                f'{message.from_user.first_name}, укажи, что мне нужно искать. Например: /searchw Python'
            )
        else:
            bot.send_message(
                message.chat.id,
                'Укажи мне что искать. Например: /searchw Python'
            )


# Команда /ping
@bot.message_handler(commands=['ping'])
def ping(message):
    bot.reply_to(message,
                 f"1, 2, 3 \n1, 2, 3 \nБот абсолютно здоров! \n{message.from_user.full_name} ({message.from_user.id})")


# Команда /admins
@bot.message_handler(commands=['admins'])
def adminlist(message):
    # Проверяем, что команда вызвана в группе
    if message.chat.type in ['group', 'supergroup']:
        admins = bot.get_chat_administrators(message.chat.id)

        # Собираем список строк с упоминаниями
        lines = []
        for admin in admins:
            user = admin.user
            # Исключаем ботов, если хочешь видеть только людей
            if not user.is_bot:
                # Создаем кликабельное имя через HTML
                mention = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'
                lines.append(f"{mention}")

        response_text = "<b>Админы этого чата:</b>\n" + "\n".join(lines)

        # Важно указать parse_mode='HTML'
        bot.send_message(message.chat.id, response_text, parse_mode='HTML')
    else:
        bot.reply_to(message, "Эта команда работает только в группах.")


# Команда /balance
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


# ========== ОБРАБОТЧИКИ НА СЛОВА ==========

# Обработчик слова "фураль" (фарм)
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


# Обработчик слова "топ" (таблица лидеров)
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


# Обработчик слова "счётчик" (статистика сообщений)
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


# ========== ОБРАБОТЧИКИ ИНЛАЙН КНОПОК ==========

# Обработчик для кнопок фарма
@bot.callback_query_handler(func=lambda call: call.data == "try_again" or call.data == "claim_drop")
def handle_farm_callback(call):
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


# Обработчик для кнопок счётчика
@bot.callback_query_handler(func=lambda call: call.data.startswith("period_"))
def handle_counter_callback(call):
    user_id = call.from_user.id
    period = call.data.replace("period_", "")

    if user_id not in temp_counter:
        bot.answer_callback_query(call.id, "Сессия истекла. Начни заново командой 'счётчик'")
        return

    chat_id = temp_counter[user_id]["chat_id"]
    chat_type = temp_counter[user_id]["chat_type"]

    if chat_type in ['group', 'supergroup']:
        # Статистика по чату
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


# ========== ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ (ДЛЯ СЧЁТЧИКА) ==========
# ВАЖНО: этот обработчик должен быть ПОСЛЕДНИМ!

@bot.message_handler(func=lambda message: True)
def count_all_messages(message):
    # Игнорируем команду "счётчик" чтобы не было конфликтов
    if message.text and message.text.lower().strip() == "счётчик":
        return

    # Игнорируем команды
    if message.text and message.text.startswith('/'):
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


# ========== ЗАПУСК БОТА ==========
if __name__ == '__main__':
    print("Бот запущен!")
    bot.polling(none_stop=True, interval=0)