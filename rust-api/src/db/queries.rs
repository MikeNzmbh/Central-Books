// Database queries for core models
// These functions query the existing SQLite database
#![allow(dead_code)]

use sqlx::SqlitePool;
use super::models::*;

// =============================================================================
// Business Queries
// =============================================================================

pub async fn get_business_by_id(pool: &SqlitePool, id: i64) -> Result<Option<Business>, sqlx::Error> {
    sqlx::query_as::<_, Business>(
        "SELECT id, name, currency, fiscal_year_start, owner_user_id, plan, status, 
                is_deleted, created_at, bank_setup_completed, is_tax_registered, 
                tax_country, tax_region, ai_companion_enabled
         FROM core_business WHERE id = ?"
    )
    .bind(id)
    .fetch_optional(pool)
    .await
}

pub async fn get_business_by_owner(pool: &SqlitePool, user_id: i64) -> Result<Option<Business>, sqlx::Error> {
    sqlx::query_as::<_, Business>(
        "SELECT id, name, currency, fiscal_year_start, owner_user_id, plan, status, 
                is_deleted, created_at, bank_setup_completed, is_tax_registered, 
                tax_country, tax_region, ai_companion_enabled
         FROM core_business WHERE owner_user_id = ? AND is_deleted = 0"
    )
    .bind(user_id)
    .fetch_optional(pool)
    .await
}

// =============================================================================
// User Queries
// =============================================================================

pub async fn get_user_by_id(pool: &SqlitePool, id: i64) -> Result<Option<User>, sqlx::Error> {
    sqlx::query_as::<_, User>(
        "SELECT id, username, email, first_name, last_name, is_active, is_staff, date_joined
         FROM auth_user WHERE id = ?"
    )
    .bind(id)
    .fetch_optional(pool)
    .await
}

pub async fn get_user_by_email(pool: &SqlitePool, email: &str) -> Result<Option<User>, sqlx::Error> {
    sqlx::query_as::<_, User>(
        "SELECT id, username, email, first_name, last_name, is_active, is_staff, date_joined
         FROM auth_user WHERE email = ?"
    )
    .bind(email)
    .fetch_optional(pool)
    .await
}

pub async fn get_user_by_username(pool: &SqlitePool, username: &str) -> Result<Option<User>, sqlx::Error> {
    sqlx::query_as::<_, User>(
        "SELECT id, username, email, first_name, last_name, is_active, is_staff, date_joined
         FROM auth_user WHERE username = ?"
    )
    .bind(username)
    .fetch_optional(pool)
    .await
}

// =============================================================================
// Account Queries
// =============================================================================

pub async fn get_accounts_by_business(pool: &SqlitePool, business_id: i64) -> Result<Vec<Account>, sqlx::Error> {
    sqlx::query_as::<_, Account>(
        "SELECT id, business_id, code, name, type as account_type, parent_id, 
                is_active, description, is_favorite, is_suspense
         FROM core_account WHERE business_id = ? ORDER BY type, code, name"
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
}

pub async fn get_account_by_id(pool: &SqlitePool, id: i64) -> Result<Option<Account>, sqlx::Error> {
    sqlx::query_as::<_, Account>(
        "SELECT id, business_id, code, name, type as account_type, parent_id, 
                is_active, description, is_favorite, is_suspense
         FROM core_account WHERE id = ?"
    )
    .bind(id)
    .fetch_optional(pool)
    .await
}

// =============================================================================
// Customer Queries
// =============================================================================

pub async fn get_customers_by_business(pool: &SqlitePool, business_id: i64) -> Result<Vec<Customer>, sqlx::Error> {
    sqlx::query_as::<_, Customer>(
        "SELECT id, business_id, name, email, phone, is_active, created_at
         FROM core_customer WHERE business_id = ? ORDER BY name"
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
}

// =============================================================================
// Supplier Queries
// =============================================================================

pub async fn get_suppliers_by_business(pool: &SqlitePool, business_id: i64) -> Result<Vec<Supplier>, sqlx::Error> {
    sqlx::query_as::<_, Supplier>(
        "SELECT id, business_id, name, email, phone, created_at
         FROM core_supplier WHERE business_id = ? ORDER BY name"
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
}

// =============================================================================
// Invoice Queries
// =============================================================================

pub async fn get_invoices_by_business(pool: &SqlitePool, business_id: i64) -> Result<Vec<Invoice>, sqlx::Error> {
    sqlx::query_as::<_, Invoice>(
        "SELECT id, business_id, customer_id, invoice_number, issue_date, due_date,
                status, description, total_amount, subtotal, tax_amount,
                net_total, tax_total, grand_total, amount_paid, balance, created_at
         FROM core_invoice WHERE business_id = ? ORDER BY issue_date DESC"
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
}

pub async fn get_invoice_by_id(pool: &SqlitePool, id: i64) -> Result<Option<Invoice>, sqlx::Error> {
    sqlx::query_as::<_, Invoice>(
        "SELECT id, business_id, customer_id, invoice_number, issue_date, due_date,
                status, description, total_amount, subtotal, tax_amount,
                net_total, tax_total, grand_total, amount_paid, balance, created_at
         FROM core_invoice WHERE id = ?"
    )
    .bind(id)
    .fetch_optional(pool)
    .await
}

// =============================================================================
// Expense Queries
// =============================================================================

pub async fn get_expenses_by_business(pool: &SqlitePool, business_id: i64) -> Result<Vec<Expense>, sqlx::Error> {
    sqlx::query_as::<_, Expense>(
        "SELECT id, business_id, supplier_id, category_id, date, description, amount,
                status, paid_date, net_total, tax_total, grand_total, amount_paid, balance, created_at
         FROM core_expense WHERE business_id = ? ORDER BY date DESC"
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
}

// =============================================================================
// Bank Account Queries
// =============================================================================

pub async fn get_bank_accounts_by_business(pool: &SqlitePool, business_id: i64) -> Result<Vec<BankAccount>, sqlx::Error> {
    sqlx::query_as::<_, BankAccount>(
        "SELECT id, business_id, name, bank_name, account_number_mask, usage_role,
                account_id, is_active, last_imported_at, created_at
         FROM core_bankaccount WHERE business_id = ? ORDER BY name"
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
}

// =============================================================================
// Bank Transaction Queries
// =============================================================================

pub async fn get_bank_transactions_by_account(
    pool: &SqlitePool, 
    bank_account_id: i64,
    limit: i64,
) -> Result<Vec<BankTransaction>, sqlx::Error> {
    sqlx::query_as::<_, BankTransaction>(
        "SELECT id, bank_account_id, date, description, amount, allocated_amount,
                external_id, normalized_hash, status, suggestion_confidence, suggestion_reason,
                category_id, customer_id, supplier_id, matched_invoice_id, matched_expense_id,
                is_reconciled, reconciliation_status
         FROM core_banktransaction WHERE bank_account_id = ? ORDER BY date DESC LIMIT ?"
    )
    .bind(bank_account_id)
    .bind(limit)
    .fetch_all(pool)
    .await
}

pub async fn get_unreconciled_transactions(
    pool: &SqlitePool, 
    bank_account_id: i64,
) -> Result<Vec<BankTransaction>, sqlx::Error> {
    sqlx::query_as::<_, BankTransaction>(
        "SELECT id, bank_account_id, date, description, amount, allocated_amount,
                external_id, normalized_hash, status, suggestion_confidence, suggestion_reason,
                category_id, customer_id, supplier_id, matched_invoice_id, matched_expense_id,
                is_reconciled, reconciliation_status
         FROM core_banktransaction 
         WHERE bank_account_id = ? AND status = 'NEW'
         ORDER BY date DESC"
    )
    .bind(bank_account_id)
    .fetch_all(pool)
    .await
}

// =============================================================================
// Journal Entry Queries
// =============================================================================

pub async fn get_journal_entries_by_business(
    pool: &SqlitePool, 
    business_id: i64,
    limit: i64,
) -> Result<Vec<JournalEntry>, sqlx::Error> {
    sqlx::query_as::<_, JournalEntry>(
        "SELECT id, business_id, date, description, is_void, created_at, allocation_operation_id
         FROM core_journalentry WHERE business_id = ? AND is_void = 0 ORDER BY date DESC LIMIT ?"
    )
    .bind(business_id)
    .bind(limit)
    .fetch_all(pool)
    .await
}

pub async fn get_journal_lines_by_entry(pool: &SqlitePool, entry_id: i64) -> Result<Vec<JournalLine>, sqlx::Error> {
    sqlx::query_as::<_, JournalLine>(
        "SELECT id, journal_entry_id, account_id, debit, credit, description, is_reconciled
         FROM core_journalline WHERE journal_entry_id = ? ORDER BY id"
    )
    .bind(entry_id)
    .fetch_all(pool)
    .await
}

// =============================================================================
// Companion Issue Queries
// =============================================================================

pub async fn get_open_companion_issues(
    pool: &SqlitePool, 
    business_id: i64,
) -> Result<Vec<CompanionIssue>, sqlx::Error> {
    sqlx::query_as::<_, CompanionIssue>(
        "SELECT id, business_id, surface, run_type, run_id, severity, status,
                title, description, recommended_action, estimated_impact, trace_id,
                created_at, updated_at
         FROM core_companionissue 
         WHERE business_id = ? AND status = 'open'
         ORDER BY created_at DESC"
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
}
