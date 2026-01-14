//! Dashboard and core API routes for Clover Books
//!
//! Native Rust endpoints that read directly from the existing database.
//! Replaces legacy proxy calls for better performance.
#![allow(dead_code)]

use axum::{
    extract::{Path, Query, State},
    http::{StatusCode, HeaderMap},
    response::IntoResponse,
    Json,
};
use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;

use crate::AppState;
use crate::routes::auth::extract_claims_from_header;

// ============================================================================
// Authentication Helper
// ============================================================================

/// Extract business_id from JWT claims, falling back to query param or None.
/// Returns (business_id, is_authenticated)
fn get_business_id_from_auth(headers: &HeaderMap, query_business_id: Option<i64>) -> (Option<i64>, bool) {
    match extract_claims_from_header(headers) {
        Ok(claims) => {
            // Use business_id from JWT claims if available
            if let Some(bid) = claims.business_id {
                return (Some(bid), true);
            }
            // Authenticated but no business - allow query param
            (query_business_id, true)
        }
        Err(_) => {
            // Not authenticated - use query param but mark as unauthenticated
            (query_business_id, false)
        }
    }
}

/// Get business_id from query param with security warning.
/// DEPRECATED: Routes should migrate to get_business_id_from_auth.
/// Logs a warning when falling back to default business_id=1.
fn get_business_id_with_warning(business_id: Option<i64>, endpoint: &str) -> i64 {
    match business_id {
        Some(id) => id,
        None => {
            tracing::warn!(
                "⚠️  SECURITY: {} using default business_id=1 without authentication. \
                 This should be fixed to require JWT auth.",
                endpoint
            );
            1
        }
    }
}

// ============================================================================
// Dashboard Types
// ============================================================================

#[derive(Debug, Serialize)]
pub struct DashboardResponse {
    pub ok: bool,
    pub business: Option<BusinessSummary>,
    pub metrics: DashboardMetrics,
    pub recent_invoices: Vec<InvoiceSummary>,
    pub recent_expenses: Vec<ExpenseSummary>,
    pub bank_accounts: Vec<BankAccountSummary>,
}

#[derive(Debug, Serialize)]
pub struct BusinessSummary {
    pub id: i64,
    pub name: String,
    pub currency: String,
}

#[derive(Debug, Serialize)]
pub struct DashboardMetrics {
    pub total_revenue: f64,
    pub total_expenses: f64,
    pub net_income: f64,
    pub outstanding_invoices: f64,
    pub outstanding_bills: f64,
    pub cash_balance: f64,
}

#[derive(Debug, Serialize)]
pub struct InvoiceSummary {
    pub id: i64,
    pub invoice_number: String,
    pub customer_name: String,
    pub total_amount: f64,
    pub status: String,
    pub issue_date: String,
}

#[derive(Debug, Serialize)]
pub struct ExpenseSummary {
    pub id: i64,
    pub description: String,
    pub supplier_name: Option<String>,
    pub amount: f64,
    pub status: String,
    pub date: String,
}

#[derive(Debug, Serialize)]
pub struct BankAccountSummary {
    pub id: i64,
    pub name: String,
    pub bank_name: String,
    pub balance: f64,
    pub unreconciled_count: i64,
}

// ============================================================================
// List API Types
// ============================================================================

#[derive(Debug, Deserialize)]
pub struct ListQuery {
    #[serde(default = "default_limit")]
    pub limit: i64,
    #[serde(default)]
    pub offset: i64,
    pub status: Option<String>,
}

fn default_limit() -> i64 {
    50
}

#[derive(Debug, Serialize)]
pub struct ListResponse<T> {
    pub ok: bool,
    pub items: Vec<T>,
    pub total: i64,
    pub limit: i64,
    pub offset: i64,
}

// ============================================================================
// Dashboard Routes
// ============================================================================

/// GET /api/dashboard
/// 
/// Get dashboard data for the current business.
/// Requires authentication - business_id from JWT claims.
pub async fn dashboard(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<DashboardQuery>,
) -> impl IntoResponse {
    // Get business_id from JWT claims
    let (business_id_opt, is_authenticated) = get_business_id_from_auth(&headers, params.business_id);
    
    if !is_authenticated {
        return (
            StatusCode::UNAUTHORIZED,
            Json(serde_json::json!({
                "ok": false,
                "error": "Authentication required"
            })),
        ).into_response();
    }
    
    let business_id = match business_id_opt {
        Some(id) => id,
        None => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "ok": false,
                    "error": "No business associated with this account"
                })),
            ).into_response();
        }
    };
    
    tracing::info!("Fetching dashboard for business_id={}", business_id);
    
    // Get business info
    let business = sqlx::query_as::<_, (i64, String, String)>(
        "SELECT id, name, currency FROM core_business WHERE id = ? AND is_deleted = 0"
    )
    .bind(business_id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten()
    .map(|(id, name, currency)| BusinessSummary { id, name, currency });
    
    // Get metrics
    let metrics = get_dashboard_metrics(&state.db, business_id).await;
    
    // Get recent invoices (last 5)
    let recent_invoices = get_recent_invoices(&state.db, business_id, 5).await;
    
    // Get recent expenses (last 5)
    let recent_expenses = get_recent_expenses(&state.db, business_id, 5).await;
    
    // Get bank accounts with balances
    let bank_accounts = get_bank_accounts(&state.db, business_id).await;
    
    (
        StatusCode::OK,
        Json(DashboardResponse {
            ok: true,
            business,
            metrics,
            recent_invoices,
            recent_expenses,
            bank_accounts,
        }),
    ).into_response()
}

#[derive(Debug, Deserialize)]
pub struct DashboardQuery {
    pub business_id: Option<i64>,
}

async fn get_dashboard_metrics(pool: &SqlitePool, business_id: i64) -> DashboardMetrics {
    // Total revenue (paid invoices)
    let total_revenue: f64 = sqlx::query_scalar(
        "SELECT COALESCE(SUM(grand_total), 0) FROM core_invoice 
         WHERE business_id = ? AND status = 'PAID'"
    )
    .bind(business_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0.0);
    
    // Total expenses (paid)
    let total_expenses: f64 = sqlx::query_scalar(
        "SELECT COALESCE(SUM(grand_total), 0) FROM core_expense 
         WHERE business_id = ? AND status = 'PAID'"
    )
    .bind(business_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0.0);
    
    // Outstanding invoices (not paid)
    let outstanding_invoices: f64 = sqlx::query_scalar(
        "SELECT COALESCE(SUM(balance), 0) FROM core_invoice 
         WHERE business_id = ? AND status IN ('SENT', 'PARTIAL')"
    )
    .bind(business_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0.0);
    
    // Outstanding bills (unpaid expenses)
    let outstanding_bills: f64 = sqlx::query_scalar(
        "SELECT COALESCE(SUM(balance), 0) FROM core_expense 
         WHERE business_id = ? AND status IN ('UNPAID', 'PARTIAL')"
    )
    .bind(business_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0.0);
    
    DashboardMetrics {
        total_revenue,
        total_expenses,
        net_income: total_revenue - total_expenses,
        outstanding_invoices,
        outstanding_bills,
        cash_balance: 0.0, // Would need to calculate from bank accounts
    }
}

async fn get_recent_invoices(pool: &SqlitePool, business_id: i64, limit: i64) -> Vec<InvoiceSummary> {
    sqlx::query_as::<_, (i64, String, String, f64, String, String)>(
        "SELECT i.id, i.invoice_number, c.name, i.grand_total, i.status, i.issue_date
         FROM core_invoice i
         JOIN core_customer c ON i.customer_id = c.id
         WHERE i.business_id = ?
         ORDER BY i.issue_date DESC
         LIMIT ?"
    )
    .bind(business_id)
    .bind(limit)
    .fetch_all(pool)
    .await
    .unwrap_or_default()
    .into_iter()
    .map(|(id, invoice_number, customer_name, total_amount, status, issue_date)| {
        InvoiceSummary {
            id,
            invoice_number,
            customer_name,
            total_amount,
            status,
            issue_date,
        }
    })
    .collect()
}

async fn get_recent_expenses(pool: &SqlitePool, business_id: i64, limit: i64) -> Vec<ExpenseSummary> {
    sqlx::query_as::<_, (i64, String, Option<String>, f64, String, String)>(
        "SELECT e.id, e.description, s.name, e.grand_total, e.status, e.date
         FROM core_expense e
         LEFT JOIN core_supplier s ON e.supplier_id = s.id
         WHERE e.business_id = ?
         ORDER BY e.date DESC
         LIMIT ?"
    )
    .bind(business_id)
    .bind(limit)
    .fetch_all(pool)
    .await
    .unwrap_or_default()
    .into_iter()
    .map(|(id, description, supplier_name, amount, status, date)| {
        ExpenseSummary {
            id,
            description,
            supplier_name,
            amount,
            status,
            date,
        }
    })
    .collect()
}

async fn get_bank_accounts(pool: &SqlitePool, business_id: i64) -> Vec<BankAccountSummary> {
    sqlx::query_as::<_, (i64, String, String)>(
        "SELECT id, name, bank_name FROM core_bankaccount 
         WHERE business_id = ? AND is_active = 1
         ORDER BY name"
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
    .unwrap_or_default()
    .into_iter()
    .map(|(id, name, bank_name)| {
        BankAccountSummary {
            id,
            name,
            bank_name,
            balance: 0.0, // Would need balance calculation
            unreconciled_count: 0, // Would need count query
        }
    })
    .collect()
}

// ============================================================================
// Invoice List API
// ============================================================================

/// GET /api/invoices
pub async fn list_invoices(
    State(state): State<AppState>,
    Query(params): Query<InvoiceListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    let limit = params.limit.unwrap_or(50);
    let offset = params.offset.unwrap_or(0);
    
    tracing::info!("Listing invoices for business_id={}", business_id);
    
    let invoices = sqlx::query_as::<_, (i64, String, String, f64, String, String, f64)>(
        "SELECT i.id, i.invoice_number, c.name, i.grand_total, i.status, i.issue_date, i.balance
         FROM core_invoice i
         JOIN core_customer c ON i.customer_id = c.id
         WHERE i.business_id = ?
         ORDER BY i.issue_date DESC
         LIMIT ? OFFSET ?"
    )
    .bind(business_id)
    .bind(limit)
    .bind(offset)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM core_invoice WHERE business_id = ?"
    )
    .bind(business_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or(0);
    
    let items: Vec<serde_json::Value> = invoices
        .into_iter()
        .map(|(id, invoice_number, customer_name, grand_total, status, issue_date, balance)| {
            serde_json::json!({
                "id": id,
                "invoice_number": invoice_number,
                "customer_name": customer_name,
                "grand_total": grand_total,
                "status": status,
                "issue_date": issue_date,
                "balance": balance
            })
        })
        .collect();
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    })))
}

#[derive(Debug, Deserialize)]
pub struct InvoiceListQuery {
    pub business_id: Option<i64>,
    pub limit: Option<i64>,
    pub offset: Option<i64>,
    pub status: Option<String>,
}

// ============================================================================
// Expense List API
// ============================================================================

/// GET /api/expenses
pub async fn list_expenses(
    State(state): State<AppState>,
    Query(params): Query<ExpenseListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    let limit = params.limit.unwrap_or(50);
    let offset = params.offset.unwrap_or(0);
    
    tracing::info!("Listing expenses for business_id={}", business_id);
    
    let expenses = sqlx::query_as::<_, (i64, String, Option<String>, f64, String, String)>(
        "SELECT e.id, e.description, s.name, e.grand_total, e.status, e.date
         FROM core_expense e
         LEFT JOIN core_supplier s ON e.supplier_id = s.id
         WHERE e.business_id = ?
         ORDER BY e.date DESC
         LIMIT ? OFFSET ?"
    )
    .bind(business_id)
    .bind(limit)
    .bind(offset)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM core_expense WHERE business_id = ?"
    )
    .bind(business_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or(0);
    
    let items: Vec<serde_json::Value> = expenses
        .into_iter()
        .map(|(id, description, supplier_name, grand_total, status, date)| {
            serde_json::json!({
                "id": id,
                "description": description,
                "supplier_name": supplier_name,
                "grand_total": grand_total,
                "status": status,
                "date": date
            })
        })
        .collect();
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    })))
}

#[derive(Debug, Deserialize)]
pub struct ExpenseListQuery {
    pub business_id: Option<i64>,
    pub limit: Option<i64>,
    pub offset: Option<i64>,
    pub status: Option<String>,
}

// ============================================================================
// Customer List API
// ============================================================================

/// GET /api/customers
pub async fn list_customers(
    State(state): State<AppState>,
    Query(params): Query<CustomerListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    let limit = params.limit.unwrap_or(100);
    
    let customers = sqlx::query_as::<_, (i64, String, Option<String>, String, bool)>(
        "SELECT id, name, email, phone, is_active FROM core_customer 
         WHERE business_id = ?
         ORDER BY name
         LIMIT ?"
    )
    .bind(business_id)
    .bind(limit)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let items: Vec<serde_json::Value> = customers
        .into_iter()
        .map(|(id, name, email, phone, is_active)| {
            serde_json::json!({
                "id": id,
                "name": name,
                "email": email,
                "phone": phone,
                "is_active": is_active
            })
        })
        .collect();
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "items": items
    })))
}

#[derive(Debug, Deserialize)]
pub struct CustomerListQuery {
    pub business_id: Option<i64>,
    pub limit: Option<i64>,
}

// ============================================================================
// Supplier List API
// ============================================================================

/// GET /api/suppliers
pub async fn list_suppliers(
    State(state): State<AppState>,
    Query(params): Query<SupplierListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    let limit = params.limit.unwrap_or(100);
    
    let suppliers = sqlx::query_as::<_, (i64, String, Option<String>, String)>(
        "SELECT id, name, email, phone FROM core_supplier 
         WHERE business_id = ?
         ORDER BY name
         LIMIT ?"
    )
    .bind(business_id)
    .bind(limit)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let items: Vec<serde_json::Value> = suppliers
        .into_iter()
        .map(|(id, name, email, phone)| {
            serde_json::json!({
                "id": id,
                "name": name,
                "email": email,
                "phone": phone
            })
        })
        .collect();
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "items": items
    })))
}

#[derive(Debug, Deserialize)]
pub struct SupplierListQuery {
    pub business_id: Option<i64>,
    pub limit: Option<i64>,
}

// ============================================================================
// Bank Account APIs
// ============================================================================

/// GET /api/bank-accounts
pub async fn list_bank_accounts(
    State(state): State<AppState>,
    Query(params): Query<BankAccountListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    
    let accounts = sqlx::query_as::<_, (i64, String, String, String, String, bool)>(
        "SELECT id, name, bank_name, account_number_mask, usage_role, is_active 
         FROM core_bankaccount 
         WHERE business_id = ?
         ORDER BY name"
    )
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let items: Vec<serde_json::Value> = accounts
        .into_iter()
        .map(|(id, name, bank_name, mask, usage_role, is_active)| {
            serde_json::json!({
                "id": id,
                "name": name,
                "bank_name": bank_name,
                "account_number_mask": mask,
                "usage_role": usage_role,
                "is_active": is_active
            })
        })
        .collect();
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "items": items
    })))
}

#[derive(Debug, Deserialize)]
pub struct BankAccountListQuery {
    pub business_id: Option<i64>,
}

/// GET /api/bank-accounts/:id/transactions
pub async fn list_bank_transactions(
    State(state): State<AppState>,
    Path(account_id): Path<i64>,
    Query(params): Query<BankTransactionQuery>,
) -> impl IntoResponse {
    let limit = params.limit.unwrap_or(50);
    let offset = params.offset.unwrap_or(0);
    
    tracing::info!("Listing transactions for bank_account_id={}", account_id);
    
    let transactions = sqlx::query_as::<_, (i64, String, String, f64, String, i32, bool)>(
        "SELECT id, date, description, amount, status, 
                COALESCE(suggestion_confidence, 0), is_reconciled
         FROM core_banktransaction 
         WHERE bank_account_id = ?
         ORDER BY date DESC, id DESC
         LIMIT ? OFFSET ?"
    )
    .bind(account_id)
    .bind(limit)
    .bind(offset)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM core_banktransaction WHERE bank_account_id = ?"
    )
    .bind(account_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or(0);
    
    let items: Vec<serde_json::Value> = transactions
        .into_iter()
        .map(|(id, date, description, amount, status, confidence, is_reconciled)| {
            serde_json::json!({
                "id": id,
                "date": date,
                "description": description,
                "amount": amount,
                "status": status,
                "suggestion_confidence": confidence,
                "is_reconciled": is_reconciled
            })
        })
        .collect();
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    })))
}

#[derive(Debug, Deserialize)]
pub struct BankTransactionQuery {
    pub limit: Option<i64>,
    pub offset: Option<i64>,
    pub status: Option<String>,
}

// ============================================================================
// Full Customer List API (legacy-compatible format)
// ============================================================================

/// GET /api/customers/list/
/// Returns customers in the format the frontend expects
pub async fn list_customers_full(
    State(state): State<AppState>,
    Query(params): Query<CustomerListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    
    // Get business currency
    let currency: String = sqlx::query_scalar(
        "SELECT currency FROM core_business WHERE id = ?"
    )
    .bind(business_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or_else(|_| "CAD".to_string());
    
    let customers = sqlx::query_as::<_, (i64, String, Option<String>, Option<String>, Option<String>, bool)>(
        "SELECT id, name, email, phone, company, is_active FROM core_customer 
         WHERE business_id = ?
         ORDER BY name"
    )
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let customer_list: Vec<serde_json::Value> = customers
        .into_iter()
        .map(|(id, name, email, phone, company, is_active)| {
            serde_json::json!({
                "id": id,
                "name": name,
                "email": email,
                "phone": phone.unwrap_or_default(),
                "company": company,
                "is_active": is_active,
                "status": if is_active { "active" } else { "inactive" },
                "open_balance": "0.00",
                "ytd_revenue": "0.00",
                "mtd_revenue": "0.00",
                "currency": currency
            })
        })
        .collect();
    
    let total = customer_list.len();
    
    (StatusCode::OK, Json(serde_json::json!({
        "customers": customer_list,
        "stats": {
            "total_customers": total,
            "total_ytd": "0.00",
            "total_mtd": "0.00",
            "total_open_balance": "0.00"
        },
        "currency": currency
    })))
}

// ============================================================================
// Products List API
// ============================================================================

/// GET /api/products/list/
pub async fn list_products(
    State(state): State<AppState>,
    Query(params): Query<ProductListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    
    // Get business currency
    let currency: String = sqlx::query_scalar(
        "SELECT currency FROM core_business WHERE id = ?"
    )
    .bind(business_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or_else(|_| "CAD".to_string());
    
    // Try to get products from core_item table
    let items = sqlx::query_as::<_, (i64, String, Option<String>, Option<String>, Option<f64>, bool)>(
        "SELECT id, name, sku, description, price, is_active FROM core_item
         WHERE business_id = ?
         ORDER BY name"
    )
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let product_list: Vec<serde_json::Value> = items
        .into_iter()
        .map(|(id, name, sku, description, price, is_active)| {
            serde_json::json!({
                "id": id,
                "name": name,
                "code": sku.clone().unwrap_or_else(|| format!("ITEM-{}", id)),
                "sku": sku.unwrap_or_default(),
                "kind": "product",
                "status": if is_active { "active" } else { "archived" },
                "type": "PRODUCT",
                "price": price.unwrap_or(0.0),
                "description": description,
                "usage_count": 0
            })
        })
        .collect();
    
    let active_count = product_list.iter().filter(|p| p["status"] == "active").count();
    let product_count = product_list.len();
    
    (StatusCode::OK, Json(serde_json::json!({
        "items": product_list,
        "stats": {
            "active_count": active_count,
            "product_count": product_count,
            "service_count": 0,
            "avg_price": 0
        },
        "currency": currency
    })))
}

#[derive(Debug, Deserialize)]
pub struct ProductListQuery {
    pub business_id: Option<i64>,
    pub kind: Option<String>,
    pub status: Option<String>,
    pub q: Option<String>,
}

// ============================================================================
// Create Product API
// ============================================================================

#[derive(Debug, Deserialize)]
pub struct CreateProductRequest {
    pub name: String,
    pub sku: Option<String>,
    pub price: Option<f64>,
    pub description: Option<String>,
    pub kind: Option<String>, // "product" or "service"
}

/// POST /api/products/create/
pub async fn create_product(
    State(state): State<AppState>,
    Json(body): Json<CreateProductRequest>,
) -> impl IntoResponse {
    // Default to business_id 1 (demo mode - in production, extract from JWT)
    let business_id = 1i64;
    
    tracing::info!("Creating product for business_id={}: {:?}", business_id, body.name);
    
    // Generate SKU if not provided
    let sku = body.sku.unwrap_or_else(|| {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        format!("ITEM-{}", timestamp)
    });
    
    let result = sqlx::query(
        "INSERT INTO core_item (business_id, name, sku, description, price, is_active, created_at, updated_at) 
         VALUES (?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))"
    )
    .bind(business_id)
    .bind(&body.name)
    .bind(&sku)
    .bind(&body.description)
    .bind(body.price.unwrap_or(0.0))
    .execute(&state.db)
    .await;
    
    match result {
        Ok(r) => {
            let item_id = r.last_insert_rowid();
            tracing::info!("Created product id={} for business_id={}", item_id, business_id);
            (StatusCode::CREATED, Json(serde_json::json!({
                "ok": true,
                "id": item_id,
                "name": body.name,
                "sku": sku,
                "message": "Product created successfully"
            })))
        }
        Err(e) => {
            tracing::error!("Failed to create product: {:?}", e);
            (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
                "ok": false,
                "error": format!("Failed to create product: {}", e)
            })))
        }
    }
}


// ============================================================================
// Banking Overview API
// ============================================================================

/// GET /api/banking/overview/
pub async fn banking_overview(
    State(state): State<AppState>,
    Query(params): Query<BankAccountListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    
    let accounts = sqlx::query_as::<_, (i64, String, String)>(
        "SELECT id, name, bank_name FROM core_bankaccount 
         WHERE business_id = ? AND is_active = 1
         ORDER BY name"
    )
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let account_list: Vec<serde_json::Value> = accounts
        .into_iter()
        .map(|(id, name, bank_name)| {
            serde_json::json!({
                "id": id,
                "name": name,
                "bank_name": bank_name
            })
        })
        .collect();
    
    (StatusCode::OK, Json(serde_json::json!({
        "accounts": account_list
    })))
}

// ============================================================================
// Full Suppliers List API (for Suppliers page)
// ============================================================================

/// GET /api/suppliers/list/
pub async fn list_suppliers_full(
    State(state): State<AppState>,
    Query(params): Query<SupplierListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    
    // Get business currency
    let currency: String = sqlx::query_scalar(
        "SELECT currency FROM core_business WHERE id = ?"
    )
    .bind(business_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or_else(|_| "CAD".to_string());
    
    let suppliers = sqlx::query_as::<_, (i64, String, Option<String>, Option<String>, Option<String>, bool)>(
        "SELECT id, name, email, phone, company_name, is_active FROM core_supplier 
         WHERE business_id = ?
         ORDER BY name"
    )
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let supplier_list: Vec<serde_json::Value> = suppliers
        .into_iter()
        .map(|(id, name, email, phone, company, is_active)| {
            serde_json::json!({
                "id": id,
                "name": name,
                "email": email,
                "phone": phone.unwrap_or_default(),
                "company_name": company,
                "is_active": is_active,
                "open_balance": "0.00",
                "ytd_spend": "0.00",
                "mtd_spend": "0.00"
            })
        })
        .collect();
    
    let total = supplier_list.len();
    
    (StatusCode::OK, Json(serde_json::json!({
        "suppliers": supplier_list,
        "stats": {
            "total_suppliers": total,
            "total_ytd": "0.00",
            "total_open_balance": "0.00"
        },
        "currency": currency
    })))
}

// ============================================================================
// Categories List API (for Categories/COA page)
// ============================================================================

#[derive(Debug, Deserialize)]
pub struct CategoryListQuery {
    pub business_id: Option<i64>,
    pub parent_id: Option<i64>,
    #[serde(rename = "type")]
    pub category_type: Option<String>,
}

/// GET /api/categories/list/
pub async fn list_categories(
    State(state): State<AppState>,
    Query(params): Query<CategoryListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    
    // Try to get categories from core_category or core_account table
    let categories = sqlx::query_as::<_, (i64, String, Option<String>, Option<i64>, Option<String>, bool)>(
        "SELECT id, name, code, parent_id, account_type, is_active FROM core_account 
         WHERE business_id = ?
         ORDER BY code, name"
    )
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let category_list: Vec<serde_json::Value> = categories
        .into_iter()
        .map(|(id, name, code, parent_id, account_type, is_active)| {
            serde_json::json!({
                "id": id,
                "name": name,
                "code": code.unwrap_or_default(),
                "parent_id": parent_id,
                "account_type": account_type,
                "is_active": is_active,
                "type": account_type.clone().unwrap_or_else(|| "expense".to_string()),
                "balance": "0.00"
            })
        })
        .collect();
    
    let total = category_list.len();
    
    (StatusCode::OK, Json(serde_json::json!({
        "categories": category_list,
        "total": total
    })))
}

// ============================================================================
// Full Expenses List API (for Expenses page)
// ============================================================================

/// GET /api/expenses/list/
pub async fn list_expenses_full(
    State(state): State<AppState>,
    Query(params): Query<ExpenseListQuery>,
) -> impl IntoResponse {
    let business_id = get_business_id_with_warning(params.business_id, "list_invoices");
    let limit = params.limit.unwrap_or(100);
    let offset = params.offset.unwrap_or(0);
    
    // Get business currency
    let currency: String = sqlx::query_scalar(
        "SELECT currency FROM core_business WHERE id = ?"
    )
    .bind(business_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or_else(|_| "CAD".to_string());
    
    let expenses = sqlx::query_as::<_, (i64, String, Option<String>, f64, String, String, f64)>(
        "SELECT e.id, e.description, s.name, e.grand_total, e.status, e.date, e.balance
         FROM core_expense e
         LEFT JOIN core_supplier s ON e.supplier_id = s.id
         WHERE e.business_id = ?
         ORDER BY e.date DESC
         LIMIT ? OFFSET ?"
    )
    .bind(business_id)
    .bind(limit)
    .bind(offset)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM core_expense WHERE business_id = ?"
    )
    .bind(business_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or(0);
    
    let expense_list: Vec<serde_json::Value> = expenses
        .into_iter()
        .map(|(id, description, supplier_name, grand_total, status, date, balance)| {
            serde_json::json!({
                "id": id,
                "description": description,
                "supplier_name": supplier_name,
                "grand_total": grand_total,
                "status": status,
                "date": date,
                "balance": balance,
                "currency": currency
            })
        })
        .collect();
    
    (StatusCode::OK, Json(serde_json::json!({
        "expenses": expense_list,
        "total": total,
        "limit": limit,
        "offset": offset,
        "currency": currency
    })))
}

// ============================================================================
// Banking Feed Transactions API
// ============================================================================

#[derive(Debug, Deserialize)]
pub struct FeedTransactionQuery {
    pub bank_account_id: Option<i64>,
    pub status: Option<String>,
    pub limit: Option<i64>,
    pub offset: Option<i64>,
}

/// GET /api/banking/feed/transactions/
pub async fn list_feed_transactions(
    State(state): State<AppState>,
    Query(params): Query<FeedTransactionQuery>,
) -> impl IntoResponse {
    let limit = params.limit.unwrap_or(50);
    let offset = params.offset.unwrap_or(0);
    
    // Build query based on params
    let mut query = String::from(
        "SELECT id, date, description, amount, status, is_reconciled, suggestion_confidence
         FROM core_banktransaction 
         WHERE 1=1"
    );
    
    if let Some(bank_account_id) = params.bank_account_id {
        query.push_str(&format!(" AND bank_account_id = {}", bank_account_id));
    }
    
    query.push_str(" ORDER BY date DESC, id DESC");
    query.push_str(&format!(" LIMIT {} OFFSET {}", limit, offset));
    
    let transactions = sqlx::query_as::<_, (i64, String, String, f64, String, bool, Option<i32>)>(&query)
        .fetch_all(&state.db)
        .await
        .unwrap_or_default();
    
    let tx_list: Vec<serde_json::Value> = transactions
        .into_iter()
        .map(|(id, date, description, amount, status, is_reconciled, confidence)| {
            serde_json::json!({
                "id": id,
                "date": date,
                "description": description,
                "amount": amount,
                "status": status,
                "is_reconciled": is_reconciled,
                "suggestion_confidence": confidence.unwrap_or(0),
                "category": null,
                "suggested_category": null
            })
        })
        .collect();
    
    let total = tx_list.len() as i64;
    
    (StatusCode::OK, Json(serde_json::json!({
        "transactions": tx_list,
        "total": total,
        "limit": limit,
        "offset": offset
    })))
}

/// POST /api/banking/feed/transactions/:id/exclude/
pub async fn exclude_feed_transaction(
    State(state): State<AppState>,
    Path(tx_id): Path<i64>,
) -> impl IntoResponse {
    tracing::info!("Excluding feed transaction id={}", tx_id);
    
    let result = sqlx::query(
        "UPDATE core_banktransaction SET status = 'EXCLUDED', updated_at = datetime('now') WHERE id = ?"
    )
    .bind(tx_id)
    .execute(&state.db)
    .await;
    
    match result {
        Ok(r) if r.rows_affected() > 0 => {
            (StatusCode::OK, Json(serde_json::json!({
                "ok": true,
                "message": "Transaction excluded"
            })))
        }
        _ => {
            (StatusCode::NOT_FOUND, Json(serde_json::json!({
                "ok": false,
                "error": "Transaction not found"
            })))
        }
    }
}

/// POST /api/banking/feed/transactions/:id/categorize/
pub async fn categorize_feed_transaction(
    State(state): State<AppState>,
    Path(tx_id): Path<i64>,
    Json(body): Json<serde_json::Value>,
) -> impl IntoResponse {
    tracing::info!("Categorizing feed transaction id={}: {:?}", tx_id, body);
    
    // TODO: Actually update category from body.category_id
    let result = sqlx::query(
        "UPDATE core_banktransaction SET updated_at = datetime('now') WHERE id = ?"
    )
    .bind(tx_id)
    .execute(&state.db)
    .await;
    
    match result {
        Ok(r) if r.rows_affected() > 0 => {
            (StatusCode::OK, Json(serde_json::json!({
                "ok": true,
                "message": "Transaction categorized"
            })))
        }
        _ => {
            (StatusCode::NOT_FOUND, Json(serde_json::json!({
                "ok": false,
                "error": "Transaction not found"
            })))
        }
    }
}
