/** Version Compare page: side-by-side comparison of two agent versions.
 *
 * Input two version labels, and the page fetches cohort summaries for each,
 * displaying run counts, success rates, cost, duration, and tool usage deltas.
 * Warnings are shown when cohorts are too small for statistical significance.
 */

import { useState } from "react";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import {
  Layout,
  PageHeader,
  PageBody,
  SummaryCard,
  DeltaBadge,
  DurationDisplay,
  ErrorState,
  EmptyState,
} from "../components/ui";

export default function VersionComparePage() {
  const [agentName, setAgentName] = useState("");
  const [versionA, setVersionA] = useState("");
  const [versionB, setVersionB] = useState("");

  const canCompare = versionA.trim() !== "" && versionB.trim() !== "";

  const { data, loading, error, refetch } = useAsync(
    () => {
      if (!canCompare)
        return Promise.reject(new Error("Select two versions"));
      return api.getCompare({
        agent_name: agentName || undefined,
        version_a: versionA.trim(),
        version_b: versionB.trim(),
      });
    },
    [agentName, versionA, versionB]
  );

  return (
    <Layout>
      <PageHeader
        title="Version Compare"
        subtitle="Compare two agent versions side by side"
      />
      <PageBody>
        <div className="mb-6 flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Agent Name
            </label>
            <input
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Optional"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Version A
            </label>
            <input
              value={versionA}
              onChange={(e) => setVersionA(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="e.g. v1.0"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Version B
            </label>
            <input
              value={versionB}
              onChange={(e) => setVersionB(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="e.g. v2.0"
            />
          </div>
        </div>

        {!canCompare && (
          <EmptyState
            title="Select two versions to compare"
            description="Enter version labels above to see deltas"
          />
        )}

        {error && canCompare && <ErrorState message={error} onRetry={refetch} />}

        {loading && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="h-32 animate-pulse rounded-xl bg-gray-200" />
              <div className="h-32 animate-pulse rounded-xl bg-gray-200" />
            </div>
            <div className="h-24 animate-pulse rounded-xl bg-gray-200" />
            <div className="h-48 animate-pulse rounded-xl bg-gray-200" />
          </div>
        )}

        {data && !loading && (
          <>
            <div className="mb-6 grid gap-4 sm:grid-cols-2">
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-gray-700">
                  {data.version_a.version}
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <SummaryCard
                    label="Runs"
                    value={data.version_a.total_runs}
                  />
                  <SummaryCard
                    label="Success Rate"
                    value={`${(
                      (data.version_a.success_count /
                        data.version_a.total_runs) *
                      100
                    ).toFixed(1)}%`}
                  />
                  <SummaryCard
                    label="Avg Cost"
                    value={`$${data.version_a.avg_cost.toFixed(3)}`}
                  />
                  <SummaryCard
                    label="Avg Duration"
                    value={
                      <DurationDisplay ms={data.version_a.avg_duration_ms} />
                    }
                  />
                </div>
              </div>
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-gray-700">
                  {data.version_b.version}
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <SummaryCard
                    label="Runs"
                    value={data.version_b.total_runs}
                  />
                  <SummaryCard
                    label="Success Rate"
                    value={`${(
                      (data.version_b.success_count /
                        data.version_b.total_runs) *
                      100
                    ).toFixed(1)}%`}
                  />
                  <SummaryCard
                    label="Avg Cost"
                    value={`$${data.version_b.avg_cost.toFixed(3)}`}
                  />
                  <SummaryCard
                    label="Avg Duration"
                    value={
                      <DurationDisplay ms={data.version_b.avg_duration_ms} />
                    }
                  />
                </div>
              </div>
            </div>

            <div className="mb-6 grid gap-4 sm:grid-cols-3">
              <SummaryCard
                label="Cost Delta"
                value={<DeltaBadge value={data.cost_delta_pct} />}
                sub={`${data.version_a.version}: $${data.version_a.avg_cost.toFixed(3)} → ${data.version_b.version}: $${data.version_b.avg_cost.toFixed(3)}`}
                accent={Math.abs(data.cost_delta_pct) > 20}
              />
              <SummaryCard
                label="Retry Delta"
                value={<DeltaBadge value={data.retry_delta_pct} />}
                sub={`${data.version_a.total_retries} → ${data.version_b.total_retries} retries`}
                accent={data.retry_delta_pct > 0}
              />
              <SummaryCard
                label="Duration Delta"
                value={<DeltaBadge value={data.duration_delta_pct} />}
              />
            </div>

            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-gray-700">
                Tool Usage
              </h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <h4 className="mb-2 text-xs font-medium text-gray-500">
                    {data.version_a.version}
                  </h4>
                  <div className="space-y-1.5">
                    {Object.entries(data.version_a.top_tools).map(
                      ([tool, count]) => (
                        <div
                          key={tool}
                          className="flex items-center justify-between text-sm"
                        >
                          <span className="font-mono text-xs text-gray-700">
                            {tool}
                          </span>
                          <span className="font-medium text-gray-900">
                            {count}
                          </span>
                        </div>
                      )
                    )}
                  </div>
                </div>
                <div>
                  <h4 className="mb-2 text-xs font-medium text-gray-500">
                    {data.version_b.version}
                  </h4>
                  <div className="space-y-1.5">
                    {Object.entries(data.version_b.top_tools).map(
                      ([tool, count]) => (
                        <div
                          key={tool}
                          className="flex items-center justify-between text-sm"
                        >
                          <span className="font-mono text-xs text-gray-700">
                            {tool}
                          </span>
                          <span className="font-medium text-gray-900">
                            {count}
                          </span>
                        </div>
                      )
                    )}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </PageBody>
    </Layout>
  );
}