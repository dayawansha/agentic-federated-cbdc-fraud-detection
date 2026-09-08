FROM python:3.11-slim

WORKDIR /app

# Copy project metadata and source for installation
COPY central-coordinator/federated-model-aggregator/pyproject.toml .
COPY central-coordinator/federated-model-aggregator/src/ ./src/

# Install dependencies and the project (with pip cache to save bandwidth)
ENV PIP_DEFAULT_TIMEOUT=19000

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
        torch \
        --index-url https://download.pytorch.org/whl/cpu

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
        "numpy>=1.24.0" \
        "fastapi>=0.100.0" \
        "uvicorn>=0.23.0" \
        "pydantic>=2.0.0" \
        "python-dotenv>=1.0.0" \
        "cryptography>=41.0.0"

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps .


EXPOSE 8002

CMD ["python", "src/main.py"]
