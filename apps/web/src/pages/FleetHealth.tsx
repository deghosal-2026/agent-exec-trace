/** Fleet Health page: tabular view of all agent/version/workload groups.
 *
 * Provides summary cards, filterable dropdowns, and a table with run counts,
 * success rates, error counts, anomalies, cost, and duration.  Rows are
 * clickable to navigate to the run timeline filtered by agent.
 */

import { useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import {
  Layout,
  PageHeader,
  PageBody,
  SummaryCard,
  ErrorState,
  EmptyState,
  SkeletonList,
} from "../components/ui";

export default function FleetHealthPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const nav = useNavigate();

  const agentFilter = searchParams.get("agent") ?? "";
  const versionFilter = searchParams.get("version") ?? "";
  const workloadFilter = searchParams.get("workload") ?? "";

  const { data, loading, error, refetch } = useAsync(
    () =>
      api.getFleet({
        agent_name: agentFilter || undefined,
        version: versionFilter || undefined,
        workload_type: workloadFilter || undefined,
      }),
    [agentFilter, versionFilter, workloadFilter]
  );

  const groups = data?.groups ?? [];

  const agents = useMemo(
    () => [...new Set(groups.map((g) => g.agent_name))],
    [groups]
  );
  const versions = useMemo(
    () => [...new Set(groups.map((g) => g.agent_version))],
    [groups]
  );
  const workloads = useMemo(
    () => [...new Set(groups.map((g) => g.workload_type))],
    [groups]
  );

  const totalRuns = groups.reduce((s, g) => s + g.total_runs, 0);
  const totalAnomalies = groups.reduce((s, g) => s + g.anomaly_count, 0);
  const avgCost =
    groups.length > 0
      ? groups.reduce((s, g) => s + g.avg_cost, 0) / groups.length
      : 0;
  const avgSuccess =
    groups.length > 0
      ? groups.reduce(
          (s, g) => s + (g.total_runs > 0 ? g.success_count / g.total_runs : 0),
          0
        ) / groups.length
      : 0;

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  }

  return (
    <Layout>
      <PageHeader
        title="Fleet Health"
        subtitle="All agents grouped by version and workload"
      />
      <PageBody>
        {error && <ErrorState message={error} onRetry={refetch} />}

        {loading && (
          <>
            <div className="mb-6 grid grid-cols-4 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="h-24 animate-pulse rounded-xl bg-gray-200"
                />
              ))}
            </div>
            <SkeletonList rows={5} />
          </>
        )}

        {!loading && !error && (
          <>
            <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <SummaryCard label="Total Runs" value={totalRuns} />
              <SummaryCard label="Anomalies" value={totalAnomalies} />
              <SummaryCard label="Avg Cost" value={`$${avgCost.toFixed(3)}`} />
              <SummaryCard
                label="Avg Success"
                value={`${(avgSuccess * 100).toFixed(1)}%`}
              />
            </div>

            <div className="mb-6 flex flex-wrap items-center gap-3">
              <select
                value={agentFilter}
                onChange={(e) => setFilter("agent", e.target.value)}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                aria-label="Filter by agent"
              >
                <option value="">All agents</option>
                {agents.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
              <select
                value={versionFilter}
                onChange={(e) => setFilter("version", e.target.value)}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                aria-label="Filter by version"
              >
                <option value="">All versions</option>
                {versions.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
              <select
                value={workloadFilter}
                onChange={(e) => setFilter("workload", e.target.value)}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                aria-label="Filter by workload"
              >
                <option value="">All workloads</option>
                {workloads.map((w) => (
                  <option key={w} value={w}>
                    {w}
                  </option>
                ))}
              </select>
              {(agentFilter || versionFilter || workloadFilter) && (
                <button
                  onClick={() => setSearchParams({}, { replace: true })}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Clear filters
                </button>
              )}
            </div>

            {groups.length === 0 ? (
              <EmptyState
                title={
                  agentFilter || versionFilter || workloadFilter
                    ? "No results for current filters"
                    : "No fleet data yet"
                }
                description={
                  agentFilter || versionFilter || workloadFilter
                    ? "Try broadening your filter"
                    : "Instrument an agent and generate some runs first"
                }
              />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50 text-xs font-medium text-gray-500">
                      <th className="px-4 py-3">Agent</th>
                      <th className="px-4 py-3">Version</th>
                      <th className="px-4 py-3">Workload</th>
                      <th className="px-4 py-3 text-right">Runs</th>
                      <th className="px-4 py-3 text-right">Success</th>
                      <th className="px-4 py-3 text-right">Errors</th>
                      <th className="px-4 py-3 text-right">Anomalies</th>
                      <th className="px-4 py-3 text-right">Avg Cost</th>
                      <th className="px-4 py-3 text-right">Avg Duration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {groups.map((g) => {
                      const successRate =
                        g.total_runs > 0
                          ? ((g.success_count / g.total_runs) * 100).toFixed(1)
                          : "0.0";
                      return (
                        <tr
                          key={`${g.agent_name}-${g.agent_version}-${g.workload_type}`}
                          className="hover:bg-gray-50 cursor-pointer"
                          onClick={() =>
                            nav(
                              `/runs?agent=${encodeURIComponent(g.agent_name)}`
                            )
                          }
                        >
                          <td className="px-4 py-3 font-medium text-gray-900">
                            {g.agent_name}
                          </td>
                          <td className="px-4 py-3 text-gray-600">{g.agent_version}</td>
                          <td className="px-4 py-3 text-gray-600">{g.workload_type}</td>
                          <td className="px-4 py-3 text-right text-gray-900">
                            {g.total_runs}
                          </td>
                          <td className="px-4 py-3 text-right text-emerald-600">
                            {successRate}%
                          </td>
                          <td className="px-4 py-3 text-right text-red-600">
                            {g.error_count}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {g.anomaly_count > 0 ? (
                              <span className="font-medium text-amber-600">
                                {g.anomaly_count}
                              </span>
                            ) : (
                              <span className="text-gray-400">0</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right text-gray-900">
                            ${g.avg_cost.toFixed(3)}
                          </td>
                          <td className="px-4 py-3 text-right text-gray-600">
                            {g.avg_duration_ms}ms
                          </td>
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