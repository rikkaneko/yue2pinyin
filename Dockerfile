FROM python:3.14-slim

WORKDIR /app
COPY pyproject.toml ./
COPY yen2pinyin ./yen2pinyin
RUN pip install --no-cache-dir .
COPY assests ./assests

RUN useradd --create-home --uid 10001 appuser && chown appuser:appuser /app;
USER appuser
EXPOSE 8000
CMD ["uvicorn", "yen2pinyin.api:app", "--host", "0.0.0.0", "--port", "8000"]
