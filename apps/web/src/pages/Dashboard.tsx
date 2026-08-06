/**
 * Dashboard page — agent fleet overview with summary cards and agent cards.
 *
 * ## Purpose
 * This is the landing page of the application. It displays a high-level overview
 * of the entire agent fleet: total runs, active agents, anomaly count, and
 * average cost. Below the summary cards, each agent is rendered as a clickable
 * card showing its runs, success rate, and cost.
 *
 * ## Data flow
 * 1. On mount, `useAsync` calls `api.getFleet()` (no filters — full fleet view).
 * 2. Response is aggregated into summary metrics: totalRuns, totalAnomalies,
 *    unique agent count, and average cost.
 * 3. Each agent group is rendered as a `DashboardCard` in a responsive grid.
 *
 * ## User interactions
 * - Clicking an agent card navigates to `/fleet?agent=<agent_name>` for a
 *   filtered Fleet Health view.
 *
 * ## UI states
 * - **Loading**: 4 skeleton cards for the summary area.
 * - **Error**: `ErrorState` with retry button.
 * - **Empty**: "No fleet data yet" with instructions to instrument an agent.
 * - **Data**: summary cards + agent card grid with staggered animations.
 */

import { useNavigate } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import type { FleetGroup } from "../types/api";
import { Layout, PageHeader, PageBody, SummaryCard, ErrorState, EmptyState, SkeletonCard } from "../components/ui";

/**
 * Individual agent card in the dashboard grid.
 *
 * Displays agent name, version, workload type, run count, success rate, cost per run,
 * and an anomaly count badge (only when anomalies > 0).
 *
 * On click, navigates to the Fleet Health page filtered to this agent.
 *
 * @param group - Fleet rollup data for this agent/version/workload combination
 * @param index - Position in the grid (used for staggered animation delay)
 */
function DashboardCard({ group, index }: { group: FleetGroup; index: number }) {
  const nav = useNavigate();
  // Calculate success rate as a percentage string
  const successRate = group.total_runs > 0 ? ((group.success_count / group.total_runs) * 100).toFixed(1) : "0.0";
  // Cycling emoji icons for visual variety
  const names = ["🛰️", "🔬", "⚙️", "📊"];
  return (
    <button
      onClick={() => nav(`/fleet?agent=${encodeURIComponent(group.agent_name)}`)}
      className={`animate-fade-in-up stagger-${Math.min(index + 1, 10)} group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-lg hover:border-blue-200`}
    >
      {/* Decorative gradient circle that appears on hover */}
      <div className="absolute -right-6 -top-6 size-20 rounded-full bg-gradient-to-br from-blue-50 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      <div className="relative">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-xl bg-slate-100 text-sm">{names[index % names.length]}</span>
            <div>
              {/* Agent name: underscores → spaces, capitalized */}
              <h3 className="text-sm font-bold text-slate-800 capitalize">{group.agent_name.replace(/_/g, " ")}</h3>
              <p className="text-[11px] text-slate-400">v{group.agent_version} · {group.workload_type}</p>
            </div>
          </div>
          {/* Anomaly count badge: only rendered when anomalies exist */}
          {group.anomaly_count > 0 && (
            <span className="rounded-full bg-red-50 px-2.5 py-0.5 text-[11px] font-bold text-red-600 border border-red-100">
              {group.anomaly_count}
            </span>
          )}
        </div>
        {/* Three-column stat grid within each card */}
        <div className="mt-5 grid grid-cols-3 gap-3">
          <div className="rounded-xl bg-slate-50 p-2.5 text-center">
            <p className="text-lg font-bold tabular-nums text-slate-800">{group.total_runs}</p>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Runs</p>
          </div>
          <div className="rounded-xl bg-emerald-50 p-2.5 text-center">
            <p className="text-lg font-bold tabular-nums text-emerald-700">{successRate}%</p>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-500">Success</p>
          </div>
          <div className="rounded-xl bg-slate-50 p-2.5 text-center">
            <p className="text-lg font-bold tabular-nums text-slate-800">${group.avg_cost.toFixed(2)}</p>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Cost</p>
          </div>
        </div>
      </div>
    </button>
  );
}

/**
 * Dashboard page — main landing page showing fleet overview and agent cards.
 *
 * Aggregates fleet data into four summary stats (total runs, active agents,
 * anomalies, avg cost) and renders each agent group as a clickable card.
 */
export default function DashboardPage() {
  // Fetch full fleet data (no filters) on mount
  const { data, loading, error, refetch } = useAsync(() => api.getFleet(), []);
  const groups = data?.groups ?? [];

  // Derive summary statistics from the fleet groups
  const totalRuns = groups.reduce((s, g) => s + g.total_runs, 0);
  const totalAnomalies = groups.reduce((s, g) => s + g.anomaly_count, 0);
  const totalAgents = new Set(groups.map(g => g.agent_name)).size;
  const avgCost = groups.length > 0 ? groups.reduce((s, g) => s + g.avg_cost, 0) / groups.length : 0;

  return (
    <Layout>
      <PageHeader title="Dashboard" subtitle="Real-time fleet observability at a glance" />
      <PageBody>
        {/* Error state: full-width error card with retry */}
        {error && <ErrorState message={error} onRetry={refetch} />}

        {/* Loading state: 4 shimmer cards for the summary row */}
        {loading && (
          <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        )}

        {/* Data state: summary cards + agent card grid */}
        {!loading && !error && (
          <>
            {/* Summary cards row: Total Runs, Active Agents, Anomalies, Avg Cost */}
            <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div className="animate-fade-in-up stagger-1"><SummaryCard label="Total Runs" value={totalRuns.toLocaleString()} /></div>
              <div className="animate-fade-in-up stagger-2"><SummaryCard label="Active Agents" value={totalAgents} /></div>
              {/* Anomalies card gets accent styling when anomalies > 0 */}
              <div className="animate-fade-in-up stagger-3"><SummaryCard label="Anomalies" value={totalAnomalies} accent={totalAnomalies > 0} /></div>
              <div className="animate-fade-in-up stagger-4"><SummaryCard label="Avg Cost" value={`$${avgCost.toFixed(3)}`} /></div>
            </div>

            {/* Empty state: no fleet data */}
            {groups.length === 0 ? (
              <EmptyState title="No fleet data yet" description="Instrument an agent and generate some runs to see your fleet here." />
            ) : (
              /* Agent card grid: responsive 1→2→3 columns */
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {groups.map((g, i) => <DashboardCard key={`${g.agent_name}-${g.agent_version}-${g.workload_type}`} group={g} index={i} />)}
              </div>
            )}
          </>
        )}
      </PageBody>
    </Layout>
  );
}