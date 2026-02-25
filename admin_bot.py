# Бот будет передан из main.py
bot = None

def set_bot(bot_instance):
    global bot
    bot = bot_instance

def register_admin_handlers():
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