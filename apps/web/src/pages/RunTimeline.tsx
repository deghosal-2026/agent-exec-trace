/** Run Timeline page: search for a run by ID and inspect its span tree.
 *
 * Shows a search input, run metadata header, anomaly list, span tree with
 * expand/collapse, and a detail panel for the selected span.
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import {
  Layout,
  PageHeader,
  PageBody,
  StatusBadge,
  CostDisplay,
  DurationDisplay,
  SpanTree,
  SpanDetail,
  AnomalyList,
  ErrorState,
  EmptyState,
} from "../components/ui";

export default function RunTimelinePage() {
  const { runId } = useParams<{ runId: string }>();
  const nav = useNavigate();
  const [inputRunId, setInputRunId] = useState(runId ?? "");
  const [searchId, setSearchId] = useState(runId ?? "");
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);

  const { data, loading, error, refetch } = useAsync(
    () => (searchId ? api.getRunTimeline(searchId) : Promise.reject(new Error("Enter a run ID"))),
    [searchId]
  );

  function handleSearch() {
    const id = inputRunId.trim();
    if (!id) return;
    setSearchId(id);
    nav(`/runs/${encodeURIComponent(id)}`, { replace: true });
  }

  const selectedSpan = data?.spans.find((s) => s.span_id === selectedSpanId) ?? null;

  return (
    <Layout>
      <PageHeader title="Run Timeline" subtitle="Inspect a single agent run" />
      <PageBody>
        <div className="mb-6 flex items-center gap-3">
          <input
            value={inputRunId}
            onChange={(e) => setInputRunId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Enter run ID..."
            className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-label="Run ID"
          />
          <button
            onClick={handleSearch}
            className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
          >
            Inspect
          </button>
        </div>

        {!searchId && (
          <EmptyState
            title="Enter a run ID to inspect"
            description="Paste a run ID above or select one from anomalies or fleet"
          />
        )}

        {error && searchId && <ErrorState message={error} onRetry={refetch} />}

        {loading && searchId && (
          <div className="space-y-3">
            <div className="h-24 animate-pulse rounded-xl bg-gray-200" />
            <div className="h-64 animate-pulse rounded-xl bg-gray-200" />
          </div>
        )}

        {data && !loading && (
          <>
            <div className="mb-6 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold text-gray-900">
                      {data.agent_name}
                    </h2>
                    <StatusBadge status={data.status} />
                    {data.loop_detected && (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                        Loop ×{data.loop_count}
                      </span>
                    )}
                  </div>
                  <p className="font-mono text-xs text-gray-500">{data.run_id}</p>
                  <p className="text-xs text-gray-500">
                    v{data.agent_version}
                  </p>
                </div>
                <div className="flex flex-wrap gap-4 text-right text-sm">
                  <div>
                    <p className="text-xs text-gray-500">Duration</p>
                    <p className="font-semibold text-gray-900">
                      <DurationDisplay ms={data.duration_ms} />
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Cost</p>
                    <p className="font-semibold text-gray-900">
                      <CostDisplay value={data.estimated_cost} />
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {data.anomalies.length > 0 && (
              <div className="mb-4">
                <h3 className="mb-2 text-sm font-semibold text-gray-700">
                  Anomalies ({data.anomalies.length})
                </h3>
                <AnomalyList anomalies={data.anomalies} />
              </div>
            )}

            <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-gray-700">
                  Span Tree
                </h3>
                {data.spans.length === 0 ? (
                  <EmptyState
                    title="No behavior spans captured"
                    description="The run completed without recording detailed behavior spans"
                  />
                ) : (
                  <SpanTree
                    spans={data.spans}
                    anomalies={data.anomalies}
                    selectedSpanId={selectedSpanId}
                    onSelectSpan={setSelectedSpanId}
                  />
                )}
              </div>
              {selectedSpan && (
                <div>
                  <SpanDetail span={selectedSpan} anomalies={data.anomalies} />
                </div>
              )}
            </div>
          </>
        )}
      </PageBody>
    </Layout>
  );
}