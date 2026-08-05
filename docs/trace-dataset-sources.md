# Open Source Agent Trace Datasets — Sources for 30K+ Samples

## Primary Sources (Hugging Face)

### V1 Datasets (chat/log format — downloaded)

| # | Dataset | Rows | Description | URL |
|---|---|---|---|---|
| 1 | `agent-data/misc-merged-claude-code-traces-v1` | **32.1K** | Real Claude Code agent traces merged from multiple sources | huggingface.co/datasets/agent-data/misc-merged-claude-code-traces-v1 |
| 2 | `juliensimon/open-agent-traces` | **17K** | Open agent traces from multiple frameworks | huggingface.co/datasets/juliensimon/open-agent-traces |
| 3 | `lambda/hermes-agent-reasoning-traces` | **14.7K** | Agent reasoning traces for Hermes model | huggingface.co/datasets/lambda/hermes-agent-reasoning-traces |
| 4 | `DCAgent/neulab-nebius-swe-agent-trajectories-sandboxes-traces-terminus-2` | **12K** | SWE agent trajectories with sandbox traces | huggingface.co/datasets/DCAgent/neulab-nebius-swe-agent-trajectories-sandboxes-traces-terminus-2 |
| 5 | `agent-data/code-contests-sandboxes-traces-terminus-2` | **10K** | Code contest agent traces | huggingface.co/datasets/agent-data/code-contests-sandboxes-traces-terminus-2 |
| 6 | `YunjueTech/Yunjue-Agent-Traces` | **4K** | Agent execution traces | huggingface.co/datasets/YunjueTech/Yunjue-Agent-Traces |
| 7 | `vincentoh/sandbagging-agent-traces` | **3.2K** | Sandbagging agent behavior traces | huggingface.co/datasets/vincentoh/sandbagging-agent-traces |
| 8 | `juliensimon/agent-traces-code-review-pipeline` | **2K** | Code review agent pipeline traces | huggingface.co/datasets/juliensimon/agent-traces-code-review-pipeline |
| 9 | `juliensimon/agent-traces-data-pipeline-debugging` | **2K** | Data pipeline debugging traces | huggingface.co/datasets/juliensimon/agent-traces-data-pipeline-debugging |
| 10 | `juliensimon/agent-traces-market-research` | **1.7K** | Market research agent traces | huggingface.co/datasets/juliensimon/agent-traces-market-research |

**V1 limitation:** These datasets are primarily flat chat logs / reasoning transcripts. Only ~7.5% have tool names and 0% have retry semantics. 63% lack operation taxonomy entirely.

### V2 Datasets (structured execution format — targeted for tool-use, retry, cost coverage)

| # | Dataset | Rows | Description | Key Features |
|---|---|---|---|---|
| 1 | `Exgentic/agent-llm-traces-v2` | **10K** | OpenTelemetry-shaped execution traces | OTel format, tool-use, gen-ai spans, SWE-bench, BrowseComp, τ² |
| 2 | `DiscoPosse/agent-llm-traces` | **~5K** | Multi-benchmark OTel agent traces | OpenTelemetry, multi-benchmark, structured spans |
| 3 | `trace-commons/agent-traces` | **~1K** | Claude Code coding sessions | Tool-use tagged, JSONL sessions with tool calls |
| 4 | `aisa-group/instrumental-choices-agent-traces` | **1.7K** | Agent safety evaluation trajectories | Tool-use, Inspect AI framework |
| 5 | `mcphunt-benchmark/mcphunt-agent-traces` | **~500** | MCP agent tool execution traces | Tool execution, cross-boundary MCP calls |
| 6 | `kingkw1/read-along-ai-agent-traces` | **~200** | Pair-programming agent traces | Coding agent sessions with tool calls |
| 7 | `open-agent-leaderboard/traces` | **~700** | Agent leaderboard evaluation traces | Multi-agent evaluation runs |
| 8 | `netpreme/coding_agent_traces` | **~300** | Claude Code vs custom model traces | Coding agent with tool calls |

**Usage:** `python -m analytics.main download-traces --datasets-version v2 --target 150000`

## 15 GitHub OSS Agents (Self-Instrument)

| # | Agent | Framework | Stars | Failure patterns |
|---|---|---|---|---|
| 1-4 | langchain-ai/langgraph (4 examples) | LangGraph | 38.8k | Routing loops, HITL timeout, replanning, self-critique |
| 5-8 | crewAIInc/crewAI-examples (4 examples) | CrewAI | 6.1k | Inter-crew deadlock, quality loops, parallel cost, API retries |
| 9 | microsoft/autogen (magentic-one) | AutoGen | 60.2k | Orchestrator delegation loops |
| 10 | microsoft/agent-framework (workflows) | MS Agent Framework | 12.6k | Checkpoint corruption, handoff loops |
| 11-12 | openai/openai-agents-python (2 examples) | OpenAI Agents SDK | 28.4k | Guardrail bypass, triage misrouting |
| 13 | browser-use/browser-use | Custom (Playwright) | 107.8k | Page navigation loops, DOM desync |
| 14 | Aider-AI/aider | Custom (Git-native) | 47.9k | Edit-undo-lint cycles |
| 15 | TransformerOptimus/SuperAGI | Custom (Flask+Celery) | 17.7k | Task queue deadlock |

## 30K Trace Strategy

Combine:
1. **Hugging Face datasets**: 32.1K + 17K = 49.1K (take subset of 20K for diversity)
2. **Self-instrumented agents**: Run the 15 OSS agents with our SDK, generate 5K traces
3. **Seeded demo**: 5K parameterized demo agent runs
4. **Total**: ~30K trace samples with ground truth labels

## Trace Format Conversion

Downloaded HF traces need conversion from their native format to OTel-compatible spans:
- LangChain/LangGraph traces → OTel spans via our SDK's semantic conventions
- CrewAI traces → OTel spans via `@trace_agent` decorator
- Custom traces → normalize to SpanNode format

## LLM-Augmented Detection (Local LLM via MLX)

### What the LLM Does (Not Replace Rule-Based, Augment)

| Capability | How LLM Helps | Implementation |
|---|---|---|
| Explanation quality | LLM rates if a detector's explanation is clear and actionable | Score 1-5, flag < 3 for human review |
| False positive triage | LLM reviews anomaly context and classifies likely FP vs TP | Second-pass filter before alerting |
| Output semantic drift | LLM embedding compares output across versions | Cosine similarity on output embeddings |
| Severity calibration | LLM suggests severity adjustments based on run context | "Is this really critical or just unusual?" |
| Pattern discovery | LLM analyzes uncaught failures for new detector ideas | Runs after bulk processing on anomaly-free traces |
| Natural language query | "Show me runs where the agent got confused" | Semantic search over trace metadata and explanations |

### Local LLM Setup

```python
# Uses MLX (mlx-lm) with llama3.2 or qwen2.5 (3B params, runs on Apple Silicon laptop)
# Fallback: if MLX model server not available, skip LLM features gracefully
# All LLM calls are optional — detectors work without LLM
```

### LLM Detectors (New Anomaly Types)

| # | Detector | What it catches | Why LLM is needed |
|---|---|---|---|
| 36 | SemanticLoopDetector | Agent produces semantically identical outputs repeatedly | Rule-based is blind to meaning |
| 37 | HallucinationDetector | Agent output contains fabricated data | Requires factual verification |
| 38 | GoalDriftDetector | Agent pursues wrong sub-goal over time | Requires semantic understanding of intent |
| 39 | QualityDegradationDetector | Output quality drops vs baseline | Requires quality assessment |
| 40 | ConfusionPatternDetector | Agent exhibits confused, contradictory behavior | Requires multi-turn reasoning analysis |
