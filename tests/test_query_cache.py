import asyncio
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from fastapi import Request
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from yue2pinyin import api
from yue2pinyin.contracts import ApproxTextRequest, TextRequest


BUILD_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_flashcard_db.py"


def test_query_results_reuse_jyutpin_and_approximation(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
  words = tmp_path / "words.csv"
  characters = tmp_path / "characters.json"
  words.write_text("words,jyutpin\n你好,nei5 hou2\n表,biu2\n", encoding="utf-8")
  characters.write_text(json.dumps({"你": {"nei5": 1}}), encoding="utf-8")
  monkeypatch.setenv("YUE2PINYIN_WORDS_PATH", str(words))
  monkeypatch.setenv("YUE2PINYIN_CHARACTERS_PATH", str(characters))
  monkeypatch.setenv("YUE2PINYIN_CACHE_PATH", str(tmp_path / "trie.dat"))
  flashcards = tmp_path / "flashcards.yaml"
  flashcards.write_text("metadata: {}\nentries:\n  - headwords: [{word: 你好, readings: [nei5 hou2]}]\n    pos: []\n    sim: []\n    label: []\n    ant: []\n    img: []\n    ref: []\n    definitions: [{explanation: [], eg: [{yue: 你好, jyutpin: nei5 hou2}]}]\n    reviewed: 1\n", encoding="utf-8")
  database = tmp_path / "flashcards.sqlite3"
  subprocess.run([sys.executable, str(BUILD_SCRIPT), "--input", str(flashcards), "--output", str(database)], check=True)
  monkeypatch.setenv("YUE2PINYIN_FLASHCARD_DB_PATH", str(database))

  with TestClient(api.app) as client:
    with patch.object(api.app.state.trie, "annotate", wraps=api.app.state.trie.annotate) as lookup:
      with patch.object(api, "approximate", wraps=api.approximate) as convert:
        first_jyutpin = client.post("/jyutpin", json={"text": "你好"}).json()
        assert client.post("/jyutpin", json={"text": "你好"}).json() == first_jyutpin
        first_approx = client.post("/approx_pinyin", json={"text": "你好"}).json()
        assert client.post("/approx_pinyin", json={"text": "你好"}).json() == first_approx
        assert first_approx["jyutpin"] == first_jyutpin["jyutpin"]
        assert lookup.call_count == 1
        assert convert.call_count == 2
        assert list(api.app.state.jyutpin_cache) == ["你好"]
        assert list(api.app.state.approx_pinyin_cache) == [("你好", False)]
        literal = client.post("/approx_pinyin", json={"text": "你好", "allow_invalid_pinyin": True}).json()
        assert list(api.app.state.approx_pinyin_cache) == [("你好", False), ("你好", True)]
        assert literal["jyutpin"] == first_approx["jyutpin"]
        assert lookup.call_count == 1
        assert convert.call_count == 4

        # An approximate-pinyin first request also populates the Jyutpin cache.
        client.post("/approx_pinyin", json={"text": "你"})
        client.post("/jyutpin", json={"text": "你"})
        assert lookup.call_count == 2
        assert client.post("/jyutpin", json={"text": ""}).status_code == 200
        assert client.post("/jyutpin", json={"text": ""}).status_code == 200
        assert lookup.call_count == 3
        before = len(api.app.state.jyutpin_cache)
        assert client.post("/jyutpin", json={"text": 7}).status_code == 422
        assert len(api.app.state.jyutpin_cache) == before

        # Returned models have no mutable list aliases into either cache.
        request = Request({"type": "http", "app": api.app})
        jyutpin_result = asyncio.run(api.jyutpin(TextRequest(text="你好"), request))
        jyutpin_result.jyutpin[0] = "changed"
        approx_result = asyncio.run(api.approx_pinyin(ApproxTextRequest(text="你好"), request))
        approx_result.jyutpin[0] = "changed"
        assert asyncio.run(api.jyutpin(TextRequest(text="你好"), request)).jyutpin == ["nei5", "hou2"]
        assert asyncio.run(api.approx_pinyin(ApproxTextRequest(text="你好"), request)).jyutpin == ["nei5", "hou2"]
        valid_word = client.post("/approx_pinyin", json={"text": "表"}).json()
        literal_word = client.post("/approx_pinyin", json={"text": "表", "allow_invalid_pinyin": True}).json()
        assert valid_word["approx_pinyin"] == ["biao2"]
        assert valid_word["approx_pinyin_words"] == ["biao2"]
        assert literal_word["approx_pinyin"] == ["biu2"]
        assert literal_word["approx_pinyin_words"] == ["biu2"]
        assert valid_word["hint"] == literal_word["hint"]


def test_independent_lru_eviction_and_lifespan_reset(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
  words = tmp_path / "words.csv"
  characters = tmp_path / "characters.json"
  words.write_text("words,jyutpin\n你好,nei5 hou2\n", encoding="utf-8")
  characters.write_text("{}", encoding="utf-8")
  monkeypatch.setenv("YUE2PINYIN_WORDS_PATH", str(words))
  monkeypatch.setenv("YUE2PINYIN_CHARACTERS_PATH", str(characters))
  monkeypatch.setenv("YUE2PINYIN_CACHE_PATH", str(tmp_path / "trie.dat"))
  flashcards = tmp_path / "flashcards.yaml"
  flashcards.write_text("metadata: {}\nentries:\n  - headwords: [{word: 你好, readings: [nei5 hou2]}]\n    pos: []\n    sim: []\n    label: []\n    ant: []\n    img: []\n    ref: []\n    definitions: [{explanation: [], eg: [{yue: 你好, jyutpin: nei5 hou2}]}]\n    reviewed: 1\n", encoding="utf-8")
  database = tmp_path / "flashcards.sqlite3"
  subprocess.run([sys.executable, str(BUILD_SCRIPT), "--input", str(flashcards), "--output", str(database)], check=True)
  monkeypatch.setenv("YUE2PINYIN_FLASHCARD_DB_PATH", str(database))
  assert api.QUERY_CACHE_SIZE == 1000
  monkeypatch.setattr(api, "QUERY_CACHE_SIZE", 2)

  with TestClient(api.app) as client:
    with patch.object(api.app.state.trie, "annotate", wraps=api.app.state.trie.annotate) as lookup:
      for text in ("甲", "乙", "甲", "丙"):
        assert client.post("/jyutpin", json={"text": text}).status_code == 200
      assert list(api.app.state.jyutpin_cache) == ["甲", "丙"]
      for text in ("甲", "乙", "甲", "丙"):
        assert client.post("/approx_pinyin", json={"text": text}).status_code == 200
      assert list(api.app.state.approx_pinyin_cache) == [("甲", False), ("丙", False)]
      assert list(api.app.state.jyutpin_cache) == ["乙", "丙"]
      assert lookup.call_count == 5

  with TestClient(api.app):
    assert len(api.app.state.jyutpin_cache) == 0
    assert len(api.app.state.approx_pinyin_cache) == 0
