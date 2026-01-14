import React, { Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { CustomerLayout } from "./layouts/CustomerLayout";

import CloverBooksDashboard from "./dashboard/CloverBooksDashboard";
import { cashflowSample, profitAndLossSample } from "./reports/sampleData";
import CloverBooksLoginPage from "./auth/LoginPage";
import CloverBooksWelcomePage from "./auth/CloverBooksWelcomePage";
import CloverBooksCreateAccount from "./auth/CloverBooksCreateAccount";
import OAuthCallbackPage from "./auth/OAuthCallbackPage";

const LazyCompanionControlTowerPage = React.lazy(() => import("./companion/CompanionControlTowerPage"));
const LazyCompanionOverviewPage = React.lazy(() => import("./companion/CompanionOverviewPage"));
const LazyCompanionIssuesPage = React.lazy(() => import("./companion/CompanionIssuesPage"));
const LazyCompanionProposalsPage = React.lazy(() => import("./companion/CompanionProposalsPage"));
const LazyTaxGuardianPage = React.lazy(() => import("./companion/TaxGuardianPage"));
const LazyTaxCatalogPage = React.lazy(() => import("./companion/TaxCatalogPage"));
const LazyTaxProductRulesPage = React.lazy(() => import("./companion/TaxProductRulesPage"));
const LazyTaxSettingsPage = React.lazy(() => import("./companion/TaxSettingsPage"));
const LazyInvoicesPage = React.lazy(() => import("./invoices/InvoicesPage"));
const LazyInvoicesListPage = React.lazy(() => import("./invoices/InvoicesListPage"));
const LazyExpensesListPage = React.lazy(() => import("./expenses/ExpensesListPage"));
const LazyReceiptsPage = React.lazy(() => import("./receipts/ReceiptsPage"));
const LazyCustomersPage = React.lazy(() => import("./customers/CustomersPage"));
const LazySuppliersPage = React.lazy(() => import("./suppliers/SuppliersPage"));
const LazyProductsPage = React.lazy(() => import("./products/ProductsPage"));
const LazyCategoriesPage = React.lazy(() => import("./categories/CategoriesPage"));
const LazyInventoryOverviewPage = React.lazy(() => import("./inventory/InventoryOverviewPage"));
const LazyBankingAccountsAndFeedPage = React.lazy(() => import("./BankingAccountsAndFeedPage"));
const LazyBankSetupPage = React.lazy(() => import("./banking/BankSetupPage"));
const LazyReconciliationPage = React.lazy(() => import("./reconciliation/ReconciliationPage"));
const LazyReconciliationReportPage = React.lazy(() => import("./reconciliation/ReconciliationReportPage"));
const LazyProfitAndLossReportPage = React.lazy(() => import("./reports/ProfitAndLossReportPage"));
const LazyCashflowReportPage = React.lazy(() => import("./reports/CashflowReportPage"));
const LazyCashflowReportPrintPage = React.lazy(async () => {
  const module = await import("./reports/CashflowReportPrintPage");
  return { default: module.CashflowReportPrintPage };
});
const LazyChartOfAccountsPage = React.lazy(() => import("./ChartOfAccountsPage"));
const LazyJournalEntriesPage = React.lazy(() => import("./journal/JournalEntriesPage"));
const LazyTransactionsPage = React.lazy(() => import("./transactions/TransactionsPage"));
const LazyAccountSettingsPage = React.lazy(() => import("./settings/AccountSettingsPage"));
const LazyRolesSettingsPage = React.lazy(() => import("./settings/RolesSettingsPage"));
const LazyTeamManagement = React.lazy(() => import("./settings/TeamManagement"));
const LazyBankReviewPage = React.lazy(() => import("./bankReview/BankReviewPage"));
const LazyBooksReviewPage = React.lazy(() => import("./booksReview/BooksReviewPage"));
const LazyAgenticConsolePage = React.lazy(() => import("./agentic/AgenticConsolePage"));
const LazyReceiptsDemoPage = React.lazy(() => import("./agentic/ReceiptsDemoPage"));
const LazyOnboardingPage = React.lazy(() => import("./onboarding/OnboardingPage"));

const RouteFallback: React.FC = () => (
  <div className="min-h-screen flex items-center justify-center text-slate-600">
    Loading...
  </div>
);

const RequireAuth: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { auth } = useAuth();
  const location = useLocation();

  if (auth.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-600">
        Loading workspace…
      </div>
    );
  }

  if (!auth.authenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
};

const DashboardRoute: React.FC = () => {
  const { auth } = useAuth();
  const username = auth.user?.name || auth.user?.firstName || auth.user?.email || "there";
  return <CloverBooksDashboard username={username} />;
};

const CashflowReportRoute: React.FC = () => <LazyCashflowReportPage {...cashflowSample} />;
const CashflowReportPrintRoute: React.FC = () => <LazyCashflowReportPrintPage {...cashflowSample} />;
const ProfitAndLossReportRoute: React.FC = () => <LazyProfitAndLossReportPage {...profitAndLossSample} />;

// Mock data for Chart of Accounts page
const mockCOAPayload = {
  accounts: [
    { id: 1, code: "1000", name: "Cash", type: "ASSET" as const, detailType: "Cash and Cash Equivalents", isActive: true, balance: 45250.00, favorite: true },
    { id: 2, code: "1100", name: "Accounts Receivable", type: "ASSET" as const, detailType: "Accounts Receivable", isActive: true, balance: 12500.00, favorite: false },
    { id: 3, code: "1200", name: "Inventory", type: "ASSET" as const, detailType: "Inventory", isActive: true, balance: 8750.00, favorite: false },
    { id: 4, code: "2000", name: "Accounts Payable", type: "LIABILITY" as const, detailType: "Accounts Payable", isActive: true, balance: 5200.00, favorite: false },
    { id: 5, code: "2100", name: "Credit Card", type: "LIABILITY" as const, detailType: "Credit Card", isActive: true, balance: 1500.00, favorite: false },
    { id: 6, code: "3000", name: "Owner's Equity", type: "EQUITY" as const, detailType: "Owner's Equity", isActive: true, balance: 50000.00, favorite: false },
    { id: 7, code: "3100", name: "Retained Earnings", type: "EQUITY" as const, detailType: "Retained Earnings", isActive: true, balance: 8500.00, favorite: true },
    { id: 8, code: "4000", name: "Sales Revenue", type: "INCOME" as const, detailType: "Sales", isActive: true, balance: 125000.00, favorite: true },
    { id: 9, code: "4100", name: "Service Revenue", type: "INCOME" as const, detailType: "Service/Fee Income", isActive: true, balance: 35000.00, favorite: false },
    { id: 10, code: "5000", name: "Cost of Goods Sold", type: "EXPENSE" as const, detailType: "Cost of Goods Sold", isActive: true, balance: 62000.00, favorite: false },
    { id: 11, code: "6000", name: "Rent Expense", type: "EXPENSE" as const, detailType: "Rent or Lease", isActive: true, balance: 18000.00, favorite: false },
    { id: 12, code: "6100", name: "Utilities", type: "EXPENSE" as const, detailType: "Utilities", isActive: true, balance: 4200.00, favorite: false },
    { id: 13, code: "6200", name: "Salaries & Wages", type: "EXPENSE" as const, detailType: "Payroll Expenses", isActive: true, balance: 85000.00, favorite: true },
  ],
  currencyCode: "USD",
};
const ChartOfAccountsRoute: React.FC = () => (
  <LazyChartOfAccountsPage payload={mockCOAPayload} newAccountUrl="/chart-of-accounts/new" />
);

// Route wrappers for pages with required props
const InvoicesRoute: React.FC = () => <LazyInvoicesPage defaultCurrency="USD" />;

const BankingRoute: React.FC = () => (
  <LazyBankingAccountsAndFeedPage
    overviewUrl="/api/banking/overview/"
    feedUrl="/api/banking/feed/"
    importUrl="/banking/import"
  />
);

// Settings page with mock form data to prevent crashes
const mockFormField = (name: string, label: string, value = "") => ({
  name, id: name, label, value, errors: [], type: "text", required: false
});
const mockSettingsProps = {
  csrfToken: "",
  profileForm: { form_id: "profile", fields: [mockFormField("name", "Name")], hidden_fields: [], non_field_errors: [] },
  businessForm: { form_id: "business", fields: [mockFormField("business_name", "Business Name")], hidden_fields: [], non_field_errors: [] },
  passwordForm: { form_id: "password", fields: [], hidden_fields: [], non_field_errors: [] },
  sessions: { current_ip: "127.0.0.1", user_agent: "Browser" },
  postUrls: { profile: "/api/settings/profile/", business: "/api/settings/business/", password: "/api/settings/password/", logoutAll: "/api/auth/logout-all/" },
  messages: [],
};
const AccountSettingsRoute: React.FC = () => <LazyAccountSettingsPage {...mockSettingsProps} />;



export const AppRoutes: React.FC = () => (
  <Suspense fallback={<RouteFallback />}>
    <Routes>
      <Route path="/login" element={<CloverBooksLoginPage />} />
      <Route path="/welcome" element={<CloverBooksWelcomePage />} />
      <Route path="/signup" element={<CloverBooksCreateAccount />} />
      <Route path="/auth/callback" element={<OAuthCallbackPage />} />
      <Route
        path="/agentic/console"
        element={
          <RequireAuth>
            <LazyAgenticConsolePage />
          </RequireAuth>
        }
      />
      <Route
        path="/agentic/receipts-demo"
        element={
          <RequireAuth>
            <LazyReceiptsDemoPage />
          </RequireAuth>
        }
      />
      <Route
        path="/onboarding"
        element={
          <RequireAuth>
            <LazyOnboardingPage />
          </RequireAuth>
        }
      />

      <Route
        element={
          <RequireAuth>
            <CustomerLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardRoute />} />
        <Route path="/companion" element={<LazyCompanionControlTowerPage />} />
        <Route path="/companion/overview" element={<LazyCompanionOverviewPage />} />
        <Route path="/companion/issues" element={<LazyCompanionIssuesPage />} />
        <Route path="/companion/proposals" element={<LazyCompanionProposalsPage />} />
        <Route path="/companion/tax" element={<LazyTaxGuardianPage />} />
        <Route path="/companion/tax/catalog" element={<LazyTaxCatalogPage />} />
        <Route path="/companion/tax/product-rules" element={<LazyTaxProductRulesPage />} />
        <Route path="/companion/tax/settings" element={<LazyTaxSettingsPage />} />
        <Route path="/invoices" element={<InvoicesRoute />} />
        <Route path="/invoices/list" element={<LazyInvoicesListPage />} />
        <Route path="/expenses" element={<LazyExpensesListPage />} />
        <Route path="/receipts" element={<LazyReceiptsPage />} />
        <Route path="/customers" element={<LazyCustomersPage />} />
        <Route path="/suppliers" element={<LazySuppliersPage />} />
        <Route path="/products" element={<LazyProductsPage />} />
        <Route path="/categories" element={<LazyCategoriesPage />} />
        <Route path="/inventory" element={<LazyInventoryOverviewPage />} />
        <Route path="/banking" element={<BankingRoute />} />
        <Route path="/banking/setup" element={<LazyBankSetupPage />} />
        <Route path="/reconciliation" element={<LazyReconciliationPage />} />
        <Route path="/reconciliation/report" element={<LazyReconciliationReportPage />} />
        <Route path="/reports/pl" element={<ProfitAndLossReportRoute />} />
        <Route path="/reports/cashflow" element={<CashflowReportRoute />} />
        <Route path="/reports/cashflow/print" element={<CashflowReportPrintRoute />} />
        <Route path="/chart-of-accounts" element={<ChartOfAccountsRoute />} />
        <Route path="/journal" element={<LazyJournalEntriesPage />} />
        <Route path="/transactions" element={<LazyTransactionsPage />} />
        <Route path="/settings" element={<AccountSettingsRoute />} />
        <Route path="/settings/roles" element={<LazyRolesSettingsPage />} />
        <Route path="/settings/team" element={<LazyTeamManagement />} />
        <Route path="/bank-review" element={<LazyBankReviewPage />} />
        <Route path="/books-review" element={<LazyBooksReviewPage />} />
        <Route path="/help" element={<div className="p-6 text-slate-600">Help center coming soon.</div>} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  </Suspense>
);

const App: React.FC = () => (
  <AuthProvider>
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  </AuthProvider>
);

export default App;
