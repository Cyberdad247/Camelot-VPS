# Security Model: Camelot-VPS Hub

## 1. Threat Model

| Threat | Mitigation |
|--------|------------|
| Cross-tenant access | PostgreSQL RLS, Qdrant payload filters |
| VFS escape | Path normalization, allowlist, workspace root |
| Forged lease | Ed25519 signature verification, epoch check |
| Receipt tampering | SHA-256 hash chain, anchor export |
| Consent bypass | Multivoice registry lookup before send |

## 2. Controls

- **Auth:** mTLS for node auth, session cookies for browser.
- **Tenant Derivation:** Server-side only, never trust client.
- **Audit:** Receipt export with hash-chain verification.
- **Compliance:** SOC 2-aligned evidence (access logs, policy decisions).
