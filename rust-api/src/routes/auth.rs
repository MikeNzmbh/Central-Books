//! Authentication routes for Clover Books API
//! 
//! Handles login, signup, session management, and JWT tokens.
//! Reads from the SQLite database for real user authentication.

use axum::{
    extract::{Json, State},
    http::{StatusCode, HeaderMap},
    response::IntoResponse,
};
use serde::{Deserialize, Serialize};
use chrono::{Duration, Utc};
use jsonwebtoken::{encode, decode, Header, EncodingKey, DecodingKey, Validation};

use crate::AppState;

// ============================================================================
// JWT Secret Configuration
// ============================================================================

/// Get JWT secret from environment variable.
/// SECURITY: In production, JWT_SECRET environment variable MUST be set.
fn get_jwt_secret() -> Vec<u8> {
    match std::env::var("JWT_SECRET") {
        Ok(secret) if !secret.is_empty() => secret.into_bytes(),
        _ => {
            // Only allow fallback in development
            let env = std::env::var("RUST_ENV").unwrap_or_else(|_| "development".to_string());
            if env == "production" {
                panic!("JWT_SECRET environment variable must be set in production!");
            }
            tracing::warn!("⚠️  Using default JWT secret - set JWT_SECRET env var for production!");
            b"clover-books-dev-secret-CHANGE-IN-PRODUCTION".to_vec()
        }
    }
}

// ============================================================================
// Data Types
// ============================================================================

#[derive(Debug, Serialize, Deserialize)]
pub struct LoginRequest {
    pub email: String,
    pub password: String,
    #[serde(default)]
    pub remember_me: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SignupRequest {
    pub email: String,
    pub password: String,
    pub first_name: Option<String>,
    pub last_name: Option<String>,
    pub business_name: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AuthResponse {
    pub ok: bool,
    pub token: Option<String>,
    pub user: Option<UserInfo>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct UserInfo {
    pub id: i64,
    pub email: String,
    pub first_name: String,
    pub last_name: String,
    pub business_name: Option<String>,
    pub business_id: Option<i64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,  // user ID
    pub email: String,
    pub business_id: Option<i64>,
    pub exp: usize,   // expiration timestamp
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AuthConfig {
    pub google_enabled: bool,
    pub magic_link_enabled: bool,
    pub password_enabled: bool,
}

// ============================================================================
// JWT Token Extraction
// ============================================================================

/// Extract and validate JWT token from Authorization header.
/// This function can be used by other route handlers to authenticate requests.
pub fn extract_claims_from_header(headers: &HeaderMap) -> Result<Claims, String> {
    let auth_header = headers
        .get("authorization")
        .and_then(|h| h.to_str().ok())
        .ok_or("Missing authorization header")?;
    
    if !auth_header.starts_with("Bearer ") {
        return Err("Invalid authorization header format".to_string());
    }
    
    let token = &auth_header[7..];
    let secret = get_jwt_secret();
    
    let token_data = decode::<Claims>(
        token,
        &DecodingKey::from_secret(&secret),
        &Validation::default(),
    ).map_err(|e| format!("Invalid token: {}", e))?;
    
    Ok(token_data.claims)
}

// ============================================================================
// Database Row Types
// ============================================================================

#[derive(sqlx::FromRow)]
struct UserRow {
    id: i64,
    email: String,
    password: String,
    first_name: String,
    last_name: String,
    is_active: bool,
}

#[derive(sqlx::FromRow)]
struct BusinessRow {
    id: i64,
    name: String,
}

// ============================================================================
// Password Verification (Legacy PBKDF2-SHA256)
// ============================================================================

/// Verify legacy PBKDF2 password hash
/// Legacy format: pbkdf2_sha256$iterations$salt$hash
fn verify_legacy_password(password: &str, hash: &str) -> bool {
    let parts: Vec<&str> = hash.split('$').collect();
    if parts.len() != 4 {
        return false;
    }
    
    let algorithm = parts[0];
    let iterations: u32 = parts[1].parse().unwrap_or(0);
    let salt = parts[2];
    let expected_hash = parts[3];
    
    if algorithm != "pbkdf2_sha256" || iterations == 0 {
        return false;
    }
    
    // Use PBKDF2 with SHA256
    use sha2::Sha256;
    use hmac::Hmac;
    use pbkdf2::pbkdf2;
    
    let mut derived_key = vec![0u8; 32]; // SHA256 produces 32 bytes
    let _ = pbkdf2::<Hmac<Sha256>>(
        password.as_bytes(),
        salt.as_bytes(),
        iterations,
        &mut derived_key,
    );
    
    // Compare with base64-encoded expected hash
    use base64::{Engine as _, engine::general_purpose::STANDARD};
    let expected_bytes = STANDARD.decode(expected_hash).unwrap_or_default();
    
    derived_key == expected_bytes
}

// ============================================================================
// Route Handlers
// ============================================================================

/// POST /api/auth/login
/// 
/// Authenticate user with email/password against the existing database.
pub async fn login(
    State(state): State<AppState>,
    Json(payload): Json<LoginRequest>,
) -> impl IntoResponse {
    tracing::info!("Login attempt for: {}", payload.email);
    
    // Look up user in database
    let user_result = sqlx::query_as::<_, UserRow>(
        "SELECT id, email, password, first_name, last_name, is_active 
         FROM auth_user WHERE email = ? OR username = ?"
    )
    .bind(&payload.email)
    .bind(&payload.email)
    .fetch_optional(&state.db)
    .await;
    
    let user_row = match user_result {
        Ok(Some(user)) => user,
        Ok(None) => {
            tracing::warn!("User not found: {}", payload.email);
            return (
                StatusCode::UNAUTHORIZED,
                Json(AuthResponse {
                    ok: false,
                    token: None,
                    user: None,
                    error: Some("Invalid email or password".to_string()),
                }),
            );
        }
        Err(e) => {
            tracing::error!("Database error: {}", e);
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(AuthResponse {
                    ok: false,
                    token: None,
                    user: None,
                    error: Some("Database error".to_string()),
                }),
            );
        }
    };
    
    // Check if user is active
    if !user_row.is_active {
        return (
            StatusCode::UNAUTHORIZED,
            Json(AuthResponse {
                ok: false,
                token: None,
                user: None,
                error: Some("Account is disabled".to_string()),
            }),
        );
    }
    
    // Verify password against legacy hash
    if !verify_legacy_password(&payload.password, &user_row.password) {
        tracing::warn!("Invalid password for: {}", payload.email);
        return (
            StatusCode::UNAUTHORIZED,
            Json(AuthResponse {
                ok: false,
                token: None,
                user: None,
                error: Some("Invalid email or password".to_string()),
            }),
        );
    }
    
    // Get user's business
    let business = sqlx::query_as::<_, BusinessRow>(
        "SELECT id, name FROM core_business WHERE owner_user_id = ? AND is_deleted = 0"
    )
    .bind(user_row.id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();
    
    // Build user info
    let user = UserInfo {
        id: user_row.id,
        email: user_row.email.clone(),
        first_name: user_row.first_name.clone(),
        last_name: user_row.last_name.clone(),
        business_name: business.as_ref().map(|b| b.name.clone()),
        business_id: business.as_ref().map(|b| b.id),
    };

    // Generate JWT token
    let expiration = if payload.remember_me {
        Utc::now() + Duration::days(30)
    } else {
        Utc::now() + Duration::hours(24)
    };

    let claims = Claims {
        sub: user.id.to_string(),
        email: user.email.clone(),
        business_id: user.business_id,
        exp: expiration.timestamp() as usize,
    };

    let token = encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(&get_jwt_secret()),
    )
    .unwrap();

    tracing::info!("Login successful for: {} (user_id={})", payload.email, user.id);

    (
        StatusCode::OK,
        Json(AuthResponse {
            ok: true,
            token: Some(token),
            user: Some(user),
            error: None,
        }),
    )
}

/// POST /api/auth/signup
/// 
/// Create a new user account.
pub async fn signup(
    State(_state): State<AppState>,
    Json(payload): Json<SignupRequest>,
) -> impl IntoResponse {
    tracing::info!("Signup attempt for: {}", payload.email);

    // Validate email
    if !payload.email.contains('@') {
        return (
            StatusCode::BAD_REQUEST,
            Json(AuthResponse {
                ok: false,
                token: None,
                user: None,
                error: Some("Invalid email address".to_string()),
            }),
        );
    }

    // Validate password
    if payload.password.len() < 6 {
        return (
            StatusCode::BAD_REQUEST,
            Json(AuthResponse {
                ok: false,
                token: None,
                user: None,
                error: Some("Password must be at least 6 characters".to_string()),
            }),
        );
    }

    // TODO: Create user in database with legacy-compatible password hash
    // For now, return error indicating signup should be done via the existing web app
    (
        StatusCode::NOT_IMPLEMENTED,
        Json(AuthResponse {
            ok: false,
            token: None,
            user: None,
            error: Some("Signup not yet implemented in Rust API. Please use the existing web app.".to_string()),
        }),
    )
}

/// GET /api/auth/me
/// 
/// Get current authenticated user info from JWT token.
pub async fn me(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> impl IntoResponse {
    // Extract and validate JWT token
    let claims = match extract_claims_from_header(&headers) {
        Ok(c) => c,
        Err(e) => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({
                    "ok": false,
                    "error": e
                })),
            );
        }
    };
    
    // Get user from database
    let user_id: i64 = claims.sub.parse().unwrap_or(0);
    let user = sqlx::query_as::<_, UserRow>(
        "SELECT id, email, password, first_name, last_name, is_active 
         FROM auth_user WHERE id = ?"
    )
    .bind(user_id)
    .fetch_optional(&state.db)
    .await;
    
    match user {
        Ok(Some(u)) if u.is_active => {
            // Get business info
            let business = sqlx::query_as::<_, BusinessRow>(
                "SELECT id, name FROM core_business WHERE owner_user_id = ? AND is_deleted = 0"
            )
            .bind(user_id)
            .fetch_optional(&state.db)
            .await
            .ok()
            .flatten();
            
            (
                StatusCode::OK,
                Json(serde_json::json!({
                    "ok": true,
                    "user": {
                        "id": u.id,
                        "email": u.email,
                        "first_name": u.first_name,
                        "last_name": u.last_name,
                        "business_name": business.as_ref().map(|b| &b.name),
                        "business_id": business.as_ref().map(|b| b.id)
                    }
                })),
            )
        }
        Ok(Some(_)) => (
            StatusCode::UNAUTHORIZED,
            Json(serde_json::json!({
                "ok": false,
                "error": "Account is disabled"
            })),
        ),
        _ => (
            StatusCode::UNAUTHORIZED,
            Json(serde_json::json!({
                "ok": false,
                "error": "User not found"
            })),
        ),
    }
}

/// POST /api/auth/logout
/// 
/// Logout current user (client should discard token).
pub async fn logout() -> impl IntoResponse {
    (StatusCode::OK, Json(serde_json::json!({
        "ok": true,
        "message": "Logged out successfully"
    })))
}

/// GET /api/auth/config
/// 
/// Get authentication configuration for frontend.
pub async fn config() -> impl IntoResponse {
    let config = AuthConfig {
        google_enabled: true,
        magic_link_enabled: false,
        password_enabled: true,
    };

    (StatusCode::OK, Json(config))
}

/// GET /api/auth/google/login
/// 
/// Initiate Google OAuth flow.
/// NOTE: Requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.
pub async fn google_login() -> impl IntoResponse {
    // Check for Google OAuth configuration
    let client_id = std::env::var("GOOGLE_CLIENT_ID").ok();
    
    let html = if let Some(client_id) = client_id {
        // Build Google OAuth URL and show redirect page
        let redirect_uri = std::env::var("GOOGLE_REDIRECT_URI")
            .unwrap_or_else(|_| "http://localhost:3001/api/auth/google/callback".to_string());
        
        let oauth_url = format!(
            "https://accounts.google.com/o/oauth2/v2/auth?client_id={}&redirect_uri={}&response_type=code&scope=email%20profile&access_type=offline",
            client_id,
            urlencoding::encode(&redirect_uri)
        );
        
        format!(r#"<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0;url={}">
    <title>Redirecting to Google...</title>
</head>
<body>
    <p>Redirecting to Google...</p>
    <p>If not redirected, <a href="{}">click here</a>.</p>
</body>
</html>"#, oauth_url, oauth_url)
    } else {
        // Return HTML page with error message
        r#"<!DOCTYPE html>
<html>
<head>
    <title>Google OAuth Not Configured</title>
    <style>
        body { font-family: system-ui, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: linear-gradient(to br, #f1f5f9, #fff, #e0f2fe); }
        .card { background: white; border-radius: 24px; padding: 40px; max-width: 400px; box-shadow: 0 20px 60px rgba(0,0,0,0.1); text-align: center; }
        h1 { color: #0f172a; font-size: 24px; margin-bottom: 16px; }
        p { color: #64748b; line-height: 1.6; }
        code { background: #f1f5f9; padding: 2px 8px; border-radius: 6px; font-size: 13px; }
        a { display: inline-block; margin-top: 20px; padding: 12px 24px; background: #0f172a; color: white; text-decoration: none; border-radius: 999px; font-weight: 500; }
        a:hover { background: #1e293b; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Google OAuth Not Configured</h1>
        <p>To enable Google login, set these environment variables:</p>
        <p><code>GOOGLE_CLIENT_ID</code><br><code>GOOGLE_CLIENT_SECRET</code></p>
        <p>Get them from the <a href="https://console.cloud.google.com/apis/credentials" target="_blank" style="color: #0ea5e9; background: none; padding: 0; margin: 0;">Google Cloud Console</a></p>
        <a href="/login">← Back to Login</a>
    </div>
</body>
</html>"#.to_string()
    };
    
    (
        StatusCode::OK,
        [("Content-Type", "text/html")],
        html,
    )
}

/// GET /api/auth/google/callback
/// 
/// Handle Google OAuth callback - exchange code for tokens and login user.
pub async fn google_callback(
    State(state): State<AppState>,
    axum::extract::Query(params): axum::extract::Query<GoogleCallbackParams>,
) -> impl IntoResponse {
    let code = match params.code {
        Some(c) => c,
        None => {
            return error_html("No authorization code received from Google");
        }
    };

    // Get credentials from environment
    let client_id = std::env::var("GOOGLE_CLIENT_ID").unwrap_or_default();
    let client_secret = std::env::var("GOOGLE_CLIENT_SECRET").unwrap_or_default();
    let redirect_uri = std::env::var("GOOGLE_REDIRECT_URI")
        .unwrap_or_else(|_| "http://localhost:3001/api/auth/google/callback".to_string());

    // Exchange code for tokens
    let client = reqwest::Client::new();
    let token_response = client
        .post("https://oauth2.googleapis.com/token")
        .form(&[
            ("code", code.as_str()),
            ("client_id", client_id.as_str()),
            ("client_secret", client_secret.as_str()),
            ("redirect_uri", redirect_uri.as_str()),
            ("grant_type", "authorization_code"),
        ])
        .send()
        .await;

    let tokens: GoogleTokenResponse = match token_response {
        Ok(resp) => match resp.json().await {
            Ok(t) => t,
            Err(e) => {
                tracing::error!("Failed to parse Google token response: {}", e);
                return error_html(&format!("Failed to parse Google response: {}", e));
            }
        },
        Err(e) => {
            tracing::error!("Failed to exchange code: {}", e);
            return error_html(&format!("Failed to exchange code: {}", e));
        }
    };

    // Get user info from Google
    let user_info_response = client
        .get("https://www.googleapis.com/oauth2/v2/userinfo")
        .bearer_auth(&tokens.access_token)
        .send()
        .await;

    let google_user: GoogleUserInfo = match user_info_response {
        Ok(resp) => match resp.json().await {
            Ok(u) => u,
            Err(e) => {
                tracing::error!("Failed to parse Google user info: {}", e);
                return error_html(&format!("Failed to get user info: {}", e));
            }
        },
        Err(e) => {
            tracing::error!("Failed to fetch user info: {}", e);
            return error_html(&format!("Failed to fetch user info: {}", e));
        }
    };

    tracing::info!("Google OAuth: Got user info for {}", google_user.email);

    // Find or create user
    let user = sqlx::query_as::<_, UserRow>(
        "SELECT id, email, password, first_name, last_name, is_active 
         FROM auth_user WHERE email = ?"
    )
    .bind(&google_user.email)
    .fetch_optional(&state.db)
    .await;

    let user_id: i64;
    let first_name: String;
    let last_name: String;

    match user {
        Ok(Some(existing_user)) => {
            // User exists, use their info
            user_id = existing_user.id;
            first_name = existing_user.first_name;
            last_name = existing_user.last_name;
            tracing::info!("Google OAuth: Found existing user id={}", user_id);
        }
        _ => {
            // Create new user
            let given_name = google_user.given_name.unwrap_or_else(|| "Google".to_string());
            let family_name = google_user.family_name.unwrap_or_else(|| "User".to_string());
            
            let result = sqlx::query(
                "INSERT INTO auth_user (email, password, first_name, last_name, username, is_active, is_staff, is_superuser, date_joined) 
                 VALUES (?, '', ?, ?, ?, 1, 0, 0, datetime('now'))"
            )
            .bind(&google_user.email)
            .bind(&given_name)
            .bind(&family_name)
            .bind(&google_user.email) // username = email
            .execute(&state.db)
            .await;

            match result {
                Ok(r) => {
                    user_id = r.last_insert_rowid();
                    first_name = given_name;
                    last_name = family_name;
                    tracing::info!("Google OAuth: Created new user id={}", user_id);
                }
                Err(e) => {
                    tracing::error!("Failed to create user: {}", e);
                    return error_html(&format!("Failed to create account: {}", e));
                }
            }
        }
    }

    // Get business_id if exists
    let business_id: Option<i64> = sqlx::query_scalar(
        "SELECT id FROM core_business WHERE owner_id = ? LIMIT 1"
    )
    .bind(user_id)
    .fetch_optional(&state.db)
    .await
    .ok()
    .flatten();

    // Generate JWT token
    let expiration = Utc::now() + Duration::days(7);
    let claims = Claims {
        sub: user_id.to_string(),
        email: google_user.email.clone(),
        business_id,
        exp: expiration.timestamp() as usize,
    };

    let token = match encode(&Header::default(), &claims, &EncodingKey::from_secret(&get_jwt_secret())) {
        Ok(t) => t,
        Err(e) => {
            tracing::error!("Failed to generate JWT: {}", e);
            return error_html(&format!("Failed to generate session: {}", e));
        }
    };

    // Redirect to frontend with token in URL (localStorage is per-origin, so we pass via URL)
    let redirect_url = format!(
        "http://localhost:5173/auth/callback?token={}&user_id={}&email={}&first_name={}&last_name={}",
        urlencoding::encode(&token),
        user_id,
        urlencoding::encode(&google_user.email),
        urlencoding::encode(&first_name),
        urlencoding::encode(&last_name)
    );
    
    // Use HTML meta refresh for consistent return type with error_html
    let html = format!(r#"<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0;url={}">
    <title>Logging in...</title>
</head>
<body>
    <p>Logging in... <a href="{}">Click here if not redirected</a></p>
</body>
</html>"#, redirect_url, redirect_url);

    (
        StatusCode::OK,
        [("Content-Type", "text/html")],
        html,
    )
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct GoogleCallbackParams {
    pub code: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct GoogleTokenResponse {
    access_token: String,
    #[serde(default)]
    token_type: String,
    #[serde(default)]
    expires_in: i64,
    #[serde(default)]
    refresh_token: Option<String>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct GoogleUserInfo {
    id: String,
    email: String,
    #[serde(default)]
    verified_email: bool,
    #[serde(default)]
    name: Option<String>,
    #[serde(default)]
    given_name: Option<String>,
    #[serde(default)]
    family_name: Option<String>,
    #[serde(default)]
    picture: Option<String>,
}

fn error_html(message: &str) -> (StatusCode, [(&'static str, &'static str); 1], String) {
    let html = format!(r#"<!DOCTYPE html>
<html>
<head>
    <title>Login Error</title>
    <style>
        body {{ font-family: system-ui, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: linear-gradient(to br, #f1f5f9, #fff, #e0f2fe); }}
        .card {{ background: white; border-radius: 24px; padding: 40px; max-width: 400px; box-shadow: 0 20px 60px rgba(0,0,0,0.1); text-align: center; }}
        h1 {{ color: #dc2626; font-size: 24px; margin-bottom: 16px; }}
        p {{ color: #64748b; line-height: 1.6; }}
        a {{ display: inline-block; margin-top: 20px; padding: 12px 24px; background: #0f172a; color: white; text-decoration: none; border-radius: 999px; font-weight: 500; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Login Error</h1>
        <p>{}</p>
        <a href="/login">← Back to Login</a>
    </div>
</body>
</html>"#, message);

    (
        StatusCode::BAD_REQUEST,
        [("Content-Type", "text/html")],
        html,
    )
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    /// Test that a valid legacy PBKDF2-SHA256 password hash is verified correctly.
    /// 
    /// This hash is generated by the legacy system for password "test123" with known salt.
    #[test]
    fn test_verify_legacy_password_valid() {
        // Legacy password hash format: pbkdf2_sha256$iterations$salt$hash
        // Generated a test hash for password "test123"
        let password = "test123";
        
        // Generate a known hash for testing using the same algorithm
        use sha2::Sha256;
        use hmac::Hmac;
        use pbkdf2::pbkdf2;
        use base64::{Engine as _, engine::general_purpose::STANDARD};
        
        let salt = "testsalt123";
        let iterations: u32 = 600000;
        let mut derived_key = vec![0u8; 32];
        let _ = pbkdf2::<Hmac<Sha256>>(
            password.as_bytes(),
            salt.as_bytes(),
            iterations,
            &mut derived_key,
        );
        let hash_b64 = STANDARD.encode(&derived_key);
        let legacy_hash = format!("pbkdf2_sha256${}${}${}", iterations, salt, hash_b64);
        
        assert!(
            verify_legacy_password(password, &legacy_hash),
            "Valid password should be verified successfully"
        );
    }

    /// Test that an invalid password is rejected.
    #[test]
    fn test_verify_legacy_password_invalid() {
        // Create a valid hash for "correct_password"
        use sha2::Sha256;
        use hmac::Hmac;
        use pbkdf2::pbkdf2;
        use base64::{Engine as _, engine::general_purpose::STANDARD};
        
        let correct_password = "correct_password";
        let wrong_password = "wrong_password";
        let salt = "randomsalt";
        let iterations: u32 = 600000;
        
        let mut derived_key = vec![0u8; 32];
        let _ = pbkdf2::<Hmac<Sha256>>(
            correct_password.as_bytes(),
            salt.as_bytes(),
            iterations,
            &mut derived_key,
        );
        let hash_b64 = STANDARD.encode(&derived_key);
        let legacy_hash = format!("pbkdf2_sha256${}${}${}", iterations, salt, hash_b64);
        
        assert!(
            !verify_legacy_password(wrong_password, &legacy_hash),
            "Wrong password should be rejected"
        );
    }

    /// Test that malformed hash formats are rejected.
    #[test]
    fn test_verify_legacy_password_malformed() {
        let password = "anypassword";
        
        // Too few parts
        assert!(!verify_legacy_password(password, "pbkdf2_sha256$100000"));
        
        // Empty hash
        assert!(!verify_legacy_password(password, ""));
        
        // Wrong algorithm
        assert!(!verify_legacy_password(password, "argon2$100000$salt$hash"));
        
        // Invalid iteration count
        assert!(!verify_legacy_password(password, "pbkdf2_sha256$invalid$salt$hash"));
        
        // Zero iterations
        assert!(!verify_legacy_password(password, "pbkdf2_sha256$0$salt$hash"));
    }

    /// Test AuthConfig serialization
    #[test]
    fn test_auth_config_serialization() {
        let config = AuthConfig {
            google_enabled: true,
            magic_link_enabled: false,
            password_enabled: true,
        };
        
        let json = serde_json::to_string(&config).unwrap();
        assert!(json.contains("\"google_enabled\":true"));
        assert!(json.contains("\"magic_link_enabled\":false"));
        assert!(json.contains("\"password_enabled\":true"));
    }

    /// Test LoginRequest deserialization
    #[test]
    fn test_login_request_deserialization() {
        let json = r#"{"email": "test@example.com", "password": "secret123"}"#;
        let request: LoginRequest = serde_json::from_str(json).unwrap();
        
        assert_eq!(request.email, "test@example.com");
        assert_eq!(request.password, "secret123");
        assert!(!request.remember_me); // Default should be false
    }

    /// Test LoginRequest with remember_me
    #[test]
    fn test_login_request_with_remember_me() {
        let json = r#"{"email": "test@example.com", "password": "secret", "remember_me": true}"#;
        let request: LoginRequest = serde_json::from_str(json).unwrap();
        
        assert!(request.remember_me);
    }

    /// Test Claims serialization
    #[test]
    fn test_claims_serialization() {
        let claims = Claims {
            sub: "123".to_string(),
            email: "user@example.com".to_string(),
            business_id: Some(456),
            exp: 1234567890,
        };
        
        let json = serde_json::to_string(&claims).unwrap();
        assert!(json.contains("\"sub\":\"123\""));
        assert!(json.contains("\"email\":\"user@example.com\""));
        assert!(json.contains("\"business_id\":456"));
    }
}
