FROM python:3.11-slim

WORKDIR /app

# Copy project structure
COPY bank-node/local-gnn-model/pyproject.toml .
RUN pip install .

COPY bank-node/local-gnn-model/src/ ./src/
COPY shared/ /app/shared/

EXPOSE 9002

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "9002"]
