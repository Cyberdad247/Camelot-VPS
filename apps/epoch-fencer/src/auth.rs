use axum::http::{header::AUTHORIZATION, HeaderMap};

fn constant_time_eq(left: &str, right: &str) -> bool {
    let left = left.as_bytes();
    let right = right.as_bytes();
    if left.len() != right.len() {
        return false;
    }
    let mut diff = 0_u8;
    for (a, b) in left.iter().zip(right.iter()) {
        diff |= a ^ b;
    }
    diff == 0
}

pub fn bearer_allowed(headers: &HeaderMap, expected: &str) -> bool {
    let expected = format!("Bearer {expected}");
    headers
        .get(AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .map(|value| constant_time_eq(value, &expected))
        .unwrap_or(false)
}

pub fn promotion_allowed(headers: &HeaderMap, expected: &str) -> bool {
    headers
        .get("x-camelot-promotion-assertion")
        .and_then(|value| value.to_str().ok())
        .map(|value| constant_time_eq(value, expected))
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::constant_time_eq;

    #[test]
    fn compares_equal_length_credentials_without_early_content_exit() {
        assert!(constant_time_eq("alpha", "alpha"));
        assert!(!constant_time_eq("alpha", "alpHa"));
        assert!(!constant_time_eq("alpha", "alph"));
    }
}
