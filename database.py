import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

# Путь к файлу базы данных
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


# Инициализируем БД при импорте
init_db()


# ========== ФУНКЦИИ ДЛЯ ФАРМА ==========

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


# ========== ФУНКЦИИ ДЛЯ СЧЁТЧИКА СООБЩЕНИЙ ==========

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


# Функция для получения топ-10 самых активных пользователей в чате
def get_top_chatters(chat_id, limit=10, hours=0, days=0):
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT first_name, username, COUNT(*) as msg_count 
            FROM messages 
            WHERE chat_id = ?
        """
        params = [chat_id]

        if hours > 0 or days > 0:
            time_ago = datetime.now() - timedelta(hours=hours, days=days)
            query += " AND timestamp >= ?"
            params.append(time_ago)

        query += " GROUP BY user_id ORDER BY msg_count DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return cursor.fetchall()


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