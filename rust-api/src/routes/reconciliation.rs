//! Reconciliation API endpoints
//!
//! Provides bank account reconciliation functionality.
//! Currently returns stub data to prevent frontend errors.

#![allow(dead_code)]

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use chrono::Datelike;
use serde::{Deserialize, Serialize};

use crate::AppState;

// ============================================================================
// Reconciliation Types
// ============================================================================

#[derive(Debug, Serialize)]
pub struct ReconciliationAccount {
    pub id: i64,
    pub name: String,
    pub bank_name: String,
    pub last_reconciled_date: Option<String>,
    pub unreconciled_count: i64,
}

#[derive(Debug, Serialize)]
pub struct ReconciliationPeriod {
    pub period: String,
    pub start_date: String,
    pub end_date: String,
    pub transaction_count: i64,
    pub is_reconciled: bool,
}

#[derive(Debug, Serialize)]
pub struct ReconciliationSession {
    pub id: i64,
    pub bank_account_id: i64,
    pub status: String,
    pub statement_balance: Option<f64>,
    pub calculated_balance: f64,
    pub difference: f64,
    pub transactions: Vec<ReconciliationTransaction>,
}

#[derive(Debug, Serialize)]
pub struct ReconciliationTransaction {
    pub id: i64,
    pub date: String,
    pub description: String,
    pub amount: f64,
    pub is_matched: bool,
    pub is_excluded: bool,
    pub match_type: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct SessionQuery {
    pub bank_account_id: Option<i64>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct MatchQuery {
    pub transaction_id: Option<i64>,
}

// ============================================================================
// Reconciliation Routes
// ============================================================================

/// GET /api/reconciliation/accounts/
/// List bank accounts available for reconciliation
pub async fn list_accounts(
    State(state): State<AppState>,
) -> impl IntoResponse {
    tracing::info!("Listing reconciliation accounts");
    
    // Try to get bank accounts from database
    let accounts = sqlx::query_as::<_, (i64, String, String)>(
        "SELECT id, name, bank_name FROM core_bankaccount 
         WHERE is_active = 1
         ORDER BY name"
    )
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let account_list: Vec<serde_json::Value> = accounts
        .into_iter()
        .map(|(id, name, bank_name)| {
            serde_json::json!({
                "id": id,
                "name": name,
                "bank_name": bank_name,
                "last_reconciled_date": null,
                "unreconciled_count": 0
            })
        })
        .collect();
    
    (StatusCode::OK, Json(account_list))
}

/// GET /api/reconciliation/accounts/:id/periods/
/// Get available reconciliation periods for an account
pub async fn list_periods(
    State(_state): State<AppState>,
    Path(account_id): Path<i64>,
) -> impl IntoResponse {
    tracing::info!("Listing reconciliation periods for account {}", account_id);
    
    // Generate mock periods for the last 6 months
    let today = chrono::Local::now().date_naive();
    let mut periods = Vec::new();
    
    for i in 0..6 {
        let period_date = today - chrono::Duration::days(30 * i as i64);
        let year = period_date.format("%Y").to_string();
        let month = period_date.format("%m").to_string();
        
        // Calculate start and end of month
        let start_of_month = chrono::NaiveDate::from_ymd_opt(
            period_date.year(),
            period_date.month(),
            1
        ).unwrap_or(period_date);
        
        let end_of_month = {
            let next_month = if period_date.month() == 12 {
                chrono::NaiveDate::from_ymd_opt(period_date.year() + 1, 1, 1)
            } else {
                chrono::NaiveDate::from_ymd_opt(period_date.year(), period_date.month() + 1, 1)
            };
            next_month.map(|d| d - chrono::Duration::days(1)).unwrap_or(period_date)
        };
        
        let month_names = ["", "January", "February", "March", "April", "May", "June",
                          "July", "August", "September", "October", "November", "December"];
        let month_idx = period_date.month() as usize;
        let label = format!("{} {}", month_names.get(month_idx).unwrap_or(&""), year);
        
        periods.push(serde_json::json!({
            "id": format!("{}-{}", year, month),
            "label": label,
            "start_date": start_of_month.format("%Y-%m-%d").to_string(),
            "end_date": end_of_month.format("%Y-%m-%d").to_string(),
            "is_current": i == 0,
            "is_locked": i > 2  // Older periods are locked
        }));
    }
    
    (StatusCode::OK, Json(serde_json::json!({
        "periods": periods,
        "bank_account_id": account_id
    })))
}

/// GET /api/reconciliation/session/
/// Get or create a reconciliation session
pub async fn get_session(
    State(_state): State<AppState>,
    Query(params): Query<SessionQuery>,
) -> impl IntoResponse {
    tracing::info!("Getting reconciliation session: {:?}", params);
    
    // Return stub session
    (StatusCode::OK, Json(serde_json::json!({
        "session": {
            "id": 0,
            "bank_account_id": params.bank_account_id.unwrap_or(0),
            "status": "open",
            "statement_balance": null,
            "calculated_balance": 0.0,
            "difference": 0.0,
            "transactions": []
        },
        "transactions": [],
        "message": "No transactions to reconcile"
    })))
}

/// GET /api/reconciliation/matches/
/// Get match candidates for a transaction
pub async fn get_matches(
    State(_state): State<AppState>,
    Query(params): Query<MatchQuery>,
) -> impl IntoResponse {
    tracing::info!("Getting match candidates for transaction: {:?}", params.transaction_id);
    
    // Return empty matches
    (StatusCode::OK, Json(Vec::<serde_json::Value>::new()))
}

/// POST /api/reconciliation/confirm-match/
/// Confirm a match between transaction and document
pub async fn confirm_match(
    State(_state): State<AppState>,
    Json(body): Json<serde_json::Value>,
) -> impl IntoResponse {
    tracing::info!("Confirming match: {:?}", body);
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "message": "Match confirmed"
    })))
}

/// POST /api/reconciliation/add-as-new/
/// Add transaction as new record
pub async fn add_as_new(
    State(_state): State<AppState>,
    Json(body): Json<serde_json::Value>,
) -> impl IntoResponse {
    tracing::info!("Adding as new: {:?}", body);
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "message": "Added as new"
    })))
}

/// POST /api/reconciliation/session/:id/exclude/
/// Exclude a transaction from reconciliation
pub async fn exclude_transaction(
    State(_state): State<AppState>,
    Path(session_id): Path<i64>,
    Json(body): Json<serde_json::Value>,
) -> impl IntoResponse {
    tracing::info!("Excluding transaction from session {}: {:?}", session_id, body);
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "message": "Transaction excluded"
    })))
}

/// POST /api/reconciliation/session/:id/unmatch/
/// Unmatch a previously matched transaction
pub async fn unmatch_transaction(
    State(_state): State<AppState>,
    Path(session_id): Path<i64>,
    Json(body): Json<serde_json::Value>,
) -> impl IntoResponse {
    tracing::info!("Unmatching transaction from session {}: {:?}", session_id, body);
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "message": "Transaction unmatched"
    })))
}

/// POST /api/reconciliation/session/:id/set_statement_balance/
/// Set the statement ending balance
pub async fn set_statement_balance(
    State(_state): State<AppState>,
    Path(session_id): Path<i64>,
    Json(body): Json<serde_json::Value>,
) -> impl IntoResponse {
    tracing::info!("Setting statement balance for session {}: {:?}", session_id, body);
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "message": "Statement balance set"
    })))
}

/// POST /api/reconciliation/sessions/:id/complete/
/// Complete a reconciliation session
pub async fn complete_session(
    State(_state): State<AppState>,
    Path(session_id): Path<i64>,
) -> impl IntoResponse {
    tracing::info!("Completing reconciliation session {}", session_id);
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "message": "Session completed"
    })))
}

/// POST /api/reconciliation/sessions/:id/reopen/
/// Reopen a completed reconciliation session
pub async fn reopen_session(
    State(_state): State<AppState>,
    Path(session_id): Path<i64>,
) -> impl IntoResponse {
    tracing::info!("Reopening reconciliation session {}", session_id);
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "message": "Session reopened"
    })))
}

/// POST /api/reconciliation/sessions/:id/delete/
/// Delete a reconciliation session
pub async fn delete_session(
    State(_state): State<AppState>,
    Path(session_id): Path<i64>,
) -> impl IntoResponse {
    tracing::info!("Deleting reconciliation session {}", session_id);
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "message": "Session deleted"
    })))
}

/// POST /api/reconciliation/create-adjustment/
/// Create an adjustment entry
pub async fn create_adjustment(
    State(_state): State<AppState>,
    Json(body): Json<serde_json::Value>,
) -> impl IntoResponse {
    tracing::info!("Creating adjustment: {:?}", body);
    
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "message": "Adjustment created"
    })))
}
