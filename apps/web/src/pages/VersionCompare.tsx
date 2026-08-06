/** Version Compare — side-by-side cohort analysis with delta badges. */

import { useState } from "react";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import { Layout, PageHeader, PageBody, SummaryCard, DeltaBadge, ErrorState, EmptyState } from "../components/ui";

export default function VersionComparePage() {
  const [agentName, setAgentName] = useState("");
  const [versionA, setVersionA] = useState("");
  const [versionB, setVersionB] = useState("");
  const canCompare = versionA.trim() !== "" && versionB.trim() !== "";

  const { data, loading, error, refetch } = useAsync(
    () => { if (!canCompare) return Promise.reject(new Error("Select two versions")); return api.getCompare({ agent_name: agentName || undefined, version_a: versionA.trim(), version_b: versionB.trim() }); },
    [agentName, versionA, versionB]
  );

  return (
    <Layout>
      <PageHeader title="Version Compare" subtitle="Side-by-side delta analysis between two agent versions" />
      <PageBody>
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

        {!canCompare && <EmptyState title="Select two versions to compare" description="Enter version labels above to see side-by-side deltas." />}
        {error && canCompare && <ErrorState message={error} onRetry={refetch} />}
        {loading && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="h-40 shimmer rounded-xl" />
              <div className="h-40 shimmer rounded-xl" />
            </div>
            <div className="h-24 shimmer rounded-xl" />
          </div>
        )}

        {data && !loading && (
          <>
            {data.warning && (
              <div className="mb-6 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 animate-fade-in">
                <span>⚠️</span> {data.note ?? "Cohort data may be sparse; interpret deltas with caution."}
              </div>
            )}

            <div className="mb-6 grid gap-5 sm:grid-cols-2 animate-fade-in-up">
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

            <div className="mb-6 grid gap-4 sm:grid-cols-3 animate-fade-in-up">
              <SummaryCard label="Cost Delta" value={<DeltaBadge value={data.deltas.avg_cost_usd ?? 0} suffix="$" />}
                accent={Math.abs(data.deltas.avg_cost_usd ?? 0) > 0} />
              <SummaryCard label="Retry Rate Delta" value={<DeltaBadge value={(data.deltas.retry_rate ?? 0) * 100} />}
                accent={(data.deltas.retry_rate ?? 0) > 0} />
              <SummaryCard label="Success Rate Delta" value={<DeltaBadge value={(data.deltas.success_rate ?? 0) * 100} />}
                accent={Math.abs(data.deltas.success_rate ?? 0) > 0.05} />
            </div>

            {data.tool_deltas.length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm animate-fade-in-up">
                <h3 className="mb-4 text-sm font-bold text-slate-700">Tool Usage Comparison</h3>
                <div className="grid gap-4 sm:grid-cols-2">
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