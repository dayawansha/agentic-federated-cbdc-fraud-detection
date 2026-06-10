FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY bank-node/transaction-graph/pyproject.toml .
RUN pip install --no-cache-dir .

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY bank-node/transaction-graph/src/ ./src/
COPY shared/ /app/shared/

EXPOSE 9004

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "9004"]

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

EXPOSE 9004
EXPOSE 50051

CMD ["python", "src/main.py"]
