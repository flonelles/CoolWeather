import logging
import sqlite3

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    CallbackContext
)
from os import environ
from weather import get_temperature, get_status, get_weather_week

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
            entry_points=[CommandHandler('start_weather_message', self.start_weather_message)],
            states={
                'get_temperature_message': [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                           self.get_temperature_message)],
            },
            fallbacks=[]
        )
        # диалог для получения местоположения пользователя и вывода погоды
        self.handler_location_weather = ConversationHandler(
            entry_points=[CommandHandler('start_get_location', self.start_get_location)],
            states={
                # 'get_temperature': [MessageHandler(filters.TEXT & ~filters.COMMAND,)],
            },
            fallbacks=[]
        )
        # инлайн клавиатура с кнопками  для добавления город в список отслеживаемых
        self.inline_keyboard_city = InlineKeyboardMarkup([
            [InlineKeyboardButton("Добавить", callback_data='add')],
            [InlineKeyboardButton("Не добавить", callback_data='no_add')],
            [InlineKeyboardButton("Открыть список отслеживаемых городов", callback_data='tracked cities')]
        ])
        # инлайн клавиатура для начала работы приложения
        self.inline_keyboard_start = InlineKeyboardMarkup([
            [InlineKeyboardButton("Узнать погоду по городу", callback_data='get_weather_city')],
            [InlineKeyboardButton("Узнать погоду по местоположению", callback_data='get_location')],
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
        self.aplication.add_handler(CallbackQueryHandler(self.button_click))
        self.aplication.add_handler(CommandHandler('tracked_cities', self.show_tracked_cities))
        self.aplication.add_handler(CommandHandler('start_get_location', self.start_get_location))
    # приветствие и ознакомление
    async def start(self, update, context):
        user = update.effective_user
        await update.message.reply_html(
            rf"Привет {user.mention_html()}! Вот мои функции:", reply_markup=self.inline_keyboard_start
        )

    # вход в диалог для нахождения погоды в городе
    async def start_weather_message(self, update,
                                    context):  # КОНТЕКСТ НАДО ПРОКИДЫВАТЬ ЕСЛИ ФУНКЦИЯ НАХОДИТСЯ В ДИАЛОГЕ
        await update.message.reply_text('Введите название города')
        return 'get_temperature_message'

    # вывод погоды или если неправильно написан город вывод ошибки(решил поместить в одну тк меньше занимает)
    async def get_temperature_message(self, update, context):
        city = update.message.text
        weather = get_temperature(city)
        if weather != '':
            self.logger.info(weather)
            await update.message.reply_text(f"Сейчас в городе {city.lower().capitalize()}: {weather}"
                                            f" {get_status(city)}\n\nДобавить город в список отслеживаемых?",
                                            reply_markup=self.inline_keyboard_city)
        else:
            await update.message.reply_text("Кажется, вы неправильно ввели город... Попробуйте ещё раз!"
                                            " /start_weather_message")
        return ConversationHandler.END

    # обработчик кнопок
    async def button_click(self, update, context):
        query = update.callback_query
        user_id = query.from_user.id
        button_type = query.data

        if button_type == 'add':
            city_name = query.message.text.split()[3][:-1]
            if self.is_city_tracked(user_id, city_name):
                await query.answer("Город уже есть в списке отслеживаемых!")
            else:
                self.add_tracked_city(user_id, city_name)
                await query.answer("Город добавлен в список отслеживаемых.")
        elif button_type == 'no_add':
            await query.answer("Город не добавлен.")
        elif button_type == 'tracked cities':
            await self.show_tracked_cities(update, context)
        elif button_type == 'get_weather_city':
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='Введите команду /start_weather_message'
            )
        elif button_type == 'get_location':
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='Введите команду /get_weather_location'
            )
        else:
            await query.answer('Отправляю...')
            await self.get_full_weather_city(update, button_type)  # в button_type сейчас лежит город

    # получить погоду по местоположению
    async def start_get_location(self, update, context):

        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("Поделиться местоположением", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text("Пожалуйста, поделитесь своим местоположением.", reply_markup=keyboard)

    async def get_full_weather_city(self, update, city):
        weather_for_week = get_weather_week(city)
        weather_now = get_temperature(city)
        status = get_status(city)

        if update.callback_query:
            await update.callback_query.answer("Вывожу...")
            await update.callback_query.message.reply_text(
                f"Прямо сейчас в городе {city} {weather_now}, {status}\n\n Погода на неделю:\n{weather_for_week}"
            )
        elif update.message:
            await update.message.reply_text(
                f"Прямо сейчас в городе {city} {weather_now}, {status}\n\n Погода на неделю:\n{weather_for_week}"
            )
        else:
            self.logger.error("Update is not supported for this operation.")

    # добавление города в список отслеживаемых
    def add_tracked_city(self, user_id, city_name):
        if not self.is_city_tracked(user_id, city_name):
            self.cursor.execute("INSERT INTO tracked_cities (user_id, city_name) VALUES (?, ?)",
                                (user_id, city_name.lower().capitalize()))
            self.conn.commit()

    # проверка есть ли уже город в списке отслеживаемых
    def is_city_tracked(self, user_id, city_name):
        self.cursor.execute("SELECT * FROM tracked_cities WHERE user_id = ? AND city_name = ?",
                            (user_id, city_name.lower().capitalize()))
        return bool(self.cursor.fetchone())

    # показать пользователю список отслеживаемых городов
    async def show_tracked_cities(self, update, context):
        user_id = update.effective_user.id
        self.cursor.execute("SELECT distinct city_name FROM tracked_cities WHERE user_id = ?",
                            (user_id,))
        tracked_cities = self.cursor.fetchall()

        if tracked_cities:
            message = "Список отслеживаемых городов:\n\n"
            keyboard = []
            for city_name in tracked_cities:
                keyboard.append([InlineKeyboardButton(city_name[0], callback_data=city_name[0])])

            self.inline_keyboard_tracked_cities = InlineKeyboardMarkup(keyboard)
            message += "Выберите город для просмотра подробной информации о погоде:"
        else:
            message = "У вас пока нет отслеживаемых городов."

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            reply_markup=self.inline_keyboard_tracked_cities
        )

    # запуск
    def run(self):
        self.aplication.run_polling()
