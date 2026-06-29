# Tallinja API

Unofficial JSON API for **Malta Public Transport (Tallinja)** bus-stop departure
boards. It mirrors the public timetable page —
`service-information.publictransport.com.mt/timetable?bus_stop=<code>` (the page
behind the QR codes on bus-stop signage) — and serves it as clean, structured JSON.

> ⚠️ Unofficial. This scrapes a public page; markup changes at the origin can
> break parsing. See **Verifying the parser** below.

## How it works

```
HTTP request ──▶ FastAPI ──▶ service ──▶ cache (TTL) ─▶ fetcher ─▶ origin board (HTML)
                                  │                         │
                                  └───── parser ◀───────────┘
                                         (HTML → Departure[])
```

- **`bus_stop`** in the origin URL is the stop **code** — the number printed on
  the pole / QR sign (e.g. `1090`). It is the only input the API needs.
- The board is **server-rendered HTML**, so no headless browser is required.
- Responses are cached per stop for a short TTL (default 25s) so the origin
  isn't hit on every request while still feeling "live".

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/stops/{stop_code}/departures` | Upcoming departures for a stop |
| `GET` | `/health` | Liveness/version |
| `GET` | `/docs` | Interactive OpenAPI docs |

### Example

```bash
curl http://localhost:8000/api/v1/stops/1090/departures
```

```jsonc
{
  "stop": { "code": "1090", "name": "Valletta, Bus Terminus" },
  "retrieved_at": "2026-06-29T20:40:00Z",
  "cached": false,
  "departures": [
    {
      "route": "13",
      "destination": "Marsa",
      "scheduled": "20:48",
      "estimated": "20:51",
      "minutes_away": null,
      "realtime": true
    }
  ]
}
```

Errors share one shape: `{ "error": "<code>", "detail": "<message>" }` with
`invalid_stop_code` (400), `stop_not_found` (404), and `upstream_unavailable` /
`parse_error` (502).

## Run it

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

Configuration is via env vars (prefix `TALLINJA_`), e.g. `TALLINJA_CACHE_TTL_SECONDS=10`.
See `app/config.py`.

## Verifying the parser ⚠️

The parser in `app/parser.py` targets the *documented* board structure (route •
destination • scheduled/estimated time). The build environment used to create
this project **cannot reach the origin host** (egress policy), so the exact live
markup was not confirmed. The extraction is therefore **layout-tolerant** — it
works off text patterns (route tokens, `HH:MM`, `N min`, "Due") rather than
brittle CSS selectors.

To lock it to production:

1. Save a real page: `curl 'https://service-information.publictransport.com.mt/timetable?bus_stop=1090' > tests/fixtures/stop_1090.html`
2. Run `pytest` and adjust `_iter_departure_rows` / `_extract_stop_name` if needed.
3. The public function `parse_board(html, code)` and its return types stay the same.

## Tests

```bash
pytest          # parser + API (origin mocked with respx), 13 tests
ruff check .
```
