# Teaching Guide: From Flask CRUD to an API

## Lesson Goal

Students already know how to build a Flask CRUD app, such as their Story app. This lesson reuses that knowledge and changes one main thing: **how the client and server communicate**.

By the end, students should be able to explain that both apps can use Flask, routes, validation, SQL, and CRUD. In the HTML version, Flask returns rendered pages. In the API version, Flask returns JSON and browser JavaScript updates the page.

## Start With What They Know

Ask students to recall one action from their Story CRUD app, such as adding a story:

1. The browser submits an HTML form.
2. Flask reads `request.form` and validates the values.
3. Flask saves the story in the database.
4. Flask redirects or renders an HTML page.
5. The browser displays the returned page.

Tell the class: **We are not learning CRUD again. We are changing the response and the client workflow.** The book shelf is the example domain; compare its two implementations to the Story app they already built.

## The Main Comparison

| Question | Familiar Flask CRUD app | Flask API + JavaScript |
| --- | --- | --- |
| Who sends the request? | Browser submits an HTML form | JavaScript calls `fetch()` |
| What data is sent? | Form fields (`request.form`) | JSON body (`request.get_json()`) |
| What does Flask return? | HTML, often followed by a redirect | JSON data and an HTTP status |
| Who updates the visible page? | Flask renders a new page | JavaScript changes the current page |
| What stays the same? | Flask routes, validation, database, CRUD | Flask routes, validation, database, CRUD |

**One-sentence takeaway:** An API is a defined way for another program, here browser JavaScript, to request data or actions; it is not a different database or a different kind of CRUD.

## Draw This Flow

### Server-rendered form

`Browser form -> Flask route -> validate -> MySQL -> redirect/HTML -> browser renders page`

### API request

`JavaScript fetch -> Flask API route -> validate JSON -> MySQL -> JSON + status -> JavaScript updates page`

Point out that MySQL is behind both flows. The browser does not connect to MySQL directly; Flask remains between the client and the database.

## Teach the API Vocabulary

Use one familiar operation to introduce each term:

- **Endpoint:** a URL and HTTP method together, such as `GET /api/books`.
- **Request:** the method, URL, headers, and optional body sent by the client.
- **JSON:** the data format used for the API request and response.
- **Status code:** the result of the request, such as `201` for a created book or `404` when a book is missing.
- **Client:** the program making the request. In this project, it is JavaScript running in the browser.

Avoid saying that an API is just a URL or that JSON is the API. The API is the agreed request-and-response contract.

## Route Map

| Method | Endpoint | CRUD action | Successful response |
| --- | --- | --- | --- |
| GET | `/api/books` | Read all | `200` + JSON array |
| GET | `/api/books/<id>` | Read one | `200` + JSON object |
| POST | `/api/books` | Create | `201` + created JSON object |
| PUT | `/api/books/<id>` | Update | `200` + JSON object |
| DELETE | `/api/books/<id>` | Delete | `204` + empty response |

The home page `GET /` is still HTML. The `/api/books` routes are the data interface used by JavaScript.

## Live Presentation Sequence

### 1. Compare the same action (5 minutes)

Open both versions side by side. Add a book in `flask_only`, then add one in `with_js`. Ask students what changed in the browser and what stayed the same on the server.

Expected answer: both validate and save a book. The first submits a form and receives a page/redirect; the second sends a fetch request and receives JSON while JavaScript updates the page.

### 2. Inspect one API request (10 minutes)

Open browser DevTools, select **Network**, and add a book in the JavaScript app. Inspect:

- Request URL and method: `POST /api/books`
- Request header: `Content-Type: application/json`
- Request payload: title, author, and status
- Response status: `201`
- Response body: the created book as JSON

Then visit `http://127.0.0.1:5001/api/books` directly. Explain that the browser is showing the API response body, not a rendered book-list page.

### 3. Trace the code from browser to database (15 minutes)

Follow one create request across the files:

1. In `with_js/static/app.js`, find `fetch()` in the form submit handler. `JSON.stringify(data)` makes the request body JSON.
2. In `with_js/app.py`, find `create_book()` at `@app.post('/api/books')`. Flask checks the content type, reads JSON, validates fields, and runs a parameterized insert.
3. Flask returns the created record with status `201`.
4. JavaScript reads the response, shows a message, then calls `loadBooks()` to refresh the visible list.

Contrast this with `flask_only/app.py`: it reads `request.form`, then uses `redirect(url_for('home'))`. The browser requests and displays a new page after the redirect.

### 4. Make the contract fail on purpose (10 minutes)

Try a title that is too short. The server rejects it with `400`; explain that browser checks are helpful but cannot replace server validation. Request an ID that does not exist to see `404`. Delete a book and inspect the `204` response, which has no response body.

### 5. Summarize the difference (5 minutes)

Ask students to complete these sentences:

- “In our old CRUD app, Flask returned ___.” (HTML or a redirect to HTML.)
- “In the API app, Flask returns ___.” (JSON and a status code.)
- “The page changes because ___.” (JavaScript reads the response and updates the DOM.)
- “The database is accessed by ___.” (Flask, not browser JavaScript.)

## Code Concepts to Emphasize

- `fetch()` sends an HTTP request; it does not talk directly to Python or MySQL.
- `Content-Type: application/json` tells Flask what format the request body uses.
- `request.get_json()` reads the JSON body; `jsonify()` creates a JSON response.
- SQL values use placeholders, keeping submitted values separate from SQL text.
- `400` means the request data is invalid; `404` means the requested resource was not found.
- The API response does not automatically change the page. JavaScript decides what to render.

## Misconceptions to Check

- **“An API is a new database.”** No. Both apps use MySQL; the API changes how a client communicates with Flask.
- **“The API is only for mobile apps.”** No. Any client that can make HTTP requests can use it, including browser JavaScript.
- **“JSON updates the page by itself.”** No. JavaScript reads JSON and updates the DOM.
- **“If the form checks the input, the server does not need validation.”** No. Clients can be bypassed, so Flask validates too.
- **“Every Flask route is an API endpoint.”** A route can return HTML or data. Here, the `/api/` routes return JSON; `/` serves the HTML page.

## Student Practice

Ask students to add a `genre` field to the book app. Have them trace all parts of the API contract: JavaScript payload, server validation, database schema, JSON response, and DOM rendering. Then ask them to identify how the corresponding form and Jinja display change in the server-rendered version.

For a smaller exercise, add a `GET /api/books/<id>` call to the page or test it directly and explain the difference between `200` and `404`.

## Exit Questions

1. What is the biggest difference between the Story CRUD app and this API version?
2. What does `fetch()` send, and what does Flask return?
3. Why does Flask validate JSON even if JavaScript checks the form?
4. Which part of the system reads or writes MySQL?
5. What does the browser receive from `GET /api/books`: HTML or JSON?

These are local classroom demonstrations: they have no login or CSRF protection and should not be put online as-is.