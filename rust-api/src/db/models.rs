// Rust models matching the core schema
// These structs map directly to the existing database tables
#![allow(dead_code)]
// Using f64 for financial values as SQLite stores decimals as REAL

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;

// =============================================================================
// Business & User Models
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Business {
    pub id: i64,
    pub name: String,
    pub currency: String,
    pub fiscal_year_start: String,
    pub owner_user_id: i64,
    pub plan: String,
    pub status: String,
    pub is_deleted: bool,
    pub created_at: DateTime<Utc>,
    pub bank_setup_completed: bool,
    pub is_tax_registered: bool,
    pub tax_country: String,
    pub tax_region: String,
    pub ai_companion_enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct User {
    pub id: i64,
    pub username: String,
    pub email: String,
    pub first_name: String,
    pub last_name: String,
    pub is_active: bool,
    pub is_staff: bool,
    pub date_joined: DateTime<Utc>,
}

// =============================================================================
// Account & Category Models
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Account {
    pub id: i64,
    pub business_id: i64,
    pub code: String,
    pub name: String,
    #[sqlx(rename = "type")]
    pub account_type: String, // ASSET, LIABILITY, EQUITY, INCOME, EXPENSE
    pub parent_id: Option<i64>,
    pub is_active: bool,
    pub description: String,
    pub is_favorite: bool,
    pub is_suspense: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Category {
    pub id: i64,
    pub business_id: i64,
    pub name: String,
    #[sqlx(rename = "type")]
    pub category_type: String, // INCOME, EXPENSE
    pub code: String,
    pub description: String,
    pub account_id: Option<i64>,
    pub is_archived: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct TaxRate {
    pub id: i64,
    pub business_id: i64,
    pub name: String,
    pub code: String,
    pub percentage: f64,  // SQLite REAL
    pub is_recoverable: bool,
    pub is_default_sales: bool,
    pub is_default_purchases: bool,
    pub is_active: bool,
    pub country: String,
    pub region: String,
}

// =============================================================================
// Customer & Supplier Models
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Customer {
    pub id: i64,
    pub business_id: i64,
    pub name: String,
    pub email: Option<String>,
    pub phone: String,
    pub is_active: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Supplier {
    pub id: i64,
    pub business_id: i64,
    pub name: String,
    pub email: Option<String>,
    pub phone: String,
    pub created_at: DateTime<Utc>,
}

// =============================================================================
// Invoice & Expense Models
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Invoice {
    pub id: i64,
    pub business_id: i64,
    pub customer_id: i64,
    pub invoice_number: String,
    pub issue_date: NaiveDate,
    pub due_date: Option<NaiveDate>,
    pub status: String, // DRAFT, SENT, PARTIAL, PAID, VOID
    pub description: String,
    pub total_amount: f64,
    pub subtotal: Option<f64>,
    pub tax_amount: Option<f64>,
    pub net_total: f64,
    pub tax_total: f64,
    pub grand_total: f64,
    pub amount_paid: f64,
    pub balance: f64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Expense {
    pub id: i64,
    pub business_id: i64,
    pub supplier_id: Option<i64>,
    pub category_id: Option<i64>,
    pub date: NaiveDate,
    pub description: String,
    pub amount: f64,
    pub status: String, // UNPAID, PARTIAL, PAID
    pub paid_date: Option<NaiveDate>,
    pub net_total: f64,
    pub tax_total: f64,
    pub grand_total: f64,
    pub amount_paid: f64,
    pub balance: f64,
    pub created_at: DateTime<Utc>,
}

// =============================================================================
// Banking Models
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct BankAccount {
    pub id: i64,
    pub business_id: i64,
    pub name: String,
    pub bank_name: String,
    pub account_number_mask: String,
    pub usage_role: String, // OPERATING, SAVINGS, CREDIT_CARD, WALLET, OTHER
    pub account_id: Option<i64>,
    pub is_active: bool,
    pub last_imported_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct BankTransaction {
    pub id: i64,
    pub bank_account_id: i64,
    pub date: NaiveDate,
    pub description: String,
    pub amount: f64,
    pub allocated_amount: f64,
    pub external_id: Option<String>,
    pub normalized_hash: String,
    pub status: String, // NEW, SUGGESTED, PARTIAL, MATCHED_SINGLE, etc.
    pub suggestion_confidence: Option<i32>,
    pub suggestion_reason: String,
    pub category_id: Option<i64>,
    pub customer_id: Option<i64>,
    pub supplier_id: Option<i64>,
    pub matched_invoice_id: Option<i64>,
    pub matched_expense_id: Option<i64>,
    pub is_reconciled: bool,
    pub reconciliation_status: String,
}

// =============================================================================
// Journal Entry Models
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct JournalEntry {
    pub id: i64,
    pub business_id: i64,
    pub date: NaiveDate,
    pub description: String,
    pub is_void: bool,
    pub created_at: DateTime<Utc>,
    pub allocation_operation_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct JournalLine {
    pub id: i64,
    pub journal_entry_id: i64,
    pub account_id: i64,
    pub debit: f64,
    pub credit: f64,
    pub description: String,
    pub is_reconciled: bool,
}

// =============================================================================
// Companion Models
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct CompanionIssue {
    pub id: i64,
    pub business_id: i64,
    pub surface: String, // receipts, invoices, books, bank, tax
    pub run_type: String,
    pub run_id: Option<i64>,
    pub severity: String, // low, medium, high
    pub status: String,   // open, snoozed, resolved, dismissed
    pub title: String,
    pub description: String,
    pub recommended_action: String,
    pub estimated_impact: String,
    pub trace_id: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}
