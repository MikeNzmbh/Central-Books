// Database connection module
// Provides SQLite connection pool for accessing the existing database

pub mod models;
pub mod queries;

use sqlx::sqlite::{SqlitePool, SqlitePoolOptions};
use std::env;
use std::path::PathBuf;

/// Shared database state used across the application
#[derive(Clone)]
pub struct DbPool {
    pub pool: SqlitePool,
}

impl DbPool {
    /// Create a new database connection pool
    pub async fn new() -> Result<Self, sqlx::Error> {
        let database_url = get_database_url();
        
        let pool = SqlitePoolOptions::new()
            .max_connections(10)
            .connect(&database_url)
            .await?;
        
        tracing::info!("Connected to SQLite database");
        
        Ok(Self { pool })
    }
    
    /// Get the underlying pool reference
    #[allow(dead_code)]
    pub fn get(&self) -> &SqlitePool {
        &self.pool
    }
}

/// Get the database URL, defaulting to the SQLite database
fn get_database_url() -> String {
    if let Ok(url) = env::var("DATABASE_URL") {
        return url;
    }
    
    // Default: SQLite database in legacy/db folder
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.pop(); // Go up from rust-api
    path.push("legacy");
    path.push("db");
    path.push("db.sqlite3");
    
    format!("sqlite:{}", path.display())
}
