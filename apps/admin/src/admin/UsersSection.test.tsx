import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { UsersSection } from "./UsersSection";
import * as api from "./api";

vi.mock("./api", () => {
  const mockUsers = {
    results: [
      {
        id: 1,
        email: "user@example.com",
        first_name: "Test",
        last_name: "User",
        is_active: true,
        workspace_count: 2,
        has_google_login: true,
        has_usable_password: true,
        auth_providers: ["google"],
        date_joined: "2024-01-01T00:00:00Z",
        last_login: "2024-01-02T00:00:00Z",
        social_account_count: 1,
      },
    ],
    next: null,
    previous: null,
  };
  return {
    fetchUsers: vi.fn().mockResolvedValue(mockUsers),
    updateUser: vi.fn().mockResolvedValue(mockUsers.results[0]),
    startImpersonation: vi.fn().mockResolvedValue({ redirect_url: "/internal/impersonate/1234/" }),
    resetPassword: vi.fn().mockResolvedValue({ approval_required: true, approval_request_id: "req-1", approval_status: "PENDING" }),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("UsersSection", () => {
  it("renders users list", async () => {
    render(<UsersSection roleLevel={2} />);
    await waitFor(() => expect(screen.getAllByText(/user@example.com/i).length).toBeGreaterThan(0));
    expect(screen.getByText(/Users/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Google/i).length).toBeGreaterThan(0);
  });

  it("starts impersonation and redirects to returned URL", async () => {
    const startImpersonation = api.startImpersonation as unknown as vi.Mock;
    startImpersonation.mockResolvedValueOnce({ redirect_url: "/internal/impersonate/redirect-token/" });
    const promptSpy = vi.spyOn(window, "prompt").mockReturnValue("Debugging session");
    const originalLocation = window.location;
    // @ts-expect-error - allow overriding for test
    delete window.location;
    // @ts-expect-error - jsdom location override for test assertion
    window.location = { href: "" };

    render(<UsersSection roleLevel={2} />);
    const button = await screen.findByRole("button", { name: /impersonate/i });
    fireEvent.click(button);

    await waitFor(() =>
      expect((window as any).location.href).toContain("/internal/impersonate/redirect-token/")
    );

    window.location = originalLocation;
    promptSpy.mockRestore();
  });

  it("applies filters to fetch users", async () => {
    render(<UsersSection roleLevel={2} />);
    const fetchUsersMock = api.fetchUsers as unknown as vi.Mock;
    await waitFor(() => expect(fetchUsersMock).toHaveBeenCalledTimes(1));
    fetchUsersMock.mockClear();

    fireEvent.click(await screen.findByLabelText(/status filter/i));
    fireEvent.click(screen.getByText("Suspended"));

    fireEvent.click(screen.getByLabelText(/google login filter/i));
    fireEvent.click(screen.getByText("Has Google"));

    const searchInput = screen.getByLabelText(/search users/i);
    fireEvent.change(searchInput, { target: { value: "alice" } });
    await waitFor(() => expect(searchInput).toHaveValue("alice"));
    fireEvent.click(screen.getByRole("button", { name: /^search$/i }));

    await waitFor(() => expect(fetchUsersMock).toHaveBeenCalled());
    const lastCall = fetchUsersMock.mock.calls[fetchUsersMock.mock.calls.length - 1]?.[0];
    expect(lastCall).toMatchObject({ page: 1, search: "alice", status: "suspended", has_google: "true", page_size: 12 });
  });
});
