//! Agentic AI endpoints for Invoice and other AI processing
//!
//! Rust-first implementation backed by agentic document tables and CAE work items.

#![allow(dead_code)]

use axum::{
    extract::{Multipart, Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use chrono::{Duration, TimeZone, Utc};
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::SqlitePool;
use std::collections::HashMap;
use uuid::Uuid;

use crate::AppState;
use crate::companion_autonomy::models::{AgentOutput, WorkItemSeed};
use crate::companion_autonomy::scheduler;
use crate::companion_autonomy::store as autonomy_store;
use crate::routes::auth::extract_claims_from_header;

struct UploadedFile {
    filename: String,
    size_bytes: usize,
}

#[derive(sqlx::FromRow)]
struct ReceiptRunRow {
    id: i64,
    business_id: i64,
    status: String,
    total_documents: i64,
    success_count: i64,
    warning_count: i64,
    error_count: i64,
    metrics_json: String,
    llm_explanations_json: String,
    llm_ranked_documents_json: String,
    llm_suggested_classifications_json: String,
    llm_suggested_followups_json: String,
    trace_id: Option<String>,
    created_at: String,
    updated_at: String,
}

#[derive(sqlx::FromRow)]
struct ReceiptDocumentRow {
    id: i64,
    run_id: i64,
    business_id: i64,
    status: String,
    storage_key: String,
    original_filename: String,
    extracted_payload_json: String,
    proposed_journal_payload_json: String,
    audit_flags_json: String,
    audit_score: Option<f64>,
    risk_level: Option<String>,
    posted_journal_entry_id: Option<i64>,
    error_message: Option<String>,
    work_item_id: Option<i64>,
    created_at: String,
    updated_at: String,
}

#[derive(sqlx::FromRow)]
struct InvoiceRunRow {
    id: i64,
    business_id: i64,
    status: String,
    total_documents: i64,
    success_count: i64,
    warning_count: i64,
    error_count: i64,
    metrics_json: String,
    llm_explanations_json: String,
    llm_ranked_documents_json: String,
    llm_suggested_followups_json: String,
    trace_id: Option<String>,
    created_at: String,
    updated_at: String,
}

#[derive(sqlx::FromRow)]
struct InvoiceDocumentRow {
    id: i64,
    run_id: i64,
    business_id: i64,
    status: String,
    storage_key: String,
    original_filename: String,
    extracted_payload_json: String,
    proposed_journal_payload_json: String,
    audit_flags_json: String,
    audit_score: Option<f64>,
    risk_level: Option<String>,
    posted_journal_entry_id: Option<i64>,
    error_message: Option<String>,
    work_item_id: Option<i64>,
    created_at: String,
    updated_at: String,
}

#[derive(Debug, Deserialize)]
struct CompanionIssuesQuery {
    status: Option<String>,
    surface: Option<String>,
    severity: Option<String>,
    limit: Option<i64>,
}

#[derive(Debug, Deserialize)]
struct IssueStatusPayload {
    status: String,
}

#[derive(Debug, Deserialize)]
struct ReceiptApprovePayload {
    overrides: Option<ReceiptOverrides>,
}

#[derive(Debug, Deserialize)]
struct ReceiptOverrides {
    date: Option<String>,
    amount: Option<String>,
    currency: Option<String>,
    vendor: Option<String>,
    category: Option<String>,
    description: Option<String>,
}

#[derive(Debug, Deserialize)]
struct InvoiceOverrides {
    vendor: Option<String>,
    invoice_number: Option<String>,
    issue_date: Option<String>,
    due_date: Option<String>,
    amount: Option<String>,
    tax: Option<String>,
    currency: Option<String>,
    category: Option<String>,
    description: Option<String>,
}

struct ReceiptDocSeed {
    doc_id: i64,
    run_id: i64,
    vendor: String,
    amount: Option<f64>,
    currency: String,
    date: String,
    original_filename: String,
    risk_level: String,
    trace_id: Option<String>,
}

struct InvoiceDocSeed {
    doc_id: i64,
    run_id: i64,
    vendor: String,
    invoice_number: String,
    issue_date: String,
    due_date: String,
    amount: Option<f64>,
    tax: Option<f64>,
    currency: String,
    original_filename: String,
    risk_level: String,
    trace_id: Option<String>,
}

fn require_business_id(headers: &HeaderMap) -> Result<i64, (StatusCode, Json<Value>)> {
    extract_claims_from_header(headers)
        .ok()
        .and_then(|claims| claims.business_id)
        .ok_or_else(|| (StatusCode::UNAUTHORIZED, Json(json!({ "ok": false, "error": "unauthorized" }))))
}

fn require_user_id(headers: &HeaderMap) -> Result<i64, (StatusCode, Json<Value>)> {
    extract_claims_from_header(headers)
        .ok()
        .and_then(|claims| claims.sub.parse::<i64>().ok())
        .ok_or_else(|| (StatusCode::UNAUTHORIZED, Json(json!({ "ok": false, "error": "unauthorized" }))))
}

async fn parse_multipart_form(
    mut multipart: Multipart,
) -> Result<(HashMap<String, String>, Vec<UploadedFile>), (StatusCode, Json<Value>)> {
    let mut fields = HashMap::new();
    let mut files = Vec::new();

    while let Some(field) = multipart.next_field().await.map_err(|err| {
        (
            StatusCode::BAD_REQUEST,
            Json(json!({ "ok": false, "error": format!("invalid multipart: {}", err) })),
        )
    })? {
        let name = field.name().unwrap_or("").to_string();
        if name == "files" {
            let filename = field.file_name().unwrap_or("upload").to_string();
            let data = field.bytes().await.map_err(|err| {
                (
                    StatusCode::BAD_REQUEST,
                    Json(json!({ "ok": false, "error": format!("invalid file: {}", err) })),
                )
            })?;
            files.push(UploadedFile {
                filename,
                size_bytes: data.len(),
            });
        } else if !name.is_empty() {
            let text = field.text().await.map_err(|err| {
                (
                    StatusCode::BAD_REQUEST,
                    Json(json!({ "ok": false, "error": format!("invalid field: {}", err) })),
                )
            })?;
            fields.insert(name, text);
        }
    }

    Ok((fields, files))
}

fn parse_json_value(raw: &str) -> Value {
    serde_json::from_str(raw).unwrap_or_else(|_| json!({}))
}

fn parse_json_array(raw: &str) -> Value {
    match serde_json::from_str::<Value>(raw) {
        Ok(Value::Array(items)) => Value::Array(items),
        _ => json!([]),
    }
}

fn parse_amount(raw: &str) -> Option<f64> {
    raw.trim().replace(',', "").parse::<f64>().ok()
}

fn amount_from_value(value: &Value) -> Option<f64> {
    match value {
        Value::Number(num) => num.as_f64(),
        Value::String(s) => parse_amount(s),
        _ => None,
    }
}

fn approval_threshold() -> f64 {
    std::env::var("ENGINE_APPROVAL_AMOUNT_THRESHOLD")
        .ok()
        .and_then(|raw| raw.parse::<f64>().ok())
        .unwrap_or(1000.0)
}

fn risk_level_for_amount(amount: Option<f64>) -> &'static str {
    match amount {
        Some(value) if value >= 5000.0 => "high",
        Some(value) if value >= 1000.0 => "medium",
        Some(_) => "low",
        None => "medium",
    }
}

fn requires_approval(amount: Option<f64>) -> bool {
    amount.map(|value| value >= approval_threshold()).unwrap_or(false)
}

fn format_amount(amount: Option<f64>) -> String {
    amount.map(|value| format!("{:.2}", value)).unwrap_or_else(|| "0.00".to_string())
}

fn format_amount_with_currency(amount: Option<f64>, currency: &str) -> Option<String> {
    amount.map(|value| format!("{} {:.2}", currency, value))
}

fn fallback_vendor(default_vendor: Option<&String>, filename: &str) -> String {
    if let Some(vendor) = default_vendor {
        let trimmed = vendor.trim();
        if !trimmed.is_empty() {
            return trimmed.to_string();
        }
    }
    let leaf = filename.rsplit('/').next().unwrap_or(filename);
    let stem = leaf.split('.').next().unwrap_or(leaf);
    let trimmed = stem.trim();
    if trimmed.is_empty() {
        "Unknown vendor".to_string()
    } else {
        trimmed.to_string()
    }
}

fn default_ai_values() -> (bool, bool, String, i64, String, String, String) {
    let value_breaker_threshold = std::env::var("ENGINE_APPROVAL_AMOUNT_THRESHOLD")
        .unwrap_or_else(|_| "1000".to_string());
    (
        true,
        false,
        "suggest_only".to_string(),
        60,
        value_breaker_threshold,
        "2.5".to_string(),
        "0.25".to_string(),
    )
}

async fn ensure_ai_settings(
    pool: &SqlitePool,
    business_id: i64,
) -> Result<crate::companion_autonomy::models::AiSettingsRow, sqlx::Error> {
    if let Some(settings) = autonomy_store::fetch_ai_settings(pool, business_id).await? {
        return Ok(settings);
    }
    let (ai_enabled, kill_switch, ai_mode, velocity_limit, value_breaker, anomaly_stddev, trust_rate) =
        default_ai_values();
    autonomy_store::upsert_ai_settings(
        pool,
        business_id,
        ai_enabled,
        kill_switch,
        &ai_mode,
        velocity_limit,
        &value_breaker,
        &anomaly_stddev,
        &trust_rate,
    )
    .await
}

async fn ensure_ai_enabled(
    pool: &SqlitePool,
    business_id: i64,
) -> Result<crate::companion_autonomy::models::AiSettingsRow, (StatusCode, Json<Value>)> {
    let global_enabled = autonomy_store::business_ai_enabled(pool, business_id)
        .await
        .unwrap_or(None)
        .unwrap_or(false);
    if !global_enabled {
        return Err((
            StatusCode::FORBIDDEN,
            Json(json!({ "ok": false, "error": "ai disabled" })),
        ));
    }
    let settings = ensure_ai_settings(pool, business_id).await.map_err(|_| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "ok": false, "error": "settings unavailable" })),
        )
    })?;
    if !settings.ai_enabled || settings.kill_switch {
        return Err((
            StatusCode::FORBIDDEN,
            Json(json!({ "ok": false, "error": "ai disabled" })),
        ));
    }
    Ok(settings)
}

fn build_receipt_work_item_seed(business_id: i64, doc: &ReceiptDocSeed) -> WorkItemSeed {
    let amount_label = format_amount(doc.amount);
    let vendor_label = doc.vendor.clone();
    let summary = format!(
        "Receipt from {} for {} {} on {}.",
        vendor_label,
        doc.currency,
        amount_label,
        doc.date
    );

    WorkItemSeed {
        tenant_id: business_id,
        business_id,
        work_type: "review_receipt".to_string(),
        surface: "receipts".to_string(),
        status: "open".to_string(),
        priority: 50,
        dedupe_key: format!("receipt_doc:{}", doc.doc_id),
        inputs: json!({
            "receipt_document_id": doc.doc_id,
            "run_id": doc.run_id,
            "amount": doc.amount,
            "currency": doc.currency,
            "vendor": vendor_label,
            "date": doc.date,
            "trace_id": doc.trace_id
        }),
        state: json!({}),
        due_at: None,
        snoozed_until: None,
        risk_level: doc.risk_level.clone(),
        confidence_score: 0.72,
        requires_approval: requires_approval(doc.amount),
        customer_title: format!("Review receipt {}", doc.original_filename),
        customer_summary: summary,
        internal_title: format!("receipt_document:{}", doc.doc_id),
        internal_notes: format!("run_id:{}", doc.run_id),
        links: json!({ "target_url": "/receipts" }),
    }
}

fn build_invoice_work_item_seed(business_id: i64, doc: &InvoiceDocSeed) -> WorkItemSeed {
    let amount_label = format_amount(doc.amount);
    let summary = format!(
        "Invoice {} from {} for {} {} (due {}).",
        doc.invoice_number,
        doc.vendor,
        doc.currency,
        amount_label,
        doc.due_date
    );

    WorkItemSeed {
        tenant_id: business_id,
        business_id,
        work_type: "review_invoice".to_string(),
        surface: "invoices".to_string(),
        status: "open".to_string(),
        priority: 50,
        dedupe_key: format!("invoice_doc:{}", doc.doc_id),
        inputs: json!({
            "invoice_document_id": doc.doc_id,
            "run_id": doc.run_id,
            "amount": doc.amount,
            "tax": doc.tax,
            "currency": doc.currency,
            "vendor": doc.vendor,
            "invoice_number": doc.invoice_number,
            "issue_date": doc.issue_date,
            "due_date": doc.due_date,
            "trace_id": doc.trace_id
        }),
        state: json!({}),
        due_at: None,
        snoozed_until: None,
        risk_level: doc.risk_level.clone(),
        confidence_score: 0.72,
        requires_approval: requires_approval(doc.amount),
        customer_title: format!("Review invoice {}", doc.original_filename),
        customer_summary: summary,
        internal_title: format!("invoice_document:{}", doc.doc_id),
        internal_notes: format!("run_id:{}", doc.run_id),
        links: json!({ "target_url": "/invoices" }),
    }
}

fn apply_receipt_overrides(
    extracted: &mut Value,
    proposed: &mut Value,
    overrides: &ReceiptOverrides,
) -> Option<f64> {
    let mut amount = extracted
        .get("total")
        .and_then(amount_from_value)
        .or_else(|| overrides.amount.as_deref().and_then(parse_amount));

    if let Some(obj) = extracted.as_object_mut() {
        if let Some(date) = overrides.date.as_deref() {
            obj.insert("date".to_string(), Value::String(date.to_string()));
        }
        if let Some(value) = overrides.amount.as_deref() {
            obj.insert("total".to_string(), Value::String(value.to_string()));
            amount = parse_amount(value);
        }
        if let Some(currency) = overrides.currency.as_deref() {
            obj.insert("currency".to_string(), Value::String(currency.to_string()));
        }
        if let Some(vendor) = overrides.vendor.as_deref() {
            obj.insert("vendor".to_string(), Value::String(vendor.to_string()));
        }
        if let Some(category) = overrides.category.as_deref() {
            obj.insert("category_hint".to_string(), Value::String(category.to_string()));
        }
    }

    let description = overrides
        .description
        .as_deref()
        .or_else(|| proposed.get("description").and_then(|v| v.as_str()))
        .unwrap_or("Receipt");

    let amount_label = format_amount(amount);

    if let Some(obj) = proposed.as_object_mut() {
        obj.insert("description".to_string(), Value::String(description.to_string()));
        obj.insert(
            "lines".to_string(),
            json!([
                { "account_id": 6100, "debit": amount_label, "credit": "0", "description": "Expense" },
                { "account_id": 1000, "debit": "0", "credit": amount_label, "description": "Cash" }
            ]),
        );
    }

    amount
}

fn apply_invoice_overrides(
    extracted: &mut Value,
    proposed: &mut Value,
    overrides: &InvoiceOverrides,
) -> (Option<f64>, Option<f64>) {
    let mut amount = extracted
        .get("grand_total")
        .and_then(amount_from_value)
        .or_else(|| overrides.amount.as_deref().and_then(parse_amount));
    let mut tax = extracted
        .get("tax_total")
        .and_then(amount_from_value)
        .or_else(|| overrides.tax.as_deref().and_then(parse_amount));

    if let Some(obj) = extracted.as_object_mut() {
        if let Some(vendor) = overrides.vendor.as_deref() {
            obj.insert("vendor".to_string(), Value::String(vendor.to_string()));
        }
        if let Some(invoice_number) = overrides.invoice_number.as_deref() {
            obj.insert("invoice_number".to_string(), Value::String(invoice_number.to_string()));
        }
        if let Some(issue_date) = overrides.issue_date.as_deref() {
            obj.insert("issue_date".to_string(), Value::String(issue_date.to_string()));
        }
        if let Some(due_date) = overrides.due_date.as_deref() {
            obj.insert("due_date".to_string(), Value::String(due_date.to_string()));
        }
        if let Some(value) = overrides.amount.as_deref() {
            obj.insert("grand_total".to_string(), Value::String(value.to_string()));
            amount = parse_amount(value);
        }
        if let Some(value) = overrides.tax.as_deref() {
            obj.insert("tax_total".to_string(), Value::String(value.to_string()));
            tax = parse_amount(value);
        }
        if let Some(currency) = overrides.currency.as_deref() {
            obj.insert("currency".to_string(), Value::String(currency.to_string()));
        }
        if let Some(category) = overrides.category.as_deref() {
            obj.insert("category_hint".to_string(), Value::String(category.to_string()));
        }
    }

    let description = overrides
        .description
        .as_deref()
        .or_else(|| proposed.get("description").and_then(|v| v.as_str()))
        .unwrap_or("Invoice");

    let amount_label = format_amount(amount);

    if let Some(obj) = proposed.as_object_mut() {
        obj.insert("description".to_string(), Value::String(description.to_string()));
        obj.insert(
            "lines".to_string(),
            json!([
                { "account_id": 2000, "debit": "0", "credit": amount_label, "description": "Payable" },
                { "account_id": 6000, "debit": amount_label, "credit": "0", "description": "Expense" }
            ]),
        );
    }

    (amount, tax)
}

async fn apply_work_item_action(
    pool: &SqlitePool,
    business_id: i64,
    work_item_id: i64,
    actor_id: i64,
) -> Result<bool, sqlx::Error> {
    let action = autonomy_store::action_for_work_item(pool, business_id, work_item_id)
        .await
        .ok()
        .flatten();

    let action = match action {
        Some(action) => action,
        None => return Ok(false),
    };

    if action.requires_confirm {
        let approved_count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM companion_autonomy_approval_requests WHERE work_item_id = ? AND status = 'approved'",
        )
        .bind(work_item_id)
        .fetch_one(pool)
        .await
        .unwrap_or(0);

        if approved_count == 0 {
            let request = autonomy_store::create_approval_request(
                pool,
                business_id,
                business_id,
                work_item_id,
                &format!("user:{}", actor_id),
                false,
                None,
                None,
            )
            .await?;
            let _ = autonomy_store::set_approval_status(
                pool,
                business_id,
                request.id,
                "approved",
                Some(actor_id),
                Some("approved via UI"),
            )
            .await?;
        }
    }

    let allowed = crate::routes::companion_autonomy::can_apply_action(pool, business_id, action.id)
        .await
        .unwrap_or(false);

    if !allowed {
        return Ok(false);
    }

    let applied = autonomy_store::apply_action(pool, business_id, action.id)
        .await
        .unwrap_or(false);

    if applied {
        let _ = autonomy_store::update_work_item_status(pool, work_item_id, business_id, "applied").await;
    }

    Ok(applied)
}

// ============================================================================
// Invoice AI Routes
// ============================================================================

/// GET /api/agentic/invoices/runs
/// List all invoice processing runs
pub async fn list_runs(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let runs = sqlx::query_as::<_, InvoiceRunRow>(
        "SELECT id, business_id, status, total_documents, success_count, warning_count, error_count,
                metrics_json, llm_explanations_json, llm_ranked_documents_json, llm_suggested_followups_json,
                trace_id, created_at, updated_at
         FROM agentic_invoice_runs
         WHERE business_id = ?
         ORDER BY created_at DESC
         LIMIT 50",
    )
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let run_list: Vec<Value> = runs
        .into_iter()
        .map(|run| {
            json!({
                "id": run.id,
                "status": run.status,
                "created_at": run.created_at,
                "total_documents": run.total_documents,
                "success_count": run.success_count,
                "warning_count": run.warning_count,
                "error_count": run.error_count,
                "metrics": parse_json_value(&run.metrics_json),
                "trace_id": run.trace_id,
            })
        })
        .collect();

    (
        StatusCode::OK,
        Json(json!({
            "runs": run_list,
            "total": run_list.len()
        })),
    )
}

/// GET /api/agentic/invoices/run/:id
/// Get details of a specific run
pub async fn get_run(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(run_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let run = sqlx::query_as::<_, InvoiceRunRow>(
        "SELECT id, business_id, status, total_documents, success_count, warning_count, error_count,
                metrics_json, llm_explanations_json, llm_ranked_documents_json, llm_suggested_followups_json,
                trace_id, created_at, updated_at
         FROM agentic_invoice_runs
         WHERE id = ? AND business_id = ?",
    )
    .bind(run_id)
    .bind(business_id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    let run = match run {
        Some(run) => run,
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({
                    "error": "Run not found",
                    "run_id": run_id
                })),
            )
                .into_response();
        }
    };

    let documents = sqlx::query_as::<_, InvoiceDocumentRow>(
        "SELECT id, run_id, business_id, status, storage_key, original_filename,
                extracted_payload_json, proposed_journal_payload_json, audit_flags_json, audit_score,
                risk_level, posted_journal_entry_id, error_message, work_item_id, created_at, updated_at
         FROM agentic_invoice_documents
         WHERE run_id = ? AND business_id = ?
         ORDER BY id ASC",
    )
    .bind(run_id)
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let doc_list: Vec<Value> = documents
        .into_iter()
        .map(|doc| {
            json!({
                "id": doc.id,
                "status": doc.status,
                "storage_key": doc.storage_key,
                "original_filename": doc.original_filename,
                "extracted_payload": parse_json_value(&doc.extracted_payload_json),
                "proposed_journal_payload": parse_json_value(&doc.proposed_journal_payload_json),
                "audit_flags": parse_json_array(&doc.audit_flags_json),
                "audit_score": doc.audit_score,
                "audit_explanations": [],
                "risk_level": doc.risk_level,
                "posted_journal_entry_id": doc.posted_journal_entry_id,
                "error_message": doc.error_message,
            })
        })
        .collect();

    (
        StatusCode::OK,
        Json(json!({
            "id": run.id,
            "created_at": run.created_at,
            "status": run.status,
            "total_documents": run.total_documents,
            "success_count": run.success_count,
            "warning_count": run.warning_count,
            "error_count": run.error_count,
            "metrics": parse_json_value(&run.metrics_json),
            "trace_id": run.trace_id,
            "documents": doc_list,
            "llm_explanations": parse_json_array(&run.llm_explanations_json),
            "llm_ranked_documents": parse_json_array(&run.llm_ranked_documents_json),
            "llm_suggested_classifications": [],
            "llm_suggested_followups": parse_json_array(&run.llm_suggested_followups_json)
        })),
    )
}

/// POST /api/agentic/invoices/run
/// Upload and process invoice files
pub async fn create_run(
    State(state): State<AppState>,
    headers: HeaderMap,
    multipart: Multipart,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _ = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    if let Err(response) = ensure_ai_enabled(&state.db, business_id).await {
        return response;
    }

    let (fields, files) = match parse_multipart_form(multipart).await {
        Ok(result) => result,
        Err(response) => return response,
    };

    if files.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "ok": false, "error": "no files uploaded" })),
        );
    }

    let default_currency = fields
        .get("default_currency")
        .cloned()
        .unwrap_or_else(|| "USD".to_string());
    let default_vendor = fields.get("default_vendor").cloned().unwrap_or_default();
    let default_category = fields.get("default_category").cloned().unwrap_or_default();
    let default_issue_date = fields.get("default_issue_date").cloned().unwrap_or_default();
    let default_due_date = fields.get("default_due_date").cloned().unwrap_or_default();

    let total_bytes: usize = files.iter().map(|f| f.size_bytes).sum();
    let metrics_json = json!({
        "file_count": files.len(),
        "bytes_total": total_bytes
    })
    .to_string();
    let trace_id = Uuid::new_v4().to_string();

    let run_result = sqlx::query(
        "INSERT INTO agentic_invoice_runs (
            business_id, status, total_documents, success_count, warning_count, error_count,
            metrics_json, llm_explanations_json, llm_ranked_documents_json, llm_suggested_followups_json,
            trace_id, created_at, updated_at
        ) VALUES (?, 'COMPLETED', ?, ?, 0, 0, ?, '[]', '[]', '[]', ?, datetime('now'), datetime('now'))",
    )
    .bind(business_id)
    .bind(files.len() as i64)
    .bind(files.len() as i64)
    .bind(metrics_json)
    .bind(&trace_id)
    .execute(&state.db)
    .await;

    let run_id = match run_result {
        Ok(result) => result.last_insert_rowid(),
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "ok": false, "error": "failed to create run" })),
            );
        }
    };

    let mut seeds = Vec::new();

    for (index, file) in files.iter().enumerate() {
        let vendor = fallback_vendor(Some(&default_vendor), &file.filename);
        let issue_date = if !default_issue_date.is_empty() {
            default_issue_date.clone()
        } else {
            Utc::now().date_naive().to_string()
        };
        let due_date = if !default_due_date.is_empty() {
            default_due_date.clone()
        } else {
            let parsed = chrono::NaiveDate::parse_from_str(&issue_date, "%Y-%m-%d")
                .unwrap_or_else(|_| Utc::now().date_naive());
            (parsed + Duration::days(30)).to_string()
        };
        let amount_value = None;
        let tax_value = None;
        let risk_level = risk_level_for_amount(amount_value).to_string();
        let audit_score = if risk_level == "high" { 70.0 } else if risk_level == "medium" { 45.0 } else { 20.0 };

        let extracted_payload = json!({
            "vendor": vendor,
            "invoice_number": format!("INV-{:04}", run_id * 1000 + index as i64 + 1),
            "issue_date": issue_date,
            "due_date": due_date,
            "subtotal": format_amount(amount_value),
            "tax_total": format_amount(tax_value),
            "grand_total": format_amount(amount_value),
            "currency": default_currency,
            "category_hint": default_category,
            "user_hints": {
                "issue_date_hint": default_issue_date,
                "due_date_hint": default_due_date,
                "currency_hint": default_currency,
                "vendor_hint": default_vendor,
                "category_hint": default_category
            }
        });

        let amount_label = format_amount(amount_value);
        let proposed_payload = json!({
            "date": issue_date,
            "description": format!("Invoice - {}", file.filename),
            "lines": [
                { "account_id": 2000, "debit": "0", "credit": amount_label, "description": "Payable" },
                { "account_id": 6000, "debit": amount_label, "credit": "0", "description": "Expense" }
            ]
        });

        let audit_flags = json!([]);

        let doc_result = sqlx::query(
            "INSERT INTO agentic_invoice_documents (
                run_id, business_id, status, storage_key, original_filename, extracted_payload_json,
                proposed_journal_payload_json, audit_flags_json, audit_score, risk_level,
                posted_journal_entry_id, error_message, work_item_id, created_at, updated_at
            ) VALUES (?, ?, 'PROCESSED', ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, datetime('now'), datetime('now'))",
        )
        .bind(run_id)
        .bind(business_id)
        .bind(format!("invoices/{}/{}", run_id, file.filename.replace(' ', "_")))
        .bind(&file.filename)
        .bind(extracted_payload.to_string())
        .bind(proposed_payload.to_string())
        .bind(audit_flags.to_string())
        .bind(audit_score)
        .bind(&risk_level)
        .execute(&state.db)
        .await;

        if let Ok(result) = doc_result {
            let doc_id = result.last_insert_rowid();
            let seed = InvoiceDocSeed {
                doc_id,
                run_id,
                vendor: extracted_payload.get("vendor").and_then(|v| v.as_str()).unwrap_or("Vendor").to_string(),
                invoice_number: extracted_payload
                    .get("invoice_number")
                    .and_then(|v| v.as_str())
                    .unwrap_or("INV")
                    .to_string(),
                issue_date: extracted_payload
                    .get("issue_date")
                    .and_then(|v| v.as_str())
                    .unwrap_or(&issue_date)
                    .to_string(),
                due_date: extracted_payload
                    .get("due_date")
                    .and_then(|v| v.as_str())
                    .unwrap_or(&due_date)
                    .to_string(),
                amount: amount_value,
                tax: tax_value,
                currency: default_currency.clone(),
                original_filename: file.filename.clone(),
                risk_level: risk_level.clone(),
                trace_id: Some(trace_id.clone()),
            };
            seeds.push(seed);
        }
    }

    let output = AgentOutput {
        signals: Vec::new(),
        recommendations: Vec::new(),
        evidence_refs: Vec::new(),
        work_items: seeds
            .iter()
            .map(|seed| build_invoice_work_item_seed(business_id, seed))
            .collect(),
    };

    if let Err(err) = scheduler::apply_agent_output(&state.db, &output).await {
        return (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "ok": false, "error": err })),
        );
    }

    for seed in &seeds {
        let dedupe_key = format!("invoice_doc:{}", seed.doc_id);
        if let Ok(Some(work_item)) = autonomy_store::work_item_by_dedupe_key(&state.db, business_id, &dedupe_key).await {
            let _ = sqlx::query(
                "UPDATE agentic_invoice_documents
                 SET work_item_id = ?, updated_at = datetime('now')
                 WHERE id = ? AND business_id = ?",
            )
            .bind(work_item.id)
            .bind(seed.doc_id)
            .bind(business_id)
            .execute(&state.db)
            .await;
        }
    }

    (
        StatusCode::OK,
        Json(json!({
            "ok": true,
            "run_id": run_id,
            "status": "COMPLETED"
        })),
    )
}

/// POST /api/agentic/invoices/:id/approve
/// Approve an extracted invoice for posting
pub async fn approve_invoice(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(invoice_id): Path<i64>,
    Json(payload): Json<InvoiceOverrides>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let doc = sqlx::query_as::<_, InvoiceDocumentRow>(
        "SELECT id, run_id, business_id, status, storage_key, original_filename,
                extracted_payload_json, proposed_journal_payload_json, audit_flags_json, audit_score,
                risk_level, posted_journal_entry_id, error_message, work_item_id, created_at, updated_at
         FROM agentic_invoice_documents WHERE id = ? AND business_id = ?",
    )
    .bind(invoice_id)
    .bind(business_id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    let doc = match doc {
        Some(doc) => doc,
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({ "ok": false, "error": "invoice not found" })),
            );
        }
    };

    let mut extracted = parse_json_value(&doc.extracted_payload_json);
    let mut proposed = parse_json_value(&doc.proposed_journal_payload_json);

    let (amount_value, _tax_value) = apply_invoice_overrides(&mut extracted, &mut proposed, &payload);

    if let Some(work_item_id) = doc.work_item_id {
        match apply_work_item_action(&state.db, business_id, work_item_id, actor_id).await {
            Ok(true) => {}
            Ok(false) => {
                return (
                    StatusCode::FORBIDDEN,
                    Json(json!({ "ok": false, "error": "approval required" })),
                );
            }
            Err(_) => {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(json!({ "ok": false, "error": "failed to apply work item" })),
                );
            }
        }
    }

    let posted_id = invoice_id + 100000;
    let _ = sqlx::query(
        "UPDATE agentic_invoice_documents
         SET status = 'POSTED', posted_journal_entry_id = ?, extracted_payload_json = ?,
             proposed_journal_payload_json = ?, updated_at = datetime('now')
         WHERE id = ? AND business_id = ?",
    )
    .bind(posted_id)
    .bind(extracted.to_string())
    .bind(proposed.to_string())
    .bind(invoice_id)
    .bind(business_id)
    .execute(&state.db)
    .await;

    (
        StatusCode::OK,
        Json(json!({
            "ok": true,
            "invoice_id": invoice_id,
            "status": "POSTED",
            "amount": amount_value,
            "journal_entry_id": posted_id
        })),
    )
}

/// POST /api/agentic/invoices/:id/discard
/// Discard an extracted invoice
pub async fn discard_invoice(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(invoice_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let doc = sqlx::query_as::<_, InvoiceDocumentRow>(
        "SELECT id, run_id, business_id, status, storage_key, original_filename,
                extracted_payload_json, proposed_journal_payload_json, audit_flags_json, audit_score,
                risk_level, posted_journal_entry_id, error_message, work_item_id, created_at, updated_at
         FROM agentic_invoice_documents WHERE id = ? AND business_id = ?",
    )
    .bind(invoice_id)
    .bind(business_id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    let doc = match doc {
        Some(doc) => doc,
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({ "ok": false, "error": "invoice not found" })),
            );
        }
    };

    if let Some(work_item_id) = doc.work_item_id {
        let _ = autonomy_store::dismiss_work_item(&state.db, business_id, work_item_id).await;
    }

    let _ = sqlx::query(
        "UPDATE agentic_invoice_documents
         SET status = 'DISCARDED', updated_at = datetime('now')
         WHERE id = ? AND business_id = ?",
    )
    .bind(invoice_id)
    .bind(business_id)
    .execute(&state.db)
    .await;

    (
        StatusCode::OK,
        Json(json!({
            "ok": true,
            "invoice_id": invoice_id,
            "status": "DISCARDED"
        })),
    )
}

// ============================================================================
// Receipts AI Routes
// ============================================================================

/// GET /api/agentic/receipts/runs
/// List all receipt processing runs
pub async fn list_receipt_runs(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let runs = sqlx::query_as::<_, ReceiptRunRow>(
        "SELECT id, business_id, status, total_documents, success_count, warning_count, error_count,
                metrics_json, llm_explanations_json, llm_ranked_documents_json, llm_suggested_classifications_json,
                llm_suggested_followups_json, trace_id, created_at, updated_at
         FROM agentic_receipt_runs
         WHERE business_id = ?
         ORDER BY created_at DESC
         LIMIT 50",
    )
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let run_list: Vec<Value> = runs
        .into_iter()
        .map(|run| {
            json!({
                "id": run.id,
                "status": run.status,
                "created_at": run.created_at,
                "total_documents": run.total_documents,
                "success_count": run.success_count,
                "warning_count": run.warning_count,
                "error_count": run.error_count,
                "metrics": parse_json_value(&run.metrics_json),
                "trace_id": run.trace_id,
            })
        })
        .collect();

    (
        StatusCode::OK,
        Json(json!({
            "runs": run_list,
            "total": run_list.len()
        })),
    )
}

/// GET /api/agentic/receipts/run/:id
/// Get details of a specific receipt run
pub async fn get_receipt_run(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(run_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let run = sqlx::query_as::<_, ReceiptRunRow>(
        "SELECT id, business_id, status, total_documents, success_count, warning_count, error_count,
                metrics_json, llm_explanations_json, llm_ranked_documents_json, llm_suggested_classifications_json,
                llm_suggested_followups_json, trace_id, created_at, updated_at
         FROM agentic_receipt_runs
         WHERE id = ? AND business_id = ?",
    )
    .bind(run_id)
    .bind(business_id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    let run = match run {
        Some(run) => run,
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({
                    "error": "Run not found",
                    "run_id": run_id
                })),
            )
                .into_response();
        }
    };

    let documents = sqlx::query_as::<_, ReceiptDocumentRow>(
        "SELECT id, run_id, business_id, status, storage_key, original_filename,
                extracted_payload_json, proposed_journal_payload_json, audit_flags_json, audit_score,
                risk_level, posted_journal_entry_id, error_message, work_item_id, created_at, updated_at
         FROM agentic_receipt_documents
         WHERE run_id = ? AND business_id = ?
         ORDER BY id ASC",
    )
    .bind(run_id)
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();

    let doc_list: Vec<Value> = documents
        .into_iter()
        .map(|doc| {
            json!({
                "id": doc.id,
                "status": doc.status,
                "storage_key": doc.storage_key,
                "original_filename": doc.original_filename,
                "extracted_payload": parse_json_value(&doc.extracted_payload_json),
                "proposed_journal_payload": parse_json_value(&doc.proposed_journal_payload_json),
                "audit_flags": parse_json_array(&doc.audit_flags_json),
                "audit_score": doc.audit_score,
                "audit_explanations": [],
                "risk_level": doc.risk_level,
                "posted_journal_entry_id": doc.posted_journal_entry_id,
                "error_message": doc.error_message,
            })
        })
        .collect();

    (
        StatusCode::OK,
        Json(json!({
            "id": run.id,
            "created_at": run.created_at,
            "status": run.status,
            "total_documents": run.total_documents,
            "success_count": run.success_count,
            "warning_count": run.warning_count,
            "error_count": run.error_count,
            "metrics": parse_json_value(&run.metrics_json),
            "trace_id": run.trace_id,
            "documents": doc_list,
            "llm_explanations": parse_json_array(&run.llm_explanations_json),
            "llm_ranked_documents": parse_json_array(&run.llm_ranked_documents_json),
            "llm_suggested_classifications": parse_json_array(&run.llm_suggested_classifications_json),
            "llm_suggested_followups": parse_json_array(&run.llm_suggested_followups_json)
        })),
    )
}

/// POST /api/agentic/receipts/run
/// Upload and process receipt files
pub async fn create_receipt_run(
    State(state): State<AppState>,
    headers: HeaderMap,
    multipart: Multipart,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _ = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    if let Err(response) = ensure_ai_enabled(&state.db, business_id).await {
        return response;
    }

    let (fields, files) = match parse_multipart_form(multipart).await {
        Ok(result) => result,
        Err(response) => return response,
    };

    if files.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "ok": false, "error": "no files uploaded" })),
        );
    }

    let default_currency = fields
        .get("default_currency")
        .cloned()
        .unwrap_or_else(|| "USD".to_string());
    let default_vendor = fields.get("default_vendor").cloned().unwrap_or_default();
    let default_category = fields.get("default_category").cloned().unwrap_or_default();
    let default_date = fields.get("default_date").cloned().unwrap_or_default();

    let total_bytes: usize = files.iter().map(|f| f.size_bytes).sum();
    let metrics_json = json!({
        "file_count": files.len(),
        "bytes_total": total_bytes
    })
    .to_string();
    let trace_id = Uuid::new_v4().to_string();

    let run_result = sqlx::query(
        "INSERT INTO agentic_receipt_runs (
            business_id, status, total_documents, success_count, warning_count, error_count,
            metrics_json, llm_explanations_json, llm_ranked_documents_json,
            llm_suggested_classifications_json, llm_suggested_followups_json,
            trace_id, created_at, updated_at
        ) VALUES (?, 'COMPLETED', ?, ?, 0, 0, ?, '[]', '[]', '[]', '[]', ?, datetime('now'), datetime('now'))",
    )
    .bind(business_id)
    .bind(files.len() as i64)
    .bind(files.len() as i64)
    .bind(metrics_json)
    .bind(&trace_id)
    .execute(&state.db)
    .await;

    let run_id = match run_result {
        Ok(result) => result.last_insert_rowid(),
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "ok": false, "error": "failed to create run" })),
            );
        }
    };

    let mut seeds = Vec::new();

    for file in &files {
        let vendor = fallback_vendor(Some(&default_vendor), &file.filename);
        let date_value = if !default_date.is_empty() {
            default_date.clone()
        } else {
            Utc::now().date_naive().to_string()
        };
        let amount_value = None;
        let risk_level = risk_level_for_amount(amount_value).to_string();
        let audit_score = if risk_level == "high" { 70.0 } else if risk_level == "medium" { 45.0 } else { 20.0 };

        let extracted_payload = json!({
            "vendor": vendor,
            "date": date_value,
            "total": format_amount(amount_value),
            "currency": default_currency,
            "category_hint": default_category,
            "user_hints": {
                "date_hint": default_date,
                "currency_hint": default_currency,
                "vendor_hint": default_vendor,
                "category_hint": default_category
            }
        });

        let amount_label = format_amount(amount_value);
        let proposed_payload = json!({
            "date": extracted_payload.get("date").and_then(|v| v.as_str()).unwrap_or(""),
            "description": format!("Receipt - {}", file.filename),
            "lines": [
                { "account_id": 6100, "debit": amount_label, "credit": "0", "description": "Expense" },
                { "account_id": 1000, "debit": "0", "credit": amount_label, "description": "Cash" }
            ]
        });

        let audit_flags = json!([]);

        let doc_result = sqlx::query(
            "INSERT INTO agentic_receipt_documents (
                run_id, business_id, status, storage_key, original_filename, extracted_payload_json,
                proposed_journal_payload_json, audit_flags_json, audit_score, risk_level,
                posted_journal_entry_id, error_message, work_item_id, created_at, updated_at
            ) VALUES (?, ?, 'PROCESSED', ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, datetime('now'), datetime('now'))",
        )
        .bind(run_id)
        .bind(business_id)
        .bind(format!("receipts/{}/{}", run_id, file.filename.replace(' ', "_")))
        .bind(&file.filename)
        .bind(extracted_payload.to_string())
        .bind(proposed_payload.to_string())
        .bind(audit_flags.to_string())
        .bind(audit_score)
        .bind(&risk_level)
        .execute(&state.db)
        .await;

        if let Ok(result) = doc_result {
            let doc_id = result.last_insert_rowid();
            let seed = ReceiptDocSeed {
                doc_id,
                run_id,
                vendor: extracted_payload.get("vendor").and_then(|v| v.as_str()).unwrap_or("Vendor").to_string(),
                amount: amount_value,
                currency: default_currency.clone(),
                date: extracted_payload
                    .get("date")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                original_filename: file.filename.clone(),
                risk_level: risk_level.clone(),
                trace_id: Some(trace_id.clone()),
            };
            seeds.push(seed);
        }
    }

    let output = AgentOutput {
        signals: Vec::new(),
        recommendations: Vec::new(),
        evidence_refs: Vec::new(),
        work_items: seeds
            .iter()
            .map(|seed| build_receipt_work_item_seed(business_id, seed))
            .collect(),
    };

    if let Err(err) = scheduler::apply_agent_output(&state.db, &output).await {
        return (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "ok": false, "error": err })),
        );
    }

    for seed in &seeds {
        let dedupe_key = format!("receipt_doc:{}", seed.doc_id);
        if let Ok(Some(work_item)) = autonomy_store::work_item_by_dedupe_key(&state.db, business_id, &dedupe_key).await {
            let _ = sqlx::query(
                "UPDATE agentic_receipt_documents
                 SET work_item_id = ?, updated_at = datetime('now')
                 WHERE id = ? AND business_id = ?",
            )
            .bind(work_item.id)
            .bind(seed.doc_id)
            .bind(business_id)
            .execute(&state.db)
            .await;
        }
    }

    (
        StatusCode::OK,
        Json(json!({
            "ok": true,
            "run_id": run_id,
            "status": "COMPLETED"
        })),
    )
}

/// POST /api/agentic/receipts/:id/approve
/// Approve an extracted receipt for posting
pub async fn approve_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(receipt_id): Path<i64>,
    Json(payload): Json<ReceiptApprovePayload>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let doc = sqlx::query_as::<_, ReceiptDocumentRow>(
        "SELECT id, run_id, business_id, status, storage_key, original_filename,
                extracted_payload_json, proposed_journal_payload_json, audit_flags_json, audit_score,
                risk_level, posted_journal_entry_id, error_message, work_item_id, created_at, updated_at
         FROM agentic_receipt_documents WHERE id = ? AND business_id = ?",
    )
    .bind(receipt_id)
    .bind(business_id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    let doc = match doc {
        Some(doc) => doc,
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({ "ok": false, "error": "receipt not found" })),
            );
        }
    };

    let mut extracted = parse_json_value(&doc.extracted_payload_json);
    let mut proposed = parse_json_value(&doc.proposed_journal_payload_json);

    let overrides = payload.overrides.unwrap_or(ReceiptOverrides {
        date: None,
        amount: None,
        currency: None,
        vendor: None,
        category: None,
        description: None,
    });

    let amount_value = apply_receipt_overrides(&mut extracted, &mut proposed, &overrides);

    if let Some(work_item_id) = doc.work_item_id {
        match apply_work_item_action(&state.db, business_id, work_item_id, actor_id).await {
            Ok(true) => {}
            Ok(false) => {
                return (
                    StatusCode::FORBIDDEN,
                    Json(json!({ "ok": false, "error": "approval required" })),
                );
            }
            Err(_) => {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(json!({ "ok": false, "error": "failed to apply work item" })),
                );
            }
        }
    }

    let posted_id = receipt_id + 100000;
    let _ = sqlx::query(
        "UPDATE agentic_receipt_documents
         SET status = 'POSTED', posted_journal_entry_id = ?, extracted_payload_json = ?,
             proposed_journal_payload_json = ?, updated_at = datetime('now')
         WHERE id = ? AND business_id = ?",
    )
    .bind(posted_id)
    .bind(extracted.to_string())
    .bind(proposed.to_string())
    .bind(receipt_id)
    .bind(business_id)
    .execute(&state.db)
    .await;

    (
        StatusCode::OK,
        Json(json!({
            "ok": true,
            "receipt_id": receipt_id,
            "status": "POSTED",
            "amount": amount_value,
            "journal_entry_id": posted_id
        })),
    )
}

/// POST /api/agentic/receipts/:id/discard
/// Discard an extracted receipt
pub async fn discard_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(receipt_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let doc = sqlx::query_as::<_, ReceiptDocumentRow>(
        "SELECT id, run_id, business_id, status, storage_key, original_filename,
                extracted_payload_json, proposed_journal_payload_json, audit_flags_json, audit_score,
                risk_level, posted_journal_entry_id, error_message, work_item_id, created_at, updated_at
         FROM agentic_receipt_documents WHERE id = ? AND business_id = ?",
    )
    .bind(receipt_id)
    .bind(business_id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    let doc = match doc {
        Some(doc) => doc,
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({ "ok": false, "error": "receipt not found" })),
            );
        }
    };

    if let Some(work_item_id) = doc.work_item_id {
        let _ = autonomy_store::dismiss_work_item(&state.db, business_id, work_item_id).await;
    }

    let _ = sqlx::query(
        "UPDATE agentic_receipt_documents
         SET status = 'DISCARDED', updated_at = datetime('now')
         WHERE id = ? AND business_id = ?",
    )
    .bind(receipt_id)
    .bind(business_id)
    .execute(&state.db)
    .await;

    (
        StatusCode::OK,
        Json(json!({
            "ok": true,
            "receipt_id": receipt_id,
            "status": "DISCARDED"
        })),
    )
}

// ============================================================================
// Companion AI Routes (for Control Tower)
// ============================================================================

async fn surface_status_counts(
    pool: &SqlitePool,
    business_id: i64,
    days: i64,
) -> HashMap<String, HashMap<String, i64>> {
    let rows = sqlx::query_as::<_, (String, String, i64)>(
        "SELECT surface, status, COUNT(*)
         FROM companion_autonomy_work_items
         WHERE tenant_id = ? AND created_at >= datetime('now', ?)
         GROUP BY surface, status",
    )
    .bind(business_id)
    .bind(format!("-{} days", days))
    .fetch_all(pool)
    .await
    .unwrap_or_default();

    let mut map: HashMap<String, HashMap<String, i64>> = HashMap::new();
    for (surface, status, count) in rows {
        map.entry(surface)
            .or_default()
            .insert(status, count);
    }
    map
}

fn coverage_entry(total: i64, covered: i64) -> Value {
    let percent = if total > 0 {
        ((covered as f64) / (total as f64) * 100.0).round()
    } else {
        100.0
    };
    json!({
        "coverage_percent": percent,
        "total_items": total,
        "covered_items": covered
    })
}

fn score_from_open(open: i64) -> i64 {
    let score = 100 - (open * 6);
    score.clamp(0, 100)
}

async fn fetch_receipt_run_summaries(pool: &SqlitePool, business_id: i64, limit: i64) -> Vec<Value> {
    let runs = sqlx::query_as::<_, ReceiptRunRow>(
        "SELECT id, business_id, status, total_documents, success_count, warning_count, error_count,
                metrics_json, llm_explanations_json, llm_ranked_documents_json, llm_suggested_classifications_json,
                llm_suggested_followups_json, trace_id, created_at, updated_at
         FROM agentic_receipt_runs
         WHERE business_id = ?
         ORDER BY created_at DESC
         LIMIT ?",
    )
    .bind(business_id)
    .bind(limit)
    .fetch_all(pool)
    .await
    .unwrap_or_default();

    if runs.is_empty() {
        return Vec::new();
    }

    let run_ids: Vec<i64> = runs.iter().map(|r| r.id).collect();
    let placeholders = std::iter::repeat("?").take(run_ids.len()).collect::<Vec<_>>().join(",");
    let query = format!(
        "SELECT run_id,
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END), 0) as high_risk,
                COALESCE(SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END), 0) as errors
         FROM agentic_receipt_documents
         WHERE run_id IN ({})
         GROUP BY run_id",
        placeholders
    );

    let mut q = sqlx::query_as::<_, (i64, i64, i64, i64)>(&query);
    for run_id in &run_ids {
        q = q.bind(run_id);
    }
    let counts = q.fetch_all(pool).await.unwrap_or_default();

    let mut count_map: HashMap<i64, (i64, i64, i64)> = HashMap::new();
    for (run_id, total, high_risk, errors) in counts {
        count_map.insert(run_id, (total, high_risk, errors));
    }

    runs
        .into_iter()
        .map(|run| {
            let (total, high_risk, errors) = count_map.get(&run.id).copied().unwrap_or((0, 0, 0));
            json!({
                "id": run.id,
                "created_at": run.created_at,
                "documents_total": total,
                "high_risk_count": high_risk,
                "errors_count": errors,
                "risk_level": if high_risk > 0 { "high" } else { "low" },
                "trace_id": run.trace_id
            })
        })
        .collect()
}

async fn fetch_invoice_run_summaries(pool: &SqlitePool, business_id: i64, limit: i64) -> Vec<Value> {
    let runs = sqlx::query_as::<_, InvoiceRunRow>(
        "SELECT id, business_id, status, total_documents, success_count, warning_count, error_count,
                metrics_json, llm_explanations_json, llm_ranked_documents_json, llm_suggested_followups_json,
                trace_id, created_at, updated_at
         FROM agentic_invoice_runs
         WHERE business_id = ?
         ORDER BY created_at DESC
         LIMIT ?",
    )
    .bind(business_id)
    .bind(limit)
    .fetch_all(pool)
    .await
    .unwrap_or_default();

    if runs.is_empty() {
        return Vec::new();
    }

    let run_ids: Vec<i64> = runs.iter().map(|r| r.id).collect();
    let placeholders = std::iter::repeat("?").take(run_ids.len()).collect::<Vec<_>>().join(",");
    let query = format!(
        "SELECT run_id,
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END), 0) as high_risk,
                COALESCE(SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END), 0) as errors
         FROM agentic_invoice_documents
         WHERE run_id IN ({})
         GROUP BY run_id",
        placeholders
    );

    let mut q = sqlx::query_as::<_, (i64, i64, i64, i64)>(&query);
    for run_id in &run_ids {
        q = q.bind(run_id);
    }
    let counts = q.fetch_all(pool).await.unwrap_or_default();

    let mut count_map: HashMap<i64, (i64, i64, i64)> = HashMap::new();
    for (run_id, total, high_risk, errors) in counts {
        count_map.insert(run_id, (total, high_risk, errors));
    }

    runs
        .into_iter()
        .map(|run| {
            let (total, high_risk, errors) = count_map.get(&run.id).copied().unwrap_or((0, 0, 0));
            json!({
                "id": run.id,
                "created_at": run.created_at,
                "documents_total": total,
                "high_risk_count": high_risk,
                "errors_count": errors,
                "risk_level": if high_risk > 0 { "high" } else { "low" },
                "trace_id": run.trace_id
            })
        })
        .collect()
}

async fn totals_for_documents(
    pool: &SqlitePool,
    business_id: i64,
    table: &str,
) -> HashMap<String, i64> {
    let query = format!(
        "SELECT
            COUNT(*) as total,
            COALESCE(SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END), 0) as high_risk,
            COALESCE(SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END), 0) as errors
         FROM {} WHERE business_id = ? AND created_at >= datetime('now', '-30 days')",
        table
    );

    let row = sqlx::query_as::<_, (i64, i64, i64)>(&query)
        .bind(business_id)
        .fetch_optional(pool)
        .await
        .ok()
        .flatten()
        .unwrap_or((0, 0, 0));

    let mut totals = HashMap::new();
    totals.insert("total".to_string(), row.0);
    totals.insert("high_risk".to_string(), row.1);
    totals.insert("errors".to_string(), row.2);
    totals
}

async fn high_risk_counts_30d(pool: &SqlitePool, business_id: i64) -> HashMap<String, i64> {
    let rows = sqlx::query_as::<_, (String, i64)>(
        "SELECT surface, COUNT(*)
         FROM companion_autonomy_work_items
         WHERE tenant_id = ? AND risk_level = 'high' AND created_at >= datetime('now', '-30 days')
         GROUP BY surface",
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
    .unwrap_or_default();

    let mut map = HashMap::new();
    for (surface, count) in rows {
        map.insert(surface, count);
    }
    map
}

async fn agent_retries_30d(pool: &SqlitePool, business_id: i64) -> i64 {
    sqlx::query_scalar(
        "SELECT COUNT(*) FROM companion_autonomy_agent_runs
         WHERE tenant_id = ? AND status IN ('failed', 'blocked') AND created_at >= datetime('now', '-30 days')",
    )
    .bind(business_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0)
}

async fn revenue_expense_series(pool: &SqlitePool, business_id: i64) -> Vec<Value> {
    let invoice_rows = sqlx::query_as::<_, (String, f64)>(
        "SELECT strftime('%Y-%m', issue_date) as ym, COALESCE(SUM(grand_total), 0)
         FROM core_invoice
         WHERE business_id = ? AND issue_date >= date('now', '-3 months')
         GROUP BY ym",
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
    .unwrap_or_default();

    let expense_rows = sqlx::query_as::<_, (String, f64)>(
        "SELECT strftime('%Y-%m', date) as ym, COALESCE(SUM(grand_total), 0)
         FROM core_expense
         WHERE business_id = ? AND date >= date('now', '-3 months')
         GROUP BY ym",
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
    .unwrap_or_default();

    let mut revenue_map = HashMap::new();
    for (ym, total) in invoice_rows {
        revenue_map.insert(ym, total);
    }

    let mut expense_map = HashMap::new();
    for (ym, total) in expense_rows {
        expense_map.insert(ym, total);
    }

    let mut months = Vec::new();
    for offset in (0..3).rev() {
        let date = Utc::now() - Duration::days(30 * offset);
        let ym_key = date.format("%Y-%m").to_string();
        let label = date.format("%b").to_string();
        let rev = revenue_map.get(&ym_key).copied().unwrap_or(0.0);
        let exp = expense_map.get(&ym_key).copied().unwrap_or(0.0);
        months.push(json!({ "m": label, "rev": rev, "exp": exp }));
    }

    months
}

async fn expenses_last_30d(pool: &SqlitePool, business_id: i64) -> f64 {
    sqlx::query_scalar(
        "SELECT COALESCE(SUM(grand_total), 0) FROM core_expense
         WHERE business_id = ? AND date >= date('now', '-30 days')",
    )
    .bind(business_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0.0)
}

/// GET /api/agentic/companion/summary
/// Returns comprehensive AI companion summary for the Control Tower
pub async fn companion_summary(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let global_enabled = autonomy_store::business_ai_enabled(&state.db, business_id)
        .await
        .unwrap_or(None)
        .unwrap_or(false);
    let settings = ensure_ai_settings(&state.db, business_id).await.ok();
    let ai_companion_enabled = global_enabled
        && settings
            .as_ref()
            .map(|s| s.ai_enabled && !s.kill_switch)
            .unwrap_or(true);

    let open_items = autonomy_store::list_work_items_by_status(
        &state.db,
        business_id,
        &["open", "ready", "waiting_approval"],
        200,
    )
    .await
    .unwrap_or_default();

    let mut open_counts: HashMap<String, i64> = HashMap::new();
    for item in &open_items {
        *open_counts.entry(item.surface.clone()).or_insert(0) += 1;
    }
    let open_total: i64 = open_counts.values().sum();

    let coverage_counts = surface_status_counts(&state.db, business_id, 30).await;
    let resolved_statuses = ["applied", "dismissed"];

    let coverage_for_surface = |surface: &str| -> (i64, i64) {
        let counts = coverage_counts.get(surface);
        let total = counts
            .map(|map| map.values().sum())
            .unwrap_or(0);
        let covered = counts
            .map(|map| {
                resolved_statuses
                    .iter()
                    .filter_map(|status| map.get(*status))
                    .sum()
            })
            .unwrap_or(0);
        (total, covered)
    };

    let (receipts_total, receipts_covered) = coverage_for_surface("receipts");
    let (invoices_total, invoices_covered) = coverage_for_surface("invoices");
    let (bank_total, bank_covered) = coverage_for_surface("bank");
    let (books_total, books_covered) = coverage_for_surface("books");

    let radar = json!({
        "cash_reconciliation": {
            "score": score_from_open(*open_counts.get("bank").unwrap_or(&0)),
            "open_issues": open_counts.get("bank").copied().unwrap_or(0)
        },
        "revenue_invoices": {
            "score": score_from_open(*open_counts.get("invoices").unwrap_or(&0)),
            "open_issues": open_counts.get("invoices").copied().unwrap_or(0)
        },
        "expenses_receipts": {
            "score": score_from_open(*open_counts.get("receipts").unwrap_or(&0)),
            "open_issues": open_counts.get("receipts").copied().unwrap_or(0)
        },
        "tax_compliance": {
            "score": 100,
            "open_issues": 0
        }
    });

    let coverage = json!({
        "receipts": coverage_entry(receipts_total, receipts_covered),
        "invoices": coverage_entry(invoices_total, invoices_covered),
        "banking": coverage_entry(bank_total, bank_covered),
        "bank": coverage_entry(bank_total, bank_covered),
        "books": coverage_entry(books_total, books_covered)
    });

    let mut playbook_items = Vec::new();
    let mut open_sorted = open_items.clone();
    open_sorted.sort_by(|a, b| {
        let risk_rank = |risk: &str| match risk {
            "high" => 2,
            "medium" => 1,
            _ => 0,
        };
        risk_rank(&b.risk_level)
            .cmp(&risk_rank(&a.risk_level))
            .then(b.priority.cmp(&a.priority))
    });

    for item in open_sorted.iter().take(3) {
        let links: Value = serde_json::from_str(&item.links_json).unwrap_or_default();
        let target_url = links.get("target_url").and_then(|v| v.as_str()).unwrap_or("/companion");
        playbook_items.push(json!({
            "label": item.customer_title,
            "description": item.customer_summary,
            "severity": item.risk_level,
            "surface": item.surface,
            "url": target_url,
            "requires_premium": false
        }));
    }

    let focus_mode = if open_total == 0 {
        "all_clear"
    } else if open_total <= 3 {
        "watchlist"
    } else {
        "fire_drill"
    };
    let primary_cta = if open_total == 0 {
        "All clear. No action needed.".to_string()
    } else {
        format!(
            "Review {} open item{}.",
            open_total,
            if open_total == 1 { "" } else { "s" }
        )
    };

    let progress_percent = if open_total == 0 {
        100
    } else {
        (100 - (open_total * 5).min(90))
    };

    let mut blocking_items = Vec::new();
    for item in open_sorted.iter().take(3) {
        blocking_items.push(json!({
            "reason": item.customer_title,
            "surface": item.surface,
            "severity": item.risk_level
        }));
    }
    let blocking_reasons: Vec<String> = blocking_items
        .iter()
        .filter_map(|v| v.get("reason").and_then(|r| r.as_str()).map(|s| s.to_string()))
        .collect();

    let llm_subtitles = json!({
        "receipts": if open_counts.get("receipts").copied().unwrap_or(0) > 0 { "Receipts need review" } else { "" },
        "invoices": if open_counts.get("invoices").copied().unwrap_or(0) > 0 { "Invoices need review" } else { "" },
        "books": "",
        "bank": if open_counts.get("bank").copied().unwrap_or(0) > 0 { "Banking needs review" } else { "" }
    });

    let monthly_burn = expenses_last_30d(&state.db, business_id).await;
    let runway_months = if monthly_burn > 0.0 { None } else { None };
    let months = revenue_expense_series(&state.db, business_id).await;

    let finance_snapshot = json!({
        "ending_cash": 0.0,
        "monthly_burn": monthly_burn,
        "runway_months": runway_months,
        "months": months,
        "ar_buckets": [],
        "total_overdue": 0
    });

    let high_risk = high_risk_counts_30d(&state.db, business_id).await;
    let global_high_risk = json!({
        "receipts": high_risk.get("receipts").copied().unwrap_or(0),
        "invoices": high_risk.get("invoices").copied().unwrap_or(0),
        "bank_transactions": high_risk.get("bank").copied().unwrap_or(0),
        "books": high_risk.get("books").copied().unwrap_or(0)
    });

    let engine_snapshot_meta = fetch_engine_snapshot_meta(&state.db, business_id).await;

    let receipts_runs = fetch_receipt_run_summaries(&state.db, business_id, 3).await;
    let invoices_runs = fetch_invoice_run_summaries(&state.db, business_id, 3).await;

    let receipt_totals = totals_for_documents(&state.db, business_id, "agentic_receipt_documents").await;
    let invoice_totals = totals_for_documents(&state.db, business_id, "agentic_invoice_documents").await;

    (
        StatusCode::OK,
        Json(json!({
            "ai_companion_enabled": ai_companion_enabled,
            "generated_at": Utc::now().to_rfc3339(),
            "voice": {
                "greeting": "Hello",
                "focus_mode": focus_mode,
                "tone_tagline": if open_total == 0 { "All clear." } else { "A few items need attention." },
                "primary_call_to_action": primary_cta
            },
            "radar": radar,
            "coverage": coverage,
            "playbook": playbook_items,
            "close_readiness": {
                "status": if open_total == 0 { "ready" } else { "not_ready" },
                "period_label": Utc::now().format("%B %Y").to_string(),
                "progress_percent": progress_percent,
                "blocking_items": blocking_items,
                "blocking_reasons": blocking_reasons
            },
            "llm_subtitles": llm_subtitles,
            "finance_snapshot": finance_snapshot,
            "tax": {
                "period_key": Utc::now().format("%Y-%m").to_string(),
                "net_tax": 0,
                "jurisdictions": [],
                "anomaly_counts": { "low": 0, "medium": 0, "high": 0 }
            },
            "engine_snapshot_meta": engine_snapshot_meta,
            "surfaces": {
                "receipts": {
                    "recent_runs": receipts_runs,
                    "totals_last_30_days": receipt_totals
                },
                "invoices": {
                    "recent_runs": invoices_runs,
                    "totals_last_30_days": invoice_totals
                },
                "books_review": {
                    "recent_runs": [],
                    "totals_last_30_days": {}
                },
                "bank_review": {
                    "recent_runs": [],
                    "totals_last_30_days": {}
                }
            },
            "global": {
                "last_books_review": null,
                "high_risk_items_30d": global_high_risk,
                "agent_retries_30d": agent_retries_30d(&state.db, business_id).await
            }
        })),
    )
}

async fn fetch_engine_snapshot_meta(
    pool: &SqlitePool,
    business_id: i64,
) -> Option<serde_json::Value> {
    let snapshot = autonomy_store::latest_queue_snapshot(pool, business_id)
        .await
        .ok()
        .flatten()?;

    let stale = is_queue_snapshot_stale(&snapshot.generated_at, snapshot.stale_after_seconds);
    let payload: serde_json::Value = serde_json::from_str(&snapshot.snapshot_json).unwrap_or_default();
    let queued_total = payload
        .get("job_totals")
        .and_then(|v| v.get("queued"))
        .and_then(|v| v.as_i64())
        .unwrap_or(0);
    let blocked_total = payload
        .get("job_totals")
        .and_then(|v| v.get("blocked"))
        .and_then(|v| v.as_i64())
        .unwrap_or(0);
    let breaker_events = payload
        .get("stats")
        .and_then(|v| v.get("breaker_events_last_day"))
        .and_then(|v| v.as_i64())
        .unwrap_or(0);
    let mode = payload
        .get("mode")
        .and_then(|v| v.as_str())
        .unwrap_or("suggest_only");

    Some(json!({
        "generated_at": snapshot.generated_at,
        "stale": stale,
        "queued_total": queued_total,
        "blocked_total": blocked_total,
        "mode": mode,
        "breakers_ok": breaker_events == 0
    }))
}

fn is_queue_snapshot_stale(generated_at: &str, stale_after_seconds: i64) -> bool {
    if let Ok(parsed) = chrono::NaiveDateTime::parse_from_str(generated_at, "%Y-%m-%d %H:%M:%S") {
        let generated = Utc.from_utc_datetime(&parsed);
        let age_seconds = (Utc::now() - generated).num_seconds();
        return age_seconds > stale_after_seconds;
    }
    false
}

/// GET /api/agentic/companion/context-summary
pub async fn companion_context_summary(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let open_items = autonomy_store::list_work_items_by_status(
        &state.db,
        business_id,
        &["open", "ready", "waiting_approval"],
        200,
    )
    .await
    .unwrap_or_default();
    let open_total = open_items.len() as i64;
    let score = score_from_open(open_total);

    (
        StatusCode::OK,
        Json(json!({
            "generated_at": Utc::now().to_rfc3339(),
            "health_index": {
                "score": score,
                "open_issues": open_total,
                "status": if score >= 90 { "healthy" } else if score >= 70 { "watch" } else { "risk" }
            }
        })),
    )
}

/// GET /api/agentic/companion/issues
/// Returns open companion issues for the Control Tower
pub async fn companion_issues(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<CompanionIssuesQuery>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let status = params.status.unwrap_or_else(|| "open".to_string());
    let limit = params.limit.unwrap_or(100);

    let statuses: Vec<&str> = match status.as_str() {
        "resolved" => vec!["applied", "dismissed"],
        "snoozed" => vec!["snoozed"],
        "all" | "" => vec!["open", "ready", "waiting_approval", "snoozed", "applied", "dismissed"],
        _ => vec!["open", "ready", "waiting_approval"],
    };

    let mut items = autonomy_store::list_work_items_by_status(&state.db, business_id, &statuses, limit)
        .await
        .unwrap_or_default();

    if let Some(surface) = params.surface.as_deref() {
        if !surface.is_empty() {
            items.retain(|item| item.surface == surface);
        }
    }

    if let Some(severity) = params.severity.as_deref() {
        if !severity.is_empty() {
            items.retain(|item| item.risk_level == severity);
        }
    }

    let issues: Vec<Value> = items
        .into_iter()
        .map(|item| {
            let inputs: Value = serde_json::from_str(&item.inputs_json).unwrap_or_default();
            let amount = inputs.get("amount").and_then(amount_from_value);
            let currency = inputs
                .get("currency")
                .and_then(|v| v.as_str())
                .unwrap_or("USD");
            let estimated_impact = format_amount_with_currency(amount, currency);
            let issue_status = match item.status.as_str() {
                "snoozed" => "snoozed",
                "applied" | "dismissed" => "resolved",
                _ => "open",
            };

            json!({
                "id": item.id,
                "surface": item.surface,
                "severity": item.risk_level,
                "status": issue_status,
                "title": item.customer_title,
                "description": item.customer_summary,
                "recommended_action": item.customer_summary,
                "estimated_impact": estimated_impact,
                "run_type": item.work_type,
                "run_id": inputs.get("run_id").and_then(|v| v.as_i64()),
                "trace_id": inputs.get("trace_id").and_then(|v| v.as_str()),
                "created_at": item.created_at
            })
        })
        .collect();

    (
        StatusCode::OK,
        Json(json!({
            "issues": issues,
            "total": issues.len()
        })),
    )
}

/// PATCH /api/agentic/companion/issues/:id
/// Update companion issue status
pub async fn update_companion_issue(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(issue_id): Path<i64>,
    Json(payload): Json<IssueStatusPayload>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _ = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let target_status = match payload.status.as_str() {
        "snoozed" => "snoozed",
        "resolved" => "dismissed",
        _ => "open",
    };

    let exists = autonomy_store::work_item_by_id(&state.db, business_id, issue_id)
        .await
        .ok()
        .flatten()
        .is_some();

    if !exists {
        return (
            StatusCode::NOT_FOUND,
            Json(json!({ "ok": false, "error": "issue not found" })),
        );
    }

    let _ = autonomy_store::update_work_item_status(&state.db, issue_id, business_id, target_status).await;

    (
        StatusCode::OK,
        Json(json!({
            "ok": true,
            "id": issue_id,
            "status": payload.status
        })),
    )
}
