use serde_json::json;

use crate::companion_autonomy::copy::customer_safe_copy;
use crate::companion_autonomy::models::{RecommendationSeed, WorkItemSeed};

pub fn build_card(
    seed: &WorkItemSeed,
    recommendations: &[RecommendationSeed],
    signals: &[serde_json::Value],
    evidence_refs: &[String],
) -> (serde_json::Value, String) {
    let summary = customer_safe_copy(&seed.customer_summary);

    let checks = vec![
        json!({
            "check": "policy_threshold",
            "status": if seed.requires_approval { "needs_review" } else { "ok" },
        }),
        json!({
            "check": "dedupe_key",
            "status": "ok",
        }),
    ];

    let what_will_change: Vec<String> = recommendations
        .iter()
        .map(|rec| match rec.action_kind.as_str() {
            "apply" => "Apply the suggested change.".to_string(),
            "review" => "Open review before applying.".to_string(),
            "ask" => "Request clarification.".to_string(),
            _ => "Review the suggested change.".to_string(),
        })
        .collect();

    let sections = json!({
        "summary": summary,
        "signals": signals,
        "checks": checks,
        "evidence": evidence_refs,
        "what_will_change": what_will_change,
    });

    let customer_safe_text = customer_safe_copy(&format!(
        "{} {}",
        seed.customer_summary,
        what_will_change.join(" ")
    ));

    (sections, customer_safe_text)
}
