"""Export 400 real-agent traces from Jaeger as span-level parquet.

Writes one span-level parquet per agent into ``data/m13-real/traces/`` in the
format the analytics ``validate`` command loads (each parquet holds many traces
grouped by ``source_row_idx``; rows carry ``trace_id``, ``span_id``,
``parent_span_id``, ``operation_name``, ``start_time``, ``end_time``,
``duration_ms``, ``attributes_json``, ``status``, ``source_row_idx``,
``source_dataset``).
"""

import argparse
import datetime as dt
import json
import os

import httpx
import pyarrow as pa
import pyarrow.parquet as pq

SERVICES = [
    "m13-raw-agent",
    "m13-pydantic-agent",
    "m13-pydantic-v1-agent",
    "m13-langgraph-agent",
]

SERVICE_TO_AGENT = {
    "m13-raw-agent": "raw-support-triage",
    "m13-pydantic-agent": "pydantic-weather",
    "m13-pydantic-v1-agent": "pydantic-v1-weather",
    "m13-langgraph-agent": "request-triage",
}

SPAN_SCHEMA = pa.schema([
    ("trace_id", pa.string()),
    ("span_id", pa.string()),
    ("parent_span_id", pa.string()),
    ("operation_name", pa.string()),
    ("start_time", pa.timestamp("us")),
    ("end_time", pa.timestamp("us")),
    ("duration_ms", pa.int64()),
    ("attributes_json", pa.string()),
    ("status", pa.string()),
    ("source_row_idx", pa.int64()),
    ("source_dataset", pa.string()),
])


def _tags_to_attrs(tags: list[dict]) -> dict:
    attrs = {}
    for tag in tags or []:
        key = tag.get("key")
        if key is None:
            continue
        val = tag.get("value")
        if val is not None:
            attrs[key] = val
    return attrs


def _us_to_pyarrow(us: int):
    if not us:
        return None
    return dt.datetime.fromtimestamp(us / 1_000_000, tz=dt.timezone.utc)


def fetch_service(jaeger: str, service: str) -> list[dict]:
    """Fetch all traces for a service. Jaeger caps at ~100 per page; loop until fewer returned."""
    all_traces: list[dict] = []
    seen: set[str] = set()
    while True:
        resp = httpx.get(
            f"{jaeger}/api/traces",
            params={"service": service, "limit": 1000},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            break
        new = 0
        for trace in data:
            tid = trace.get("traceID", "")
            if tid in seen:
                continue
            seen.add(tid)
            all_traces.append(trace)
            new += 1
        if len(data) < 1000 or new == 0:
            break
    return all_traces


def main(jaeger: str, out: str) -> None:
    os.makedirs(out, exist_ok=True)
    rows: list[dict] = []
    for service in SERVICES:
        agent = SERVICE_TO_AGENT[service]
        traces = fetch_service(jaeger, service)
        for trace_idx, trace in enumerate(traces, start=1):
            trace_id = trace.get("traceID", "")
            spans = trace.get("spans", [])
            for sp in spans:
                start_us = sp.get("startTime", 0)
                dur_us = sp.get("duration", 0)
                refs = sp.get("references") or []
                parent = refs[0].get("spanID", "") if refs else None
                attrs = _tags_to_attrs(sp.get("tags"))
                rows.append({
                    "trace_id": trace_id,
                    "span_id": sp.get("spanID", ""),
                    "parent_span_id": parent,
                    "operation_name": sp.get("operationName", ""),
                    "start_time": _us_to_pyarrow(start_us),
                    "end_time": _us_to_pyarrow(start_us + dur_us),
                    "duration_ms": int(dur_us / 1000) if dur_us else None,
                    "attributes_json": json.dumps(attrs, default=str),
                    "status": sp.get("status", ""),
                    "source_row_idx": trace_idx,
                    "source_dataset": agent,
                })
        print(f"{agent}: {len(traces)} traces, {len(rows)} spans total")

    for agent in SERVICE_TO_AGENT.values():
        subset = [r for r in rows if r["source_dataset"] == agent]
        table = pa.Table.from_pylist(subset, schema=SPAN_SCHEMA)
        pq.write_table(table, f"{out}/{agent}.parquet")
        print(f"  wrote {out}/{agent}.parquet ({len(subset)} spans)")

    print(f"TOTAL spans: {len(rows)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--jaeger", default="http://localhost:16686")
    ap.add_argument("--out", default="data/m13-real/traces")
    args = ap.parse_args()
    main(args.jaeger, args.out)