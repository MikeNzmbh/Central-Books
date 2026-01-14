pub mod agents;
pub mod copy;
pub mod models;
pub mod policy;
pub mod schema;
pub mod scheduler;
pub mod store;
pub mod tool_gateway;

pub fn now_utc_str() -> String {
    chrono::Utc::now().to_rfc3339()
}

pub fn hash_inputs(payload: &str) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(payload.as_bytes());
    format!("{:x}", hasher.finalize())
}
