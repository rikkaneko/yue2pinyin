"""FastAPI routes for static Cantonese pronunciation analysis."""

from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from pydantic_settings import BaseSettings, SettingsConfigDict

from yen2pinyin.approximation import approximate
from yen2pinyin.contracts import ApproxPinyinResponse, JyutpinResponse, TextRequest
from yen2pinyin.trie import PronunciationTrie


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERY_CACHE_SIZE = 1000


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_prefix="YEN2PINYIN_", extra="ignore")

  words_path: Path = PROJECT_ROOT / "assests/rime-cantonese/jyut6ping3.words.dict.csv"
  characters_path: Path = PROJECT_ROOT / "assests/words-hk/charlist.json"
  cache_path: Path = Path("/tmp/yen2pinyin/jyutping.dat")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
  # Resolve the optional dotenv file at startup, using the process working directory.
  settings = Settings(_env_file=Path.cwd() / ".env")
  app.state.trie = PronunciationTrie.load_or_build(
    settings.words_path, settings.characters_path, settings.cache_path,
  )
  # Query results live with this trie instance and are discarded at worker restart.
  app.state.jyutpin_cache = OrderedDict()
  app.state.approx_pinyin_cache = OrderedDict()
  yield


app = FastAPI(title="yen2pinyin", lifespan=lifespan)


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
    text=list(payload.text),
    jyutpin=lookup.jyutpin,
    words=lookup.words,
    jyutpin_words=lookup.jyutpin_words,
  )
  cache[payload.text] = result.model_copy(deep=True)
  if len(cache) > QUERY_CACHE_SIZE:
    cache.popitem(last=False)
  return result


@app.post("/approx_pinyin", response_model=ApproxPinyinResponse)
async def approx_pinyin(payload: TextRequest, request: Request) -> ApproxPinyinResponse:
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
      text=list(payload.text),
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

  converted = [approximate(syllable) if syllable is not None else (None, None) for syllable in jyutpin_result.jyutpin]
  per_character = [item[0] for item in converted]
  grouped: list[str | None] = []
  offset = 0
  for word in jyutpin_result.words:
    syllables = per_character[offset:offset + len(word)]
    if any(syllable is None for syllable in syllables):
      grouped.append(None)
    else:
      grouped.append(" ".join(syllable for syllable in syllables if syllable is not None))
    offset += len(word)
  result = ApproxPinyinResponse(
    text=jyutpin_result.text,
    jyutpin=jyutpin_result.jyutpin,
    words=jyutpin_result.words,
    jyutpin_words=jyutpin_result.jyutpin_words,
    approx_pinyin=per_character,
    approx_pinyin_words=grouped,
    hint=[item[1] for item in converted],
  )
  cache[payload.text] = result.model_copy(deep=True)
  if len(cache) > QUERY_CACHE_SIZE:
    cache.popitem(last=False)
  return result
