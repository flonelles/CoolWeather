from pyowm.owm import OWM
from pyowm.utils.config import get_default_config
from os import environ
import requests
import calendar
import locale
from datetime import datetime, timedelta

WEATHER_KEY = environ['WEATHER_KEY']


def get_temperature(city: str) -> str:
    owm = OWM(WEATHER_KEY)
    mgr = owm.weather_manager()
    try:
        if ''.join(set(city)) == ' ':
            raise Exception
        observation = mgr.weather_at_place(city)
        weather = observation.weather
        temperature = weather.temperature('celsius')['temp']
        return f'{temperature}C°'.capitalize()
    except Exception:
        return ''


def get_status(city: str) -> str:
    config_dict = get_default_config()
    config_dict['language'] = 'ru'
    owm = OWM(WEATHER_KEY, config_dict)
    mgr = owm.weather_manager()
    observation = mgr.weather_at_place(city)
    weather = observation.weather
    return weather.detailed_status.capitalize()


def get_weather_week(city: str) -> str:
    try:
        if ''.join(set(city)) == ' ':
            raise Exception
        api_key = WEATHER_KEY

        url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&lang=ru&units=metric&appid={api_key}"

        response = requests.get(url)
        data = response.json()

        months_names = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
            7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
        }

        days_of_week = {
            0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
            4: "пятница", 5: "суббота", 6: "воскресенье"
        }

        forecast_by_day = {}

        for forecast in data["list"]:
            forecast_date = datetime.strptime(forecast["dt_txt"], "%Y-%m-%d %H:%M:%S")
            day_number = forecast_date.strftime("%d")
            month = months_names[int(forecast_date.strftime("%m"))]
            day_of_week = days_of_week[forecast_date.weekday()]

            temperature = f"{forecast['main']['temp']}°C"
            weather_info = f"{day_number} {month}, {day_of_week}: {temperature}"

            if day_number not in forecast_by_day:
                forecast_by_day[day_number] = weather_info
        forecast_strings = [forecast_by_day[day] for day in sorted(forecast_by_day.keys())]
        return "\n".join(forecast_strings)
    except Exception:
        return ''
