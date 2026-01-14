//! Onboarding API routes for Calm Companion Onboarding
//!
//! Endpoints:
//! - GET  /api/onboarding/profile     - Get current profile
//! - PUT  /api/onboarding/profile     - Partial merge update
//! - POST /api/onboarding/event       - Log analytics event
//! - POST /api/consents/grant         - Grant consent
//! - POST /api/consents/revoke        - Revoke consent
//! - POST /api/ai/handshake/confirm   - Store AI rules

use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    Json,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Sha256, Digest};

use crate::routes::auth::extract_claims_from_header;
use crate::AppState;

// =============================================================================
// Constants
// =============================================================================

/// Maximum size for profile_json in bytes (64KB)
const MAX_PROFILE_SIZE: usize = 65536;

/// Allowed keys in profile_json (stable schema)
const ALLOWED_PROFILE_KEYS: &[&str] = &[
    "business_name",
    "intent", 
    "industry",
    "entity_type",
    "fiscal_year_end",
    "data_source",
    "employee_count",
    "annual_revenue_bracket",
    "tax_registration",
    "accounting_method",
    // New fields for enhanced AI Companion context
    "business_age",
    "biggest_challenges",
    "current_tools",
    "bank_accounts_count",
    "monthly_transactions",
    "has_accountant",
    "accounting_frequency",
    "tax_concerns",
    "_inferred",
];

// =============================================================================
// Types
// =============================================================================

#[derive(Debug, Serialize)]
pub struct ApiError {
    pub error_code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<Vec<String>>,
}

impl ApiError {
    fn unauthorized() -> Self {
        Self {
            error_code: "UNAUTHORIZED".into(),
            message: "Authentication required".into(),
            details: None,
        }
    }

    fn validation(message: &str, details: Vec<String>) -> Self {
        Self {
            error_code: "VALIDATION_ERROR".into(),
            message: message.into(),
            details: Some(details),
        }
    }

    fn not_found(message: &str) -> Self {
        Self {
            error_code: "NOT_FOUND".into(),
            message: message.into(),
            details: None,
        }
    }

    fn internal(message: &str) -> Self {
        Self {
            error_code: "INTERNAL_ERROR".into(),
            message: message.into(),
            details: None,
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct ProfileUpdatePayload {
    pub profile: Value,
    #[serde(default)]
    pub current_step: Option<String>,
    #[serde(default)]
    pub onboarding_status: Option<String>,
    #[serde(default)]
    pub fast_path: Option<bool>,
}

#[derive(Debug, Deserialize)]
pub struct EventPayload {
    pub event_name: String,
    #[serde(default)]
    pub properties: Value,
    /// Optional client-generated ID for idempotency
    #[serde(default)]
    pub client_event_id: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ConsentPayload {
    pub consent_key: String,
    #[serde(default)]
    pub metadata: Value,
}

#[derive(Debug, Deserialize)]
pub struct AIHandshakePayload {
    pub rules: Vec<AIRuleInput>,
}

#[derive(Debug, Deserialize)]
pub struct AIRuleInput {
    pub rule_type: String,
    pub rule: Value,
    #[serde(default = "default_confidence")]
    pub confidence: f64,
}

fn default_confidence() -> f64 {
    1.0
}

#[derive(Debug, Serialize)]
pub struct ContextBuilderOutput {
    pub narrative_context_string: String,
    pub structured_context_json: Value,
    pub unknowns: Vec<String>,
}

// =============================================================================
// Helpers
// =============================================================================

fn resolve_business_id(headers: &HeaderMap) -> Option<i64> {
    extract_claims_from_header(headers)
        .ok()
        .and_then(|c| c.business_id)
}

fn resolve_user_id(headers: &HeaderMap) -> Option<i64> {
    extract_claims_from_header(headers)
        .ok()
        .and_then(|c| c.sub.parse::<i64>().ok())
}

/// Require both business_id and user_id from auth, or return an error response
fn require_auth(headers: &HeaderMap) -> Result<(i64, i64), (StatusCode, Json<Value>)> {
    let business_id = resolve_business_id(headers).ok_or_else(|| {
        (StatusCode::UNAUTHORIZED, Json(json!(ApiError::unauthorized())))
    })?;
    let user_id = resolve_user_id(headers).ok_or_else(|| {
        (StatusCode::UNAUTHORIZED, Json(json!(ApiError::unauthorized())))
    })?;
    Ok((business_id, user_id))
}

/// Deep merge two JSON objects, with `patch` values overwriting `base`
fn deep_merge(base: &mut Value, patch: &Value) {
    match (base, patch) {
        (Value::Object(base_map), Value::Object(patch_map)) => {
            for (key, patch_value) in patch_map {
                let base_value = base_map.entry(key.clone()).or_insert(Value::Null);
                deep_merge(base_value, patch_value);
            }
        }
        (base, patch) => {
            *base = patch.clone();
        }
    }
}

/// Validate profile keys against allowlist
fn validate_profile_keys(profile: &Value) -> Result<(), Vec<String>> {
    let obj = match profile.as_object() {
        Some(o) => o,
        None => return Ok(()), // Non-object is fine, will be handled elsewhere
    };

    let unknown_keys: Vec<String> = obj
        .keys()
        .filter(|k| !ALLOWED_PROFILE_KEYS.contains(&k.as_str()))
        .cloned()
        .collect();

    if unknown_keys.is_empty() {
        Ok(())
    } else {
        Err(unknown_keys)
    }
}

/// Compute a stable hash for rule deduplication
fn compute_rule_hash(rule_type: &str, rule_json: &Value) -> String {
    let mut hasher = Sha256::new();
    hasher.update(rule_type.as_bytes());
    hasher.update(b":");
    hasher.update(serde_json::to_string(rule_json).unwrap_or_default().as_bytes());
    format!("{:x}", hasher.finalize())
}

/// Build AI context from profile for companion injection
/// Safety: Never invents data, clearly marks unknowns, uses "likely" for inferred
pub fn build_context(profile_json: &Value) -> ContextBuilderOutput {
    let mut unknowns = Vec::new();
    let mut narrative_parts = Vec::new();

    // Helper to extract string field
    let get_str = |key: &str| -> Option<&str> {
        profile_json.get(key).and_then(|v| v.as_str()).filter(|s| !s.is_empty())
    };

    // Extract known fields - never invent defaults
    let business_name = get_str("business_name");
    let industry = get_str("industry");
    let intent = get_str("intent");
    let entity_type = get_str("entity_type");
    let fiscal_year_end = get_str("fiscal_year_end");
    
    // New fields for enhanced AI context
    let employee_count = get_str("employee_count");
    let business_age = get_str("business_age");
    let biggest_challenges = profile_json.get("biggest_challenges").and_then(|v| v.as_array());
    let current_tools = get_str("current_tools");
    let monthly_transactions = get_str("monthly_transactions");
    let has_accountant = profile_json.get("has_accountant").and_then(|v| v.as_bool());
    let accounting_frequency = get_str("accounting_frequency");

    // Check for inferred data
    let inferred = profile_json.get("_inferred").and_then(|v| v.as_object());

    // Build narrative with clear provenance
    if let Some(name) = business_name {
        narrative_parts.push(format!("Business: {}", name));
    } else {
        unknowns.push("business_name".to_string());
    }
    
    if let Some(ind) = industry {
        narrative_parts.push(format!("Industry: {}", ind));
    } else if let Some(inf) = inferred.and_then(|i| i.get("industry")).and_then(|v| v.as_str()) {
        // Mark inferred clearly
        narrative_parts.push(format!("Industry (likely): {}", inf));
    } else {
        unknowns.push("industry".to_string());
    }

    if let Some(int) = intent {
        narrative_parts.push(format!("Primary goal: {}", int));
    } else {
        unknowns.push("intent".to_string());
    }

    if let Some(entity) = entity_type {
        narrative_parts.push(format!("Entity type: {}", entity));
    }

    if let Some(fy) = fiscal_year_end {
        narrative_parts.push(format!("Fiscal year ends: {}", fy));
    }

    // New enhanced context fields
    if let Some(count) = employee_count {
        narrative_parts.push(format!("Team size: {}", count));
    }

    if let Some(age) = business_age {
        narrative_parts.push(format!("Business age: {}", age));
    }

    if let Some(challenges) = biggest_challenges {
        let challenge_strs: Vec<&str> = challenges
            .iter()
            .filter_map(|v| v.as_str())
            .collect();
        if !challenge_strs.is_empty() {
            narrative_parts.push(format!("Key challenges: {}", challenge_strs.join(", ")));
        }
    }

    if let Some(tools) = current_tools {
        narrative_parts.push(format!("Currently using: {}", tools));
    }

    if let Some(txns) = monthly_transactions {
        narrative_parts.push(format!("Monthly transaction volume: {}", txns));
    }

    if let Some(has_acc) = has_accountant {
        narrative_parts.push(format!("Has accountant: {}", if has_acc { "Yes" } else { "No" }));
    }

    if let Some(freq) = accounting_frequency {
        narrative_parts.push(format!("Accounting frequency: {}", freq));
    }

    let narrative_context_string = if narrative_parts.is_empty() {
        "No business profile information provided yet.".to_string()
    } else {
        narrative_parts.join(". ")
    };

    // Build structured output - only include what was provided
    let mut structured = serde_json::Map::new();
    if let Some(name) = business_name {
        structured.insert("business_name".to_string(), json!(name));
    }
    if let Some(ind) = industry {
        structured.insert("industry".to_string(), json!(ind));
    }
    if let Some(int) = intent {
        structured.insert("intent".to_string(), json!(int));
    }
    if let Some(entity) = entity_type {
        structured.insert("entity_type".to_string(), json!(entity));
    }
    if let Some(fy) = fiscal_year_end {
        structured.insert("fiscal_year_end".to_string(), json!(fy));
    }
    // New fields
    if let Some(count) = employee_count {
        structured.insert("employee_count".to_string(), json!(count));
    }
    if let Some(age) = business_age {
        structured.insert("business_age".to_string(), json!(age));
    }
    if let Some(challenges) = biggest_challenges {
        structured.insert("biggest_challenges".to_string(), json!(challenges));
    }
    if let Some(tools) = current_tools {
        structured.insert("current_tools".to_string(), json!(tools));
    }
    if let Some(txns) = monthly_transactions {
        structured.insert("monthly_transactions".to_string(), json!(txns));
    }
    if let Some(has_acc) = has_accountant {
        structured.insert("has_accountant".to_string(), json!(has_acc));
    }
    if let Some(freq) = accounting_frequency {
        structured.insert("accounting_frequency".to_string(), json!(freq));
    }
    if let Some(inf) = inferred {
        structured.insert("_inferred".to_string(), json!(inf));
    }

    ContextBuilderOutput {
        narrative_context_string,
        structured_context_json: Value::Object(structured),
        unknowns,
    }
}

// =============================================================================
// Route Handlers
// =============================================================================

/// GET /api/onboarding/profile
/// Returns profile for authenticated business only (tenant-isolated)
pub async fn get_profile(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> impl axum::response::IntoResponse {
    let (business_id, _user_id) = match require_auth(&headers) {
        Ok(ids) => ids,
        Err(resp) => return resp,
    };

    let result = sqlx::query_as::<_, (i64, String, String, String, Option<String>, bool, String, String)>(
        "SELECT id, profile_json, onboarding_version, onboarding_status, current_step, fast_path, created_at, updated_at 
         FROM business_profiles WHERE business_id = ?"
    )
    .bind(business_id)
    .fetch_optional(&state.db)
    .await;

    match result {
        Ok(Some((id, profile_json, version, status, step, fast_path, created, updated))) => {
            let profile: Value = serde_json::from_str(&profile_json).unwrap_or(json!({}));
            let context = build_context(&profile);

            (
                StatusCode::OK,
                Json(json!({
                    "ok": true,
                    "profile": {
                        "id": id,
                        "business_id": business_id,
                        "data": profile,
                        "onboarding_version": version,
                        "onboarding_status": status,
                        "current_step": step,
                        "fast_path": fast_path,
                        "created_at": created,
                        "updated_at": updated
                    },
                    "context": context
                })),
            )
        }
        Ok(None) => {
            // No profile exists yet - return empty with unknowns
            (
                StatusCode::OK,
                Json(json!({
                    "ok": true,
                    "profile": null,
                    "context": {
                        "narrative_context_string": "No business profile information provided yet.",
                        "structured_context_json": {},
                        "unknowns": ["business_name", "industry", "intent"]
                    }
                })),
            )
        }
        Err(e) => {
            tracing::error!("Failed to fetch profile: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!(ApiError::internal("Failed to fetch profile"))),
            )
        }
    }
}

/// PUT /api/onboarding/profile
/// Updates profile for authenticated business only (tenant-isolated)
pub async fn update_profile(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<ProfileUpdatePayload>,
) -> impl axum::response::IntoResponse {
    let (business_id, _user_id) = match require_auth(&headers) {
        Ok(ids) => ids,
        Err(resp) => return resp,
    };

    // Validate profile keys
    if let Err(unknown_keys) = validate_profile_keys(&payload.profile) {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!(ApiError::validation(
                "Unknown profile keys",
                unknown_keys
            ))),
        );
    }

    // Check max size
    let profile_str_check = serde_json::to_string(&payload.profile).unwrap_or_default();
    if profile_str_check.len() > MAX_PROFILE_SIZE {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!(ApiError::validation(
                "Profile data too large",
                vec![format!("Max size: {} bytes", MAX_PROFILE_SIZE)]
            ))),
        );
    }

    // Get existing profile or create new
    let existing = sqlx::query_scalar::<_, String>(
        "SELECT profile_json FROM business_profiles WHERE business_id = ?"
    )
    .bind(business_id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    let mut merged_profile: Value = existing
        .as_ref()
        .and_then(|s| serde_json::from_str(s).ok())
        .unwrap_or(json!({}));

    // Deep merge the incoming profile
    deep_merge(&mut merged_profile, &payload.profile);

    let profile_str = serde_json::to_string(&merged_profile).unwrap_or_else(|_| "{}".to_string());
    let now = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S").to_string();
    let variant = if payload.fast_path.unwrap_or(true) { "fast" } else { "guided" };

    let result = if existing.is_some() {
        // Update existing
        let mut query = String::from("UPDATE business_profiles SET profile_json = ?, updated_at = ?");
        let mut binds: Vec<String> = vec![profile_str.clone(), now.clone()];

        if let Some(step) = &payload.current_step {
            query.push_str(", current_step = ?");
            binds.push(step.clone());
        }
        if let Some(status) = &payload.onboarding_status {
            query.push_str(", onboarding_status = ?");
            binds.push(status.clone());
        }
        if let Some(fast) = payload.fast_path {
            query.push_str(", fast_path = ?, onboarding_variant = ?");
            binds.push(if fast { "1".to_string() } else { "0".to_string() });
            binds.push(variant.to_string());
        }
        query.push_str(" WHERE business_id = ?");

        let mut q = sqlx::query(&query);
        for bind in &binds {
            q = q.bind(bind);
        }
        q = q.bind(business_id);
        q.execute(&state.db).await
    } else {
        // Insert new
        let status = payload.onboarding_status.as_deref().unwrap_or("in_progress");
        let fast = payload.fast_path.unwrap_or(true);
        
        sqlx::query(
            "INSERT INTO business_profiles (business_id, profile_json, onboarding_status, current_step, fast_path, onboarding_variant, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
        .bind(business_id)
        .bind(&profile_str)
        .bind(status)
        .bind(&payload.current_step)
        .bind(fast)
        .bind(variant)
        .bind(&now)
        .bind(&now)
        .execute(&state.db)
        .await
    };

    match result {
        Ok(_) => {
            let context = build_context(&merged_profile);
            (
                StatusCode::OK,
                Json(json!({
                    "ok": true,
                    "profile": merged_profile,
                    "context": context,
                    "updated_at": now
                })),
            )
        }
        Err(e) => {
            tracing::error!("Failed to update profile: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!(ApiError::internal("Failed to update profile"))),
            )
        }
    }
}

/// POST /api/onboarding/event
/// Logs event for authenticated business/user (tenant-isolated)
/// Supports client_event_id for idempotency
pub async fn log_event(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<EventPayload>,
) -> impl axum::response::IntoResponse {
    let (business_id, user_id) = match require_auth(&headers) {
        Ok(ids) => ids,
        Err(resp) => return resp,
    };

    let properties_str = serde_json::to_string(&payload.properties).unwrap_or_else(|_| "{}".to_string());

    // If client_event_id provided, check for duplicate first
    if let Some(ref client_id) = payload.client_event_id {
        let exists = sqlx::query_scalar::<_, i64>(
            "SELECT 1 FROM onboarding_events WHERE business_id = ? AND client_event_id = ? LIMIT 1"
        )
        .bind(business_id)
        .bind(client_id)
        .fetch_optional(&state.db)
        .await
        .ok()
        .flatten();

        if exists.is_some() {
            // Idempotent: already logged
            return (
                StatusCode::OK,
                Json(json!({ "ok": true, "event": payload.event_name, "deduplicated": true })),
            );
        }
    }

    let result = sqlx::query(
        "INSERT INTO onboarding_events (business_id, user_id, event_name, properties_json, client_event_id)
         VALUES (?, ?, ?, ?, ?)"
    )
    .bind(business_id)
    .bind(user_id)
    .bind(&payload.event_name)
    .bind(&properties_str)
    .bind(&payload.client_event_id)
    .execute(&state.db)
    .await;

    match result {
        Ok(_) => (
            StatusCode::OK,
            Json(json!({ "ok": true, "event": payload.event_name })),
        ),
        Err(e) => {
            tracing::error!("Failed to log event: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!(ApiError::internal("Failed to log event"))),
            )
        }
    }
}

/// POST /api/consents/grant
/// Grants consent for authenticated business/user (tenant-isolated)
pub async fn grant_consent(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<ConsentPayload>,
) -> impl axum::response::IntoResponse {
    let (business_id, user_id) = match require_auth(&headers) {
        Ok(ids) => ids,
        Err(resp) => return resp,
    };

    let now = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S").to_string();
    let metadata_str = serde_json::to_string(&payload.metadata).unwrap_or_else(|_| "{}".to_string());

    let result = sqlx::query(
        "INSERT INTO consents (business_id, user_id, consent_key, status, granted_at, metadata_json)
         VALUES (?, ?, ?, 'granted', ?, ?)
         ON CONFLICT(business_id, user_id, consent_key) 
         DO UPDATE SET status = 'granted', granted_at = ?, revoked_at = NULL"
    )
    .bind(business_id)
    .bind(user_id)
    .bind(&payload.consent_key)
    .bind(&now)
    .bind(&metadata_str)
    .bind(&now)
    .execute(&state.db)
    .await;

    match result {
        Ok(_) => (
            StatusCode::OK,
            Json(json!({ 
                "ok": true, 
                "consent_key": payload.consent_key,
                "status": "granted",
                "granted_at": now
            })),
        ),
        Err(e) => {
            tracing::error!("Failed to grant consent: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!(ApiError::internal("Failed to grant consent"))),
            )
        }
    }
}

/// POST /api/consents/revoke
/// Revokes consent for authenticated business/user (tenant-isolated)
pub async fn revoke_consent(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<ConsentPayload>,
) -> impl axum::response::IntoResponse {
    let (business_id, user_id) = match require_auth(&headers) {
        Ok(ids) => ids,
        Err(resp) => return resp,
    };

    let now = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S").to_string();

    let result = sqlx::query(
        "UPDATE consents SET status = 'revoked', revoked_at = ?
         WHERE business_id = ? AND user_id = ? AND consent_key = ?"
    )
    .bind(&now)
    .bind(business_id)
    .bind(user_id)
    .bind(&payload.consent_key)
    .execute(&state.db)
    .await;

    match result {
        Ok(r) if r.rows_affected() > 0 => (
            StatusCode::OK,
            Json(json!({ 
                "ok": true, 
                "consent_key": payload.consent_key,
                "status": "revoked",
                "revoked_at": now
            })),
        ),
        Ok(_) => (
            StatusCode::NOT_FOUND,
            Json(json!(ApiError::not_found("Consent not found"))),
        ),
        Err(e) => {
            tracing::error!("Failed to revoke consent: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!(ApiError::internal("Failed to revoke consent"))),
            )
        }
    }
}

/// POST /api/ai/handshake/confirm
/// Stores AI rules for authenticated business (tenant-isolated)
/// Deduplicates rules by hash
pub async fn confirm_ai_handshake(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(payload): Json<AIHandshakePayload>,
) -> impl axum::response::IntoResponse {
    let (business_id, user_id) = match require_auth(&headers) {
        Ok(ids) => ids,
        Err(resp) => return resp,
    };

    let now = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S").to_string();
    let mut created_rules = Vec::new();
    let mut skipped_duplicates = 0;

    for rule_input in &payload.rules {
        let rule_str = serde_json::to_string(&rule_input.rule).unwrap_or_else(|_| "{}".to_string());
        let rule_hash = compute_rule_hash(&rule_input.rule_type, &rule_input.rule);

        // Check for existing rule with same hash
        let exists = sqlx::query_scalar::<_, i64>(
            "SELECT 1 FROM ai_rules WHERE business_id = ? AND rule_hash = ? LIMIT 1"
        )
        .bind(business_id)
        .bind(&rule_hash)
        .fetch_optional(&state.db)
        .await
        .ok()
        .flatten();

        if exists.is_some() {
            skipped_duplicates += 1;
            continue;
        }

        let result = sqlx::query(
            "INSERT INTO ai_rules (business_id, rule_type, rule_json, rule_hash, confidence, source, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, 'user_confirmed', ?, ?)"
        )
        .bind(business_id)
        .bind(&rule_input.rule_type)
        .bind(&rule_str)
        .bind(&rule_hash)
        .bind(rule_input.confidence)
        .bind(&now)
        .bind(&now)
        .execute(&state.db)
        .await;

        if result.is_ok() {
            created_rules.push(json!({
                "rule_type": rule_input.rule_type,
                "rule": rule_input.rule,
                "confidence": rule_input.confidence
            }));
        }
    }

    // Log the AI_Rule_Created event if we created any rules
    if !created_rules.is_empty() {
        let _ = sqlx::query(
            "INSERT INTO onboarding_events (business_id, user_id, event_name, properties_json)
             VALUES (?, ?, 'AI_Rule_Created', ?)"
        )
        .bind(business_id)
        .bind(user_id)
        .bind(serde_json::to_string(&json!({ 
            "rules_count": created_rules.len(),
            "skipped_duplicates": skipped_duplicates
        })).unwrap())
        .execute(&state.db)
        .await;
    }

    (
        StatusCode::OK,
        Json(json!({
            "ok": true,
            "created_rules": created_rules,
            "total": created_rules.len(),
            "skipped_duplicates": skipped_duplicates
        })),
    )
}

// =============================================================================
// Startup Safety
// =============================================================================

/// Verify onboarding tables exist. Returns error message if missing.
pub async fn verify_schema(pool: &sqlx::SqlitePool) -> Result<(), String> {
    let tables = ["business_profiles", "consents", "onboarding_events", "ai_rules"];
    
    for table in tables {
        let result = sqlx::query_scalar::<_, i64>(
            &format!("SELECT 1 FROM sqlite_master WHERE type='table' AND name='{}' LIMIT 1", table)
        )
        .fetch_optional(pool)
        .await
        .map_err(|e| format!("Failed to check table {}: {}", table, e))?;

        if result.is_none() {
            return Err(format!(
                "Required table '{}' not found. Please run migrations: sqlx migrate run",
                table
            ));
        }
    }
    
    Ok(())
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deep_merge_simple() {
        let mut base = json!({ "a": 1, "b": 2 });
        let patch = json!({ "b": 3, "c": 4 });
        deep_merge(&mut base, &patch);
        assert_eq!(base, json!({ "a": 1, "b": 3, "c": 4 }));
    }

    #[test]
    fn test_deep_merge_nested() {
        let mut base = json!({ "user": { "name": "Alice", "age": 30 } });
        let patch = json!({ "user": { "age": 31, "city": "NYC" } });
        deep_merge(&mut base, &patch);
        assert_eq!(base, json!({ "user": { "name": "Alice", "age": 31, "city": "NYC" } }));
    }

    #[test]
    fn test_deep_merge_preserves_unpatched() {
        let mut base = json!({ "a": { "b": 1, "c": 2 }, "d": 3 });
        let patch = json!({ "a": { "b": 10 } });
        deep_merge(&mut base, &patch);
        assert_eq!(base["a"]["b"], 10);
        assert_eq!(base["a"]["c"], 2);
        assert_eq!(base["d"], 3);
    }

    #[test]
    fn test_build_context_complete() {
        let profile = json!({
            "business_name": "Acme Corp",
            "industry": "Retail",
            "intent": "Track expenses",
            "entity_type": "LLC",
            "fiscal_year_end": "December"
        });
        let ctx = build_context(&profile);
        assert!(ctx.narrative_context_string.contains("Acme Corp"));
        assert!(ctx.narrative_context_string.contains("Retail"));
        assert!(ctx.unknowns.is_empty());
    }

    #[test]
    fn test_build_context_partial() {
        let profile = json!({
            "business_name": "Test Co"
        });
        let ctx = build_context(&profile);
        assert!(ctx.unknowns.contains(&"industry".to_string()));
        assert!(ctx.unknowns.contains(&"intent".to_string()));
    }

    #[test]
    fn test_build_context_empty_produces_all_unknowns() {
        let profile = json!({});
        let ctx = build_context(&profile);
        assert!(ctx.unknowns.contains(&"business_name".to_string()));
        assert!(ctx.unknowns.contains(&"industry".to_string()));
        assert!(ctx.unknowns.contains(&"intent".to_string()));
        assert!(ctx.narrative_context_string.contains("No business profile information"));
    }

    #[test]
    fn test_build_context_inferred_marked_likely() {
        let profile = json!({
            "business_name": "Test Co",
            "_inferred": {
                "industry": "Technology"
            }
        });
        let ctx = build_context(&profile);
        assert!(ctx.narrative_context_string.contains("likely"));
        assert!(!ctx.unknowns.contains(&"industry".to_string()));
    }

    #[test]
    fn test_validate_profile_keys_valid() {
        let profile = json!({
            "business_name": "Test",
            "industry": "Retail",
            "intent": "Track"
        });
        assert!(validate_profile_keys(&profile).is_ok());
    }

    #[test]
    fn test_validate_profile_keys_invalid() {
        let profile = json!({
            "business_name": "Test",
            "invalid_key": "value",
            "another_bad": 123
        });
        let result = validate_profile_keys(&profile);
        assert!(result.is_err());
        let unknown = result.unwrap_err();
        assert!(unknown.contains(&"invalid_key".to_string()));
        assert!(unknown.contains(&"another_bad".to_string()));
    }

    #[test]
    fn test_compute_rule_hash_deterministic() {
        let rule = json!({"vendor": "Shell", "category": "Gas"});
        let hash1 = compute_rule_hash("vendor_map", &rule);
        let hash2 = compute_rule_hash("vendor_map", &rule);
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_compute_rule_hash_different_for_different_types() {
        let rule = json!({"vendor": "Shell"});
        let hash1 = compute_rule_hash("vendor_map", &rule);
        let hash2 = compute_rule_hash("keyword_map", &rule);
        assert_ne!(hash1, hash2);
    }
}
