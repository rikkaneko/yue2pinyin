import csv
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/convert_words_hk.py"


def test_multiline_annotations_definitions_and_examples(tmp_path: Path) -> None:
  source = tmp_path / "source.csv"
  output = tmp_path / "output.yaml"
  with source.open("w", encoding="utf-8", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerow(["", "", "--- Generated 2026-09-27 20:05:02.987704 (UTC) - rights notice"])
    writer.writerow([""])
    writer.writerow([
      "123",
      "模型:mou4 jing4:mou6 jing4,model:!",
      "(pos:名詞)(pos:語素)(sim:樣板)(sim:模本)(label:外來語)(ant:原件)\n"
      "<explanation>\nyue:第一個定義\neng:first definition\n"
      "<eg>\nyue:模型車 (mou4 jing4 ce1)\nEng:model car\n"
      "<eg>\nzho:模型車\nyue:冇讀音\neng:no reading\n"
      "----\n<explanation>\nyue:第二個定義\neng:second definition\n"
      "<eg>\nyue:佢有模型。 (keoi5 jau5 mou4 jing4.)\neng:He has a model.",
      "模形",
      "OK",
      "已公開",
    ])
    writer.writerow(["124", "跳馬", "未有內容 NO DATA", "", "OK", "未公開"])
    writer.writerow([
      "125", "風流:fung1 lau4", "(pos:形容詞)\nyue:直接定義\neng:direct definition\n"
      "<eg>\nyue:風流韻事 (舊指文人活動)\neng:old meaning",
      "",
      "未經覆核，可能有錯漏 UNREVIEWED ENTRY - MAY CONTAIN ERRORS OR OMISSIONS",
      "已公開",
    ])

  result = subprocess.run(
    [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
    capture_output=True,
    text=True,
    check=True,
  )
  assert "Converted 3 entries" in result.stdout
  document = yaml.safe_load(output.read_text(encoding="utf-8"))
  assert document["metadata"] == {
    "total_entries": 3,
    "last_updated": "2026-09-27T20:05:02.987704+00:00",
  }
  entries = document["entries"]
  assert len(entries) == 3
  first = entries[0]
  assert "123" not in str(first)
  assert first["headwords"] == [
    {"word": "模型", "readings": ["mou4 jing4", "mou6 jing4"]},
    {"word": "model", "readings": ["!"]},
  ]
  assert first["pos"] == ["名詞", "語素"]
  assert first["sim"] == ["樣板", "模本"]
  assert first["label"] == ["外來語"]
  assert first["ant"] == ["原件"]
  assert first["reviewed"] == 1
  assert "source_field_4" not in first
  assert "publication_status" not in first
  assert "review_status" not in first
  assert "raw_headword" not in first
  assert "raw_definition" not in first
  assert len(first["definitions"]) == 2
  assert first["definitions"][0]["explanation"] == [{"yue": "第一個定義", "eng": "first definition"}]
  assert first["definitions"][0]["eg"] == [
    {"jyutpin": "mou4 jing4 ce1", "yue": "模型車", "eng": "model car"},
    {"jyutpin": None, "zho": "模型車", "yue": "冇讀音", "eng": "no reading"},
  ]
  assert first["definitions"][1]["eg"][0]["jyutpin"] == "keoi5 jau5 mou4 jing4."
  assert first["definitions"][1]["eg"][0]["yue"] == "佢有模型。"
  assert entries[1]["headwords"] == [{"word": "跳馬", "readings": []}]
  assert entries[1]["definitions"] == []
  assert entries[2]["definitions"][0]["explanation"] == [{"yue": "直接定義", "eng": "direct definition"}]
  assert entries[2]["definitions"][0]["eg"][0]["yue"] == "風流韻事 (舊指文人活動)"
  assert entries[2]["definitions"][0]["eg"][0]["jyutpin"] is None
  assert entries[2]["reviewed"] == 0

  raw_output = tmp_path / "with_raw.yaml"
  subprocess.run(
    [
      sys.executable, str(SCRIPT), "--input", str(source), "--output", str(raw_output),
      "--include-raw-section",
    ],
    capture_output=True,
    text=True,
    check=True,
  )
  raw_document = yaml.safe_load(raw_output.read_text(encoding="utf-8"))
  assert raw_document["metadata"] == document["metadata"]
  raw_entries = raw_document["entries"]
  assert raw_entries[0]["raw_headword"] == "模型:mou4 jing4:mou6 jing4,model:!"
  assert raw_entries[0]["raw_definition"].startswith("(pos:名詞)(pos:語素)")
  assert raw_entries[0]["publication_status"] == "已公開"
  assert raw_entries[2]["reviewed"] == 0


def test_missing_export_timestamp_and_empty_entries(tmp_path: Path) -> None:
  source = tmp_path / "empty.csv"
  output = tmp_path / "empty.yaml"
  with source.open("w", encoding="utf-8", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerow(["", "", "rights notice without timestamp"])
    writer.writerow([""])
  subprocess.run(
    [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
    capture_output=True,
    text=True,
    check=True,
  )
  assert yaml.safe_load(output.read_text(encoding="utf-8")) == {
    "metadata": {"total_entries": 0, "last_updated": None},
    "entries": [],
  }


def test_bad_column_count_fails(tmp_path: Path) -> None:
  source = tmp_path / "bad.csv"
  output = tmp_path / "output.yaml"
  source.write_text("a,b,c\n\n1,2,3\n", encoding="utf-8")
  result = subprocess.run(
    [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
    capture_output=True,
    text=True,
  )
  assert result.returncode != 0
  assert "expected 6" in result.stderr


def test_input_and_output_cannot_be_same_file(tmp_path: Path) -> None:
  source = tmp_path / "source.csv"
  source.write_text("", encoding="utf-8")
  result = subprocess.run(
    [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(source)],
    capture_output=True,
    text=True,
  )
  assert result.returncode != 0
  assert "must differ" in result.stderr
