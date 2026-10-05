FROM python:3.14-slim

WORKDIR /app
COPY pyproject.toml ./
COPY yen2pinyin ./yen2pinyin
RUN pip install --no-cache-dir .
COPY assests ./assests
COPY scripts/build_flashcard_db.py ./scripts/build_flashcard_db.py
RUN python scripts/build_flashcard_db.py --input ./assests/words-hk/all-latest.yaml --output ./words.sqlite3

RUN useradd --system --uid 10001 appuser && chown -R appuser:appuser /app;
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn yen2pinyin.api:app --host 0.0.0.0 --port \"${YEN2PINYIN_PORT:-8000}\";"]
