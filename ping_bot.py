from config import bot  # Добавляем этот импорт

def register_ping_handlers():
    @bot.message_handler(commands=['ping'])
    def ping(message):
        bot.reply_to(message, f"1, 2, 3 \n1, 2, 3 \nБот абсолютно здоров! \n{message.from_user.full_name} ({message.from_user.id})")