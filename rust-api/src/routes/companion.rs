//! AI Companion routes for Clover Books
//!
//! Native Rust endpoints for companion issues, high-risk audits, and radar data.
#![allow(dead_code)]

use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::AppState;
use crate::companion_autonomy::store as autonomy_store;
use crate::companion_autonomy::models::{BusinessPolicyRow, AiSettingsRow, WorkItem};
use crate::routes::auth::extract_claims_from_header;

// ============================================================================
// Security Helper
// ============================================================================

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

// ============================================================================
// Companion Issue Types
// ============================================================================

#[derive(Debug, Serialize)]
pub struct CompanionIssue {
    pub id: i64,
    pub surface: String,
    pub severity: String,
    pub status: String,
    pub title: String,
    pub description: String,
    pub recommended_action: String,
    pub estimated_impact: String,
    pub created_at: String,
}

#[derive(Debug, Serialize)]
pub struct CompanionIssuesResponse {
    pub ok: bool,
    pub issues: Vec<CompanionIssue>,
    pub total: i64,
    pub by_severity: SeverityCounts,
    pub by_surface: SurfaceCounts,
}

#[derive(Debug, Serialize, Default)]
pub struct SeverityCounts {
    pub high: i64,
    pub medium: i64,
    pub low: i64,
}

#[derive(Debug, Serialize, Default)]
pub struct SurfaceCounts {
    pub receipts: i64,
    pub invoices: i64,
    pub books: i64,
    pub bank: i64,
    pub tax: i64,
}

#[derive(Debug, Deserialize)]
pub struct CompanionIssueQuery {
    pub business_id: Option<i64>,
    pub status: Option<String>,
    pub severity: Option<String>,
    pub surface: Option<String>,
    #[serde(default = "default_limit")]
    pub limit: i64,
}

fn default_limit() -> i64 {
    50
}

// ============================================================================
// High-Risk Audit Types
// ============================================================================

#[derive(Debug, Serialize)]
pub struct HighRiskAudit {
    pub id: i64,
    pub risk_level: String,
    pub status: String,
    pub reason: String,
    pub target_type: String,
    pub target_id: i64,
    pub created_at: String,
    pub reviewed_by: Option<String>,
    pub reviewed_at: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct HighRiskAuditsResponse {
    pub ok: bool,
    pub audits: Vec<HighRiskAudit>,
    pub pending_count: i64,
    pub approved_count: i64,
    pub rejected_count: i64,
}

// ============================================================================
// Companion Radar Types
// ============================================================================

#[derive(Debug, Serialize)]
pub struct CompanionRadar {
    pub health_score: f64,
    pub coverage: RadarCoverage,
    pub alerts: Vec<RadarAlert>,
}

#[derive(Debug, Serialize)]
pub struct RadarCoverage {
    pub receipts: f64,
    pub invoices: f64,
    pub books: f64,
    pub bank: f64,
    pub tax: f64,
}

#[derive(Debug, Serialize)]
pub struct RadarAlert {
    pub surface: String,
    pub message: String,
    pub priority: i32,
}

// ============================================================================
// Route Handlers
// ============================================================================

/// GET /api/companion/issues
/// 
/// List companion issues for a business.
pub async fn list_issues(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<CompanionIssueQuery>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let status = params.status.as_deref().unwrap_or("open");
    let limit = params.limit;
    
    tracing::info!("Listing companion issues for business_id={}, status={}", business_id, status);
    
    // Get issues
    let issues = sqlx::query_as::<_, (i64, String, String, String, String, String, String, String, String)>(
        "SELECT id, surface, severity, status, title, description, 
                recommended_action, estimated_impact, created_at
         FROM core_companionissue 
         WHERE business_id = ? AND status = ?
         ORDER BY 
           CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
           created_at DESC
         LIMIT ?"
    )
    .bind(business_id)
    .bind(status)
    .bind(limit)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let total = issues.len() as i64;
    
    // Count by severity
    let mut by_severity = SeverityCounts::default();
    let mut by_surface = SurfaceCounts::default();
    
    let items: Vec<CompanionIssue> = issues
        .into_iter()
        .map(|(id, surface, severity, status, title, description, recommended_action, estimated_impact, created_at)| {
            // Count severity
            match severity.as_str() {
                "high" => by_severity.high += 1,
                "medium" => by_severity.medium += 1,
                _ => by_severity.low += 1,
            }
            // Count surface
            match surface.as_str() {
                "receipts" => by_surface.receipts += 1,
                "invoices" => by_surface.invoices += 1,
                "books" => by_surface.books += 1,
                "bank" => by_surface.bank += 1,
                "tax" => by_surface.tax += 1,
                _ => {}
            }
            
            CompanionIssue {
                id,
                surface,
                severity,
                status,
                title,
                description,
                recommended_action,
                estimated_impact,
                created_at,
            }
        })
        .collect();
    
    (
        StatusCode::OK,
        Json(CompanionIssuesResponse {
            ok: true,
            issues: items,
            total,
            by_severity,
            by_surface,
        }),
    )
}

/// POST /api/companion/issues/:id/dismiss
/// 
/// Dismiss a companion issue.
pub async fn dismiss_issue(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(issue_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    tracing::info!("Dismissing companion issue id={}", issue_id);
    
    let result = sqlx::query(
        "UPDATE core_companionissue
         SET status = 'dismissed', updated_at = datetime('now')
         WHERE id = ? AND business_id = ?"
    )
    .bind(issue_id)
    .bind(business_id)
    .execute(&state.db)
    .await;
    
    match result {
        Ok(r) if r.rows_affected() > 0 => {
            (StatusCode::OK, Json(serde_json::json!({
                "ok": true,
                "message": "Issue dismissed"
            })))
        }
        _ => {
            (StatusCode::NOT_FOUND, Json(serde_json::json!({
                "ok": false,
                "error": "Issue not found"
            })))
        }
    }
}

/// POST /api/companion/issues/:id/snooze
/// 
/// Snooze a companion issue.
pub async fn snooze_issue(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(issue_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    tracing::info!("Snoozing companion issue id={}", issue_id);
    
    let result = sqlx::query(
        "UPDATE core_companionissue
         SET status = 'snoozed', updated_at = datetime('now')
         WHERE id = ? AND business_id = ?"
    )
    .bind(issue_id)
    .bind(business_id)
    .execute(&state.db)
    .await;
    
    match result {
        Ok(r) if r.rows_affected() > 0 => {
            (StatusCode::OK, Json(serde_json::json!({
                "ok": true,
                "message": "Issue snoozed"
            })))
        }
        _ => {
            (StatusCode::NOT_FOUND, Json(serde_json::json!({
                "ok": false,
                "error": "Issue not found"
            })))
        }
    }
}

/// POST /api/companion/issues/:id/resolve
/// 
/// Mark a companion issue as resolved.
pub async fn resolve_issue(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(issue_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    tracing::info!("Resolving companion issue id={}", issue_id);
    
    let result = sqlx::query(
        "UPDATE core_companionissue
         SET status = 'resolved', updated_at = datetime('now')
         WHERE id = ? AND business_id = ?"
    )
    .bind(issue_id)
    .bind(business_id)
    .execute(&state.db)
    .await;
    
    match result {
        Ok(r) if r.rows_affected() > 0 => {
            (StatusCode::OK, Json(serde_json::json!({
                "ok": true,
                "message": "Issue resolved"
            })))
        }
        _ => {
            (StatusCode::NOT_FOUND, Json(serde_json::json!({
                "ok": false,
                "error": "Issue not found"
            })))
        }
    }
}

/// GET /api/companion/audits
/// 
/// List high-risk audits for a business.
pub async fn list_audits(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<AuditQuery>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    
    tracing::info!("Listing high-risk audits for business_id={}", business_id);
    
    let audits = sqlx::query_as::<_, (i64, String, String, String, String, i64, String, Option<i64>, Option<String>)>(
        "SELECT a.id, a.risk_level, a.status, a.reason, 
                ct.model as target_type, a.object_id, a.created_at,
                a.reviewed_by_id, a.reviewed_at
         FROM core_highriskaudit a
         JOIN django_content_type ct ON a.content_type_id = ct.id
         WHERE a.business_id = ?
         ORDER BY 
           CASE a.status WHEN 'pending' THEN 1 ELSE 2 END,
           CASE a.risk_level WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END,
           a.created_at DESC
         LIMIT 50"
    )
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let mut pending_count = 0i64;
    let mut approved_count = 0i64;
    let mut rejected_count = 0i64;
    
    let items: Vec<HighRiskAudit> = audits
        .into_iter()
        .map(|(id, risk_level, status, reason, target_type, target_id, created_at, _reviewed_by_id, reviewed_at)| {
            match status.as_str() {
                "pending" => pending_count += 1,
                "approved" => approved_count += 1,
                "rejected" => rejected_count += 1,
                _ => {}
            }
            
            HighRiskAudit {
                id,
                risk_level,
                status,
                reason,
                target_type,
                target_id,
                created_at,
                reviewed_by: None, // Would need user lookup
                reviewed_at,
            }
        })
        .collect();
    
    (
        StatusCode::OK,
        Json(HighRiskAuditsResponse {
            ok: true,
            audits: items,
            pending_count,
            approved_count,
            rejected_count,
        }),
    )
}

#[derive(Debug, Deserialize)]
pub struct AuditQuery {
    pub business_id: Option<i64>,
    pub status: Option<String>,
}

/// POST /api/companion/audits/:id/approve
/// 
/// Approve a high-risk audit.
pub async fn approve_audit(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(audit_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    tracing::info!("Approving audit id={}", audit_id);
    
    let result = sqlx::query(
        "UPDATE core_highriskaudit 
         SET status = 'approved', reviewed_at = datetime('now'), updated_at = datetime('now') 
         WHERE id = ? AND business_id = ?"
    )
    .bind(audit_id)
    .bind(business_id)
    .execute(&state.db)
    .await;
    
    match result {
        Ok(r) if r.rows_affected() > 0 => {
            (StatusCode::OK, Json(serde_json::json!({
                "ok": true,
                "message": "Audit approved"
            })))
        }
        _ => {
            (StatusCode::NOT_FOUND, Json(serde_json::json!({
                "ok": false,
                "error": "Audit not found"
            })))
        }
    }
}

/// POST /api/companion/audits/:id/reject
/// 
/// Reject a high-risk audit.
pub async fn reject_audit(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(audit_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    tracing::info!("Rejecting audit id={}", audit_id);
    
    let result = sqlx::query(
        "UPDATE core_highriskaudit 
         SET status = 'rejected', reviewed_at = datetime('now'), updated_at = datetime('now') 
         WHERE id = ? AND business_id = ?"
    )
    .bind(audit_id)
    .bind(business_id)
    .execute(&state.db)
    .await;
    
    match result {
        Ok(r) if r.rows_affected() > 0 => {
            (StatusCode::OK, Json(serde_json::json!({
                "ok": true,
                "message": "Audit rejected"
            })))
        }
        _ => {
            (StatusCode::NOT_FOUND, Json(serde_json::json!({
                "ok": false,
                "error": "Audit not found"
            })))
        }
    }
}

/// GET /api/companion/radar
/// 
/// Get companion radar data (health score, coverage, alerts).
pub async fn radar(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<RadarQuery>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    
    tracing::info!("Getting companion radar for business_id={}", business_id);
    
    // Count issues by surface area to determine coverage
    let surface_counts = sqlx::query_as::<_, (String, i64)>(
        "SELECT surface, COUNT(*) as count 
         FROM core_companionissue 
         WHERE business_id = ? AND status = 'open'
         GROUP BY surface"
    )
    .bind(business_id)
    .fetch_all(&state.db)
    .await
    .unwrap_or_default();
    
    let mut coverage = RadarCoverage {
        receipts: 100.0,
        invoices: 100.0,
        books: 100.0,
        bank: 100.0,
        tax: 100.0,
    };
    
    let mut alerts = Vec::new();
    let mut total_issues = 0i64;
    
    for (surface, count) in surface_counts {
        total_issues += count;
        // Reduce coverage based on issue count
        let reduction = (count as f64 * 10.0).min(50.0);
        match surface.as_str() {
            "receipts" => {
                coverage.receipts -= reduction;
                if count > 0 {
                    alerts.push(RadarAlert {
                        surface: "receipts".to_string(),
                        message: format!("{} receipt issues need attention", count),
                        priority: count as i32,
                    });
                }
            }
            "invoices" => {
                coverage.invoices -= reduction;
                if count > 0 {
                    alerts.push(RadarAlert {
                        surface: "invoices".to_string(),
                        message: format!("{} invoice issues need attention", count),
                        priority: count as i32,
                    });
                }
            }
            "books" => {
                coverage.books -= reduction;
                if count > 0 {
                    alerts.push(RadarAlert {
                        surface: "books".to_string(),
                        message: format!("{} book issues need attention", count),
                        priority: count as i32,
                    });
                }
            }
            "bank" => {
                coverage.bank -= reduction;
                if count > 0 {
                    alerts.push(RadarAlert {
                        surface: "bank".to_string(),
                        message: format!("{} bank reconciliation issues", count),
                        priority: count as i32,
                    });
                }
            }
            "tax" => {
                coverage.tax -= reduction;
                if count > 0 {
                    alerts.push(RadarAlert {
                        surface: "tax".to_string(),
                        message: format!("{} tax compliance issues", count),
                        priority: count as i32,
                    });
                }
            }
            _ => {}
        }
    }
    
    // Calculate health score (average coverage minus penalty for issues)
    let avg_coverage = (coverage.receipts + coverage.invoices + coverage.books + coverage.bank + coverage.tax) / 5.0;
    let health_score = (avg_coverage - (total_issues as f64 * 2.0)).max(0.0);
    
    // Sort alerts by priority (highest first)
    alerts.sort_by(|a, b| b.priority.cmp(&a.priority));
    
    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok": true,
            "radar": CompanionRadar {
                health_score,
                coverage,
                alerts,
            }
        })),
    )
}

#[derive(Debug, Deserialize)]
pub struct RadarQuery {
    pub business_id: Option<i64>,
}

// ============================================================================
// Companion v2 Shadow Events API (for Control Tower)
// ============================================================================

#[derive(Debug, Deserialize)]
pub struct ShadowEventsQuery {
    pub status: Option<String>,
    pub limit: Option<i64>,
    pub event_type: Option<String>,
    pub subject_object_id: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub struct SettingsQuery {
    pub workspace_id: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub struct AiSettingsPatch {
    pub ai_enabled: Option<bool>,
    pub kill_switch: Option<bool>,
    pub ai_mode: Option<String>,
    pub velocity_limit_per_minute: Option<i64>,
    pub value_breaker_threshold: Option<String>,
    pub anomaly_stddev_threshold: Option<String>,
    pub trust_downgrade_rejection_rate: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct BusinessPolicyPatch {
    pub materiality_threshold: Option<String>,
    pub risk_appetite: Option<String>,
    pub commingling_risk_vendors: Option<Vec<String>>,
    pub related_entities: Option<Vec<Value>>,
    pub intercompany_enabled: Option<bool>,
    pub sector_archetype: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ProposalApplyPayload {
    pub workspace_id: Option<i64>,
    pub override_splits: Option<Vec<Value>>,
}

#[derive(Debug, Deserialize)]
pub struct ProposalRejectPayload {
    pub workspace_id: Option<i64>,
    pub reason: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ProposalsQuery {
    pub workspace_id: Option<i64>,
    pub event_type: Option<String>,
    pub subject_object_id: Option<i64>,
    pub limit: Option<i64>,
}

fn parse_string_vec(raw: &str) -> Vec<String> {
    serde_json::from_str(raw).unwrap_or_default()
}

fn parse_value_vec(raw: &str) -> Vec<Value> {
    serde_json::from_str(raw).unwrap_or_default()
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
    pool: &sqlx::SqlitePool,
    business_id: i64,
) -> Result<AiSettingsRow, sqlx::Error> {
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

async fn ensure_business_policy(
    pool: &sqlx::SqlitePool,
    business_id: i64,
) -> Result<BusinessPolicyRow, sqlx::Error> {
    if let Some(policy) = autonomy_store::fetch_business_policy(pool, business_id).await? {
        return Ok(policy);
    }
    let commingling = serde_json::to_string(&Vec::<String>::new()).unwrap_or_else(|_| "[]".to_string());
    let related = serde_json::to_string(&Vec::<Value>::new()).unwrap_or_else(|_| "[]".to_string());
    autonomy_store::upsert_business_policy(
        pool,
        business_id,
        "1000",
        "standard",
        &commingling,
        &related,
        false,
        "general",
    )
    .await
}

fn ai_settings_payload(global_ai_enabled: bool, settings: &AiSettingsRow) -> Value {
    json!({
        "global_ai_enabled": global_ai_enabled,
        "settings": {
            "ai_enabled": settings.ai_enabled,
            "kill_switch": settings.kill_switch,
            "ai_mode": settings.ai_mode,
            "velocity_limit_per_minute": settings.velocity_limit_per_minute,
            "value_breaker_threshold": settings.value_breaker_threshold,
            "anomaly_stddev_threshold": settings.anomaly_stddev_threshold,
            "trust_downgrade_rejection_rate": settings.trust_downgrade_rejection_rate,
            "updated_at": settings.updated_at,
            "created_at": settings.created_at
        }
    })
}

fn business_policy_payload(policy: &BusinessPolicyRow) -> Value {
    json!({
        "materiality_threshold": policy.materiality_threshold,
        "risk_appetite": policy.risk_appetite,
        "commingling_risk_vendors": parse_string_vec(&policy.commingling_risk_vendors_json),
        "related_entities": parse_value_vec(&policy.related_entities_json),
        "intercompany_enabled": policy.intercompany_enabled,
        "sector_archetype": policy.sector_archetype,
        "updated_at": policy.updated_at,
        "created_at": policy.created_at
    })
}

// ========================================================================
// Companion v2 Settings & Policy API
// ========================================================================

/// GET /api/companion/v2/settings/
pub async fn get_ai_settings_v2(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(_params): Query<SettingsQuery>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let global_enabled = match autonomy_store::business_ai_enabled(&state.db, business_id).await {
        Ok(Some(value)) => value,
        Ok(None) => {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({ "ok": false, "error": "business not found" })),
            );
        }
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "ok": false, "error": "failed to load business" })),
            );
        }
    };

    let settings = match ensure_ai_settings(&state.db, business_id).await {
        Ok(settings) => settings,
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "ok": false, "error": "failed to load settings" })),
            );
        }
    };

    (StatusCode::OK, Json(ai_settings_payload(global_enabled, &settings)))
}

/// PATCH /api/companion/v2/settings/
pub async fn patch_ai_settings_v2(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(_params): Query<SettingsQuery>,
    Json(patch): Json<AiSettingsPatch>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let global_enabled = autonomy_store::business_ai_enabled(&state.db, business_id)
        .await
        .ok()
        .flatten()
        .unwrap_or(false);

    let current = match ensure_ai_settings(&state.db, business_id).await {
        Ok(settings) => settings,
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "ok": false, "error": "failed to load settings" })),
            );
        }
    };

    let ai_enabled = patch.ai_enabled.unwrap_or(current.ai_enabled);
    let kill_switch = patch.kill_switch.unwrap_or(current.kill_switch);
    let ai_mode = patch.ai_mode.unwrap_or(current.ai_mode);
    let velocity_limit_per_minute = patch
        .velocity_limit_per_minute
        .unwrap_or(current.velocity_limit_per_minute);
    let value_breaker_threshold = patch
        .value_breaker_threshold
        .unwrap_or(current.value_breaker_threshold);
    let anomaly_stddev_threshold = patch
        .anomaly_stddev_threshold
        .unwrap_or(current.anomaly_stddev_threshold);
    let trust_downgrade_rejection_rate = patch
        .trust_downgrade_rejection_rate
        .unwrap_or(current.trust_downgrade_rejection_rate);

    let updated = match autonomy_store::upsert_ai_settings(
        &state.db,
        business_id,
        ai_enabled,
        kill_switch,
        &ai_mode,
        velocity_limit_per_minute,
        &value_breaker_threshold,
        &anomaly_stddev_threshold,
        &trust_downgrade_rejection_rate,
    )
    .await
    {
        Ok(settings) => settings,
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "ok": false, "error": "failed to update settings" })),
            );
        }
    };

    (StatusCode::OK, Json(ai_settings_payload(global_enabled, &updated)))
}

/// GET /api/companion/v2/policy/
pub async fn get_business_policy_v2(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let policy = match ensure_business_policy(&state.db, business_id).await {
        Ok(policy) => policy,
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "ok": false, "error": "failed to load policy" })),
            );
        }
    };

    (StatusCode::OK, Json(business_policy_payload(&policy)))
}

/// PATCH /api/companion/v2/policy/
pub async fn patch_business_policy_v2(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(patch): Json<BusinessPolicyPatch>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let current = match ensure_business_policy(&state.db, business_id).await {
        Ok(policy) => policy,
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "ok": false, "error": "failed to load policy" })),
            );
        }
    };

    let materiality_threshold = patch
        .materiality_threshold
        .unwrap_or(current.materiality_threshold);
    let risk_appetite = patch.risk_appetite.unwrap_or(current.risk_appetite);
    let commingling_risk_vendors = patch
        .commingling_risk_vendors
        .unwrap_or_else(|| parse_string_vec(&current.commingling_risk_vendors_json));
    let related_entities = patch
        .related_entities
        .unwrap_or_else(|| parse_value_vec(&current.related_entities_json));
    let intercompany_enabled = patch.intercompany_enabled.unwrap_or(current.intercompany_enabled);
    let sector_archetype = patch.sector_archetype.unwrap_or(current.sector_archetype);

    let commingling_json = serde_json::to_string(&commingling_risk_vendors).unwrap_or_else(|_| "[]".to_string());
    let related_json = serde_json::to_string(&related_entities).unwrap_or_else(|_| "[]".to_string());

    let updated = match autonomy_store::upsert_business_policy(
        &state.db,
        business_id,
        &materiality_threshold,
        &risk_appetite,
        &commingling_json,
        &related_json,
        intercompany_enabled,
        &sector_archetype,
    )
    .await
    {
        Ok(policy) => policy,
        Err(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "ok": false, "error": "failed to update policy" })),
            );
        }
    };

    (StatusCode::OK, Json(business_policy_payload(&updated)))
}

// ========================================================================
// Companion v2 Proposals API (customer-facing)
// ========================================================================

/// GET /api/companion/v2/proposals/
pub async fn list_proposals(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<ProposalsQuery>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let limit = params.limit.unwrap_or(200);
    let event_list = fetch_shadow_events(
        &state.db,
        business_id,
        "proposed",
        limit,
        params.event_type.as_deref(),
        params.subject_object_id,
    )
    .await;

    (StatusCode::OK, Json(event_list))
}

/// POST /api/companion/v2/proposals/:id/apply/
pub async fn apply_proposal(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<i64>,
    Json(_payload): Json<ProposalApplyPayload>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let action = autonomy_store::action_for_work_item(&state.db, business_id, event_id)
        .await
        .ok()
        .flatten();
    let action_id = match action.as_ref().map(|a| a.id) {
        Some(id) => id,
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({ "ok": false, "error": "proposal not found" })),
            );
        }
    };

    let allowed = crate::routes::companion_autonomy::can_apply_action(&state.db, business_id, action_id)
        .await
        .unwrap_or(false);
    if !allowed {
        return (
            StatusCode::FORBIDDEN,
            Json(json!({ "ok": false, "error": "approval required" })),
        );
    }

    let applied = autonomy_store::apply_action(&state.db, business_id, action_id)
        .await
        .unwrap_or(false);
    if applied {
        let _ = autonomy_store::update_work_item_status(&state.db, event_id, business_id, "applied").await;
    }

    let updated_item = autonomy_store::work_item_by_id(&state.db, business_id, event_id)
        .await
        .ok()
        .flatten();
    let event = updated_item
        .as_ref()
        .map(|item| build_shadow_event(item, action.as_ref()))
        .unwrap_or_else(|| json!({}));

    (StatusCode::OK, Json(json!({ "shadow_event": event, "result": { "applied": applied } })))
}

/// POST /api/companion/v2/proposals/:id/reject/
pub async fn reject_proposal(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<i64>,
    Json(_payload): Json<ProposalRejectPayload>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let exists = autonomy_store::work_item_by_id(&state.db, business_id, event_id)
        .await
        .ok()
        .flatten();

    if exists.is_none() {
        return (
            StatusCode::NOT_FOUND,
            Json(json!({ "ok": false, "error": "proposal not found" })),
        );
    }

    let _ = autonomy_store::dismiss_work_item(&state.db, business_id, event_id)
        .await
        .unwrap_or(false);

    let updated_item = autonomy_store::work_item_by_id(&state.db, business_id, event_id)
        .await
        .ok()
        .flatten();
    let action = autonomy_store::action_for_work_item(&state.db, business_id, event_id)
        .await
        .ok()
        .flatten();
    let event = updated_item
        .as_ref()
        .map(|item| build_shadow_event(item, action.as_ref()))
        .unwrap_or_else(|| json!({}));

    (StatusCode::OK, Json(event))
}

/// GET /api/companion/v2/shadow-events/
/// 
/// List shadow events (AI suggestions) for the Control Tower.
/// Reads from companion_autonomy_work_items (CAE) to keep Rust-first sources.
pub async fn list_shadow_events(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<ShadowEventsQuery>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let status = params.status.as_deref().unwrap_or("proposed");
    let limit = params.limit.unwrap_or(50);
    let event_list = fetch_shadow_events(
        &state.db,
        business_id,
        status,
        limit,
        params.event_type.as_deref(),
        params.subject_object_id,
    )
    .await;
    let total = event_list.len();

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "proposals": event_list,
            "total": total,
            "status": status
        })),
    )
}

async fn fetch_shadow_events(
    pool: &sqlx::SqlitePool,
    business_id: i64,
    status: &str,
    limit: i64,
    event_type: Option<&str>,
    subject_object_id: Option<i64>,
) -> Vec<serde_json::Value> {
    let statuses = work_item_statuses_for_shadow_status(status);
    let mut items = autonomy_store::list_work_items_by_status(pool, business_id, &statuses, limit)
        .await
        .unwrap_or_default();

    if let Some(event_type) = event_type {
        let work_type = work_type_for_event_type(event_type);
        if let Some(work_type) = work_type {
            items.retain(|item| item.work_type == work_type);
        }
    }

    if let Some(subject_id) = subject_object_id {
        items.retain(|item| {
            serde_json::from_str::<serde_json::Value>(&item.inputs_json)
                .ok()
                .and_then(|v| {
                    v.get("transaction_id")
                        .and_then(|id| id.as_i64())
                        .or_else(|| v.get("document_id").and_then(|id| id.as_i64()))
                        .or_else(|| v.get("receipt_document_id").and_then(|id| id.as_i64()))
                        .or_else(|| v.get("invoice_document_id").and_then(|id| id.as_i64()))
                })
                .map(|id| id == subject_id)
                .unwrap_or(false)
        });
    }

    let mut event_list = Vec::new();
    for item in items {
        let action = autonomy_store::action_for_work_item(pool, business_id, item.id)
            .await
            .ok()
            .flatten();
        event_list.push(build_shadow_event(&item, action.as_ref()));
    }
    event_list
}

/// POST /api/companion/v2/shadow-events/:id/apply/
/// 
/// Apply (accept) a shadow event suggestion.
pub async fn apply_shadow_event(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    tracing::info!("Applying shadow event id={}", event_id);

    let action = autonomy_store::action_for_work_item(&state.db, business_id, event_id)
        .await
        .ok()
        .flatten();
    let action_id = match action.as_ref().map(|a| a.id) {
        Some(id) => id,
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(serde_json::json!({
                    "ok": false,
                    "error": "Shadow event not found"
                })),
            );
        }
    };

    let allowed = crate::routes::companion_autonomy::can_apply_action(&state.db, business_id, action_id)
        .await
        .unwrap_or(false);
    if !allowed {
        return (
            StatusCode::FORBIDDEN,
            Json(serde_json::json!({
                "ok": false,
                "error": "approval required"
            })),
        );
    }

    let applied = autonomy_store::apply_action(&state.db, business_id, action_id)
        .await
        .unwrap_or(false);
    if applied {
        let _ = autonomy_store::update_work_item_status(&state.db, event_id, business_id, "applied").await;
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok": true,
            "applied": applied
        })),
    )
}

/// POST /api/companion/v2/shadow-events/:id/reject/
/// 
/// Reject a shadow event suggestion.
pub async fn reject_shadow_event(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(event_id): Path<i64>,
) -> impl IntoResponse {
    let business_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let _actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    tracing::info!("Rejecting shadow event id={}", event_id);

    let dismissed = autonomy_store::dismiss_work_item(&state.db, business_id, event_id)
        .await
        .unwrap_or(false);

    if dismissed {
        return (
            StatusCode::OK,
            Json(serde_json::json!({
                "ok": true,
                "message": "Suggestion rejected"
            })),
        );
    }

    (
        StatusCode::NOT_FOUND,
        Json(serde_json::json!({
            "ok": false,
            "error": "Shadow event not found"
        })),
    )
}

fn work_item_statuses_for_shadow_status(status: &str) -> Vec<&'static str> {
    match status.to_lowercase().as_str() {
        "applied" | "accepted" => vec!["applied"],
        "rejected" | "dismissed" => vec!["dismissed"],
        "snoozed" => vec!["snoozed"],
        _ => vec!["open", "ready", "waiting_approval"],
    }
}

fn work_type_for_event_type(event_type: &str) -> Option<&'static str> {
    let normalized = event_type.to_lowercase();
    if normalized.contains("bankmatch") || normalized.contains("match_bank") {
        Some("match_bank")
    } else if normalized.contains("categorization") || normalized.contains("categorize_tx") {
        Some("categorize_tx")
    } else {
        None
    }
}

fn build_shadow_event(
    item: &WorkItem,
    action: Option<&crate::companion_autonomy::models::ActionRecommendation>,
) -> serde_json::Value {
    let inputs: serde_json::Value = serde_json::from_str(&item.inputs_json).unwrap_or_default();
    let links: serde_json::Value = serde_json::from_str(&item.links_json).unwrap_or_default();
    let target_url = links.get("target_url").and_then(|v| v.as_str()).unwrap_or("/banking");
    let event_type = match item.work_type.as_str() {
        "match_bank" => "BankMatchProposed",
        "categorize_tx" => "CategorizationProposed",
        _ => "WorkItemProposed",
    };
    let status = match item.status.as_str() {
        "applied" => "applied",
        "dismissed" => "rejected",
        _ => "proposed",
    };
    let risk_tier = match item.risk_level.as_str() {
        "high" => 2,
        "medium" => 1,
        _ => 0,
    };
    let mut risk_reasons = Vec::new();
    if item.requires_approval {
        risk_reasons.push("approval_required");
    }
    if item.risk_level == "high" {
        risk_reasons.push("high_risk");
    }
    let action_kind = action
        .map(|a| a.action_kind.as_str())
        .unwrap_or(if item.requires_approval || item.risk_level == "high" { "review" } else { "apply" });
    let preview_effects = action
        .and_then(|a| serde_json::from_str::<serde_json::Value>(&a.preview_effects_json).ok())
        .unwrap_or_else(|| serde_json::json!([item.customer_summary]));

    serde_json::json!({
        "id": item.id.to_string(),
        "event_type": event_type,
        "status": status,
        "bank_transaction": inputs.get("transaction_id"),
        "source_command": null,
        "data": {
            "transaction_id": inputs.get("transaction_id"),
            "bank_transaction_description": inputs.get("description"),
            "bank_transaction_amount": inputs.get("amount"),
            "date": inputs.get("date"),
            "surface": item.surface,
            "target_url": target_url,
            "preview_effects": preview_effects
        },
        "actor": "system_companion_v1",
        "confidence_score": format!("{:.2}", item.confidence_score),
        "logic_trace_id": item.dedupe_key,
        "rationale": item.customer_summary,
        "business_profile_constraint": "default",
        "human_in_the_loop": {
            "tier": risk_tier,
            "status": status,
            "risk_reasons": risk_reasons
        },
        "metadata": {
            "proposal_group": item.work_type
        },
        "customer_action_kind": action_kind,
        "risk_level": item.risk_level,
        "created_at": item.created_at,
        "updated_at": item.updated_at
    })
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // =========================================================================
    // SeverityCounts Tests
    // =========================================================================

    #[test]
    fn test_severity_counts_default() {
        let counts = SeverityCounts::default();
        assert_eq!(counts.high, 0);
        assert_eq!(counts.medium, 0);
        assert_eq!(counts.low, 0);
    }

    #[test]
    fn test_severity_counts_serialization() {
        let counts = SeverityCounts {
            high: 5,
            medium: 10,
            low: 15,
        };
        
        let json = serde_json::to_string(&counts).unwrap();
        assert!(json.contains("\"high\":5"));
        assert!(json.contains("\"medium\":10"));
        assert!(json.contains("\"low\":15"));
    }

    // =========================================================================
    // SurfaceCounts Tests
    // =========================================================================

    #[test]
    fn test_surface_counts_default() {
        let counts = SurfaceCounts::default();
        assert_eq!(counts.receipts, 0);
        assert_eq!(counts.invoices, 0);
        assert_eq!(counts.books, 0);
        assert_eq!(counts.bank, 0);
        assert_eq!(counts.tax, 0);
    }

    #[test]
    fn test_surface_counts_serialization() {
        let counts = SurfaceCounts {
            receipts: 2,
            invoices: 4,
            books: 1,
            bank: 3,
            tax: 0,
        };
        
        let json = serde_json::to_string(&counts).unwrap();
        assert!(json.contains("\"receipts\":2"));
        assert!(json.contains("\"bank\":3"));
    }

    // =========================================================================
    // RadarCoverage Tests
    // =========================================================================

    #[test]
    fn test_radar_coverage_serialization() {
        let coverage = RadarCoverage {
            receipts: 95.5,
            invoices: 88.0,
            books: 100.0,
            bank: 75.5,
            tax: 90.0,
        };
        
        let json = serde_json::to_string(&coverage).unwrap();
        assert!(json.contains("\"receipts\":95.5"));
        assert!(json.contains("\"books\":100"));
    }

    #[test]
    fn test_radar_alert_serialization() {
        let alert = RadarAlert {
            surface: "invoices".to_string(),
            message: "3 overdue invoices".to_string(),
            priority: 3,
        };
        
        let json = serde_json::to_string(&alert).unwrap();
        assert!(json.contains("\"surface\":\"invoices\""));
        assert!(json.contains("\"priority\":3"));
    }

    // =========================================================================
    // CompanionIssue Tests
    // =========================================================================

    #[test]
    fn test_companion_issue_serialization() {
        let issue = CompanionIssue {
            id: 42,
            surface: "receipts".to_string(),
            severity: "high".to_string(),
            status: "open".to_string(),
            title: "Missing receipt".to_string(),
            description: "Receipt for transaction not found".to_string(),
            recommended_action: "Upload receipt".to_string(),
            estimated_impact: "$150.00".to_string(),
            created_at: "2024-01-15T10:00:00Z".to_string(),
        };
        
        let json = serde_json::to_string(&issue).unwrap();
        assert!(json.contains("\"id\":42"));
        assert!(json.contains("\"severity\":\"high\""));
        assert!(json.contains("\"surface\":\"receipts\""));
    }

    // =========================================================================
    // HighRiskAudit Tests
    // =========================================================================

    #[test]
    fn test_high_risk_audit_serialization() {
        let audit = HighRiskAudit {
            id: 100,
            risk_level: "critical".to_string(),
            status: "pending".to_string(),
            reason: "Large transaction detected".to_string(),
            target_type: "invoice".to_string(),
            target_id: 555,
            created_at: "2024-01-20T15:30:00Z".to_string(),
            reviewed_by: None,
            reviewed_at: None,
        };
        
        let json = serde_json::to_string(&audit).unwrap();
        assert!(json.contains("\"risk_level\":\"critical\""));
        assert!(json.contains("\"status\":\"pending\""));
        assert!(json.contains("\"target_id\":555"));
    }

    // =========================================================================
    // Query Deserialization Tests
    // =========================================================================

    #[test]
    fn test_companion_issue_query_defaults() {
        let json = r#"{}"#;
        let query: CompanionIssueQuery = serde_json::from_str(json).unwrap();
        
        assert!(query.business_id.is_none());
        assert!(query.status.is_none());
        assert!(query.severity.is_none());
        assert_eq!(query.limit, 50); // Default
    }

    #[test]
    fn test_companion_issue_query_with_params() {
        let json = r#"{"business_id": 123, "status": "open", "severity": "high", "limit": 10}"#;
        let query: CompanionIssueQuery = serde_json::from_str(json).unwrap();
        
        assert_eq!(query.business_id, Some(123));
        assert_eq!(query.status, Some("open".to_string()));
        assert_eq!(query.severity, Some("high".to_string()));
        assert_eq!(query.limit, 10);
    }

    #[test]
    fn test_radar_query_deserialization() {
        let json = r#"{"business_id": 456}"#;
        let query: RadarQuery = serde_json::from_str(json).unwrap();
        
        assert_eq!(query.business_id, Some(456));
    }

    #[test]
    fn test_audit_query_deserialization() {
        let json = r#"{"business_id": 789, "status": "pending"}"#;
        let query: AuditQuery = serde_json::from_str(json).unwrap();
        
        assert_eq!(query.business_id, Some(789));
        assert_eq!(query.status, Some("pending".to_string()));
    }

    // =========================================================================
    // Response Structure Tests
    // =========================================================================

    #[test]
    fn test_issues_response_structure() {
        let response = CompanionIssuesResponse {
            ok: true,
            issues: vec![],
            total: 0,
            by_severity: SeverityCounts::default(),
            by_surface: SurfaceCounts::default(),
        };
        
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("\"ok\":true"));
        assert!(json.contains("\"issues\":[]"));
        assert!(json.contains("\"total\":0"));
    }

    #[test]
    fn test_audits_response_structure() {
        let response = HighRiskAuditsResponse {
            ok: true,
            audits: vec![],
            pending_count: 5,
            approved_count: 10,
            rejected_count: 2,
        };
        
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("\"pending_count\":5"));
        assert!(json.contains("\"approved_count\":10"));
        assert!(json.contains("\"rejected_count\":2"));
    }
}
