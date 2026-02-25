from config import bot
import database
import wikipedia_bot
import farm_bot

# Регистрируем все обработчики
wikipedia_bot.register_wikipedia_handlers()
farm_bot.register_farm_handlers()

# Простые команды, которые можно оставить в main.py
@bot.message_handler(commands=["start"])
def start(m, res=False):
    bot.send_message(m.chat.id, 'Привет! Я бот-энциклопедия. Чтобы найти информацию, используй команду /searchw')

@bot.message_handler(commands=['ping'])
def ping(message):
    bot.reply_to(message, f"1, 2, 3 \n1, 2, 3 \nБот абсолютно здоров! \n{message.from_user.full_name} ({message.from_user.id})")

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

# Запускаем бота
if __name__ == '__main__':
    print("Бот запущен!")
    bot.polling(none_stop=True, interval=0)