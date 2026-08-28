# Worklog

Session-by-session record of what changed and why. Newest first.
One `## YYYY-MM-DD` heading per session; keep entries terse and factual.

## 2026-08-16

**Session: repo critique → Windows pivot landed, VPS wired, legacy frontend frozen**
(branch `feat/envy-windows-pivot`, unpushed)

- `55cff5e` feat(envy): committed the previously-uncommitted Windows pivot —
  44 files, +6615/−480. Envy runtime (`lib/envy_db.py`, `lib/api/agent.py`,
  tool gateway, hermes bridge), wired frontend-vite pages, Tauri `py -3`
  spawn, `Envy.spec`, both vendor submodules, 3 test files.
- `d3c9dfd` fix(tree_vps): VPS walker now works on Windows. Root causes:
  1. Win32-OpenSSH has no ControlMaster/mux support — the mux options made
     every daemon SSH call fail ("Failed to connect to new control master").
     Now emitted only on POSIX.
  2. Bare `ssh` resolved via PATH to Git's MSYS ssh, whose runtime
     path-converts POSIX-looking argv (`/home/avi/x` →
     `C:/Program Files/Git/home/avi/x`, glob quoting mangled), breaking the
     remote `find`. New `_ssh_bin()` prefers
     `%SystemRoot%\System32\OpenSSH\ssh.exe`.
  Verified live: buldoze/roofing-sydney/moana/hot-tyres trees walk RC 0.
  `tests/test_tree_vps.py` argv contract test made platform-aware (18/18 pass).
- `65fa6e6` docs(frontend): froze legacy `frontend/` (Babel/CDN). Vite tree is
  canonical. `nerd-mode.jsx` + `galaxy-data.jsx` flagged port-or-drop.
- `~/.invisible/invisible.toml` rewritten (untracked, per-machine):
  - `vps.host = "vps"` — real ssh alias (docs assumed `srv982719`, which
    doesn't exist in `~/.ssh/config`); identity `~/.ssh/id_ed25519_vps`.
  - 8 projects (added buldoze, activend, alfa); verified VPS paths:
    buldoze `/home/avi/buldoze`, hot-tyres `/home/avi/motorcycle_tyres`,
    moana `/home/avi/projects/Moana`, roofing `/home/avi/roofing.sydney`.
  - `claude_model = "claude-sonnet-5"` (was stale `claude-sonnet-4-6`).
  - 7 terminal panes incl. `vps-main` ssh pane.
  Validated through `lib/config.load_toml()`.

**Open items**
- Push `feat/envy-windows-pivot` + open PR.
- Rebuild `dist/Envy.exe` — packaged build predates the tree_vps fix.
- Restart dashboard daemon to pick up new toml + fix.
- Codex review of `d3c9dfd` skipped (denied this session) — rerun if wanted.
- Port-or-drop decision: `nerd-mode.jsx`, `galaxy-data.jsx`.
- CI is ubuntu-only; Windows job missing for a Windows-target product.
- Known drift (from critique): route registry bypassed for POST/PUT/DELETE,
  Tauri Rust bridge unused by frontend (`csp: null`), two SQLite stores,
  blocking Infisical call adds ~9s to launch, `lib/config.py` TOML
  backslash-repair regex can mangle valid escapes.
