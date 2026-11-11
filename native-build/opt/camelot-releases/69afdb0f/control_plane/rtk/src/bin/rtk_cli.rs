// SPDX-License-Identifier: MIT

//! rtk_cli — thin CLI over the real `rtk::strip` engine so non-Rust callers
//! (e.g. the Go omni-router) can invoke RTK noise-stripping via subprocess.
//!
//! Usage:
//!   rtk_cli "<text>"     strip the argument
//!   echo "<text>" | rtk_cli    strip stdin (when no arg given)
//!
//! Output: one line of JSON: {"engine":"rtk","stripped":"<cleaned text>"}

use std::io::Read;

fn main() {
    // Prefer the first CLI arg; fall back to stdin.
    let input = match std::env::args().nth(1) {
        Some(a) => a,
        None => {
            let mut buf = String::new();
            let _ = std::io::stdin().read_to_string(&mut buf);
            buf
        }
    };

    let stripped = rtk::strip(&input);
    // Hand-rolled JSON-string escaping (no serde dependency — keeps the build
    // std-only and fast).
    println!("{{\"engine\":\"rtk\",\"stripped\":\"{}\"}}", json_escape(&stripped));
}

fn json_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 8);
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out
}
