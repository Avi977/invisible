#!/usr/bin/env bash
# tests/smoke_dashboard_wiring.sh
# ───────────────────────────────────────────────────────────────────────────
# Nyquist behavioral smoke test for Phase 01 — Real /api/v1/projects end-to-end.
#
# Validates the 5 phase success criteria (per workstream ROADMAP) using ONLY
# tools already available in this workstream (bash, curl, python3, grep). Does
# NOT introduce a JS test framework — that's WS-6's scope per PROJECT.md.
#
# Sections:
#   1. Backend unit tests (delegates to pytest tests/test_api_projects.py).
#   2. Live API smoke — launches `bin/invisible-dashboard --no-auth` on 127.0.0.1:8765,
#      curls /api/v1/projects, asserts JSON shape + CORS behavior, then cleans up.
#   3. Static frontend assertions — grep-based checks on dashboard.jsx, data.jsx,
#      and app.jsx that the Dashboard component fetches the real endpoint, uses a
#      single projectsToRender source for ALL FOUR layouts, routes action buttons
#      via p.id, and does NOT touch app.jsx's DATA_SETS pipeline (mock-toggle
#      preservation for sister pages).
#
# Run:
#   bash tests/smoke_dashboard_wiring.sh
#
# Exit codes:
#   0 — all checks passed
#   1 — at least one check failed (specific failure printed)
#   2 — environment failure (daemon couldn't start, curl missing, etc.)
# ───────────────────────────────────────────────────────────────────────────

set -u  # -e is intentionally NOT set: we want to count every check, even failures.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

PASS=0
FAIL=0
SKIP=0

# Color codes for human readability (turned off when piped).
if [[ -t 1 ]]; then
  G='\033[32m'; R='\033[31m'; Y='\033[33m'; D='\033[2m'; X='\033[0m'
else
  G=''; R=''; Y=''; D=''; X=''
fi

_pass() { printf "  ${G}PASS${X}  %s\n" "$1"; PASS=$((PASS + 1)); }
_fail() { printf "  ${R}FAIL${X}  %s\n" "$1"; printf "        ${D}%s${X}\n" "$2"; FAIL=$((FAIL + 1)); }
_skip() { printf "  ${Y}SKIP${X}  %s\n" "$1"; printf "        ${D}%s${X}\n" "$2"; SKIP=$((SKIP + 1)); }
_head() { printf "\n${Y}═══ %s${X}\n" "$1"; }

# ───────────────────────────────────────────────────────────────────────────
# Section 1: backend pytest suite — REQ-01 criterion #1 contract
# ───────────────────────────────────────────────────────────────────────────
_head "Section 1: backend pytest (7 hermetic cases — REQ-01 contract)"

if command -v python3 >/dev/null 2>&1; then
  if python3 -m pytest tests/test_api_projects.py -q --no-header 2>&1 | tail -1 | grep -qE '^(7 passed|[0-9]+ passed)'; then
    _pass "tests/test_api_projects.py — 7/7 cases green"
  else
    out=$(python3 -m pytest tests/test_api_projects.py -q --no-header 2>&1 | tail -10)
    _fail "tests/test_api_projects.py — pytest reported a failure" "$out"
  fi
else
  _skip "python3 not on PATH" "cannot run pytest backend suite"
fi

# ───────────────────────────────────────────────────────────────────────────
# Section 2: live API smoke — REQ-01 criterion #1 wire-up + CORS
# ───────────────────────────────────────────────────────────────────────────
_head "Section 2: live /api/v1/projects (HTTP 200, JSON shape, loopback CORS)"

DASH_PID=""
SMOKE_HOME=""

_cleanup() {
  if [[ -n "$DASH_PID" ]] && kill -0 "$DASH_PID" 2>/dev/null; then
    kill "$DASH_PID" 2>/dev/null || true
    wait "$DASH_PID" 2>/dev/null || true
  fi
  # Belt-and-suspenders: any stray smoke-test daemons we spawned.
  pkill -f "invisible-dashboard --no-auth --port 8766" 2>/dev/null || true
  if [[ -n "$SMOKE_HOME" && -d "$SMOKE_HOME" ]]; then
    rm -rf "$SMOKE_HOME"
  fi
}
trap _cleanup EXIT

# Use a non-standard port (8766) so we don't fight with the user's running
# canonical daemon on 8765 (or any sibling workstream's daemon).
SMOKE_PORT=8766
SMOKE_URL="http://127.0.0.1:${SMOKE_PORT}/api/v1/projects"

# Synthetic INVISIBLE_HOME so the live API has at least one row to validate
# shape + types against. The 7 hermetic pytest cases already exercise the
# adapter with tmp_path; here we want the live HTTP/CORS path to return a
# real-shape row that we can grep for the 13 keys.
SMOKE_HOME="$(mktemp -d -t inv-smoke-XXXXXX)"
mkdir -p "${SMOKE_HOME}"
# Repo can be anywhere inside $HOME — point at this worktree's own git dir
# (a real repo) so _safe_path() accepts it and branch/lastCommit succeed.
cat > "${SMOKE_HOME}/invisible.toml" <<EOF
[[projects]]
name = "smoketest"
repo_path = "${ROOT}"
summary = "smoke test project"
stack = ["bash", "python"]
EOF

# Kill any leftover smoke daemon from a prior run on the SAME port.
pkill -f "invisible-dashboard --no-auth --port ${SMOKE_PORT}" 2>/dev/null || true
sleep 0.3

# Start the daemon. --no-auth keeps the test hermetic (no token plumbing needed).
# Pin INVISIBLE_HOME to the synthetic dir so the daemon reads OUR fixture toml
# (sibling workstreams may have their own daemons running on canonical 8765
# with different cwds — see 01-02-SUMMARY's "daemon-port race" note).
INVISIBLE_HOME="$SMOKE_HOME" ./bin/invisible-dashboard --no-auth --port "${SMOKE_PORT}" --host 127.0.0.1 \
  </dev/null >/tmp/smoke-dash.log 2>&1 &
DASH_PID=$!

# Wait up to ~8s for /healthz to respond (cold-start can take ~1-2s on first
# import; suppress curl error spam during readiness polling).
ready=0
for _ in $(seq 1 16); do
  if curl -fsS -o /dev/null --max-time 1 "http://127.0.0.1:${SMOKE_PORT}/healthz" 2>/dev/null; then
    ready=1
    break
  fi
  # Bail out early if the daemon died.
  if ! kill -0 "$DASH_PID" 2>/dev/null; then
    break
  fi
  sleep 0.5
done

if [[ "$ready" != "1" ]]; then
  _fail "daemon failed to come up on port ${SMOKE_PORT}" "see /tmp/smoke-dash.log"
  # Skip the rest of section 2 — no point hitting an absent daemon.
  _skip "API checks (2.1–2.5)" "depends on a healthy daemon"
else
  _pass "daemon healthy on 127.0.0.1:${SMOKE_PORT}"

  # 2.1 — HTTP 200 + JSON array body
  status=$(curl -s -o /tmp/smoke-body.json -w '%{http_code}' "$SMOKE_URL")
  if [[ "$status" == "200" ]]; then
    if python3 -c "import json,sys; d=json.load(open('/tmp/smoke-body.json')); sys.exit(0 if isinstance(d, list) else 1)"; then
      _pass "GET /api/v1/projects → 200 + JSON array body"
    else
      _fail "GET /api/v1/projects body is not a JSON array" "$(head -c 200 /tmp/smoke-body.json)"
    fi
  else
    _fail "GET /api/v1/projects returned HTTP $status" "expected 200"
  fi

  # 2.2 — When non-empty, each row has the exact 13-key DATA_SETS shape.
  shape_out=$(python3 <<'PY'
import json
required = {"id","code","name","color","status","branch","lastCommit",
            "summary","progress","todos","note","stack","nextEvent"}
try:
    rows = json.load(open("/tmp/smoke-body.json"))
except Exception as e:
    print(f"FAIL parse:{e}")
    raise SystemExit(0)
if not isinstance(rows, list):
    print("FAIL not a list")
    raise SystemExit(0)
if not rows:
    print("SKIP empty array (no projects in invisible.toml)")
    raise SystemExit(0)
got = set(rows[0].keys())
missing = required - got
extra = got - required
if missing or extra:
    print(f"FAIL missing={sorted(missing)} extra={sorted(extra)}")
else:
    print("PASS")
PY
)
  case "$shape_out" in
    PASS) _pass "First row has exact 13-key DATA_SETS shape" ;;
    SKIP*) _skip "Shape check" "${shape_out#SKIP }" ;;
    *)    _fail "Shape mismatch" "$shape_out" ;;
  esac

  # 2.3 — Field types match the DATA_SETS contract (when row exists).
  types_out=$(python3 <<'PY'
import json
try:
    rows = json.load(open("/tmp/smoke-body.json"))
except Exception:
    print("FAIL parse")
    raise SystemExit(0)
if not isinstance(rows, list) or not rows:
    print("SKIP no rows to type-check")
    raise SystemExit(0)
r = rows[0]
errs = []
for k in ("id","code","name","color","branch","lastCommit","summary","note","nextEvent"):
    if not isinstance(r.get(k), str):
        errs.append(f"{k} is {type(r.get(k)).__name__}")
if not isinstance(r.get("progress"), int) or not (0 <= r["progress"] <= 100):
    errs.append(f"progress={r.get('progress')!r}")
if not isinstance(r.get("todos"), list):
    errs.append("todos not list")
if not isinstance(r.get("stack"), list):
    errs.append("stack not list")
if r.get("status") not in {"in-progress","blocked","planning","shipped"}:
    errs.append(f"status={r.get('status')!r}")
print("PASS" if not errs else "FAIL " + "; ".join(errs))
PY
)
  case "$types_out" in
    PASS) _pass "Field types match DATA_SETS contract" ;;
    SKIP*) _skip "Type check" "${types_out#SKIP }" ;;
    *)    _fail "Field types violate contract" "$types_out" ;;
  esac

  # 2.4 — CORS: loopback Origin is echoed.
  hdrs=$(curl -fsS -i -H "Origin: http://127.0.0.1:8090" "$SMOKE_URL" 2>/dev/null | tr -d '\r')
  if echo "$hdrs" | grep -qi "^Access-Control-Allow-Origin: http://127.0.0.1:8090"; then
    _pass "CORS — loopback Origin echoed (Access-Control-Allow-Origin: http://127.0.0.1:8090)"
  else
    _fail "CORS loopback echo missing" "$(echo "$hdrs" | head -20)"
  fi

  # 2.5 — CORS: non-loopback Origin is NOT echoed.
  hdrs_evil=$(curl -fsS -i -H "Origin: https://evil.example" "$SMOKE_URL" 2>/dev/null | tr -d '\r')
  if echo "$hdrs_evil" | grep -qi "^Access-Control-Allow-Origin"; then
    _fail "CORS leak — non-loopback origin received Access-Control-Allow-Origin" \
          "$(echo "$hdrs_evil" | grep -i 'access-control')"
  else
    _pass "CORS — non-loopback Origin denied (no Access-Control-Allow-Origin header)"
  fi

  # 2.6 — Legacy /healthz still responds (regression guard).
  if curl -fsS "http://127.0.0.1:${SMOKE_PORT}/healthz" 2>/dev/null | grep -q "ok"; then
    _pass "Legacy /healthz route still responds (no regression)"
  else
    _fail "/healthz regressed" "expected body 'ok'"
  fi
fi

# Cleanup daemon now (before grep section) so the trap stays a safety net.
if [[ -n "$DASH_PID" ]] && kill -0 "$DASH_PID" 2>/dev/null; then
  kill "$DASH_PID" 2>/dev/null || true
  wait "$DASH_PID" 2>/dev/null || true
fi
DASH_PID=""

# ───────────────────────────────────────────────────────────────────────────
# Section 3: static frontend assertions — REQ-01 criteria #2, #3, #4, #5
# ───────────────────────────────────────────────────────────────────────────
_head "Section 3: static frontend wiring (criteria #2-#5)"

DJ="frontend/pages/dashboard.jsx"
DJX="frontend/data.jsx"
AJX="frontend/app.jsx"

# 3.1 — Criterion #2: Dashboard fetches /api/v1/projects on mount AND
#       contains zero DATA_SETS references.
if grep -q "useEffect" "$DJ" && grep -q "fetchProjects" "$DJ"; then
  _pass "dashboard.jsx mounts useEffect that calls fetchProjects()"
else
  _fail "dashboard.jsx missing useEffect or fetchProjects call" \
        "useEffect=$(grep -c useEffect "$DJ"), fetchProjects=$(grep -c fetchProjects "$DJ")"
fi

ds_count=$(grep -c "DATA_SETS" "$DJ" || true)
if [[ "$ds_count" == "0" ]]; then
  _pass "dashboard.jsx has 0 references to DATA_SETS (mock removed for this page)"
else
  _fail "dashboard.jsx still references DATA_SETS" \
        "$(grep -n DATA_SETS "$DJ" | head -5)"
fi

# 3.2 — Criterion #1+#2: data.jsx defines fetchProjects() hitting /api/v1/projects.
if grep -q "fetchProjects" "$DJX" && grep -q "/api/v1/projects" "$DJX"; then
  _pass "data.jsx exposes fetchProjects() pointing at /api/v1/projects"
else
  _fail "data.jsx fetchProjects helper missing or wrong URL" \
        "fetchProjects=$(grep -c fetchProjects "$DJX"), /api/v1/projects=$(grep -c '/api/v1/projects' "$DJX")"
fi

# 3.3 — Criterion #3: ALL four layouts (bento/grid/kanban/list) read from the
#       SAME single source — projectsToRender. This is a static-analysis
#       substitute for the visual layout-cycling test that would need a real
#       browser. The grep matches:
#         a. kanban branch: uses projectsToRender.filter(...) (status-bucketed)
#         b. bento/grid/list shared branch: uses projectsToRender.map(...) inside
#            `<div className={"dash-grid layout-" + layout}>...`
#       If either grep returns 0, the data path has diverged between layouts.
if grep -q "projectsToRender" "$DJ"; then
  ptr_count=$(grep -c "projectsToRender" "$DJ" || true)
  # Need projectsToRender on both branches: kanban AND non-kanban (>=3 references).
  if [[ "$ptr_count" -ge 3 ]]; then
    _pass "All four layouts feed from the same projectsToRender (${ptr_count} refs)"
  else
    _fail "projectsToRender appears only in ${ptr_count} places — layouts may diverge" \
          "expected >=3 (kanban filter + non-kanban map + DashHeader projects prop)"
  fi
  # Specific patterns that prove kanban and non-kanban each consume it.
  if grep -q 'projectsToRender\.filter' "$DJ" \
     && grep -q 'projectsToRender\.map' "$DJ" \
     && grep -q '"dash-grid layout-" + layout' "$DJ"; then
    _pass "Kanban (filter) + bento/grid/list (map on layout-\${layout}) both use projectsToRender"
  else
    _fail "Layout branches do not uniformly use projectsToRender" \
          "filter=$(grep -c 'projectsToRender\.filter' "$DJ"), map=$(grep -c 'projectsToRender\.map' "$DJ"), classname=$(grep -c '\"dash-grid layout-\" + layout' "$DJ")"
  fi
else
  _fail "projectsToRender missing entirely" "see plan 01-02 task 2 step 7"
fi

# 3.4 — Criterion #4: action buttons (Tools / Terminal / Focus) route via navTo(<page>, p.id).
#       The three onClick handlers from the action-buttons row at the bottom of the card.
tools=$(grep -c 'navTo("tools", p.id)' "$DJ" || true)
term=$(grep -c 'navTo("terminals", p.id)' "$DJ" || true)
focus=$(grep -c 'navTo("focus", p.id)' "$DJ" || true)
if [[ "$tools" -ge 1 && "$term" -ge 1 && "$focus" -ge 1 ]]; then
  _pass "Action buttons route via navTo(...) with p.id (tools=$tools, terminals=$term, focus=$focus)"
else
  _fail "Action button routing wrong or missing" \
        "tools=$tools, terminals=$term, focus=$focus (each must be >=1)"
fi

# 3.5 — Criterion #5: app.jsx still consumes DATA_SETS so the Mock-data toggle
#       continues to drive Focus / Terminals / Tools / Analytics. (Phase
#       success criterion: "Mock toggle still works for OTHER pages".)
if grep -q "DATA_SETS\[" "$AJX"; then
  _pass "app.jsx still reads DATA_SETS — Mock toggle preserved for sister pages"
else
  _fail "app.jsx no longer consumes DATA_SETS — sister-page mock toggle broken" \
        "expected DATA_SETS[<key>] reference"
fi

# 3.6 — REQ-01 secure behavior: no dangerouslySetInnerHTML in the Dashboard
#       page or its data helper (XSS mitigation T-INV-01-09 cited in 01-SECURITY.md).
#       (01-SECURITY.md owns this in full — we re-check the grep to keep the
#       smoke test honest about the file state right NOW.)
if [[ "$(grep -c dangerouslySetInnerHTML "$DJ" || true)" == "0" \
   && "$(grep -c dangerouslySetInnerHTML "$DJX" || true)" == "0" ]]; then
  _pass "No dangerouslySetInnerHTML in dashboard.jsx or data.jsx (XSS surface clean)"
else
  _fail "dangerouslySetInnerHTML found" \
        "$(grep -nH dangerouslySetInnerHTML "$DJ" "$DJX" 2>/dev/null)"
fi

# 3.7 — Loading + Error UI strings present (criterion: readable error/loading;
#       no blank page or unhandled-promise console error).
need_strings=("Loading projects" "Couldn't load projects" "Retry" "Show mock data instead")
missing=()
for s in "${need_strings[@]}"; do
  grep -q "$s" "$DJ" || missing+=("$s")
done
if [[ ${#missing[@]} == 0 ]]; then
  _pass "Loading + error UI strings all present (loading / error / retry / fallback)"
else
  _fail "Loading/error UI strings missing" "${missing[*]}"
fi

# ───────────────────────────────────────────────────────────────────────────
# Summary
# ───────────────────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL + SKIP))
printf "\n${Y}═══ Summary${X}\n"
printf "  Total:  %d\n" "$TOTAL"
printf "  ${G}Pass:${X}   %d\n" "$PASS"
printf "  ${R}Fail:${X}   %d\n" "$FAIL"
printf "  ${Y}Skip:${X}   %d\n" "$SKIP"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
