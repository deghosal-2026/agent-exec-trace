import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Layout } from "../components/ui";

describe("Layout", () => {
  it("renders navigation links", () => {
    render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>
    );
    expect(screen.getByText("Run Timeline")).toBeInTheDocument();
    expect(screen.getByText("Fleet Health")).toBeInTheDocument();
    expect(screen.getByText("Version Compare")).toBeInTheDocument();
    expect(screen.getByText("Anomaly Inbox")).toBeInTheDocument();
  });
});
