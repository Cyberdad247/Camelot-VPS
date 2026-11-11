## Native Harness Runners (Go and Rust)

`OMCTeam` can execute harness targets through native runners before falling back
to direct CLI dispatch.

### Runtime Selection

Set `CAMELOT_HARNESS_RUNTIME`:

- `auto` (default): prefer Go runner, then Rust runner, then Python fallback.
- `go`: require Go runner binary.
- `rust`: require Rust runner binary.
- `python`: disable native runners and use direct CLI fallback.

Optional overrides:

- `CAMELOT_GO_HARNESS_RUNNER`: absolute path to Go runner binary.
- `CAMELOT_RUST_HARNESS_RUNNER`: absolute path to Rust runner binary.

### Build Go Runner

```powershell
cd C:\Users\vizio\CAMELOT_OS\control_plane\runners\go
go build -o .\bin\harness-runner.exe .\cmd\harness-runner
```

Default Go runner location:
`C:\Users\vizio\CAMELOT_OS\control_plane\runners\go\bin\harness-runner.exe`

### Build Rust Runner

```powershell
cd C:\Users\vizio\CAMELOT_OS\control_plane\runners\rust
cargo build --release
```

Default Rust runner location:
`C:\Users\vizio\CAMELOT_OS\control_plane\runners\rust\target\release\harness_runner.exe`
