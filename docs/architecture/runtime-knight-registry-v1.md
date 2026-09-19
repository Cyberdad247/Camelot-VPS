# Runtime Knight Registry v1

This slice makes the Contract Forge persona identity package enforceable in Camelot-VPS without creating a second authority service.

## Boundary

The registry is a file-backed verification library loaded by Sentinel. It proves that a `knight:<persona_id>` actor is bound to a currently valid, signed Contract Forge bundle:

```text
Soul
  + camelot-persona/1
  + Enterprise Role
  + Knight Package
        |
        v
camelot-knight verifier
        |
        v
Sentinel
        |
        v
signed capability lease
```

The registry never issues permission. Sentinel remains the sole lease authority.

## Bundle format

A registry file is named:

`<package_id>.bundle.json`

and contains:

```json
{
  "package": {},
  "soul": {},
  "persona": {},
  "enterprise_role": {}
}
```

The three signed objects use `camelot-c14n-json/1`, SHA-256, domain-separated Ed25519 signatures, and the exact Contract Forge schemas copied from the canonical CAMELOT_OS contract branch. The unsigned persona competence profile is immutable because its full canonical digest is pinned inside the signed Knight Package.

## Sentinel migration rule

- Non-Knight service/operator actors remain backward compatible.
- Any actor whose id begins with `knight:` must present `knight_package_id`.
- When Knight registry configuration is enabled, Sentinel verifies the package before lease issuance.
- The resulting Sentinel-signed lease carries a `knight_binding` containing package id, package digest, persona id, and persona class.
- Policy evaluation re-loads the package and verifies the binding, so local lifecycle/revocation changes fail closed for active Knight leases.
- A package is identity and competence provenance only. It does not bypass Sentinel capability/resource checks.

## Configuration

Enable the registry by setting all of:

```text
CAMELOT_KNIGHT_REGISTRY_DIR=/etc/camelot/knights
CAMELOT_KNIGHT_PUBLIC_KEY=<32-byte Ed25519 public key in hex>
CAMELOT_KNIGHT_TENANT_SCOPE=tenant_primary
CAMELOT_KNIGHT_WORKSPACE_SCOPE=ws_camelot
```

Optional restrictive admission ceilings:

```text
CAMELOT_KNIGHT_MAX_RISK_TIER=T1
CAMELOT_KNIGHT_MAX_COGNITION_CEILING=L1
CAMELOT_KNIGHT_REVOKED_IDS=knightpkg_example,...
```

The current revocation list is a local control-plane input. A signed revocation event/checkpoint stream remains a later hardening step.
