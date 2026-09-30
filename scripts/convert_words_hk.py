"""Convert the multiline words.hk CSV into structured YAML."""

from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator, model_validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "assests/words-hk/all-latest.csv"
OUTPUT_PATH = SOURCE_PATH.with_suffix(".yaml")
ANNOTATION = re.compile(r"\((pos|sim|label|ant|img|ref):([^)]*)\)")
TAG = re.compile(r"<([a-z][a-z0-9_-]*)>\Z")
LANGUAGE = re.compile(r"([A-Za-z]{3}):([\s\S]*)\Z")
TRAILING_READING = re.compile(r"^(.*?)\s+\(([^()]*)\)$")
JYUTPING_SYLLABLE = re.compile(r"[a-z]+[1-6]")
HAN = re.compile(r"[\u3400-\u9fff]")
GENERATED_AT = re.compile(r"Generated (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?) \(UTC\)")


class ConversionArguments(BaseModel):
  input_path: Path
  output_path: Path
  include_raw_section: bool = False

  @field_validator("input_path")
  @classmethod
  def input_exists(cls, value: Path) -> Path:
    if not value.is_file():
      raise ValueError(f"Input CSV does not exist: {value}")
    return value

  @model_validator(mode="after")
  def distinct_paths(self) -> ConversionArguments:
    if self.input_path.resolve() == self.output_path.resolve():
      raise ValueError("Input and output paths must differ")
    if not self.output_path.parent.is_dir():
      raise ValueError(f"Output directory does not exist: {self.output_path.parent}")
    return self


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--input", type=Path, default=SOURCE_PATH, dest="input_path")
  parser.add_argument("--output", type=Path, default=OUTPUT_PATH, dest="output_path")
  parser.add_argument("--include-raw-section", action="store_true")
  args = ConversionArguments.model_validate(vars(parser.parse_args()))

  # Count entries and read the export timestamp before writing the YAML header.
  count = 0
  last_updated: str | None = None
  with args.input_path.open(encoding="utf-8-sig", newline="") as source:
    for row_number, row in enumerate(csv.reader(source), start=1):
      if row_number == 1 and len(row) >= 3:
        timestamp_match = GENERATED_AT.search(row[2])
        if timestamp_match is not None:
          last_updated = datetime.fromisoformat(timestamp_match.group(1)).replace(tzinfo=timezone.utc).isoformat()
      if row_number <= 2 and (len(row) != 6 or not row[0].strip()):
        continue
      if len(row) != 6:
        raise ValueError(f"CSV record {row_number} has {len(row)} columns; expected 6")
      count += 1

  converted = 0
  with args.input_path.open(encoding="utf-8-sig", newline="") as source, args.output_path.open(
    "w", encoding="utf-8", newline="\n"
  ) as output:
    output.write("metadata:\n")
    output.write(f"  total_entries: {count}\n")
    output.write(f"  last_updated: '{last_updated}'\n" if last_updated is not None else "  last_updated: null\n")
    output.write("entries:\n" if count else "entries: []\n")
    for row_number, row in enumerate(csv.reader(source), start=1):
      # The export starts with a three-column rights notice and a one-column blank record.
      if row_number <= 2 and (len(row) != 6 or not row[0].strip()):
        continue
      if len(row) != 6:
        raise ValueError(f"CSV record {row_number} has {len(row)} columns; expected 6")

      _, raw_headword, raw_definition, source_field_4, review_status, publication_status = row
      if review_status == "OK":
        reviewed = 1
      elif "UNREVIEWED" in review_status:
        reviewed = 0
      else:
        raise ValueError(f"CSV record {row_number} has unknown review status: {review_status}")
      headwords: list[dict[str, Any]] = []
      for variant in raw_headword.split(","):
        word, *readings = variant.split(":")
        headwords.append({"word": word, "readings": [reading for reading in readings if reading]})

      annotations: dict[str, list[str]] = {key: [] for key in ("pos", "sim", "label", "ant", "img", "ref")}
      definitions: list[dict[str, Any]] = []
      current_definition: dict[str, Any] = {"explanation": [], "eg": []}
      active_tag = "explanation"
      active_item: dict[str, Any] | None = None
      active_language: str | None = None

      if raw_definition != "未有內容 NO DATA":
        for line_number, line in enumerate(raw_definition.splitlines()):
          # Export annotations occupy the first line; all occurrences retain source order.
          if line_number == 0:
            for key, value in ANNOTATION.findall(line):
              annotations[key].append(value)
            line = ANNOTATION.sub("", line).strip()
            if not line:
              continue

          if line == "----":
            definitions.append(current_definition)
            current_definition = {"explanation": [], "eg": []}
            active_tag = "explanation"
            active_item = None
            active_language = None
            continue

          tag_match = TAG.fullmatch(line)
          if tag_match is not None:
            active_tag = tag_match.group(1)
            active_item = {"jyutpin": None} if active_tag == "eg" else {}
            current_definition.setdefault(active_tag, []).append(active_item)
            active_language = None
            continue

          language_match = LANGUAGE.fullmatch(line)
          if language_match is not None:
            language, value = language_match.groups()
            language = language.lower()
            if active_item is None:
              active_item = {"jyutpin": None} if active_tag == "eg" else {}
              current_definition.setdefault(active_tag, []).append(active_item)
            if active_tag == "eg" and language == "yue":
              reading_match = TRAILING_READING.fullmatch(value)
              if reading_match is not None:
                reading = reading_match.group(2)
                if JYUTPING_SYLLABLE.search(reading) is not None and HAN.search(reading) is None:
                  value = reading_match.group(1)
                  active_item["jyutpin"] = reading
            if language in active_item:
              active_item[language] += "\n" + value
            else:
              active_item[language] = value
            active_language = language
            continue

          # Keep wrapped or irregular lines attached to the preceding language value.
          if active_item is not None and active_language is not None:
            active_item[active_language] += "\n" + line
          elif line:
            current_definition.setdefault("unparsed", []).append(line)

        definitions.append(current_definition)

      entry: dict[str, Any] = {
        "headwords": headwords,
        **annotations,
        "definitions": definitions,
        "reviewed": reviewed,
      }
      if args.include_raw_section:
        entry["raw_headword"] = raw_headword
        entry["raw_definition"] = raw_definition
        entry["publication_status"] = publication_status
      for line in yaml.safe_dump([entry], allow_unicode=True, sort_keys=False, width=120).splitlines(keepends=True):
        output.write("  " + line)
      converted += 1

  if converted != count:
    raise ValueError(f"CSV changed during conversion: expected {count} entries, found {converted}")
  print(f"Converted {converted} entries to {args.output_path}")
