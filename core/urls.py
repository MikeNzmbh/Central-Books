from django.urls import path

from . import views
from taxes import views as tax_views
from . import views_reconciliation
from . import views_monitoring  # Monitoring agent Slack endpoint
from . import views_auth  # Auth API endpoints
from .views import (
    CustomerListView,
    InvoiceListView,
    SuppliersView,
    ExpenseListView,
    ProductServiceListView,
    ItemCreateView,
    ItemUpdateView,
)
from .views_reports import (
    pnl_ledger_debug,
    reconciliation_report_view,
    cashflow_report_print_view,
    pl_report_print_view,
)
from .views_accounts import (
    account_detail_view,
    api_account_activity,
    api_account_ledger,
    api_account_toggle_favorite,
    api_account_manual_transaction,
)
from .views_reconciliation import reconcile_bank_account
from .views_reconciliation import (
    api_reconciliation_overview,
    api_reconciliation_transactions,
    api_reconciliation_matches,
    api_reconciliation_confirm_match,
    api_reconciliation_create_split,
    api_reconciliation_audit,
    api_reconciliation_create_rule,
    api_ledger_search,
)

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("business/setup/", views.business_setup, name="business_setup"),
    path("settings/account/", views.account_settings, name="account_settings"),
    path("dashboard/", views.dashboard, name="dashboard"),
    
    # Auth API
    path("api/auth/me", views_auth.current_user, name="api_current_user"),
    path("api/auth/login/", views_auth.api_login, name="api_auth_login"),
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
    path(
        "reconciliation/<int:session_id>/report/",
        reconciliation_report_view,
        name="reconciliation_report",
    ),
    path(
        "reports/cashflow/print/",
        cashflow_report_print_view,
        name="cashflow_report_print",
    ),
    path(
        "reports/pl/print/",
        pl_report_print_view,
        name="pl_report_print",
    ),
    path("reports/tax/gst-hst/", tax_views.gst_hst_report, name="gst_hst_report"),
    path("reports/tax/us-sales/", tax_views.us_sales_tax_report, name="us_sales_tax_report"),
    path("bank-accounts/", views.bank_account_list, name="bank_account_list"),
    path("bank-accounts/new/", views.bank_account_create, name="bank_account_create"),
    path(
        "bank-accounts/<int:pk>/edit/",
        views.bank_account_edit,
        name="bank_account_edit",
    ),
    path("bank-accounts/<int:pk>/reconcile/", reconcile_bank_account, name="reconcile_bank_account"),
    path("api/bank-accounts/<int:pk>/reconciliation/overview/", api_reconciliation_overview, name="api_reco_overview"),
    path("api/bank-accounts/<int:pk>/reconciliation/transactions/", api_reconciliation_transactions, name="api_reco_transactions"),
    path("api/reconciliation/matches/", api_reconciliation_matches, name="api_reco_matches"),
    path("api/reconciliation/confirm-match/", api_reconciliation_confirm_match, name="api_reco_confirm_match"),
    path("api/reconciliation/add-as-new/", views_reconciliation.api_reconciliation_add_as_new, name="api_reco_add_as_new"),
    path("api/reconciliation/create-split/", api_reconciliation_create_split, name="api_reco_create_split"),
    path("api/reconciliation/create-rule/", views_reconciliation.api_reconciliation_create_rule, name="api_reconciliation_create_rule"),
    path("api/reconciliation/config/", views_reconciliation.api_reconciliation_config, name="api_reconciliation_config"),
    path("api/reconciliation/periods/", views_reconciliation.api_reconciliation_periods, name="api_reconciliation_periods"),
    path("api/reconciliation/feed/", views_reconciliation.api_reconciliation_feed, name="api_reconciliation_feed"),
    path("api/reconciliation/session/", views_reconciliation.api_reconciliation_session_v1, name="api_reconciliation_session"),
    path("api/reconciliation/complete/", views_reconciliation.api_reconciliation_complete, name="api_reconciliation_complete"),
    path("api/reconciliation/toggle-include/", views_reconciliation.api_reconciliation_toggle_include, name="api_reconciliation_toggle_include"),
    path("api/reconciliation/create-adjustment/", views_reconciliation.api_reconciliation_create_adjustment, name="api_reconciliation_create_adjustment"),
    # Reconciliation v1 stable API
    path("api/reconciliation/accounts/", views_reconciliation.api_reconciliation_accounts_v1, name="api_reco_accounts_v1"),
    path(
        "api/reconciliation/accounts/<int:account_id>/periods/",
        views_reconciliation.api_reconciliation_periods_v1,
        name="api_reco_periods_v1",
    ),
    path("api/reconciliation/session/<int:session_id>/set_statement_balance/", views_reconciliation.api_reconciliation_set_statement_balance_v1, name="api_reco_set_statement_balance_v1"),
    path("api/reconciliation/session/<int:session_id>/match/", views_reconciliation.api_reconciliation_match_v1, name="api_reco_match_v1"),
    path("api/reconciliation/session/<int:session_id>/unmatch/", views_reconciliation.api_reconciliation_unmatch_v1, name="api_reco_unmatch_v1"),
    path("api/reconciliation/session/<int:session_id>/exclude/", views_reconciliation.api_reconciliation_exclude_v1, name="api_reco_exclude_v1"),
    path("api/reconciliation/session/<int:session_id>/complete/", views_reconciliation.api_reconciliation_complete_v1, name="api_reco_complete_v1"),
    path(
        "api/reconciliation/sessions/<int:session_id>/complete/",
        views_reconciliation.api_reconciliation_complete_v1,
        name="reconciliation-complete-session",
    ),
    path(
        "api/reconciliation/session/<int:session_id>/",
        views_reconciliation.api_reconciliation_session_report,
        name="api_reco_session_report",
    ),
    path("api/reconciliation/audit/", api_reconciliation_audit, name="api_reco_audit"),
    path("api/reconciliation/rules/", api_reconciliation_create_rule, name="api_reco_rule"),
    path("api/ledger/search/", api_ledger_search, name="api_ledger_search"),
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
    # Reconciliation
    path("reconciliation/", views.reconciliation_entry, name="reconciliation_entry"),
    path("reconciliation/<int:bank_account_id>/", views.reconciliation_page, name="reconciliation_page"),
    # Banking accounts feed
    path("banking/", views.banking_accounts_feed_spa, name="banking_accounts_feed"),
    path("bank/setup/", views.bank_setup_page, name="bank_setup"),
    path("api/bank/setup/save/", views.api_bank_setup_save, name="api_bank_setup_save"),
    path("api/bank/setup/skip/", views.api_bank_setup_skip, name="api_bank_setup_skip"),
    path("workspace/", views.workspace_home, name="workspace_home"),
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
    path("api/categories/", views.api_create_category, name="api_create_category"),
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
        "api/banking/feed/transactions/<int:tx_id>/add/",
        views.api_banking_feed_add_entry,
        name="api_banking_feed_add_entry",
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
    # Slack monitoring slash command endpoint
    path("slack/monitoring/report/", views_monitoring.slack_monitoring_report, name="slack_monitoring_report"),
]
