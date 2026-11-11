// SPDX-License-Identifier: MIT

//! RTK — Real-Time Kontext noise stripper (CYBERTRONIA P1-T09).
//!
//! C ABI consumed by `control_plane/anya_gate.py::_load_rtk`:
//!     strip_context_noise(*const c_char) -> *const c_char
//!
//! Strips fenced markdown code blocks and HTML/XML tags, then collapses runs of
//! whitespace — byte-for-byte matching the pure-Python fallback in
//! `_stage_rtk_strip`, so pipeline behavior is identical whether or not the DLL
//! is loaded.

use std::ffi::{CStr, CString};
use std::os::raw::c_char;

/// Strip context noise from a UTF-8 C string. Returns a newly-allocated C string
/// whose ownership is transferred to the caller (ctypes copies on `.decode()`).
///
/// # Safety
/// `input` must be a valid, NUL-terminated C string pointer or NULL.
#[no_mangle]
pub unsafe extern "C" fn strip_context_noise(input: *const c_char) -> *const c_char {
    if input.is_null() {
        return std::ptr::null();
    }
    let text = match unsafe { CStr::from_ptr(input) }.to_str() {
        Ok(s) => s,
        Err(_) => return std::ptr::null(),
    };
    match CString::new(strip(text)) {
        // into_raw transfers ownership out; leaks one CString per call. RTK runs
        // once per intent, so the leak is bounded and acceptable.
        Ok(c) => c.into_raw() as *const c_char,
        Err(_) => std::ptr::null(),
    }
}

pub fn strip(text: &str) -> String {
    let no_fences = remove_fences(text);
    let no_tags = remove_tags(&no_fences);
    no_tags.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// Remove ```...``` fenced code blocks (including the fences), replacing each
/// with a single space. An unterminated fence drops the remainder.
fn remove_fences(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut rest = s;
    while let Some(start) = rest.find("```") {
        out.push_str(&rest[..start]);
        let after = &rest[start + 3..];
        match after.find("```") {
            Some(end) => {
                out.push(' ');
                rest = &after[end + 3..];
            }
            None => return out, // no closing fence — drop the rest
        }
    }
    out.push_str(rest);
    out
}

/// Replace every `<...>` tag with a single space (matches `re.sub(r"<[^>]+>", " ")`).
fn remove_tags(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut in_tag = false;
    for c in s.chars() {
        match c {
            '<' => in_tag = true,
            '>' if in_tag => {
                in_tag = false;
                out.push(' ');
            }
            _ if !in_tag => out.push(c),
            _ => {}
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::strip;

    #[test]
    fn strips_html_tags() {
        assert_eq!(strip("<b>hello</b> world"), "hello world");
    }

    #[test]
    fn strips_code_fences() {
        assert_eq!(strip("before ```rust\nlet x = 1;\n``` after"), "before after");
    }

    #[test]
    fn collapses_whitespace() {
        assert_eq!(strip("a    b\n\nc"), "a b c");
    }

    #[test]
    fn plain_text_unchanged() {
        assert_eq!(strip("build a dashboard"), "build a dashboard");
    }
}
