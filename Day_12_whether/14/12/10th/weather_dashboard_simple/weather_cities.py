"""
weather_cities.py - city-name helpers shared by app.py and build_cities.py.

validate_city_name() holds the one rule for what a city name may look like, so the
server (app.py) and the city-list builder (build_cities.py) cannot drift apart.
It is the Python twin of validateCity() in static/js/script.js.
"""
import re  # used to check that the city name has only valid characters

# starts with a letter, then letters, spaces, dot, apostrophe or hyphen (no digits / symbols)
CITY_PATTERN = re.compile(r"[^\W\d_](?:[^\W\d_]|[ .'-])*")


def validate_city_name(city):
    """
    Check a city name.

    Arguments: city (str) - the name typed by the user, e.g. "Hyderabad".
    Returns  : "" when the name is valid, otherwise a short error message.
    Example  : validate_city_name("Hyd123") -> "City name can only contain letters, spaces, - ' and ."
    """
    city = " ".join((city or "").split())  # trim and collapse repeated spaces
    if len(city) < 2:  # empty or too short
        return "Please enter a city name (at least 2 letters)."
    if len(city) > 60:  # too long
        return "City name is too long (maximum 60 characters)."
    if not CITY_PATTERN.fullmatch(city):  # bad characters
        return "City name can only contain letters, spaces, - ' and ."
    return ""  # "" means the name is valid
