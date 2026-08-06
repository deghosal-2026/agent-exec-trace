#!/usr/bin/env bash
# M13.1 — 3-way LLM detector validation on synthetic traces.
#
# Runs the analytics validator THREE times against the same trace sample:
#   1. Rule-based only (no LLM)     → data/m13/no-llm/
#   2. Rule-based + LLM (4B model)  → data/m13/llm-Qwen3.5-4B-4bit/
#   3. Rule-based + LLM (9B model)  → data/m13/llm-Qwen3.5-9B-MLX-4bit/
# Then generates a 3-way comparison report.
#
# All M13 output is isolated under data/m13/.
#
# Usage:
#   bash scripts/m13/run-llm-validation.sh                 # 25 traces (default)
#   bash scripts/m13/run-llm-validation.sh --traces 50      # override sample size
#   bash scripts/m13/run-llm-validation.sh --skip-llm       # skip LLM passes (debugging)
#   bash scripts/m13/run-llm-validation.sh --skip-4b       # skip 4B pass
#   bash scripts/m13/run-llm-validation.sh --skip-9b        # skip 9B pass

set -euo pipefail

# ── Defaults ────────────────────────────────────────────────────────────
NUM_TRACES=25
SKIP_LLM=0
SKIP_4B=0
SKIP_9B=0
INPUT_DIR="data/traces2/synthetic"
OUTPUT_BASE="data/m13"
NO_LLM_DIR="${OUTPUT_BASE}/no-llm"
LLM_4B_DIR="${OUTPUT_BASE}/llm-Qwen3.5-4B-4bit"
LLM_9B_DIR="${OUTPUT_BASE}/llm-Qwen3.5-9B-MLX-4bit"
COMPARE_DIR="${OUTPUT_BASE}/comparison"

LLM_4B_MODEL="Qwen3.5-4B-4bit"
LLM_9B_MODEL="Qwen3.5-9B-MLX-4bit"

# ── Parse args ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --traces)   NUM_TRACES="$2"; shift 2 ;;
    --skip-llm) SKIP_LLM=1; shift ;;
    --skip-4b) SKIP_4B=1; shift ;;
    --skip-9b) SKIP_9B=1; shift ;;
    --input)   INPUT_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--traces N] [--input DIR] [--skip-llm] [--skip-4b] [--skip-9b]"
      exit 0 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  M13.1 — 3-Way LLM Detector Validation                      ║"
echo "║  Traces: ${NUM_TRACES}    Input: ${INPUT_DIR}"
echo "║  Passes: no-llm + llm-4B + llm-9B"
echo "╚══════════════════════════════════════════════════════════════╝"

# ── Pre-flight checks ─────────────────────────────────────────────────
cd "$(git rev-parse --show-toplevel)"

if [[ ! -d "$INPUT_DIR" ]]; then
  echo "ERROR: synthetic trace directory not found: $INPUT_DIR"
  exit 1
fi

PARQUET_COUNT=$(find "$INPUT_DIR" -name "*.parquet" | wc -l | tr -d ' ')
if [[ "$PARQUET_COUNT" -eq 0 ]]; then
  echo "ERROR: no parquet files found in $INPUT_DIR"
  exit 1
fi
echo "Found $PARQUET_COUNT parquet files in $INPUT_DIR"

# ── Ensure output directories exist (do NOT delete existing) ─────────
echo "Output directory: $OUTPUT_BASE"
mkdir -p "$NO_LLM_DIR" "$LLM_4B_DIR" "$LLM_9B_DIR" "$COMPARE_DIR"

# ── Step 1: Rule-based only (no LLM) ──────────────────────────────────
echo ""
echo "══ Step 1/4: Rule-based only (no LLM) ════════════════════════"
echo "Output: $NO_LLM_DIR"
echo ""

python3 -m analytics.main validate \
  --input "$INPUT_DIR" \
  --output "$NO_LLM_DIR" \
  --max-traces "$NUM_TRACES" \
  --db

# ── Step 2: Rule-based + LLM 4B ────────────────────────────────────────
echo ""
echo "══ Step 2/4: Rule-based + LLM ($LLM_4B_MODEL) ═══════════════"
echo "Output: $LLM_4B_DIR"
echo ""

if [[ "$SKIP_LLM" -eq 1 || "$SKIP_4B" -eq 1 ]]; then
  echo "SKIP: 4B pass skipped"
else
  if curl -s --max-time 3 "http://127.0.0.1:8000/v1/models" >/dev/null 2>&1; then
    echo "LLM server reachable"
  else
    echo "WARNING: LLM server not reachable at http://127.0.0.1:8000/v1"
    echo "Start the MLX server: omlx serve $LLM_4B_MODEL"
  fi
  echo ""

  ANALYTICS_LLM_CHAT_MODEL="$LLM_4B_MODEL" \
  python3 -m analytics.main validate \
    --input "$INPUT_DIR" \
    --output "$LLM_4B_DIR" \
    --max-traces "$NUM_TRACES" \
    --llm-sample "$NUM_TRACES" \
    --llm-batch 10 \
    --db
fi

# ── Step 3: Rule-based + LLM 9B ───────────────────────────────────────
echo ""
echo "══ Step 3/4: Rule-based + LLM ($LLM_9B_MODEL) ═══════════════"
echo "Output: $LLM_9B_DIR"
echo ""

if [[ "$SKIP_LLM" -eq 1 || "$SKIP_9B" -eq 1 ]]; then
  echo "SKIP: 9B pass skipped"
else
  if curl -s --max-time 3 "http://127.0.0.1:8000/v1/models" >/dev/null 2>&1; then
    echo "LLM server reachable"
  else
    echo "WARNING: LLM server not reachable at http://127.0.0.1:8000/v1"
    echo "Start the MLX server: omlx serve $LLM_9B_MODEL"
  fi
  echo ""

  ANALYTICS_LLM_CHAT_MODEL="$LLM_9B_MODEL" \
  python3 -m analytics.main validate \
    --input "$INPUT_DIR" \
    --output "$LLM_9B_DIR" \
    --max-traces "$NUM_TRACES" \
    --llm-sample "$NUM_TRACES" \
    --llm-batch 10 \
    --db
fi

# ── Step 4: 3-way comparison report ───────────────────────────────────
echo ""
echo "══ Step 4/4: Generate 3-way comparison report ════════════════"
echo "Output: $COMPARE_DIR"
echo ""

python3 - <<'PYEOF'
"""Generate a 3-way comparison report: no-llm vs llm-4b vs llm-9b."""
import json
from pathlib import Path

base = Path("data/m13")
dirs = {
    "no-llm": base / "no-llm",
    "llm-4b": base / "llm-Qwen3.5-4B-4bit",
    "llm-9b": base / "llm-Qwen3.5-9B-MLX-4bit",
}
compare = base / "comparison"
compare.mkdir(parents=True, exist_ok=True)

def load_summary(d: Path) -> dict:
    summaries = list(d.rglob("summary.json"))
    if summaries:
        return json.loads(summaries[0].read_text())
    return {}

def load_by_type(d: Path) -> dict[str, int]:
    return load_summary(d).get("anomaly_by_type", {})

summaries = {k: load_summary(v) for k, v in dirs.items()}
by_type = {k: load_by_type(v) for k, v in dirs.items()}

LLM_TYPES = {
    "semantic_loop", "hallucination", "goal_drift",
    "quality_degradation", "confusion_pattern", "output_drift",
}

all_types = sorted(set().union(*[set(t.keys()) for t in by_type.values()]))

rows = []
for t in all_types:
    n = by_type["no-llm"].get(t, 0)
    b4 = by_type["llm-4b"].get(t, 0)
    b9 = by_type["llm-9b"].get(t, 0)
    is_llm_only = t in LLM_TYPES
    rows.append({
        "anomaly_type": t,
        "no_llm": n,
        "llm_4b": b4,
        "llm_9b": b9,
        "delta_4b": b4 - n,
        "delta_9b": b9 - n,
        "category": "llm-only" if is_llm_only else "rule-based",
    })

report = {
    "traces_sampled": summaries["no-llm"].get("traces_processed", "N/A"),
    "no_llm_total": summaries["no-llm"].get("anomaly_count", 0),
    "llm_4b_total": summaries["llm-4b"].get("anomaly_count", 0),
    "llm_9b_total": summaries["llm-9b"].get("anomaly_count", 0),
    "no_llm_types": len([r for r in rows if r["no_llm"] > 0]),
    "llm_4b_types": len([r for r in rows if r["llm_4b"] > 0]),
    "llm_9b_types": len([r for r in rows if r["llm_9b"] > 0]),
    "llm_4b_only_types": len([r for r in rows if r["llm_4b"] > 0 and r["category"] == "llm-only"]),
    "llm_9b_only_types": len([r for r in rows if r["llm_9b"] > 0 and r["category"] == "llm-only"]),
    "per_detector": rows,
}

(compare / "comparison.json").write_text(json.dumps(report, indent=2))

lines = [
    "# M13.1 — 3-Way Comparison: No-LLM vs LLM-4B vs LLM-9B",
    "",
    f"**Traces sampled:** {report['traces_sampled']}",
    "",
    "| Metric | No LLM | LLM 4B | LLM 9B |",
    "|---|---|---|---|",
    f"| Total anomalies | {report['no_llm_total']} | {report['llm_4b_total']} | {report['llm_9b_total']} |",
    f"| Types fired | {report['no_llm_types']} | {report['llm_4b_types']} | {report['llm_9b_types']} |",
    f"| LLM-only types fired | — | {report['llm_4b_only_types']} | {report['llm_9b_only_types']} |",
    "",
    "## Per-Detector Breakdown",
    "",
    "| Anomaly Type | No LLM | LLM 4B | LLM 9B | Δ 4B | Δ 9B | Category |",
    "|---|---|---|---|---|---|---|",
]
for r in rows:
    d4b = f"{r['delta_4b']:+d}" if r['delta_4b'] != 0 else "0"
    d9b = f"{r['delta_9b']:+d}" if r['delta_9b'] != 0 else "0"
    lines.append(f"| `{r['anomaly_type']}` | {r['no_llm']} | {r['llm_4b']} | {r['llm_9b']} | {d4b} | {d9b} | {r['category']} |")

lines += ["", f"_Report saved to `{compare}/comparison.json`_"]
(compare / "comparison-report.md").write_text("\n".join(lines))
print("\n".join(lines))
PYEOF

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  M13.1 complete. Results in $OUTPUT_BASE"
echo "║  Comparison: $COMPARE_DIR/comparison-report.md"
echo "╚══════════════════════════════════════════════════════════════╝"
