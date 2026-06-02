---
phase: INV-01-windows-msi-cross-compile
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src-tauri/tauri.conf.json
  - .planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/PHASE-VERIFICATION.md
autonomous: true
requirements:
  - INV-01-SC1   # cargo xwin --version resolves
  - INV-01-SC2   # bundle.targets includes "msi"
  - INV-01-SC3   # bundle.windows.wix block (productName + manufacturer + language)
  - INV-01-SC4   # cargo tauri build --target x86_64-pc-windows-msvc succeeds; .msi at expected path
  - INV-01-SC5   # SHA256 captured in PHASE-VERIFICATION.md
  - INV-01-SC6   # File size between 15 and 40 MB

must_haves:
  truths:
    - "`cargo xwin --version` resolves on this Mac"
    - "`rustup target list --installed` shows `x86_64-pc-windows-msvc`"
    - "`src-tauri/tauri.conf.json` `bundle.targets` array includes `\"msi\"`"
    - "`src-tauri/tauri.conf.json` has a `bundle.windows.wix` object with `language: [\"en-US\"]` plus productName/manufacturer values"
    - "A `.msi` file exists at `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi`"
    - "`file <msi>` identifies the artefact (output matches MSI / Microsoft Installer / CDFV2)"
    - "The `.msi` file size is between 15 and 40 MB"
    - "`PHASE-VERIFICATION.md` records SHA256, file path, file size, `file` output, and a criterion-by-criterion pass/fail table"
  artifacts:
    - path: "src-tauri/tauri.conf.json"
      provides: "MSI bundle config (targets entry + windows.wix block)"
      contains: "\"msi\""
    - path: "src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi"
      provides: "Cross-compiled Windows installer artefact"
    - path: ".planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/PHASE-VERIFICATION.md"
      provides: "Criterion-by-criterion verification record with SHA256"
      contains: "SHA256"
  key_links:
    - from: "src-tauri/tauri.conf.json"
      to: "Tauri WiX bundler"
      via: "bundle.targets includes \"msi\" + bundle.windows.wix block"
      pattern: "\"msi\""
    - from: "cargo tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc"
      to: "cargo-xwin"
      via: "Explicit --runner cargo-xwin flag (per PLAN-REVIEW B1)"
      pattern: "cargo xwin --version"
    - from: "PHASE-VERIFICATION.md"
      to: "actual .msi artefact"
      via: "shasum -a 256 + stat -f %z output captured verbatim"
      pattern: "SHA256"
---

<objective>
Cross-compile a working Windows `.msi` for the Invisible Tauri shell from this macOS worktree using `cargo-xwin`, edit `src-tauri/tauri.conf.json` so the MSI bundle target + WiX configuration are persisted, and record the artefact's SHA256 + size in a phase-level verification document.

Purpose: This is the first of three workstream phases that move the Tauri shell from "builds on macOS only" to "tag-triggered cross-platform release pipeline". Without Phase 1, no Windows binary can be produced at all. The output of this phase becomes the input to Phase 2 (signing) and Phase 3 (CI release workflow).

Output:
- Persistent `bundle.targets` + `bundle.windows.wix` config in `src-tauri/tauri.conf.json` (atomic commit).
- A built `.msi` at `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi` (build artefact, gitignored — recorded by hash only).
- `PHASE-VERIFICATION.md` with criterion-by-criterion proof (atomic commit).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/workstreams/tauri-windows/ROADMAP.md
@.planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/CONTEXT.md
@src-tauri/tauri.conf.json
@src-tauri/Cargo.toml

<interfaces>
<!-- Current state of src-tauri/tauri.conf.json bundle block (only the relevant slice). -->
<!-- Tasks 2 below adds "msi" to the targets array and inserts a new "windows" sibling object. -->

Current `bundle` block in src-tauri/tauri.conf.json:
```json
"bundle": {
  "active": true,
  "targets": ["app", "dmg"],
  "icon": ["icons/32x32.png", "icons/128x128.png", "icons/128x128@2x.png", "icons/icon.icns", "icons/icon.ico"],
  "category": "DeveloperTool",
  "shortDescription": "Personal multi-agent dev cockpit",
  "longDescription": "Native Tauri shell for the invisible cockpit. Loads the Vite-bundled React UI; bridges the invisible-dashboard event stream to the frontend."
}
```

Target shape after Task 2 (additive only — no existing key is altered):
```json
"bundle": {
  "active": true,
  "targets": ["app", "dmg", "msi"],
  "icon": [...],
  "category": "DeveloperTool",
  "shortDescription": "...",
  "longDescription": "...",
  "windows": {
    "wix": {
      "language": ["en-US"]
    }
  }
}
```

Tauri WiX schema reference (Tauri 2.11): `productName` and `manufacturer` are read from
top-level config (`productName: "Invisible"` already present) and `bundle.publisher` /
`bundle.windows.wix.*` respectively. `bundle.publisher` ("The Profit Platform") satisfies
manufacturer. `bundle.windows.wix.language` is the only WiX-specific key we MUST set
explicitly for the bundler to emit `Invisible_0.1.0_x64_en-US.msi`.

The phase identifier (`com.theprofitplatform.invisible`) is unchanged — Tauri auto-generates
an UpgradeCode UUID from it per Phase 1 constraints (Phase 2 will lock it).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 01-01: Bootstrap cross-compile toolchain</name>
  <files>(no source files modified — installs only)</files>
  <action>
Install the two pieces of cross-compile toolchain that are missing per CONTEXT.md (verified absent 2026-06-02). Run from the worktree root.

1. `source "$HOME/.cargo/env"` so `cargo` is on PATH inside this shell session.
2. `cargo install cargo-xwin` — installs the `xwin` subcommand. This compiles the binary, so allow ~5 minutes.
3. `rustup target add x86_64-pc-windows-msvc` — adds the Rust std library for the Windows MSVC target. Quick (a few seconds).

Do NOT run any `cargo tauri build` yet (that's Task 03). Do NOT touch any project files in this task — it's purely a host-toolchain operation. No commit (no tracked files change).

If `cargo install cargo-xwin` reports "already installed" or `rustup target add` reports the target is already installed, that's a pass — just record it.
  </action>
  <verify>
    <automated>cargo xwin --version &amp;&amp; rustup target list --installed | grep -qx x86_64-pc-windows-msvc</automated>
  </verify>
  <done>`cargo xwin --version` prints a version string AND `rustup target list --installed` contains `x86_64-pc-windows-msvc`. No git changes (verify with `git status --porcelain` — empty expected).</done>
</task>

<task type="auto">
  <name>Task 01-02: Add MSI target + WiX block to tauri.conf.json</name>
  <files>src-tauri/tauri.conf.json</files>
  <action>
Make a minimal additive edit to `src-tauri/tauri.conf.json` (satisfies INV-01-SC2 and INV-01-SC3). Two changes inside the existing `bundle` object only — do NOT touch any other top-level key (`productName`, `version`, `identifier`, `build`, `app`).

Edit 1 — append `"msi"` to `bundle.targets`:
- Before: `"targets": ["app", "dmg"]`
- After:  `"targets": ["app", "dmg", "msi"]`

Edit 2 — add a `publisher` field and a `windows` object as new siblings inside `bundle` (place them after `longDescription`). `publisher` satisfies WiX `manufacturer`; the `windows.wix` block satisfies the language requirement and locks the output filename to `Invisible_0.1.0_x64_en-US.msi`:

```json
"publisher": "The Profit Platform",
"windows": {
  "wix": {
    "language": ["en-US"]
  }
}
```

`productName` is already `"Invisible"` at the top level of the file — Tauri reads it from there for the WiX product name, so DO NOT duplicate it inside `bundle.windows.wix`.

DO NOT add `upgradeCode` — per CONTEXT.md "Constraints", Phase 1 lets Tauri auto-generate the UpgradeCode from the identifier; Phase 2 will lock it.

After saving, validate the JSON parses (`python3 -c "import json; json.load(open('src-tauri/tauri.conf.json'))"` exits 0).

Commit atomically. Conventional Commits format. Stage only `src-tauri/tauri.conf.json`:
- Message: `feat(tauri-windows): add MSI bundle target + WiX en-US config`
- Body: one-line rationale referencing INV-01-SC2 and INV-01-SC3.
  </action>
  <verify>
    <automated>python3 -c "import json,sys; c=json.load(open('src-tauri/tauri.conf.json')); assert 'msi' in c['bundle']['targets'], 'msi missing from bundle.targets'; assert c['bundle']['windows']['wix']['language'] == ['en-US'], 'wix.language wrong'; assert c['bundle']['publisher'] == 'The Profit Platform', 'publisher missing'; print('OK')"</automated>
  </verify>
  <done>JSON parses; `bundle.targets` contains `"msi"`; `bundle.windows.wix.language` is `["en-US"]`; `bundle.publisher` is `"The Profit Platform"`; commit landed on `ws/tauri-windows` (verify with `git log -1 --oneline` — message starts with `feat(tauri-windows):`).</done>
</task>

<task type="auto">
  <name>Task 01-03: First Windows cross-compile (cold build ~30 min)</name>
  <files>(produces build artefacts under src-tauri/target/ — gitignored)</files>
  <action>
Run the actual cross-compile. This is the long-running step (~30 min wall-clock cold because cargo-xwin downloads ~700 MB of MSVC headers + libs from Microsoft's CDN on first invocation, then compiles the full dependency tree for the new target). Subsequent builds reuse the cache.

1. `source "$HOME/.cargo/env"` (ensure PATH).
2. `cd src-tauri`.
3. Run: `cargo tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc 2>&amp;1 | tee /tmp/inv-01-build.log`
   - The `--runner cargo-xwin` flag is REQUIRED. Tauri 2.11 does NOT auto-detect cargo-xwin on a non-Windows host (earlier plan claim was incorrect — see PLAN-REVIEW.md B1).
   - **Wall-clock timeout: 1800 seconds (30 minutes).** Bash tool's default 2-minute timeout will kill the cold build. Invoke with `timeout: 1800000` (ms) or equivalent.
   - The `beforeBuildCommand` runs `pnpm build` in `frontend-vite/` first. Ensure `pnpm` is on PATH (it should be — corepack is configured per CONTEXT.md).
4. On success, confirm the artefact exists at the expected path:
   `ls -la src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi`
5. Capture three metadata facts for Task 04 (don't write them anywhere durable yet — Task 04 owns PHASE-VERIFICATION.md):
   - SHA256: `shasum -a 256 src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi`
   - File size in bytes: `stat -f %z src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi`
   - File type: `file src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi`

Known issues to expect and how to react (per CONTEXT.md "Failure modes"):
- **WiX template missing** — if cargo tauri build complains about WiX tooling, `brew install wixtools` then retry the build. Do NOT abandon the task.
- **Linker errors mentioning `\\?\` path prefixes** — known cargo-xwin path-canonicalisation quirk. Retry the build (`cargo tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc` again). Document in PHASE-VERIFICATION if it took >1 attempt.
- **Symbol/version mismatch from a half-installed toolchain** — `cargo clean --target x86_64-pc-windows-msvc` then retry.

If the build fails for any reason that is NOT one of the above three knowns: STOP, do not retry blindly. Capture the last 50 lines of `/tmp/inv-01-build.log` for the verification doc, then surface the failure to the planner via the checker — Phase 1 needs a successful build to advance.

No commit — only build artefacts changed, and those are gitignored.
  </action>
  <verify>
    <automated>MSI=src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi; test -f "$MSI" &amp;&amp; file "$MSI" | grep -qi "msi installer\|composite document\|microsoft installer\|cdfv2" &amp;&amp; SIZE=$(stat -f %z "$MSI") &amp;&amp; [ "$SIZE" -ge 15728640 ] &amp;&amp; [ "$SIZE" -le 41943040 ] &amp;&amp; echo "OK size=$SIZE"</automated>
  </verify>
  <done>`.msi` file exists at the exact expected path; `file` recognises it as an MSI/CDFV2/Microsoft Installer artefact; file size is between 15 MB (15728640 bytes) and 40 MB (41943040 bytes) inclusive. No git changes.</done>
</task>

<task type="auto">
  <name>Task 01-04: Write PHASE-VERIFICATION.md and commit</name>
  <files>.planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/PHASE-VERIFICATION.md</files>
  <action>
Create the phase verification document. It must prove every one of the six ROADMAP success criteria with concrete evidence (commands run + their actual output).

Write `PHASE-VERIFICATION.md` at the path in `<files>` with this structure (replace ALL `{...}` placeholders with the real values gathered in Task 03 — do NOT leave any placeholder):

```markdown
# Phase 1 Verification — Windows .msi Cross-Compile

**Phase:** INV-01-windows-msi-cross-compile
**Branch:** ws/tauri-windows
**Host:** macOS (Darwin 25.5.0, arm64)
**Date:** {YYYY-MM-DD of completion}
**Plan:** 01-01-PLAN.md
**Outcome:** PASS

## Artefact

| Field | Value |
|-------|-------|
| Path  | `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi` |
| SHA256 | `{sha256 from Task 03}` |
| Size (bytes) | `{stat -f %z output}` |
| Size (MB, rounded) | `{size_bytes / 1048576, 2 decimals}` |
| `file` output | `{file <msi> output}` |
| Code-signed? | **No** — code signing is deferred to Phase 2 (see CONTEXT.md "Constraints"). |
| UpgradeCode | Auto-generated by Tauri from identifier `com.theprofitplatform.invisible` (locked in Phase 2). |

## Success criteria (verbatim from ROADMAP)

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | `cargo xwin --version` resolves; `cargo install cargo-xwin` adds it. | PASS | Task 01-01. `cargo xwin --version` -> `{actual version string}`. |
| 2 | `src-tauri/tauri.conf.json` `bundle.targets` includes `"msi"`. | PASS | Task 01-02 commit `{short-sha}`. `jq '.bundle.targets' src-tauri/tauri.conf.json` -> `["app","dmg","msi"]`. |
| 3 | `src-tauri/tauri.conf.json` has a `bundle.windows.wix` block with productName, manufacturer, `language: ["en-US"]`. | PASS | Task 01-02. productName inherited from top-level `"Invisible"`; manufacturer = `bundle.publisher` = `"The Profit Platform"`; `bundle.windows.wix.language` = `["en-US"]`. |
| 4 | `cargo tauri build --target x86_64-pc-windows-msvc` succeeds; output at `src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi`. | PASS | Task 01-03. `ls -la` output recorded in "Build log excerpt" below. |
| 5 | SHA256 of the `.msi` captured in PHASE-VERIFICATION.md. | PASS | Recorded above in "Artefact" table. |
| 6 | File size between 15 and 40 MB. | PASS | `{size_mb} MB` falls in [15, 40] MB. |

## Toolchain snapshot

```
{output of: rustc --version}
{output of: cargo --version}
{output of: cargo tauri --version}
{output of: cargo xwin --version}
{output of: rustup target list --installed | grep windows}
```

## Build log excerpt

```
{last 20-30 lines of /tmp/inv-01-build.log — must include the "Built ... Invisible_0.1.0_x64_en-US.msi" Tauri success line}
```

## Anomalies / notes

{One of:
 - "Build completed on first attempt; no retries.", OR
 - "Build required N attempts due to <linker prefix issue | wixtools install | other>; final attempt succeeded.", OR
 - whatever actually happened.}

The artefact is **unsigned** by design — Phase 2 of this workstream adds Authenticode signing for Windows. A Windows VM smoke-test is also a Phase 2/3 concern; Phase 1 only proves the build pipeline produces a structurally valid `.msi`.

## Hand-off to Phase 2

- The MSI bundle config in `tauri.conf.json` is in place.
- UpgradeCode is currently auto-generated. Phase 2 should run `uuidgen` once and add it as `bundle.windows.wix.upgradeCode` so upgrades from Phase-1 to Phase-2 builds remain coherent for any tester who installs the unsigned `0.1.0` artefact.
- Phase 2 should add a Windows signing identity to `bundle.windows` (`certificateThumbprint` or `signCommand`) and add macOS signing to `bundle.macOS.signingIdentity`.
```

Validation before commit:
- Every `{...}` placeholder must be replaced with a real value.
- Every row in the criteria table must say `PASS` and reference real evidence (not "TBD").

Commit atomically. Stage only the PHASE-VERIFICATION.md file:
- Message: `docs(tauri-windows): phase 1 verification — Windows .msi cross-compile`
- Body: one line with the SHA256 of the artefact (for grep-ability in the workstream history).
  </action>
  <verify>
    <automated>F=.planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/PHASE-VERIFICATION.md; test -f "$F" &amp;&amp; ! grep -qE '\{[a-z_]+\}|TBD|TODO' "$F" &amp;&amp; grep -q '^| 6 |' "$F" &amp;&amp; grep -qi 'SHA256' "$F" &amp;&amp; grep -Eq '[a-f0-9]{64}' "$F" &amp;&amp; git log -1 --oneline -- "$F" | grep -q 'docs(tauri-windows)' &amp;&amp; echo OK</automated>
  </verify>
  <done>`PHASE-VERIFICATION.md` exists with no placeholder strings remaining (`{...}`/`TBD`/`TODO`), contains a 64-hex-char SHA256, all 6 ROADMAP criteria marked PASS, and the file is committed on `ws/tauri-windows` with a `docs(tauri-windows):` Conventional Commit message.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| local macOS host -> Microsoft CDN | `cargo xwin` downloads MSVC SDK headers/libs (~700 MB) over HTTPS from `aka.ms` / `download.visualstudio.microsoft.com`. Untrusted external bytes are fed into the build toolchain. |
| local macOS host -> crates.io | `cargo install cargo-xwin` pulls a crate; transitive build-time supply chain. |
| local macOS host -> npm registry | `pnpm build` in `frontend-vite/` re-runs at `beforeBuildCommand`; npm packages execute install scripts. |
| local filesystem -> repo working tree | Two files touched (`tauri.conf.json`, `PHASE-VERIFICATION.md`). Build artefacts under `target/` are gitignored. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INV-01-01 | Tampering | `cargo install cargo-xwin` (Task 01-01) | mitigate | crates.io install over TLS; `cargo install` verifies registry signature on download. `cargo-xwin` is a published, widely-used crate (already cited in the workstream ROADMAP as the chosen approach). No locally-built fork. |
| T-INV-01-02 | Tampering | MSVC SDK download via `xwin` (Task 01-03) | mitigate | `xwin` pins SDK manifest URLs to Microsoft's `aka.ms` / VS CDN over HTTPS and verifies each blob's manifest-listed SHA256 before extracting. Threat residual: trust in Microsoft's CDN PKI, which is the same trust assumption as `rustup` itself. |
| T-INV-01-03 | Tampering | `pnpm build` for `frontend-vite/` (Task 01-03) | accept | This phase does not modify `frontend-vite/` or its `package.json` / `pnpm-lock.yaml`. The lockfile is governed by sibling workstreams; their CI runs are the supply-chain authority for the frontend tree. |
| T-INV-01-04 | Information Disclosure | the unsigned `.msi` artefact | accept | The artefact is unsigned by design (Phase 2 adds signing). Phase 1 only stores the SHA256 in `PHASE-VERIFICATION.md`; the binary itself is gitignored and never published in this phase. |
| T-INV-01-05 | Denial of Service | first-run xwin SDK download (~700 MB, ~30 min) | accept | Documented in CONTEXT.md and Task 01-03's `<action>`. Single host, single user, no scheduled deadline. Cached for subsequent builds. |
| T-INV-01-06 | Repudiation | git commits for config + verification doc | mitigate | Two atomic Conventional Commits with explicit scope (`feat(tauri-windows):` and `docs(tauri-windows):`) so the change is attributable in workstream history. |
| T-INV-01-07 | Spoofing | `bundle.publisher` claim ("The Profit Platform") | accept | Phase 1 produces an UNSIGNED artefact, so `publisher` is metadata only — no Authenticode chain backs the claim. Phase 2 binds publisher to a real code-signing cert. Until then, any party can mint an MSI with this publisher string; that is acceptable for a build-pipeline-validation phase. |
| T-INV-01-08 | Elevation of Privilege | WiX install scaffolding | accept | We use Tauri's default WiX template (no custom WXS fragments, no custom CustomActions). Phase 1 cannot elevate beyond what `cargo tauri build` already grants the developer running it. |
| T-INV-01-SC | Tampering | npm/pip/cargo installs | mitigate | One cargo install in scope (`cargo-xwin`). It is a well-known crate, NOT [ASSUMED]/[SUS]/[SLOP] (no Package Legitimacy Audit gating this install per RESEARCH.md — none exists for this phase, and the workstream ROADMAP names cargo-xwin explicitly as the approach). No npm/pip installs introduced by Phase 1; the existing `pnpm install` for the frontend is owned by sibling workstreams. |

Threats T-INV-01-04, T-INV-01-05, T-INV-01-07, T-INV-01-08 are accepted with explicit rationale because they are intrinsic to the "unsigned cross-compile, no Windows VM" scope of Phase 1. Phase 2 closes T-INV-01-04 and T-INV-01-07.
</threat_model>

<verification>
After all four tasks succeed, the phase passes if and only if:

1. `git log --oneline ws/tauri-shell..ws/tauri-windows -- src-tauri/tauri.conf.json .planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/` shows exactly two new commits: one `feat(tauri-windows): ...MSI bundle...` and one `docs(tauri-windows): phase 1 verification...`.
2. `jq '.bundle | {targets, publisher, windows}' src-tauri/tauri.conf.json` shows `msi` in targets, `"The Profit Platform"` as publisher, and `language: ["en-US"]` under `windows.wix`.
3. `test -f src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/Invisible_0.1.0_x64_en-US.msi` is true.
4. The SHA256 hex string in PHASE-VERIFICATION.md matches `shasum -a 256` of the artefact (re-run if necessary).
5. PHASE-VERIFICATION.md contains no `{...}`, `TBD`, or `TODO` strings.

If any check fails, the phase does not advance to Phase 2.
</verification>

<success_criteria>
This plan is complete when all 6 ROADMAP success criteria are demonstrably met and recorded in PHASE-VERIFICATION.md, both git commits are on `ws/tauri-windows`, and `cargo tauri build --target x86_64-pc-windows-msvc` is reproducible from a fresh shell on this host (toolchain installs persist across sessions).
</success_criteria>

<output>
On completion, create `.planning/workstreams/tauri-windows/phases/INV-01-windows-msi-cross-compile/01-01-SUMMARY.md` summarising:
- The two commits landed (short SHAs + messages).
- The artefact SHA256 + size.
- Any anomalies during the cold build (retry count, wixtools install, etc.).
- A one-line hand-off note for Phase 2 about UpgradeCode and signing.
</output>
