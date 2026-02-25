import telebot

# Этот файл теперь только для импорта бота
# Токен будет передаваться из main.py
bot = None

def init_bot(token):
    global bot
    bot = telebot.TeleBot(token)
    return bot