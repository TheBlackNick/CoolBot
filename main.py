import telebot
import wikipedia
import re
import sqlite3
import random
from datetime import datetime, timedelta

# Создаем экземпляр бота
bot = telebot.TeleBot('8245109729:AAHD6OB10e3nps-D-KmgLljmuUJfOeE1e3A')

# Создаем соединение с базой данных
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

# Создаем таблицу пользователей
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    fural INTEGER DEFAULT 0,
    last_farm TIMESTAMP
)
''')
conn.commit()

# Словарь для хранения временных данных дропов
# Формат: {user_id: {"attempts_left": 4, "current_drop": None}}
temp_drops = {}

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


# Функция для получения или создания пользователя в базе
def get_or_create_user(user_id, username, first_name):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, fural, last_farm) 
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, 0, None))
        conn.commit()
        return (user_id, username, first_name, 0, None)
    return user


# Функция для обновления количества фуралей
def update_fural(user_id, amount):
    cursor.execute('''
        UPDATE users 
        SET fural = fural + ?, last_farm = ? 
        WHERE user_id = ?
    ''', (amount, datetime.now(), user_id))
    conn.commit()


# Функция для получения топ-10 игроков
def get_top_players(limit=10):
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


# Функция, обрабатывающая команду /start
@bot.message_handler(commands=["start"])
def start(m, res=False):
    bot.send_message(m.chat.id, 'Привет! Я бот-энциклопедия. Чтобы найти информацию, используй команду /searchw')


# Функция, обрабатывающая команду /searchw
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


@bot.message_handler(commands=['ping'])
def ping(message):
    bot.reply_to(message,
                 f"1, 2, 3 \n1, 2, 3 \nБот абсолютно здоров! \n{message.from_user.full_name} ({message.from_user.id})")


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


# Фарм фуралей на слово "фураль"
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


# Обработчик инлайн кнопок
@bot.callback_query_handler(func=lambda call: True)
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
        cursor.execute('SELECT fural FROM users WHERE user_id = ?', (user_id,))
        total = cursor.fetchone()[0]

        # Формируем финальное сообщение с правильным склонением
        word = get_fural_word(final_drop['amount'])
        total_word = get_fural_word(total)

        if final_drop["rarity"] == "Легендарный":
            final_message = f"{first_name}, ТЕБЕ ВЫПАЛ ЛЕГЕНДАРНЫЙ ДРОП! Ты получил {final_drop['amount']} {word}! Всего: {total} {total_word}"
        elif final_drop["rarity"] == "Эпический":
            final_message = f"{first_name}, Эпический дроп! Ты получил {final_drop['amount']} {word}. Всего: {total} {total_word}"
        else:
            final_message = f"{first_name}, ты получил {final_drop['amount']} {word} ({final_drop['rarity']} дроп). Всего: {total} {total_word}"

        # Удаляем временные данные
        del temp_drops[user_id]

        # Обновляем сообщение (без клавиатуры)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=final_message
        )

        bot.answer_callback_query(call.id, "Дроп получен!")


# Таблица лидеров на слово "топ"
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


# Проверка своего баланса
@bot.message_handler(commands=['balance'])
def check_balance(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Получаем или создаем пользователя
    user = get_or_create_user(user_id, username, first_name)

    word = get_fural_word(user[3])
    response = f"{first_name}, у тебя {user[3]} {word}"
    bot.reply_to(message, response)


# Запускаем бота
bot.polling(none_stop=True, interval=0)