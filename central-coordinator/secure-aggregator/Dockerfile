FROM python:3.11-slim

WORKDIR /app

COPY central-coordinator/secure-aggregator/pyproject.toml .
RUN pip install .

COPY central-coordinator/secure-aggregator/src/ ./src/
COPY shared/ /app/shared/

EXPOSE 8002

CMD ["python", "src/main.py"]
