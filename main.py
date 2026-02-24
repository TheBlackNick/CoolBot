import os
import telebot
from dotenv import load_dotenv

load_dotenv ()

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

@bot.message_handler(commands = ['start'])
def start (message):
    bot.reply_to(message, f"Всё работает, можно творить!\n{message.from_user.full_name}")

bot.polling()