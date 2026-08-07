"""Export Postgres run summaries + anomalies to per-agent parquet files."""

import argparse
import json
import os

import psycopg2
import pyarrow.parquet as pq

SCHEMA_COLUMNS = [
    "run_id",
    "agent_name",
    "agent_version",
    "trace_id",
    "status",
    "duration_ms",
    "total_tool_calls",
    "total_retries",
    "estimated_cost",
    "anomaly_types",
    "anomaly_details",
]


def fetch_agents(cur) -> list[str]:
    cur.execute("SELECT DISTINCT agent_name FROM run_summaries ORDER BY agent_name")
    return [r[0] for r in cur.fetchall()]


def fetch_anomalies(cur, run_ids) -> dict[str, list[tuple[str, str, str, str]]]:
    cur.execute(
        """
        SELECT run_id, anomaly_type, severity, COALESCE(explanation, '')
        FROM anomalies
        WHERE run_id = ANY(%s)
        ORDER BY run_id, detected_at
        """,
        (run_ids,),
    )
    out: dict[str, list[tuple[str, str, str, str]]] = {}
    for run_id, atype, sev, expl in cur.fetchall():
        out.setdefault(run_id, []).append((atype, sev, expl, ""))
    return out


def fk_evidence(cur, run_id) -> str:
    """Placeholder for evidence; the legacy export stored a JSON detail blob."""
    cur.execute(
        """
        SELECT COALESCE(evidence::text, '')
        FROM anomalies WHERE run_id = %s ORDER BY detected_at
        """,
        (run_id,),
    )
    rows = cur.fetchall()
    return "[" + ",".join(r[0] for r in rows if r[0]) + "]"


def export(dsn: str, output_dir: str, agents: list[str] | None = None) -> None:
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    os.makedirs(output_dir, exist_ok=True)

    agent_list = agents or fetch_agents(cur)

    for agent in agent_list:
        cur.execute(
            """
            SELECT run_id, agent_name, agent_version, trace_id, status,
                   duration_ms, total_tool_calls, total_retries,
                   estimated_cost
            FROM run_summaries
            WHERE agent_name = %s
            ORDER BY started_at
            """,
            (agent,),
        )
        rows = cur.fetchall()
        run_ids = [r[0] for r in rows]
        anomaly_map = fetch_anomalies(cur, run_ids)

        records = []
        for r in rows:
            run_id, run_agent, ver, trace_id, status, dur, tools, retries, cost = r
            anoms = anomaly_map.get(run_id, [])
            anomaly_types = [a[0] for a in anoms]
            anomaly_details = _detail_json(anoms)
            records.append({
                "run_id": run_id,
                "agent_name": run_agent,
                "agent_version": ver,
                "trace_id": trace_id,
                "status": status,
                "duration_ms": dur,
                "total_tool_calls": tools,
                "total_retries": retries,
                "estimated_cost": float(cost or 0),
                "anomaly_types": anomaly_types,
                "anomaly_details": anomaly_details,
            })

        import pyarrow as pa
        table = pa.Table.from_pylist(records, schema=(
            pa.schema([("run_id", pa.string()), ("agent_name", pa.string()),
                       ("agent_version", pa.string()), ("trace_id", pa.string()),
                       ("status", pa.string()), ("duration_ms", pa.int64()),
                       ("total_tool_calls", pa.int64()), ("total_retries", pa.int64()),
                       ("estimated_cost", pa.float64()),
                       ("anomaly_types", pa.list_(pa.string())),
                       ("anomaly_details", pa.string())])
        ))
        safe = agent.replace("/", "-")
        path = os.path.join(output_dir, f"{safe}.parquet")
        pq.write_table(table, path)
        print(f"{agent}: {len(records)} runs -> {path}")

    cur.close()
    conn.close()


def _detail_json(anoms) -> str:
    parts = []
    for atype, sev, expl, _ in anoms:
        parts.append({"type": atype, "severity": sev, "explanation": expl})
    return json.dumps(parts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("DSN"))
    ap.add_argument("--out", default="data/m13-real/export")
    ap.add_argument("--agent", action="append")
    args = ap.parse_args()
    export(args.dsn, args.out, args.agent)