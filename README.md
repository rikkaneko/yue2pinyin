# Yen2Pinyin

FastAPI service for Cantonese pronunciation and Words.hk flashcards, with a separately hosted static frontend. Pronunciation uses the checked-in dictionaries and mapping guides.

## Installation and configuration

Requires Python 3.11 or newer. From the project root:

```sh
uv venv --managed-python --seed .venv
uv pip install --python .venv/bin/python -e '.[test]'
cp -n .env.example .env;
.venv/bin/python scripts/build_flashcard_db.py
.venv/bin/uvicorn yen2pinyin.api:app --host 127.0.0.1 --port 8000
```

Build the SQLite catalog again whenever the Words.hk YAML changes. At startup, the app reads `.env` from its current working directory if present. The copy command above leaves an existing `.env` untouched. Process environment variables take precedence over `.env`; missing settings use the defaults below.

The API serves `/jyutpin`, `/approx_pinyin`, and `/word`; it does not serve the frontend. Set `YEN2PINYIN_CORS_ORIGINS=http://localhost:8080` in `.env` before starting it, then serve `frontend/` from another terminal:

```sh
python3 -m http.server 8080 --bind 127.0.0.1 --directory frontend
```

Open `http://localhost:8080/`. The standalone page reads its single API base URL from `frontend/config.js` (default `http://127.0.0.1:8000`) and appends each API path. Edit that file for another deployment. Bootstrap, jQuery, and Zod load from versioned jsDelivr URLs, so the browser needs internet access for the interface.

To run the service with Docker Compose, create `.env` from `.env.example` if needed, then start it from the project root:

```sh
cp -n .env.example .env;
docker compose up --build;
```

The Docker build generates the SQLite catalog from the bundled YAML. Compose passes the `YEN2PINYIN_*` values from `.env` into the container. The service listens on port 8000 inside the Compose network, but `compose.yaml` publishes no host port. To access it from the host, explicitly add a `ports` mapping such as `127.0.0.1:8000:8000` in a local Compose override. The compiled trie cache is stored inside the container by default.

| Variable | Default | Purpose |
| --- | --- | --- |
| `YEN2PINYIN_WORDS_PATH` | `assests/rime-cantonese/jyut6ping3.words.dict.csv` within the package project | Word dictionary |
| `YEN2PINYIN_CHARACTERS_PATH` | `assests/words-hk/charlist.json` within the package project | Character pronunciation counts |
| `YEN2PINYIN_CACHE_PATH` | `./jyutping.dat` | Writable compiled-trie cache |
| `YEN2PINYIN_FLASHCARD_DB_PATH` | `./words.sqlite3` within the package project | Built Words.hk flashcard and pronunciation catalog |
| `YEN2PINYIN_CORS_ORIGINS` | empty | Comma-separated allowed frontend origins; empty denies cross-origin browser requests |

CORS entries can be exact HTTP(S) origins (`https://app.nekoid.cc`), subdomains (`https://*.nekoid.cc`), or a host with any explicit numeric port (`http://localhost:*`). A subdomain wildcard excludes the root domain. List the root separately when needed. Paths, query strings, malformed hosts, and invalid fixed ports fail validation at process start. Cross-origin `GET`, `POST`, and `Content-Type` preflight requests are supported without credentials. Allowed preflights advertise `Access-Control-Max-Age: 86400` (one day); browsers may evict or cap that cache sooner. Restart the API after changing CORS settings.

## Features

- Input segmentation at Unicode punctuation and whitespace before longest-word Jyutping matching, including ASCII and fullwidth forms.
- Character pronunciation fallback selected by frequency.
- Deterministic approximate Mandarin pinyin and concise sound cues.
- Parallel text-unit arrays retaining punctuation and unknown characters, with each Latin word in one unit.
- Word-group arrays that preserve dictionary matches and cover the full input.
- A standalone converter for the multiline words.hk CSV, with structured YAML output.
- Uniform random flashcards selected from entries with a substantive Cantonese example.
- Responsive pronunciation and flashcard views with browser Cantonese speech controls.
- Bootstrap 5 default-theme frontend with a random example placeholder, horizontally scrollable word readings, grouped unreadable text, visible hint cues, and labeled flashcard translations.

## Usage

```sh
curl -X POST http://127.0.0.1:8000/jyutpin -H 'Content-Type: application/json' -d '{"text":"你好，龘"}'
curl -X POST http://127.0.0.1:8000/approx_pinyin -H 'Content-Type: application/json' -d '{"text":"你好，龘"}'
curl -X POST http://127.0.0.1:8000/approx_pinyin -H 'Content-Type: application/json' -d '{"jyutpin":["nei5",["so1","wi4"],null]}'
curl http://127.0.0.1:8000/word
.venv/bin/python -m pytest -q
```

For `{ "text": "..." }`, both pronunciation routes return parallel text-unit and reading arrays. Cantonese characters, punctuation, and whitespace occupy one unit each; a contiguous Latin word such as `sorry` occupies one unit and retains its input case. `words` and `jyutpin_words` group dictionary matches. Rime readings take precedence; valid Words.hk headword readings fill missing words. Latin matching ignores case. A multi-syllable Latin reading occupies one nested array, so `sorry囉` returns `text: ["sorry", "囉"]` and `jyutpin: [["so1", "wi4"], "lo3"]`. Single-syllable readings remain strings; missing readings are `null`.

For text input, `/approx_pinyin` adds per-unit `approx_pinyin` and `hint`, plus `approx_pinyin_words`. Nested Latin readings convert syllable by syllable, preserving positions with `null` for unsupported syllables; for `sorry囉`, `approx_pinyin` is `[["so1", "wi3"], "lo1"]`. A grouped Cantonese approximation remains `null` if any unit is unsupported. An ordinary sound has an empty hint string. Alternatively, `{ "jyutpin": ["nei5", ["so1", "wi4"], null] }` converts readings directly and returns only `jyutpin`, `approx_pinyin`, and `hint` arrays. Existing space-separated strings such as `"so1 wi4"` remain accepted and return nested arrays. Explicit nested arrays retain their shape, including one-syllable arrays. Empty or null elements have null approximation and hint. See [pronunciation rules](docs/pronunciation-rules.md) for mapping details.

Each API worker keeps separate in-memory LRU caches of the latest 1,000 exact input texts for Jyutpin and approximate-pinyin responses. An approximate-pinyin cache miss reuses the Jyutpin result cache. These query caches start empty on worker startup and are not shared across workers; the compiled dictionary cache described above remains on disk.

`GET /word` returns one complete Words.hk entry as JSON. Each worker opens the built SQLite database read-only and fetches only the selected entry. Entries qualify when at least one example has nonempty Cantonese text other than `X` (ignoring case and surrounding whitespace). Draws may repeat. A missing, incompatible, or empty database fails startup with a clear error. See [flashcard and frontend details](docs/flashcards-frontend.md).

## words.hk CSV conversion

The generated `assests/words-hk/all-latest.yaml` has a `metadata` mapping and an `entries` list of 59,396 records. `metadata.total_entries` counts converted records, and `metadata.last_updated` is the CSV export time as an ISO 8601 UTC string (`null` when a custom CSV has no export timestamp). Rebuild it from the CSV with:

```sh
.venv/bin/python scripts/convert_words_hk.py
```

Use `--input PATH --output PATH` to convert another file in the same six-column export format. The converter skips the rights notice and blank preamble record, omits the internal database ID, and splits `----` into ordered `definitions`. Each definition has `explanation` and `eg` arrays; a trailing parenthesized Jyutping reading in an example is moved from `yue` to `jyutpin`. Examples without a recognizable reading have `jyutpin: null`. Repeated `pos`, `sim`, `label`, `ant`, `img`, and `ref` annotations are arrays. Each entry has `reviewed: 1` for `OK` or `reviewed: 0` for a status containing `UNREVIEWED`. Pass `--include-raw-section` to include `raw_headword`, `raw_definition`, and `publication_status`; these fields are omitted by default.

To run the optional browser regression, start the API with `YEN2PINYIN_CORS_ORIGINS=http://localhost:8080`, serve `frontend/` on `http://localhost:8080/`, then run `BROWSER_TEST_URL=http://localhost:8080/ .venv/bin/python -m pytest -q tests/test_frontend_browser.py`. Set `BROWSER_TEST_API_URL` as well when using a different local API port. This requires the `agent-browser` CLI and a browser installation.

## License

AGPLv3

The bundled source dictionaries may have separate licenses; verify their terms before redistribution.

- words.hk CSVs states that all rights are reserved and redistribution requires explicit permission or an applicable license. Apply the same terms to the generated YAML.
- `jyut6ping3.maps` is released under a [Open Data Commons Open Database v1.0 License](https://opendatacommons.org/licenses/odbl/) by [rime-cantonese](https://github.com/rime/rime-cantonese).
