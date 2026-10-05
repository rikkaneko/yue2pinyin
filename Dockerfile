# syntax=docker/dockerfile:1

FROM python:3.14-slim

WORKDIR /app
COPY pyproject.toml ./
COPY yen2pinyin ./yen2pinyin
RUN --mount=type=cache,target=/root/.cache/pip pip install .
COPY assests ./assests
COPY scripts/build_flashcard_db.py ./scripts/build_flashcard_db.py
# Prefer the database supplied in the build context; otherwise generate it from YAML.
RUN --mount=type=bind,source=.,target=/build-context,readonly \
    if [ -f /build-context/words.sqlite3 ]; then \
      cp /build-context/words.sqlite3 ./words.sqlite3; \
    else \
      python scripts/build_flashcard_db.py --input ./assests/words-hk/all-latest.yaml --output ./words.sqlite3; \
    fi;

RUN useradd --system --uid 10001 appuser && chown -R appuser:appuser /app;
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn yen2pinyin.api:app --host 0.0.0.0 --port \"${YEN2PINYIN_PORT:-8000}\";"]
