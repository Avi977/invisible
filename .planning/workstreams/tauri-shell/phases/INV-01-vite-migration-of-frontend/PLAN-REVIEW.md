# Plan review — INV-01 (Vite migration of frontend)

**Verdict:** REVISE — plan is structurally sound and covers all 4 ROADMAP success criteria, but two grep gates use macOS-incompatible regex (lookahead) that will throw spurious failures during verification on the target machine.

## Goal coverage table

| # | ROADMAP success criterion | Delivered by |
|---|---------------------------|--------------|
| 1 | `frontend-vite/` is a Vite + React 18 (TS-optional) project | Task 1 (package.json with `react: 18.3.1`, `vite: ^5.4.0`, `@vitejs/plugin-react-swc`; `vite.config.js` with `base: './'`) |
| 2 | Every file in `frontend/` has a Vite-compatible equivalent under `frontend-vite/src/` | Task 1 (`styles.css`, `index.html`, `main.jsx`) + Task 2 (5 shared modules: `App`, `Icons`, `Data`, `AiChat`, `TweaksPanel`) + Task 3 (8 pages) |
| 3 | `pnpm dev` on 5173 with HMR; all 8 pages identical to 8090 | Task 3 (dev-server smoke + import-resolution gate) + Task 4 (human visual-parity checkpoint, enumerates all 8 pages explicitly + 5 Tweaks-panel control axes + HMR confirmation step) |
| 4 | `pnpm build` produces static `dist/` Tauri can bundle | Task 5 (`pnpm build` + `dist/index.html` + hashed JS/CSS + explicit check for relative `./assets/` paths + static-serve render check on port 5174) |

All four criteria are addressed by a named task whose `<done>` clause would have to be true for execution to pass.

## Concerns

### 1. MAJOR — macOS `grep -E` does NOT support Perl lookahead (`(?!...)`)
The Task 2 `<action>` includes this regex (PLAN.md line 359):

> `grep -RnE "useStateApp|useEffectApp|useStateAI|useRefAI|useEffectAI|useStateF|useStateFC|useEffectFC|useRefFC|useStateG|useRefG|useEffectG|useStateT(?!ype)|useRefT|useEffectT|useStateTL|...`

The token `useStateT(?!ype)` is a negative-lookahead — that's PCRE, not POSIX ERE. macOS ships BSD grep, which will treat `(?!ype)` literally and never match anything (or, depending on the build, error out). The gate will either silently pass when it shouldn't, or fail the task. The grep was added because `useState` and `useStateType` would collide on a naive `useStateT` match — but there is no `useStateType` anywhere in the source (verified — it doesn't appear in any of the 14 source files). The lookahead is unnecessary; the bare token `useStateT` is safe.

Same risk applies to the gate's intent on `useStateA` (collision with `useStateApp` — but the regex already lists `useStateApp` separately, so the collision matters in the other direction: matching `useStateApp` against the `useStateA` alternative is a false positive on a file that legitimately only has `useStateApp`. The simpler fix is to anchor with word boundaries: `\buseStateA\b`).

**Fix:** replace `useStateT(?!ype)` with `useStateT` (no collision exists), and add `\b` word boundaries to the other ambiguous tokens (`useStateA`, `useStateF`, `useStateC`, `useStateG`). Confirm by running the rewritten regex on macOS before locking the plan.

### 2. MINOR — Task 2 mischaracterizes the legacy `window.claude.complete` behavior
The `<action>` for `AiChat.jsx` (PLAN.md line 336) says wrapping in `if (typeof window.claude?.complete === 'function') { ... }` is behavior-preserving "because the legacy frontend produced an undefined error in the same scenario". Inspection of `frontend/ai-chat.jsx:25-42` shows the call is inside `try/catch`, so the legacy frontend actually surfaced `"(couldn't reach the model — try again)"` — it did NOT throw uncaught. The proposed wrap is fine (functionally identical in dev where neither path will succeed), but the justification is wrong. The ported fix message is also different: `"(AI chat will be wired in a later phase.)"` vs the legacy `"(couldn't reach the model — try again)"`. This is a visible string change and the visual-parity gate at 1200×800 does NOT require the user to open the AI bubble and send a message, so it can slip through.

**Fix:** in Task 2 Step describing AiChat, either (a) keep the legacy `"(couldn't reach the model — try again)"` message string, or (b) add an explicit instruction to the Task 4 checkpoint to open the AI bubble, send any message, and confirm the response text matches the legacy frontend.

### 3. MINOR — node-version preflight missing
CONTEXT.md asserts `node v22.14 ✓` but Task 1 Step 1 only preflights pnpm/corepack, not node. Vite 5.4 requires Node ≥18. If a future executor runs this on a stale machine, `pnpm install` will succeed but `pnpm dev` may fail with cryptic errors. Adds 1 line to fix.

**Fix:** prepend to Task 1 Step 1: `node -v | awk -F. '{ exit ($1+0 >= 18) ? 0 : 1 }' || { echo "Node 18+ required"; exit 1; }`

### 4. MINOR — Task 1 verify gate uses `pnpm install --frozen-lockfile=false` flag form
`pnpm install --frozen-lockfile=false` is valid pnpm syntax but the more idiomatic form is omitting the flag entirely (default is to write the lockfile). Not a blocker, just noise. If `pnpm-lock.yaml` doesn't exist yet (which it doesn't on first run), the default behavior writes it. Leave as-is unless plan is being touched anyway.

### 5. MINOR — Task 1 / Task 3 background-server cleanup uses `pkill -f vite`
This will match anything with "vite" in its argv — including the user's editor, an unrelated electron app, etc. Limited blast radius on a developer machine, but worth scoping to the just-spawned PID. Use `pnpm dev & PID=$!; ...; kill $PID` instead of `pkill -f vite`.

### 6. MINOR — Sweep gate in Task 5 over-broad
The hygiene grep (PLAN.md line 495) excludes `node_modules` and `/dist/` but does NOT exclude `pnpm-lock.yaml`. The lockfile contains package URLs that reference `@babel/runtime` (a transitive dep of `react-dom`/`@vitejs/plugin-react-swc`), and depending on resolution might match `@babel/standalone`. Defensive fix: also exclude `pnpm-lock.yaml` from the babel-standalone sweep. The text-pattern `text/babel` is also too loose — narrow to `text/babel"|@babel/standalone` quoted to avoid matching prose in the lockfile.

### 7. INFO — visual-parity rigor is strong
Task 4 explicitly enumerates all 8 pages by name AND walks the user through the 5 Tweaks-panel control axes (Accent × 3, Density × 3, Sidebar × 2, Layout × 4, Mock data × 2). That's the right level of rigor for "pixel-identical at 1200×800". No change needed.

### 8. INFO — independence from siblings is correctly bounded
Files modified list (PLAN.md frontmatter lines 8-29) contains only paths under `frontend-vite/`. The Task 5 `<action>` Step 4 explicitly runs `git status frontend/` and reverts any drift. `bin/` and `lib/` are not referenced anywhere in the action text. The plan stays in its lane.

### 9. INFO — Tauri-ready output is verified
Task 5 verify gate checks both `grep -q './assets/' dist/index.html` (positive) AND `! grep -qE '"/assets/' dist/index.html` (negative), which catches the case where `base: './'` is accidentally set to `'/'`. This is exactly what Phase 2 needs.

## Suggested edits (if executing REVISE)

**Edit 1 — PLAN.md line 359:** replace
```
useStateT(?!ype)|useRefT|useEffectT
```
with
```
\\buseStateT\\b|\\buseRefT\\b|\\buseEffectT\\b
```
and add `\b` boundaries to the other single-letter-suffix tokens (`useStateA`, `useStateF`, `useStateC`, `useStateG`, `useMemoA`, `useMemoC`).

**Edit 2 — PLAN.md line 336:** change
```
} else { return "(AI chat will be wired in a later phase.)"; }
```
to keep the legacy string:
```
} else { return "(couldn't reach the model — try again)"; }
```
OR add to Task 4 step 5 a sub-bullet: "Open the AI bubble, send any test message, confirm the fallback text matches between 5173 and 8090."

**Edit 3 — PLAN.md Task 1 Step 1:** prepend node version check before the pnpm preflight.

**Edit 4 (optional):** swap `pkill -f vite` for tracked-PID cleanup in Tasks 1, 3 verify gates and Task 4 how-to-verify.

Once edits 1 + 2 are applied (3 and 4 are nice-to-have), this plan is green-light for execution.
