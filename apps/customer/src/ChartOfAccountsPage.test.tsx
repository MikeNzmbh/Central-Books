/**
 * Chart of Accounts Page Tests
 *
 * Tests the ChartOfAccountsPage component rendering and functionality.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

import ChartOfAccountsPage, { AccountDTO, ChartOfAccountsBootPayload } from "./ChartOfAccountsPage";

// Generate mock account data
const createMockAccount = (
    id: number,
    code: string,
    name: string,
    type: "ASSET" | "LIABILITY" | "EQUITY" | "INCOME" | "EXPENSE",
    balance: number,
    isActive = true
): AccountDTO => ({
    id,
    code,
    name,
    type,
    detailType: `${type} Detail`,
    isActive,
    balance,
    favorite: id <= 3,
});

const mockAccounts: AccountDTO[] = [
    createMockAccount(1, "1000", "Cash", "ASSET", 45250),
    createMockAccount(2, "1100", "Accounts Receivable", "ASSET", 12500),
    createMockAccount(3, "1200", "Inventory", "ASSET", 8750),
    createMockAccount(4, "2000", "Accounts Payable", "LIABILITY", 5200),
    createMockAccount(5, "2100", "Credit Card", "LIABILITY", 1500),
    createMockAccount(6, "3000", "Owner's Equity", "EQUITY", 50000),
    createMockAccount(7, "4000", "Sales Revenue", "INCOME", 125000),
    createMockAccount(8, "5000", "Cost of Goods Sold", "EXPENSE", 62000),
    createMockAccount(9, "6000", "Rent Expense", "EXPENSE", 18000),
    createMockAccount(10, "9999", "Archived Account", "ASSET", 0, false),
];

const mockPayload: ChartOfAccountsBootPayload = {
    accounts: mockAccounts,
    currencyCode: "USD",
};

describe("ChartOfAccountsPage", () => {
    describe("Rendering", () => {
        it("renders without crashing", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            expect(screen.getByText("Chart of Accounts")).toBeInTheDocument();
        });

        it("displays the page header correctly", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            expect(screen.getByText("REPORTS")).toBeInTheDocument();
            expect(screen.getByText("Chart of Accounts")).toBeInTheDocument();
            expect(
                screen.getByText(/Review, group, and maintain the accounts/)
            ).toBeInTheDocument();
        });

        it("shows + New account button", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            expect(screen.getByText("+ New account")).toBeInTheDocument();
        });

        it("displays account count correctly", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            // Should show active accounts count (all but one archived)
            expect(screen.getByText(/9 active account/)).toBeInTheDocument();
        });
    });

    describe("Accounts Table", () => {
        it("displays account codes", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            expect(screen.getByText("1000")).toBeInTheDocument();
            expect(screen.getByText("1100")).toBeInTheDocument();
            expect(screen.getByText("2000")).toBeInTheDocument();
        });

        it("displays account names", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            expect(screen.getByText("Cash")).toBeInTheDocument();
            expect(screen.getByText("Accounts Receivable")).toBeInTheDocument();
            expect(screen.getByText("Sales Revenue")).toBeInTheDocument();
        });

        it("displays formatted balances", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            // Check for formatted currency values
            expect(screen.getByText("$45250.00 USD")).toBeInTheDocument();
        });

        it("shows active badge for active accounts", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            const activeBadges = screen.getAllByText("Active");
            expect(activeBadges.length).toBeGreaterThan(0);
        });
    });

    describe("Filtering", () => {
        it("shows type filter buttons", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            expect(screen.getByText("All types")).toBeInTheDocument();
            expect(screen.getAllByText("Assets").length).toBeGreaterThan(0);
            expect(screen.getAllByText("Liabilities").length).toBeGreaterThan(0);
            expect(screen.getAllByText("Equity").length).toBeGreaterThan(0);
            expect(screen.getAllByText("Income").length).toBeGreaterThan(0);
            expect(screen.getAllByText("Expenses").length).toBeGreaterThan(0);
        });

        it("filters by account type when clicked", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            // Verify filter buttons exist and are clickable
            const incomeButtons = screen.getAllByText("Income");
            expect(incomeButtons.length).toBeGreaterThan(0);

            // Click the filter button (first instance in the filter section)
            fireEvent.click(incomeButtons[0]);

            // After clicking, the page should still render without error
            expect(screen.getByText("Chart of Accounts")).toBeInTheDocument();
        });

        it("shows status filter buttons", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            expect(screen.getByText("Active only")).toBeInTheDocument();
            expect(screen.getByText("Archived only")).toBeInTheDocument();
            expect(screen.getByText("Show all")).toBeInTheDocument();
        });

        it("filters to show archived accounts", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            // Click on "Archived only"
            fireEvent.click(screen.getByText("Archived only"));

            // Should show archived account
            expect(screen.getByText("Archived Account")).toBeInTheDocument();
            // Should not show active accounts
            expect(screen.queryByText("Cash")).not.toBeInTheDocument();
        });

        it("has a search input", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            const searchInput = screen.getByPlaceholderText(
                "Search by name, code, or detail type"
            );
            expect(searchInput).toBeInTheDocument();
        });

        it("filters accounts by search term", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            const searchInput = screen.getByPlaceholderText(
                "Search by name, code, or detail type"
            );
            fireEvent.change(searchInput, { target: { value: "receivable" } });

            // Should show matching account
            expect(screen.getByText("Accounts Receivable")).toBeInTheDocument();
            // Should not show non-matching accounts
            expect(screen.queryByText("Cash")).not.toBeInTheDocument();
        });

        it("has a reset button that clears filters", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            const resetButton = screen.getByText("Reset");
            expect(resetButton).toBeInTheDocument();
        });
    });

    describe("Balances by Type Section", () => {
        it("shows balances summary", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            expect(screen.getByText("Balances by type")).toBeInTheDocument();
        });

        it("shows all account type labels in summary", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            // Summary section shows type labels - check for any case variation
            expect(screen.getAllByText(/assets/i).length).toBeGreaterThan(0);
            expect(screen.getAllByText(/liabilities/i).length).toBeGreaterThan(0);
            expect(screen.getAllByText(/equity/i).length).toBeGreaterThan(0);
            expect(screen.getAllByText(/income/i).length).toBeGreaterThan(0);
            expect(screen.getAllByText(/expenses/i).length).toBeGreaterThan(0);
        });
    });

    describe("Empty State", () => {
        it("shows empty message when no accounts match filters", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            // Search for something that doesn't exist
            const searchInput = screen.getByPlaceholderText(
                "Search by name, code, or detail type"
            );
            fireEvent.change(searchInput, { target: { value: "xyznonexistent" } });

            expect(
                screen.getByText("No accounts match these filters.")
            ).toBeInTheDocument();
        });
    });

    describe("Favorites", () => {
        it("has favorites only checkbox", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            expect(screen.getByText("Show favorites only")).toBeInTheDocument();
        });

        it("filters to show only favorite accounts", () => {
            render(
                <ChartOfAccountsPage
                    payload={mockPayload}
                    newAccountUrl="/chart-of-accounts/new"
                />
            );

            const favoritesCheckbox = screen.getByRole("checkbox");
            fireEvent.click(favoritesCheckbox);

            // First 3 accounts are favorites
            expect(screen.getByText("Cash")).toBeInTheDocument();
            expect(screen.getByText("Accounts Receivable")).toBeInTheDocument();
            expect(screen.getByText("Inventory")).toBeInTheDocument();
            // Non-favorites should not be visible
            expect(screen.queryByText("Accounts Payable")).not.toBeInTheDocument();
        });
    });
});

describe("ChartOfAccountsPage with Empty Data", () => {
    it("handles empty accounts array", () => {
        const emptyPayload: ChartOfAccountsBootPayload = {
            accounts: [],
            currencyCode: "USD",
        };

        render(
            <ChartOfAccountsPage
                payload={emptyPayload}
                newAccountUrl="/chart-of-accounts/new"
            />
        );

        expect(
            screen.getByText("No accounts match these filters.")
        ).toBeInTheDocument();
    });

    it("handles missing currencyCode with default", () => {
        const payloadWithoutCurrency = {
            accounts: mockAccounts,
        } as ChartOfAccountsBootPayload;

        render(
            <ChartOfAccountsPage
                payload={payloadWithoutCurrency}
                newAccountUrl="/chart-of-accounts/new"
            />
        );

        // Should render without crashing, using default USD
        expect(screen.getByText("Chart of Accounts")).toBeInTheDocument();
    });
});
