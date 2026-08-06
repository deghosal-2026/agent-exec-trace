/** Shared UI components — agent-exec-trace v0.1.0
 *
 * Cyber-industrial design system: dark sidebar, electric-blue accents, refined
 * data surfaces, animated micro-interactions, and professional status indicators.
 */

import { useState, type ReactNode, type MouseEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import type { Anomaly } from "../types/api";

/* ── Design tokens ── */

const STATUS_COLORS = {
  success: "bg-emerald-500",
  error: "bg-red-500",
  loop: "bg-amber-500",
} as const;

const STATUS_LABELS: Record<string, string> = {
  success: "Healthy",
  error: "Failed",
  loop: "Looping",
};

const SEVERITY_COLORS = {
  info: { bg: "bg-indigo-50", text: "text-indigo-700", dot: "bg-indigo-500", border: "border-indigo-200" },
  warning: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-500", border: "border-amber-200" },
  critical: { bg: "bg-red-50", text: "text-red-700", dot: "bg-red-500", border: "border-red-200" },
} as const;

const ANOMALY_TYPE_LABELS: Record<string, string> = {
  loop: "Loop", pattern_loop: "Pattern Loop", argument_loop: "Arg Loop",
  retry_storm: "Retry Storm", systemic_retry: "Systemic Retry", cascading_retry: "Cascading Retry",
  cost_spike: "Cost Spike", cost_vs_baseline: "Cost vs Baseline", token_explosion: "Token Explosion",
  tool_error_rate: "Tool Errors", tool_latency: "Latency Spike", tool_timeout: "Timeout",
  run_duration: "Duration", inactivity: "Inactivity", empty_response: "Empty Output",
  output_drift: "Output Drift", escalation_rate: "Escalation",
};

const OPERATION_ICONS: Record<string, string> = {
  invoke_agent: "🤖", plan: "📋", execute_tool: "🔧", retrieval: "📎",
  create_memory: "💾", search_memory: "🔍", update_memory: "✏️", delete_memory: "🗑️",
};

/* ── Status & Severity Badges ── */

export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status as keyof typeof STATUS_COLORS] ?? "bg-slate-500";
  const label = STATUS_LABELS[status] ?? status;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold text-white ${color}`}>
      <span className="size-1.5 rounded-full bg-white/70" />
      {label}
    </span>
  );
}

export function AnomalyBadge({ anomaly_type, severity }: { anomaly_type: string; severity: string }) {
  const sev = SEVERITY_COLORS[severity as keyof typeof SEVERITY_COLORS] ?? SEVERITY_COLORS.warning;
  const label = ANOMALY_TYPE_LABELS[anomaly_type] ?? anomaly_type.replace(/_/g, " ");
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold ${sev.bg} ${sev.text} border ${sev.border}`}>
      <span className={`size-1.5 rounded-full ${sev.dot}`} />
      {label}
    </span>
  );
}

export function SeverityDot({ severity }: { severity: string }) {
  const sev = SEVERITY_COLORS[severity as keyof typeof SEVERITY_COLORS] ?? SEVERITY_COLORS.warning;
  return (
    <span className={`inline-flex size-3 rounded-full ${sev.dot} ring-2 ring-offset-1 ${sev.dot.replace("bg-", "ring-")}/30 shrink-0`} />
  );
}

export function AnomalyMarker({ severity }: { severity: string }) {
  const sev = SEVERITY_COLORS[severity as keyof typeof SEVERITY_COLORS] ?? SEVERITY_COLORS.warning;
  return <span className={`inline-block size-2 rounded-full ${sev.dot} shrink-0`} />;
}

/* ── Display formatters ── */

export function OperationIcon({ operation }: { operation: string }) {
  const icon = OPERATION_ICONS[operation as keyof typeof OPERATION_ICONS] ?? "⚙️";
  return <span className="text-sm">{icon}</span>;
}

export function CostDisplay({ value }: { value: number }) {
  return (
    <span className="tabular-nums">
      <span className="text-slate-400">$</span>
      {value.toFixed(4)}
    </span>
  );
}

export function DurationDisplay({ ms }: { ms: number }) {
  if (ms >= 60000) return <span className="tabular-nums">{(ms / 60000).toFixed(1)}<span className="text-slate-400">m</span></span>;
  if (ms >= 1000) return <span className="tabular-nums">{(ms / 1000).toFixed(2)}<span className="text-slate-400">s</span></span>;
  return <span className="tabular-nums">{ms}<span className="text-slate-400">ms</span></span>;
}

export function DeltaBadge({ value, suffix = "%" }: { value: number; suffix?: string }) {
  const abs = Math.abs(value);
  const isUp = value > 0;
  const isZero = value === 0;
  if (isZero) return <span className="text-sm font-medium text-slate-400 tabular-nums">—</span>;
  return (
    <span className={`inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-xs font-bold tabular-nums ${isUp ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-600"}`}>
      <span className="text-[10px]">{isUp ? "▲" : "▼"}</span>
      {abs.toFixed(1)}{suffix}
    </span>
  );
}

/* ── Loading skeletons ── */

function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 py-3">
      <div className="h-4 w-4 shimmer rounded" />
      <div className="h-4 w-3/5 shimmer rounded" />
      <div className="h-4 w-20 shimmer rounded" />
      <div className="h-4 w-16 shimmer rounded" />
    </div>
  );
}

export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-slate-100">
      {Array.from({ length: rows }).map((_, i) => <SkeletonRow key={i} />)}
    </div>
  );
}

export function SkeletonCard() {
  return <div className="h-28 shimmer rounded-xl" />;
}

/* ── States: Error, Empty ── */

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-2xl border border-red-200 bg-gradient-to-b from-red-50 to-white p-10 text-center animate-fade-in-up">
      <div className="flex size-14 items-center justify-center rounded-2xl bg-red-100 text-2xl shadow-sm">⚠️</div>
      <div>
        <h3 className="text-sm font-semibold text-red-800">Something went wrong</h3>
        <p className="mt-1 text-sm text-red-600">{message}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="rounded-xl bg-red-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-red-700 hover:shadow-md active:scale-95 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2">
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/50 p-12 text-center animate-fade-in">
      <div className="flex size-14 items-center justify-center rounded-2xl bg-slate-100 text-2xl text-slate-300">∅</div>
      <h3 className="text-sm font-semibold text-slate-600">{title}</h3>
      {description && <p className="max-w-xs text-sm text-slate-400">{description}</p>}
    </div>
  );
}

/* ── Navigation Sidebar ── */

const SIDEBAR_ITEMS = [
  { path: "/", label: "Dashboard", icon: "◈" },
  { path: "/runs", label: "Run Timeline", icon: "⏱" },
  { path: "/fleet", label: "Fleet Health", icon: "⊞" },
  { path: "/compare", label: "Version Compare", icon: "⇄" },
  { path: "/anomalies", label: "Anomaly Inbox", icon: "⚡" },
];

function Sidebar() {
  const location = useLocation();
  return (
    <nav className="flex w-60 shrink-0 flex-col border-r border-slate-800 bg-[#0b1120]">
      <div className="flex items-center gap-3 border-b border-slate-800 px-5 py-5">
        <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/25">
          <span className="text-lg font-bold text-white">⟁</span>
        </div>
        <div>
          <div className="text-sm font-bold text-white leading-tight">agent-exec</div>
          <div className="text-[10px] font-medium uppercase tracking-widest text-blue-400">Trace</div>
        </div>
      </div>
      <div className="flex flex-col gap-0.5 p-3">
        {SIDEBAR_ITEMS.map((item) => {
          const active = item.path === "/" ? location.pathname === "/" : location.pathname.startsWith(item.path);
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
                active
                  ? "bg-blue-600/10 text-blue-400 shadow-sm"
                  : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
              }`}
            >
              <span className={`flex size-7 items-center justify-center rounded-lg text-base transition-all ${active ? "bg-blue-600/20 text-blue-400" : "bg-slate-800 text-slate-500 group-hover:bg-slate-700 group-hover:text-slate-300"}`}>
                {item.icon}
              </span>
              {item.label}
              {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-blue-400" />}
            </Link>
          );
        })}
      </div>
      <div className="mt-auto border-t border-slate-800 p-4">
        <div className="rounded-xl bg-slate-800/50 px-3 py-2.5">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">v0.1.0</div>
          <div className="mt-0.5 text-xs text-slate-400">35 detectors active</div>
        </div>
      </div>
    </nav>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-auto">{children}</main>
    </div>
  );
}

/* ── Page chrome ── */

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="border-b border-slate-200 bg-white px-8 py-5">
      <h1 className="text-xl font-bold tracking-tight text-slate-900">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
    </div>
  );
}

export function PageBody({ children }: { children: ReactNode }) {
  return <div className="flex-1 p-8">{children}</div>;
}

export function TimeDisplay({ iso }: { iso: string }) {
  const d = new Date(iso);
  return <time className="text-xs tabular-nums text-slate-400">{d.toLocaleString()}</time>;
}

/* ── Summary Stat Card ── */

export function SummaryCard({ label, value, sub, accent }: {
  label: string; value: ReactNode; sub?: string; accent?: boolean;
}) {
  return (
    <div className={`group rounded-2xl border p-5 transition-all hover:shadow-md ${accent ? "border-blue-200 bg-gradient-to-br from-blue-50 to-white shadow-sm shadow-blue-100/50" : "border-slate-200 bg-white shadow-sm"}`}>
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</p>
      <p className={`mt-2 text-3xl font-bold tracking-tight tabular-nums ${accent ? "text-blue-700" : "text-slate-900"}`}>
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

/* ── Anomaly List ── */

export function AnomalyList({ anomalies }: { anomalies: Anomaly[] }) {
  if (anomalies.length === 0) return null;
  return (
    <div className="space-y-2">
      {anomalies.map((a) => {
        const sev = SEVERITY_COLORS[a.severity as keyof typeof SEVERITY_COLORS] ?? SEVERITY_COLORS.warning;
        return (
          <div key={a.id} className={`flex items-start gap-3 rounded-xl border p-3 text-sm ${sev.bg} ${sev.border}`}>
            <SeverityDot severity={a.severity} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <AnomalyBadge anomaly_type={a.anomaly_type} severity={a.severity} />
              </div>
              <p className={`mt-1 text-xs ${sev.text}`}>{a.explanation}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Span Tree ── */

export function SpanTree({ spans, anomalies, selectedSpanId, onSelectSpan }: {
  spans: import("../types/api").Span[];
  anomalies: Anomaly[];
  selectedSpanId: string | null;
  onSelectSpan: (spanId: string | null) => void;
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const anomalySpanIds = new Set(anomalies.map(a => a.id).filter(Boolean));
  const rootSpans = spans.filter(s => !s.parent_span_id);
  const childrenMap = new Map<string, import("../types/api").Span[]>();
  for (const s of spans) {
    if (s.parent_span_id) {
      const c = childrenMap.get(s.parent_span_id) ?? [];
      c.push(s);
      childrenMap.set(s.parent_span_id, c);
    }
  }

  function renderSpan(span: import("../types/api").Span, depth: number) {
    const selected = span.span_id === selectedSpanId;
    const kids = childrenMap.get(span.span_id) ?? [];
    const isCollapsed = collapsed.has(span.span_id);
    const hasErr = anomalySpanIds.has(span.span_id);
    const dur = new Date(span.end_time).getTime() - new Date(span.start_time).getTime();

    function toggle(e: MouseEvent) {
      e.stopPropagation();
      setCollapsed(prev => {
        const n = new Set(prev);
        n.has(span.span_id) ? n.delete(span.span_id) : n.add(span.span_id);
        return n;
      });
    }

    return (
      <div key={span.span_id}>
        <button
          onClick={() => onSelectSpan(selected ? null : span.span_id)}
          className={`flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm transition-all ${
            selected ? "bg-blue-50 ring-1 ring-blue-200 shadow-sm" : "hover:bg-slate-50"
          } ${hasErr ? "ring-1 ring-amber-300" : ""}`}
          style={{ paddingLeft: `${16 + depth * 24}px` }}
        >
          {kids.length > 0 ? (
            <span onClick={toggle} className="flex size-5 shrink-0 items-center justify-center rounded text-xs text-slate-400 hover:bg-slate-200 hover:text-slate-600 transition-colors">
              {isCollapsed ? "▸" : "▾"}
            </span>
          ) : <span className="size-5 shrink-0" />}
          <OperationIcon operation={span.operation} />
          <span className="flex-1 truncate font-medium text-slate-700">{span.name}</span>
          {hasErr && <AnomalyMarker severity="warning" />}
          <span className="text-xs tabular-nums text-slate-400"><DurationDisplay ms={dur} /></span>
        </button>
        {!isCollapsed && kids.map(c => renderSpan(c, depth + 1))}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      {rootSpans.length === 0 ? (
        <div className="p-6 text-center text-sm text-slate-400">No spans recorded</div>
      ) : (
        rootSpans.map(s => renderSpan(s, 0))
      )}
    </div>
  );
}

/* ── Span Detail Panel ── */

export function SpanDetail({ span, anomalies }: {
  span: import("../types/api").Span;
  anomalies: Anomaly[];
}) {
  const dur = new Date(span.end_time).getTime() - new Date(span.start_time).getTime();
  const spanAnomalies = anomalies.filter(a => a.id === span.span_id);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm animate-slide-in">
      <div className="mb-4 flex items-center gap-2">
        <OperationIcon operation={span.operation} />
        <h3 className="text-sm font-bold text-slate-800">{span.name}</h3>
        {span.status && <StatusBadge status={span.status} />}
      </div>
      <dl className="space-y-2.5 text-sm">
        <Row label="Operation" value={span.operation} />
        <Row label="Duration" value={<DurationDisplay ms={dur} />} />
        <Row label="Start" value={new Date(span.start_time).toLocaleString()} />
        <Row label="Span ID" value={span.span_id} mono />
        {span.parent_span_id && <Row label="Parent ID" value={span.parent_span_id} mono />}
      </dl>
      {spanAnomalies.length > 0 && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <h4 className="mb-2 text-xs font-bold text-amber-800 uppercase tracking-wider">Anomalies</h4>
          {spanAnomalies.map(a => (
            <div key={a.id} className="text-xs text-amber-700 flex items-center gap-2 py-1">
              <AnomalyMarker severity={a.severity} />
              <strong>{a.anomaly_type}</strong>: {a.explanation}
            </div>
          ))}
        </div>
      )}
      {Object.keys(span.attributes).length > 0 && (
        <div className="mt-4">
          <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">Attributes</h4>
          <pre className="overflow-auto rounded-xl bg-slate-50 p-3 text-xs text-slate-600 border border-slate-100">
            {JSON.stringify(span.attributes, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="shrink-0 text-slate-400">{label}</dt>
      <dd className={`text-right text-slate-800 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}

/* ── Filter Select ── */

export function FilterSelect({ value, options, onChange, placeholder }: {
  value: string; options: { value: string; label: string }[]; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition-all hover:border-slate-300 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20">
      {placeholder && <option value="">{placeholder}</option>}
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

/* ── Input ── */

export function TextInput({ value, onChange, placeholder, ariaLabel, onKeyDown, className }: {
  value: string; onChange: (v: string) => void; placeholder?: string; ariaLabel?: string;
  onKeyDown?: (e: React.KeyboardEvent) => void; className?: string;
}) {
  return (
    <input value={value} onChange={e => onChange(e.target.value)} onKeyDown={onKeyDown}
      placeholder={placeholder} aria-label={ariaLabel}
      className={`rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 transition-all hover:border-slate-300 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 ${className ?? ""}`} />
  );
}

/* ── Primary Button ── */

export function PrimaryButton({ onClick, children, className }: {
  onClick: () => void; children: ReactNode; className?: string;
}) {
  return (
    <button onClick={onClick}
      className={`rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-slate-800 hover:shadow-md active:scale-[0.97] focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 ${className ?? ""}`}>
      {children}
    </button>
  );
}

/* ── Clear Filters Button ── */

export function ClearButton({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} className="rounded-xl px-3 py-2 text-xs font-semibold text-slate-400 transition-all hover:bg-slate-100 hover:text-slate-600">
      Clear all
    </button>
  );
}