import logging
import sqlite3

from telegram import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
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
from bot.weather.weather import get_temperature, get_status, get_weather_week
from bot.location.location import get_city_by_coordinates

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
                'get_weather_location': [MessageHandler(filters.LOCATION, self.get_weather_location)],
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
        self.conn = sqlite3.connect('../tracked_cities.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS tracked_cities
                                              (user_id INTEGER, city_name TEXT)''')
        self.conn.commit()

        # обработчики
        self.aplication.add_handler(self.handler_city)
        self.aplication.add_handler(self.handler_location_weather)
        self.aplication.add_handler(CommandHandler('start', self.start))
        self.aplication.add_handler(CallbackQueryHandler(self.button_click))
        self.aplication.add_handler(CommandHandler('tracked_cities', self.show_tracked_cities))
        self.aplication.add_handler(CommandHandler('help', self.help))

    # приветствие и ознакомление
    async def start(self, update, context):
        user = update.effective_user
        await update.message.reply_html(
            rf"Привет {user.mention_html()}! Вот мои функции:", reply_markup=self.inline_keyboard_start
        )

    # помощь
    async def help(self, update, context):  # контекст нужен
        await update.message.reply_html('/start - начало работы бота\n'
                                        '/tracked_cities - открыть список отслеживаемых городов\n'
                                        '/start_get_location - погода по геолокации\n'
                                        '/start_weather_message - погода по введенному городу')

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
                text='Введите команду /start_get_location'
            )
        else:
            await query.answer('Отправляю...')
            await self.get_full_weather_city(update, button_type)  # в button_type сейчас лежит город

    # пользователь делится геолокацией
    async def start_get_location(self, update, context):
        button = ReplyKeyboardMarkup(
            [[KeyboardButton("Поделиться местоположением", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text("Пожалуйста, поделитесь своим местоположением.", reply_markup=button)
        return 'get_weather_location'

    async def get_weather_location(self, update, context):
        location = update.message.location
        if location:
            await update.message.reply_text("Спасибо за предоставленное местоположение.",
                                            reply_markup=ReplyKeyboardRemove())
            latitude = location.latitude
            longitude = location.longitude
            city = get_city_by_coordinates(latitude, longitude)
            weather = get_temperature(city)
            if weather != '':
                self.logger.info(weather)
                await update.message.reply_text(f"Сейчас в городе {city.lower().capitalize()}: {weather}"
                                                f" {get_status(city)}\n\nДобавить город в список отслеживаемых?",
                                                reply_markup=self.inline_keyboard_city)
            else:
                await update.message.reply_text("Что то пошло не так... Попробуйте ещё раз! /start_get_location")
        else:
            await update.message.reply_text("Я не получил ваше местоположнеие( Попробуйте ещё раз! /start_get_location")

        return ConversationHandler.END

    # полная погода))) или вывод погоды на неделю
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
            self.logger.error("ошибка((")

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
