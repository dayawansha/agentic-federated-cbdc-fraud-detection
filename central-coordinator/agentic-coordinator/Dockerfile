FROM python:3.11-slim

WORKDIR /app

COPY central-coordinator/agentic-coordinator/pyproject.toml .
RUN pip install .

COPY central-coordinator/agentic-coordinator/src/ ./src/
COPY shared/ /app/shared/

EXPOSE 8001

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
