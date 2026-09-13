use axum::http::{header::AUTHORIZATION, HeaderMap};

pub fn bearer_allowed(headers: &HeaderMap, expected: &str) -> bool {
    headers
        .get(AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .map(|value| value == format!("Bearer {expected}"))
        .unwrap_or(false)
}

pub fn promotion_allowed(headers: &HeaderMap, expected: &str) -> bool {
    headers
        .get("x-camelot-promotion-assertion")
        .and_then(|value| value.to_str().ok())
        .map(|value| value == expected)
        .unwrap_or(false)
}
