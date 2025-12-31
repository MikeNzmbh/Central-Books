import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";

beforeEach(() => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ authenticated: false, user: null }),
    }) as Promise<Response>
  ) as unknown as typeof fetch;
});

test("renders the admin sign in screen", async () => {
  render(<App />);
  expect(await screen.findByText(/Admin sign in/i)).toBeInTheDocument();
});
