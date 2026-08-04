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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>
);