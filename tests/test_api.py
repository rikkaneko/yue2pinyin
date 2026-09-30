import json
from pathlib import Path

import yaml
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


def test_flashcard_readings_and_direct_jyutpin(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
  words = tmp_path / "words.csv"
  words.write_text("words,jyutpin\n你好,nei5 hou2\n", encoding="utf-8")
  characters = tmp_path / "characters.json"
  characters.write_text("{}", encoding="utf-8")
  flashcards = tmp_path / "flashcards.yaml"
  entries = []
  for word, readings in (
    ("你好", ["nei5 hou6"]), ("hello", ["haa1 lou3", "haa1 lou2"]),
    ("新詞", ["san1 ci4"]), ("OK啦", ["ou1 kei1 laa1"]), ("AI", ["ei1 aai1"]),
    ("broken", ["haa1 xyz1"]), ("hi", ["haa1"]),
  ):
    entries.append({
      "headwords": [{"word": word, "readings": readings}],
      "pos": [], "sim": [], "label": [], "ant": [], "img": [], "ref": [],
      "definitions": [{"explanation": [], "eg": [{"yue": "你好"}]}], "reviewed": 1,
    })
  entries[4]["definitions"][0]["eg"] = []
  flashcards.write_text(yaml.safe_dump({"metadata": {}, "entries": entries}, allow_unicode=True), encoding="utf-8")
  monkeypatch.setenv("YEN2PINYIN_WORDS_PATH", str(words))
  monkeypatch.setenv("YEN2PINYIN_CHARACTERS_PATH", str(characters))
  monkeypatch.setenv("YEN2PINYIN_FLASHCARD_WORDS_PATH", str(flashcards))
  monkeypatch.setenv("YEN2PINYIN_CACHE_PATH", str(tmp_path / "trie.dat"))

  with TestClient(app) as client:
    result = client.post("/approx_pinyin", json={"text": "你好HELLO，新詞!"}).json()
    assert result["text"] == ["你", "好", "HELLO", "，", "新", "詞", "!"]
    assert result["words"] == ["你好", "HELLO", "，", "新詞", "!"]
    assert result["jyutpin"] == ["nei5", "hou2", ["haa1", "lou3"], None, "san1", "ci4", None]
    assert result["jyutpin_words"] == ["nei5 hou2", ["haa1", "lou3"], None, "san1 ci4", None]
    assert result["approx_pinyin"][2] == ["ha1", "lao1"]
    assert result["approx_pinyin_words"][1] == ["ha1", "lao1"]
    assert result["hint"][2] == ["喉音起聲", ""]
    assert client.post("/jyutpin", json={"text": "HeLlO OK啦"}).json()["text"] == ["HeLlO", " ", "OK", "啦"]
    assert client.post("/jyutpin", json={"text": "HeLlO OK啦"}).json()["jyutpin"] == [
      ["haa1", "lou3"], None, None, None,
    ]
    assert client.post("/jyutpin", json={"text": "ai"}).json()["jyutpin"] == [["ei1", "aai1"]]
    partial = client.post("/approx_pinyin", json={"text": "broken hi"}).json()
    assert partial["jyutpin"] == [["haa1", "xyz1"], None, "haa1"]
    assert partial["approx_pinyin"] == [["ha1", None], None, "ha1"]
    assert partial["approx_pinyin_words"] == [["ha1", None], None, "ha1"]
    assert partial["hint"] == [["喉音起聲", None], None, "喉音起聲"]

    direct = client.post("/approx_pinyin", json={
      "jyutpin": ["nei5", "haa1 lou3", ["so1", "wi4"], ["haa1"], None, "", "xyz1", "haa1 xyz1"],
    })
    assert direct.status_code == 200
    assert direct.json() == {
      "jyutpin": ["nei5", ["haa1", "lou3"], ["so1", "wi4"], ["haa1"], None, "", "xyz1", ["haa1", "xyz1"]],
      "approx_pinyin": ["nei2", ["ha1", "lao1"], ["so1", "wi3"], ["ha1"], None, None, None, ["ha1", None]],
      "hint": ["", ["喉音起聲", ""], ["舌葉音起聲", ""], ["喉音起聲"], None, None, None,
               ["喉音起聲", None]],
    }
    assert client.post("/approx_pinyin", json={"jyutpin": []}).json() == {
      "jyutpin": [], "approx_pinyin": [], "hint": [],
    }
    for malformed in ({"text": "你好", "jyutpin": ["nei5"]}, {"jyutpin": "nei5"},
                      {"jyutpin": [5]}, {"jyutpin": [[5]]}, {"jyutpin": ["nei5"], "extra": True}):
      assert client.post("/approx_pinyin", json=malformed).status_code == 422
