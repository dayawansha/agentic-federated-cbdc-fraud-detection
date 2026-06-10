FROM python:3.11-slim

WORKDIR /app

# Copy project structure
COPY bank-node/local-agent/pyproject.toml .
RUN pip install .

COPY bank-node/local-agent/src/ ./src/
COPY shared/ /app/shared/

EXPOSE 9001

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "9001"]
