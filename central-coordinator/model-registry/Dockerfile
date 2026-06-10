FROM python:3.11-slim

WORKDIR /app

COPY central-coordinator/model-registry/pyproject.toml .
RUN pip install .

COPY central-coordinator/model-registry/src/ ./src/
COPY shared/ /app/shared/

EXPOSE 8004

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8004"]
