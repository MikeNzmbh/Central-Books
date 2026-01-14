use serde_json::json;
use sqlx::SqlitePool;

use crate::companion_autonomy::agents::AgentContext;
use crate::companion_autonomy::copy::customer_safe_copy;
use crate::companion_autonomy::models::{AgentOutput, WorkItemSeed};
use crate::companion_autonomy::policy::{confidence_for_amount, requires_approval, risk_for_amount};

pub async fn run(ctx: &AgentContext) -> Result<AgentOutput, String> {
    let rows = fetch_unmatched_transactions(&ctx.pool, ctx.business_id)
        .await
        .map_err(|e| e.to_string())?;

    let mut output = AgentOutput::empty();

    for (id, description, amount, date, status) in rows {
        let amount_value = amount.unwrap_or(0.0);
        let requires = requires_approval(Some(amount_value), &ctx.policy);
        let risk = risk_for_amount(Some(amount_value)).to_string();
        let confidence = confidence_for_amount(Some(amount_value));

        let title = format!("Match bank activity for {}", description);
        let summary = format!("This transaction is still marked as {} and needs matching.", status);

        let seed = WorkItemSeed {
            tenant_id: ctx.tenant_id,
            business_id: ctx.business_id,
            work_type: "match_bank".to_string(),
            surface: "bank".to_string(),
            status: "open".to_string(),
            priority: 60,
            dedupe_key: format!("match_bank:{}", id),
            inputs: json!({
                "transaction_id": id,
                "description": description,
                "amount": amount_value,
                "date": date,
                "status": status,
            }),
            state: json!({
                "match_candidates": [],
                "confidence": confidence,
            }),
            due_at: None,
            snoozed_until: None,
            risk_level: risk,
            confidence_score: confidence,
            requires_approval: requires,
            customer_title: customer_safe_copy(&title),
            customer_summary: customer_safe_copy(&summary),
            internal_title: format!("Match bank transaction {}", id),
            internal_notes: format!("Unmatched bank transaction: {}", description),
            links: json!({"target_url": "/banking"}),
        };

        output.signals.push(json!({
            "type": "unmatched_bank",
            "transaction_id": id,
            "amount": amount_value
        }));
        output.evidence_refs.push(format!("bank_transaction:{}", id));
        output.work_items.push(seed);
    }

    Ok(output)
}

async fn fetch_unmatched_transactions(
    pool: &SqlitePool,
    business_id: i64,
) -> Result<Vec<(i64, String, Option<f64>, String, String)>, sqlx::Error> {
    sqlx::query_as(
        "SELECT t.id, COALESCE(t.description, ''), t.amount, t.date, t.status
         FROM core_banktransaction t
         JOIN core_bankaccount a ON t.bank_account_id = a.id
         WHERE a.business_id = ?
           AND t.status = 'NEW'
         ORDER BY t.date DESC
         LIMIT 25"
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
}
