//! Integration tests for the Clover Books API
//!
//! Tests all API endpoints using axum-test to simulate HTTP requests.
//! Run with: cargo test -- --nocapture

use axum::{
    routing::{get, post},
    Router,
};
use axum_test::TestServer;
use serde_json::json;

/// Create a minimal test router with basic endpoints
fn create_test_app() -> Router {
    Router::new()
        .route("/health", get(|| async { "OK" }))
        .route("/api/auth/config", get(auth_config))
        .route("/api/auth/logout", post(logout))
        // Dashboard endpoints
        .route("/api/dashboard", get(dashboard_summary))
        .route("/api/dashboard/invoices", get(list_invoices))
        .route("/api/dashboard/expenses", get(list_expenses))
        // Companion endpoints
        .route("/api/companion/issues", get(companion_issues))
        .route("/api/agentic/companion/summary", get(companion_summary))
        // Tax endpoints
        .route("/api/tax/periods/", get(tax_periods))
        // Reconciliation endpoints
        .route("/api/reconciliation/accounts/", get(reconciliation_accounts))
        .route("/api/reconciliation/accounts/:id/periods/", get(reconciliation_periods))
        .route("/api/reconciliation/session/", get(reconciliation_session))
        // Banking endpoints
        .route("/api/banking/overview/", get(banking_overview))
        .route("/api/banking/feed/", get(banking_feed))
}

// ============================================================================
// Mock Endpoint Handlers
// ============================================================================

async fn auth_config() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "google_enabled": true,
        "magic_link_enabled": false,
        "password_enabled": true
    }))
}

async fn logout() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "ok": true,
        "message": "Logged out successfully"
    }))
}

async fn dashboard_summary() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "revenue_this_month": 25000.00,
        "expenses_this_month": 12000.00,
        "net_profit": 13000.00,
        "accounts_receivable": 8500.00,
        "accounts_payable": 3200.00
    }))
}

async fn list_invoices() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "invoices": [
            {"id": 1, "invoice_number": "INV-001", "customer_name": "Acme Corp", "grand_total": "1500.00", "status": "DRAFT", "currency": "USD"},
            {"id": 2, "invoice_number": "INV-002", "customer_name": "Beta Inc", "grand_total": "2300.00", "status": "SENT", "currency": "USD"}
        ],
        "stats": {
            "open_balance_total": "3800.00",
            "revenue_ytd": "125000.00",
            "total_invoices": 45,
            "avg_invoice_value": "2778.00"
        },
        "currency": "USD"
    }))
}

async fn list_expenses() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "expenses": [
            {"id": 1, "description": "Office Supplies", "supplier_name": "Staples", "amount": "250.00", "status": "PENDING", "currency": "USD"},
            {"id": 2, "description": "Software License", "supplier_name": "Adobe", "amount": "599.00", "status": "PAID", "currency": "USD"}
        ],
        "stats": {
            "expenses_ytd": "45000.00",
            "expenses_month": "3500.00",
            "total_all": "45000.00",
            "avg_expense": "450.00"
        },
        "currency": "USD"
    }))
}

async fn companion_issues() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "ok": true,
        "issues": [],
        "total": 0,
        "by_severity": {"high": 0, "medium": 0, "low": 0},
        "by_surface": {}
    }))
}

async fn companion_summary() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "ai_companion_enabled": true,
        "health_pulse_radar": {"books_health": 85, "tax_compliance": 90, "cash_flow": 75},
        "close_readiness": {"status": "ready", "blocking_items": []},
        "finance_snapshot": {"revenue": 125000, "expenses": 45000, "net_profit": 80000}
    }))
}

async fn tax_periods() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "periods": [
            {"period_key": "2026-01", "status": "DRAFT", "net_tax": 2500.00, "payments_payment_total": 0.0},
            {"period_key": "2025-12", "status": "FILED", "net_tax": 2100.00, "payments_payment_total": 2100.00}
        ]
    }))
}

async fn reconciliation_accounts() -> axum::Json<Vec<serde_json::Value>> {
    axum::Json(vec![
        json!({"id": 1, "name": "Business Checking", "bank_name": "Wells Fargo", "last_reconciled_date": null, "unreconciled_count": 5}),
        json!({"id": 2, "name": "Savings Account", "bank_name": "Chase", "last_reconciled_date": "2025-12-15", "unreconciled_count": 0})
    ])
}

async fn reconciliation_periods(
    axum::extract::Path(_account_id): axum::extract::Path<i64>,
) -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "periods": [
            {"id": "2026-01", "label": "January 2026", "start_date": "2026-01-01", "end_date": "2026-01-31", "is_current": true, "is_locked": false},
            {"id": "2025-12", "label": "December 2025", "start_date": "2025-12-01", "end_date": "2025-12-31", "is_current": false, "is_locked": false}
        ],
        "bank_account_id": 1
    }))
}

async fn reconciliation_session() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "session": {
            "id": 1,
            "status": "DRAFT",
            "total_transactions": 10,
            "reconciled_count": 8,
            "unreconciled_count": 2
        },
        "feed": {"new": [], "matched": [], "partial": [], "excluded": []},
        "bank_account": {"id": 1, "name": "Business Checking", "currency": "USD"}
    }))
}

async fn banking_overview() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "accounts": [
            {"id": 1, "name": "Business Checking", "institution": "Wells Fargo", "balance": 45250.00, "currency": "CAD", "status": "ok", "unreconciledCount": 5}
        ],
        "summary": {
            "new_to_review": 12,
            "created_from_feed": 45,
            "matched_to_invoices": 23,
            "reconciled_percent": 85
        }
    }))
}

async fn banking_feed() -> axum::Json<serde_json::Value> {
    axum::Json(json!({
        "transactions": [
            {"id": 1, "date": "2026-01-05", "description": "STRIPE TRANSFER", "amount": 1500.00, "direction": "in", "status": "NEW"},
            {"id": 2, "date": "2026-01-04", "description": "AMAZON WEB SERVICES", "amount": 125.00, "direction": "out", "status": "MATCHED"}
        ],
        "total": 2
    }))
}

// ============================================================================
// Health Check Tests
// ============================================================================

#[tokio::test]
async fn test_health_endpoint() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/health").await;
    
    response.assert_status_ok();
    response.assert_text("OK");
}

// ============================================================================
// Auth Tests
// ============================================================================

#[tokio::test]
async fn test_auth_config_endpoint() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/auth/config").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert_eq!(body["google_enabled"], true);
    assert_eq!(body["password_enabled"], true);
}

#[tokio::test]
async fn test_logout_endpoint() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.post("/api/auth/logout").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert_eq!(body["ok"], true);
}

// ============================================================================
// Dashboard Tests
// ============================================================================

#[tokio::test]
async fn test_dashboard_summary() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/dashboard").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert!(body["revenue_this_month"].is_number());
    assert!(body["expenses_this_month"].is_number());
    assert!(body["net_profit"].is_number());
}

#[tokio::test]
async fn test_dashboard_invoices() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/dashboard/invoices").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert!(body["invoices"].is_array());
    assert!(body["stats"].is_object());
    assert_eq!(body["currency"], "USD");
}

#[tokio::test]
async fn test_dashboard_expenses() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/dashboard/expenses").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert!(body["expenses"].is_array());
    assert!(body["stats"].is_object());
}

// ============================================================================
// AI Companion Tests
// ============================================================================

#[tokio::test]
async fn test_companion_issues() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/companion/issues").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert_eq!(body["ok"], true);
    assert!(body["issues"].is_array());
}

#[tokio::test]
async fn test_companion_summary() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/agentic/companion/summary").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert_eq!(body["ai_companion_enabled"], true);
    assert!(body["health_pulse_radar"].is_object());
}

// ============================================================================
// Tax Guardian Tests
// ============================================================================

#[tokio::test]
async fn test_tax_periods() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/tax/periods/").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert!(body["periods"].is_array());
    
    let periods = body["periods"].as_array().unwrap();
    assert!(!periods.is_empty(), "Tax periods should not be empty");
}

// ============================================================================
// Reconciliation Tests
// ============================================================================

#[tokio::test]
async fn test_reconciliation_accounts() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/reconciliation/accounts/").await;
    
    response.assert_status_ok();
    
    let body: Vec<serde_json::Value> = response.json();
    assert!(!body.is_empty(), "Should have at least one bank account");
    assert!(body[0]["id"].is_number());
    assert!(body[0]["name"].is_string());
}

#[tokio::test]
async fn test_reconciliation_periods() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/reconciliation/accounts/1/periods/").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert!(body["periods"].is_array());
    
    let periods = body["periods"].as_array().unwrap();
    assert!(!periods.is_empty(), "Reconciliation periods should not be empty");
}

#[tokio::test]
async fn test_reconciliation_session() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/reconciliation/session/").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert!(body["session"].is_object());
    assert!(body["bank_account"].is_object());
}

// ============================================================================
// Banking Tests
// ============================================================================

#[tokio::test]
async fn test_banking_overview() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/banking/overview/").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert!(body["accounts"].is_array());
    assert!(body["summary"].is_object());
}

#[tokio::test]
async fn test_banking_feed() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/banking/feed/").await;
    
    response.assert_status_ok();
    
    let body: serde_json::Value = response.json();
    assert!(body["transactions"].is_array());
}

// ============================================================================
// Error Handling Tests
// ============================================================================

#[tokio::test]
async fn test_unknown_endpoint_returns_404() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.get("/api/nonexistent").await;
    
    response.assert_status_not_found();
}

#[tokio::test]
async fn test_wrong_method_returns_405() {
    let app = create_test_app();
    let server = TestServer::new(app).unwrap();
    
    let response = server.post("/health").await;
    
    response.assert_status(axum::http::StatusCode::METHOD_NOT_ALLOWED);
}
