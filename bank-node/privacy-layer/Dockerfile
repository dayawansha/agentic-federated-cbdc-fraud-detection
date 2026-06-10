FROM python:3.11-slim

WORKDIR /app

# Copy project structure
COPY bank-node/privacy-layer/pyproject.toml .
RUN pip install .

COPY bank-node/privacy-layer/src/ ./src/
COPY shared/ /app/shared/

EXPOSE 9003

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "9003"]
