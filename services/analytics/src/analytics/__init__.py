"""Analytics service for agent execution trace observability.

This package provides a complete ingestion + analysis pipeline for agent traces:

**Data flow:**

1. **Ingestion** (``ingest.py``, ``worker.py``): Traces are fetched from Jaeger,
   parsed into ``SpanNode`` trees, summarized into ``RunSummary`` objects, and
   persisted to PostgreSQL.  A background worker polls Jaeger on a configurable
   interval.

2. **Anomaly Detection** (``detectors/``): 35 rule-based anomaly detectors (plus
   6 LLM-augmented detectors) analyze each run for issues like tool loops,
   retry storms, cost spikes, output drift, hallucinations, and more.  Each
   detector is independently toggle-able via ``ANALYTICS_DETECTOR_DISABLED``.

3. **Alerting** (``alerts.py``): Detected anomalies are dispatched to a
   configurable webhook endpoint for integration with external notification
   systems.

4. **Materialization** (``materializer.py``): After each polling cycle, the
   worker aggregates raw run summaries into fleet rollups and version cohort
   summaries for efficient dashboard querying.

5. **Trace Pipeline** (``trace_pipeline/``): A separate pipeline downloads
   agent traces from Hugging Face datasets, converts them to OTel-compatible
   SpanNode format, validates the tree structure, stores results as parquet
   files, and optionally feeds them through the analytics ingestion pipeline.

**Key design decisions:**

- **Graceful degradation**: All LLM detectors return ``None`` when the LLM
  server is unavailable, so rule-based detection continues unimpeded.
- **Database-first**: PostgreSQL (asyncpg) stores all summaries, anomalies,
  rollups, and cohorts.  The database is the canonical source of truth.
- **Streaming**: The Hugging Face downloader uses streaming mode to avoid
  materializing entire datasets in memory.
- **Configurable thresholds**: Every detector threshold is driven by
  ``ANALYTICS_*`` environment variables via Pydantic settings.
"""
