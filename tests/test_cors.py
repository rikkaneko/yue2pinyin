"""CORS configuration and preflight behavior for a separately hosted frontend."""

import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from yue2pinyin.api import Settings


def test_cors_settings_accept_supported_origins() -> None:
  settings = Settings(
    _env_file=None,
    cors_origins="https://app.nekoid.cc, https://*.nekoid.cc, http://localhost:*",
  )
  assert settings.cors_origins == [
    "https://app.nekoid.cc", "https://*.nekoid.cc", "http://localhost:*",
  ]
  assert Settings(_env_file=None, cors_origins="").cors_origins == []


@pytest.mark.parametrize("origin", [
  "*", "ftp://example.com", "https://example.com/path", "https://example.com/",
  "https://*.nekoid..cc", "http://localhost:abc", "http://localhost:99999",
  "https://user@example.com", "https://example.com?x=1",
  "https://example.com,",
])
def test_cors_settings_reject_malformed_origins(origin: str) -> None:
  with pytest.raises(ValidationError):
    Settings(_env_file=None, cors_origins=origin)


def test_cors_actual_and_preflight_responses() -> None:
  environment = os.environ.copy()
  environment["YUE2PINYIN_CORS_ORIGINS"] = (
    "https://app.nekoid.cc,https://*.nekoid.cc,http://localhost:*"
  )
  script = """
from fastapi.testclient import TestClient
from yue2pinyin.api import app

client = TestClient(app)
for origin in (
  "https://app.nekoid.cc", "https://a.nekoid.cc", "https://a.b.nekoid.cc",
  "http://localhost:3000", "http://localhost:65535",
):
  response = client.options(
    "/approx_pinyin",
    headers={
      "Origin": origin,
      "Access-Control-Request-Method": "POST",
      "Access-Control-Request-Headers": "content-type",
    },
  )
  assert response.status_code == 200, (origin, response.text)
  assert response.headers["access-control-allow-origin"] == origin
  assert "POST" in response.headers["access-control-allow-methods"]
  assert "content-type" in response.headers["access-control-allow-headers"].lower()
  assert response.headers["access-control-max-age"] == "86400"

for origin in (
  "https://nekoid.cc", "https://evilnekoid.cc", "http://localhost",
  "http://localhost.evil.cc:3000", "http://a.nekoid.cc", "http://localhost:65536",
):
  response = client.options(
    "/word", headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
  )
  assert response.status_code == 400, (origin, response.text)
  assert "access-control-allow-origin" not in response.headers

actual = client.get("/openapi.json", headers={"Origin": "https://a.nekoid.cc"})
assert actual.status_code == 200
assert actual.headers["access-control-allow-origin"] == "https://a.nekoid.cc"
denied = client.get("/openapi.json", headers={"Origin": "https://nekoid.cc"})
assert denied.status_code == 200
assert "access-control-allow-origin" not in denied.headers
"""
  result = subprocess.run(
    [sys.executable, "-c", script], capture_output=True, text=True, env=environment,
  )
  assert result.returncode == 0, result.stderr


def test_invalid_cors_environment_rejects_app_start() -> None:
  environment = os.environ.copy()
  environment["YUE2PINYIN_CORS_ORIGINS"] = "https://example.com/path"
  result = subprocess.run(
    [sys.executable, "-c", "from yue2pinyin.api import app"],
    capture_output=True, text=True, env=environment,
  )
  assert result.returncode != 0
  assert "Invalid CORS origin" in result.stderr
