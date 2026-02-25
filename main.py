import telebot
import database
import wikipedia_bot
import farm_bot
import admin_bot
import ping_bot
import message_counter

bot = telebot.TeleBot("BOT_TOKEN")

# ВАЖНО: Сначала регистрируем обработчики команд
wikipedia_bot.register_wikipedia_handlers()
farm_bot.register_farm_handlers()
admin_bot.register_admin_handlers()
ping_bot.register_ping_handlers() 
# ПОТОМ регистрируем обработчик слова "счётчик"
message_counter.register_counter_handlers()

# В САМУЮ ПОСЛЕДНЮЮ ОЧЕРЕДЬ - обработчик всех сообщений
message_counter.register_message_saver()

# Простые команды
@bot.message_handler(commands=["start"])
def start(m, res=False):
    bot.send_message(m.chat.id, 'Привет! Я бот-энциклопедия. Чтобы найти информацию, используй команду /searchw')

# Запускаем бота
if __name__ == '__main__':
    print("Бот запущен!")
    bot.polling(none_stop=True, interval=0)