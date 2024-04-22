import logging
import sqlite3

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from os import environ
from weather import get_temperature, get_status

BOT_TOKEN = environ["BOT_TOKEN"]


class TelegramBot:
    def __init__(self):
        # logger
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
        )
        self.logger = logging.getLogger(__name__)

        # запуск приложения
        self.aplication = Application.builder().token(BOT_TOKEN).build()

        # простой диалог с получением погоды в городе
        self.handler_city = ConversationHandler(
            entry_points=[CommandHandler('weather', self.weather)],
            states={
                # Функция читает ответ на первый вопрос и задаёт второй.
                'get_temperature': [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_temperature)],
            },
            fallbacks=[CommandHandler('get_temperature', self.get_temperature)]
        )
        # инлайн клавиатура с кнопками  для добавления город в список отслеживаемых
        self.inline_keyboard_city = InlineKeyboardMarkup([
            [InlineKeyboardButton("Добавить", callback_data='add')],
            [InlineKeyboardButton("Не добавить", callback_data='no_add')],
            [InlineKeyboardButton("Открыть список отслеживаемых городов", callback_data='tracked cities')]
        ])
        # инлайн клавиатура с кнопками  для вывода списка отслеживаемых городов
        self.inline_keyboard_tracked_cities = InlineKeyboardMarkup([])
        # подключаемся к базе данных
        self.conn = sqlite3.connect('tracked_cities.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS tracked_cities
                                              (user_id INTEGER, city_name TEXT)''')
        self.conn.commit()

        # обработчики
        self.aplication.add_handler(self.handler_city)
        self.aplication.add_handler(CommandHandler('start', self.start))
        self.aplication.add_handler(CallbackQueryHandler(self.button_click_city))
        self.aplication.add_handler(CommandHandler('tracked_cities', self.show_tracked_cities))

    # приветствие и ознакомление
    async def start(self, update, context):
        user = update.effective_user
        await update.message.reply_html(
            rf"Привет {user.mention_html()}! Чтобы узнать погоду в городе - печатай /weather",
        )

    # вход в диалог для нахождения погоды в городе
    async def weather(self, update, context):
        await update.message.reply_text('Введите название города')
        return 'get_temperature'

    # вывод погоды или если неправильно написан город вывод ошибки(решил поместить в одну тк меньше занимает)
    async def get_temperature(self, update, context):
        city = update.message.text
        weather = get_temperature(city)
        if weather != 'miss':  # мис отправляется в случае если неправильно написан город или его нет openweathermap
            self.logger.info(weather)
            await update.message.reply_text(f"Сейчас в городе {weather}° "
                                            f"{get_status(city)}", reply_markup=self.inline_keyboard_city)
        else:
            await update.message.reply_text("Кажется, вы неправильно ввели город... Попробуйте ещё раз! /weather")
        return ConversationHandler.END

    # основные инлайн кнопки для работы приложения
    async def button_click_city(self, update, context):
        query = update.callback_query
        user_id = query.from_user.id
        button_type = query.data

        if button_type == 'add':
            city_name = query.message.text.split()[3]  # Extract city name from the message
            if self.is_city_tracked(user_id, city_name):
                await query.answer("Город уже есть в списке отслеживаемых!")
            else:
                self.add_tracked_city(user_id, city_name)
                await query.answer("Город добавлен в список отслеживаемых.")
        elif button_type == 'no_add':
            await query.answer("Город не добавлен.")
        elif button_type == 'tracked cities':
            await self.show_tracked_cities(update, context)

    # добавление города в список отслеживаемых
    def add_tracked_city(self, user_id, city_name):
        if not self.is_city_tracked(user_id, city_name):
            self.cursor.execute("INSERT INTO tracked_cities (user_id, city_name) VALUES (?, ?)",
                                (user_id, city_name))
            self.conn.commit()

    # проверка есть ли уже город в списке отслеживаемых
    def is_city_tracked(self, user_id, city_name):
        self.cursor.execute("SELECT * FROM tracked_cities WHERE user_id = ? AND city_name = ?",
                            (user_id, city_name))
        return bool(self.cursor.fetchone())

    # показать пользователю список отслеживаемых городов
    async def show_tracked_cities(self, update, context):
        user_id = update.effective_user.id
        self.cursor.execute("SELECT distinct city_name FROM tracked_cities WHERE user_id = ?", (user_id,))
        tracked_cities = self.cursor.fetchall()
        if tracked_cities:
            message = "Список отслеживаемых городов:\n\n"
            self.inline_keyboard_tracked_cities = \
                InlineKeyboardMarkup([[InlineKeyboardButton(city_name,)] for city_name in tracked_cities])
            for city_name in tracked_cities:
                weather = get_temperature(*city_name)
                status = get_status(*city_name)
                message += f"{weather}° {status}\n"


        else:
            message = "У вас пока нет отслеживаемых городов."

        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

    # запуск
    def run(self):
        self.aplication.run_polling()
