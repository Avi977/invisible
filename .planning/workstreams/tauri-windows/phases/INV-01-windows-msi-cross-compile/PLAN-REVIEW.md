# PLAN-REVIEW — Phase 1: Windows .msi cross-compile

**Verdict:** REVISE
**Reviewer:** gsd-plan-checker (Opus 4.7, 1M context)
**Date:** 2026-06-01
**Plan under review:** `01-01-PLAN.md` (4 tasks, autonomous, wave 1)

---

## Summary

The plan covers all 6 ROADMAP success criteria with concrete `<done>` clauses, is well-scoped (single Tauri config edit + build + verification doc), respects the workstream's file-lane constraints, and has a robust verify step for the artefact. **One blocker** — the documented mechanism for routing `cargo tauri build` through `cargo-xwin` from macOS is misstated as "auto-detected, no flag needed." Empirically and per upstream docs, Tauri requires an explicit signal: either `--runner cargo-xwin`, a `.cargo/config.toml` runner entry, or invoking `cargo xwin build` directly. Without this fix, Task 01-03 will compile-fail at the linker stage with `link.exe not found` / `lld-link` errors on a Mac.

One additional **warning**: the verify gate for the long-running build does not declare an extended timeout, which will trip the default 2-minute bash timeout used by autonomous execution.

---

## Goal Coverage (1/1 — PASS)

All six ROADMAP success criteria trace to covering tasks and `<done>` clauses:

| SC | Criterion (verbatim from ROADMAP) | Task | `<done>` evidence |
|----|-----------------------------------|------|-------------------|
| 1 | `cargo xwin --version` resolves | 01-01 | "`cargo xwin --version` prints a version string AND `rustup target list --installed` contains `x86_64-pc-windows-msvc`" |
| 2 | `bundle.targets` includes `"msi"` | 01-02 | "`bundle.targets` contains `\"msi\"`" |
| 3 | `bundle.windows.wix` block w/ productName + manufacturer + language | 01-02 | "`bundle.windows.wix.language` is `[\"en-US\"]`; `bundle.publisher` is `\"The Profit Platform\"`" (productName inherited from top-level — correct per Tauri 2.x schema) |
| 4 | Build succeeds; `.msi` at expected path | 01-03 | "`.msi` file exists at the exact expected path" |
| 5 | SHA256 captured in PHASE-VERIFICATION.md | 01-04 | "contains a 64-hex-char SHA256" |
| 6 | Size in [15, 40] MB | 01-03 + 01-04 | Verify `[ "$SIZE" -ge 15728640 ] && [ "$SIZE" -le 41943040 ]`; recorded in PHASE-VERIFICATION |

Coverage is complete.

---

## Issues

### BLOCKER — B1: cargo-xwin invocation path is not actually triggered

**Dimension:** task_completeness / key_links_planned
**Severity:** blocker
**Plan:** 01-01
**Task:** 01-03

**The claim (PLAN.md line 188 + frontmatter `key_links`):**
> "Tauri 2.11 auto-detects cargo-xwin on a non-Windows host and routes the cargo invocation through it; no extra flag is needed."

**Reality:** Tauri's CLI does not auto-route cargo through `cargo-xwin`. The supported mechanisms to make `cargo tauri build --target x86_64-pc-windows-msvc` actually use the xwin toolchain from macOS are (any one of):

1. **`--runner cargo-xwin` flag** (Tauri CLI native runner override):
   ```
   cargo tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc
   ```
2. **`.cargo/config.toml` runner entry** at the repo (or `src-tauri/`) level:
   ```toml
   [target.x86_64-pc-windows-msvc]
   runner = "cargo-xwin"
   linker = "lld"  # optional; cargo-xwin handles this
   ```
3. **Direct `cargo xwin build`** (bypasses `cargo tauri` entirely — loses bundler).

The first option is least invasive and keeps the plan additive. The second is the "set it once, all future builds work" path and is the documented xwin idiom.

Without one of these, `cargo` will hand the Windows target to the default macOS linker (`cc`/`ld`), which has no MSVC awareness, and the build fails at the link stage — Task 01-03 verify never reaches a `.msi` artefact.

The planner's own ROADMAP entry hedges: "cargo xwin or NSIS bundler from macOS" — implying explicit `cargo xwin`. The PLAN.md then drops the explicit invocation in favour of an unverified auto-detect claim.

**Required edit (pick one — recommend option A for minimal scope):**

**Option A (preferred, minimal):** Change Task 01-03 step 3 to:
```
3. Run: `cargo tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc 2>&1 | tee /tmp/inv-01-build.log`
```
Update the `key_links` entry accordingly:
```yaml
- from: "cargo tauri build"
  to: "cargo-xwin"
  via: "explicit --runner cargo-xwin flag"
  pattern: "--runner cargo-xwin"
```
Update PHASE-VERIFICATION.md template SC4 evidence row to mention the flag.

**Option B (more durable, slightly larger blast radius):** Add a Task 01-02b that writes `.cargo/config.toml`:
```toml
[target.x86_64-pc-windows-msvc]
runner = "cargo-xwin"
```
- Add `.cargo/config.toml` to `files_modified`.
- Verify the file is in `.gitignore` requirements OR commit it. (Recommend commit — it's the canonical place for cross-compile config.)
- Then Task 01-03 keeps its current invocation.

**Why this is a blocker, not a warning:** If the assumption is wrong, the entire phase fails. The planner explicitly flagged this as an assumption in their own summary. Treating it as a warning shifts the risk to the executor, who will burn a 30-minute cold build before discovering the failure.

---

### WARNING — W1: Verify gate lacks explicit timeout for the cold build

**Dimension:** scope_sanity
**Severity:** warning
**Plan:** 01-01
**Task:** 01-03

The `<action>` says "~30 min wall-clock cold". The `<verify>` `<automated>` command only runs the post-build `file` check, not the build itself, so the verify gate is fast. But the **build step** inside `<action>` (`cargo tauri build ...`) has no timeout declared. If the autonomous executor runs Task 03's action via a default bash invocation (2-min default), it kills the build mid-MSVC-SDK download.

**Required edit:** Add to Task 01-03 action, after step 3:

> Use bash `timeout: 1800000` (30 min) when invoking the build command in an autonomous tool call. The build is bounded by the network speed of Microsoft's `aka.ms` CDN on first run and CPU-bound on subsequent runs.

Or, embed the directive in the action prose:

> NOTE TO EXECUTOR: This bash invocation must use `timeout: 1800000` (30 minutes). Default 2-minute timeout will kill the build during MSVC SDK download.

---

### WARNING — W2: `wixtools` install path not exercised by the verify

**Dimension:** verification_derivation
**Severity:** warning
**Plan:** 01-01
**Task:** 01-03

The action acknowledges that the build may need `brew install wixtools` ("WiX template missing" failure mode), but the `<done>` clause only checks the final artefact. If `wixtools` is missing, the build will fail with a confusing error that the executor must then diagnose against the failure-modes list.

**Recommended edit (not blocking — it's a known-issue workaround):** Add a pre-flight to Task 01-03:
```
0. Check whether `wixtools` is on PATH: `command -v candle || brew list wixtools 2>/dev/null`. If neither resolves, run `brew install wixtools` before the build. (Skip if already installed.)
```
This converts a runtime failure into a deterministic pre-flight, saving a ~30-min wasted build.

---

### INFO — I1: PHASE-VERIFICATION criteria table strict-match on placeholder regex

**Dimension:** task_completeness
**Severity:** info
**Plan:** 01-01
**Task:** 01-04

The verify regex `\{[a-z_]+\}` rejects literal `{lowercase_with_underscores}` strings — but the template uses `{YYYY-MM-DD of completion}`, `{actual version string}`, `{sha256 from Task 03}`, etc. Some of those contain spaces and won't match the regex, so the verify won't catch them as un-replaced placeholders. Concretely:
- `{YYYY-MM-DD of completion}` — contains spaces, NOT matched (false negative)
- `{sha256 from Task 03}` — contains spaces, NOT matched
- `{actual version string}` — contains spaces, NOT matched

Only literal placeholders like `{short-sha}` or `{size_mb}` are caught.

**Recommended edit:** Tighten the regex:
```bash
! grep -qE '\{[^}]*\}|TBD|TODO' "$F"
```
This catches any `{...}` pair on a single line regardless of content. Minor robustness fix.

---

## Other checks (PASS)

### Independence (PASS)

`files_modified` lists exactly:
- `src-tauri/tauri.conf.json`
- `.planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/PHASE-VERIFICATION.md`

No edits to `frontend/`, `frontend-vite/src/`, `bin/`, `lib/`, `src-tauri/src/*.rs`. Task 02 action explicitly prohibits touching `productName`, `version`, `identifier`, `build`, `app`. `beforeBuildCommand` runs `pnpm build` in `frontend-vite/` but that is read-only execution of an existing script — sibling workstream territory is not crossed. Task 03 produces only gitignored artefacts under `src-tauri/target/`. Threat model T-INV-01-03 explicitly disclaims responsibility for the `frontend-vite/` lockfile.

If Option B in B1 is adopted, `.cargo/config.toml` is added — this is the **only** file outside the declared lane that adoption would touch. It's a new top-level file owned by no sibling workstream; safe.

### WiX block correctness (PASS, with one nuance)

Tauri 2.x reads manufacturer from `bundle.publisher`. The plan sets `"publisher": "The Profit Platform"`. The `bundle.windows.wix.language` array drives the output filename suffix (`_en-US.msi`), which the plan correctly mirrors in the expected artefact path. `productName` is correctly inherited from top-level (not duplicated under `wix`). The decision to omit `upgradeCode` for Phase 1 is consistent with CONTEXT.md "Constraints" and is explicitly handed off to Phase 2 in the PHASE-VERIFICATION template.

**Nuance:** Tauri's WiX bundler auto-derives an `UpgradeCode` UUID from the `identifier` string on each build. This UUID is **stable** (a hash of the identifier), not random, so a subsequent Phase 2 build with the same identifier produces the same UpgradeCode — meaning Phase 1's unsigned `0.1.0` MSI WILL be upgrade-compatible with Phase 2's signed `0.1.0` MSI. The hand-off note in PHASE-VERIFICATION.md should clarify this (Phase 2 can lock the auto-derived value rather than mint a fresh one).

### Build-time + size sanity (PASS)

- SHA capture: `shasum -a 256` is the correct macOS-native tool. Works.
- Size bounds: `[15728640, 41943040]` correctly translates 15-40 MB. The actual Tauri-shell-plus-Vite MSI lands around 18-25 MB based on similar projects, comfortably inside the band.
- `file` regex: `"msi installer\|composite document\|microsoft installer\|cdfv2"` (case-insensitive) covers the three common `file(1)` output variants on macOS for MSI artefacts (`CDFV2 Microsoft Installer`, `MSI Installer`, `Composite Document File V2 Document`). Robust.
- Artefact filename: `Invisible_0.1.0_x64_en-US.msi` matches Tauri 2.x's filename convention `${productName}_${version}_x64_${language}.msi`. Correct.

### First-build cold-download tolerance

See W1 above. The verify command itself (the `<automated>` block) is fast and won't flake — but the **build invocation inside the action** is at risk if the executor uses a default bash timeout.

### Task structure (PASS)

All four tasks have `<files>`, `<action>`, `<verify>`, `<done>`. Auto type. Verify commands are runnable shell. Done clauses are measurable. Two atomic Conventional Commits planned (`feat(tauri-windows):` for Task 02, `docs(tauri-windows):` for Task 04) — clean history.

### Dependency graph (PASS)

`depends_on: []`, wave 1, single plan. Trivially acyclic.

### CONTEXT.md compliance (PASS)

- Constraint "No code signing in this phase" — honoured (PHASE-VERIFICATION.md explicitly states "Code-signed? No").
- Constraint "No upgrade code yet" — honoured (PHASE-VERIFICATION.md says "Auto-generated by Tauri ... locked in Phase 2").
- Constraint "PR #7 stacking" — out of plan scope; branch state already on `ws/tauri-windows`.
- Failure-mode 1 (cold download) — partially addressed (see W1).
- Failure-mode 2 (WiX template) — partially addressed (see W2).
- Failure-mode 3 (linker path quirk) — addressed inline in Task 03 action.
- Out-of-scope items (Windows VM smoke-test, signing, auto-updater, CI release workflow) — correctly excluded.

### Threat model (PASS)

STRIDE register is comprehensive, with 8 threats classified, each with disposition + mitigation. Trust boundaries match the actual external network surface (crates.io + Microsoft CDN + npm registry). T-INV-01-SC (the supply-chain meta-threat) is correctly disposed: cargo-xwin is named in the ROADMAP so no Package Legitimacy Audit gate fires.

### Architectural tier compliance

No `Architectural Responsibility Map` in any RESEARCH.md for this phase (no RESEARCH.md exists, per CONTEXT.md). Dimension SKIPPED.

### Nyquist compliance (PASS)

Every task has an `<automated>` verify command:
- 01-01: `cargo xwin --version && rustup target list --installed | grep -qx ...`
- 01-02: `python3 -c "import json; ..."`
- 01-03: `test -f $MSI && file ... && stat ... && [ size in band ]`
- 01-04: `test -f $F && ! grep -qE '{...}' && grep ... 64-hex SHA && git log ...`

No watch-mode flags, no E2E suites, no delays > 30s in the verify itself (the build duration sits inside `<action>`, not `<verify>`).

Sampling: 4/4 tasks have automated verify. PASS.

---

## Verdict

**REVISE** — one blocker (B1: cargo-xwin invocation mechanism) plus two warnings (W1: build timeout, W2: wixtools pre-flight). Fix B1 + W1 minimum; W2 + I1 are quality improvements.

After B1 is addressed (recommend Option A — add `--runner cargo-xwin` flag to Task 01-03 and adjust the `key_links` entry to remove the "auto-detect" claim), and W1 is addressed (explicit 30-min timeout directive in Task 01-03 action), the plan is execution-ready.

---

## Concrete diff sketch (apply this for re-verification)

```diff
--- a/PLAN.md (Task 01-03 action, step 3)
+++ b/PLAN.md
@@
-3. Run: `cargo tauri build --target x86_64-pc-windows-msvc 2>&1 | tee /tmp/inv-01-build.log`
-   - Tauri 2.11 auto-detects cargo-xwin on a non-Windows host and routes the cargo invocation through it; no extra flag is needed.
+3. Run: `cargo tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc 2>&1 | tee /tmp/inv-01-build.log`
+   - The `--runner cargo-xwin` flag tells Tauri's CLI to route the underlying `cargo build` invocation through `cargo-xwin`, which provides the MSVC linker stubs from the downloaded SDK. Without this flag, cargo would attempt to use the macOS native linker for a Windows target and fail at the link stage.
+   - NOTE TO EXECUTOR: invoke this bash command with `timeout: 1800000` (30 minutes). Default 2-minute timeout will kill the build during the first-run MSVC SDK download (~700 MB from Microsoft's CDN).

--- a/PLAN.md (frontmatter must_haves.key_links)
+++ b/PLAN.md
@@
-    - from: "cargo tauri build --target x86_64-pc-windows-msvc"
-      to: "cargo-xwin"
-      via: "Tauri 2.11 auto-detects cargo-xwin on non-Windows host"
-      pattern: "cargo xwin --version"
+    - from: "cargo tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc"
+      to: "cargo-xwin"
+      via: "explicit --runner cargo-xwin flag on Tauri CLI"
+      pattern: "--runner cargo-xwin"
```

Optionally (W2 pre-flight):
```diff
--- a/PLAN.md (Task 01-03 action, before step 1)
+++ b/PLAN.md
@@
+0. Pre-flight: verify `wixtools` is installed (`command -v candle >/dev/null 2>&1 || brew install wixtools`). Skip the brew step if `candle` already resolves.
 1. `source "$HOME/.cargo/env"` (ensure PATH).
```

Optionally (I1 regex tightening):
```diff
--- a/PLAN.md (Task 01-04 verify automated)
+++ b/PLAN.md
@@
-test -f "$F" && ! grep -qE '\{[a-z_]+\}|TBD|TODO' "$F" && ...
+test -f "$F" && ! grep -qE '\{[^}]*\}|TBD|TODO' "$F" && ...
```

---

## Re-verification path

After the planner applies the diff:
1. Re-run `/gsd:plan-phase 1` with `--revise` to invoke the checker again.
2. Expected outcome: PASS on second pass.
3. Then proceed to `/gsd:execute-phase 1`.
