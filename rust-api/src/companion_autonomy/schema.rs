use sqlx::SqlitePool;

pub async fn run_migrations(pool: &SqlitePool) -> Result<(), sqlx::migrate::MigrateError> {
    sqlx::migrate!("./migrations").run(pool).await
}

pub async fn auto_init(pool: &SqlitePool) -> Result<(), sqlx::migrate::MigrateError> {
    if std::env::var("CAE_SCHEMA_AUTOINIT").ok().as_deref() == Some("1") {
        run_migrations(pool).await?;
    }
    Ok(())
}
