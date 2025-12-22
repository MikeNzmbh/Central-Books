import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "./AuthContext";

const TestHarness = () => {
  const { auth, logout } = useAuth();
  return (
    <div>
      <span data-testid="auth-state">{auth.authenticated ? "auth" : "anon"}</span>
      <button onClick={logout}>Logout</button>
    </div>
  );
};

describe("AuthContext", () => {
  let originalLocation: Location;

  beforeEach(() => {
    originalLocation = window.location;
    // @ts-expect-error override for test
    delete window.location;
    // @ts-expect-error override for test
    window.location = { assign: vi.fn() } as Location;

    const mockFetch = vi.fn().mockImplementation((url: RequestInfo | URL) => {
      const href = String(url);
      if (href === "/api/auth/config") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ csrfToken: "testtoken" }),
        });
      }
      if (href === "/api/auth/me") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ authenticated: true, user: { email: "user@example.com" } }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      });
    });
    vi.stubGlobal("fetch", mockFetch as unknown as typeof fetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    // Restore window.location
    window.location = originalLocation;
  });

  it("renders logout button", async () => {
    render(
      <AuthProvider>
        <TestHarness />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByText("Logout")).toBeInTheDocument());
  });

  it("logout clears auth state", async () => {
    render(
      <AuthProvider>
        <TestHarness />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("auth-state").textContent).toBe("auth"));

    fireEvent.click(screen.getByText("Logout"));

    await waitFor(() => expect(screen.getByTestId("auth-state").textContent).toBe("anon"));
    expect((window.location as any).assign).toHaveBeenCalledWith("/login/");
  });
});
