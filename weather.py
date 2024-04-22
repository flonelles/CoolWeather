from pyowm.owm import OWM
from pyowm.utils.config import get_default_config
from os import environ

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
        return f'{city} {temperature}'.capitalize()
    except Exception:
        return 'miss'


def get_status(city: str):
    config_dict = get_default_config()
    config_dict['language'] = 'ru'
    owm = OWM(WEATHER_KEY, config_dict)
    mgr = owm.weather_manager()
    observation = mgr.weather_at_place(city)
    weather = observation.weather
    return weather.detailed_status.capitalize()
