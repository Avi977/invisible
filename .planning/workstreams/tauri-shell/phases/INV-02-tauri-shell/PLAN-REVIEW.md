# Plan Review — INV-02 Tauri shell

**Verdict:** REVISE
**Reviewer mode:** goal-backward, adversarial
**Plan reviewed:** `PLAN.md` (1,258 lines, 6 tasks)
**Sources cross-checked:** CONTEXT.md, ROADMAP.md, `bin/invisible-dashboard`, `bin/invisible-app`, `bin/invisible-server`, `frontend-vite/{package.json,vite.config.js}`

---

## Goal coverage table

| ROADMAP success criterion | Covering task(s) | `<done>` clause guarantees it? | Notes |
|---|---|---|---|
| #1 `cd src-tauri && cargo tauri dev` launches, loads Vite dev server, HMR works | Task 1 (build/launch smoke) + Task 5 step 1-2 (manual HMR confirm) | YES (modulo concern #8 below — `beforeDevCommand` may fail without pnpm workspace) | `devUrl: http://localhost:5173`, `frontendDist: ../frontend-vite/dist` both confirmed in plan lines 391-392; Vite confirms `port: 5173, strictPort: true` in `vite.config.js:8`. |
| #2 Five Tauri commands: `list_projects`, `run_orchestrator(project,task?)`, `kill_run(project)`, `tail_log(project,lines)`, `status` | Task 2 (all 5 implemented + registered) + Task 5 steps 3-5 (manual invoke from DevTools) | YES, with caveat: behavior includes the canonical defensive behaviors (`tail_log("nonexistent", 10) → ""` not Err; `list_projects` empty when worktrees dir absent → `Ok([])`). | Concerns #4 (borrow-checker landmine on `project` capture), #5 (path traversal not in action steps), #6 (capability validator `\S+` rejects `--task` strings with spaces) all apply. |
| #3 System tray with Open / Hide / Quit; close-to-hide | Task 3 (tray + `WindowEvent::CloseRequested` handler) + Task 5 step 6 (manual click-through) | YES — `MenuItem::with_id`, `TrayIconBuilder::with_id`, `WindowEvent::CloseRequested { api, .. }`, `api.prevent_close()` all match Tauri 2.x canonical API; mirrors `bin/invisible-app:264-271`. | Clean. |
| #4 SSE bridge `invisible-dashboard` → Tauri event bus | Task 4 (SSE-first with 404 → poll fallback; exponential backoff) + Task 5 steps 7-8 (daemon up + daemon down) | YES — confirmed `bin/invisible-dashboard` has NO `/api/stream` (only `/api/projects`, `/api/p/<>`, `/api/reviews` — verified at dashboard lines 296-309); confirmed `bin/invisible-server` DOES expose `/api/stream` (line 364). Polling fallback is justified. Backoff steps 1s→2s→5s→10s match CONTEXT.md. | Concern #7 (no SSE re-probe after switching to poll mode) is minor. |

All four ROADMAP criteria have at least one task whose `<done>` clause guarantees them. The plan **structurally covers the goal**; the verdict is REVISE because of concrete correctness issues in the Tauri 2.x API surface and security mitigations, not goal-coverage gaps.

---

## Concerns (numbered, severity-tagged, with line citations)

### 1. [MAJOR] Capability allow-list schema is speculative — plan itself hedges

PLAN.md lines 313-323 (and re-stated at 305-322 in `<interfaces>`) writes the `shell:allow-execute` entry as an inline JSON object with `{ identifier, allow: [{ name, cmd: { program, args: [{validator}] }, sidecar }] }`. Two problems:

1. **The plan concedes this may be wrong:** line 326 says *"If Tauri 2 emits a schema warning about the `cmd` shape on the first `cargo tauri dev`, adapt to whatever the current 2.11 schema expects ... consult [`gen/schemas/desktop-schema.json`] on warning."* A plan that documents "adapt at runtime" for a capability file isn't a plan — it's a hope. Capability files gate **what the webview can call**; a misshapen file either silently fails-open or blocks the 5 commands entirely.
2. **The current Tauri 2 `tauri-plugin-shell` scope schema** uses `permissions[].scope` (or a scope-set permission) with entries like `{"name": "invisible-status", "cmd": "invisible-status", "args": true | ["arg1", {"validator": "..."}]}`. The wrapping `{identifier, allow: [...]}` pattern shown is closer to a Tauri 2 *capability* object schema, but the inner `{name, cmd: {program, args}, sidecar}` shape is not canonical for `tauri-plugin-shell` 2.x — `cmd` is typically a string identifier, not a nested object.

**Severity rationale:** This is the gate between the React UI and the 4 backing CLIs. If the schema is wrong, criterion #2 (`run_orchestrator` etc invoke successfully) fails at runtime, not at `cargo build`.

**Suggested edit (concrete):** Before the executor writes `capabilities/default.json`, scaffold a throwaway `cargo tauri init` in `/tmp/`, copy its generated `capabilities/default.json` and `src-tauri/gen/schemas/desktop-schema.json` shapes, then translate the 4 `invisible-*` entries into that canonical shape. Alternative: replace the inline scope with a curated permission set like `shell:allow-execute` (default scope) + a separate, version-pinned scope JSON file referenced from `tauri.conf.json` plugin config — and verify against `https://schema.tauri.app/config/2`.

### 2. [MAJOR] Capability `args` validator `"\\S+"` will reject `run_orchestrator(project, task=…)` with multi-word tasks

PLAN.md lines 316-319: every `invisible-*` entry uses `args: [{ "validator": "\\S+" }]`. `\S+` = one-or-more non-whitespace. But:

- `run_orchestrator("foo", Some("fix the off-by-one in lib.rs"))` produces args `["foo", "--task", "fix the off-by-one in lib.rs"]`. The third arg contains spaces and **fails the `\S+` validator**, so `tauri-plugin-shell` rejects the spawn. The user types a normal sentence into the chat box; nothing happens.
- `invisible-status --json` passes 1 arg; that's fine.
- `tail_log` doesn't shell out (it reads the filesystem) — no validator issue, but the allow-list lists `invisible-log` and the plan never actually invokes `invisible-log` (Task 2 Step 6 reads the file directly). So `invisible-log` is in the allow-list **defensively** — fine, but worth noting it's unused.

**Severity rationale:** Criterion #2 is "the 5 commands invoke successfully". `run_orchestrator` with a freeform `task?` parameter is the highest-value command in the entire shell (it's how the user kicks off a review). If the validator blocks any task containing spaces, criterion #2 is functionally broken for the headline use case.

**Suggested edit:** Replace `args: [{ "validator": "\\S+" }]` with shape-specific entries per command. For `invisible-review` it should be either `args: true` (permit any) or a structured 3-arg shape that explicitly allows whitespace in the `--task` value, e.g. `args: [{validator: "[^\\x00]+"}, "--task", {validator: "[^\\x00]+"}]` — or per Tauri 2 plugin-shell idiom, model the command with optional args and accept arbitrary content in the trailing positional. The `\S+` form is fine for `invisible-status --json`, `invisible-ps`, and `invisible-review <project> --stop`, but NOT for `--task "…"` payloads.

### 3. [MAJOR] `tail_log` path-traversal mitigation is in the threat model but NOT in the action steps

PLAN.md line 1151 (threat T-INV02-02): *"the executor in Task 2 MUST sanitise `project` by extracting only the last path component (`PathBuf::file_name()`) and forbidding empty/dot strings."*

But Task 2 Step 6 (PLAN.md lines 589-593) reads in full:
> *"`let lines = lines.clamp(1, 10_000) as usize;` / `let path = invisible_home().join("logs").join(format!("{}.log", project));` / If `!path.exists()` → return `Ok(String::new())`."*

**No sanitisation.** A literal read: `tail_log("../../etc/passwd", 10)` → joins `~/.invisible/logs/../../etc/passwd.log` → on macOS that path doesn't end in `.log` because of the embedded literal `/etc/passwd`, but `~/.invisible/logs/../foo.log` is a real escape. The format string `format!("{}.log", project)` appends `.log` to the user input; so `project = "../foo"` yields `~/.invisible/logs/../foo.log` = `~/.invisible/foo.log` — escape to one level up; `project = "../../tmp/anything"` escapes further. The threat model knows this, the action steps don't.

**Severity rationale:** Filesystem read primitive exposed to webview JS. Even with first-party origins (T-INV02-04 accept), any future bug that lets attacker-controlled JS reach the webview (XSS in any of the 8 pages, or a malicious npm dep in `frontend-vite/`) yields unconstrained reads.

**Suggested edit:** Insert into Task 2 Step 6 action between "let lines = …" and "let path = …":
```rust
let safe_project = std::path::Path::new(&project)
    .file_name()
    .and_then(|s| s.to_str())
    .ok_or_else(|| "invalid project name".to_string())?;
if safe_project.is_empty() || safe_project.starts_with('.') {
    return Err("invalid project name".to_string());
}
let path = invisible_home().join("logs").join(format!("{}.log", safe_project));
```
And add to `<verify>` (line 641): `grep -q 'file_name()' src/commands.rs` and a runtime check `tail_log("../etc", 10)` returns `Err`.

### 4. [MAJOR] `run_orchestrator` async-move closure has a borrow-checker landmine

PLAN.md Task 2 Step 4 (lines 571-583):

```rust
let (mut rx, child) = app.shell().command("invisible-review").args(args).spawn()...
... RunHandle { pid, project }   // ← project moved here
tauri::async_runtime::spawn(async move {
    while let Some(event) = rx.recv().await {
        match event { CommandEvent::Stdout(line) => { let _ = app_handle.emit("run:stdout", serde_json::json!({"project": project, ...}); }  // ← `project` used here AFTER the move
```

The sketch references `project` and `app_handle` inside the `async move {}` block, but:
- `project` was consumed when building `RunHandle { pid, project }` (or earlier when building `args`).
- `app_handle` is not bound anywhere in the visible sketch — there's no `let app_handle = app.app_handle().clone();` line.

A competent executor will fix these (`let project_ev = project.clone(); let app_handle = app.app_handle().clone();` before the spawn), but the plan reads as if the snippet is paste-ready. With the plan's `cargo build` smoke at line 629-635, this WILL fail compile on first attempt, and the executor may guess wrong about the fix (e.g. cloning into the wrong scope).

**Severity rationale:** Compile error is recoverable but eats execution context. More importantly the plan's <verify> at line 641 runs `cargo build` and expects success — the test will fail on a literal interpretation.

**Suggested edit:** Rewrite Step 4 to show explicit clones:
```rust
let project_for_handle = project.clone();
let app_handle = app.app_handle().clone();
let args: Vec<String> = match task { Some(t) => vec![project.clone(), "--task".into(), t], None => vec![project.clone()] };
let (mut rx, child) = app.shell().command("invisible-review").args(&args).spawn().map_err(|e| e.to_string())?;
let pid = child.pid();
tauri::async_runtime::spawn(async move {
    let project = project_for_handle;  // owned by the task
    while let Some(event) = rx.recv().await {
        match event {
            CommandEvent::Stdout(line) => { let _ = app_handle.emit("run:stdout", serde_json::json!({"project": project, "line": String::from_utf8_lossy(&line)})); }
            // ...
        }
    }
});
Ok(RunHandle { pid, project })
```

### 5. [MAJOR] `beforeDevCommand: "pnpm --filter ./frontend-vite dev"` requires a pnpm workspace that doesn't exist

PLAN.md line 393: `"beforeDevCommand": "pnpm --filter ./frontend-vite dev"`. Plan line 430 admits this might break: *"If pnpm filters fail on macOS (they should not), fall back to `cd ../frontend-vite && pnpm dev`."*

But `pnpm --filter` requires a workspace defined by `pnpm-workspace.yaml` at the repo root (or invoking from a parent that contains one). There's no evidence in the inputs that this exists — `frontend-vite/package.json` is a standalone package; the plan creates no `pnpm-workspace.yaml`. Without it, `pnpm --filter ./frontend-vite` fails with `ERR_PNPM_NO_MATCHING_PROJECT` or treats `./frontend-vite` as a literal path that pnpm doesn't recognise unless invoked from the parent.

Even if it works on macOS pnpm 9+, `beforeDevCommand` runs from `src-tauri/` (Tauri's CWD), and `--filter ./frontend-vite` resolved relative to `src-tauri/` is `src-tauri/frontend-vite` — does not exist.

**Severity rationale:** Criterion #1 depends on this command launching the Vite dev server. If it fails, `cargo tauri dev` either errors or proceeds without HMR.

**Suggested edit:** Replace with `cd ../frontend-vite && pnpm dev` directly (the plan's own fallback). Or: create a minimal `pnpm-workspace.yaml` at repo root listing `frontend-vite` (additive, no other changes). Recommend the fallback form (less invasive — no new top-level file).

### 6. [MINOR] SSE bridge never re-probes `/api/stream` after switching to poll mode

PLAN.md `sse.rs` lines 866-873: once `BridgeError::SseNotSupported` fires, `prefer_polling = true` is permanent for the process lifetime. If the user starts `cargo tauri dev` against the local `invisible-dashboard` (no SSE) then later `export INVISIBLE_SERVER_URL=https://…/` and restarts the VPS-backed daemon — without restarting Tauri — the bridge will keep polling instead of upgrading to SSE.

**Severity rationale:** Not in the explicit criteria; acceptable for Phase 2. Would surprise a developer iterating on the daemon though.

**Suggested edit:** Every Nth polling cycle (e.g. every 12 ticks = 60s), try the SSE endpoint once; on 200 + `text/event-stream`, set `prefer_polling = false` and break. Or simply note this limitation in SUMMARY and defer to Phase 3.

### 7. [MINOR] `status` fallback chain is circular-ish

PLAN.md Task 2 Step 7 (lines 595-598): `status()` tries `invisible-status --json` → on fail, tries `invisible-ps` → "*run `list_projects()` again as a deep fallback*". But `list_projects()` ALSO tries `invisible-status --json` first. So on the cold path where `invisible-status` is broken, we re-invoke it from inside `status`'s fallback. Wasted work, not a correctness bug.

**Suggested edit:** When `status` falls back, call the worktree-scan logic directly (the same code path `list_projects` uses as ITS fallback) rather than calling `list_projects` whole.

### 8. [MINOR] `Cargo.lock` gitignored under `src-tauri/.gitignore`

PLAN.md line 365-367 explicitly gitignores `Cargo.lock` in `src-tauri/`. Rust convention is to commit `Cargo.lock` for binaries (and `invisible-tauri` is a binary). The threat model at line 1157 notes this: *"`Cargo.lock` is gitignored ... so the lockfile is per-checkout — Phase 3 may revisit this for reproducibility."* But Phase 3 is when the binary gets distributed; reproducible builds matter MORE then, not less, so the deferral logic is suspect.

**Severity rationale:** Doesn't block Phase 2 goals, but accumulates technical debt: Phase 3's signed/notarized macOS build needs a locked dep graph. Easier to commit it now.

**Suggested edit:** Remove `Cargo.lock` from `src-tauri/.gitignore` and let `git add src-tauri/Cargo.lock` happen in Task 6. Update threat-model note T-INV02-SC accordingly.

### 9. [MINOR] `withGlobalTauri: true` for "DevTools console verification" is fine for Phase 2 but conflicts with the threat model's accept for T-INV02-04

PLAN.md line 397 and threat T-INV02-04 (line 1153): `withGlobalTauri: true` is on because CONTEXT.md verification uses `window.__TAURI__.core.invoke(...)`. The threat model accepts this for Phase 2. Fine. Just make sure the SUMMARY explicitly carries forward the "Phase 3 must reconsider" obligation so it isn't lost.

### 10. [MINOR] No explicit handling for "daemon comes UP later" in poll_loop

PLAN.md `poll_loop` (lines 927-957): if the very first poll fails (daemon down), returns `BridgeError::Transient` → backoff in `run_bridge` → retry. Good. If the daemon comes up between polls, the next poll succeeds. Good. Coverage of the 4 prompt-required cases:
- (a) daemon down at startup → backoff retries SSE first, then switches to poll on first 200-but-404 response. If daemon down means *connect refused*, that's `Transient` from `sse_loop`; backoff retries. Eventually daemon comes up → SSE attempt → 404 → switches to poll. ✓
- (b) daemon comes up later → covered as above. ✓
- (c) daemon goes down mid-session → `poll_loop` Ok-arm sees non-success status (logs but doesn't bail) OR connect error (returns `Transient`, backoff). ✓
- (d) JSON parse errors → `serde_json::from_str(&body).unwrap_or(Value::String(body))` — non-panicking. ✓

All 4 cases handled. Concern only that the warning-log path in `poll_loop` line 949 (`warn!("poll {} → {}", url, resp.status())`) doesn't bail — it sleeps and re-polls. So a daemon returning persistent 500s will spin at 5s/poll forever. Cosmetic; acceptable.

### 11. [PASS] Independence from siblings — verified clean

`files_modified` (PLAN.md lines 9-33) contains zero entries under `frontend/`, `bin/invisible-*`, `lib/`, or `frontend-vite/src/*.jsx`. The verify automation at lines 641, 996, 1126, 1219, 1225 explicitly assert this via `git status --porcelain` and pattern checks. The plan correctly leaves the pywebview, the legacy `frontend/`, the CLI scripts, and the existing JSX files untouched.

### 12. [PASS] Cross-platform paths — verified clean

`commands.rs` uses `invisible_home()` (PLAN.md lines 555-562) which resolves `$INVISIBLE_HOME` first, then `dirs::home_dir().join(".invisible")`. Verify at line 641: `! grep -RnE '"/Users/ace/\.invisible|/Users/[a-z]+/\.invisible' src/`. Good.

### 13. [PASS] Tauri 2.x API correctness on the patterns the plan does specify

- `#[tauri::command] async fn ... -> Result<T, String>`: ✓ (line 158, 542-548).
- `tauri::generate_handler![...]` invocation in `Builder::default().invoke_handler(...)`: ✓ (lines 163-169, 615-622).
- `TrayIconBuilder::with_id("main")`: ✓ (line 180, 673).
- `MenuItem::with_id(app, "open", "Open", true, None::<&str>)?`: ✓ (Tauri 2 menu API — the `None::<&str>` is the accelerator arg).
- `WindowEvent::CloseRequested { api, .. } => { api.prevent_close(); window.hide(); }`: ✓ (lines 705-710); mirrors `bin/invisible-app:264-271` semantically.
- `tauri_plugin_shell::init()` registered: ✓ (line 162, 614).
- `app.emit("dashboard:event", payload)` via `tauri::Emitter` trait import: ✓ (lines 202-203, 658).
- `capabilities/default.json` lives under `src-tauri/capabilities/`: ✓ (Tauri 2 model).

The patterns the plan calls out are Tauri-2-correct. The problems are in the PLUGIN scope schema (concerns #1 + #2), not in the core Tauri API.

### 14. [PASS] HMR claim is structurally sound

`devUrl: http://localhost:5173` for `dev`, `frontendDist: ../frontend-vite/dist` for `build`. Vite is configured with `base: './'` (frontend-vite/vite.config.js:6) and `port: 5173, strictPort: true` (line 8) — exactly what Tauri 2 needs. HMR will work iff `beforeDevCommand` actually launches Vite (see concern #5). Conditional pass.

---

## Suggested edits — exact text changes

These are the minimal edits that flip the verdict from REVISE to PASS:

**Edit 1 (concern #5, blocker for criterion #1):**
PLAN.md line 393: replace
```json
"beforeDevCommand": "pnpm --filter ./frontend-vite dev",
"beforeBuildCommand": "pnpm --filter ./frontend-vite build"
```
with
```json
"beforeDevCommand": "cd ../frontend-vite && pnpm dev",
"beforeBuildCommand": "cd ../frontend-vite && pnpm build"
```

**Edit 2 (concern #2, blocker for `run_orchestrator(task=...)`):**
PLAN.md lines 316-320: the `invisible-review` entry's `args` field cannot use `[{ "validator": "\\S+" }]`. Replace just the `invisible-review` row with a permissive-but-positional shape, or model it as two separate scoped entries — one for `[project, "--task", <freeform>]` and one for `[project, "--stop"]`. Defer to the canonical Tauri 2 plugin-shell schema (resolve via concern #1's spike).

**Edit 3 (concern #3, security):**
PLAN.md Task 2 Step 6 (lines 589-593) — insert the `PathBuf::file_name()` sanitisation block shown in concern #3 above. Add `grep -q 'file_name()' src/commands.rs` to the Task 2 `<verify>` at line 641.

**Edit 4 (concern #4, compile correctness):**
PLAN.md Task 2 Step 4 (lines 571-583) — rewrite the sketch with explicit `project_for_handle` and `app_handle` clones as shown in concern #4 above.

**Edit 5 (concern #1, plugin-shell scope):**
Before Task 1's "Step 7 — Create `src-tauri/capabilities/default.json`", add a Step 7a: spike a one-time `cargo tauri init` in a `/tmp/` scratch dir, copy its generated `capabilities/default.json` shape (plus the generated schema), then translate to Invisible's 4-binary scope using THAT schema. Update PLAN.md `<interfaces>` "Capability allow-list" with the corrected JSON. Remove the runtime-hedge language at line 326.

**Edit 6 (concern #8, lockfile):**
PLAN.md `src-tauri/.gitignore` Step 2 line 365: remove `Cargo.lock` from the gitignore list. Update T-INV02-SC (line 1157) to note the lockfile is now committed.

---

## Greenlight

**NOT cleared for execution.** Three blockers (concerns #1, #2, #5) will cause runtime failure of criteria #1 and #2 as specified. One MAJOR (concern #3) is a security regression even though the threat model documents the mitigation. One MAJOR (concern #4) will fail the Task 2 `cargo build` smoke and waste executor context guessing at the fix.

Recommended revision loop: apply the 6 edits above, then re-submit for verification. Expected re-verification time: <5 minutes; the structural goal-coverage is sound.

---

## 3-line summary

1. **Verdict:** REVISE — goal coverage is sound (all 4 ROADMAP criteria have covering tasks with concrete `<done>` clauses) but 3 blockers will cause runtime failure as written.
2. **Top concern:** capability allow-list `args: [{"validator": "\\S+"}]` for `invisible-review` rejects `run_orchestrator` calls with multi-word `--task` strings — silently blocks the highest-value command of the entire shell.
3. **Greenlight:** NO. Apply edits #1-#5 above (concern #1 spike + concern #2 scope rewrite + concern #3 path sanitisation + concern #4 closure clones + concern #5 `beforeDevCommand` fix), then re-verify.
