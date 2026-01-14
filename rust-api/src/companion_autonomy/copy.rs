use regex::Regex;

const TERM_MAP: &[(&str, &str)] = &[
    ("journal entry", "change to your books"),
    ("journal entries", "changes to your books"),
    ("proposal", "AI suggestion"),
    ("proposals", "AI suggestions"),
    ("shadow ledger", "AI suggestions"),
    ("shadow event", "suggested change"),
    ("shadow events", "suggested changes"),
    ("canonical ledger", "your books"),
    ("canonical", "your books"),
    ("categorization", "category"),
    ("reclassification", "category correction"),
    ("reconciliation", "matching"),
    ("anomaly", "issue"),
    ("anomalies", "issues"),
    ("autopilot", "auto-apply"),
    ("shadow mode", "learning mode"),
    ("suggest mode", "review mode"),
];

const BANNED_TERMS: &[&str] = &[
    "shadow ledger",
    "journal entry",
    "journal entries",
    "canonical",
];

fn replace_terms(text: &str) -> String {
    let mut result = text.to_string();
    for (internal, customer) in TERM_MAP {
        let pattern = format!(r"(?i)\\b{}\\b", regex::escape(internal));
        if let Ok(re) = Regex::new(&pattern) {
            result = re.replace_all(&result, *customer).to_string();
        }
    }
    let debit_card_re = Regex::new(r"(?i)\\bdebit card\\b").unwrap();
    let credit_card_re = Regex::new(r"(?i)\\bcredit card\\b").unwrap();
    let debit_re = Regex::new(r"(?i)\\bdebit\\b").unwrap();
    let credit_re = Regex::new(r"(?i)\\bcredit\\b").unwrap();

    let placeholder_debit = "__DEBIT_CARD__";
    let placeholder_credit = "__CREDIT_CARD__";
    let result = debit_card_re.replace_all(&result, placeholder_debit).to_string();
    let result = credit_card_re.replace_all(&result, placeholder_credit).to_string();
    let result = debit_re.replace_all(&result, "increase").to_string();
    let result = credit_re.replace_all(&result, "decrease").to_string();
    let result = result.replace(placeholder_debit, "debit card");
    result.replace(placeholder_credit, "credit card")
}

fn contains_banned(text: &str) -> Option<&'static str> {
    let lower = text.to_lowercase();
    BANNED_TERMS
        .iter()
        .find(|term| lower.contains(**term))
        .copied()
}

pub fn customer_safe_copy(text: &str) -> String {
    let sanitized = replace_terms(text);
    if contains_banned(&sanitized).is_some() {
        "Details are ready for review.".to_string()
    } else {
        sanitized
    }
}

#[allow(dead_code)]
pub fn ensure_customer_safe(text: &str) -> Result<String, String> {
    if let Some(term) = contains_banned(text) {
        return Err(format!("banned term detected: {}", term));
    }
    Ok(replace_terms(text))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn customer_safe_copy_removes_banned_terms() {
        let input = "Post a journal entry to the shadow ledger.";
        let output = customer_safe_copy(input);
        assert!(!output.to_lowercase().contains("journal entry"));
        assert!(!output.to_lowercase().contains("shadow ledger"));
    }

    #[test]
    fn ensure_customer_safe_blocks_terms() {
        let input = "Shadow ledger note";
        let result = ensure_customer_safe(input);
        assert!(result.is_err());
    }
}
