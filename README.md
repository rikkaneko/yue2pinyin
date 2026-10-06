# Yue2Pinyin

FastAPI service for Cantonese pronunciation and Words.hk flashcards, with a separately hosted static frontend. Pronunciation uses the checked-in dictionaries and mapping guides.

## Installation and configuration

Requires Python 3.11 or newer. From the project root:

```sh
uv venv --managed-python --seed .venv
uv pip install --python .venv/bin/python -e '.[test]'
cp -n .env.example .env;
.venv/bin/python scripts/build_flashcard_db.py --input ./assests/words-hk/all-latest.yaml --output ./words.sqlite3
.venv/bin/uvicorn yue2pinyin.api:app --host 127.0.0.1 --port 8000
```

Build the SQLite catalog again whenever the Words.hk YAML changes. At startup, the app reads `.env` from its current working directory if present. The copy command above leaves an existing `.env` untouched. Process environment variables take precedence over `.env`; missing settings use the defaults below.

The API serves `/jyutpin`, `/approx_pinyin`, and `/word`; it does not serve the frontend. Set `YUE2PINYIN_CORS_ORIGINS=http://localhost:8080` in `.env` before starting it, then serve `frontend/` from another terminal:

```sh
python3 -m http.server 8080 --bind 127.0.0.1 --directory frontend
```

To run the service with Docker Compose, create `.env` from `.env.example` if needed, then start it from the project root:

```sh
cp -n .env.example .env;
docker compose up --build;
```

The Docker build uses `words.sqlite3` from the project root when present in the build context; otherwise it generates the catalog from the bundled YAML. Regenerate the local database after YAML changes. BuildKit caches pip downloads between builds. Compose passes the `YUE2PINYIN_*` values from `.env` into the container. The service listens on port 8000 inside the Compose network, but `docker-compose.yaml` publishes no host port. To access it from the host, explicitly add a `ports` mapping such as `127.0.0.1:8000:8000` in a local Compose override. The compiled trie cache is stored inside the container by default.

| Variable | Default | Purpose |
| --- | --- | --- |
| `YUE2PINYIN_WORDS_PATH` | `assests/rime-cantonese/jyut6ping3.words.dict.csv` within the package project | Word dictionary |
| `YUE2PINYIN_CHARACTERS_PATH` | `assests/words-hk/charlist.json` within the package project | Character pronunciation counts |
| `YUE2PINYIN_CACHE_PATH` | `./jyutping.dat` | Writable compiled-trie cache |
| `YUE2PINYIN_FLASHCARD_DB_PATH` | `./words.sqlite3` within the package project | Built Words.hk flashcard and pronunciation catalog |
| `YUE2PINYIN_CORS_ORIGINS` | empty | Comma-separated allowed frontend origins; empty denies cross-origin browser requests |

CORS entries can be exact HTTP(S) origins (`https://app.nekoid.cc`), subdomains (`https://*.nekoid.cc`), or a host with any explicit numeric port (`http://localhost:*`). A subdomain wildcard excludes the root domain. List the root separately when needed. Paths, query strings, malformed hosts, and invalid fixed ports fail validation at process start. Cross-origin `GET`, `POST`, and `Content-Type` preflight requests are supported without credentials. Allowed preflights advertise `Access-Control-Max-Age: 86400` (one day); browsers may evict or cap that cache sooner. Restart the API after changing CORS settings.

## Features

- Input segmentation at Unicode punctuation and whitespace before longest-word Jyutping matching, including ASCII and fullwidth forms.
- Character pronunciation fallback selected by frequency.
- Deterministic approximate Mandarin pinyin with standard syllable bases by default, an opt-in Jyutping-like mode, and concise sound cues.
- Parallel text-unit arrays retaining punctuation and unknown characters, with each Latin word in one unit.
- Word-group arrays that preserve dictionary matches and cover the full input.
- A standalone converter for the multiline words.hk CSV, with structured YAML output.
- Uniform random flashcards selected from entries with a substantive Cantonese example.
- Responsive pronunciation and flashcard views with browser Cantonese speech controls.
- Vowel tone marks and synchronized pronunciation-mode controls below text-analysis and flashcard reading rows.

## Usage

### Retrieve Jyutpin from Cantonese text

```sh
curl -X POST http://127.0.0.1:8000/jyutpin -H 'Content-Type: application/json' -d '{"text":"檸檬茶少甜少冰，唔該。"}'
```

#### Response

`*_words` fields store actual Jyutpin when pronouncing as a word.

```json
{
    "text": [
        "檸",
        "檬",
        "茶",
        "少",
        "甜",
        "少",
        "冰",
        "，",
        "唔",
        "該",
        "。"
    ],
    "jyutpin": [
        "ning4",
        "mung1",
        "caa4",
        "siu2",
        "tim4",
        "siu2",
        "bing1",
        null,
        "m4",
        "goi1",
        null
    ],
    "words": [
        "檸檬茶",
        "少甜",
        "少",
        "冰",
        "，",
        "唔該",
        "。"
    ],
    "jyutpin_words": [
        "ning4 mung1 caa4",
        "siu2 tim4",
        "siu2",
        "bing1",
        null,
        "m4 goi1",
        null
    ]
}
```

### Retrieve Jyutping, approximate Mandarin pinyin, and pronunciation hints

```sh
# Cantonese text
curl -X POST http://127.0.0.1:8000/approx_pinyin -H 'Content-Type: application/json' -d '{"text":"檸檬茶少甜少冰，唔該。"}'
# Jyutpin
curl -X POST http://127.0.0.1:8000/approx_pinyin -H 'Content-Type: application/json' -d '{"jyutpin":["ning4 mung1 caa4","siu2 tim4","siu2","bing1",null,"m4 goi1",null],null]}'
# Preserve the older Jyutping-like spellings when needed
curl -X POST http://127.0.0.1:8000/approx_pinyin -H 'Content-Type: application/json' -d '{"jyutpin":["m4","biu1","goek3"],"allow_invalid_pinyin":true}'
```

#### Response

Both `/approx_pinyin` request forms accept `allow_invalid_pinyin` as a boolean. Omit it or send `false` for the nearest standard Mandarin syllable base; send `true` for the previous literal Jyutping-like approximation. For example, `m4` yields `mu3` by default and `m3` in literal mode; `biu1` yields `biao1` or `biu1`. Checked-stop apostrophes remain in both modes. Responses keep numeric tone digits; the frontend displays marks on the main vowel. A checkbox sits below each Jyutping and approximate-pinyin result, including flashcard readings; changing one synchronizes all controls and refreshes visible readings. See [pronunciation rules](docs/pronunciation-rules.md).

`approx_pinyin_*` and `hint` are computed from the static mapping table and vowel restructuring rules from [CUHK Cantonese Online Tutorial](https://www.ilc.cuhk.edu.hk/workshop/Chinese/Cantonese/OnlineTutorial/intro.aspx).

The idea of `hint` is to restore the special mouth shape and pronuncation method in Cantonese.

```json
{
    "text": [
        "檸",
        "檬",
        "茶",
        "少",
        "甜",
        "少",
        "冰",
        "，",
        "唔",
        "該",
        "。"
    ],
    "jyutpin": [
        "ning4",
        "mung1",
        "caa4",
        "siu2",
        "tim4",
        "siu2",
        "bing1",
        null,
        "m4",
        "goi1",
        null
    ],
    "words": [
        "檸檬茶",
        "少甜",
        "少",
        "冰",
        "，",
        "唔該",
        "。"
    ],
    "jyutpin_words": [
        "ning4 mung1 caa4",
        "siu2 tim4",
        "siu2",
        "bing1",
        null,
        "m4 goi1",
        null
    ],
    "approx_pinyin": [
        "ning3",
        "meng1",
        "ca3",
        "xiu2",
        "tan3",
        "xiu2",
        "bing1",
        null,
        "mu3",
        "gai1",
        null
    ],
    "approx_pinyin_words": [
        "ning3 meng1 ca3",
        "xiu2 tan3",
        "xiu2",
        "bing1",
        null,
        "mu3 gai1",
        null
    ],
    "hint": [
        "",
        "",
        "舌葉平鋪，不捲舌",
        "舌葉平鋪，不捲舌",
        "韻尾雙唇緊閉，鼻腔出氣",
        "舌葉平鋪，不捲舌",
        "",
        null,
        "雙唇閉合，鼻音獨立成節",
        "",
        null
    ]
}
```

### Randomly draw a words with exmaples (at least one)

```sh
curl http://127.0.0.1:8000/word
```

#### Response

```json
{
    "headwords": [
        {
            "word": "正日",
            "readings": [
                "zing3 jat2"
            ]
        }
    ],
    "pos": [
        "名詞"
    ],
    "sim": [],
    "label": [],
    "ant": [],
    "img": [],
    "ref": [],
    "definitions": [
        {
            "explanation": [
                {
                    "yue": "節日或活動嘅當日",
                    "eng": "the exact date (of holidays, festivals or solar terms)"
                }
            ],
            "eg": [
                {
                    "jyutpin": "zung1 cau1 zing3 jat",
                    "yue": "中秋正日",
                    "eng": "tge exact date of Mid-Autumn Festival"
                },
                {
                    "jyutpin": "gam1 jat6 ngo5 zing3 jat2 wo3, m4 hai6 m4 bei2 min2 aa6 maa5?",
                    "yue": "今日我正日喎，唔係唔俾面呀嘛？",
                    "eng": "[ChatGPT]Today is my day off, why aren't you giving me face?"
                }
            ]
        }
    ],
    "reviewed": 0
}
```

## words.hk CSV conversion

The generated `assests/words-hk/all-latest.yaml` has a `metadata` mapping and an `entries` list of 59,396 records. `metadata.total_entries` counts converted records, and `metadata.last_updated` is the CSV export time as an ISO 8601 UTC string (`null` when a custom CSV has no export timestamp). Rebuild it from the CSV with:

```sh
.venv/bin/python scripts/convert_words_hk.py --input PATH --output PATH
```

## License

AGPLv3

The bundled source dictionaries may have separate licenses; verify their terms before redistribution.

- words.hk CSVs states that all rights are reserved and redistribution requires explicit permission or an applicable license. Apply the same terms to the generated YAML.
- `jyut6ping3.maps` is released under a [Open Data Commons Open Database v1.0 License](https://opendatacommons.org/licenses/odbl/) by [rime-cantonese](https://github.com/rime/rime-cantonese).
