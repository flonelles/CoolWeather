from geopy.geocoders import Nominatim


def get_city_by_coordinates(latitude: str, longitude: str) -> str:
    geolocator = Nominatim(user_agent="city_locator")
    location = geolocator.reverse((latitude, longitude), language='ru')
    address = location.raw['address']
    city = address.get('city', '')
    if not city:
        city = address.get('town', '')
    if not city:
        city = address.get('village', '')
    return city
