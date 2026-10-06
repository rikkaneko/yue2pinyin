import json
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from yue2pinyin.api import PROJECT_ROOT, Settings, app


BUILD_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_flashcard_db.py"


def test_startup_reads_dotenv_from_working_directory(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
  (tmp_path / "words.csv").write_text("words,jyutpin\n你好,nei5 hou2\n", encoding="utf-8")
  (tmp_path / "characters.json").write_text(json.dumps({"你": {"nei5": 1}}), encoding="utf-8")
  (tmp_path / "flashcards.yaml").write_text("metadata: {}\nentries:\n  - headwords: [{word: 你好, readings: [nei5 hou2]}]\n    pos: []\n    sim: []\n    label: []\n    ant: []\n    img: []\n    ref: []\n    definitions: [{explanation: [], eg: [{yue: 你好, jyutpin: nei5 hou2}]}]\n    reviewed: 1\n", encoding="utf-8")
  subprocess.run([sys.executable, str(BUILD_SCRIPT), "--input", str(tmp_path / "flashcards.yaml"),
                  "--output", str(tmp_path / "flashcards.sqlite3")], check=True)
  (tmp_path / ".env").write_text(
    "YUE2PINYIN_WORDS_PATH=words.csv\n"
    "YUE2PINYIN_CHARACTERS_PATH=characters.json\n"
    "YUE2PINYIN_CACHE_PATH=cache.dat\n"
    "YUE2PINYIN_FLASHCARD_DB_PATH=flashcards.sqlite3\n"
    "YUE2PINYIN_CORS_ORIGINS=http://localhost:*\n",
    encoding="utf-8",
  )
  for key in ("WORDS_PATH", "CHARACTERS_PATH", "CACHE_PATH", "FLASHCARD_DB_PATH"):
    monkeypatch.delenv(f"YUE2PINYIN_{key}", raising=False)
  monkeypatch.chdir(tmp_path)
  with TestClient(app) as client:
    assert client.post("/jyutpin", json={"text": "你好"}).json()["jyutpin_words"] == ["nei5 hou2"]
  assert Settings(_env_file=Path.cwd() / ".env").cors_origins == ["http://localhost:*"]
  assert (tmp_path / "cache.dat").exists()


def test_environment_override_and_missing_dotenv(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
  (tmp_path / ".env").write_text(
    "YUE2PINYIN_WORDS_PATH=from-file.csv\n"
    "YUE2PINYIN_CACHE_PATH=from-file.dat\n",
    encoding="utf-8",
  )
  for key in ("WORDS_PATH", "CHARACTERS_PATH", "CACHE_PATH", "FLASHCARD_DB_PATH"):
    monkeypatch.delenv(f"YUE2PINYIN_{key}", raising=False)
  monkeypatch.chdir(tmp_path)
  monkeypatch.setenv("YUE2PINYIN_WORDS_PATH", "from-process.csv")
  settings = Settings(_env_file=Path.cwd() / ".env")
  assert settings.words_path == Path("from-process.csv")
  assert settings.cache_path == Path("from-file.dat")

  monkeypatch.delenv("YUE2PINYIN_WORDS_PATH")
  empty_directory = tmp_path / "no-env"
  empty_directory.mkdir()
  monkeypatch.chdir(empty_directory)
  monkeypatch.setenv("YUE2PINYIN_WORDS_PATH", "legacy.csv")
  defaults = Settings(_env_file=Path.cwd() / ".env")
  assert defaults.words_path == PROJECT_ROOT / "assests/rime-cantonese/jyut6ping3.words.dict.csv"
  assert defaults.characters_path == PROJECT_ROOT / "assests/words-hk/charlist.json"
  assert defaults.cache_path == PROJECT_ROOT / "jyutping.dat"
  assert defaults.flashcard_db_path == PROJECT_ROOT / "words.sqlite3"
  assert defaults.cors_origins == []
