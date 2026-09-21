#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
REGISTRY = CONTRACTS / "registry.json"
LOCK = CONTRACTS / "contracts.lock"

def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()

def fail(message: str) -> None:
    raise SystemExit(f"contract-registry: FAIL: {message}")

registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
lock = json.loads(LOCK.read_text(encoding="utf-8"))

if registry.get("registryVersion") != "camelot-contract-registry/1":
    fail("unsupported registryVersion")
if registry.get("authoritySemantics") != "contract-registry-not-authority":
    fail("registry authority semantics changed")
if registry.get("lockFile") != "contracts/contracts.lock":
    fail("unexpected lockFile")
if lock.get("lockVersion") != "camelot-contract-lock/1":
    fail("unsupported lockVersion")
if lock.get("authoritySemantics") != "contract-lock-not-authority":
    fail("lock authority semantics changed")
if lock.get("sourceIntegrityAlgorithm") != "git-blob-sha1":
    fail("unexpected source integrity algorithm")
if lock.get("releaseDigestRequirement") != "sha256":
    fail("release proof must require sha256")

schema_paths = sorted(
    p.relative_to(ROOT).as_posix()
    for p in CONTRACTS.rglob("*.schema.json")
)
locked = lock.get("contracts", [])
locked_by_path = {item["path"]: item for item in locked}

if len(locked_by_path) != len(locked):
    fail("duplicate contract path in lock")

missing = sorted(set(schema_paths) - set(locked_by_path))
extra = sorted(set(locked_by_path) - set(schema_paths))
if missing:
    fail(f"unlocked schemas: {missing}")
if extra:
    fail(f"lock references missing schemas: {extra}")

aggregate = hashlib.sha256()
for path in schema_paths:
    data = (ROOT / path).read_bytes()
    observed_blob = git_blob_sha(data)
    expected_blob = locked_by_path[path]["gitBlobSha"]
    if observed_blob != expected_blob:
        fail(f"byte lock mismatch for {path}: expected {expected_blob}, observed {observed_blob}")

    try:
        json.loads(data.decode("utf-8"))
    except Exception as exc:
        fail(f"invalid JSON in {path}: {exc}")

    content_sha256 = hashlib.sha256(data).hexdigest()
    aggregate.update(path.encode("utf-8"))
    aggregate.update(b"\0")
    aggregate.update(content_sha256.encode("ascii"))
    aggregate.update(b"\n")

print(
    "contract-registry: verified "
    f"{len(schema_paths)} schemas "
    f"aggregateSha256={aggregate.hexdigest()}"
)
