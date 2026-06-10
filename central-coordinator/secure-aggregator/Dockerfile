FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install .

COPY src/ ./src/

EXPOSE 8002

CMD ["python", "src/main.py"]
