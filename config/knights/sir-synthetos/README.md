# Sir Synthetos runtime bundle

This directory documents the first Camelot v3 persona-runtime deployment bundle.

Production deployment must provision four files outside the repository:

- `soul.json` — signed `camelot-soul/1`
- `persona.json` — `camelot-persona/1`, digest-bound by the Knight package
- `enterprise-role.json` — signed `camelot-enterprise-role/1`
- `knight-package.json` — signed `camelot-knight-package/1`

The signing key is not stored here.

Initial policy posture:

```text
persona: sir_synthetos
risk ceiling: T1
cognition ceiling: L1
allowed effects:
  ro.fetch
  ro.audit
  internal.synth
authority: none
```

Knight Registry and Context Compiler both independently verify the bundle using the pinned registry public key. The Context Compiler may sign a short-lived Spark for provenance, but that Spark is explicitly `context-not-authority`.
