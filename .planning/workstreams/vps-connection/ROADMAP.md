# Workstream: vps-connection (M2 — VPS hardening)

> Sister-workstreams: tauri-windows, tools-page, relations-page,
> calendar-events, ci-and-onboarding. Mostly isolated. Conflict surface:
> `lib/api/tree_vps.py` (you rewrite SSH-driven walker) and `lib/pty_server.py`
> (you add ssh variant). Both files already exist on main from M1 — you
> extend them, not replace.

## Phases

- [ ] **Phase 1: SSH ControlMaster + invisible.toml host** — `srv982719` wired, connection multiplexed
- [ ] **Phase 2: `invisible-server` as systemd service + nginx vhost** — dashboard daemon available remotely under HTTPS
- [ ] **Phase 3: Folders/VPS column populated + Terminals ssh variant** — end-to-end VPS reach inside the app

## Phase Details

### Phase 1: SSH ControlMaster + invisible.toml host

**Goal:** A single `ssh srv982719` from inside the app reuses one TCP/TLS connection, multiplexed via ControlMaster. The 6 terminal panes can each open `ssh srv982719` without each one triggering a new auth handshake.

**Depends on:** Nothing (foundation for Phases 2 and 3).

**Requirements:** REQ-VPS-01 (see `.planning/REQUIREMENTS.md` — fall back to milestone-level REQ-04 if M2 requirements not yet enumerated).

**Success criteria:**
1. `~/.ssh/config` has a `Host srv982719` block with `ControlMaster auto`, `ControlPath ~/.ssh/cm-%r@%h:%p`, `ControlPersist 10m`.
2. `invisible.toml` `vps.host = "srv982719"` and `vps.identity = "~/.ssh/id_ed25519"` (or similar).
3. From a fresh shell, `ssh srv982719 echo ok` succeeds without password prompt (key-based auth).
4. A second `ssh srv982719 echo ok` runs in under 200ms (reuses the master connection).

**Plans:** 2 plans
- [ ] 01-01: SSH config + invisible.toml wiring; document the ed25519 key generation in README
- [ ] 01-02: `lib/api/tree_vps.py` rewritten to actually hit `srv982719` (currently returns 503 because `vps.host=""`)

### Phase 2: invisible-server systemd unit + nginx vhost

**Goal:** `invisible-server` runs as `systemd --user` on `srv982719`, behind nginx at `https://invisible.theprofitplatform.com.au`, with bearer-token auth.

**Depends on:** Phase 1 (SSH multiplex used by deploy scripts).

**Requirements:** REQ-VPS-02 (M2 deployment).

**Success criteria:**
1. `/srv/invisible/invisible-server.service` exists and is enabled (`systemctl --user enable invisible-server`).
2. nginx vhost at `theprofitplatform.com.au` reverse-proxies `https://invisible.theprofitplatform.com.au/` → `127.0.0.1:8765`.
3. `INVISIBLE_SERVER_TOKEN` stored in Infisical; loaded by both Mac app and VPS daemon.
4. `curl -H "Authorization: Bearer $TOKEN" https://invisible.theprofitplatform.com.au/api/projects` returns 200; without the token returns 401.

**Plans:** 2 plans
- [ ] 02-01: systemd unit + nginx config (deployed via ssh, NOT via the Mac repo)
- [ ] 02-02: Cert via existing wildcard (`*.theprofitplatform.com.au` already exists per memory `vps_infra.md`)

### Phase 3: In-app VPS reach (Folders + Terminals ssh variant)

**Goal:** Folders page's VPS column shows real `srv982719` files. Terminals page panes can launch `ssh srv982719` and behave normally.

**Depends on:** Phase 1 (SSH multiplex) and Phase 2 (remote dashboard daemon).

**Requirements:** REQ-VPS-03 (M2 in-app reach).

**Success criteria:**
1. `GET /api/v1/tree/vps` returns the actual tree from `srv982719:/srv/<configured-paths>` (not the 503).
2. The frontend Folders page renders the VPS column without the "not configured" placeholder.
3. A terminal pane configured with `ssh srv982719` opens, types `pwd`, returns `/home/<user>` from the VPS.
4. SSH connection drops (kill the master) → terminal pane stays usable; next command transparently re-establishes via ControlMaster.

**Plans:** 2 plans
- [ ] 03-01: `lib/pty_server.py` ssh variant — pane id config from `invisible.toml` `[[terminals]]` block
- [ ] 03-02: Folders frontend already uses the endpoint; smoke-test through it

## Files this workstream OWNS

- `invisible.toml.example` — VPS section template
- `invisible.toml` (your local; gitignored) — for testing
- `~/.ssh/config` — out-of-repo, documented
- `lib/api/tree_vps.py` — REWRITE the SSH-driven walker (currently returns 503)
- `lib/pty_server.py` — ADD ssh variant; don't touch existing local-shell path
- `bin/invisible-server` and supporting `infra/systemd/invisible-server.service` (new)
- `infra/nginx/invisible.conf` (new)

## Files this workstream EDITS LIGHTLY

- `README.md` — VPS setup section
- `bin/invisible-doctor` — add SSH reachability check

## Files this workstream MUST NOT TOUCH

- `frontend/pages/folders.jsx` and `frontend/pages/terminals.jsx` — locked.
- `lib/api/{projects,chat,tree_local,tree_repo,analytics}.py` — siblings own these.
- `src-tauri/` — owned by tauri-windows.
- `.github/workflows/` — owned by ci-and-onboarding.

## Verify locally

```bash
# Phase 1
ssh srv982719 echo ok
ssh -v srv982719 echo ok 2>&1 | grep "Connection to" | head -1   # should reuse master

# Phase 2 (after deploy)
curl -H "Authorization: Bearer $INVISIBLE_SERVER_TOKEN" https://invisible.theprofitplatform.com.au/api/projects

# Phase 3
curl -s http://127.0.0.1:8765/api/v1/tree/vps | python3 -m json.tool | head -20  # should NOT be 503
# In-app: open Terminals, configure a pane with `ssh srv982719`, run `pwd`
```

## Resume

```bash
cd ~/.invisible-ws/vps-connection
gsd-sdk query workstream.set vps-connection --raw --cwd .
/gsd:plan-phase 1
```
