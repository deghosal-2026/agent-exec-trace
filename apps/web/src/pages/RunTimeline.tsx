/** Run Timeline — inspect individual agent runs with span tree visualization. */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import { Layout, PageHeader, PageBody, StatusBadge, CostDisplay, DurationDisplay, SpanTree, SpanDetail, AnomalyList, ErrorState, EmptyState, PrimaryButton, TextInput } from "../components/ui";

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

  const selectedSpan = data?.spans.find(s => s.span_id === selectedSpanId) ?? null;

  return (
    <Layout>
      <PageHeader title="Run Timeline" subtitle="Deep-dive into a single agent execution trace" />
      <PageBody>
        <div className="mb-6 flex items-center gap-3">
          <TextInput value={inputRunId} onChange={setInputRunId} onKeyDown={e => e.key === "Enter" && handleSearch()}
            placeholder="Paste a run ID..." ariaLabel="Run ID" className="max-w-xl flex-1" />
          <PrimaryButton onClick={handleSearch}>Inspect</PrimaryButton>
        </div>

        {!searchId && <EmptyState title="Enter a run ID to inspect" description="Paste a run ID above or navigate from anomalies, fleet, or dashboard." />}
        {error && searchId && <ErrorState message={error} onRetry={refetch} />}
        {loading && searchId && (
          <div className="space-y-4">
            <div className="h-28 shimmer rounded-xl" />
            <div className="h-64 shimmer rounded-xl" />
          </div>
        )}

        {data && !loading && (
          <>
            <div className="mb-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm animate-fade-in-up">
              <div className="border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white px-6 py-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-bold text-slate-800 capitalize">{data.agent_name.replace(/_/g, " ")}</h2>
                      <StatusBadge status={data.status} />
                      {data.loop_detected && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-bold text-amber-700 border border-amber-200">
                          ⟳ Loop ×{data.loop_count}
                        </span>
                      )}
                    </div>
                    <p className="font-mono text-xs text-slate-400">ID: {data.run_id}</p>
                    <p className="text-xs text-slate-400">Version {data.agent_version}</p>
                  </div>
                  <div className="flex gap-6 text-right">
                    <div className="rounded-xl bg-slate-50 px-4 py-2.5">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Duration</p>
                      <p className="mt-0.5 text-sm font-bold tabular-nums text-slate-800"><DurationDisplay ms={data.duration_ms} /></p>
                    </div>
                    <div className="rounded-xl bg-slate-50 px-4 py-2.5">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Cost</p>
                      <p className="mt-0.5 text-sm font-bold tabular-nums text-slate-800"><CostDisplay value={data.estimated_cost} /></p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {data.anomalies.length > 0 && (
              <div className="mb-6 animate-fade-in-up">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-700">
                  <span className="flex size-5 items-center justify-center rounded-md bg-red-100 text-xs text-red-600">!</span>
                  Anomalies <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-bold text-red-600">{data.anomalies.length}</span>
                </h3>
                <AnomalyList anomalies={data.anomalies} />
              </div>
            )}

            <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
              <div className="animate-fade-in-up">
                <h3 className="mb-3 text-sm font-bold text-slate-700">Span Tree</h3>
                {data.spans.length === 0 ? (
                  <EmptyState title="No behavior spans captured" description="This run completed without recording detailed span-level behavior data." />
                ) : (
                  <SpanTree spans={data.spans} anomalies={data.anomalies} selectedSpanId={selectedSpanId} onSelectSpan={setSelectedSpanId} />
                )}
              </div>
              {selectedSpan && <div><SpanDetail span={selectedSpan} anomalies={data.anomalies} /></div>}
            </div>
          </>
        )}
      </PageBody>
    </Layout>
  );
}