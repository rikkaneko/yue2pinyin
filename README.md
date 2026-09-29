# yen2pinyin

FastAPI service that looks up Cantonese Jyutping and produces static Mandarin pinyin approximations with pronunciation cues. Stage 1 uses the checked-in dictionaries and mapping guides

## Installation and configuration

Requires Python 3.11 or newer. From the project root:

```sh
uv venv --managed-python --seed .venv
uv pip install --python .venv/bin/python -e '.[test]'
cp -n .env.example .env;
.venv/bin/uvicorn yen2pinyin.api:app --host 127.0.0.1 --port 8000
```

At startup, the app reads `.env` from its current working directory if present. The copy command above leaves an existing `.env` untouched. Process environment variables take precedence over `.env`; missing settings use the defaults below. The example file sets the cache to `./jyutping.dat`, which is ignored by Git. The first startup compiles the word dictionary into a double-array trie. Later starts reuse a compressed cache when the word CSV and character frequency JSON are unchanged.

To run the service with Docker Compose, create `.env` from `.env.example` if needed, then start it from the project root:

```sh
cp -n .env.example .env;
docker compose up --build;
```

Compose passes the `YEN2PINYIN_*` values from `.env` into the container. The service listens on port 8000 inside the Compose network, but `compose.yaml` publishes no host port. To access it from the host, explicitly add a `ports` mapping such as `127.0.0.1:8000:8000` in a local Compose override. The compiled trie cache is stored inside the container by default.

| Variable | Default | Purpose |
| --- | --- | --- |
| `YEN2PINYIN_WORDS_PATH` | `assests/rime-cantonese/jyut6ping3.words.dict.csv` within the package project | Word dictionary |
| `YEN2PINYIN_CHARACTERS_PATH` | `assests/words-hk/charlist.json` within the package project | Character pronunciation counts |
| `YEN2PINYIN_CACHE_PATH` | `/tmp/yen2pinyin/jyutping.dat` | Writable compiled-trie cache |

## Features

- Input segmentation at Unicode punctuation and whitespace before longest-word Jyutping matching, including ASCII and fullwidth forms.
- Character pronunciation fallback selected by frequency.
- Deterministic approximate Mandarin pinyin and concise sound cues.
- Per-character JSON arrays retaining punctuation and unknown characters.
- Word-group arrays that preserve dictionary matches and cover the full input.
- A standalone converter for the multiline words.hk CSV, with structured YAML output.

## Usage

```sh
curl -X POST http://127.0.0.1:8000/jyutpin -H 'Content-Type: application/json' -d '{"text":"你好，龘"}'
curl -X POST http://127.0.0.1:8000/approx_pinyin -H 'Content-Type: application/json' -d '{"text":"你好，龘"}'
.venv/bin/python -m pytest -q
```

Both routes return one `text` entry per Unicode character and add parallel `words` and `jyutpin_words` arrays. A dictionary match stays grouped, while fallback characters, punctuation, and whitespace each form one group. Grouped syllables are joined with spaces, for example `"你好"` with `"nei5 hou2"`. Missing readings are `null` in both per-character and grouped arrays.

`/approx_pinyin` adds per-character `approx_pinyin` and `hint`, plus `approx_pinyin_words`. A grouped approximation is `null` if any syllable in its group is unsupported. An ordinary sound has an empty hint string. See [pronunciation rules](docs/pronunciation-rules.md) for mapping details.

Each API worker keeps separate in-memory LRU caches of the latest 1,000 exact input texts for Jyutpin and approximate-pinyin responses. An approximate-pinyin cache miss reuses the Jyutpin result cache. These query caches start empty on worker startup and are not shared across workers; the compiled dictionary cache described above remains on disk.

## words.hk CSV conversion

The generated `assests/words-hk/all-1790539501.yaml` has a `metadata` mapping and an `entries` list of 59,396 records. `metadata.total_entries` counts converted records, and `metadata.last_updated` is the CSV export time as an ISO 8601 UTC string (`null` when a custom CSV has no export timestamp). Rebuild it from the CSV with:

```sh
.venv/bin/python scripts/convert_words_hk.py
```

Use `--input PATH --output PATH` to convert another file in the same six-column export format. The converter skips the rights notice and blank preamble record, omits the internal database ID, and splits `----` into ordered `definitions`. Each definition has `explanation` and `eg` arrays; a trailing parenthesized Jyutping reading in an example is moved from `yue` to `jyutpin`. Examples without a recognizable reading have `jyutpin: null`. Repeated `pos`, `sim`, `label`, `ant`, `img`, and `ref` annotations are arrays. Each entry has `reviewed: 1` for `OK` or `reviewed: 0` for a status containing `UNREVIEWED`, plus the publication status and unlabeled fourth CSV field. Pass `--include-raw-section` to also include `raw_headword` and `raw_definition`; these fields are omitted by default.

## License

LGPLv3

The bundled source dictionaries may have separate licenses; verify their terms before redistribution.

- words.hk CSVs states that all rights are reserved and redistribution requires explicit permission or an applicable license. Apply the same terms to the generated YAML.
- `jyut6ping3.maps` is released under a [Open Data Commons Open Database v1.0 License](https://opendatacommons.org/licenses/odbl/) by [rime-cantonese](https://github.com/rime/rime-cantonese).
