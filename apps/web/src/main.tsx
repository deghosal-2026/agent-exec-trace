/**
 * Application entry point for the agent-exec-trace web dashboard.
 *
 * ## Architecture
 * - Rendered into the `<div id="root">` element in `index.html`.
 * - Wrapped in `<StrictMode>` for development-time checks (double-rendering, etc.).
 * - Uses React Router's `<BrowserRouter>` for client-side routing.
 *
 * ## Route table
 * | Path              | Component       | Description                    |
 * |-------------------|-----------------|--------------------------------|
 * | `/`               | Dashboard       | Fleet overview landing page    |
 * | `/runs`           | RunTimeline     | Run search (empty state)       |
 * | `/runs/:runId`    | RunTimeline     | Run timeline with auto-search  |
 * | `/fleet`          | FleetHealth     | Filterable fleet health table  |
 * | `/compare`        | VersionCompare  | Side-by-side version comparison|
 * | `/anomalies`      | AnomalyInbox    | Prioritized anomaly triage     |
 * | `*` (catch-all)   | Navigate → "/"  | Redirect unknown paths to home |
 *
 * ## CSS
 * Global styles (`index.css`) are imported here and apply to the entire app.
 * Tailwind CSS is configured via `@import "tailwindcss"` in the CSS file.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import RunTimeline from "./pages/RunTimeline";
import FleetHealth from "./pages/FleetHealth";
import VersionCompare from "./pages/VersionCompare";
import AnomalyInbox from "./pages/AnomalyInbox";
import "./index.css";

/** Application entry point. Renders the router with all page routes. */
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/runs" element={<RunTimeline />} />
        <Route path="/runs/:runId" element={<RunTimeline />} />
        <Route path="/fleet" element={<FleetHealth />} />
        <Route path="/compare" element={<VersionCompare />} />
        <Route path="/anomalies" element={<AnomalyInbox />} />
        {/* Catch-all: redirect unknown paths to the dashboard */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>
);