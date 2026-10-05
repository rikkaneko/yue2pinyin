import json
from pathlib import Path
from unittest.mock import MagicMock
import zlib

from yue2pinyin.trie import CACHE_VERSION, PronunciationTrie


def test_longest_match_boundaries_and_frequency(tmp_path: Path) -> None:
  words = tmp_path / "words.csv"
  characters = tmp_path / "characters.json"
  cache = tmp_path / "cache.dat"
  words.write_text(
    "words,jyutpin\n行路,haang4 lou6\n行路,hang4 lou6\n行路,hang4 lou6\n你好,nei5 hou2\n你好嗎,nei5 hou2 maa3\n",
    encoding="utf-8",
  )
  characters.write_text(
    json.dumps({"行": {"haang4": 2, "hang4": 5}, "路": {"lou6": 1}, "你": {"nei5": 3}, "嗎": {"maa3": 3}}),
    encoding="utf-8",
  )
  flashcards = tmp_path / "flashcards.sqlite3"
  flashcards.write_bytes(b"first catalog")
  trie = PronunciationTrie.load_or_build(words, characters, cache, flashcards, [])
  result = trie.annotate("你好嗎，行路!你 龘")
  assert result.jyutpin == [
    "nei5", "hou2", "maa3", None, "hang4", "lou6", None, "nei5", None, None,
  ]
  assert result.words == ["你好嗎", "，", "行路", "!", "你", " ", "龘"]
  assert result.jyutpin_words == ["nei5 hou2 maa3", None, "hang4 lou6", None, "nei5", None, None]
  assert trie.annotate("行路").jyutpin == ["hang4", "lou6"]
  assert len(trie.base) == len(trie.check)
  assert cache.exists()


def test_cache_reuse_invalidation_and_corruption(tmp_path: Path) -> None:
  words = tmp_path / "words.csv"
  characters = tmp_path / "characters.json"
  cache = tmp_path / "cache.dat"
  words.write_text("words,jyutpin\n行路,haang4 lou6\n行路,hang4 lou6\n", encoding="utf-8")
  characters.write_text(json.dumps({"行": {"haang4": 2, "hang4": 5}}), encoding="utf-8")
  flashcards = tmp_path / "flashcards.sqlite3"
  flashcards.write_bytes(b"first catalog")
  first = PronunciationTrie.load_or_build(words, characters, cache, flashcards, [])
  assert first.annotate("行路").jyutpin == ["hang4", "lou6"]
  first_bytes = cache.read_bytes()
  unreadable_headwords = MagicMock()
  unreadable_headwords.__iter__.side_effect = AssertionError("cache hit scanned headwords")
  second = PronunciationTrie.load_or_build(words, characters, cache, flashcards, unreadable_headwords)
  assert second.annotate("行路") == first.annotate("行路")
  assert cache.read_bytes() == first_bytes

  old_cache = json.loads(zlib.decompress(first_bytes))
  old_cache["version"] = CACHE_VERSION - 1
  old_cache["values"] = {}
  cache.write_bytes(zlib.compress(json.dumps(old_cache).encode("utf-8")))
  version_rebuilt = PronunciationTrie.load_or_build(words, characters, cache, flashcards, [])
  assert version_rebuilt.annotate("行路").jyutpin == ["hang4", "lou6"]
  assert json.loads(zlib.decompress(cache.read_bytes()))["version"] == CACHE_VERSION

  characters.write_text(json.dumps({"行": {"haang4": 8, "hang4": 5}}), encoding="utf-8")
  third = PronunciationTrie.load_or_build(words, characters, cache, flashcards, [])
  assert third.annotate("行路").jyutpin == ["haang4", "lou6"]
  assert cache.read_bytes() != first_bytes

  words.write_text("words,jyutpin\n行路,haang4 lou6\n新路,san1 lou6\n", encoding="utf-8")
  changed_words = PronunciationTrie.load_or_build(words, characters, cache, flashcards, [])
  assert changed_words.annotate("新路").jyutpin == ["san1", "lou6"]

  cache.write_bytes(b"broken cache")
  rebuilt = PronunciationTrie.load_or_build(words, characters, cache, flashcards, [])
  assert rebuilt.annotate("行路").jyutpin == ["haang4", "lou6"]


def test_equal_frequency_uses_first_csv_reading(tmp_path: Path) -> None:
  words = tmp_path / "words.csv"
  characters = tmp_path / "characters.json"
  words.write_text("words,jyutpin\n行路,haang4 lou6\n行路,hang4 lou6\n", encoding="utf-8")
  characters.write_text(json.dumps({"行": {"haang4": 5, "hang4": 5}}), encoding="utf-8")
  flashcards = tmp_path / "flashcards.sqlite3"
  flashcards.write_bytes(b"first catalog")
  trie = PronunciationTrie.load_or_build(words, characters, tmp_path / "cache.dat", flashcards, [])
  assert trie.annotate("行路").jyutpin == ["haang4", "lou6"]


def test_flashcard_cache_invalidation_and_reading_selection(tmp_path: Path) -> None:
  words = tmp_path / "words.csv"
  words.write_text("words,jyutpin\n你好,nei5 hou2\n", encoding="utf-8")
  characters = tmp_path / "characters.json"
  characters.write_text("{}", encoding="utf-8")
  flashcards = tmp_path / "flashcards.sqlite3"
  cache = tmp_path / "cache.dat"
  flashcards.write_bytes(b"first source")
  first = PronunciationTrie.load_or_build(words, characters, cache, flashcards, [("HELLO", '["haa1 lou3", "haa1 lou2"]')])
  assert first.annotate("hello").jyutpin == [["haa1", "lou3"]]
  assert first.annotate("HELLO").text == ["HELLO"]
  original_cache = cache.read_bytes()
  flashcards.write_bytes(b"changed source")
  second = PronunciationTrie.load_or_build(words, characters, cache, flashcards, [("HELLO", '["haa1 lou2"]')])
  assert second.annotate("HeLlO").jyutpin == [["haa1", "lou2"]]
  assert cache.read_bytes() != original_cache
