import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import CloverBooksDashboard from "./CloverBooksDashboard";

vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));
vi.mock("../companion/CompanionPanel", () => ({
  __esModule: true,
  default: () => <div data-testid="companion-panel" />,
}));

describe("CloverBooksDashboard P&L card", () => {
  it("shows explanatory message when there is no ledger activity in the period", () => {
    render(
      <CloverBooksDashboard
        metrics={{
          revenue_month: 0,
          expenses_month: 0,
          net_income_month: 0,
          pl_period_label: "This month",
          pl_prev_period_label: "Last month",
          pl_prev_income: 0,
          pl_prev_expenses: 0,
          pl_prev_net: 0,
          pl_debug: { no_ledger_activity_for_period: true },
        }}
      />
    );

    expect(screen.getAllByText(/No income or expenses have been posted/i).length).toBeGreaterThan(0);
  });

  it("renders P&L values and comparison when data exists", () => {
    render(
      <CloverBooksDashboard
        metrics={{
          revenue_month: 1200,
          expenses_month: 400,
          net_income_month: 800,
          pl_period_label: "This month (Dec 01–Dec 31)",
          pl_prev_period_label: "Last month",
          pl_prev_income: 900,
          pl_prev_expenses: 300,
          pl_prev_net: 600,
          pl_debug: { no_ledger_activity_for_period: false },
        }}
      />
    );

    expect(screen.queryByText(/No income or expenses have been posted/i)).not.toBeInTheDocument();
    expect(screen.getByText("This month (Dec 01–Dec 31)")).toBeInTheDocument();
    expect(screen.getByText(/vs Last month/i)).toBeInTheDocument();
    expect(screen.getByText(/Revenue \$1,200\.00/)).toBeInTheDocument();
    expect(screen.getByText(/Expenses \$400\.00/)).toBeInTheDocument();
  });
});
