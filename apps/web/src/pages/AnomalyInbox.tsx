/**
 * Anomaly Inbox page — prioritized triage list for operator review.
 *
 * ## Purpose
 * Displays a filterable, paginated list of detected anomalies across all agents.
 * Operators can triage by severity (critical/warning/info), anomaly type
 * (loop, retry_storm, cost_spike, etc.), and agent name.
 *
 * ## Data flow
 * 1. User sets filter state (severity, type, agent).
 * 2. `useAsync` hook triggers `api.getAnomalies()` when filters change.
 * 3. API returns normalized anomaly items.
 * 4. Component renders one of three states: loading skeleton, error, or anomaly list.
 *
 * ## User interactions
 * - Filter dropdowns for severity and type.
 * - Free-text input for agent name filtering.
 * - "Clear all" button resets all filters to defaults.
 * - Clicking an anomaly card navigates to the associated run's timeline page.
 *
 * ## UI states
 * - **Loading**: 8 skeleton rows via `SkeletonList`.
 * - **Error**: `ErrorState` with retry button.
 * - **Empty (no filters)**: "No anomalies detected" message.
 * - **Empty (with filters)**: "No anomalies match these filters" with suggestion.
 * - **Data**: stacked card list with staggered fade-in animation.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import { Layout, PageHeader, PageBody, AnomalyBadge, SeverityDot, TimeDisplay, ErrorState, EmptyState, SkeletonList, ClearButton } from "../components/ui";

/** Severity filter options for the dropdown. */
const SEVERITY_OPTIONS = [
  { value: "critical", label: "Critical" },
  { value: "warning", label: "Warning" },
  { value: "info", label: "Info" },
];

/** Anomaly type filter options. */
const TYPE_OPTIONS = [
  { value: "loop", label: "Loop" },
  { value: "retry_storm", label: "Retry Storm" },
  { value: "cost_spike", label: "Cost Spike" },
  { value: "tool_error_rate", label: "Tool Errors" },
  { value: "pattern_loop", label: "Pattern Loop" },
  { value: "output_drift", label: "Output Drift" },
];

/**
 * Anomaly Inbox page component.
 *
 * Renders a filter bar + paginated list of anomaly cards. Each card shows:
 * - Severity dot (colored circle)
 * - Anomaly type badge (e.g. "Loop", "Retry Storm")
 * - Agent name (capitalized, underscores → spaces)
 * - Detection timestamp
 * - Explanation text (clamped to 2 lines)
 * - Run ID in monospace
 *
 * Clicking a card navigates to `/runs/:runId` for deep inspection.
 */
export default function AnomalyInboxPage() {
  const nav = useNavigate();
  const [severity, setSeverity] = useState("");
  const [type, setType] = useState("");
  const [agent, setAgent] = useState("");

  // Fetch anomalies whenever filters change; pass undefined for empty strings
  const { data, loading, error, refetch } = useAsync(
    () => api.getAnomalies({ severity: severity || undefined, anomaly_type: type || undefined, agent_name: agent || undefined, limit: 50 }),
    [severity, type, agent]
  );

  const items = data?.items ?? [];
  const hasFilters = !!(severity || type || agent);

  return (
    <Layout>
      <PageHeader title="Anomaly Inbox" subtitle="Prioritized anomalies for operator triage" />
      <PageBody>
        {/* Filter bar: severity dropdown, type dropdown, agent text input */}
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <select value={severity} onChange={e => setSeverity(e.target.value)}
            className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition-all hover:border-slate-300 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500/20"
            aria-label="Filter by severity">
            <option value="">All severities</option>
            {SEVERITY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select value={type} onChange={e => setType(e.target.value)}
            className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition-all hover:border-slate-300 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
            aria-label="Filter by type">
            <option value="">All types</option>
            {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <input value={agent} onChange={e => setAgent(e.target.value)}
            placeholder="Agent name..."
            className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm text-slate-700 shadow-sm placeholder:text-slate-400 transition-all hover:border-slate-300 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 w-44"
            aria-label="Filter by agent" />
          {/* Clear button: only visible when at least one filter is active */}
          {hasFilters && <ClearButton onClick={() => { setSeverity(""); setType(""); setAgent(""); }} />}
        </div>

        {/* Error state: shown when the API call fails */}
        {error && <ErrorState message={error} onRetry={refetch} />}

        {/* Loading state: shimmer skeleton rows */}
        {loading && <SkeletonList rows={8} />}

        {/* Empty state: shown after loading completes with zero results */}
        {!loading && !error && items.length === 0 && (
          <EmptyState
            title={hasFilters ? "No anomalies match these filters" : "No anomalies detected"}
            description={hasFilters ? "Try broadening your type, severity, or agent filter." : "No anomalies detected in the current window — fleet is healthy."}
          />
        )}

        {/* Data state: anomaly card list with staggered animation */}
        {!loading && !error && items.length > 0 && (
          <div className="space-y-2.5">
            {items.map((item, i) => (
              <button key={item.id}
                onClick={() => nav(`/runs/${encodeURIComponent(item.run_id)}`)}
                className={`animate-fade-in-up stagger-${Math.min(i + 1, 10)} group flex w-full items-start gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md`}>
                <SeverityDot severity={item.severity} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <AnomalyBadge anomaly_type={item.anomaly_type} severity={item.severity} />
                    {/* Capitalize and replace underscores for display */}
                    <span className="truncate text-sm font-bold text-slate-800 capitalize">{item.agent_name.replace(/_/g, " ")}</span>
                    <TimeDisplay iso={item.detected_at} />
                  </div>
                  {/* Line-clamp to 2 lines to keep inbox items compact */}
                  <p className="text-sm text-slate-600 line-clamp-2">{item.explanation}</p>
                  <p className="mt-1 font-mono text-[11px] text-slate-300">ID: {item.run_id}</p>
                </div>
                {/* Arrow indicator: subtle on rest, blue on hover */}
                <span className="mt-1 shrink-0 rounded-lg bg-slate-100 px-2 py-1 text-xs font-bold text-slate-400 transition-colors group-hover:bg-blue-100 group-hover:text-blue-600">→</span>
              </button>
            ))}
          </div>
        )}
      </PageBody>
    </Layout>
  );
}