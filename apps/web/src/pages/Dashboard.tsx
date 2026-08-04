/** Dashboard page: fleet overview with summary cards and per-agent cards.
 *
 * Displays aggregate fleet metrics (total runs, agents, anomalies, avg cost)
 * and a grid of clickable agent cards that navigate to the fleet health view
 * filtered by that agent.
 */

import { useNavigate } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import type { FleetGroup } from "../types/api";
import {
  Layout,
  PageHeader,
  PageBody,
  SummaryCard,
  ErrorState,
  EmptyState,
} from "../components/ui";

/** Clickable card showing a single agent group's run count, success rate, and cost. */
function DashboardCard({ group }: { group: FleetGroup }) {
  const nav = useNavigate();
  const successRate =
    group.total_runs > 0
      ? ((group.success_count / group.total_runs) * 100).toFixed(1)
      : "0.0";
  return (
    <button
      onClick={() =>
        nav(`/fleet?agent=${encodeURIComponent(group.agent_name)}`)
      }
      className="rounded-xl border border-gray-200 bg-white p-5 text-left shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">
            {group.agent_name}
          </h3>
          <p className="text-xs text-gray-500">
            v{group.agent_version} · {group.workload_type}
          </p>
        </div>
        {group.anomaly_count > 0 && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
            {group.anomaly_count}
          </span>
        )}
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3 text-center text-xs">
        <div>
          <p className="font-semibold text-gray-900">{group.total_runs}</p>
          <p className="text-gray-500">runs</p>
        </div>
        <div>
          <p className="font-semibold text-gray-900">{successRate}%</p>
          <p className="text-gray-500">success</p>
        </div>
        <div>
          <p className="font-semibold text-gray-900">${group.avg_cost.toFixed(3)}</p>
          <p className="text-gray-500">avg cost</p>
        </div>
      </div>
    </button>
  );
}

export default function DashboardPage() {
  const { data, loading, error, refetch } = useAsync(() => api.getFleet(), []);
  const groups = data?.groups ?? [];

  const totalRuns = groups.reduce((s, g) => s + g.total_runs, 0);
  const totalAnomalies = groups.reduce((s, g) => s + g.anomaly_count, 0);
  const totalAgents = new Set(groups.map((g) => g.agent_name)).size;
  const avgCost =
    groups.length > 0
      ? groups.reduce((s, g) => s + g.avg_cost, 0) / groups.length
      : 0;

  return (
    <Layout>
      <PageHeader title="Dashboard" subtitle="Agent fleet at a glance" />
      <PageBody>
        {error && <ErrorState message={error} onRetry={refetch} />}
        {loading && (
          <div className="mb-6 grid grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-24 animate-pulse rounded-xl bg-gray-200"
              />
            ))}
          </div>
        )}
        {!loading && !error && (
          <>
            <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <SummaryCard label="Total Runs" value={totalRuns} />
              <SummaryCard label="Active Agents" value={totalAgents} />
              <SummaryCard
                label="Anomalies"
                value={totalAnomalies}
                accent={totalAnomalies > 0}
              />
              <SummaryCard label="Avg Cost" value={`$${avgCost.toFixed(3)}`} />
            </div>
            {groups.length === 0 ? (
              <EmptyState
                title="No fleet data yet"
                description="Instrument an agent and generate some runs first"
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {groups.map((g) => (
                  <DashboardCard key={`${g.agent_name}-${g.agent_version}-${g.workload_type}`} group={g} />
                ))}
              </div>
            )}
          </>
        )}
      </PageBody>
    </Layout>
  );
}