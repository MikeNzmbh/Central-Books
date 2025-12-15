import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { WorkspacesSection } from "./WorkspacesSection";

vi.mock("./api", () => {
  const mockWorkspaces = {
    results: [
      {
        id: 1,
        name: "Clover Books Labs Inc.",
        owner_email: "owner@example.com",
        plan: "Pro",
        status: "active",
        is_deleted: false,
        created_at: "2024-01-01T00:00:00Z",
        unreconciled_count: 0,
        ledger_status: "balanced",
      },
    ],
    next: null,
    previous: null,
  };
  return {
    fetchWorkspaces: vi.fn().mockResolvedValue(mockWorkspaces),
    updateWorkspace: vi.fn().mockResolvedValue(mockWorkspaces.results[0]),
  };
});

describe("WorkspacesSection", () => {
  it("renders workspaces table", async () => {
    render(<WorkspacesSection />);
    await waitFor(() => expect(screen.getAllByText(/Clover Books Labs Inc./i).length).toBeGreaterThan(0));
    expect(screen.getAllByRole("columnheader", { name: /Owner/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("columnheader", { name: /Plan/i }).length).toBeGreaterThan(0);
  });
});
