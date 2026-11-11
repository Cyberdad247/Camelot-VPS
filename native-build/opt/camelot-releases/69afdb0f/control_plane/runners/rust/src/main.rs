// SPDX-License-Identifier: MIT

mod qdrant_memory;

use serde::Serialize;
use std::env;
use std::path::PathBuf;
use std::process::{Command, Stdio};

#[derive(Serialize)]
struct Payload {
    backend: String,
    knight_id: String,
    engine_cmd: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    returncode: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    stdout: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    stderr: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    prompt: Option<String>,
}

fn get_arg_value(args: &[String], key: &str, default: &str) -> String {
    args.windows(2)
        .find(|w| w[0] == key)
        .map(|w| w[1].clone())
        .unwrap_or_else(|| default.to_string())
}

fn resolve_command(engine: &str, prompt: &str) -> Result<Vec<String>, String> {
    if engine.to_ascii_lowercase().ends_with(".cmd") {
        return Ok(vec![
            "cmd.exe".to_string(),
            "/c".to_string(),
            engine.to_string(),
            "--print".to_string(),
            prompt.to_string(),
        ]);
    }

    let path_entries = env::var_os("PATH").ok_or_else(|| "PATH not set".to_string())?;
    for dir in env::split_paths(&path_entries) {
        let direct = dir.join(engine);
        if direct.exists() {
            return Ok(vec![direct.to_string_lossy().to_string(), prompt.to_string()]);
        }
        let exe = dir.join(format!("{engine}.exe"));
        if exe.exists() {
            return Ok(vec![exe.to_string_lossy().to_string(), prompt.to_string()]);
        }
    }
    Err(format!("engine not found: {engine}"))
}

fn print_payload(p: &Payload) {
    match serde_json::to_string_pretty(p) {
        Ok(s) => println!("{s}"),
        Err(_) => println!(
            "{{\"backend\":\"rust-native-harness\",\"status\":\"failed\",\"error\":\"serialization failure\"}}"
        ),
    }
}

#[tokio::main]
async fn main() {
    let args: Vec<String> = env::args().collect();

    // --probe-qdrant: connect to Qdrant Cloud (REST), list collections, print JSON
    if args.contains(&"--probe-qdrant".to_string()) {
        match qdrant_memory::QdrantRest::new() {
            Ok(qd) => match qd.probe().await {
                Ok(info) => println!("{}", serde_json::to_string_pretty(&info).unwrap()),
                Err(e)   => eprintln!("probe failed: {e}"),
            },
            Err(e) => eprintln!("QdrantRest::new failed: {e}"),
        }
        return;
    }

    let engine = get_arg_value(&args, "--engine", "");
    let prompt = get_arg_value(&args, "--prompt", "");
    let cwd = get_arg_value(&args, "--cwd", ".");
    let _timeout_sec: u64 = get_arg_value(&args, "--timeout-sec", "120")
        .parse()
        .unwrap_or(120);
    let knight_id = get_arg_value(&args, "--knight-id", "");

    let mut payload = Payload {
        backend: "rust-native-harness".to_string(),
        knight_id,
        engine_cmd: engine.clone(),
        returncode: None,
        stdout: None,
        stderr: None,
        status: None,
        error: None,
        prompt: None,
    };

    if engine.trim().is_empty() {
        payload.status = Some("failed".to_string());
        payload.error = Some("missing --engine".to_string());
        payload.prompt = Some(prompt);
        print_payload(&payload);
        return;
    }

    let command = match resolve_command(&engine, &prompt) {
        Ok(c) => c,
        Err(err) => {
            payload.status = Some("failed".to_string());
            payload.error = Some(err);
            payload.prompt = Some(prompt);
            print_payload(&payload);
            return;
        }
    };

    let abs_cwd = PathBuf::from(&cwd);
    let program = &command[0];
    let argv = &command[1..];

    let output = match Command::new(program)
        .args(argv)
        .current_dir(abs_cwd)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
    {
        Ok(out) => out,
        Err(err) => {
            payload.status = Some("failed".to_string());
            payload.error = Some(err.to_string());
            payload.prompt = Some(prompt);
            print_payload(&payload);
            return;
        }
    };
    payload.returncode = output.status.code();
    payload.stdout = Some(String::from_utf8_lossy(&output.stdout).trim().to_string());
    payload.stderr = Some(String::from_utf8_lossy(&output.stderr).trim().to_string());
    print_payload(&payload);
}
