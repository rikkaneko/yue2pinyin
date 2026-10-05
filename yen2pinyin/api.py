"""FastAPI routes for Cantonese pronunciation and flashcards."""

from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
import re
from random import randrange
import sqlite3
from typing import Annotated, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from yen2pinyin.approximation import approximate
from yen2pinyin.contracts import (
  ApproximationValue, ApproxPinyinResponse, DirectApproxPinyinResponse, JyutpinRequest,
  JyutpinResponse, JyutpinValue, TextRequest, WordEntry,
)
from yen2pinyin.trie import PronunciationTrie


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERY_CACHE_SIZE = 1000
HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
ORIGIN = re.compile(r"(https?)://(\*\.)?([a-z0-9.-]+)(?::(\*|[0-9]+))?\Z", re.IGNORECASE)
ANY_VALID_PORT = r":(?:[1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])"


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_prefix="YEN2PINYIN_", extra="ignore")

  words_path: Path = PROJECT_ROOT / "assests/rime-cantonese/jyut6ping3.words.dict.csv"
  characters_path: Path = PROJECT_ROOT / "assests/words-hk/charlist.json"
  cache_path: Path = PROJECT_ROOT / "jyutping.dat"
  flashcard_db_path: Path = PROJECT_ROOT / "words.sqlite3"
  cors_origins: Annotated[list[str], NoDecode] = []

  @field_validator("cors_origins", mode="before")
  @classmethod
  def validate_cors_origins(cls, value: str | list[str]) -> list[str]:
    origins = value.split(",") if isinstance(value, str) else value
    normalized: list[str] = []
    for raw in origins:
      origin = raw.strip().lower()
      if not origin:
        if len(origins) == 1:
          continue
        raise ValueError("CORS origins cannot contain empty entries")
      match = ORIGIN.fullmatch(origin)
      if match is None or any(HOST_LABEL.fullmatch(label) is None for label in match.group(3).split(".")):
        raise ValueError(f"Invalid CORS origin: {raw}")
      port = match.group(4)
      if port is not None and port != "*" and not 1 <= int(port) <= 65535:
        raise ValueError(f"Invalid CORS port: {raw}")
      normalized.append(origin)
    return normalized


class WordCatalog:
  def __init__(self, source: Path) -> None:
    # Open the built catalog without loading its records into worker memory.
    try:
      self.connection = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
      version = self.connection.execute("PRAGMA user_version").fetchone()[0]
      if version != 1:
        raise ValueError(f"unsupported schema version {version}")
      row = self.connection.execute("SELECT eligible_count FROM catalog_meta").fetchone()
      if row is None or not isinstance(row[0], int) or row[0] < 1:
        raise ValueError("no eligible flashcard entries")
      self.eligible_count = row[0]
      if self.connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0] != self.eligible_count:
        raise ValueError("eligible entry count does not match catalog metadata")
      self.connection.execute("SELECT word, readings FROM headwords LIMIT 1").fetchone()
    except (OSError, sqlite3.Error, ValueError) as error:
      if hasattr(self, "connection"):
        self.connection.close()
      raise RuntimeError(f"Cannot load flashcard database from {source}: {error}") from error

  def get(self, entry_id: int) -> WordEntry:
    row = self.connection.execute("SELECT payload FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
      raise RuntimeError(f"Flashcard entry {entry_id} is missing")
    return WordEntry.model_validate_json(row[0])

  def close(self) -> None:
    self.connection.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
  # Resolve the optional dotenv file at startup, using the process working directory.
  settings = Settings(_env_file=Path.cwd() / ".env")
  app.state.word_catalog = WordCatalog(settings.flashcard_db_path)
  try:
    app.state.trie = PronunciationTrie.load_or_build(
      settings.words_path, settings.characters_path, settings.cache_path,
      settings.flashcard_db_path,
      app.state.word_catalog.connection.execute("SELECT word, readings FROM headwords ORDER BY id"),
    )
    # Query results live with this trie instance and are discarded at worker restart.
    app.state.jyutpin_cache = OrderedDict()
    app.state.approx_pinyin_cache = OrderedDict()
    yield
  finally:
    app.state.word_catalog.close()


app = FastAPI(title="yen2pinyin", lifespan=lifespan)

# Build an exact-origin list and a single anchored regex for the supported wildcard forms.
cors_settings = Settings(_env_file=Path.cwd() / ".env")
exact_origins: list[str] = []
wildcard_patterns: list[str] = []
for origin in cors_settings.cors_origins:
  match = ORIGIN.fullmatch(origin)
  assert match is not None
  scheme, subdomain_wildcard, host, port = match.groups()
  if subdomain_wildcard is None and port != "*":
    exact_origins.append(origin)
    continue
  host_pattern = re.escape(host)
  if subdomain_wildcard is not None:
    host_pattern = r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+" + host_pattern
  port_pattern = ANY_VALID_PORT if port == "*" else (":" + port if port is not None else "")
  wildcard_patterns.append(re.escape(scheme + "://") + host_pattern + port_pattern)
app.add_middleware(
  CORSMiddleware,
  allow_origins=exact_origins,
  allow_origin_regex="(?i)(?:" + "|".join(wildcard_patterns) + ")" if wildcard_patterns else None,
  allow_methods=["GET", "POST"],
  allow_headers=["Content-Type"],
  allow_credentials=False,
  max_age=86400,
)


@app.get("/word", response_model=WordEntry, response_model_exclude_unset=True)
async def word(request: Request) -> WordEntry:
  catalog: WordCatalog = request.app.state.word_catalog
  return catalog.get(randrange(1, catalog.eligible_count + 1))


@app.post("/jyutpin", response_model=JyutpinResponse)
async def jyutpin(payload: TextRequest, request: Request) -> JyutpinResponse:
  cache: OrderedDict[str, JyutpinResponse] = request.app.state.jyutpin_cache
  cached = cache.get(payload.text)
  if cached is not None:
    cache.move_to_end(payload.text)
    return cached.model_copy(deep=True)

  # Keep per-character and word-group results from the same longest-match pass.
  lookup = request.app.state.trie.annotate(payload.text)
  result = JyutpinResponse(
    text=lookup.text,
    jyutpin=lookup.jyutpin,
    words=lookup.words,
    jyutpin_words=lookup.jyutpin_words,
  )
  cache[payload.text] = result.model_copy(deep=True)
  if len(cache) > QUERY_CACHE_SIZE:
    cache.popitem(last=False)
  return result


@app.post("/approx_pinyin", response_model=ApproxPinyinResponse | DirectApproxPinyinResponse)
async def approx_pinyin(
  payload: TextRequest | JyutpinRequest, request: Request,
) -> ApproxPinyinResponse | DirectApproxPinyinResponse:
  if isinstance(payload, JyutpinRequest):
    normalized: list[JyutpinValue] = []
    converted: list[ApproximationValue] = []
    hints: list[ApproximationValue] = []
    for reading in payload.jyutpin:
      syllables = reading.split() if isinstance(reading, str) else reading
      if syllables is None:
        normalized.append(None)
        converted.append(None)
        hints.append(None)
      elif not syllables:
        normalized.append(reading)
        converted.append(None)
        hints.append(None)
      elif isinstance(reading, list) or len(syllables) > 1:
        normalized.append(syllables)
        approximations = [approximate(syllable) for syllable in syllables]
        converted.append([item[0] for item in approximations])
        hints.append([item[1] for item in approximations])
      else:
        normalized.append(reading)
        approximation, hint = approximate(syllables[0])
        converted.append(approximation)
        hints.append(hint)
    return DirectApproxPinyinResponse(jyutpin=normalized, approx_pinyin=converted, hint=hints)

  cache: OrderedDict[str, ApproxPinyinResponse] = request.app.state.approx_pinyin_cache
  cached = cache.get(payload.text)
  if cached is not None:
    cache.move_to_end(payload.text)
    return cached.model_copy(deep=True)

  # Approximation reuses the Jyutpin cache, including entries from its own prior misses.
  jyutpin_cache: OrderedDict[str, JyutpinResponse] = request.app.state.jyutpin_cache
  jyutpin_result = jyutpin_cache.get(payload.text)
  if jyutpin_result is None:
    lookup = request.app.state.trie.annotate(payload.text)
    jyutpin_result = JyutpinResponse(
      text=lookup.text,
      jyutpin=lookup.jyutpin,
      words=lookup.words,
      jyutpin_words=lookup.jyutpin_words,
    )
    jyutpin_cache[payload.text] = jyutpin_result.model_copy(deep=True)
    if len(jyutpin_cache) > QUERY_CACHE_SIZE:
      jyutpin_cache.popitem(last=False)
  else:
    jyutpin_cache.move_to_end(payload.text)
    jyutpin_result = jyutpin_result.model_copy(deep=True)

  converted: list[tuple[ApproximationValue, ApproximationValue]] = []
  for reading in jyutpin_result.jyutpin:
    if reading is None:
      converted.append((None, None))
    elif isinstance(reading, list):
      approximations = [approximate(syllable) for syllable in reading]
      converted.append(([item[0] for item in approximations], [item[1] for item in approximations]))
    else:
      converted.append(approximate(reading))
  per_unit = [item[0] for item in converted]
  grouped: list[ApproximationValue] = []
  offset = 0
  for word in jyutpin_result.words:
    end = offset
    consumed = ""
    while end < len(jyutpin_result.text) and len(consumed) < len(word):
      consumed += jyutpin_result.text[end]
      end += 1
    syllables = per_unit[offset:end]
    if len(syllables) == 1 and isinstance(syllables[0], list):
      grouped.append(syllables[0])
    elif any(syllable is None or isinstance(syllable, list) and any(part is None for part in syllable)
             for syllable in syllables):
      grouped.append(None)
    else:
      grouped.append(" ".join(
        syllable if isinstance(syllable, str) else " ".join(part for part in syllable if part is not None)
        for syllable in syllables if syllable is not None
      ))
    offset = end
  result = ApproxPinyinResponse(
    text=jyutpin_result.text,
    jyutpin=jyutpin_result.jyutpin,
    words=jyutpin_result.words,
    jyutpin_words=jyutpin_result.jyutpin_words,
    approx_pinyin=per_unit,
    approx_pinyin_words=grouped,
    hint=[item[1] for item in converted],
  )
  cache[payload.text] = result.model_copy(deep=True)
  if len(cache) > QUERY_CACHE_SIZE:
    cache.popitem(last=False)
  return result
