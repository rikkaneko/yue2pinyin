from pathlib import Path
import sqlite3
import subprocess
import sys
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from yen2pinyin.api import WordCatalog, app


BUILD_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_flashcard_db.py"


def test_word_route_returns_complete_eligible_record(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
  valid = {
    "headwords": [{"word": "你好", "readings": ["nei5 hou2"]}],
    "pos": ["語句"], "sim": ["哈囉"], "label": ["常用"], "ant": [], "img": [], "ref": [],
    "definitions": [{
      "explanation": [{"yue": "打招呼", "eng": "hello"}],
      "eg": [
        {"yue": "你好啊！", "eng": "Hello!", "jyutpin": "nei5 hou2 aa3"},
        {"eng": "source entry without Cantonese", "jyutpin": None},
      ],
      "unparsed": ["source note"],
    }],
    "reviewed": 1,
    "publication_status": "已公開",
  }
  second = {
    **valid,
    "headwords": [{"word": "再見", "readings": ["zoi3 gin3"]}],
    "definitions": [{"explanation": [], "eg": [{"yue": "再見！", "jyutpin": None}]}],
  }
  placeholder = {**valid, "definitions": [{"explanation": [], "eg": [{"yue": " X ", "jyutpin": None}]}]}
  blank = {**valid, "definitions": [{"explanation": [], "eg": [{"yue": "  ", "jyutpin": None}]}]}
  no_cantonese = {**valid, "definitions": [{"explanation": [], "eg": [{"eng": "hello", "jyutpin": None}]}]}
  source = tmp_path / "words.yaml"
  source.write_text(yaml.safe_dump({"metadata": {"total_entries": 5}, "entries": [
    placeholder, valid, blank, second, no_cantonese,
  ]}, allow_unicode=True), encoding="utf-8")
  words = tmp_path / "words.csv"
  words.write_text("words,jyutpin\n你好,nei5 hou2\n", encoding="utf-8")
  characters = tmp_path / "characters.json"
  characters.write_text("{}", encoding="utf-8")
  monkeypatch.setenv("YEN2PINYIN_WORDS_PATH", str(words))
  monkeypatch.setenv("YEN2PINYIN_CHARACTERS_PATH", str(characters))
  monkeypatch.setenv("YEN2PINYIN_CACHE_PATH", str(tmp_path / "trie.dat"))
  database = tmp_path / "words.sqlite3"
  subprocess.run([sys.executable, str(BUILD_SCRIPT), "--input", str(source), "--output", str(database)], check=True)
  monkeypatch.setenv("YEN2PINYIN_FLASHCARD_DB_PATH", str(database))

  with TestClient(app) as client:
    schema = client.get("/openapi.json").json()
    assert "/word" in schema["paths"]
    assert app.state.word_catalog.eligible_count == 2
    with patch("yen2pinyin.api.randrange", return_value=1) as chosen:
      assert client.get("/word").json() == valid
      assert chosen.call_count == 1
      assert chosen.call_args.args == (1, 3)
    with patch("yen2pinyin.api.randrange", return_value=2):
      assert client.get("/word").json() == second
    assert client.get("/").status_code == 404
    assert client.get("/assets/app.js").status_code == 404


def test_flashcard_source_failures_are_explicit(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
  missing = tmp_path / "missing.sqlite3"
  with pytest.raises(RuntimeError, match="Cannot load flashcard database"):
    WordCatalog(missing)

  invalid = tmp_path / "invalid.sqlite3"
  invalid.write_bytes(b"not sqlite")
  with pytest.raises(RuntimeError, match="Cannot load flashcard database"):
    WordCatalog(invalid)

  empty = tmp_path / "empty.sqlite3"
  with sqlite3.connect(empty) as connection:
    connection.execute("CREATE TABLE catalog_meta (eligible_count INTEGER)")
    connection.execute("PRAGMA user_version = 1")
  with pytest.raises(RuntimeError, match="Cannot load flashcard database"):
    WordCatalog(empty)

  with sqlite3.connect(empty) as connection:
    connection.execute("INSERT INTO catalog_meta VALUES (0)")
  with pytest.raises(RuntimeError, match="no eligible flashcard"):
    WordCatalog(empty)

  with sqlite3.connect(empty) as connection:
    connection.execute("UPDATE catalog_meta SET eligible_count = 1")
    connection.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, payload TEXT)")
    connection.execute("CREATE TABLE headwords (id INTEGER PRIMARY KEY, word TEXT, readings TEXT)")
  with pytest.raises(RuntimeError, match="count does not match"):
    WordCatalog(empty)

  words = tmp_path / "words.csv"
  words.write_text("words,jyutpin\n你好,nei5 hou2\n", encoding="utf-8")
  characters = tmp_path / "characters.json"
  characters.write_text("{}", encoding="utf-8")
  monkeypatch.setenv("YEN2PINYIN_WORDS_PATH", str(words))
  monkeypatch.setenv("YEN2PINYIN_CHARACTERS_PATH", str(characters))
  monkeypatch.setenv("YEN2PINYIN_CACHE_PATH", str(tmp_path / "trie.dat"))
  monkeypatch.setenv("YEN2PINYIN_FLASHCARD_DB_PATH", str(missing))
  with pytest.raises(RuntimeError, match="Cannot load flashcard database"):
    with TestClient(app):
      pass


def test_build_failure_does_not_replace_existing_database(tmp_path: Path) -> None:
  source = tmp_path / "invalid.yaml"
  database = tmp_path / "words.sqlite3"
  database.write_bytes(b"existing catalog")
  source.write_text("metadata: {}\nentries: [{}]\n", encoding="utf-8")
  result = subprocess.run(
    [sys.executable, str(BUILD_SCRIPT), "--input", str(source), "--output", str(database)],
    capture_output=True, text=True,
  )
  assert result.returncode != 0
  assert database.read_bytes() == b"existing catalog"
  assert list(tmp_path.glob("*.tmp")) == []

  source.write_text("metadata: {}\nentries: []\n", encoding="utf-8")
  result = subprocess.run(
    [sys.executable, str(BUILD_SCRIPT), "--input", str(source), "--output", str(database)],
    capture_output=True, text=True,
  )
  assert result.returncode != 0
  assert "No flashcard words" in result.stderr
  assert database.read_bytes() == b"existing catalog"
  assert list(tmp_path.glob("*.tmp")) == []
