import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";

beforeEach(() => {
  globalThis.fetch = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/healthz")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: "ok" }),
      }) as Promise<Response>;
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ authenticated: false, user: null }),
    }) as Promise<Response>;
  }) as unknown as typeof fetch;
});

test("renders the admin sign in screen", async () => {
  render(<App />);
  expect(await screen.findByText(/Control Tower/i)).toBeInTheDocument();
});
