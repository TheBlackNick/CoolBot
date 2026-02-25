import wikipedia
import re
from config import bot

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

# Функция, обрабатывающая команду /searchw
def register_wikipedia_handlers():
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