/** Anomaly Inbox page: filterable list of detected anomalies.
 *
 * Displays anomalies with severity dots, type badges, agent name, explanation,
 * and timestamp.  Clicking an anomaly navigates to the run timeline for that run.
 * Supports filtering by severity, anomaly type, and agent name.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import {
  Layout,
  PageHeader,
  PageBody,
  AnomalyBadge,
  SeverityDot,
  TimeDisplay,
  ErrorState,
  EmptyState,
  SkeletonList,
} from "../components/ui";

const SEVERITY_OPTIONS = [
  { value: "info", label: "Info" },
  { value: "warning", label: "Warning" },
  { value: "critical", label: "Critical" },
];

const TYPE_OPTIONS = [
  { value: "loop", label: "Loop" },
  { value: "retry_storm", label: "Retry Storm" },
  { value: "cost_spike", label: "Cost Spike" },
];

export default function AnomalyInboxPage() {
  const nav = useNavigate();
  const [severity, setSeverity] = useState("");
  const [type, setType] = useState("");
  const [agent, setAgent] = useState("");

  const { data, loading, error, refetch } = useAsync(
    () =>
      api.getAnomalies({
        severity: severity || undefined,
        anomaly_type: type || undefined,
        agent_name: agent || undefined,
        limit: 50,
      }),
    [severity, type, agent]
  );

  const items = data?.items ?? [];

  return (
    <Layout>
      <PageHeader
        title="Anomaly Inbox"
        subtitle="Prioritized anomalies for triage"
      />
      <PageBody>
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-label="Filter by severity"
          >
            <option value="">All severities</option>
            {SEVERITY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-label="Filter by type"
          >
            <option value="">All types</option>
            {TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <input
            value={agent}
            onChange={(e) => setAgent(e.target.value)}
            placeholder="Agent name..."
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-label="Filter by agent"
          />
          {(severity || type || agent) && (
            <button
              onClick={() => {
                setSeverity("");
                setType("");
                setAgent("");
              }}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Clear filters
            </button>
          )}
        </div>

        {error && <ErrorState message={error} onRetry={refetch} />}

        {loading && <SkeletonList rows={8} />}

        {!loading && !error && items.length === 0 && (
          <EmptyState
            title={
              severity || type || agent
                ? "No anomalies match these filters"
                : "No anomalies detected"
            }
            description={
              severity || type || agent
                ? "Try broadening your type, severity, or agent filter"
                : "No anomalies detected in the current window"
            }
          />
        )}

        {!loading && !error && items.length > 0 && (
          <div className="space-y-2">
            {items.map((item) => (
              <button
                key={item.id}
                onClick={() => nav(`/runs/${encodeURIComponent(item.run_id)}`)}
                className="flex w-full items-start gap-4 rounded-xl border border-gray-200 bg-white p-4 text-left shadow-sm transition-shadow hover:shadow-md"
              >
                <SeverityDot severity={item.severity} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <AnomalyBadge
                      anomaly_type={item.anomaly_type}
                      severity={item.severity}
                    />
                    <span className="truncate text-sm font-medium text-gray-900">
                      {item.agent_name}
                    </span>
                    <TimeDisplay iso={item.detected_at} />
                  </div>
                  <p className="mt-1 text-sm text-gray-600">
                    {item.explanation}
                  </p>
                  <p className="mt-0.5 font-mono text-xs text-gray-400">
                    {item.run_id}
                  </p>
                </div>
                <span className="shrink-0 text-gray-400">→</span>
              </button>
            ))}
          </div>
        )}
      </PageBody>
    </Layout>
  );
}