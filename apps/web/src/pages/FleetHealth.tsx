/** Fleet Health — tabular view with filter chips and professional data table. */

import { useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import { Layout, PageHeader, PageBody, SummaryCard, ErrorState, EmptyState, SkeletonList, ClearButton } from "../components/ui";

export default function FleetHealthPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const nav = useNavigate();
  const agentFilter = searchParams.get("agent") ?? "";
  const versionFilter = searchParams.get("version") ?? "";
  const workloadFilter = searchParams.get("workload") ?? "";

  const { data, loading, error, refetch } = useAsync(
    () => api.getFleet({ agent_name: agentFilter || undefined, version: versionFilter || undefined, workload_type: workloadFilter || undefined }),
    [agentFilter, versionFilter, workloadFilter]
  );

  const groups = data?.groups ?? [];
  const agents = useMemo(() => [...new Set(groups.map(g => g.agent_name))], [groups]);
  const versions = useMemo(() => [...new Set(groups.map(g => g.agent_version))], [groups]);
  const workloads = useMemo(() => [...new Set(groups.map(g => g.workload_type))], [groups]);

  const totalRuns = groups.reduce((s, g) => s + g.total_runs, 0);
  const totalAnomalies = groups.reduce((s, g) => s + g.anomaly_count, 0);
  const avgCost = groups.length > 0 ? groups.reduce((s, g) => s + g.avg_cost, 0) / groups.length : 0;
  const avgSuccess = groups.length > 0 ? groups.reduce((s, g) => s + (g.total_runs > 0 ? g.success_count / g.total_runs : 0), 0) / groups.length : 0;

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value); else next.delete(key);
    setSearchParams(next, { replace: true });
  }

  const hasFilters = !!(agentFilter || versionFilter || workloadFilter);

  return (
    <Layout>
      <PageHeader title="Fleet Health" subtitle="All agents grouped by version, workload, and status" />
      <PageBody>
        {error && <ErrorState message={error} onRetry={refetch} />}
        {loading && (
          <>
            <div className="mb-6 grid grid-cols-4 gap-4">
              {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-28 shimmer rounded-xl" />)}
            </div>
            <SkeletonList rows={5} />
          </>
        )}
        {!loading && !error && (
          <>
            <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4 animate-fade-in-up">
              <SummaryCard label="Total Runs" value={totalRuns.toLocaleString()} />
              <SummaryCard label="Anomalies" value={totalAnomalies} />
              <SummaryCard label="Avg Cost" value={`$${avgCost.toFixed(3)}`} />
              <SummaryCard label="Avg Success" value={`${(avgSuccess * 100).toFixed(1)}%`} />
            </div>

            <div className="mb-6 flex flex-wrap items-center gap-2">
              <select value={agentFilter} onChange={e => setFilter("agent", e.target.value)}
                className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition-all hover:border-slate-300 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                aria-label="Filter by agent">
                <option value="">All agents</option>
                {agents.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
              <select value={versionFilter} onChange={e => setFilter("version", e.target.value)}
                className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition-all hover:border-slate-300 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                aria-label="Filter by version">
                <option value="">All versions</option>
                {versions.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
              <select value={workloadFilter} onChange={e => setFilter("workload", e.target.value)}
                className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition-all hover:border-slate-300 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                aria-label="Filter by workload">
                <option value="">All workloads</option>
                {workloads.map(w => <option key={w} value={w}>{w}</option>)}
              </select>
              {hasFilters && <ClearButton onClick={() => setSearchParams({}, { replace: true })} />}
            </div>

            {groups.length === 0 ? (
              <EmptyState
                title={hasFilters ? "No results for current filters" : "No fleet data yet"}
                description={hasFilters ? "Try broadening your filter criteria" : "Instrument an agent and generate some runs to see data here."}
              />
            ) : (
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm animate-fade-in">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50/50 text-xs font-bold uppercase tracking-wider text-slate-500">
                      <th className="px-5 py-3.5">Agent</th>
                      <th className="px-5 py-3.5">Version</th>
                      <th className="px-5 py-3.5">Workload</th>
                      <th className="px-5 py-3.5 text-right">Runs</th>
                      <th className="px-5 py-3.5 text-right">Success</th>
                      <th className="px-5 py-3.5 text-right">Errors</th>
                      <th className="px-5 py-3.5 text-right">Anomalies</th>
                      <th className="px-5 py-3.5 text-right">Cost</th>
                      <th className="px-5 py-3.5 text-right">Duration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {groups.map((g, i) => {
                      const sr = g.total_runs > 0 ? ((g.success_count / g.total_runs) * 100).toFixed(1) : "0.0";
                      return (
                        <tr key={`${g.agent_name}-${g.agent_version}-${g.workload_type}`}
                          onClick={() => nav(`/runs?agent=${encodeURIComponent(g.agent_name)}`)}
                          className={`animate-fade-in-up stagger-${Math.min(i + 1, 10)} cursor-pointer transition-colors hover:bg-blue-50/30`}>
                          <td className="px-5 py-3.5 font-semibold text-slate-800 capitalize">{g.agent_name.replace(/_/g, " ")}</td>
                          <td className="px-5 py-3.5"><span className="rounded-lg bg-slate-100 px-2 py-0.5 text-xs font-mono font-semibold text-slate-600">{g.agent_version}</span></td>
                          <td className="px-5 py-3.5 text-slate-500 text-xs">{g.workload_type}</td>
                          <td className="px-5 py-3.5 text-right font-semibold tabular-nums text-slate-800">{g.total_runs}</td>
                          <td className="px-5 py-3.5 text-right font-semibold tabular-nums text-emerald-600">{sr}%</td>
                          <td className="px-5 py-3.5 text-right font-semibold tabular-nums text-red-500">{g.error_count}</td>
                          <td className="px-5 py-3.5 text-right">
                            {g.anomaly_count > 0 ? <span className="font-bold tabular-nums text-amber-600">{g.anomaly_count}</span> : <span className="text-slate-300">0</span>}
                          </td>
                          <td className="px-5 py-3.5 text-right font-semibold tabular-nums text-slate-700">${g.avg_cost.toFixed(3)}</td>
                          <td className="px-5 py-3.5 text-right tabular-nums text-slate-500 text-xs">{g.avg_duration_ms}ms</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </PageBody>
    </Layout>
  );
}