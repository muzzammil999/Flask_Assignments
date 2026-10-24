"""
Weather Dashboard - Flask backend (no database, no .env needed).

This file talks to THREE web APIs. All three are free and need no API key.

REFERENCE CITY used in every example below
    City    : Hyderabad
    State   : Telangana        (the geocoding API calls this field "admin1")
    Country : India

API 1 - Open-Meteo GEOCODING   (city name  ->  latitude / longitude)
    URL     : https://geocoding-api.open-meteo.com/v1/search
    Example : ...?name=Hyderabad&count=1&language=en
    Returns : {"results": [{"name": "Hyderabad", "admin1": "Telangana",
                            "country": "India",
                            "latitude": 17.38, "longitude": 78.47, ...}]}

API 2 - Open-Meteo FORECAST    (latitude / longitude  ->  weather numbers)
    URL     : https://api.open-meteo.com/v1/forecast
    Example : ...?latitude=17.38&longitude=78.47&current=temperature_2m,...&hourly=rain
    Returns : {"current": {"temperature_2m": 28.2, ...},
               "hourly":  {"time": [...], "rain": [...]}}


Flow for one search:   city -> API 1 -> API 2 -> API 3 -> JSON -> browser (script.js)

----------------------------------------------------------------------------------------
FLASK TOPICS THAT ARE REALLY USED IN THIS FILE (find them by searching "FLASK TOPIC")
----------------------------------------------------------------------------------------
    Create the app ............ app = Flask(__name__)
    Routing (link create) ..... @app.route("/") and @app.route("/api/weather")
    GET request ............... both routes use the default method (GET only)
    request object ............ request.args.get("city")  (the ?city=... part of the URL)
    render a template ......... render_template("index.html")  (Jinja is used inside it)
    static files .............. url_for('static', ...) inside templates/index.html
    JSON response ............. jsonify(...)
    autocomplete endpoint ..... /api/suggest (api_suggest) feeds the dropdown under the search box
    status codes .............. 200 (default), 400, 404, 502
    server-side validation .... the len(city) < 2 check in api_weather()
    configuration ............. app.run(debug=True)
    folder structure .......... app.py + templates/ + static/ (see EXPLANATION.md)

Topics that this project does NOT need (no database, no login, no forms posted to the
server): POST, dynamic <variable> URLs, MySQL / cursor / raw SQL / CRUD, ORM, sessions,
cookies, login, layouts / template inheritance. They are explained with working
examples in FLASK_COMPLETE_GUIDE.md instead of being forced into this app.
"""

from datetime import datetime  # used to read and format the city's local date and time

import requests  # library that sends HTTP requests to the three APIs
from flask import Flask, jsonify, render_template, request  # Flask pieces we use

from weather_cities import validate_city_name  # shared city-name rule (see weather_cities.py)

# FLASK TOPIC - create the app: Flask(__name__) tells Flask "this file is the app", so it
# can find the "templates" and "static" folders that sit next to app.py.
app = Flask(__name__)  # create the Flask web application

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"  # API 1 address
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"  # API 2 address


# Weather code number (from API 2) -> words. These are the official WMO codes.
WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",  # clear to cloudy
    45: "Fog", 48: "Rime fog",  # fog types
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",  # drizzle types
    56: "Freezing drizzle", 57: "Freezing drizzle",  # icy drizzle
    61: "Light rain", 63: "Rain", 65: "Heavy rain",  # rain types
    66: "Freezing rain", 67: "Freezing rain",  # icy rain
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",  # snow types
    80: "Rain showers", 81: "Rain showers", 82: "Violent showers",  # showers
    85: "Snow showers", 86: "Snow showers",  # snow showers
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail",  # storms
}

# Wind direction names. Index 0 = North, 1 = North-East, ... (every 45 degrees).
COMPASS = ["North", "North-East", "East", "South-East",
           "South", "South-West", "West", "North-West"]  # full names
COMPASS_SHORT = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]  # short names


def wind_text(speed):
    """
    Turn a wind speed number into a short phrase (a simplified Beaufort scale).

    Purpose : the weather API gives only a number such as 14; people understand
              "Gentle breeze" faster, so this function does the translation.
    Argument: speed (float or int) - wind speed in km/h, 10 metres above the ground.
    Returns : str - one of "Calm", "Light air", "Light breeze", "Gentle breeze",
              "Moderate breeze", "Fresh breeze", "Strong breeze",
              "Near gale or stronger".
    How     : the checks run from the lowest speed to the highest. The first test that
              is true returns immediately, so the order of the ifs matters.
    Example : wind_text(14)  ->  "Gentle breeze"      (Hyderabad, Telangana, India)
    Used by : build_weather() -> key "wind_text" -> shown in the Wind Speed card.
    """
    if speed < 1:  # almost no wind
        return "Calm"
    if speed < 6:  # 1 to 5 km/h
        return "Light air"
    if speed < 12:  # 6 to 11 km/h
        return "Light breeze"
    if speed < 20:  # 12 to 19 km/h
        return "Gentle breeze"
    if speed < 29:  # 20 to 28 km/h
        return "Moderate breeze"
    if speed < 39:  # 29 to 38 km/h
        return "Fresh breeze"
    if speed < 50:  # 39 to 49 km/h
        return "Strong breeze"
    return "Near gale or stronger"  # 50 km/h and above


def pressure_text(value):
    """
    Turn sea-level air pressure into one word: Low, Normal or High.

    Purpose : a raw number like 1008 means little to most people.
    Argument: value (float or int) - pressure at mean sea level (MSL) in hPa.
    Returns : str - "Low" (below 1000), "High" (above 1025) or "Normal" (1000 to 1025).
    Example : pressure_text(1008)  ->  "Normal"
    Used by : build_weather() -> key "pressure_text" -> small text of the Pressure card.
    """
    if value < 1000:  # below 1000 hPa
        return "Low"
    if value > 1025:  # above 1025 hPa
        return "High"
    return "Normal"  # everything in between


def cloud_text(value):
    """
    Turn cloud cover (a percentage) into words.

    Purpose : "Mostly cloudy" is easier to read than "78".
    Argument: value (float or int) - how much of the sky is covered, 0 to 100 (%).
    Returns : str - "Clear sky" (0-10), "Mostly clear" (11-30), "Partly cloudy" (31-60),
              "Mostly cloudy" (61-85) or "Overcast" (86-100).
    Example : cloud_text(45)  ->  "Partly cloudy"
    Used by : build_weather() -> key "cloud_text" -> small text of the Cloud Cover card.
    """
    if value <= 10:  # almost no clouds
        return "Clear sky"
    if value <= 30:  # a few clouds
        return "Mostly clear"
    if value <= 60:  # about half the sky
        return "Partly cloudy"
    if value <= 85:  # most of the sky
        return "Mostly cloudy"
    return "Overcast"  # whole sky covered


def format_local_time(iso_text):
    """
    Turn the API's date-time text into a friendly sentence in the CITY'S OWN time.

    Purpose : the forecast API (because of timezone=auto) already gives the time of the
              searched city, e.g. Indian Standard Time for Hyderabad, Telangana, India.
              We only change the look, never the time zone.
    Argument: iso_text (str) - ISO 8601 text such as "2026-10-15T10:24".
    Returns : str - like "Thursday, 15 Oct 2026 · 10:24 AM".
    Steps   : 1) datetime.fromisoformat() reads the text into a datetime object,
              2) the 24-hour clock is converted to a 12-hour clock (hour 0 -> 12 AM,
                 hour 13 -> 1 PM) with  hour % 12 or 12,
              3) strftime() supplies the weekday name and the short month name.
    Example : format_local_time("2026-10-15T13:05")  ->  "Thursday, 15 Oct 2026 · 1:05 PM"
    Used by : build_weather() -> key "local_time" -> shown under the country name.
    """
    t = datetime.fromisoformat(iso_text)  # read the text as a date and time
    am_pm = "AM" if t.hour < 12 else "PM"  # before 12 o'clock is AM
    hour12 = t.hour % 12 or 12  # 24-hour clock -> 12-hour clock (0 becomes 12)
    return f"{t.strftime('%A')}, {t.day} {t.strftime('%b %Y')} · {hour12}:{t.minute:02d} {am_pm}"  # final text


def find_place(city, country="", state=""):
    """
    API 1 - Open-Meteo GEOCODING: find the latitude and longitude of a city name.

    Request : GET https://geocoding-api.open-meteo.com/v1/search
    Params  : name=<city>      the text the user typed
              count=1          we only want the best match
              language=en      names in English
    Response: {"results": [{"name": "Hyderabad", "admin1": "Telangana",
                            "country": "India",
                            "latitude": 17.38, "longitude": 78.47, ...}]}
              If the city is unknown, "results" is missing.
    Why     : the weather API (API 2) does not understand city names, only coordinates.

    Arguments: city (str)    - city name typed by the user, e.g. "Hyderabad".
               country (str) - OPTIONAL, e.g. "India". Given when the user clicked a suggestion.
               state (str)   - OPTIONAL, e.g. "Telangana". Given when the user clicked a suggestion.
               When country/state are given we ask the API for 10 matches (instead of 1) and
               pick the one whose country/state match, so "Hyderabad, Telangana, India" is
               never confused with "Hyderabad, Sindh, Pakistan". Without them, behaviour is
               exactly as before: the single best match is used.
    Returns : dict - the best match. Useful keys: "name" (city), "admin1" (state, when the
              API knows it), "country", "latitude", "longitude".
    Raises  : ValueError("City not found. ...")  when the API finds nothing; api_weather()
              catches it and answers with HTTP 404.
              requests.RequestException  when there is no internet, a timeout or a 4xx/5xx
              answer; api_weather() catches it and answers with HTTP 502.
    Note    : this is an OUTGOING request (our server -> the API) made with the
              "requests" library. It is not the same as Flask's incoming "request" object.
    """
    reply = requests.get(  # send the request to API 1
        GEO_URL,  # the address of API 1
        params={"name": city, "count": 10 if (country or state) else 1, "language": "en"},  # the ?name=...&count=... part of the URL
        timeout=10,  # give up after 10 seconds
    )
    reply.raise_for_status()  # raise an error if the server answered with 4xx / 5xx
    results = reply.json().get("results")  # read the JSON reply and take the "results" list
    if not results:  # list is missing or empty -> city does not exist
        raise ValueError("City not found. Please check the spelling.")  # message shown on the page
    for place in results:  # when a suggestion was clicked, look for the exact state / country
        same_country = not country or place.get("country", "").lower() == country.lower()  # country matches (or none asked)
        same_state = not state or place.get("admin1", "").lower() == state.lower()  # state matches (or none asked)
        if same_country and same_state:  # exact match found
            return place  # use it
    return results[0]  # the best match: a dict with name, country, latitude, longitude


def get_forecast(latitude, longitude):
    """
    API 2 - Open-Meteo FORECAST: get the weather for a latitude and longitude.

    Request : GET https://api.open-meteo.com/v1/forecast
    Params  : latitude, longitude   the place (from API 1)
              current=...           the numbers we want right now (temperature, humidity, ...)
              hourly=rain           rain for every hour (used for the bar chart)
              forecast_days=2       today + tomorrow, so we always have 12 hours ahead
              timezone=auto         times are in the city's own time zone
    Response: {"current": {"time": "2026-10-15T10:15", "temperature_2m": 28.2, ...},
               "hourly":  {"time": ["2026-10-15T00:00", ...], "rain": [0.0, ...]}}

    Arguments: latitude (float)  - north/south position, e.g. 17.38 for Hyderabad
               longitude (float) - east/west position,   e.g. 78.47 for Hyderabad
    Returns  : dict - the complete JSON answer converted to a Python dictionary.
               build_weather() reads data["current"] and data["hourly"] from it.
    Raises   : requests.RequestException when the API cannot be reached or answers 4xx/5xx.
    """
    wanted_now = (  # comma separated list of the "current" values we need
        "temperature_2m,apparent_temperature,relative_humidity_2m,rain,weather_code,"
        "cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,is_day"
    )
    reply = requests.get(  # send the request to API 2
        WEATHER_URL,  # the address of API 2
        params={  # the ?latitude=...&longitude=... part of the URL
            "latitude": latitude,  # north-south position
            "longitude": longitude,  # east-west position
            "current": wanted_now,  # values for right now
            "hourly": "rain",  # rain for each hour
            "forecast_days": 2,  # two days of hourly data
            "timezone": "auto",  # use the city's time zone
        },
        timeout=10,  # give up after 10 seconds
    )
    reply.raise_for_status()  # raise an error if the server answered with 4xx / 5xx
    return reply.json()  # the whole reply as a Python dict


def build_weather(city, country="", state=""):
    """
    Run API 1, API 2 and API 3 for one city and return everything the page needs.

    This is the "manager" function: it calls the other helpers in the right order,
    cleans the numbers and returns one flat dictionary that api_weather() turns into JSON.

    Arguments: city (str)    - the text typed by the user, e.g. "Hyderabad".
               country, state (str) - optional, passed on to find_place() (see there).
    Returns : dict with these keys (all consumed by showWeather() in script.js):
        city, country, state     names for the title (e.g. "Hyderabad", "India")
        local_time               friendly date/time text of the city
        temperature, feels_like  degrees Celsius (rounded)
        humidity, cloud_cover    percentages (rounded)
        rain                     millimetres right now
        cloud_text               words for the cloud cover
        wind_speed, wind_text    km/h and words
        wind_direction           degrees 0-360
        wind_short, wind_name    "SW" and "South-West"
        pressure_msl, pressure_text, surface_pressure   hPa numbers and one word
        weather_code, condition  WMO number and its words
        is_day                   True / False
        hourly                   list of 12 {"time": "10 AM", "rain": 0.0} for the chart
    Raises  : ValueError (city not found) or requests.RequestException (network problem);
              both are handled in api_weather().
    Steps   : 1) geocode the city, 2) fetch the forecast, 3) find where "now" is inside
              the hourly list and slice the next 12 hours, 4) turn degrees into a
              compass point, 5) assemble the dictionary.
    """
    place = find_place(city, country, state)  # API 1: city name -> place (name, country, latitude, longitude)
    data = get_forecast(place["latitude"], place["longitude"])  # API 2: coordinates -> weather
    cur = data["current"]  # the "right now" values

    times = data["hourly"]["time"]  # list of hours, like "2026-10-15T10:00"
    rains = data["hourly"]["rain"]  # rain (mm) for each of those hours
    this_hour = cur["time"][:13] + ":00"  # current time cut down to the full hour, "2026-10-15T10:00"
    start = 0  # index in the lists where the next 12 hours begin
    for i, t in enumerate(times):  # walk through the hours
        if t >= this_hour:  # first hour that is now or later
            start = i  # remember this position
            break  # stop looking
    hourly = []  # the 12 bars of the chart
    for i in range(start, min(start + 12, len(times))):  # take up to 12 hours from "start"
        hour = int(times[i][11:13])  # the hour number (0-23) from the text
        label = f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"  # 24-hour -> "10 AM" / "1 PM"
        hourly.append({"time": label, "rain": rains[i] or 0})  # label + rain amount (None becomes 0)

    direction = int(round(cur["wind_direction_10m"]))  # wind direction in degrees (0-360)
    index = int(round(direction / 45)) % 8  # degrees -> compass position 0..7
    code = int(cur["weather_code"])  # weather code number

    return {  # everything below is sent to script.js as JSON
        "city": place["name"],  # city name, e.g. "Hyderabad"
        "country": place.get("country", ""),  # country name, e.g. "India"
        "state": place.get("admin1", ""),  # state name, e.g. "Telangana" (not shown on the page; used by Refresh)
        "local_time": format_local_time(cur["time"]),  # the city's date and time as text
        "temperature": round(cur["temperature_2m"]),  # temperature in °C
        "feels_like": round(cur["apparent_temperature"]),  # "feels like" temperature in °C
        "humidity": round(cur["relative_humidity_2m"]),  # humidity in %
        "rain": cur["rain"],  # rain right now in mm
        "cloud_cover": round(cur["cloud_cover"]),  # clouds in %
        "cloud_text": cloud_text(cur["cloud_cover"]),  # clouds in words
        "wind_speed": round(cur["wind_speed_10m"]),  # wind speed in km/h
        "wind_text": wind_text(cur["wind_speed_10m"]),  # wind speed in words
        "wind_direction": direction,  # wind direction in degrees
        "wind_short": COMPASS_SHORT[index],  # "SW"
        "wind_name": COMPASS[index],  # "South-West"
        "pressure_msl": round(cur["pressure_msl"]),  # sea-level pressure in hPa
        "pressure_text": pressure_text(cur["pressure_msl"]),  # Low / Normal / High
        "surface_pressure": round(cur["surface_pressure"]),  # pressure at ground level in hPa
        "weather_code": code,  # code number, e.g. 2
        "condition": WEATHER_CODES.get(code, "Unknown"),  # code in words, e.g. "Partly cloudy"
        "is_day": bool(cur["is_day"]),  # True in daylight, False at night
        "hourly": hourly,  # the 12 chart bars
    }


# FLASK TOPIC - link create / routing: @app.route("/") links the URL "/" to the function below.
# No methods= is given, so only GET is allowed (a POST to "/" would get 405 Method Not Allowed).
@app.route("/")  # runs when the browser opens http://127.0.0.1:5000/
def home():
    """
    ROUTE  GET /   -  send the web page to the browser.

    FLASK TOPIC - render_template: Flask looks for "index.html" inside the "templates"
    folder, runs it through the Jinja engine (this page uses {{ url_for(...) }} to build
    the links to style.css, skyline.jpg and script.js) and returns the final HTML text.

    Arguments: none (the URL "/" has no variable part, so this is a STATIC route).
    Returns  : the HTML page with status 200 OK (the default status).
    After that: the browser downloads script.js, which immediately calls /api/weather.
    """
    return render_template("index.html")  # Flask finds the file inside the templates folder


@app.route("/api/weather")  # runs when script.js calls /api/weather?city=Hyderabad
def api_weather():
    """
    ROUTE  GET /api/weather?city=<name>  -  the only data endpoint (called by script.js).

    FLASK TOPICS used here
        request.args ...... the query string. For /api/weather?city=Hyderabad,
                            request.args.get("city") gives "Hyderabad". Optional extras
                            ?country=India&state=Telangana are sent after a suggestion click.
                            (request.args is for GET data; a POST form would use request.form.)
        server-side validation .. the length check below. The browser also checks, but
                            browser checks can be bypassed, so the server must check again.
        jsonify ........... turns a Python dict into a JSON response with the header
                            Content-Type: application/json.
        status codes ...... the number after the dict is the HTTP status.

    Answers
        200 OK ............ success, body = the weather dictionary from build_weather()
        400 Bad Request ... city missing or shorter than 2 letters   {"error": "..."}
        404 Not Found ..... the geocoding API does not know the city {"error": "..."}
        502 Bad Gateway ... an outside API (or the internet) failed  {"error": "..."}

    Arguments: none in Python; the data arrives through the URL's ?city= part.
    Example  : /api/weather?city=Hyderabad  ->  Hyderabad, Telangana, India weather as JSON.
    """
    city = request.args.get("city", "").strip()  # the text after ?city= without extra spaces
    country = request.args.get("country", "").strip()  # optional: exact country of a clicked suggestion
    state = request.args.get("state", "").strip()  # optional: exact state of a clicked suggestion
    # validation (same rule as validateCity() in script.js) lives in weather_cities.py:
    # 2-60 characters, only letters, spaces, dot, apostrophe and hyphen, starting with a letter
    if validate_city_name(city):  # "" when valid, otherwise an error message
        return jsonify({"error": "Please enter a valid city name."}), 400  # 400 = bad request (same text as before)
    try:  # the APIs can fail, so we catch the errors
        return jsonify(build_weather(city, country, state))  # success: send the weather as JSON
    except ValueError as error:  # raised by find_place when the city does not exist
        return jsonify({"error": str(error)}), 404  # 404 = not found
    except requests.RequestException:  # no internet, timeout, or API down
        return jsonify({"error": "Could not reach the weather service. Check your internet."}), 502  # 502 = bad gateway


@app.route("/api/suggest")  # runs while the user types: /api/suggest?q=Hyd
def api_suggest():
    """
    ROUTE  GET /api/suggest?q=<letters>  -  city name suggestions for the search box.

    Called by script.js a moment after the user stops typing. It asks the Open-Meteo
    GEOCODING API (the same API 1 used by find_place) for up to 8 places whose name starts
    like the typed letters, removes duplicates and returns at most 6 of them.

    FLASK TOPICS used here: request.args (the ?q= part), server-side validation (the
    length check), jsonify (a JSON list) and status codes (200, 400, 502).

    Answers
        200 OK ............ a list, possibly empty:
                            [{"name": "Hyderabad", "state": "Telangana",
                              "country": "India",
                              "label": "Hyderabad, Telangana, India"}, ...]
        400 Bad Request ... fewer than 2 letters typed   {"error": "..."}
        502 Bad Gateway ... the geocoding API could not be reached   {"error": "..."}
    Example  : /api/suggest?q=Hyd  ->  Hyderabad (Telangana, India), Hyderabad (Sindh, Pakistan) ...
    """
    text = request.args.get("q", "").strip()  # the letters typed so far
    if len(text) < 2:  # too short to suggest anything
        return jsonify({"error": "Type at least 2 letters."}), 400  # 400 = bad request
    try:  # the API can fail, so we catch the errors
        reply = requests.get(  # ask API 1 for several matches
            GEO_URL,  # the address of API 1
            params={"name": text, "count": 8, "language": "en"},  # up to 8 places
            timeout=6,  # suggestions must be fast, give up after 6 seconds
        )
        reply.raise_for_status()  # raise an error if the server answered with 4xx / 5xx
        found = reply.json().get("results") or []  # list of places (missing when nothing matches)
    except (requests.RequestException, ValueError):  # internet problem or bad JSON
        return jsonify({"error": "Could not load suggestions."}), 502  # 502 = bad gateway
    suggestions = []  # the list we send back
    seen = set()  # labels already added (to skip duplicates)
    for place in found:  # go through the places one by one
        parts = [place.get("name", ""), place.get("admin1", ""), place.get("country", "")]  # city, state, country
        label = ", ".join(part for part in parts if part)  # "Hyderabad, Telangana, India" (empty parts skipped)
        if not place.get("name") or label in seen:  # no name, or the same label again
            continue  # skip it
        seen.add(label)  # remember the label
        suggestions.append({  # one suggestion for the dropdown
            "name": place["name"],  # city
            "state": place.get("admin1", ""),  # state (may be "")
            "country": place.get("country", ""),  # country (may be "")
            "label": label,  # text shown in the dropdown
        })
    return jsonify(suggestions[:6])  # at most 6 suggestions


# FLASK TOPIC - configuration: debug=True turns on the interactive error page and the
# auto-reloader. Use it only while learning/developing, never on a real public server.
if __name__ == "__main__":  # true only when you run "python app.py"
    app.run(debug=True)  # start the server at http://127.0.0.1:5000 (debug shows errors and auto-reloads)
