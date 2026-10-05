"""Build a validated, read-only runtime flashcard catalog from Words.hk YAML."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import yaml
from pydantic import BaseModel, ValidationError, model_validator

from yen2pinyin.contracts import WordDocument


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class BuildArguments(BaseModel):
  input_path: Path
  output_path: Path

  @model_validator(mode="after")
  def validate_paths(self) -> BuildArguments:
    if not self.input_path.is_file():
      raise ValueError(f"Input YAML does not exist: {self.input_path}")
    if not self.output_path.parent.is_dir():
      raise ValueError(f"Output directory does not exist: {self.output_path.parent}")
    if self.input_path.resolve() == self.output_path.resolve():
      raise ValueError("Input and output paths must differ")
    return self


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--input", type=Path, dest="input_path")
  parser.add_argument("--output", type=Path, dest="output_path")
  args = BuildArguments.model_validate(vars(parser.parse_args()))

  # YAML and Pydantic validation happen at build time, never in an API worker.
  try:
    with args.input_path.open(encoding="utf-8") as source:
      document = WordDocument.model_validate(yaml.load(
        source, Loader=yaml.CSafeLoader if hasattr(yaml, "CSafeLoader") else yaml.SafeLoader,
      ))
  except (OSError, yaml.YAMLError, ValidationError) as error:
    parser.error(f"Cannot load flashcard YAML from {args.input_path}: {error}")

  source_hash = hashlib.sha256()
  with args.input_path.open("rb") as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
      source_hash.update(chunk)

  temporary = args.output_path.with_name(f"{args.output_path.name}.{os.getpid()}.tmp")
  try:
    connection = sqlite3.connect(temporary)
    try:
      connection.executescript(
        "CREATE TABLE catalog_meta (eligible_count INTEGER NOT NULL, source_hash TEXT NOT NULL);"
        "CREATE TABLE entries (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);"
        "CREATE TABLE headwords (id INTEGER PRIMARY KEY, word TEXT NOT NULL, readings TEXT NOT NULL);"
        "PRAGMA user_version = 1;"
      )
      eligible_count = 0
      for entry in document.entries:
        # Preserve the original complete record and its explicit versus absent fields.
        if any(
          example.yue is not None and example.yue.strip() and example.yue.strip().upper() != "X"
          for definition in entry.definitions for example in definition.eg
        ):
          eligible_count += 1
          connection.execute(
            "INSERT INTO entries (id, payload) VALUES (?, ?)",
            (eligible_count, entry.model_dump_json(exclude_unset=True)),
          )
        for headword in entry.headwords:
          connection.execute(
            "INSERT INTO headwords (word, readings) VALUES (?, ?)",
            (headword.word, json.dumps(headword.readings, ensure_ascii=False)),
          )
      if eligible_count == 0:
        parser.error("No flashcard words with substantive Cantonese examples")
      connection.execute(
        "INSERT INTO catalog_meta (eligible_count, source_hash) VALUES (?, ?)",
        (eligible_count, source_hash.hexdigest()),
      )
      connection.commit()
    finally:
      connection.close()
    os.replace(temporary, args.output_path)
  finally:
    temporary.unlink(missing_ok=True)
  print(f"Built {eligible_count} eligible flashcards from {len(document.entries)} entries at {args.output_path}")
