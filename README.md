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
  "stop": { "code": "1090", "name": "Naxxar" },
  "retrieved_at": "2026-06-29T20:40:00Z",
  "cached": false,
  "departures": [
    {
      "route": "31",
      "line_name": "Valletta - Bugibba",
      "minutes_away": 6,            // exact when live-tracked
      "display_time": "6 min",     // text exactly as shown on the board
      "realtime": true,            // green "active" row = live GPS
      "following_time": "+30 min"  // the departure after next, when shown
    },
    {
      "route": "103",
      "line_name": "Pembroke - Bidnija",
      "minutes_away": null,        // "+30 min" is a lower bound, not exact
      "display_time": "+30 min",
      "realtime": false,
      "following_time": null
    }
  ]
}
```

> The board shows **relative** times ("6 min", "+30 min"), not clock times.
> `+30 min` means "more than 30 minutes away", so `minutes_away` is `null` there
> while `display_time` preserves the exact text. `line_name` is the route's full
> name as displayed (both termini), not a single destination.

Errors share one shape: `{ "error": "<code>", "detail": "<message>" }` with
`invalid_stop_code` (400), `stop_not_found` (404), `upstream_unavailable` /
`parse_error` (502), and `upstream_circuit_open` (503, with a `Retry-After`
header — see Resilience below).

## Run it

```bash
pip install -e .          # pure-Python; no C compiler needed
uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

HTML parsing uses Python's built-in `html.parser` by default. For the faster
`lxml` backend (needs a C toolchain) install the extra — the parser uses it
automatically when present:

```bash
pip install -e ".[speed]"
```

Configuration is via env vars (prefix `TALLINJA_`), e.g. `TALLINJA_CACHE_TTL_SECONDS=10`.
See `app/config.py`.

## Parser & markup

### Fetching (TLS fingerprinting)

The origin runs bot protection that **fingerprints the TLS client (JA3)**: it
lets `curl` through but tarpits Python's `httpx` — the TLS handshake completes,
the request is sent, and the response is simply never returned (a read timeout).
Sending browser-like headers does **not** help, because the block is at the TLS
layer, not the HTTP layer.

So the fetcher has two backends (`TALLINJA_HTTP_BACKEND`):

| Value | Behaviour |
|-------|-----------|
| `auto` (default) | use the `curl` binary if present, else `httpx` |
| `curl` | always shell out to `curl` (works against the live origin) |
| `httpx` | always use `httpx` (used by tests; tarpitted by the live origin) |

For real traffic keep the default and make sure `curl` is installed. If you must
use a pure-Python client, swap in [`curl_cffi`](https://github.com/lexiforest/curl_cffi)
(`impersonate="chrome"`) which mimics a browser's TLS fingerprint.

### Parser & markup

`app/parser.py` targets the **real** page markup, captured in
`tests/fixtures/stop_1090.html`. The board is server-rendered HTML (Express),
so no headless browser is needed. The relevant elements:

| Data | Selector |
|------|----------|
| Stop name + code | `.station-text h1` → `"Naxxar - 1090"` |
| Departure row | `div.line-item` |
| Route number | `.line-number` (e.g. `31`, `N40`, `S30`, `TD12`) |
| Line name | `.line-name-container h2` |
| Live time | `.line-time-container-active` → `h4` (next), `h5` (following) |
| Static time | `.line-time-container` → `h4` (lower bound, e.g. `+30 min`) |

If the origin changes its markup, update the selectors in `_extract_stop` /
`_parse_line_item`; `parse_board(html, code)` and the response types stay the
same. To refresh the fixture from production:

```bash
mkdir -p tests/fixtures
curl -sS -A "Mozilla/5.0 ... Chrome/124.0 Safari/537.36" \
  "https://service-information.publictransport.com.mt/timetable?bus_stop=1090" \
  -o tests/fixtures/stop_1090.html
pytest
```

## Resilience

The origin runs aggressive bot protection: too many requests — or even a few
that stall connections — get the **caller's IP tarpitted**, after which *every*
request (including a plain browser-UA curl) hangs until cooldown. The service is
built to stay on the right side of that:

- **Response cache** — per-stop, `TALLINJA_CACHE_TTL_SECONDS` (default 25s), so
  repeated hits don't reach the origin.
- **Negative cache** — the origin *hangs* on unknown stop codes (it doesn't
  404), so a failed stop is remembered for `TALLINJA_NEGATIVE_CACHE_TTL_SECONDS`
  (default 30s); repeats fast-fail instead of re-incurring the timeout and
  stressing the breaker.
- **Rate limiter** — at least `TALLINJA_MIN_REQUEST_INTERVAL_SECONDS` (default
  1s) between origin fetches, across all stops.
- **Circuit breaker** — after `TALLINJA_CIRCUIT_FAILURE_THRESHOLD` (default 4)
  consecutive upstream failures it opens for `TALLINJA_CIRCUIT_COOLDOWN_SECONDS`
  (default 60s), fast-failing with `503 upstream_circuit_open` + `Retry-After`
  instead of piling on more connections. It then probes with one trial request
  before fully closing. A `404` counts as success (origin is healthy); a parse
  failure doesn't trip it (origin answered, markup just changed).
- **Short timeout** — `TALLINJA_REQUEST_TIMEOUT` (default 8s) so a stalled fetch
  doesn't hold a connection long enough to look like slowloris.

If you do get blocked, stop all traffic and wait for the cooldown — retrying
extends it.

## Tests

```bash
pytest          # parser, fetcher, resilience, API (origin mocked via respx)
ruff check .
```
