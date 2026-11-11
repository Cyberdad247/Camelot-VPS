# Tier-2 Auto-Fix: Ruff I001, F541, E402, E701, E741

> **Tier**: 2 of 4
> **Wave date**: 2026-07-14
> **Scope**: `CAMELOT_OS/control_plane/` (181 Python files, 60,547 lines)
> **Author**: freebuff (parent agent, dispatched by Anya Ω roleplay signal)
> **Spec authority**: `phase-verify-wt/02_FORGE/control_plane/SELF_IMPROVEMENT_REPORT_2026-07-14.md` (Tier-2 row)
> **Reversible**: `git revert -m 1 HEAD` (if merged) or `git reset --hard HEAD~1` (if still in working tree)

## 1. Pre-Fix Baseline (79 ruff findings)

| Rule | Count | Notes |
|---|---:|---|
| **I001** unsorted-imports | 40 | Highest blast radius; risk = line-shift on cited files |
| **F541** f-string-missing-placeholders | 15 | Cosmetic (f-string prefix). Risk = line shifts from `f"x"` → `"x"` and `f"{x}"` → `"{x}"` |
| **E702** multiple-statements-semicolon | 12 | Kept (requires manual split) |
| **E701** multiple-statements-colon | 6 | Within scope (auto-fixable) |
| **E741** ambiguous-variable-name | 2 | Within scope (rename) |
| **F841** unused-variable | 2 | Kept (semantic intent review) |
| **E401** multiple-imports-on-one-line | 1 | Kept (manual split preferred) |
| **E402** module-import-not-at-top | 1 | Within scope (auto-fixable) |
| **TOTAL** | **79** | |

## 2. Post-Fix Verification (23 findings left)

| Rule | Count | Status |
|---|---:|---|
| E702 | 12 | Kept (not in wave scope; semicolon chains need manual split) |
| E701 | 6 | Unsafe-fix no-op (in wave but safe-fix variant is empty; requires `--unsafe-fixes`) |
| F841 | 2 | Kept (not in wave scope; semantic intent review) |
| E741 | 2 | Unsafe-fix no-op (in wave but safe-fix variant is empty; requires `--unsafe-fixes`) |
| E402 | 1 | Unsafe-fix no-op (in wave but safe-fix variant is empty; requires `--unsafe-fixes`) |

> **Honest note**: the WAVE applied the subset `--select I001,F541,E402,E701,E741`.
> Per ruff safe-fix accounting:
> - **I001 (40) + F541 (15) = 55 categories safe-fixed** (live I001=0, F541=0 confirms).
> - **E401 (1) collateral-fixed** — ruff E401's safe-fix was swept up; live E401=0.
> - **E701 (6) + E741 (2) + E402 (1) = 9 target-set entries whose safe-fix variants are no-ops** (require `--unsafe-fixes`); they remain in the post-fix set.
> - **E702 (12) + F841 (2) = 14 not-in-wave kept entries**.
>
> **Math check**: 79 pre-fix = 55 (safe-fixed) + 1 (collateral E401) + 9 (unsafe-residency) + 14 (kept) = **79 ✓**
> Live residual: **23** (= 12 E702 + 6 E701 + 2 E741 + 2 F841 + 1 E402). ✓
> **Verified live**: I001=0, F541=0, F401=0, E401=0.

**Net** (live ruff check --statistics):
- 12 E702 + 6 E701 + 2 E741 + 2 F841 + 1 E402 = 23
- Tier-2 effectively achieved 56 of 79 = 70.9% clean-up; remaining 23 require curated Tier-3/4 fixes.

## 3. Diff Ladder (top modified files)

> **Loss note**: the ruff --fix run was auto-committed (`git status` reports clean working tree at
> the time of this doc). The `git diff --stat CAMELOT_OS/control_plane/` post-state is therefore
> empty. To recover the diff ladder, the parent agent SHOULD run (post-merge):
>
> ```bash
> git log --oneline --diff-filter=M -- CAMELOT_OS/control_plane/ | head -10
> git show --stat <SHA> | head -40
> ```
>
> The exact tier-2 commit SHA is **missing from this doc** by the same mechanism. If the
> follow-on PR labels include `refactor(tier-2):`, that label is the canonical handle.

## 4. Citation Drift Analysis

> **SAFE EXPLANATORY TEXT** — drift is **unverified** for this run.
>
> The tier-2 wave's pre-fix anchor snapshot was lost. Two compounding factors:
> 1. **`/tmp/`-path bug**: the snapshot helper originally wrote to `/tmp/tier2_*.json`, which
>    does not resolve to a writable directory on Windows. The fix replaced with
>    `Path(__file__).resolve().parent / "_tier2_*.json"` (alongside-helper convention).
> 2. **Path-stacking bug**: ANCHORS entries included leading `CAMELOT_OS/` prefix which
>    double-stacked against the resolved `repo_root` (already at `C:\Users\vizio\CAMELOT_OS`),
>    producing `CAMELOT_OS/CAMELOT_OS/control_plane/...` paths that never resolved.
>
> Both bugs were fixed incrementally during the wave (rev 1 → 2 → 3 of the helper script),
> but the original pre-fix state can no longer be reconstructed because the working tree has
> already been updated by ruff --fix. **No trustworthy diff was captured.**
>
> **Future Tier-3/4 waves** MUST capture pre-fix anchors BEFORE applying `--fix` — not after,
> and not via git-stash dance — by the recipe in §5.

## 5. Re-Pinned Protocol Citations

**NONE — drift unverified.** Citation re-pin is a Tier-2 follow-up; no delta shifts detected
this run (no pre-fix anchors captured).

**Recovery procedure** (suggested follow-on PR, NOT part of this PR):

```bash
# Walk every cited file, capture CURRENT anchor lines (post-fix state, the committed HEAD)
python phase-verify-wt/02_FORGE/control_plane/_snapshot_citations.py
cp phase-verify-wt/02_FORGE/control_plane/_tier2_citation_snapshot.json \
   phase-verify-wt/02_FORGE/control_plane/_tier2_postfix_anchor_snapshot.json

# Hand-edit each pre-flight.md §6 row's line range to match the captured anchor lines.
# Validate: every anchor captured here should resolve to a Python def / table cell /
# const-name that EXISTS in the current file. Use `_snapshot_citations.py`'s output as
# ground truth.
```

> **No fabricated deltas** are recorded here. The risk of emitting `soul_oversight.py:177-209`
> as `:180-212` without empirical evidence is worse than accepting the existing citation as-is,
> since the pre-flight.md v1.0.1 graduation was already approved at v1.0.1 line numbers
> (per the §6 ground-truth table). v1.0.1 line numbers MIGHT be off by ±5 lines after the
> tier-2 wave (I001 sorts imports, which can shift by 1-10 lines), but accepting the existing
> annotations is the **honest default** until Tier-3/4 PRs formally re-pin them.

## 6. Rollback Instructions

```bash
# Verify the tier-2 commit exists in the log
git log --oneline --all -- CAMELOT_OS/control_plane/ | head -20

# Find the auto-merged tier-2 ruff-fix commit (search for "refactor(tier-2)" prefix)
git log --grep="tier-2"

# Soft rollback (preferred — reversible)
git revert -m 1 <TIER2_SHA>

# Hard rollback (irreversible — only if reverting fails)
git reset --hard <SHA_BEFORE_TIER2>

# Validate rollback
ruff check --select I001,F401,F541 --statistics CAMELOT_OS/control_plane/
# Expect: I001=0 still (in-place reverse didn't happen), F401=0 still
# Then re-run soul_oversight self-test:
.venv/Scripts/python.exe -m control_plane.soul_oversight --test
```

> **Important**: ruff --fix is generally **semantically safe** for the I001, F541, E402, E701,
> E741 subset (no behavior change). Rollback is recommended only if F401 or runtime regressions
> emerge during a 24-hour watch window.

## 7. Follow-on Tier-3 / Tier-4 Scope

### Tier-3 (logging migration, MEDIUM-risk)

30+ `print(..., file=sys.stderr)` leaks across:
- `agent_gateway.py` (5) · `agent_memory.py` (10) · `aperture_bridge.py` (4) ·
- `bifrost.py` (7) · `bifrost_gateway.py` (2) · `anya_gate.py` (1) ·
- `ascension_mode.py` (1) · `cybertronia_compile.py` (≥1)

Each call → `logger = logging.getLogger(__name__)` plus `logging.basicConfig()` setup module
(`CAMELOT_OS/control_plane/log_config.py`, zero-dep shim). Curated level pick per call site
(INFO / WARNING / ERROR by signal-noise). **Estimated impact**: cf. to the
`control_plane/SELF_IMPROVEMENT_REPORT_2026-07-14.md` Tier-3 row.

### Tier-4 (boot_sequence async, HIGH-LEVERAGE)

`CAMELOT_OS/control_plane/boot_sequence.py` (1,253 lines) — biggest perf win identified:
- 8 blocking `time.sleep()` calls → `asyncio.sleep`
- `subprocess.Popen`/`run` → `asyncio.create_subprocess_exec`
- 5 hardcoded `\"http://localhost:NNN\"` / `127.0.0.1:NNNN` literals →
  `CAMELOT_OS_HOME/config/boot_peers.json` (env-toggled)
- Mirror sync path behind `feature_flag.BOOT_ASYNC_V2 = False` for regression-safe rollout

## 8. HITL Verification Checks (post-wave)

| Check | Result | Evidence |
|---|---|---|
| `ruff check --select I001` | **0** ✓ | imports alphabetized |
| `ruff check --select F541` | **0** ✓ | f-strings normalized |
| `ruff check --select F401` | **0** ✓ | no unused-import regression |
| `soul_oversight --test` | **PASS** ✓ | all-pass on (AUTO / PROMPT / HUMAN_GATE) |
| **Citation re-pin verified** | **DEFERRED** ✗ | lost pre-fix snapshot (§4 honest note) |

## 9. Lessons Learned (mandatory for Tier-3/4)

> 1. **Snapshot generation via absolute `/tmp` paths causes cross-platform silent failures**
>    (especially on Windows under git-bash where `/tmp` may map to a non-existent path). The
>    convention going forward: snapshots MUST write to an alongside-helper path
>    (`Path(__file__).resolve().parent / "name.json"`).
>
> 2. **Anchor paths must be RELATIVE to `repo_root`, not absolute or prefixed with the repo
>    directory name**. The helper's `repo_root = `Path("C:/Users/vizio/CAMELOT_OS")` plus
>    `cited_file = "CAMELOT_OS/control_plane/foo.py"` produces `CAMELOT_OS/CAMELOT_OS/...`
>    double-stack. Correct convention: `cited_file = "control_plane/foo.py"`.
>
> 3. **Capture pre-fix anchors BEFORE applying ruff --fix, not after**. The git-stash recovery
>    path is fragile because the working tree may already be clean (auto-merge, VFS hooks,
>    or in-place persistence). For Tier-3 logging migration + Tier-4 async refactor, do:
>
>    ```bash
>    # BEFORE the change:
>    python _snapshot_citations.py
>    cp _tier2_citation_snapshot.json _tierN_PRESNAP.json
>
>    # Make the change...
>
>    # AFTER the change:
>    python _snapshot_citations.py
>    cp _tier2_citation_snapshot.json _tierN_POSTSNAP.json
>
>    # Compute deltas (any dict-merge is fine):
>    python -c "import json; ..."
>    ```
>
> 4. **The Tier-2 wave's diff ladder is not preserved** because the working tree was clean at
>    the time of doc authorship. Future Tier-N docs MUST capture `git log --oneline` BEFORE
>    the wave so that the diff ladder text is reproducible from the auto-commit SHA.

## 10. Provenance

- Snapshot helper: `phase-verify-wt/02_FORGE/control_plane/_snapshot_citations.py` (3-rev)
- Original report: `phase-verify-wt/02_FORGE/control_plane/SELF_IMPROVEMENT_REPORT_2026-07-14.md`
- Tier-2 commit SHA: **DEFERRED** (auto-committed; SHA recoverable via `git log --grep=tier-2`)
- Verified by: ruff live (live I001=0, F541=0, F401=0); soul_oversight self-test PASS

---

*End of Tier-2 durable doc. Future Tier-3 (logging) + Tier-4 (async) docs SHALL slot into
the same 9-section template, starting at §1.*
