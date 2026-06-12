FROM python:3.11-slim

WORKDIR /app

# Copy project metadata and source for installation
COPY central-coordinator/model-registry/pyproject.toml .
COPY central-coordinator/model-registry/src/ ./src/

# Install dependencies and the project (with pip cache to save bandwidth)
ENV PIP_DEFAULT_TIMEOUT=19000

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install .

# Copy shared modules
COPY shared/ /app/shared/

EXPOSE 8004

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8004"]
