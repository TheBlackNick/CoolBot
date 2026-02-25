import sqlite3
from datetime import datetime

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