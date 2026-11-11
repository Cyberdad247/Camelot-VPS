#!/usr/bin/env python3
"""Sir BoB <-> NotebookLM bridge (camelot.notebooklm aspect).

Queries the staged NotebookLM notebooks with grounded, citation-backed
answers via notebooklm-py. Results are cached (24h) to respect rate limits.
Auth: `notebooklm auth import-cookies` must have been run once; the daemon
health check pages ntfy if auth breaks.

Usage:
    ./venv/bin/python bob-notebooklm.py ask "question" [--notebook N]
    ./venv/bin/python bob-notebooklm.py health
"""
import json, os, sys, time, hashlib, subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(BASE, "venv", "bin", "notebooklm")
CACHE_DIR = os.path.join(BASE, "cache")
CACHE_TTL = 24 * 3600

def load_notebooks():
    with open(os.path.join(BASE, "notebooks.json")) as f:
        return json.load(f)["notebooks"]

def cache_key(nb_id, question):
    return hashlib.sha256(f"{nb_id}:{question}".encode()).hexdigest()[:16]

def cached(nb_id, question):
    os.makedirs(CACHE_DIR, exist_ok=True)
    p = os.path.join(CACHE_DIR, cache_key(nb_id, question) + ".json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < CACHE_TTL:
        with open(p) as f:
            return json.load(f)
    return None

def ask(question, nb_index=0):
    nbs = load_notebooks()
    nb = nbs[nb_index]
    hit = cached(nb["id"], question)
    if hit:
        hit["cached"] = True
        return hit
    r = subprocess.run(
        [VENV, "ask", question, "-n", nb["id"], "--json"],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "https_proxy": "http://127.0.0.1:8888",
             "http_proxy": "http://127.0.0.1:8888"},
    )
    if r.returncode != 0:
        return {"ok": False, "error": r.stderr.strip()[-500:]}
    try:
        data = json.loads(r.stdout)
    except ValueError:
        return {"ok": False, "error": "non-JSON reply", "raw": r.stdout[:500]}
    data["cached"] = False
    p = os.path.join(CACHE_DIR, cache_key(nb["id"], question) + ".json")
    with open(p, "w") as f:
        json.dump(data, f)
    os.chmod(p, 0o600)
    return data

def health():
    r = subprocess.run([VENV, "auth", "check", "--json"],
                       capture_output=True, text=True, timeout=30)
    ok = r.returncode == 0
    return {"ok": ok, "detail": (r.stdout or r.stderr).strip()[-300:]}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: ask \"question\" [--notebook N] | health"); sys.exit(1)
    if sys.argv[1] == "health":
        print(json.dumps(health(), indent=1)); sys.exit(0)
    if sys.argv[1] == "ask" and len(sys.argv) >= 3:
        nb = 0
        if "--notebook" in sys.argv:
            nb = int(sys.argv[sys.argv.index("--notebook") + 1])
        print(json.dumps(ask(sys.argv[2], nb), indent=1)[:4000]); sys.exit(0)
    print("unknown command"); sys.exit(1)
