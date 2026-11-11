# native-build/ — live native (serve-mode) hub snapshot
Imported 2026-11-10 from camelot-host, live release tree /opt/camelot-releases/69afdb0f
(symlinked as /opt/camelot-ecosystem) + host surfaces. Release tag: v1.0.0-native.

| Imported path | On-box origin | Runs as |
|---|---|---|
| opt/camelot-releases/69afdb0f/control_plane/ | same (mesh bridge :8095/:8096, warp gate, watchtower module) | camelot-watchtower.service (module), mesh bridge service |
| opt/camelot-releases/69afdb0f/apps/bifrost/ | same (Bifrost operator API :3001, incl. 2026-11-08 warp-auth patch in src+dist) | camelot-bifrost.service (node dist/server.js) |
| opt/camelot-releases/69afdb0f/DEPLOY_MANIFEST.json | same | — |
| opt/hermesagent/data/cloudbrain/bob/ | Sir BoB gateway (OpenRouter-direct repoint 2026-11-10) + knowledge + notebooklm sync tool | bob-gateway.service |
| usr/local/lib/camelot/ | hub selfcheck + bootstrap audit + native_selfcheck.py | camelot-selfcheck.*, camelot-native-selfcheck.* |
| etc/systemd/system/* | unit files as installed on the host | systemd |

Excluded by design: every .env / key / token file (bob.key, tunnel.token, mesh.env,
atom.env — inventoried in the backup manifest, never in git), node_modules, venvs,
__pycache__, logs, runtime state.

One intentional redaction: control_plane/infra/cartridge_crucible.py carries a
deliberate self-test fixture (a fake key in a manifest named crucible-selftest-leaky,
used to prove the leak detector fires). The value is redacted in this import only;
the on-box original is untouched.
