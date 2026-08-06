# monorepo/analytics: polling worker that fetches traces from Jaeger, runs all 35 detectors,
# persists anomalies, and materializes fleet rollups and version cohorts into Postgres.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "analytics.main", "run-worker"]