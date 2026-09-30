import json
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from yen2pinyin.api import app


def test_routes_and_alignment(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
  words = tmp_path / "words.csv"
  characters = tmp_path / "characters.json"
  words.write_text("words,jyutpin\n你好,nei5 hou2\n啦好,la1 hou2\n", encoding="utf-8")
  characters.write_text(json.dumps({"你": {"nei5": 1}, "好": {"hou2": 1}}), encoding="utf-8")
  monkeypatch.setenv("YEN2PINYIN_WORDS_PATH", str(words))
  monkeypatch.setenv("YEN2PINYIN_CHARACTERS_PATH", str(characters))
  monkeypatch.setenv("YEN2PINYIN_CACHE_PATH", str(tmp_path / "cache.dat"))
  flashcards = tmp_path / "flashcards.yaml"
  flashcards.write_text("metadata: {}\nentries:\n  - headwords: [{word: 你好, readings: [nei5 hou2]}]\n    pos: []\n    sim: []\n    label: []\n    ant: []\n    img: []\n    ref: []\n    definitions: [{explanation: [], eg: [{yue: 你好, jyutpin: nei5 hou2}]}]\n    reviewed: 1\n", encoding="utf-8")
  monkeypatch.setenv("YEN2PINYIN_FLASHCARD_WORDS_PATH", str(flashcards))
  with TestClient(app) as client:
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "yen2pinyin"
    assert "/jyutpin" in schema["paths"]
    assert "/approx_pinyin" in schema["paths"]
    sample = "你好，啦好!你 龘"
    assert client.post("/jyutpin", json={"text": sample}).json() == {
      "text": list(sample),
      "jyutpin": ["nei5", "hou2", None, "la1", "hou2", None, "nei5", None, None],
      "words": ["你好", "，", "啦好", "!", "你", " ", "龘"],
      "jyutpin_words": ["nei5 hou2", None, "la1 hou2", None, "nei5", None, None],
    }
    approximate = client.post("/approx_pinyin", json={"text": sample})
    assert approximate.status_code == 200
    result = approximate.json()
    assert result["text"] == list(sample)
    assert result["jyutpin"] == ["nei5", "hou2", None, "la1", "hou2", None, "nei5", None, None]
    assert result["words"] == ["你好", "，", "啦好", "!", "你", " ", "龘"]
    assert result["jyutpin_words"] == ["nei5 hou2", None, "la1 hou2", None, "nei5", None, None]
    assert result["approx_pinyin"] == ["nei2", "hao2", None, None, "hao2", None, "nei2", None, None]
    assert result["approx_pinyin_words"] == ["nei2 hao2", None, None, None, "nei2", None, None]
    assert len(result["hint"]) == len(sample)
    assert result["hint"][-2:] == [None, None]
    assert client.post("/approx_pinyin", json={"text": ""}).json() == {
      "text": [], "jyutpin": [], "words": [], "jyutpin_words": [],
      "approx_pinyin": [], "approx_pinyin_words": [], "hint": [],
    }
    boundaries = "，!你,好。你好　你好 你好?!"
    expected_words = ["，", "!", "你", ",", "好", "。", "你好", "　", "你好", " ", "你好", "?", "!"]
    expected_jyutpin = [
      None, None, "nei5", None, "hou2", None, "nei5 hou2", None,
      "nei5 hou2", None, "nei5 hou2", None, None,
    ]
    for route in ("/jyutpin", "/approx_pinyin"):
      separated = client.post(route, json={"text": boundaries}).json()
      assert separated["words"] == expected_words
      assert separated["jyutpin_words"] == expected_jyutpin
      assert "".join(separated["words"]) == boundaries
      assert len(separated["text"]) == len(separated["jyutpin"]) == len(boundaries)
      if route == "/approx_pinyin":
        assert separated["approx_pinyin_words"] == [
          None, None, "nei2", None, "hao2", None, "nei2 hao2", None,
          "nei2 hao2", None, "nei2 hao2", None, None,
        ]
    assert client.post("/jyutpin", json={"text": 5}).status_code == 422
    assert client.post("/jyutpin", json={"text": "你", "extra": True}).status_code == 422
