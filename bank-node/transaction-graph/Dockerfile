FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata and source for installation
COPY bank-node/transaction-graph/pyproject.toml .
COPY bank-node/transaction-graph/src/ ./src/

# Install dependencies and the project (with pip cache to save bandwidth)
ENV PIP_DEFAULT_TIMEOUT=19000

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install .

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code and shared modules
COPY bank-node/transaction-graph/src/ ./src/
COPY shared/ /app/shared/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

EXPOSE 9004
EXPOSE 50051

CMD ["python", "src/main.py"]
