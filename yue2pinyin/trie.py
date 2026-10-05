"""Dictionary loading, double-array trie construction, and cached lookup."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import unicodedata
import zlib
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, TypeAlias


CACHE_VERSION = 4
SYLLABLE = re.compile(r"[a-z]+[1-6]\Z")
TrieReading: TypeAlias = str | list[str]


@dataclass
class LookupResult:
  text: list[str]
  jyutpin: list[TrieReading | None]
  words: list[str]
  jyutpin_words: list[TrieReading | None]


def split_units(text: str) -> list[str]:
  """Keep a Latin run together so borrowed words have one pronunciation slot."""
  units: list[str] = []
  for char in text:
    latin = "LATIN" in unicodedata.name(char, "")
    if units and (latin or (char.isdigit() or unicodedata.category(char).startswith("M")) and
                  "LATIN" in unicodedata.name(units[-1][0], "")):
      if "LATIN" in unicodedata.name(units[-1][0], ""):
        units[-1] += char
        continue
    units.append(char)
  return units


class PronunciationTrie:
  def __init__(
    self,
    base: list[int],
    check: list[int],
    values: dict[int, list[TrieReading]],
    characters: dict[str, dict[str, int]],
  ) -> None:
    self.base = base
    self.check = check
    self.values = values
    self.characters = characters

  @classmethod
  def load_or_build(
    cls,
    words_path: Path,
    characters_path: Path,
    cache_path: Path,
    flashcard_db_path: Path,
    flashcard_headwords: Iterable[tuple[str, str]],
  ) -> PronunciationTrie:
    # Bind the cache to all pronunciation sources, including flashcard headwords.
    source_hash = hashlib.sha256()
    for path in (words_path, characters_path, flashcard_db_path):
      with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
          source_hash.update(chunk)
    digest = source_hash.hexdigest()

    try:
      cache = json.loads(zlib.decompress(cache_path.read_bytes()))
      if cache["version"] == CACHE_VERSION and cache["source_hash"] == digest:
        base = cache["base"]
        check = cache["check"]
        values = {int(key): value for key, value in cache["values"].items()}
        if not isinstance(base, list) or not isinstance(check, list) or len(base) != len(check):
          raise ValueError("Invalid trie arrays")
        if not isinstance(cache["characters"], dict):
          raise ValueError("Invalid character map")
        return cls(base, check, values, cache["characters"])
    except (OSError, ValueError, KeyError, TypeError, zlib.error):
      pass

    characters: dict[str, dict[str, int]] = json.loads(characters_path.read_text(encoding="utf-8"))
    readings: dict[str, list[list[TrieReading]]] = {}
    with words_path.open(encoding="utf-8", newline="") as source:
      for row in csv.DictReader(source):
        word = row["words"].lower()
        syllables = row["jyutpin"].split()
        units = split_units(word)
        # Word boundaries are enforced before lookup; punctuated source entries cannot match.
        if (
          not word
          or any(char.isspace() or unicodedata.category(char).startswith("P") for char in word)
          or any(SYLLABLE.fullmatch(syllable) is None for syllable in syllables)
        ):
          continue
        if len(units) == len(syllables):
          aligned = syllables
        elif len(units) == 1 and len(word) > 1:
          aligned = [syllables]
        else:
          continue
        variants = readings.setdefault(word, [])
        if aligned not in variants:
          variants.append(aligned)

    # Stream every Words.hk headword, including entries excluded from random draws.
    for headword, readings_json in flashcard_headwords:
      word = headword.lower()
      if not word or word in readings or any(
        char.isspace() or unicodedata.category(char).startswith("P") for char in word
      ):
        continue
      units = split_units(word)
      variants = []
      for reading in json.loads(readings_json):
        syllables = reading.split()
        if not syllables or any(SYLLABLE.fullmatch(syllable) is None for syllable in syllables):
          continue
        if len(units) == len(syllables):
          aligned = syllables
        elif len(units) == 1 and len(word) > 1:
          aligned = [syllables]
        else:
          continue
        if aligned not in variants:
          variants.append(aligned)
      if variants:
        readings[word] = variants

    root: dict[int, Any] = {}
    for word, variants in readings.items():
      # A missing frequency contributes zero; source order resolves equal scores.
      syllables = max(
        variants,
        key=lambda variant: sum(
          characters.get(char, {}).get(syllable, 0) if isinstance(syllable, str) else 0
          for char, syllable in zip(split_units(word), variant)
        ),
      )
      node = root
      for byte in word.encode("utf-8"):
        node = node.setdefault(byte + 1, {})
      node[-1] = syllables

    # UTF-8 bytes provide a bounded edge alphabet for the double-array layout.
    base = [0]
    check = [0]
    values: dict[int, list[TrieReading]] = {}
    queue = deque([(root, 0)])
    next_free = 1
    next_candidate = 1
    while queue:
      node, parent = queue.popleft()
      if -1 in node:
        values[parent] = node[-1]
      edges = sorted(edge for edge in node if edge >= 0)
      if not edges:
        continue
      # Monotonic placement avoids rescanning early sparse holes for every node.
      candidate = max(next_candidate, next_free - edges[0])
      while True:
        last = candidate + edges[-1]
        if last >= len(check):
          extension = last + 1 - len(check)
          base.extend([0] * extension)
          check.extend([-1] * extension)
        if all(check[candidate + edge] == -1 for edge in edges):
          break
        candidate += 1
      base[parent] = candidate
      next_candidate = candidate
      for edge in edges:
        child = candidate + edge
        check[child] = parent
        queue.append((node[edge], child))
      while next_free < len(check) and check[next_free] != -1:
        next_free += 1

    trie = cls(base, check, values, characters)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
      "version": CACHE_VERSION,
      "source_hash": digest,
      "base": base,
      "check": check,
      "values": values,
      "characters": characters,
    }
    temporary = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
    try:
      temporary.write_bytes(zlib.compress(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")))
      os.replace(temporary, cache_path)
    finally:
      temporary.unlink(missing_ok=True)
    return trie

  def longest(self, text: list[str], start: int, end: int) -> tuple[int, list[TrieReading]] | None:
    node = 0
    best: tuple[int, list[TrieReading]] | None = None
    for position in range(start, end):
      for byte in text[position].lower().encode("utf-8"):
        slot = self.base[node] + byte + 1
        if slot >= len(self.check) or self.check[slot] != node:
          return best
        node = slot
      if node in self.values:
        best = (position + 1, self.values[node])
    return best

  def annotate(self, text: str) -> LookupResult:
    units = split_units(text)
    result: list[TrieReading | None] = [None] * len(units)
    words: list[str] = []
    jyutpin_words: list[TrieReading | None] = []
    segments: list[tuple[int, int, bool]] = []
    start = 0
    for index, unit in enumerate(units):
      if unit.isspace() or unicodedata.category(unit[0]).startswith("P"):
        if start < index:
          segments.append((start, index, False))
        segments.append((index, index + 1, True))
        start = index + 1
    if start < len(units):
      segments.append((start, len(units), False))

    # All lookup spans are fixed before matching, so no word crosses a separator.
    for start, end, separator in segments:
      if separator:
        words.append(units[start])
        jyutpin_words.append(None)
        continue
      position = start
      while position < end:
        match = self.longest(units, position, end)
        if match is not None:
          stop, syllables = match
          result[position:stop] = syllables
          words.append("".join(units[position:stop]))
          jyutpin_words.append(
            syllables[0] if len(syllables) == 1 and isinstance(syllables[0], list)
            else " ".join(syllable if isinstance(syllable, str) else " ".join(syllable) for syllable in syllables)
          )
          position = stop
          continue
        candidates = self.characters.get(units[position], {})
        words.append(units[position])
        if candidates:
          result[position] = max(candidates, key=candidates.get)
        jyutpin_words.append(result[position])
        position += 1
    return LookupResult(text=units, jyutpin=result, words=words, jyutpin_words=jyutpin_words)
