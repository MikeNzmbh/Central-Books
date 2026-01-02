import React from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { CustomerLayout } from "./layouts/CustomerLayout";

import CloverBooksDashboard from "./dashboard/CloverBooksDashboard";
import CompanionControlTowerPage from "./companion/CompanionControlTowerPage";
import CompanionOverviewPage from "./companion/CompanionOverviewPage";
import CompanionIssuesPage from "./companion/CompanionIssuesPage";
import CompanionProposalsPage from "./companion/CompanionProposalsPage";
import TaxGuardianPage from "./companion/TaxGuardianPage";
import TaxCatalogPage from "./companion/TaxCatalogPage";
import TaxProductRulesPage from "./companion/TaxProductRulesPage";
import TaxSettingsPage from "./companion/TaxSettingsPage";
import InvoicesPage from "./invoices/InvoicesPage";
import InvoicesListPage from "./invoices/InvoicesListPage";
import ExpensesListPage from "./expenses/ExpensesListPage";
import ReceiptsPage from "./receipts/ReceiptsPage";
import CustomersPage from "./customers/CustomersPage";
import SuppliersPage from "./suppliers/SuppliersPage";
import ProductsPage from "./products/ProductsPage";
import CategoriesPage from "./categories/CategoriesPage";
import InventoryOverviewPage from "./inventory/InventoryOverviewPage";
import BankingAccountsAndFeedPage from "./BankingAccountsAndFeedPage";
import BankSetupPage from "./banking/BankSetupPage";
import ReconciliationPage from "./reconciliation/ReconciliationPage";
import ReconciliationReportPage from "./reconciliation/ReconciliationReportPage";
import ProfitAndLossReportPage from "./reports/ProfitAndLossReportPage";
import CashflowReportPage from "./reports/CashflowReportPage";
import { CashflowReportPrintPage } from "./reports/CashflowReportPrintPage";
import { cashflowSample, profitAndLossSample } from "./reports/sampleData";
import ChartOfAccountsPage from "./ChartOfAccountsPage";
import JournalEntriesPage from "./journal/JournalEntriesPage";
import TransactionsPage from "./transactions/TransactionsPage";
import AccountSettingsPage from "./settings/AccountSettingsPage";
import RolesSettingsPage from "./settings/RolesSettingsPage";
import TeamManagement from "./settings/TeamManagement";
import BankReviewPage from "./bankReview/BankReviewPage";
import BooksReviewPage from "./booksReview/BooksReviewPage";
import CloverBooksLoginPage from "./auth/LoginPage";
import CloverBooksWelcomePage from "./auth/CloverBooksWelcomePage";
import CloverBooksCreateAccount from "./auth/CloverBooksCreateAccount";
import AgenticConsolePage from "./agentic/AgenticConsolePage";
import ReceiptsDemoPage from "./agentic/ReceiptsDemoPage";

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

const CashflowReportRoute: React.FC = () => <CashflowReportPage {...cashflowSample} />;
const CashflowReportPrintRoute: React.FC = () => <CashflowReportPrintPage {...cashflowSample} />;
const ProfitAndLossReportRoute: React.FC = () => <ProfitAndLossReportPage {...profitAndLossSample} />;

const AppRoutes: React.FC = () => (
  <Routes>
    <Route path="/login" element={<CloverBooksLoginPage />} />
    <Route path="/welcome" element={<CloverBooksWelcomePage />} />
    <Route path="/signup" element={<CloverBooksCreateAccount />} />
    <Route
      path="/agentic/console"
      element={
        <RequireAuth>
          <AgenticConsolePage />
        </RequireAuth>
      }
    />
    <Route
      path="/agentic/receipts-demo"
      element={
        <RequireAuth>
          <ReceiptsDemoPage />
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
      <Route path="/companion" element={<CompanionControlTowerPage />} />
      <Route path="/companion/overview" element={<CompanionOverviewPage />} />
      <Route path="/companion/issues" element={<CompanionIssuesPage />} />
      <Route path="/companion/proposals" element={<CompanionProposalsPage />} />
      <Route path="/companion/tax" element={<TaxGuardianPage />} />
      <Route path="/companion/tax/catalog" element={<TaxCatalogPage />} />
      <Route path="/companion/tax/product-rules" element={<TaxProductRulesPage />} />
      <Route path="/companion/tax/settings" element={<TaxSettingsPage />} />
      <Route path="/invoices" element={<InvoicesPage />} />
      <Route path="/invoices/list" element={<InvoicesListPage />} />
      <Route path="/expenses" element={<ExpensesListPage />} />
      <Route path="/receipts" element={<ReceiptsPage />} />
      <Route path="/customers" element={<CustomersPage />} />
      <Route path="/suppliers" element={<SuppliersPage />} />
      <Route path="/products" element={<ProductsPage />} />
      <Route path="/categories" element={<CategoriesPage />} />
      <Route path="/inventory" element={<InventoryOverviewPage />} />
      <Route path="/banking" element={<BankingAccountsAndFeedPage />} />
      <Route path="/banking/setup" element={<BankSetupPage />} />
      <Route path="/reconciliation" element={<ReconciliationPage />} />
      <Route path="/reconciliation/report" element={<ReconciliationReportPage />} />
      <Route path="/reports/pl" element={<ProfitAndLossReportRoute />} />
      <Route path="/reports/cashflow" element={<CashflowReportRoute />} />
      <Route path="/reports/cashflow/print" element={<CashflowReportPrintRoute />} />
      <Route path="/chart-of-accounts" element={<ChartOfAccountsPage />} />
      <Route path="/journal" element={<JournalEntriesPage />} />
      <Route path="/transactions" element={<TransactionsPage />} />
      <Route path="/settings" element={<AccountSettingsPage />} />
      <Route path="/settings/roles" element={<RolesSettingsPage />} />
      <Route path="/settings/team" element={<TeamManagement />} />
      <Route path="/bank-review" element={<BankReviewPage />} />
      <Route path="/books-review" element={<BooksReviewPage />} />
      <Route path="/help" element={<div className="p-6 text-slate-600">Help center coming soon.</div>} />
    </Route>
    <Route path="*" element={<Navigate to="/dashboard" replace />} />
  </Routes>
);

const App: React.FC = () => (
  <AuthProvider>
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  </AuthProvider>
);

export default App;
