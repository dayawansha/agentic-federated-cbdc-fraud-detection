FROM python:3.11-slim

WORKDIR /app

COPY central-coordinator/policy-manager/pyproject.toml .
RUN pip install .

COPY central-coordinator/policy-manager/src/ ./src/
COPY shared/ /app/shared/

EXPOSE 8003

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"]
