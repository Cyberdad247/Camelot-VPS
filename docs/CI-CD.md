# CI/CD Pipeline: Camelot-VPS Hub

## 1. Stages

1. **Lint:** `golangci-lint`, `cargo clippy`, `eslint`.
2. **Test:** Go unit tests, Rust tests, Playwright E2E.
3. **Build:** Go binaries, Rust release, HTMX templates.
4. **Package:** `.deb` or systemd units.
5. **Deploy:** Ansible playbook to InterServer VPS.
6. **Verify:** Health check script, receipt-chain verification.

## 2. Secrets

- MinIO credentials (Vault or environment).
- Neo4j/Qdrant auth (environment).
- Ed25519 lease signing key (HSM or Vault).
