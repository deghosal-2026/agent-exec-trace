/**
 * Run Timeline page — deep inspection of individual agent execution traces.
 *
 * ## Purpose
 * Allows operators to inspect a single agent run by entering a run ID.
 * Displays run metadata (agent, version, status, duration, cost), associated
 * anomalies, and an interactive span tree with detail panel for span inspection.
 *
 * ## Data flow
 * 1. User enters a run ID in the search input (pre-populated from URL param `:runId`).
 * 2. On "Inspect" click (or Enter key), the URL is updated and `searchId` state changes.
 * 3. `useAsync` triggers `api.getRunTimeline(searchId)`.
 * 4. Response populates: run summary header, anomaly list, span tree, and optional span detail.
 *
 * ## URL routing
 * - `/runs` — shows the empty input prompt.
 * - `/runs/:runId` — auto-populates the input and triggers search on mount.
 * - Search updates use `replace: true` to avoid history pollution for each new lookup.
 *
 * ## User interactions
 * - Text input + "Inspect" button (or Enter key) to search by run ID.
 * - Span tree: expand/collapse branches, click to select a span for detail view.
 * - Anomaly cards: visual list of all anomalies attached to this run.
 *
 * ## UI states
 * - **No search**: `EmptyState` prompt to enter a run ID.
 * - **Loading (with searchId)**: skeleton cards for summary + span tree.
 * - **Error (with searchId)**: `ErrorState` with retry.
 * - **Data**: run summary header, anomaly section (if anomalies exist), span tree +
 *   detail panel in a two-column layout.
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import { Layout, PageHeader, PageBody, StatusBadge, CostDisplay, DurationDisplay, SpanTree, SpanDetail, AnomalyList, ErrorState, EmptyState, PrimaryButton, TextInput } from "../components/ui";

/**
 * Run Timeline page component.
 *
 * Two input modes:
 * 1. URL param `/runs/:runId` — auto-populates input and searches on mount.
 * 2. Manual input — user pastes a run ID and clicks "Inspect".
 *
 * When data loads, the page renders:
 * - A run summary header with agent name, status badge, loop indicator, duration, and cost.
 * - An anomaly section (collapsible via presence/absence).
 * - A two-column layout: span tree (left) + span detail panel (right when a span is selected).
 */
export default function RunTimelinePage() {
  const { runId } = useParams<{ runId: string }>();
  const nav = useNavigate();

  // `inputRunId` is the controlled input value (may differ from URL on manual edits)
  const [inputRunId, setInputRunId] = useState(runId ?? "");

  // `searchId` triggers the API call; set on "Inspect" click or Enter
  const [searchId, setSearchId] = useState(runId ?? "");

  // Tracks which span is selected in the span tree for detail panel display
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);

  // Fetch run timeline when searchId is non-empty; reject with a prompt otherwise
  const { data, loading, error, refetch } = useAsync(
    () => (searchId ? api.getRunTimeline(searchId) : Promise.reject(new Error("Enter a run ID"))),
    [searchId]
  );

  /**
   * Handles the "Inspect" action: validates input, updates URL and searchId.
   * Uses `replace: true` to avoid accumulating history entries for each lookup.
   */
  function handleSearch() {
    const id = inputRunId.trim();
    if (!id) return;
    setSearchId(id);
    nav(`/runs/${encodeURIComponent(id)}`, { replace: true });
  }

  // Find the currently selected span for the detail panel (null when none selected)
  const selectedSpan = data?.spans.find(s => s.span_id === selectedSpanId) ?? null;

  return (
    <Layout>
      <PageHeader title="Run Timeline" subtitle="Deep-dive into a single agent execution trace" />
      <PageBody>
        {/* Search bar: text input + Inspect button */}
        <div className="mb-6 flex items-center gap-3">
          <TextInput value={inputRunId} onChange={setInputRunId} onKeyDown={e => e.key === "Enter" && handleSearch()}
            placeholder="Paste a run ID..." ariaLabel="Run ID" className="max-w-xl flex-1" />
          <PrimaryButton onClick={handleSearch}>Inspect</PrimaryButton>
        </div>

        {/* Empty prompt: shown when no run ID has been searched */}
        {!searchId && <EmptyState title="Enter a run ID to inspect" description="Paste a run ID above or navigate from anomalies, fleet, or dashboard." />}

        {/* Error state: shown when searchId is set but the fetch fails */}
        {error && searchId && <ErrorState message={error} onRetry={refetch} />}

        {/* Loading state: shimmer skeletons when data is being fetched */}
        {loading && searchId && (
          <div className="space-y-4">
            <div className="h-28 shimmer rounded-xl" />
            <div className="h-64 shimmer rounded-xl" />
          </div>
        )}

        {/* Data state: run summary + anomaly list + span tree + span detail */}
        {data && !loading && (
          <>
            {/* Run summary header card */}
            <div className="mb-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm animate-fade-in-up">
              <div className="border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white px-6 py-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-bold text-slate-800 capitalize">{data.agent_name.replace(/_/g, " ")}</h2>
                      <StatusBadge status={data.status} />
                      {/* Loop indicator badge: only shown when loop_detected is true */}
                      {data.loop_detected && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-bold text-amber-700 border border-amber-200">
                          ⟳ Loop ×{data.loop_count}
                        </span>
                      )}
                    </div>
                    <p className="font-mono text-xs text-slate-400">ID: {data.run_id}</p>
                    <p className="text-xs text-slate-400">Version {data.agent_version}</p>
                  </div>
                  {/* Duration and Cost stat boxes */}
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

            {/* Anomaly section: only rendered when anomalies exist */}
            {data.anomalies.length > 0 && (
              <div className="mb-6 animate-fade-in-up">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-700">
                  <span className="flex size-5 items-center justify-center rounded-md bg-red-100 text-xs text-red-600">!</span>
                  Anomalies <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-bold text-red-600">{data.anomalies.length}</span>
                </h3>
                <AnomalyList anomalies={data.anomalies} />
              </div>
            )}

            {/* Two-column layout: span tree (left) + span detail panel (right) */}
            {/* Uses CSS grid with a fixed 380px right column for the detail panel */}
            <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
              <div className="animate-fade-in-up">
                <h3 className="mb-3 text-sm font-bold text-slate-700">Span Tree</h3>
                {data.spans.length === 0 ? (
                  <EmptyState title="No behavior spans captured" description="This run completed without recording detailed span-level behavior data." />
                ) : (
                  <SpanTree spans={data.spans} anomalies={data.anomalies} selectedSpanId={selectedSpanId} onSelectSpan={setSelectedSpanId} />
                )}
              </div>
              {/* Span detail panel: only rendered when a span is selected */}
              {selectedSpan && <div><SpanDetail span={selectedSpan} anomalies={data.anomalies} /></div>}
            </div>
          </>
        )}
      </PageBody>
    </Layout>
  );
}