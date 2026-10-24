# Weather Dashboard – Explanation

A small Flask project. You type a city, and the page shows its weather, a photo of the city and a 12-hour rain chart.
**No database and no `.env` file are used.** Everything comes live from three free web APIs (no API key needed).

---

## 1. Files

| File | What it does |
|---|---|
| `app.py` | Flask server. Calls the 3 APIs and sends one JSON answer to the browser. Every line is commented. |
| `templates/index.html` | The page layout (top bar, top card, weather cards, chart, details table). |
| `static/css/style.css` | Fonts, colours and sizes copied from the design image (font: Inter). |
| `static/js/script.js` | Runs in the browser: calls our server, fills the page, draws the chart. Every line is commented. |
| `static/data/cities.json` | Known country and city names. `script.js` checks the typed city against it BEFORE any request is sent. `build_cities.py` can rebuild it as a bigger list (~25,000 cities, needs internet). |
| `static/img/skyline.jpg` | Default picture, used when a city has no Wikipedia photo. |
| `requirements.txt` | Only two packages: `Flask` and `requests`. |
| `FLASK_COMPLETE_GUIDE.md` | Study guide for all Flask topics (routes, Jinja, forms, validation, status codes, MySQL, ORM, sessions, cookies ...). Reference city: Hyderabad, Telangana, India. |

## 2. How to run

```
python -m pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 (internet is required, because the data comes from the APIs).

---

## 3. The API fetching process (step by step)

The browser **never** talks to the weather sites. It only talks to our Flask server, and Flask talks to the 3 APIs.

```
 Browser (script.js)                 Flask (app.py)                       Outside APIs
 ───────────────────                 ──────────────                       ────────────
 You type "Berlin", press Search
        │
        │  fetch("/api/weather?city=Berlin")
        ├──────────────────────────► api_weather()
                                          │  build_weather("Berlin")
                                          │
                                          ├─► find_place()       ───────► API 1  Geocoding
                                          │       ◄── latitude 52.52, longitude 13.41
                                          │
                                          ├─► get_forecast()     ───────► API 2  Forecast
                                          │       ◄── temperature, humidity, wind, rain per hour ...
                                          │
                                          ├─► find_city_image()  ───────► API 3  Wikipedia
                                          │       ◄── photo URL (or nothing)
                                          │
                                          │  mix all results into one dictionary
        ◄─────────────────────────────────┘  jsonify(...)  = one JSON answer
        │
 showWeather(data) fills the cards, icon, photo and chart
```

Why 3 calls and not 1? Each API does one job:
the weather API needs **coordinates**, not a city name, so API 1 must run first and API 2 uses its answer.
API 3 only adds the photo; if it fails, the weather is still shown.

---

## 3b. City name suggestions and the fixed top bar

**Suggestions while typing.** After you type 2 or more letters and pause for 250 ms, `script.js` calls
`GET /api/suggest?q=Hyd`. Flask (`api_suggest()` in `app.py`) asks the same Open-Meteo geocoding API for up to 8 places,
removes duplicates and returns at most 6 as JSON:

```json
[ { "name": "Hyderabad", "state": "Telangana", "country": "India", "label": "Hyderabad, Telangana, India" },
  { "name": "Hyderabad", "state": "Sindh",     "country": "Pakistan", "label": "Hyderabad, Sindh, Pakistan" } ]
```

| How you use it | Result |
|---|---|
| Click a suggestion, or `↓` / `↑` then `Enter` | That exact place loads (`/api/weather?city=Hyderabad&country=India&state=Telangana`) |
| `Esc`, click elsewhere, or press Search | The list closes; a normal typed search works exactly as before |
| Refresh button | Reloads the same city, state and country |

Why `country` and `state` are sent: many cities share a name. Without them, "Hyderabad" would always load the first match.
When they are given, `find_place()` asks the API for 10 matches and picks the one whose state and country match.
Suggestions are only a help: if the suggestion call fails the list simply stays closed.
Status codes of `/api/suggest`: 200 (list, may be empty), 400 (fewer than 2 letters), 502 (API unreachable).

**Fixed top bar.** `.topbar` in `style.css` uses `position: sticky; top: 0; z-index: 100`, so the bar (logo, search box,
Refresh) stays at the top while the page scrolls, on desktop and on phones.

---

## 4. The three APIs

### API 1 – Open-Meteo Geocoding  (city name → coordinates)
Function: `find_place(city)` in `app.py`

```
GET https://geocoding-api.open-meteo.com/v1/search?name=Berlin&count=1&language=en
```
| Parameter | Meaning |
|---|---|
| `name` | The city the user typed |
| `count=1` | Only the best match |
| `language=en` | Names in English |

Example reply (shortened):
```json
{ "results": [ { "name": "Berlin", "country": "Germany", "latitude": 52.52, "longitude": 13.41 } ] }
```
We keep `results[0]`. If `results` is missing, the city does not exist → the page shows *"City not found"*.

### API 2 – Open-Meteo Forecast  (coordinates → weather)
Function: `get_forecast(latitude, longitude)` in `app.py`

```
GET https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41
    &current=temperature_2m,apparent_temperature,relative_humidity_2m,rain,weather_code,
             cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,is_day
    &hourly=rain&forecast_days=2&timezone=auto
```
| Parameter | Meaning |
|---|---|
| `latitude`, `longitude` | The place, from API 1 |
| `current` | The values for **right now** (list below) |
| `hourly=rain` | Rain for every hour, used for the bar chart |
| `forecast_days=2` | Today and tomorrow, so we always have 12 hours ahead |
| `timezone=auto` | Times are in the **city's own** time zone |

What each `current` value becomes on the page:

| API value | Shown as |
|---|---|
| `temperature_2m` | Temperature (big number + card) |
| `apparent_temperature` | "Feels like" |
| `relative_humidity_2m` | Humidity card |
| `rain` | Current Rain card |
| `weather_code` | Condition text ("Partly cloudy") + the big icon |
| `cloud_cover` | Cloud Cover card |
| `pressure_msl` | Pressure (MSL) card |
| `surface_pressure` | Surface Pressure row in Weather Details |
| `wind_speed_10m` | Wind Speed card |
| `wind_direction_10m` | Wind Direction card (degrees → SW, South-West) |
| `is_day` | "Day / Night" badge and "Is Day" row |

Example reply (shortened):
```json
{
  "current": { "time": "2026-10-14T10:15", "temperature_2m": 18.2, "relative_humidity_2m": 68,
               "weather_code": 2, "wind_direction_10m": 220, "is_day": 1 },
  "hourly":  { "time": ["2026-10-14T00:00", "2026-10-14T01:00", "..."],
               "rain": [0.0, 0.0, "..."] }
}
```

### API 3 – Wikipedia page image  (city name → photo)
Function: `find_city_image(name, country)` in `app.py`

```
GET https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch=Berlin Germany
    &gsrlimit=1&prop=pageimages&pithumbsize=1600&format=json
```
| Parameter | Meaning |
|---|---|
| `generator=search` + `gsrsearch` | Search Wikipedia for the page "Berlin Germany" |
| `gsrlimit=1` | Only the first page found |
| `prop=pageimages` | Give us that page's main picture |
| `pithumbsize=1600` | Picture width in pixels |

Example reply (shortened):
```json
{ "query": { "pages": { "3354": { "title": "Berlin", "thumbnail": { "source": "https://upload.wikimedia.org/....jpg" } } } } }
```
If the page has no `thumbnail`, we return `""` and the page keeps the default skyline.
Answers are remembered in `image_cache` while the server runs, so Wikipedia is asked once per city.
Wikipedia chooses the picture, so some cities may show a landmark or a map instead of a skyline.

---

## 5. What `app.py` does with the answers

1. `find_place` → `place` (name, country, latitude, longitude).
2. `get_forecast` → `current` values and the `hourly` lists.
3. **Next 12 hours:** the hourly list starts at midnight, so we search for the current hour and take 12 hours from there. Hour numbers become labels like `10 AM`, `1 PM`.
4. **Words from numbers** (small helper functions):
   * `weather_code` → `WEATHER_CODES` table ("Partly cloudy")
   * wind speed → `wind_text` ("Gentle breeze")
   * wind degrees → `COMPASS` (220° → "South-West")
   * pressure → `pressure_text` (Low / Normal / High)
   * cloud % → `cloud_text`
5. `find_city_image` → photo URL.
6. Everything is put in one dictionary and sent with `jsonify`.

## 6. What `script.js` does with the answer

1. `loadWeather(city)` calls `fetch("/api/weather?city=...")` and waits (`async / await`).
2. `response.json()` turns the answer into a JavaScript object.
3. If Flask sent an error (`400`, `404`, `502`), the message is shown in the red box.
4. Otherwise `showWeather(data)` writes each value into its element, picks the icon, sets the photo (`setHeroImage`) and calls `drawChart` (Chart.js) for the 12 rain bars.
5. The **Refresh** button simply calls `loadWeather` again with the current city.

## 7. Error messages

| Situation | Where it is detected | Message on the page |
|---|---|---|
| Nothing typed / fewer than 2 letters | `validateCity` in `script.js` (no request is sent) and `api_weather` | Please enter a city name (at least 2 letters). |
| No known city starts with the typed letters (e.g. `jasd` while typing) | `hasCityStartingWith` in `script.js` (no `/api/suggest` request is sent) | No message - the suggestion list stays closed |
| Name is not in `static/data/cities.json` (e.g. `jasd`) | `isKnownCity` in `script.js` (no request is sent) | "jasd" is not in the city list. Please check the spelling. |
| Digits or symbols in the name (`Hyd123`, `@@@`), or longer than 60 characters | `validateCity` in `script.js` and `api_weather` | City name can only contain letters, spaces, - ' and . |
| City does not exist | `find_place` (no `results`) | City not found. Please check the spelling. |
| Suggestions fail (offline, API down) | `api_suggest` returns 502 | No message – the suggestion list just stays closed |
| No internet / API down / timeout | `requests.RequestException` in `api_weather` | Could not reach the weather service. Check your internet. |
| Wikipedia has no photo or fails | `find_city_image` | No message – default skyline is shown. |
