import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { AuditLogSection } from "./AuditLogSection";

vi.mock("./api", () => {
  const mockLogs = {
    results: [
      {
        id: 1,
        timestamp: "2024-01-01T00:00:00Z",
        admin_email: "admin@example.com",
        action: "USER_UPDATED",
        object_type: "user",
        object_id: "1",
        extra: {},
        remote_ip: "127.0.0.1",
        level: "INFO",
        category: "user_update",
      },
    ],
    next: null,
    previous: null,
  };
  return {
    fetchAuditLog: vi.fn().mockResolvedValue(mockLogs),
  };
});

describe("AuditLogSection", () => {
  it("renders audit log entries", async () => {
    render(<AuditLogSection />);
    await waitFor(() => expect(screen.getAllByText(/USER_UPDATED/i).length).toBeGreaterThan(0));
    expect(screen.getAllByText(/admin@example.com/i).length).toBeGreaterThan(0);
  });

  it("shows level and category filters", async () => {
    render(<AuditLogSection />);
    await waitFor(() => expect(screen.getByText(/All risks/i)).toBeInTheDocument());
    expect(screen.getByPlaceholderText(/Search by actor, IP, action/i)).toBeInTheDocument();
  });
});
