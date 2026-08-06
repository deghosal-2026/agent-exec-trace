/**
 * Version Compare page — side-by-side cohort analysis with delta badges.
 *
 * ## Purpose
 * Allows operators to compare two version cohorts of an agent to understand
 * the impact of version changes. Shows side-by-side cards for each version's
 * run counts and costs, plus delta badges for cost, retry rate, and success rate
 * changes. Also includes a tool usage comparison table when per-tool deltas exist.
 *
 * ## Data flow
 * 1. User enters two version labels (required) and optionally an agent name.
 * 2. When both versions are non-empty (`canCompare`), `useAsync` triggers
 *    `api.getCompare()`.
 * 3. Response includes left/right cohort data, global deltas, and per-tool deltas.
 * 4. Components render cohort cards, delta summary cards, and tool comparison grid.
 *
 * ## User interactions
 * - Agent name input (optional, filters to a specific agent).
 * - Two version inputs (required) with a "vs" divider.
 * - Viewing delta badges and tool usage breakdowns.
 *
 * ## UI states
 * - **Pre-search**: `EmptyState` prompt to select two versions.
 * - **Error (canCompare)**: `ErrorState` with retry.
 * - **Loading**: skeleton cards for cohort panels and delta cards.
 * - **Data**: cohort cards, delta badges, warning banner (if sparse data), tool comparison.
 */

import { useState } from "react";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import { Layout, PageHeader, PageBody, SummaryCard, DeltaBadge, ErrorState, EmptyState } from "../components/ui";

/**
 * Version Compare page component.
 *
 * Three inputs across a form card:
 * 1. Agent name (optional) — constrains comparison to one agent.
 * 2. Version A and Version B — both required for comparison to proceed.
 *
 * When data loads, the page renders:
 * - A warning banner when the API signals sparse data.
 * - Two cohort cards showing version labels with run counts and cost.
 * - Three delta cards: cost delta ($), retry rate delta (%), success rate delta (%).
 * - Tool usage comparison table when per-tool deltas are available.
 */
export default function VersionComparePage() {
  const [agentName, setAgentName] = useState("");
  const [versionA, setVersionA] = useState("");
  const [versionB, setVersionB] = useState("");

  // Comparison is only valid when both version inputs are non-empty
  const canCompare = versionA.trim() !== "" && versionB.trim() !== "";

  // Fetch comparison data; reject with a message when preconditions aren't met
  const { data, loading, error, refetch } = useAsync(
    () => { if (!canCompare) return Promise.reject(new Error("Select two versions")); return api.getCompare({ agent_name: agentName || undefined, version_a: versionA.trim(), version_b: versionB.trim() }); },
    [agentName, versionA, versionB]
  );

  return (
    <Layout>
      <PageHeader title="Version Compare" subtitle="Side-by-side delta analysis between two agent versions" />
      <PageBody>
        {/* Input form card: agent (optional) + two version inputs with "vs" divider */}
        <div className="mb-8 flex flex-wrap items-end gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div>
            <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-wider text-slate-400">Agent</label>
            <input value={agentName} onChange={e => setAgentName(e.target.value)}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm font-medium text-slate-800 placeholder:text-slate-400 transition-all focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              placeholder="Optional" />
          </div>
          <div className="flex items-center gap-2">
            <div>
              <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-wider text-slate-400">Version A</label>
              <input value={versionA} onChange={e => setVersionA(e.target.value)}
                className="rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm font-medium text-slate-800 placeholder:text-slate-400 transition-all focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 w-36"
                placeholder="v1.0" />
            </div>
            <span className="mt-5 text-slate-300 text-lg font-bold">vs</span>
            <div>
              <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-wider text-slate-400">Version B</label>
              <input value={versionB} onChange={e => setVersionB(e.target.value)}
                className="rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm font-medium text-slate-800 placeholder:text-slate-400 transition-all focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 w-36"
                placeholder="v2.0" />
            </div>
          </div>
        </div>

        {/* Pre-search state: prompt the user to enter versions */}
        {!canCompare && <EmptyState title="Select two versions to compare" description="Enter version labels above to see side-by-side deltas." />}

        {/* Error state: only shown when canCompare (avoids showing error for "Select two versions" rejection) */}
        {error && canCompare && <ErrorState message={error} onRetry={refetch} />}

        {/* Loading state: skeleton cards for the two-column layout and delta row */}
        {loading && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="h-40 shimmer rounded-xl" />
              <div className="h-40 shimmer rounded-xl" />
            </div>
            <div className="h-24 shimmer rounded-xl" />
          </div>
        )}

        {/* Data state: cohort cards + delta badges + tool comparison */}
        {data && !loading && (
          <>
            {/* Warning banner: shown when the API indicates sparse/limited data */}
            {data.warning && (
              <div className="mb-6 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 animate-fade-in">
                <span>⚠️</span> {data.note ?? "Cohort data may be sparse; interpret deltas with caution."}
              </div>
            )}

            {/* Two-column cohort summary: Version A (left) vs Version B (right) */}
            <div className="mb-6 grid gap-5 sm:grid-cols-2 animate-fade-in-up">
              {/* Left cohort (Version A) */}
              <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center gap-2">
                  <span className="inline-flex size-7 items-center justify-center rounded-lg bg-blue-100 text-xs font-bold text-blue-700">A</span>
                  <h3 className="text-sm font-bold text-slate-700">Version {data.left.version}</h3>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <SummaryCard label="Runs" value={data.left.run_count} />
                  <SummaryCard label="Avg Cost" value={`$${(data.deltas.avg_cost_usd ?? 0).toFixed(3)}`} />
                </div>
              </div>
              {/* Right cohort (Version B) */}
              <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center gap-2">
                  <span className="inline-flex size-7 items-center justify-center rounded-lg bg-indigo-100 text-xs font-bold text-indigo-700">B</span>
                  <h3 className="text-sm font-bold text-slate-700">Version {data.right.version}</h3>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <SummaryCard label="Runs" value={data.right.run_count} />
                  <SummaryCard label="Avg Cost" value={`$${(data.deltas.avg_cost_usd ?? 0).toFixed(3)}`} />
                </div>
              </div>
            </div>

            {/* Delta summary: Cost, Retry Rate, Success Rate with colored badges */}
            <div className="mb-6 grid gap-4 sm:grid-cols-3 animate-fade-in-up">
              {/* Cost delta: uses "$" suffix, accent when non-zero */}
              <SummaryCard label="Cost Delta" value={<DeltaBadge value={data.deltas.avg_cost_usd ?? 0} suffix="$" />}
                accent={Math.abs(data.deltas.avg_cost_usd ?? 0) > 0} />
              {/* Retry rate delta: multiply by 100 for percentage display */}
              <SummaryCard label="Retry Rate Delta" value={<DeltaBadge value={(data.deltas.retry_rate ?? 0) * 100} />}
                accent={(data.deltas.retry_rate ?? 0) > 0} />
              {/* Success rate delta: accent when absolute change > 5% */}
              <SummaryCard label="Success Rate Delta" value={<DeltaBadge value={(data.deltas.success_rate ?? 0) * 100} />}
                accent={Math.abs(data.deltas.success_rate ?? 0) > 0.05} />
            </div>

            {/* Tool usage comparison: only rendered when per-tool deltas exist */}
            {data.tool_deltas.length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm animate-fade-in-up">
                <h3 className="mb-4 text-sm font-bold text-slate-700">Tool Usage Comparison</h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  {/* Left side: tool counts for version A */}
                  <div className="rounded-xl bg-slate-50 p-4">
                    <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">{data.left.version}</h4>
                    <div className="space-y-2">
                      {data.tool_deltas.map(td => (
                        <div key={td.tool_name} className="flex items-center justify-between">
                          <span className="font-mono text-xs text-slate-600">{td.tool_name}</span>
                          <span className="text-xs font-bold tabular-nums text-slate-800">{td.left_count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  {/* Right side: tool counts for version B */}
                  <div className="rounded-xl bg-slate-50 p-4">
                    <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">{data.right.version}</h4>
                    <div className="space-y-2">
                      {data.tool_deltas.map(td => (
                        <div key={td.tool_name} className="flex items-center justify-between">
                          <span className="font-mono text-xs text-slate-600">{td.tool_name}</span>
                          <span className="text-xs font-bold tabular-nums text-slate-800">{td.right_count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </PageBody>
    </Layout>
  );
}