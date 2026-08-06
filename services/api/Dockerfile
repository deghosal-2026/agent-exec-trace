# monorepo/api: REST API service serving timeline, fleet, compare, and anomaly endpoints.
# Runs uvicorn with FastAPI, connecting to the shared Postgres read-model database.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]