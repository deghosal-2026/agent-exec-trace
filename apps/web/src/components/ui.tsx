/** Shared UI components for the agent-exec-trace web frontend.
 *
 * Provides reusable visual primitives: badges, cards, skeletons, layout shell,
 * span tree, span detail, and filter controls.  All components use Tailwind CSS
 * classes for styling.
 */

import { useState, type ReactNode, type MouseEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import type { Anomaly } from "../types/api";

const STATUS_COLORS = {
  success: "bg-emerald-500",
  error: "bg-red-500",
  loop: "bg-amber-500",
} as const;

const ANOMALY_COLORS = {
  info: "bg-sky-500",
  warning: "bg-amber-500",
  critical: "bg-red-500",
} as const;

const ANOMALY_TYPE_LABELS = {
  loop: "Loop",
  retry_storm: "Retry Storm",
  cost_spike: "Cost Spike",
} as const;

const OPERATION_ICONS = {
  invoke_agent: "🤖",
  plan: "📋",
  execute_tool: "🔧",
  retrieval: "📎",
  create_memory: "💾",
  search_memory: "🔍",
  update_memory: "✏️",
  delete_memory: "🗑️",
} as const;

/** Colored badge showing a run's status (success/error/loop). */
export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status as keyof typeof STATUS_COLORS] ?? "bg-gray-500";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium text-white ${color}`}
    >
      <span className="size-1.5 rounded-full bg-white/70" />
      {status}
    </span>
  );
}

/** Colored badge showing an anomaly type with severity-based background. */
export function AnomalyBadge({
  anomaly_type,
  severity,
}: {
  anomaly_type: string;
  severity: string;
}) {
  const sevColor =
    ANOMALY_COLORS[severity as keyof typeof ANOMALY_COLORS] ?? "bg-gray-500";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-white ${sevColor} whitespace-nowrap`}
    >
      {ANOMALY_TYPE_LABELS[anomaly_type as keyof typeof ANOMALY_TYPE_LABELS] ?? anomaly_type}
    </span>
  );
}

/** Small colored dot indicating an anomaly's severity. */
export function AnomalyMarker({ severity }: { severity: string }) {
  const color = ANOMALY_COLORS[severity as keyof typeof ANOMALY_COLORS] ?? "bg-gray-500";
  return <span className={`inline-block size-2 rounded-full ${color} shrink-0`} />;
}

/** Small colored dot indicating an anomaly's severity (slightly larger). */
export function SeverityDot({ severity }: { severity: string }) {
  const color = ANOMALY_COLORS[severity as keyof typeof ANOMALY_COLORS] ?? "bg-gray-500";
  return <span className={`inline-block size-2.5 rounded-full ${color}`} />;
}

/** Icon representing a span operation type. */
export function OperationIcon({ operation }: { operation: string }) {
  const icon = OPERATION_ICONS[operation as keyof typeof OPERATION_ICONS] ?? "⚙️";
  return <span className="text-sm">{icon}</span>;
}

/** Formatted dollar cost display. */
export function CostDisplay({ value }: { value: number }) {
  return <span>${value.toFixed(4)}</span>;
}

/** Formatted duration, showing seconds when >= 1000ms. */
export function DurationDisplay({ ms }: { ms: number }) {
  if (ms >= 1000) return <span>{(ms / 1000).toFixed(2)}s</span>;
  return <span>{ms}ms</span>;
}

/** Colored badge showing a delta value with up/down arrow and suffix. */
export function DeltaBadge({ value, suffix = "%" }: { value: number; suffix?: string }) {
  const isPositive = value > 0;
  const isNeutral = value === 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs font-semibold ${
        isNeutral
          ? "bg-gray-100 text-gray-600"
          : isPositive
            ? "bg-red-50 text-red-700"
            : "bg-emerald-50 text-emerald-700"
      }`}
    >
      {isNeutral ? "" : isPositive ? "↑" : "↓"}
      {Math.abs(value).toFixed(1)}
      {suffix}
    </span>
  );
}

/** Single pulsing skeleton row for loading placeholder lists. */
function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 py-3">
      <div className="h-4 w-4 animate-pulse rounded bg-gray-200" />
      <div className="h-4 flex-1 animate-pulse rounded bg-gray-200" />
      <div className="h-4 w-20 animate-pulse rounded bg-gray-200" />
      <div className="h-4 w-16 animate-pulse rounded bg-gray-200" />
    </div>
  );
}

/** Skeleton placeholder for a list of N rows. */
export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-gray-100">
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} />
      ))}
    </div>
  );
}

/** Skeleton card placeholder for loading states. */
export function LoadingCard() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="mb-3 h-4 w-24 animate-pulse rounded bg-gray-200" />
      <div className="h-8 w-16 animate-pulse rounded bg-gray-200" />
    </div>
  );
}

/** Error state with message and optional retry button. */
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-8 text-center">
      <span className="text-3xl">⚠️</span>
      <p className="text-sm text-red-700">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-lg bg-red-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/** Empty state placeholder with title and optional description. */
export function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-gray-300 p-12 text-center">
      <span className="text-4xl text-gray-300">∅</span>
      <h3 className="text-sm font-medium text-gray-700">{title}</h3>
      {description && <p className="text-xs text-gray-500">{description}</p>}
    </div>
  );
}

const SIDEBAR_ITEMS = [
  { path: "/", label: "Dashboard", icon: "⌂" },
  { path: "/runs", label: "Run Timeline", icon: "↗" },
  { path: "/fleet", label: "Fleet Health", icon: "⊞" },
  { path: "/compare", label: "Version Compare", icon: "⇄" },
  { path: "/anomalies", label: "Anomaly Inbox", icon: "⚠" },
];

/** Sidebar navigation component with active route highlighting. */
function Sidebar() {
  const location = useLocation();
  return (
    <nav className="flex w-56 shrink-0 flex-col border-r border-gray-200 bg-white">
      <div className="flex items-center gap-2 border-b border-gray-200 px-5 py-4">
        <span className="text-xl">⟁</span>
        <span className="text-sm font-semibold text-gray-900">AET</span>
      </div>
      <div className="flex flex-col gap-0.5 p-3">
        {SIDEBAR_ITEMS.map((item) => {
          const active =
            item.path === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.path);
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-gray-100 text-gray-900"
                  : "text-gray-500 hover:bg-gray-50 hover:text-gray-800"
              }`}
            >
              <span className="w-5 text-center text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

/** Main layout shell with sidebar and content area. */
export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-auto">
        {children}
      </main>
    </div>
  );
}

/** Page header with title and optional subtitle. */
export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="border-b border-gray-200 bg-white px-8 py-5">
      <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
      {subtitle && <p className="mt-0.5 text-sm text-gray-500">{subtitle}</p>}
    </div>
  );
}

/** Page body content wrapper with padding. */
export function PageBody({ children }: { children: ReactNode }) {
  return <div className="flex-1 p-8">{children}</div>;
}

/** Format an ISO timestamp to a locale string. */
function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString();
}

/** Formatted time display element. */
export function TimeDisplay({ iso }: { iso: string }) {
  return <time className="text-xs text-gray-500">{formatTime(iso)}</time>;
}

/** Renders a list of anomalies as compact warning cards. */
export function AnomalyList({
  anomalies,
}: {
  anomalies: Anomaly[];
}) {
  if (anomalies.length === 0) return null;
  return (
    <div className="space-y-1.5">
      {anomalies.map((a) => (
        <div
          key={a.id}
          className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs"
        >
          <AnomalyBadge anomaly_type={a.anomaly_type} severity={a.severity} />
          <span className="flex-1 text-amber-800">{a.explanation}</span>
        </div>
      ))}
    </div>
  );
}

/** Interactive span tree component with expand/collapse and selection.
 *
 * Renders spans as a nested tree with operation icons, duration, and anomaly
 * markers.  Clicking a span selects it (showing detail in ``SpanDetail``).
 * Clicking the collapse toggle expands/collapses children.
 */
export function SpanTree({
  spans,
  anomalies,
  selectedSpanId,
  onSelectSpan,
}: {
  spans: import("../types/api").Span[];
  anomalies: Anomaly[];
  selectedSpanId: string | null;
  onSelectSpan: (spanId: string | null) => void;
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const anomalySpanIds = new Set<string>();
  for (const a of anomalies) {
    if (a.id) anomalySpanIds.add(a.id);
  }

  const rootSpans = spans.filter((s) => !s.parent_span_id);
  const childrenMap = new Map<string, import("../types/api").Span[]>();
  for (const s of spans) {
    if (s.parent_span_id) {
      const children = childrenMap.get(s.parent_span_id) ?? [];
      children.push(s);
      childrenMap.set(s.parent_span_id, children);
    }
  }

  function renderSpan(span: import("../types/api").Span, depth: number) {
    const isSelected = span.span_id === selectedSpanId;
    const children = childrenMap.get(span.span_id) ?? [];
    const isCollapsed = collapsed.has(span.span_id);
    const hasAnomaly = anomalySpanIds.has(span.span_id);
    const start = new Date(span.start_time).getTime();
    const end = new Date(span.end_time).getTime();
    const dur = end - start;

    function toggleCollapse(e: MouseEvent) {
      e.stopPropagation();
      setCollapsed((prev) => {
        const next = new Set(prev);
        if (next.has(span.span_id)) next.delete(span.span_id);
        else next.add(span.span_id);
        return next;
      });
    }

    return (
      <div key={span.span_id}>
        <button
          onClick={() => onSelectSpan(isSelected ? null : span.span_id)}
          className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
            isSelected
              ? "bg-blue-50 ring-1 ring-blue-200"
              : "hover:bg-gray-50"
          } ${hasAnomaly ? "ring-1 ring-amber-300" : ""}`}
          style={{ paddingLeft: `${12 + depth * 20}px` }}
        >
          {children.length > 0 && (
            <button
              onClick={toggleCollapse}
              className="size-4 shrink-0 text-gray-400 hover:text-gray-600"
            >
              {isCollapsed ? "▶" : "▼"}
            </button>
          )}
          {children.length === 0 && <span className="size-4 shrink-0" />}
          <OperationIcon operation={span.operation} />
          <span className="flex-1 truncate font-medium text-gray-800">
            {span.name}
          </span>
          {hasAnomaly && <AnomalyMarker severity="warning" />}
          <span className="text-xs text-gray-500">
            <DurationDisplay ms={dur} />
          </span>
        </button>
        {!isCollapsed &&
          children.map((child) => renderSpan(child, depth + 1))}
      </div>
    );
  }

  return (
    <div className="divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white">
      {rootSpans.map((s) => renderSpan(s, 0))}
    </div>
  );
}

/** Detail panel for a selected span, showing metadata and attributes. */
export function SpanDetail({
  span,
  anomalies,
}: {
  span: import("../types/api").Span;
  anomalies: Anomaly[];
}) {
  const start = new Date(span.start_time).getTime();
  const end = new Date(span.end_time).getTime();
  const dur = end - start;

  const spanAnomalies = anomalies.filter((a) => a.id === span.span_id);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <h3 className="mb-3 text-sm font-semibold text-gray-900">Span Detail</h3>
      <dl className="space-y-2 text-sm">
        <Row label="Name" value={span.name} />
        <Row label="Operation" value={span.operation} />
        <Row label="Status" value={span.status} />
        <Row
          label="Duration"
          value={<DurationDisplay ms={dur} />}
        />
        <Row label="Start" value={new Date(span.start_time).toLocaleString()} />
        <Row label="End" value={new Date(span.end_time).toLocaleString()} />
        <Row label="Span ID" value={span.span_id} mono />
        {span.parent_span_id && (
          <Row label="Parent ID" value={span.parent_span_id} mono />
        )}
      </dl>
      {spanAnomalies.length > 0 && (
        <div className="mt-3 space-y-1.5">
          <h4 className="text-xs font-semibold text-amber-700">Anomalies</h4>
          {spanAnomalies.map((a) => (
            <div
              key={a.id}
              className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
            >
              <strong>{a.anomaly_type}</strong>: {a.explanation}
            </div>
          ))}
        </div>
      )}
      {Object.keys(span.attributes).length > 0 && (
        <div className="mt-3">
          <h4 className="mb-1 text-xs font-semibold text-gray-600">Attributes</h4>
          <pre className="overflow-auto rounded-lg bg-gray-50 p-3 text-xs text-gray-700">
            {JSON.stringify(span.attributes, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

/** A single key-value row in a definition list. */
function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="shrink-0 text-gray-500">{label}</dt>
      <dd
        className={`text-right text-gray-900 ${
          mono ? "font-mono text-xs" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  );
}

/** Dropdown select for filtering, with optional placeholder. */
export function FilterSelect({
  value,
  options,
  onChange,
  placeholder,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
    >
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

/** A summary stat card with label, large value, optional subtext, and accent. */
export function SummaryCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-5 shadow-sm ${
        accent
          ? "border-blue-200 bg-blue-50"
          : "border-gray-200 bg-white"
      }`}
    >
      <p className="text-xs font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-500">{sub}</p>}
    </div>
  );
}

/** Hook returning anomaly filter state + setters. */
export function useAnomalyFilter() {
  const [severity, setSeverity] = useState("");
  const [anomalyType, setAnomalyType] = useState("");
  const [agentName, setAgentName] = useState("");

  return {
    severity,
    setSeverity,
    anomalyType,
    setAnomalyType,
    agentName,
    setAgentName,
  };
}