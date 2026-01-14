use serde_json::json;
use sqlx::SqlitePool;

use crate::companion_autonomy::copy::customer_safe_copy;
use crate::companion_autonomy::models::{AgentOutput, WorkItemSeed};
use crate::companion_autonomy::policy::{confidence_for_amount, requires_approval, risk_for_amount};
use crate::companion_autonomy::agents::AgentContext;

pub async fn run(ctx: &AgentContext) -> Result<AgentOutput, String> {
    let rows = fetch_uncategorized_transactions(&ctx.pool, ctx.business_id)
        .await
        .map_err(|e| e.to_string())?;

    let mut output = AgentOutput::empty();

    for (id, description, amount, date) in rows {
        let amount_value = amount.unwrap_or(0.0);
        let requires = requires_approval(Some(amount_value), &ctx.policy);
        let risk = risk_for_amount(Some(amount_value)).to_string();
        let confidence = confidence_for_amount(Some(amount_value));

        let title = format!("Review category for {}", description);
        let summary = "This transaction needs a category before it can be finalized.".to_string();

        let seed = WorkItemSeed {
            tenant_id: ctx.tenant_id,
            business_id: ctx.business_id,
            work_type: "categorize_tx".to_string(),
            surface: "bank".to_string(),
            status: "open".to_string(),
            priority: 50,
            dedupe_key: format!("categorize_tx:{}", id),
            inputs: json!({
                "transaction_id": id,
                "description": description,
                "amount": amount_value,
                "date": date,
            }),
            state: json!({
                "suggested_category": null,
                "confidence": confidence,
            }),
            due_at: None,
            snoozed_until: None,
            risk_level: risk,
            confidence_score: confidence,
            requires_approval: requires,
            customer_title: customer_safe_copy(&title),
            customer_summary: customer_safe_copy(&summary),
            internal_title: format!("Categorize bank transaction {}", id),
            internal_notes: format!("Categorization candidate: {}", description),
            links: json!({"target_url": "/banking"}),
        };

        output.signals.push(json!({
            "type": "missing_category",
            "transaction_id": id,
            "amount": amount_value
        }));
        output.evidence_refs.push(format!("bank_transaction:{}", id));
        output.work_items.push(seed);
    }

    Ok(output)
}

async fn fetch_uncategorized_transactions(
    pool: &SqlitePool,
    business_id: i64,
) -> Result<Vec<(i64, String, Option<f64>, String)>, sqlx::Error> {
    sqlx::query_as(
        "SELECT t.id, COALESCE(t.description, ''), t.amount, t.date
         FROM core_banktransaction t
         JOIN core_bankaccount a ON t.bank_account_id = a.id
         WHERE a.business_id = ?
           AND t.category_id IS NULL
         ORDER BY t.date DESC
         LIMIT 25"
    )
    .bind(business_id)
    .fetch_all(pool)
    .await
}
