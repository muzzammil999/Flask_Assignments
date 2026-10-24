/*
  script.js - runs in the BROWSER.

  How the API fetching works from this side:
    1. You type a city and press Search.
    2. loadWeather() calls OUR Flask server:  fetch("/api/weather?city=Berlin")
    3. Flask calls the 3 outside APIs (geocoding, forecast, Wikipedia) and sends back ONE JSON answer.
    4. showWeather() puts every value from that JSON into the page.
  The browser never talks to Open-Meteo or Wikipedia directly - only to our Flask server.

  REFERENCE CITY used in the examples below: Hyderabad, Telangana, India.

  Flask topics seen from the browser side:
    - the page itself comes from the Flask route "/" (render_template + Jinja url_for)
    - this file is a STATIC file served from /static/js/script.js
    - fetch("/api/weather?city=...") is a GET request; Flask reads it with request.args
    - Flask answers with JSON plus a status code (200, 400, 404, 502) and we react to it
    - while you type, fetch("/api/suggest?q=Hyd") fills the city-name suggestion list
*/

// ===== Page elements we need (found once by their id / class) =====
const form = document.getElementById("search-form");          // the search form in the top bar
const cityInput = document.getElementById("city-input");
const countrySelect = document.getElementById("country-select");      // the text box where you type the city
const refreshBtn = document.getElementById("refresh-btn");    // the Refresh button
const searchBtn = document.querySelector(".btn-search");      // the Search button
const errorBox = document.getElementById("error-box");        // the red box used for error messages
const heroImg = document.getElementById("hero-img");          // the picture in the top card
const suggestBox = document.getElementById("suggestions");    // the dropdown list under the search box

let currentCity = "Berlin";                                   // the city shown now (Refresh reloads this one)
let currentCountry = "";                                      // country of the shown city (Refresh sends it back)
let currentState = "";                                        // state of the shown city (Refresh sends it back)
let rainChart = null;                                         // the Chart.js chart object (created later)
let suggestions = [];                                         // the suggestions now in the dropdown
let activeIndex = -1;                                         // which suggestion is highlighted (-1 = none)
let suggestTimer = null;                                      // timer used to wait until typing pauses
let suggestRequest = null;                                    // AbortController of the running suggestion request
const DEFAULT_IMAGE = heroImg.getAttribute("src");            // the default skyline picture path

// ===== Small helper: put text into the element with this id =====
/**
 * Put plain text into one element of the page.
 *
 * Why textContent: it inserts TEXT only (never HTML), so text coming from a server can
 * not inject tags or scripts into the page.
 *
 * @param {string} id   - the id attribute of the element, e.g. "city".
 * @param {string|number} text - what to show, e.g. "Hyderabad" or 28.
 * @returns {void}
 * @example setText("country", "India");
 */
function setText(id, text) {
  document.getElementById(id).textContent = text;             // replace the element's text
}

// ===== Weather icons: small SVG drawings built as text (box size 134 x 118) =====
/**
 * Build the SVG drawing of a sun: eight rays around a filled circle.
 *
 * The rays use a fixed list of 8 directions (no maths functions). A ray starts at
 * r + 9 from the centre and ends at r + 17, so there is a small gap around the circle.
 *
 * @param {number} cx - x position of the sun's centre inside the SVG box.
 * @param {number} cy - y position of the sun's centre inside the SVG box.
 * @param {number} r  - radius of the yellow circle.
 * @returns {string} SVG markup (text) to be placed inside an <svg> element.
 */
function sunSvg(cx, cy, r) {                                  // draw a sun: centre (cx, cy) and radius r
  // The 8 ray directions written out by hand as [x, y] steps (no sin / cos needed):
  // right, down-right, down, down-left, left, up-left, up, up-right.
  const directions = [[1, 0], [0.7, 0.7], [0, 1], [-0.7, 0.7], [-1, 0], [-0.7, -0.7], [0, -1], [0.7, -0.7]];
  let rays = "";                                              // will hold the 8 ray lines
  for (const [dx, dy] of directions) {                        // one ray per direction
    const x1 = cx + dx * (r + 9);                             // ray start (x)
    const y1 = cy + dy * (r + 9);                             // ray start (y)
    const x2 = cx + dx * (r + 17);                            // ray end (x)
    const y2 = cy + dy * (r + 17);                            // ray end (y)
    rays += `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"/>`; // add the line
  }
  return `<g stroke="#fcc419" stroke-width="5" stroke-linecap="round">${rays}</g>
          <circle cx="${cx}" cy="${cy}" r="${r}" fill="#fcc419"/>`; // rays + yellow circle
}

/**
 * Build the SVG drawing of a cloud: three circles on a flat rectangle.
 *
 * @param {number} dx - how far to move the cloud to the right (negative = left).
 * @param {number} dy - how far to move the cloud down (negative = up).
 * @returns {string} SVG markup (text) for the cloud.
 */
function cloudSvg(dx, dy) {                                   // draw a cloud, moved by dx / dy
  return `<g fill="#b6d5fb" transform="translate(${dx},${dy})">
    <rect x="47" y="88" width="66" height="20"/>
    <circle cx="47" cy="90" r="18"/><circle cx="80" cy="80" r="23"/><circle cx="113" cy="90" r="18"/></g>`; // 3 circles + a flat bottom
}

/**
 * DROPS - ready-made SVG text: three slanted blue rain drops that sit under a cloud.
 * Used by heroIconSvg() for drizzle, rain, showers and snow codes.
 */
const DROPS = `<g stroke="#3d93f7" stroke-width="5" stroke-linecap="round">
  <line x1="62" y1="104" x2="58" y2="114"/><line x1="82" y1="104" x2="78" y2="114"/>
  <line x1="102" y1="104" x2="98" y2="114"/></g>`;            // three blue rain drops
/**
 * MOON - ready-made SVG text: a yellow crescent moon, used for clear nights.
 * Used by heroIconSvg() and (scaled down) for partly cloudy nights.
 */
const MOON = `<path d="M70 14a38 38 0 1 0 40 58A44 44 0 0 1 70 14z" fill="#fcd96b"/>`; // a yellow moon

/**
 * Choose and build the big weather icon of the top card.
 *
 * The WMO weather code (sent by Flask as "weather_code") decides the picture:
 *   0, 1        clear sky            -> sun by day, moon by night
 *   2           partly cloudy        -> sun/moon + cloud
 *   51 - 86     drizzle/rain/snow    -> cloud + drops
 *   95 and up   thunderstorm         -> cloud + lightning bolt
 *   anything else (3 overcast, 45/48 fog ...) -> plain cloud
 *
 * @param {number}  code  - WMO weather code, e.g. 2 for "Partly cloudy".
 * @param {boolean} isDay - true in daylight, false at night.
 * @returns {string} a complete <svg viewBox="0 0 134 118"> ... </svg> text.
 * @example heroIconSvg(2, true); // sun + cloud for a partly cloudy day in Hyderabad
 */
function heroIconSvg(code, isDay) {                           // pick the big icon from the weather code
  let inner = "";                                             // the drawing pieces
  if (code === 0 || code === 1) inner = isDay ? sunSvg(67, 56, 30) : MOON;   // clear sky: sun or moon
  else if (code === 2) inner = (isDay ? sunSvg(48, 40, 29) : `<g transform="scale(.7)">${MOON}</g>`) + cloudSvg(0, 0); // partly cloudy: sun/moon + cloud
  else if (code >= 51 && code <= 86) inner = cloudSvg(0, -14) + DROPS;       // drizzle, rain, snow: cloud + drops
  else if (code >= 95) inner = cloudSvg(0, -14) + `<path d="M76 88l-10 16h9l-5 12 15-18h-10l6-10z" fill="#fcc419"/>`; // thunderstorm: cloud + lightning
  else inner = cloudSvg(0, -6);                               // everything else (overcast, fog): cloud
  return `<svg viewBox="0 0 134 118">${inner}</svg>`;         // wrap the pieces in an <svg> tag
}

/**
 * Build the small icon of the "Day / Night" badge (sun for day, moon for night).
 *
 * @param {boolean} isDay - true = daylight, false = night.
 * @returns {string} SVG markup placed inside the badge's <svg id="day-icon"> element.
 */
function dayIconSvg(isDay) {                                  // small sun or moon inside the "Day" badge
  return isDay
    ? `<circle cx="12" cy="12" r="5" fill="#fcc419"/><g stroke="#fcc419" stroke-width="2" stroke-linecap="round"><line x1="12" y1="1.5" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22.5"/><line x1="1.5" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22.5" y2="12"/><line x1="4.6" y1="4.6" x2="6.4" y2="6.4"/><line x1="17.6" y1="17.6" x2="19.4" y2="19.4"/><line x1="4.6" y1="19.4" x2="6.4" y2="17.6"/><line x1="17.6" y1="6.4" x2="19.4" y2="4.6"/></g>` // sun
    : `<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z" fill="#fcc419"/>`; // moon
}

// ===== Change the picture in the top card (API 3 gives the URL) =====
/**
 * Show the city photo in the top card, with a safe fallback.
 *
 * Flow: the server sends a Wikipedia picture URL (API 3) or "". An empty URL, or a URL
 * that fails to load, falls back to the default skyline that came with the page
 * (DEFAULT_IMAGE, served by Flask from /static/img/skyline.jpg).
 *
 * @param {string} url - picture URL from Flask, or "" when there is no photo.
 * @returns {void}
 */
function setHeroImage(url) {
  /* Error handler: runs only if the browser cannot load the photo (broken link, offline).
     It switches to the default skyline. It first removes itself (onerror = null) so a
     failing default image can never cause an endless loop of retries. */
  heroImg.onerror = function () {                             // if the photo cannot load...
    heroImg.onerror = null;                                   // ...stop this handler from repeating
    heroImg.src = DEFAULT_IMAGE;                              // ...and show the default skyline
  };
  heroImg.src = url || DEFAULT_IMAGE;                         // use the city photo, or the default if url is ""
}

// ===== "Partly cloudy" -> "Partly Cloudy" =====
/**
 * Make the first letter of every word a capital letter.
 *
 * The regular expression /\b\w/g means: "g" = every match, \b = a word boundary,
 * \w = one letter/digit, so only the first character of each word is matched.
 *
 * @param {string} text - e.g. "partly cloudy".
 * @returns {string} e.g. "Partly Cloudy".
 */
function titleCase(text) {
  return text.replace(/\b\w/g, letter => letter.toUpperCase()); // capital letter at the start of every word
}

// ===== Put the JSON from Flask into the page =====
/**
 * Write every value of the server's JSON answer into the page (the "render" step).
 *
 * It only reads the object and updates elements; it never talks to the server.
 * Groups of work, in order:
 *   1. top card   - city, photo, country, local time, big temperature, condition, icons, badge
 *   2. row 1      - Temperature, Humidity, Current Rain, Cloud Cover cards
 *   3. row 2      - Wind Speed, Wind Direction (arrow is rotated), Pressure cards
 *   4. details    - the "Weather Details" table rows
 *   5. chart      - drawChart() for the 12 hourly rain bars
 *
 * @param {Object} w - JSON from GET /api/weather, built by build_weather() in app.py.
 * @param {string} w.city        - e.g. "Hyderabad".
 * @param {string} w.country     - e.g. "India".
 * @param {string} w.image       - photo URL or "".
 * @param {string} w.local_time  - e.g. "Thursday, 15 Oct 2026 · 10:24 AM".
 * @param {number} w.temperature - degrees Celsius.
 * @param {number} w.weather_code - WMO code.
 * @param {boolean} w.is_day     - day (true) or night (false).
 * @param {Array<{time: string, rain: number}>} w.hourly - next 12 hours of rain.
 *        (all other fields are documented at build_weather() in app.py)
 * @returns {void}
 */
function showWeather(w) {                                     // w = the JSON object from /api/weather
  setText("city", w.city);                                    // city name in the big title
  setHeroImage(w.image);                                      // city photo (API 3)
  setText("country", w.country);                              // country name
  setText("local-time", w.local_time);                        // the city's date and time
  setText("temp-big", w.temperature);                         // big temperature number
  setText("condition", titleCase(w.condition));               // "Partly Cloudy"
  document.getElementById("hero-icon").innerHTML = heroIconSvg(w.weather_code, w.is_day); // big weather icon
  document.getElementById("day-icon").innerHTML = dayIconSvg(w.is_day);                   // small day/night icon
  setText("day-text", w.is_day ? "Day" : "Night");            // badge text

  setText("temp-card", w.temperature + "°C");                 // Temperature card value
  setText("feels", "Feels like " + w.feels_like + "°C");      // Temperature card small text
  setText("humidity", w.humidity + "%");                      // Humidity card value
  setText("rain", w.rain.toFixed(1) + " mm");                 // Current Rain card value (one decimal)
  setText("rain-text", w.rain > 0 ? "Raining right now" : "No rain right now"); // Current Rain small text
  setText("cloud", w.cloud_cover + "%");                      // Cloud Cover card value
  setText("cloud-text", w.cloud_text);                        // Cloud Cover small text

  setText("wind", w.wind_speed + " km/h");                    // Wind Speed card value
  setText("wind-text", w.wind_text);                          // Wind Speed small text, e.g. "Gentle breeze"
  setText("wind-dir", w.wind_short);                          // Wind Direction card value, e.g. "SW"
  setText("wind-name", w.wind_name);                          // Wind Direction small text, e.g. "South-West"
  document.getElementById("wind-arrow").style.transform = `rotate(${w.wind_direction + 180}deg)`; // arrow points where the wind blows TO
  setText("pressure", w.pressure_msl + " hPa");               // Pressure card value
  setText("pressure-text", w.pressure_text);                  // Pressure card small text (Low/Normal/High)

  setText("d-code", w.condition + " (" + w.weather_code + ")"); // Weather Details: code row
  setText("d-rain", w.rain.toFixed(1) + " mm");               // Weather Details: rain row
  setText("d-cloud", w.cloud_cover + "%");                    // Weather Details: cloud row
  setText("d-msl", w.pressure_msl + " hPa");                  // Weather Details: sea-level pressure row
  setText("d-surface", w.surface_pressure + " hPa");          // Weather Details: ground pressure row
  setText("d-wind", w.wind_short + " (" + w.wind_direction + "°)"); // Weather Details: wind direction row
  setText("d-day", w.is_day ? "Yes" : "No");                  // Weather Details: Is Day row

  drawChart(w.hourly);                                        // draw the 12 rain bars
}

// ===== Hourly rainfall bar chart (uses the Chart.js library) =====
/**
 * Draw the "Hourly Rainfall" bar chart with the Chart.js library.
 *
 * A chart object is kept in the global variable rainChart. A <canvas> can hold only one
 * chart, so the old chart is destroyed before a new one is created; otherwise the old
 * bars would keep flickering under the new ones.
 *
 * Options in short: bar type, no legend (one data set), hover text "0.5 mm",
 * y-axis starts at 0 and shows at least up to 2.0 in steps of 0.5 with one decimal.
 *
 * @param {Array<{time: string, rain: number}>} hourly - 12 items, e.g.
 *        [{time: "10 AM", rain: 0.1}, {time: "11 AM", rain: 0}, ...]
 *        time becomes the x-axis label, rain (mm) becomes the bar height.
 * @returns {void}
 */
function drawChart(hourly) {                                  // hourly = [{time: "10 AM", rain: 0.1}, ...]
  if (rainChart) rainChart.destroy();                         // remove the old chart before drawing a new one

  rainChart = new Chart(document.getElementById("rain-chart"), { // create a chart on the <canvas>
    type: "bar",                                              // bar chart
    data: {
      labels: hourly.map(h => h.time),                        // x-axis labels: "10 AM", "11 AM", ...
      datasets: [{
        data: hourly.map(h => h.rain),                        // bar heights: rain in mm
        backgroundColor: "#55a2fc",                           // bar colour (from the design image)
        borderRadius: 3,                                      // slightly rounded bar tops
        barPercentage: 0.5,                                   // bar width compared with its slot
        categoryPercentage: 1                                 // each slot uses the full width
      }]
    },
    options: {
      responsive: true,                                       // chart resizes with the card
      maintainAspectRatio: false,                             // chart fills the height we gave it in CSS
      animation: { duration: 400 },                           // short grow animation
      plugins: {
        legend: { display: false },                           // hide the legend (only one data set)
        tooltip: { callbacks: { label: item => item.parsed.y + " mm" } } // hover text: "0.5 mm"
      },
      scales: {
        x: {
          grid: { display: false },                           // no vertical grid lines
          border: { display: false },                         // no axis line
          ticks: { color: "#7a838d", font: { family: "Inter", size: 12 } } // label style
        },
        y: {
          beginAtZero: true,                                  // y-axis starts at 0
          suggestedMax: 2,                                    // at least up to 2.0 (grows if rain is heavier)
          border: { display: false },                         // no axis line
          grid: { color: "#ececec" },                         // light horizontal grid lines
          ticks: {
            stepSize: 0.5,                                    // 0.0, 0.5, 1.0, 1.5, 2.0
            color: "#757d86",                                 // label colour
            font: { family: "Inter", size: 12 },              // label font
            callback: value => Number(value).toFixed(1)       // always one decimal: 0.0, 0.5 ...
          }
        }
      }
    }
  });
}

// ===== THE API FETCH: ask our Flask server for a city's weather (async / await + fetch) =====
/**
 * THE API FETCH - ask our Flask server for one city's weather and show the result.
 *
 * Request  : GET /api/weather?city=<city>  (the city is made URL-safe with
 *            encodeURIComponent, so "New York" becomes "New%20York").
 * Flask    : api_weather() in app.py reads it with request.args.get("city").
 * Response : 200 -> JSON weather;  400 / 404 / 502 -> {"error": "message"}.
 *
 * Steps    : hide the old error and disable the buttons -> fetch and wait (await) ->
 *            read JSON -> if response.ok is false throw the server's message ->
 *            showWeather() -> remember the city -> finally re-enable the buttons.
 *
 * Why try / catch / finally: a network failure makes fetch() throw, and the
 * "throw new Error" above also lands in catch, so ONE place shows every error.
 * finally always runs, so the buttons can never stay disabled.
 *
 * @param {string} city - e.g. "Hyderabad".
 * @param {string} [country] - e.g. "India". Optional; sent when a suggestion was clicked.
 * @param {string} [state]   - e.g. "Telangana". Optional; sent when a suggestion was clicked.
 * @returns {Promise<void>} resolves when the page has been updated (or the error shown).
 * @example loadWeather("Hyderabad", "India", "Telangana"); // Hyderabad, Telangana, India
 */
async function loadWeather(city, country = "", state = "") {
  errorBox.hidden = true;                                     // hide any old error message
  searchBtn.disabled = true;                                  // stop double clicks while loading
  refreshBtn.disabled = true;                                 // stop double clicks while loading

  try {                                                       // errors below jump to "catch"
    let url = "/api/weather?city=" + encodeURIComponent(city);  // the base address with the city
    if (country) url += "&country=" + encodeURIComponent(country); // exact country (after a suggestion click / Refresh)
    if (state) url += "&state=" + encodeURIComponent(state);       // exact state (after a suggestion click / Refresh)
    const response = await fetch(url);                        // 1) send the request and wait for Flask
    const data = await response.json();                       // 2) read the JSON answer

    if (!response.ok) {                                       // 3) Flask answered with an error code (400, 404, 502)
      throw new Error("Error " + response.status + ": " + (data.error || "Something went wrong.")); //    jump to catch with the status code + Flask's message
    }

    showWeather(data);                                        // 4) success: show everything on the page
    currentCity = data.city;                                  //    remember the city for the Refresh button
    currentCountry = data.country;                            //    ...its country
    currentState = data.state;                                //    ...and its state
    cityInput.value = "";                                     //    clear the search box
  } catch (error) {                                           // network failure or the error thrown above
    errorBox.textContent = error.message;                     // put the message in the red box
    errorBox.hidden = false;                                  // show the red box
  } finally {                                                 // always runs, success or not
    searchBtn.disabled = false;                               // enable the Search button again
    refreshBtn.disabled = false;                              // enable the Refresh button again
  }
}

// ===== City name suggestions (shown while typing) =====

/**
 * Close the suggestion dropdown and forget the highlighted item.
 *
 * @returns {void}
 */
function hideSuggestions() {
  suggestBox.hidden = true;                                   // hide the list
  suggestBox.innerHTML = "";                                  // remove the old items
  suggestions = [];                                           // forget the data
  activeIndex = -1;                                           // nothing highlighted
  cityInput.setAttribute("aria-expanded", "false");           // tell screen readers the list is closed
}

/**
 * Highlight one suggestion (used by the Up / Down arrow keys).
 *
 * @param {number} index - position in the list; -1 removes the highlight.
 * @returns {void}
 */
function setActive(index) {
  activeIndex = index;                                        // remember the position
  Array.from(suggestBox.children).forEach(function (item, i) { // go through every <li>
    item.classList.toggle("active", i === index);             // only the chosen one gets the "active" class
  });
}

/**
 * The user picked a suggestion (mouse click or Enter key): load exactly that place.
 *
 * The state and country are sent too, so "Hyderabad, Telangana, India" is loaded and not
 * another city with the same name (for example Hyderabad in Pakistan).
 *
 * @param {{name: string, state: string, country: string, label: string}} place - the chosen suggestion.
 * @returns {void}
 */
function chooseSuggestion(place) {
  hideSuggestions();                                          // close the dropdown
  cityInput.value = place.label;                              // show the full name in the box for a moment
  if (countrySelect && countrySelect.value && place.country !== countrySelect.value) {
    cityInput.value = place.name;
    loadWeather(place.name, countrySelect.value);
  } else {
    loadWeather(place.name, place.country, place.state);
  }        // fetch that exact place (also clears the box on success)
}

/**
 * Fill the dropdown with the suggestions that came from Flask.
 *
 * Every item is built with textContent (never innerHTML), so server text can not inject HTML.
 * Each item shows the city in bold and "state, country" in small grey text.
 *
 * @param {Array<{name: string, state: string, country: string, label: string}>} list - from /api/suggest.
 * @returns {void}
 */
function showSuggestions(list) {
  suggestBox.innerHTML = "";                                  // remove the old items
  suggestions = list;                                         // remember the data
  activeIndex = -1;                                           // nothing highlighted yet
  if (list.length === 0) {                                    // nothing to show
    hideSuggestions();                                        // keep the list closed
    return;                                                   // stop here
  }
  list.forEach(function (place) {                             // one <li> per suggestion
    const item = document.createElement("li");                // the list item
    item.setAttribute("role", "option");                      // accessibility role
    const city = document.createElement("span");              // line 1: the city
    city.className = "s-city";                                // style hook
    city.textContent = place.name;                            // e.g. "Hyderabad"
    const where = document.createElement("span");             // line 2: state and country
    where.className = "s-place";                              // style hook
    where.textContent = [place.state, place.country].filter(Boolean).join(", "); // "Telangana, India"
    item.append(city, where);                                 // put both lines in the item
    item.addEventListener("mousedown", function (event) {     // mousedown fires before the input loses focus
      event.preventDefault();                                 // keep the focus in the input
      chooseSuggestion(place);                                // load this place
    });
    suggestBox.appendChild(item);                             // add the item to the list
  });
  suggestBox.hidden = false;                                  // show the list
  cityInput.setAttribute("aria-expanded", "true");            // tell screen readers the list is open
}

/**
 * Ask Flask for suggestions: GET /api/suggest?q=<typed letters>.
 *
 * A request that is still running is cancelled first (AbortController), so a slow old
 * answer can never overwrite a newer one. Errors are ignored on purpose: suggestions are
 * only a help, the normal Search button always works.
 *
 * @param {string} text - the letters typed so far, e.g. "Hyd".
 * @returns {Promise<void>} resolves when the list has been updated (or the error ignored).
 */
async function loadSuggestions(text) {
  if (suggestRequest) suggestRequest.abort();                 // cancel the older request
  suggestRequest = new AbortController();                     // a new cancel switch for this request
  try {                                                       // errors jump to "catch"
    const response = await fetch("/api/suggest?q=" + encodeURIComponent(text), { signal: suggestRequest.signal }); // ask Flask
    if (!response.ok) { hideSuggestions(); return; }          // 400 / 502: just close the list
    showSuggestions(await response.json());                   // show the list from the JSON answer
  } catch (error) {                                           // cancelled request or network failure
    if (error.name !== "AbortError") hideSuggestions();       // a cancel is normal; real failures close the list
  }
}

/**
 * Typing handler - runs after every key the user types in the city box.
 *
 * "Debounce": it waits 250 ms after the LAST key before asking Flask, so typing "Hyderabad"
 * sends one request instead of nine. Fewer than 2 letters closes the list (the server
 * also refuses them with status 400).
 *
 * @returns {void}
 */
cityInput.addEventListener("input", function () {
  clearTimeout(suggestTimer);                                 // restart the waiting time
  const text = cityInput.value.trim();                        // typed text without spaces at the ends
  if (text.length < 2) {                                      // too short to suggest anything
    if (suggestRequest) suggestRequest.abort();               // forget any running request
    hideSuggestions();                                        // close the list
    return;                                                   // stop here
  }
  if (!hasCityStartingWith(text)) {                           // no known city starts with these letters
    if (suggestRequest) suggestRequest.abort();               // forget any running request
    hideSuggestions();                                        // close the list
    return;                                                   // NO request is sent to Flask
  }
  if (!hasCityStartingWith(text)) {                           // no known city starts with these letters (e.g. "jasd")
    if (suggestRequest) suggestRequest.abort();               // forget any running request
    hideSuggestions();                                        // close the list
    return;                                                   // NO request is sent to Flask
  }
  suggestTimer = setTimeout(function () { loadSuggestions(text); }, 250); // ask Flask once typing pauses
});

/**
 * Keyboard handler for the city box: Down / Up move the highlight, Enter picks the
 * highlighted suggestion, Escape closes the list. Without a highlighted item Enter
 * behaves as before and submits the form.
 *
 * @param {KeyboardEvent} event - the key press.
 * @returns {void}
 */
cityInput.addEventListener("keydown", function (event) {
  if (suggestBox.hidden) return;                              // list closed: normal typing
  if (event.key === "ArrowDown") {                            // move down (wraps to the top)
    event.preventDefault();                                   // stop the text cursor from jumping
    setActive((activeIndex + 1) % suggestions.length);
  } else if (event.key === "ArrowUp") {                       // move up (wraps to the bottom)
    event.preventDefault();
    setActive((activeIndex - 1 + suggestions.length) % suggestions.length);
  } else if (event.key === "Enter" && activeIndex >= 0) {     // a suggestion is highlighted
    event.preventDefault();                                   // do not submit the form
    chooseSuggestion(suggestions[activeIndex]);               // load that place
  } else if (event.key === "Escape") {                        // close the list
    hideSuggestions();
  }
});

/**
 * Close the dropdown when the box loses focus (the user clicked somewhere else).
 * Clicking a suggestion is handled earlier by its "mousedown", so it is not lost.
 *
 * @returns {void}
 */
cityInput.addEventListener("blur", hideSuggestions);

// ===== Known city names (loaded once from static/data/cities.json) =====
/**
 * The list of known cities. A name that is not in this list is refused in the browser,
 * so no request is sent to Flask (and nothing appears in the Flask log).
 * knownCities stays null until the file is loaded; while it is null (or if loading fails)
 * the check is skipped and the server decides, so the page never breaks.
 */
let knownCities = null;                                       // Set of normalised city names (null = not loaded)
let knownCityList = [];                                       // the same names as an array, for the "starts with" check
let cityCountryPairs = [];                                    // city/country pairs used to validate country selection

/**
 * Make a name comparable: lower case, no accents, no . ' marks, hyphen = space.
 * "München" -> "munchen", "St. John's" -> "st johns", "Saint-Denis" -> "saint denis".
 *
 * @param {string} text - a city name as typed or as stored in the file.
 * @returns {string} the simplified name used for comparing.
 */
function normalizeName(text) {
  return text.toLowerCase()                                   // ignore capital letters
    .normalize("NFD").replace(/\p{M}/gu, "")                  // remove accents (u + ¨ -> u)
    .replace(/[.'’]/g, "")                                    // remove dots and apostrophes
    .replace(/-/g, " ")                                       // hyphen counts as a space
    .replace(/\s+/g, " ").trim();                             // single spaces only
}

/**
 * Load static/data/cities.json once, when the page opens.
 * Errors are ignored on purpose: without the file the page simply works as before.
 *
 * @returns {Promise<void>} resolves when the list is ready (or loading failed).
 */
async function loadCityList() {
  try {
    const response = await fetch("/static/data/cities.json");  // the file served by Flask from /static
    const data = await response.json();                        // {"countries": [...], "cities": [["Hyderabad","India"], ...]}
    knownCityList = [...new Set(data.cities.map(c => normalizeName(c[0])))]; // unique normalised names
    knownCities = new Set(knownCityList);                      // a Set gives an instant lookup
  } catch (error) {
    knownCities = null;                                        // keep the check switched off
  }
}

/**
 * Is this city name in the list?  (true when the list is not loaded, so the server decides)
 *
 * @param {string} city - e.g. "Hyderabad".
 * @returns {boolean} true = known (or unknown because no list), false = definitely not in the list.
 */
function isKnownCity(city) {
  return knownCities === null || knownCities.has(normalizeName(city));
}

/**
 * Does any known city START with these letters? Used to skip /api/suggest for text like "jasd".
 *
 * @param {string} text - the letters typed so far.
 * @returns {boolean} true = suggestions can exist (or no list), false = nothing can match.
 */
function hasCityStartingWith(text) {
  if (knownCities === null) return true;                       // no list: let the server suggest
  const start = normalizeName(text);                           // same simplification as the list
  return knownCityList.some(name => name.startsWith(start));   // any name that begins with the typed letters
}

loadCityList();                                                // start loading the list now

// ===== Browser-side validation of the city name (runs BEFORE any request is sent) =====
/**
 * Check the city name typed by the user.
 *
 * Rules: 2 to 60 characters; only letters (any language), spaces, dot, apostrophe and
 * hyphen; it must start with a letter. Digits and symbols such as @ # < > are refused.
 * The server checks the same rule again in api_weather() because it never trusts the browser.
 *
 * @param {string} city - the text from the search box.
 * @returns {string} "" when the name is valid, otherwise the error message to show.
 * @example validateCity("Hyd123"); // "City name can only contain letters, spaces, - ' and ."
 */
function validateCity(city) {
  city = city.trim().replace(/\s+/g, " ");                    // remove extra spaces
  if (city.length < 2) return "Please enter a city name (at least 2 letters)."; // empty or too short
  if (city.length > 60) return "City name is too long (maximum 60 characters)."; // too long
  if (!/^\p{L}[\p{L} .'-]*$/u.test(city))                    // letters, space, dot, apostrophe, hyphen only
    return "City name can only contain letters, spaces, - ' and .";
  return "";                                                  // "" means the name is valid
}

// ===== Button events =====
/**
 * Search form handler - runs when Search is clicked or Enter is pressed in the text box.
 *
 * event.preventDefault() stops the browser's normal form submit, which would reload the
 * whole page. Instead we do the fetch ourselves (no page reload).
 * This is the browser-side validation: an empty box shows a message without contacting
 * the server. (The server validates again in api_weather(); it never trusts the browser.)
 *
 * @param {SubmitEvent} event - the submit event created by the browser.
 * @returns {void}
 */
form.addEventListener("submit", function (event) {            // when Search is clicked or Enter is pressed
  event.preventDefault();                                     // stop the browser from reloading the page
  const city = cityInput.value.trim().replace(/\s+/g, " ");   // typed text, extra spaces removed
  hideSuggestions();                                          // close the dropdown
  const message = validateCity(city);                         // browser-side validation
  if (message) {                                              // invalid: show the message, do NOT call the server
    errorBox.textContent = message;                           // put the message in the red box
    errorBox.hidden = false;                                  // show the red box
    return;                                                   // stop here
  }
  const selectedCountry = countrySelect ? countrySelect.value : "";
  if (selectedCountry && !cityCountryPairs.some(item => normalizeName(item.city) === normalizeName(city) && item.country === selectedCountry)) {
    errorBox.textContent = "\"" + city + "\" is not in the selected country (" + selectedCountry + "). Choose a matching city or select All countries.";
    errorBox.hidden = false;
    return;
  }
  if (!isKnownCity(city)) {                                   // format is fine, but the city is not in cities.json
    errorBox.textContent = "\"" + city + "\" is not in the city list. Please check the spelling."; // red box message
    errorBox.hidden = false;                                  // show the red box
    return;                                                   // NO request is sent to Flask
  }
  loadWeather(city, selectedCountry);                         // valid and known: fetch this city in the selected country
});

/**
 * Refresh button handler - load the weather of the city that is shown right now again.
 * currentCity is updated by loadWeather() after every successful search.
 *
 * @returns {void}
 */
refreshBtn.addEventListener("click", function () {            // when Refresh is clicked
  loadWeather(currentCity, currentCountry, currentState);      // fetch the current city again (same state / country)
});

/* Start-up: this line runs once when the browser loads the script, so the page is never
   empty - it first shows the default city (currentCity, "Berlin"). */
loadWeather(currentCity);                                     // when the page opens, show Berlin
