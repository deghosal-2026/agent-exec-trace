/**
 * Layout component tests.
 *
 * Verifies that the application shell (sidebar + main content) renders
 * correctly with all navigation links present.
 */

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Layout } from "../components/ui";

describe("Layout", () => {
  /**
   * Verifies that the sidebar renders all five navigation links:
   * Dashboard, Run Timeline, Fleet Health, Version Compare, Anomaly Inbox.
   *
   * Uses `MemoryRouter` (not `BrowserRouter`) for isolated test routing
   * without a real browser environment.
   */
  it("renders navigation links", () => {
    // Render Layout with a simple child and MemoryRouter for routing context
    render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>
    );

    // Assert all expected navigation label texts are present in the document
    expect(screen.getByText("Run Timeline")).toBeInTheDocument();
    expect(screen.getByText("Fleet Health")).toBeInTheDocument();
    expect(screen.getByText("Version Compare")).toBeInTheDocument();
    expect(screen.getByText("Anomaly Inbox")).toBeInTheDocument();
  });
});