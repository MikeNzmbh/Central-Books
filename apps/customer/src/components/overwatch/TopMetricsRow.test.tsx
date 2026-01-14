import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import TopMetricsRow from "./TopMetricsRow";
import * as metricsHook from "./useFinancialPulseMetrics";

vi.mock("./useFinancialPulseMetrics", () => ({
  useFinancialPulseMetrics: vi.fn(),
}));

const sampleMetrics: metricsHook.FinancialPulseMetrics = {
  cashOnHand: {
    amount: 235000,
    currency: "CAD",
    updatedAt: "2025-01-01T00:00:00Z",
    trendLast30d: "up",
    trendDelta: 8.2,
  },
  runway: {
    months: 4.2,
    burnRateMonthly: -42000,
    currency: "CAD",
    burnDirection: "decreasing",
  },
  next30Days: {
    incomingAR: 32100,
    outgoingAP: 22900,
    netCash: 9200,
    currency: "CAD",
  },
  taxGuardian: {
    periodLabel: "2025-12",
    netTaxDue: 14500,
    currency: "CAD",
    status: "attention",
    dueDate: "2099-01-30",
    openAnomalies: 2,
  },
};

describe("TopMetricsRow", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders all four hero cards", () => {
    vi.mocked(metricsHook.useFinancialPulseMetrics).mockReturnValue({
      data: sampleMetrics,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    const { container } = render(
      <MemoryRouter>
        <TopMetricsRow />
      </MemoryRouter>
    );

    expect(screen.getByText(/Cash on hand/i)).toBeInTheDocument();
    expect(screen.getByText(/Runway & Burn/i)).toBeInTheDocument();
    expect(screen.getByText(/Next 30 Days — In vs Out/i)).toBeInTheDocument();
    expect(screen.getByText(/Tax & Compliance/i)).toBeInTheDocument();

    expect(screen.getByText(/Low runway/i)).toBeInTheDocument();
    expect(screen.getByText(/2 anomalies need review/i)).toBeInTheDocument();

    expect(container).toMatchSnapshot();
  });

  it("shows loading skeletons", () => {
    vi.mocked(metricsHook.useFinancialPulseMetrics).mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    });

    render(
      <MemoryRouter>
        <TopMetricsRow />
      </MemoryRouter>
    );

    expect(screen.getByText(/Cash on hand/i)).toBeInTheDocument();
    expect(screen.queryByText(/Unable to load/i)).not.toBeInTheDocument();
  });

  it("shows inline errors and retries", () => {
    const refetch = vi.fn();
    vi.mocked(metricsHook.useFinancialPulseMetrics).mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error("boom"),
      refetch,
    });

    render(
      <MemoryRouter>
        <TopMetricsRow />
      </MemoryRouter>
    );

    expect(screen.getByText(/Unable to load cash balances/i)).toBeInTheDocument();

    const buttons = screen.getAllByRole("button", { name: /Try again/i });
    fireEvent.click(buttons[0]);
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

