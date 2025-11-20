from django.urls import path

from . import views
from .views import (
    CustomerListView,
    InvoiceListView,
    SuppliersView,
    ExpenseListView,
    ProductServiceListView,
    ItemCreateView,
    ItemUpdateView,
)
from .views_reports import pnl_ledger_debug
from .views_accounts import (
    account_detail_view,
    api_account_activity,
    api_account_ledger,
    api_account_toggle_favorite,
    api_account_manual_transaction,
)

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("business/setup/", views.business_setup, name="business_setup"),
    path("settings/account/", views.account_settings, name="account_settings"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # Customers
    path("customers/", CustomerListView.as_view(), name="customer_list"),
    path("customers/new/", views.customer_create, name="customer_create"),
    path("customers/<int:pk>/edit/", views.customer_update, name="customer_update"),
    path("customers/<int:pk>/delete/", views.customer_delete, name="customer_delete"),
    # Suppliers
    path("suppliers/", SuppliersView.as_view(), name="suppliers"),
    path("suppliers/new/", views.supplier_create, name="supplier_create"),
    path("suppliers/<int:pk>/edit/", views.supplier_update, name="supplier_update"),
    path("suppliers/<int:pk>/delete/", views.supplier_delete, name="supplier_delete"),
    # Categories
    path("categories/", views.category_list, name="category_list"),
    path("categories/new/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_update, name="category_update"),
    path("categories/<int:pk>/archive/", views.category_archive, name="category_archive"),
    path("categories/<int:pk>/restore/", views.category_restore, name="category_restore"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    # Invoices
    path("invoices/", InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/new/", views.invoice_create, name="invoice_create"),
    path("invoices/<int:pk>/edit/", views.invoice_update, name="invoice_update"),
    path("invoices/<int:pk>/delete/", views.invoice_delete, name="invoice_delete"),
    path("invoices/<int:pk>/status/", views.invoice_status_update, name="invoice_status_update"),
    # Expenses
    path("expenses/", ExpenseListView.as_view(), name="expense_list"),
    path("expenses/new/", views.expense_create, name="expense_create"),
    path("expenses/<int:pk>/edit/", views.expense_update, name="expense_update"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("expenses/<int:pk>/status/", views.expense_status_update, name="expense_status_update"),
    # Products & Services
    path("products/", ProductServiceListView.as_view(), name="product_list"),
    path("items/new/", ItemCreateView.as_view(), name="item_create"),
    path("items/<int:pk>/edit/", ItemUpdateView.as_view(), name="item_update"),
    # Reports
    path("profit-loss/", views.report_pnl, name="report_pnl"),
    path("reports/cashflow/", views.cashflow_report_view, name="cashflow_report"),
    path("reports/pl-shadow/", views.pl_shadow_view, name="pl_shadow"),
    path("reports/pl-export/", views.pl_export_csv, name="pl_export_csv"),
    path("bank-accounts/", views.bank_account_list, name="bank_account_list"),
    path("bank-accounts/new/", views.bank_account_create, name="bank_account_create"),
    path(
        "bank-accounts/<int:pk>/edit/",
        views.bank_account_edit,
        name="bank_account_edit",
    ),
    path("bank/import/", views.BankStatementImportView.as_view(), name="bank_import"),
    path(
        "bank-feeds/new/",
        views.BankStatementImportView.as_view(),
        name="bank_feed_import",
    ),
    path("bank-feeds/", views.bank_feeds_overview, name="bank_feeds_overview"),
    path(
        "bank-feeds/<int:bank_account_id>/review/",
        views.bank_feed_review,
        name="bank_feed_review",
    ),
    path(
        "bank-feeds/<int:bank_account_id>/tx/<int:tx_id>/match/",
        views.bank_feed_match_invoice,
        name="bank_feed_match_invoice",
    ),
    path(
        "bank-feeds/<int:bank_account_id>/tx/<int:tx_id>/match-expense/",
        views.bank_feed_match_expense,
        name="bank_feed_match_expense",
    ),
    path(
        "bank-feeds/<int:bank_account_id>/tx/<int:tx_id>/exclude/",
        views.bank_feed_exclude_tx,
        name="bank_feed_exclude_tx",
    ),
    path("bank-feed/react/", views.bank_feed_spa, name="bank_feed_spa"),
    path("banking/", views.banking_accounts_feed_spa, name="banking_accounts_feed"),
    path("api/banking/overview/", views.api_banking_overview, name="api_banking_overview"),
    path(
        "api/banking/feed/transactions/",
        views.api_banking_feed_transactions,
        name="api_banking_feed_transactions",
    ),
    path(
        "api/banking/feed/metadata/",
        views.api_banking_feed_metadata,
        name="api_banking_feed_metadata",
    ),
    path(
        "api/banking/feed/transactions/<int:tx_id>/create/",
        views.api_banking_feed_create_entry,
        name="api_banking_feed_create_entry",
    ),
    path(
        "api/banking/feed/transactions/<int:tx_id>/match-invoice/",
        views.api_banking_feed_match_invoice_api,
        name="api_banking_feed_match_invoice_api",
    ),
    path(
        "api/banking/feed/transactions/<int:tx_id>/match-expense/",
        views.api_banking_feed_match_expense_api,
        name="api_banking_feed_match_expense_api",
    ),
    path(
        "api/banking/feed/transactions/<int:tx_id>/exclude/",
        views.api_banking_feed_exclude,
        name="api_banking_feed_exclude",
    ),
    path(
        "api/banking/transactions/<int:bank_tx_id>/allocate/",
        views.api_allocate_bank_transaction,
        name="api_allocate_bank_transaction",
    ),
    path("accounts/", views.chart_of_accounts_spa, name="account_list"),
    path("accounts/<int:account_id>/", account_detail_view, name="account_detail"),
    path(
        "chart-of-accounts/<int:account_id>/",
        account_detail_view,
        name="coa_account_detail",
    ),
    path(
        "api/accounts/<int:account_id>/activity/",
        api_account_activity,
        name="api_account_activity",
    ),
    path(
        "api/accounts/<int:account_id>/ledger/",
        api_account_ledger,
        name="api_account_ledger",
    ),
    path(
        "api/accounts/<int:account_id>/toggle-favorite/",
        api_account_toggle_favorite,
        name="api_account_toggle_favorite",
    ),
    path(
        "api/accounts/<int:account_id>/manual-transaction/",
        api_account_manual_transaction,
        name="api_account_manual_transaction",
    ),
    path("reports/pnl-ledger-debug/", pnl_ledger_debug, name="pnl_ledger_debug"),
    path("journal/", views.journal_entries, name="journal_entries"),
]
