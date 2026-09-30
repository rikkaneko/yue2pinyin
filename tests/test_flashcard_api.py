from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from yen2pinyin.api import WordCatalog, app


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
  monkeypatch.setenv("YEN2PINYIN_FLASHCARD_WORDS_PATH", str(source))

  with TestClient(app) as client:
    schema = client.get("/openapi.json").json()
    assert "/word" in schema["paths"]
    assert len(app.state.word_catalog.entries) == 2
    with patch("yen2pinyin.api.choice", side_effect=lambda entries: entries[0]) as chosen:
      assert client.get("/word").json() == valid
      assert chosen.call_count == 1
      assert len(chosen.call_args.args[0]) == 2
    with patch("yen2pinyin.api.choice", side_effect=lambda entries: entries[1]):
      assert client.get("/word").json() == second
    assert client.get("/").status_code == 404
    assert client.get("/assets/app.js").status_code == 404


def test_flashcard_source_failures_are_explicit(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
  missing = tmp_path / "missing.yaml"
  with pytest.raises(RuntimeError, match="Cannot load flashcard words"):
    WordCatalog(missing)

  invalid = tmp_path / "invalid.yaml"
  invalid.write_text("entries: [\n", encoding="utf-8")
  with pytest.raises(RuntimeError, match="Cannot load flashcard words"):
    WordCatalog(invalid)

  invalid.write_text("metadata: {}\nentries: [{}]\n", encoding="utf-8")
  with pytest.raises(RuntimeError, match="Cannot load flashcard words"):
    WordCatalog(invalid)

  invalid.write_text("metadata: {}\nentries: []\n", encoding="utf-8")
  with pytest.raises(RuntimeError, match="No flashcard words"):
    WordCatalog(invalid)

  words = tmp_path / "words.csv"
  words.write_text("words,jyutpin\n你好,nei5 hou2\n", encoding="utf-8")
  characters = tmp_path / "characters.json"
  characters.write_text("{}", encoding="utf-8")
  monkeypatch.setenv("YEN2PINYIN_WORDS_PATH", str(words))
  monkeypatch.setenv("YEN2PINYIN_CHARACTERS_PATH", str(characters))
  monkeypatch.setenv("YEN2PINYIN_CACHE_PATH", str(tmp_path / "trie.dat"))
  monkeypatch.setenv("YEN2PINYIN_FLASHCARD_WORDS_PATH", str(missing))
  with pytest.raises(RuntimeError, match="Cannot load flashcard words"):
    with TestClient(app):
      pass
