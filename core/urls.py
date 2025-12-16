from django.urls import path, include
from django.views.generic import RedirectView

from . import views
from agentic.interfaces.api import urlpatterns as agentic_urlpatterns
from taxes import views as tax_views
from . import views_reconciliation
from . import views_receipts, views_invoices, views_books_review, views_bank_review, views_companion
from . import views_bank_audit  # Bank Audit Health Check API (Option B)
from . import views_dashboard  # Dashboard API (Option B architecture)
from . import views_monitoring  # Monitoring agent Slack endpoint
from . import views_auth  # Auth API endpoints
from . import views_list_apis  # Invoice/Expense list APIs (Option B)
from . import views_memberships  # RBAC Membership Management API
from . import views_roles  # RBAC v2 Role Settings API
from .views import (
    ItemCreateView,
    ItemUpdateView,
)
from .views_receipts import api_receipts_run, api_receipts_runs, api_receipts_run_detail, api_receipt_detail, api_receipt_approve, api_receipt_discard
from .views_invoices import (
    api_invoices_run,
    api_invoices_runs,
    api_invoices_run_detail,
    api_invoice_detail,
    api_invoice_approve,
    api_invoice_discard,
)
from .views_books_review import api_books_review_run, api_books_review_runs, api_books_review_run_detail
from .views_bank_review import api_bank_review_run, api_bank_review_runs, api_bank_review_run_detail
from .views_companion import api_companion_summary, companion_overview_page
from . import views_tax_guardian, views_tax_settings
from . import views_tax_product_rules
from . import views_tax_catalog
from . import views_tax_import
from . import views_tax_documents
from .views_reports import (
    pnl_ledger_debug,
    reconciliation_report_view,
    cashflow_report_print_view,
    pl_report_print_view,
    pl_report_api,
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
    path("companion/", RedirectView.as_view(pattern_name="companion_overview_page", permanent=False)),
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("business/setup/", views.business_setup, name="business_setup"),
    # Backwards-compatible route (older frontend link)
    path(
        "account/settings/",
        RedirectView.as_view(pattern_name="account_settings", permanent=False),
        name="account_settings_legacy",
    ),
    path("settings/account/", views.account_settings, name="account_settings"),
    path("dashboard/", views.dashboard, name="dashboard"),
    
    # Dashboard API (Option B architecture)
    path("api/dashboard/", views_dashboard.api_dashboard, name="api_dashboard"),
    
    # Auth API
    path("api/auth/me", views_auth.current_user, name="api_current_user"),
    path("api/auth/login/", views_auth.api_login, name="api_auth_login"),
    path("api/auth/config", views_auth.api_auth_config, name="api_auth_config"),
    path("api/reversals/", include("reversals.urls")),
    # Customers (Option B - React)
    path("customers/", views_list_apis.customers_list_page, name="customer_list"),
    path("customers/new/", views.customer_create, name="customer_create"),
    path("customers/<int:pk>/edit/", views.customer_update, name="customer_update"),
    path("customers/<int:pk>/delete/", views.customer_delete, name="customer_delete"),
    # Customer List API (Option B)
    path("api/customers/list/", views_list_apis.api_customer_list, name="api_customer_list"),
    # Suppliers (Option B - React)
    path("suppliers/", views_list_apis.suppliers_list_page, name="suppliers"),
    path("suppliers/new/", views.supplier_create, name="supplier_create"),
    path("suppliers/<int:pk>/edit/", views.supplier_update, name="supplier_update"),
    path("suppliers/<int:pk>/delete/", views.supplier_delete, name="supplier_delete"),
    # Supplier List API (Option B)
    path("api/suppliers/list/", views_list_apis.api_supplier_list, name="api_supplier_list"),
    # Categories (Option B - React)
    path("categories/", views_list_apis.categories_list_page, name="category_list"),
    path("categories/new/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_update, name="category_update"),
    path("categories/<int:pk>/archive/", views.category_archive, name="category_archive"),
    path("categories/<int:pk>/restore/", views.category_restore, name="category_restore"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    # Category List API (Option B)
    path("api/categories/list/", views_list_apis.api_category_list, name="api_category_list"),
    # Invoices (Option B - React)
    path("invoices/", views_list_apis.invoices_list_page, name="invoice_list"),
    path("invoices/new/", views.invoice_create, name="invoice_create"),
    path("invoices/<int:pk>/edit/", views.invoice_update, name="invoice_update"),
    path("invoices/<int:pk>/delete/", views.invoice_delete, name="invoice_delete"),
    path("invoices/<int:pk>/status/", views.invoice_status_update, name="invoice_status_update"),
    path("invoices/<int:pk>/pdf/", views.invoice_pdf_view, name="invoice_pdf"),
    path("invoices/public/<uuid:token>/", views.invoice_public_view, name="invoice_public_view"),
    path("invoices/email/open/<uuid:token>.gif", views.invoice_email_open_view, name="invoice_email_open"),
    # Invoice List API (Option B)
    path("api/invoices/list/", views_list_apis.api_invoice_list, name="api_invoice_list"),
    # Expenses (Option B - React)
    path("expenses/", views_list_apis.expenses_list_page, name="expense_list"),
    path("expenses/new/", views.expense_create, name="expense_create"),
    path("expenses/<int:pk>/edit/", views.expense_update, name="expense_update"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("expenses/<int:pk>/status/", views.expense_status_update, name="expense_status_update"),
    path("expenses/<int:pk>/pdf/", views.expense_pdf_view, name="expense_pdf"),
    # Expense List API (Option B)
    path("api/expenses/list/", views_list_apis.api_expense_list, name="api_expense_list"),
    path("api/expenses/<int:expense_id>/", views_list_apis.api_expense_detail, name="api_expense_detail"),
    path("api/expenses/<int:expense_id>/pay/", views_list_apis.api_expense_pay, name="api_expense_pay"),
    # React List Pages (backwards-compatible redirects to main routes)
    path("invoices/react/", RedirectView.as_view(pattern_name="invoice_list", permanent=False)),
    path("expenses/react/", RedirectView.as_view(pattern_name="expense_list", permanent=False)),
    # Unified Transactions Page (new combined invoice/expense view)
    path("transactions/", views_list_apis.transactions_page, name="transactions"),
    # Products & Services (Option B - React)
    path("products/", views_list_apis.products_list_page, name="product_list"),
    # Product List API (Option B)
    path("api/products/list/", views_list_apis.api_product_list, name="api_product_list"),
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
    path(
        "api/reports/pl/",
        pl_report_api,
        name="pl_report_api",
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
        "api/reconciliation/sessions/<int:session_id>/reopen/",
        views_reconciliation.api_reconciliation_reopen_session,
        name="reconciliation-reopen-session",
    ),
    path(
        "api/reconciliation/sessions/<int:session_id>/delete/",
        views_reconciliation.api_reconciliation_delete_session,
        name="reconciliation-delete-session",
    ),
    path(
        "api/reconciliation/session/<int:session_id>/",
        views_reconciliation.api_reconciliation_session_report,
        name="api_reco_session_report",
    ),
    path("api/reconciliation/audit/", api_reconciliation_audit, name="api_reco_audit"),
    path("api/reconciliation/rules/", api_reconciliation_create_rule, name="api_reco_rule"),
    path("api/ledger/search/", api_ledger_search, name="api_ledger_search"),
    path("api/invoices/<int:pk>/send_email/", views.invoice_send_email_view, name="invoice_send_email"),
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
    path("api/taxes/settings/", views.api_tax_settings, name="api_tax_settings"),
    path("api/taxes/rates/", views.api_tax_rates, name="api_tax_rates"),
    path(
        "api/taxes/rates/<int:rate_id>/",
        views.api_tax_rate_detail,
        name="api_tax_rate_detail",
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
    # Receipt uploader / agentic receipts
    path("api/agentic/receipts/run", views_receipts.api_receipts_run, name="api_receipts_run"),
    path("api/agentic/receipts/runs", views_receipts.api_receipts_runs, name="api_receipts_runs"),
    path("api/agentic/receipts/run/<int:run_id>", views_receipts.api_receipts_run_detail, name="api_receipts_run_detail"),
    path("api/agentic/receipts/<int:receipt_id>", views_receipts.api_receipt_detail, name="api_receipt_detail"),
    path("api/agentic/receipts/<int:receipt_id>/approve", views_receipts.api_receipt_approve, name="api_receipt_approve"),
    path("api/agentic/receipts/<int:receipt_id>/discard", views_receipts.api_receipt_discard, name="api_receipt_discard"),
    path("receipts/", views_receipts.receipts_page, name="receipts_page"),
    # Invoice uploader / agentic invoices
    path("api/agentic/invoices/run", views_invoices.api_invoices_run, name="api_invoices_run"),
    path("api/agentic/invoices/runs", views_invoices.api_invoices_runs, name="api_invoices_runs"),
    path("api/agentic/invoices/run/<int:run_id>", views_invoices.api_invoices_run_detail, name="api_invoices_run_detail"),
    path("api/agentic/invoices/<int:invoice_id>", views_invoices.api_invoice_detail, name="api_invoice_detail"),
    path("api/agentic/invoices/<int:invoice_id>/approve", views_invoices.api_invoice_approve, name="api_invoice_approve"),
    path("api/agentic/invoices/<int:invoice_id>/discard", views_invoices.api_invoice_discard, name="api_invoice_discard"),
    path("invoices/ai/", views_invoices.invoices_page, name="invoices_ai_page"),
    # Books review companion
    path("api/agentic/books-review/run", views_books_review.api_books_review_run, name="api_books_review_run"),
    path("api/agentic/books-review/runs", views_books_review.api_books_review_runs, name="api_books_review_runs"),
    path("api/agentic/books-review/run/<int:run_id>", views_books_review.api_books_review_run_detail, name="api_books_review_run_detail"),
    path("books-review/", views_books_review.books_review_page, name="books_review_page"),
    # Bank review companion
    path("api/agentic/bank-review/run", views_bank_review.api_bank_review_run, name="api_bank_review_run"),
    path("api/agentic/bank-review/runs", views_bank_review.api_bank_review_runs, name="api_bank_review_runs"),
    path("api/agentic/bank-review/run/<int:run_id>", views_bank_review.api_bank_review_run_detail, name="api_bank_review_run_detail"),
    path("bank-review/", views_bank_review.bank_review_page, name="bank_review_page"),
    # Bank Audit Health Check API (Option B)
    path("api/agentic/bank-audit/summary", views_bank_audit.api_bank_audit_summary, name="api_bank_audit_summary"),
    path("api/agentic/companion/summary", views_companion.api_companion_summary, name="api_companion_summary"),
    path("api/agentic/companion/issues", views_companion.api_companion_issues, name="api_companion_issues"),
    path("api/agentic/companion/issues/<int:issue_id>", views_companion.api_companion_issue_patch, name="api_companion_issue_patch"),
    path("api/agentic/companion/story/refresh", views_companion.api_companion_story_refresh, name="api_companion_story_refresh"),
    # Tax Guardian APIs (deterministic)
    path("api/tax/periods/", views_tax_guardian.api_tax_periods, name="api_tax_periods"),
    path("api/tax/periods/<str:period_key>/", views_tax_guardian.api_tax_period_detail, name="api_tax_period_detail"),
    path("api/tax/periods/<str:period_key>/anomalies/", views_tax_guardian.api_tax_period_anomalies, name="api_tax_period_anomalies"),
    path("api/tax/periods/<str:period_key>/anomalies/<uuid:anomaly_id>/", views_tax_guardian.api_tax_anomaly_update, name="api_tax_anomaly_update"),
    path("api/tax/periods/<str:period_key>/refresh/", views_tax_guardian.api_tax_period_refresh, name="api_tax_period_refresh"),
    path("api/tax/periods/<str:period_key>/llm-enrich/", views_tax_guardian.api_tax_period_llm_enrich, name="api_tax_period_llm_enrich"),
    path("api/tax/periods/<str:period_key>/status/", views_tax_guardian.api_tax_period_status, name="api_tax_period_status"),
    path("api/tax/periods/<str:period_key>/reset/", views_tax_guardian.api_tax_period_reset, name="api_tax_period_reset"),
    path("api/tax/periods/<str:period_key>/payments/", views_tax_guardian.api_tax_period_payments, name="api_tax_period_payments"),
    path("api/tax/periods/<str:period_key>/payments/<uuid:payment_id>/", views_tax_guardian.api_tax_period_payment_detail, name="api_tax_period_payment_detail"),
    path("api/tax/periods/<str:period_key>/export.json", views_tax_guardian.api_tax_export_json, name="api_tax_export_json"),
    path("api/tax/periods/<str:period_key>/export.csv", views_tax_guardian.api_tax_export_csv, name="api_tax_export_csv"),
    path("api/tax/periods/<str:period_key>/export-ser.csv", views_tax_guardian.api_tax_export_ser_csv, name="api_tax_export_ser_csv"),
    path("api/tax/periods/<str:period_key>/anomalies/export.csv", views_tax_guardian.api_tax_anomalies_export_csv, name="api_tax_anomalies_export_csv"),
    path("api/tax/settings/", views_tax_settings.api_tax_settings, name="api_tax_settings"),
    path("api/tax/product-rules/", views_tax_product_rules.api_tax_product_rules, name="api_tax_product_rules"),
    path("api/tax/product-rules/<uuid:rule_id>/", views_tax_product_rules.api_tax_product_rule_detail, name="api_tax_product_rule_detail"),
    # Tax Catalog APIs (staff/admin tooling)
    path("api/tax/catalog/groups/", views_tax_catalog.api_tax_catalog_groups, name="api_tax_catalog_groups"),
    path(
        "api/tax/catalog/groups/<uuid:group_id>/",
        views_tax_catalog.api_tax_catalog_group_detail,
        name="api_tax_catalog_group_detail",
    ),
    path("api/tax/catalog/jurisdictions/", views_tax_catalog.api_tax_catalog_jurisdictions, name="api_tax_catalog_jurisdictions"),
    path(
        "api/tax/catalog/jurisdictions/<str:code>/",
        views_tax_catalog.api_tax_catalog_jurisdiction_detail,
        name="api_tax_catalog_jurisdiction_detail",
    ),
    path("api/tax/catalog/rates/", views_tax_catalog.api_tax_catalog_rates, name="api_tax_catalog_rates"),
    path(
        "api/tax/catalog/rates/<uuid:rate_id>/",
        views_tax_catalog.api_tax_catalog_rate_detail,
        name="api_tax_catalog_rate_detail",
    ),
    path("api/tax/catalog/product-rules/", views_tax_catalog.api_tax_catalog_product_rules, name="api_tax_catalog_product_rules"),
    path(
        "api/tax/catalog/product-rules/<uuid:rule_id>/",
        views_tax_catalog.api_tax_catalog_product_rule_detail,
        name="api_tax_catalog_product_rule_detail",
    ),
    # Tax Catalog Import APIs (staff/admin tooling)
    path("api/tax/catalog/import/preview/", views_tax_import.api_tax_catalog_import_preview, name="api_tax_catalog_import_preview"),
    path("api/tax/catalog/import/apply/", views_tax_import.api_tax_catalog_import_apply, name="api_tax_catalog_import_apply"),
    # Tax document drilldown APIs (deterministic)
    path("api/tax/document/invoice/<int:invoice_id>/", views_tax_documents.api_tax_document_invoice, name="api_tax_document_invoice"),
    path("api/tax/document/expense/<int:expense_id>/", views_tax_documents.api_tax_document_expense, name="api_tax_document_expense"),
    path("ai-companion/", companion_overview_page, name="companion_overview_page"),
    path("ai-companion/issues", views_companion.companion_issues_page, name="companion_issues_page"),
    path("ai-companion/issues/", views_companion.companion_issues_page, name="companion_issues_page_slash"),
    # React router deep-link support for /ai-companion/* (e.g., /ai-companion/tax)
    path("ai-companion/<path:rest>", companion_overview_page, name="companion_overview_page_catchall"),
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
    # Journal Entries (Option B - React)
    path("journal/", views_list_apis.journal_entries_list_page, name="journal_entries"),
    # Journal Entries API (Option B)
    path("api/journal/list/", views_list_apis.api_journal_entry_list, name="api_journal_entry_list"),
    # Slack monitoring slash command endpoint
    path("slack/monitoring/report/", views_monitoring.slack_monitoring_report, name="slack_monitoring_report"),
    # RBAC Workspace Membership API (v1)
    path("api/workspace/memberships/", views_memberships.api_memberships_list, name="api_memberships_list"),
    path("api/workspace/memberships/create/", views_memberships.api_memberships_create, name="api_memberships_create"),
    path("api/workspace/memberships/<int:membership_id>/", views_memberships.api_membership_detail, name="api_membership_detail"),
    path("api/workspace/roles/", views_memberships.api_roles_list, name="api_roles_list"),
    # RBAC v2 Settings API
    path("api/settings/roles/", views_roles.api_roles_collection, name="api_settings_roles"),
    path("api/settings/roles/<int:role_id>/", views_roles.api_role_resource, name="api_settings_role"),
    path("api/settings/users/", views_roles.api_settings_users_list, name="api_settings_users"),
    path(
        "api/settings/users/<int:user_id>/membership/",
        views_roles.api_settings_user_membership_update,
        name="api_settings_user_membership_update",
    ),
]

# Add agentic API endpoints
urlpatterns += agentic_urlpatterns
