import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { SupportSection } from "./SupportSection";

function createMockTickets() {
  return {
    results: [
      {
        id: 1,
        subject: "Cannot login",
        status: "OPEN",
        priority: "NORMAL",
        source: "IN_APP",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
        user_email: "user@example.com",
        workspace_name: "Acme Inc",
        notes: [],
      },
    ],
    next: null,
    previous: null,
  };
}

vi.mock("./api", () => {
  const mockTickets = createMockTickets();
  return {
    fetchSupportTickets: vi.fn().mockResolvedValue(mockTickets),
    updateSupportTicket: vi.fn().mockResolvedValue(mockTickets.results[0]),
    addSupportTicketNote: vi.fn().mockResolvedValue(mockTickets.results[0]),
  };
});

describe("SupportSection", () => {
  it("renders support tickets and applies filters", async () => {
    render(<SupportSection />);
    await waitFor(() => expect(screen.getByText(/Cannot login/i)).toBeInTheDocument());
    expect(screen.getByText(/user@example.com/i)).toBeInTheDocument();

    const searchInput = screen.getByPlaceholderText(/Search subject/i);
    fireEvent.change(searchInput, { target: { value: "login" } });
    fireEvent.blur(searchInput);
    await waitFor(() => {
      const { fetchSupportTickets } = require("./api");
      expect(fetchSupportTickets).toHaveBeenCalled();
    });
  });
});
