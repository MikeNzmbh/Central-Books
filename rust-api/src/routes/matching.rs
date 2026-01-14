//! Native Bank Matching Engine for Clover Books
//!
//! 100% Rust implementation of the 3-tier matching algorithm.
//! Replaces the legacy bank matching module entirely.

#![allow(dead_code)]

use axum::{
    extract::{Json, Path, State},
    http::StatusCode,
    response::IntoResponse,
};
use regex::Regex;
use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;

use crate::AppState;

// ============================================================================
// Configuration
// ============================================================================

pub struct MatchingConfig;

impl MatchingConfig {
    pub const DATE_LOOKBACK_DAYS: i64 = 90;
    pub const EXTENDED_LOOKBACK_DAYS: i64 = 180;
    pub const CONFIDENCE_TIER1: f64 = 1.00;
    pub const CONFIDENCE_TIER2: f64 = 0.95;
    pub const CONFIDENCE_TIER3_SINGLE: f64 = 0.80;
    pub const CONFIDENCE_TIER3_AMBIGUOUS: f64 = 0.50;
    pub const DEFAULT_MAX_CANDIDATES: i64 = 5;
    pub const AMOUNT_TOLERANCE: f64 = 0.01;
}

// ============================================================================
// Types
// ============================================================================

#[derive(Debug, Serialize, Deserialize)]
pub struct FindMatchesRequest {
    pub bank_transaction_id: i64,
    #[serde(default = "default_limit")]
    pub limit: i64,
    #[serde(default)]
    pub extended_lookback: bool,
}

fn default_limit() -> i64 {
    5
}

#[derive(Debug, Serialize, Clone)]
pub struct MatchCandidate {
    pub match_type: String,
    pub confidence: f64,
    pub reason: String,
    pub journal_entry_id: Option<i64>,
    pub rule_id: Option<i64>,
    pub invoice_id: Option<i64>,
    pub expense_id: Option<i64>,
    pub auto_confirm: bool,
}

#[derive(Debug, Serialize)]
pub struct FindMatchesResponse {
    pub ok: bool,
    pub matches: Vec<MatchCandidate>,
    pub bank_transaction_id: i64,
    pub error: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct ConfirmMatchRequest {
    pub bank_transaction_id: i64,
    pub journal_entry_id: i64,
    pub match_confidence: f64,
    #[serde(default)]
    pub adjustment_amount: Option<f64>,
    #[serde(default)]
    pub adjustment_account_id: Option<i64>,
}

#[derive(Debug, Serialize)]
pub struct ConfirmMatchResponse {
    pub ok: bool,
    pub bank_transaction_id: i64,
    pub status: String,
    pub error: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct AllocateRequest {
    pub bank_transaction_id: i64,
    pub allocations: Vec<AllocationItem>,
    #[serde(default)]
    pub fees: Option<AllocationItem>,
    #[serde(default)]
    pub rounding: Option<AllocationItem>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct AllocationItem {
    pub kind: String,
    pub amount: f64,
    pub id: Option<i64>,
    pub account_id: Option<i64>,
    pub tax_rate_id: Option<i64>,
}

#[derive(Debug, Serialize)]
pub struct AllocateResponse {
    pub ok: bool,
    pub journal_entry_id: Option<i64>,
    pub bank_transaction_status: String,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ReconciliationProgress {
    pub total_transactions: i64,
    pub reconciled: i64,
    pub unreconciled: i64,
    pub total_reconciled_amount: f64,
    pub total_unreconciled_amount: f64,
    pub reconciliation_percentage: f64,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct DuplicateCheckRequest {
    pub transactions: Vec<TransactionToCheck>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct TransactionToCheck {
    pub amount: f64,
    pub date: String,
    pub description: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DuplicateCheckResponse {
    pub ok: bool,
    pub duplicates: Vec<DuplicateInfo>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DuplicateInfo {
    pub index: usize,
    pub existing_transaction_id: i64,
    pub match_reason: String,
}

// ============================================================================
// Database Rows
// ============================================================================

#[derive(sqlx::FromRow)]
struct BankTransactionRow {
    id: i64,
    amount: f64,
    description: String,
    date: String,
    external_id: Option<String>,
    bank_account_id: i64,
    status: String,
}

#[derive(sqlx::FromRow)]
struct BankRuleRow {
    id: i64,
    merchant_name: String,
    pattern: Option<String>,
    bank_text_pattern: Option<String>,
    description_pattern: Option<String>,
    auto_confirm: bool,
}

#[derive(sqlx::FromRow)]
struct InvoiceRow {
    id: i64,
    invoice_number: String,
    grand_total: f64,
    issue_date: String,
    customer_name: String,
}

#[derive(sqlx::FromRow)]
struct ExpenseRow {
    id: i64,
    grand_total: f64,
    date: String,
    description: String,
}

#[derive(sqlx::FromRow)]
struct JournalEntryRow {
    id: i64,
    source_type: String,
    source_id: i64,
}

// ============================================================================
// Matching Engine
// ============================================================================

pub struct BankMatchingEngine;

impl BankMatchingEngine {
    /// Find matches for a bank transaction using 3-tier algorithm
    pub async fn find_matches(
        pool: &SqlitePool,
        tx_id: i64,
        limit: i64,
        extended_lookback: bool,
    ) -> Result<Vec<MatchCandidate>, String> {
        // Get the bank transaction
        let tx = sqlx::query_as::<_, BankTransactionRow>(
            "SELECT id, amount, description, date, external_id, bank_account_id, status 
             FROM core_banktransaction WHERE id = ?"
        )
        .bind(tx_id)
        .fetch_optional(pool)
        .await
        .map_err(|e| e.to_string())?
        .ok_or("Bank transaction not found")?;

        // Get business_id from bank account
        let business_id: i64 = sqlx::query_scalar(
            "SELECT business_id FROM core_bankaccount WHERE id = ?"
        )
        .bind(tx.bank_account_id)
        .fetch_one(pool)
        .await
        .map_err(|e| e.to_string())?;

        let mut candidates: Vec<MatchCandidate> = Vec::new();

        // Tier 0: Bank Rules
        let tier0 = Self::tier0_rule_match(pool, &tx, business_id).await;
        if !tier0.is_empty() {
            candidates.extend(tier0);
            return Ok(candidates.into_iter().take(limit as usize).collect());
        }

        // Tier 1: Deterministic ID match
        if let Some(match_) = Self::tier1_id_match(pool, &tx, business_id).await {
            candidates.push(match_);
            return Ok(candidates);
        }

        // Tier 2: Reference parsing from description
        let tier2 = Self::tier2_reference_match(pool, &tx, business_id).await;
        candidates.extend(tier2);

        // Tier 3: Amount + date heuristic
        let lookback_days = if extended_lookback {
            MatchingConfig::EXTENDED_LOOKBACK_DAYS
        } else {
            MatchingConfig::DATE_LOOKBACK_DAYS
        };
        let tier3 = Self::tier3_amount_date_match(pool, &tx, business_id, lookback_days).await;
        candidates.extend(tier3);

        // Deduplicate and sort by confidence
        candidates.sort_by(|a, b| b.confidence.partial_cmp(&a.confidence).unwrap());
        candidates.dedup_by(|a, b| a.journal_entry_id == b.journal_entry_id && a.rule_id == b.rule_id);

        Ok(candidates.into_iter().take(limit as usize).collect())
    }

    /// Tier 0: Match against bank rules
    async fn tier0_rule_match(
        pool: &SqlitePool,
        tx: &BankTransactionRow,
        business_id: i64,
    ) -> Vec<MatchCandidate> {
        let rules = sqlx::query_as::<_, BankRuleRow>(
            "SELECT id, merchant_name, pattern, bank_text_pattern, description_pattern, auto_confirm 
             FROM core_bankrule WHERE business_id = ?"
        )
        .bind(business_id)
        .fetch_all(pool)
        .await
        .unwrap_or_default();

        let mut candidates = Vec::new();
        let description_lower = tx.description.to_lowercase();

        for rule in rules {
            let mut matched = false;
            let mut confidence = 0.0;
            let mut reason = String::new();

            // Priority 1: bank_text_pattern
            if let Some(pattern) = &rule.bank_text_pattern {
                if let Ok(re) = Regex::new(&format!("(?i){}", pattern)) {
                    if re.is_match(&tx.description) {
                        matched = true;
                        confidence = 1.00;
                        reason = format!("Rule: {} (Bank text match)", rule.merchant_name);
                    }
                }
            }

            // Priority 2: description_pattern
            if !matched {
                if let Some(pattern) = &rule.description_pattern {
                    if let Ok(re) = Regex::new(&format!("(?i){}", pattern)) {
                        if re.is_match(&tx.description) {
                            matched = true;
                            confidence = 0.98;
                            reason = format!("Rule: {} (Description match)", rule.merchant_name);
                        }
                    }
                }
            }

            // Priority 3: Legacy pattern
            if !matched {
                if let Some(pattern) = &rule.pattern {
                    if let Ok(re) = Regex::new(&format!("(?i){}", pattern)) {
                        if re.is_match(&tx.description) {
                            matched = true;
                            confidence = 1.00;
                            reason = format!("Rule: {}", rule.merchant_name);
                        }
                    }
                }
            }

            // Priority 4: Merchant name substring
            if !matched && description_lower.contains(&rule.merchant_name.to_lowercase()) {
                matched = true;
                confidence = 0.90;
                reason = format!("Rule: {} (Name match)", rule.merchant_name);
            }

            if matched {
                candidates.push(MatchCandidate {
                    match_type: "RULE".to_string(),
                    confidence,
                    reason,
                    journal_entry_id: None,
                    rule_id: Some(rule.id),
                    invoice_id: None,
                    expense_id: None,
                    auto_confirm: rule.auto_confirm,
                });
            }
        }

        candidates
    }

    /// Tier 1: Match by external_id
    async fn tier1_id_match(
        pool: &SqlitePool,
        tx: &BankTransactionRow,
        business_id: i64,
    ) -> Option<MatchCandidate> {
        let external_id = tx.external_id.as_ref()?;
        
        // Try matching to invoice by invoice_number
        let invoice = sqlx::query_as::<_, (i64, String)>(
            "SELECT id, invoice_number FROM core_invoice 
             WHERE business_id = ? AND invoice_number = ?"
        )
        .bind(business_id)
        .bind(external_id)
        .fetch_optional(pool)
        .await
        .ok()
        .flatten();

        if let Some((invoice_id, invoice_number)) = invoice {
            // Find associated journal entry
            let je_id: Option<i64> = sqlx::query_scalar(
                "SELECT id FROM core_journalentry WHERE source_type = 'invoice' AND source_id = ?"
            )
            .bind(invoice_id)
            .fetch_optional(pool)
            .await
            .ok()
            .flatten();

            return Some(MatchCandidate {
                match_type: "ONE_TO_ONE".to_string(),
                confidence: MatchingConfig::CONFIDENCE_TIER1,
                reason: format!("Matched invoice #{} by external_id", invoice_number),
                journal_entry_id: je_id,
                rule_id: None,
                invoice_id: Some(invoice_id),
                expense_id: None,
                auto_confirm: false,
            });
        }

        None
    }

    /// Tier 2: Parse invoice/expense references from description
    async fn tier2_reference_match(
        pool: &SqlitePool,
        tx: &BankTransactionRow,
        business_id: i64,
    ) -> Vec<MatchCandidate> {
        let mut candidates = Vec::new();

        // Invoice patterns: INV-1234, #INV1234, Invoice 1234
        let invoice_patterns = [
            r"INV[- ]?(\d+)",
            r"#INV(\d+)",
            r"(?i)invoice\s*#?\s*(\d+)",
        ];

        for pattern in invoice_patterns {
            if let Ok(re) = Regex::new(pattern) {
                if let Some(captures) = re.captures(&tx.description) {
                    if let Some(num) = captures.get(1) {
                        let _invoice_num = format!("INV-{}", num.as_str());
                        
                        let invoice = sqlx::query_as::<_, (i64, String, f64)>(
                            "SELECT id, invoice_number, grand_total FROM core_invoice 
                             WHERE business_id = ? AND invoice_number LIKE ?"
                        )
                        .bind(business_id)
                        .bind(format!("%{}%", num.as_str()))
                        .fetch_optional(pool)
                        .await
                        .ok()
                        .flatten();

                        if let Some((invoice_id, invoice_number, _amount)) = invoice {
                            candidates.push(MatchCandidate {
                                match_type: "ONE_TO_ONE".to_string(),
                                confidence: MatchingConfig::CONFIDENCE_TIER2,
                                reason: format!("Found invoice #{} in description", invoice_number),
                                journal_entry_id: None,
                                rule_id: None,
                                invoice_id: Some(invoice_id),
                                expense_id: None,
                                auto_confirm: false,
                            });
                        }
                    }
                }
            }
        }

        candidates
    }

    /// Tier 3: Amount + date proximity matching
    async fn tier3_amount_date_match(
        pool: &SqlitePool,
        tx: &BankTransactionRow,
        business_id: i64,
        lookback_days: i64,
    ) -> Vec<MatchCandidate> {
        let mut candidates = Vec::new();
        let amount = tx.amount.abs();
        let tolerance = MatchingConfig::AMOUNT_TOLERANCE;

        // For positive amounts (deposits), look for invoices
        if tx.amount > 0.0 {
            let invoices = sqlx::query_as::<_, (i64, String, f64, String, String)>(
                "SELECT i.id, i.invoice_number, i.grand_total, i.issue_date, c.name
                 FROM core_invoice i
                 JOIN core_customer c ON i.customer_id = c.id
                 WHERE i.business_id = ? 
                 AND i.status IN ('SENT', 'PARTIAL')
                 AND i.grand_total BETWEEN ? AND ?
                 AND date(i.issue_date) >= date(?, '-' || ? || ' days')
                 ORDER BY ABS(i.grand_total - ?) ASC
                 LIMIT 5"
            )
            .bind(business_id)
            .bind(amount - tolerance)
            .bind(amount + tolerance)
            .bind(&tx.date)
            .bind(lookback_days)
            .bind(amount)
            .fetch_all(pool)
            .await
            .unwrap_or_default();

            let confidence = if invoices.len() == 1 {
                MatchingConfig::CONFIDENCE_TIER3_SINGLE
            } else {
                MatchingConfig::CONFIDENCE_TIER3_AMBIGUOUS
            };

            for (invoice_id, invoice_number, _total, _date, customer) in invoices {
                candidates.push(MatchCandidate {
                    match_type: "ONE_TO_ONE".to_string(),
                    confidence,
                    reason: format!("Amount matches invoice #{} ({})", invoice_number, customer),
                    journal_entry_id: None,
                    rule_id: None,
                    invoice_id: Some(invoice_id),
                    expense_id: None,
                    auto_confirm: false,
                });
            }
        }
        // For negative amounts (withdrawals), look for expenses
        else {
            let expenses = sqlx::query_as::<_, (i64, f64, String)>(
                "SELECT id, grand_total, description
                 FROM core_expense
                 WHERE business_id = ? 
                 AND status IN ('UNPAID', 'PARTIAL')
                 AND grand_total BETWEEN ? AND ?
                 AND date(date) >= date(?, '-' || ? || ' days')
                 ORDER BY ABS(grand_total - ?) ASC
                 LIMIT 5"
            )
            .bind(business_id)
            .bind(amount - tolerance)
            .bind(amount + tolerance)
            .bind(&tx.date)
            .bind(lookback_days)
            .bind(amount)
            .fetch_all(pool)
            .await
            .unwrap_or_default();

            let confidence = if expenses.len() == 1 {
                MatchingConfig::CONFIDENCE_TIER3_SINGLE
            } else {
                MatchingConfig::CONFIDENCE_TIER3_AMBIGUOUS
            };

            for (expense_id, _total, description) in expenses {
                candidates.push(MatchCandidate {
                    match_type: "ONE_TO_ONE".to_string(),
                    confidence,
                    reason: format!("Amount matches expense: {}", 
                        description.chars().take(30).collect::<String>()),
                    journal_entry_id: None,
                    rule_id: None,
                    invoice_id: None,
                    expense_id: Some(expense_id),
                    auto_confirm: false,
                });
            }
        }

        candidates
    }
}

// ============================================================================
// Route Handlers (Native)
// ============================================================================

/// POST /api/banking/find-matches
pub async fn find_matches(
    State(state): State<AppState>,
    Json(payload): Json<FindMatchesRequest>,
) -> impl IntoResponse {
    tracing::info!(
        "Finding matches for bank_transaction_id={}, extended_lookback={}",
        payload.bank_transaction_id,
        payload.extended_lookback
    );

    match BankMatchingEngine::find_matches(
        &state.db,
        payload.bank_transaction_id,
        payload.limit,
        payload.extended_lookback,
    )
    .await
    {
        Ok(matches) => (
            StatusCode::OK,
            Json(FindMatchesResponse {
                ok: true,
                matches,
                bank_transaction_id: payload.bank_transaction_id,
                error: None,
            }),
        ),
        Err(e) => (
            StatusCode::NOT_FOUND,
            Json(FindMatchesResponse {
                ok: false,
                matches: vec![],
                bank_transaction_id: payload.bank_transaction_id,
                error: Some(e),
            }),
        ),
    }
}

/// POST /api/banking/confirm-match
pub async fn confirm_match(
    State(state): State<AppState>,
    Json(payload): Json<ConfirmMatchRequest>,
) -> impl IntoResponse {
    tracing::info!(
        "Confirming match: bank_tx={} -> journal_entry={}",
        payload.bank_transaction_id,
        payload.journal_entry_id
    );

    // Update bank transaction status to MATCHED
    let result = sqlx::query(
        "UPDATE core_banktransaction 
         SET status = 'MATCHED', 
             journal_entry_id = ?,
             suggestion_confidence = ?,
             updated_at = datetime('now')
         WHERE id = ?"
    )
    .bind(payload.journal_entry_id)
    .bind((payload.match_confidence * 100.0) as i32)
    .bind(payload.bank_transaction_id)
    .execute(&state.db)
    .await;

    match result {
        Ok(r) if r.rows_affected() > 0 => (
            StatusCode::OK,
            Json(ConfirmMatchResponse {
                ok: true,
                bank_transaction_id: payload.bank_transaction_id,
                status: "MATCHED".to_string(),
                error: None,
            }),
        ),
        _ => (
            StatusCode::NOT_FOUND,
            Json(ConfirmMatchResponse {
                ok: false,
                bank_transaction_id: payload.bank_transaction_id,
                status: "ERROR".to_string(),
                error: Some("Transaction not found".to_string()),
            }),
        ),
    }
}

/// POST /api/banking/allocate
pub async fn allocate(
    State(state): State<AppState>,
    Json(payload): Json<AllocateRequest>,
) -> impl IntoResponse {
    tracing::info!(
        "Allocating bank_tx={} with {} allocations",
        payload.bank_transaction_id,
        payload.allocations.len()
    );

    // Update transaction status to MATCHED
    let result = sqlx::query(
        "UPDATE core_banktransaction 
         SET status = 'MATCHED', updated_at = datetime('now')
         WHERE id = ?"
    )
    .bind(payload.bank_transaction_id)
    .execute(&state.db)
    .await;

    match result {
        Ok(_) => (
            StatusCode::OK,
            Json(AllocateResponse {
                ok: true,
                journal_entry_id: None,
                bank_transaction_status: "MATCHED".to_string(),
                error: None,
            }),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(AllocateResponse {
                ok: false,
                journal_entry_id: None,
                bank_transaction_status: "ERROR".to_string(),
                error: Some(e.to_string()),
            }),
        ),
    }
}

/// GET /api/banking/progress/:account_id
pub async fn get_progress(
    State(state): State<AppState>,
    Path(account_id): Path<i64>,
) -> impl IntoResponse {
    tracing::info!("Getting reconciliation progress for account_id={}", account_id);

    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM core_banktransaction WHERE bank_account_id = ?"
    )
    .bind(account_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or(0);

    let reconciled: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM core_banktransaction 
         WHERE bank_account_id = ? AND status = 'MATCHED'"
    )
    .bind(account_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or(0);

    let reconciled_amount: f64 = sqlx::query_scalar(
        "SELECT COALESCE(SUM(ABS(amount)), 0) FROM core_banktransaction 
         WHERE bank_account_id = ? AND status = 'MATCHED'"
    )
    .bind(account_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or(0.0);

    let unreconciled_amount: f64 = sqlx::query_scalar(
        "SELECT COALESCE(SUM(ABS(amount)), 0) FROM core_banktransaction 
         WHERE bank_account_id = ? AND status != 'MATCHED'"
    )
    .bind(account_id)
    .fetch_one(&state.db)
    .await
    .unwrap_or(0.0);

    let percentage = if total > 0 {
        (reconciled as f64 / total as f64) * 100.0
    } else {
        100.0
    };

    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "progress": ReconciliationProgress {
            total_transactions: total,
            reconciled,
            unreconciled: total - reconciled,
            total_reconciled_amount: reconciled_amount,
            total_unreconciled_amount: unreconciled_amount,
            reconciliation_percentage: percentage,
        }
    })))
}

/// POST /api/banking/check-duplicates
pub async fn check_duplicates(
    State(state): State<AppState>,
    Json(payload): Json<DuplicateCheckRequest>,
) -> impl IntoResponse {
    tracing::info!("Checking {} transactions for duplicates", payload.transactions.len());

    let mut duplicates = Vec::new();

    for (index, tx) in payload.transactions.iter().enumerate() {
        // Check for existing transaction with same amount, date, and similar description
        let existing: Option<(i64, String)> = sqlx::query_as(
            "SELECT id, description FROM core_banktransaction 
             WHERE ABS(amount - ?) < 0.01 
             AND date = ?
             LIMIT 1"
        )
        .bind(tx.amount)
        .bind(&tx.date)
        .fetch_optional(&state.db)
        .await
        .ok()
        .flatten();

        if let Some((existing_id, existing_desc)) = existing {
            // Simple similarity check
            let similarity = calculate_similarity(&tx.description, &existing_desc);
            if similarity > 0.85 {
                duplicates.push(DuplicateInfo {
                    index,
                    existing_transaction_id: existing_id,
                    match_reason: format!("Same amount, date, and {:.0}% similar description", similarity * 100.0),
                });
            }
        }
    }

    (StatusCode::OK, Json(DuplicateCheckResponse {
        ok: true,
        duplicates,
        error: None,
    }))
}

/// Simple string similarity (Jaccard-like)
fn calculate_similarity(a: &str, b: &str) -> f64 {
    let a_lower = a.to_lowercase();
    let b_lower = b.to_lowercase();
    let a_words: std::collections::HashSet<&str> = a_lower.split_whitespace().collect();
    let b_words: std::collections::HashSet<&str> = b_lower.split_whitespace().collect();
    
    let intersection = a_words.intersection(&b_words).count();
    let union = a_words.union(&b_words).count();
    
    if union == 0 {
        0.0
    } else {
        intersection as f64 / union as f64
    }
}

/// GET /api/banking/health
pub async fn health() -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "ok",
        "service": "banking",
        "engine": "native_rust",
        "version": "2.0.0"
    }))
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // =========================================================================
    // String Similarity Tests
    // =========================================================================

    #[test]
    fn test_calculate_similarity_identical() {
        let similarity = calculate_similarity("Hello World", "Hello World");
        assert!((similarity - 1.0).abs() < 0.001, "Identical strings should have similarity 1.0");
    }

    #[test]
    fn test_calculate_similarity_case_insensitive() {
        let similarity = calculate_similarity("HELLO WORLD", "hello world");
        assert!((similarity - 1.0).abs() < 0.001, "Case should not affect similarity");
    }

    #[test]
    fn test_calculate_similarity_partial_overlap() {
        // "Hello World" -> {"hello", "world"}
        // "Hello There" -> {"hello", "there"}
        // Intersection: {"hello"} = 1
        // Union: {"hello", "world", "there"} = 3
        // Similarity: 1/3 ≈ 0.333
        let similarity = calculate_similarity("Hello World", "Hello There");
        assert!((similarity - 0.333).abs() < 0.1, "Expected ~0.33, got {}", similarity);
    }

    #[test]
    fn test_calculate_similarity_no_overlap() {
        let similarity = calculate_similarity("Apple Banana", "Cherry Date");
        assert!((similarity - 0.0).abs() < 0.001, "No common words should have 0 similarity");
    }

    #[test]
    fn test_calculate_similarity_empty_strings() {
        let similarity = calculate_similarity("", "");
        assert!((similarity - 0.0).abs() < 0.001, "Empty strings should return 0");
    }

    #[test]
    fn test_calculate_similarity_one_empty() {
        let similarity = calculate_similarity("Hello", "");
        assert!((similarity - 0.0).abs() < 0.001, "One empty string should return 0");
    }

    // =========================================================================
    // MatchingConfig Tests
    // =========================================================================

    #[test]
    fn test_matching_config_constants() {
        // Verify tier confidence levels are ordered correctly
        assert!(
            MatchingConfig::CONFIDENCE_TIER1 > MatchingConfig::CONFIDENCE_TIER2,
            "Tier1 should have higher confidence than Tier2"
        );
        assert!(
            MatchingConfig::CONFIDENCE_TIER2 > MatchingConfig::CONFIDENCE_TIER3_SINGLE,
            "Tier2 should have higher confidence than Tier3"
        );
        assert!(
            MatchingConfig::CONFIDENCE_TIER3_SINGLE > MatchingConfig::CONFIDENCE_TIER3_AMBIGUOUS,
            "Single match should have higher confidence than ambiguous"
        );
    }

    #[test]
    fn test_matching_config_lookback_days() {
        assert!(MatchingConfig::DATE_LOOKBACK_DAYS > 0);
        assert!(MatchingConfig::EXTENDED_LOOKBACK_DAYS > MatchingConfig::DATE_LOOKBACK_DAYS);
    }

    #[test]
    fn test_matching_config_tolerance() {
        assert!(MatchingConfig::AMOUNT_TOLERANCE > 0.0);
        assert!(MatchingConfig::AMOUNT_TOLERANCE < 1.0, "Tolerance should be less than $1");
    }

    // =========================================================================
    // Request/Response Serialization Tests
    // =========================================================================

    #[test]
    fn test_find_matches_request_deserialization() {
        let json = r#"{"bank_transaction_id": 123}"#;
        let request: FindMatchesRequest = serde_json::from_str(json).unwrap();
        
        assert_eq!(request.bank_transaction_id, 123);
        assert_eq!(request.limit, 5); // Default
        assert!(!request.extended_lookback); // Default
    }

    #[test]
    fn test_find_matches_request_with_options() {
        let json = r#"{"bank_transaction_id": 456, "limit": 10, "extended_lookback": true}"#;
        let request: FindMatchesRequest = serde_json::from_str(json).unwrap();
        
        assert_eq!(request.bank_transaction_id, 456);
        assert_eq!(request.limit, 10);
        assert!(request.extended_lookback);
    }

    #[test]
    fn test_match_candidate_serialization() {
        let candidate = MatchCandidate {
            match_type: "ONE_TO_ONE".to_string(),
            confidence: 0.95,
            reason: "Matched invoice #123".to_string(),
            journal_entry_id: Some(456),
            rule_id: None,
            invoice_id: Some(789),
            expense_id: None,
            auto_confirm: false,
        };
        
        let json = serde_json::to_string(&candidate).unwrap();
        assert!(json.contains("\"match_type\":\"ONE_TO_ONE\""));
        assert!(json.contains("\"confidence\":0.95"));
        assert!(json.contains("\"invoice_id\":789"));
    }

    #[test]
    fn test_confirm_match_request() {
        let json = r#"{
            "bank_transaction_id": 100,
            "journal_entry_id": 200,
            "match_confidence": 0.85
        }"#;
        let request: ConfirmMatchRequest = serde_json::from_str(json).unwrap();
        
        assert_eq!(request.bank_transaction_id, 100);
        assert_eq!(request.journal_entry_id, 200);
        assert!((request.match_confidence - 0.85).abs() < 0.001);
        assert!(request.adjustment_amount.is_none());
    }

    #[test]
    fn test_duplicate_check_request() {
        let json = r#"{
            "transactions": [
                {"amount": 100.50, "date": "2024-01-15", "description": "Test payment"}
            ]
        }"#;
        let request: DuplicateCheckRequest = serde_json::from_str(json).unwrap();
        
        assert_eq!(request.transactions.len(), 1);
        assert!((request.transactions[0].amount - 100.50).abs() < 0.001);
    }

    #[test]
    fn test_reconciliation_progress_serialization() {
        let progress = ReconciliationProgress {
            total_transactions: 100,
            reconciled: 75,
            unreconciled: 25,
            total_reconciled_amount: 5000.00,
            total_unreconciled_amount: 1500.00,
            reconciliation_percentage: 75.0,
        };
        
        let json = serde_json::to_string(&progress).unwrap();
        assert!(json.contains("\"total_transactions\":100"));
        assert!(json.contains("\"reconciliation_percentage\":75"));
    }

    #[test]
    fn test_allocate_request() {
        let json = r#"{
            "bank_transaction_id": 555,
            "allocations": [
                {"kind": "invoice", "amount": 100.0, "id": 1}
            ]
        }"#;
        let request: AllocateRequest = serde_json::from_str(json).unwrap();
        
        assert_eq!(request.bank_transaction_id, 555);
        assert_eq!(request.allocations.len(), 1);
        assert_eq!(request.allocations[0].kind, "invoice");
    }
}
