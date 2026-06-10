FROM python:3.11-slim

WORKDIR /app

COPY bank-node/alerting/pyproject.toml .
RUN pip install .

COPY bank-node/alerting/src/ ./src/
COPY shared/ /app/shared/

EXPOSE 9005

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "9005"]
