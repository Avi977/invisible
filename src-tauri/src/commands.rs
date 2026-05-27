//! The 5 `#[tauri::command]` async functions wrapping the existing
//! `invisible-*` CLI surface. All return `Result<T, String>`. Path
//! resolution goes through `invisible_home()` so the same code runs on
//! macOS / Linux / Windows (Phase 3 cross-compile target).

use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

// ─────────────────────────────────────────────────────────────────────────
// Types — canonical shapes from CONTEXT/PLAN. Serializable to JSON.
// ─────────────────────────────────────────────────────────────────────────

#[derive(Serialize, Deserialize, Debug, Clone, Default)]
pub struct ProjectMeta {
    pub project: String,
    #[serde(default)]
    pub state: String, // "RUN" | "idle" | "stale"
    #[serde(default)]
    pub iter: i32,
    #[serde(default)]
    pub max_iters: i32,
    #[serde(default)]
    pub verdict: String,
    #[serde(default)]
    pub summary: String,
    #[serde(default)]
    pub host: String,
    #[serde(default)]
    pub updated_at: String,
    #[serde(default)]
    pub started_at: String,
    #[serde(default)]
    pub age: String,
    #[serde(default)]
    pub cost_usd: f64,
    #[serde(default)]
    pub task_first: String,
}

#[derive(Serialize, Debug, Clone)]
pub struct RunHandle {
    pub pid: u32,
    pub project: String,
}

#[derive(Serialize, Debug, Clone)]
pub struct StatusReport {
    pub projects: Vec<ProjectMeta>,
    pub fetched_at: String,
    pub source: String,
}

// ─────────────────────────────────────────────────────────────────────────
// Cross-platform path helper — NEVER hardcode an absolute home path.
// ─────────────────────────────────────────────────────────────────────────

pub(crate) fn invisible_home() -> PathBuf {
    if let Ok(env_home) = std::env::var("INVISIBLE_HOME") {
        return PathBuf::from(env_home);
    }
    dirs::home_dir()
        .map(|h| h.join(".invisible"))
        .expect("home_dir() must resolve on macOS/Linux/Windows")
}

fn iso8601_now() -> String {
    // serde_json::Value::String of a coarse epoch-derived ISO-8601 is sufficient
    // for the `fetched_at` field; no need to pull chrono just for this.
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    // RFC 3339-ish: YYYY-MM-DDTHH:MM:SSZ derived from `secs` via integer math.
    // We delegate to format_secs for legibility.
    format_secs_as_iso(secs)
}

fn format_secs_as_iso(epoch_secs: u64) -> String {
    // Minimal epoch → ISO formatter (UTC). Days since 1970-01-01 + time of day.
    let secs_per_day: u64 = 86_400;
    let day_secs = epoch_secs % secs_per_day;
    let h = (day_secs / 3600) as u32;
    let m = ((day_secs % 3600) / 60) as u32;
    let s = (day_secs % 60) as u32;
    let days = (epoch_secs / secs_per_day) as i64;
    let (year, month, day) = days_to_ymd(days);
    format!("{year:04}-{month:02}-{day:02}T{h:02}:{m:02}:{s:02}Z")
}

fn days_to_ymd(mut days_from_epoch: i64) -> (i32, u32, u32) {
    // 1970-01-01 is day 0. Iterate years/months — fine for ~millennium range.
    let mut year: i32 = 1970;
    loop {
        let leap = is_leap(year);
        let yd = if leap { 366 } else { 365 };
        if days_from_epoch < yd {
            break;
        }
        days_from_epoch -= yd;
        year += 1;
    }
    let leap = is_leap(year);
    let month_lens: [i64; 12] = [
        31,
        if leap { 29 } else { 28 },
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ];
    let mut month: u32 = 1;
    for &ml in &month_lens {
        if days_from_epoch < ml {
            break;
        }
        days_from_epoch -= ml;
        month += 1;
    }
    (year, month, (days_from_epoch + 1) as u32)
}

fn is_leap(y: i32) -> bool {
    (y % 4 == 0 && y % 100 != 0) || (y % 400 == 0)
}

// ─────────────────────────────────────────────────────────────────────────
// list_projects
// ─────────────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn list_projects(app: AppHandle) -> Result<Vec<ProjectMeta>, String> {
    // Path 1 — preferred: shell out to `invisible-status --json`.
    if let Ok(out) = app
        .shell()
        .command("invisible-status")
        .args(["--json"])
        .output()
        .await
    {
        if out.status.success() {
            let stdout = String::from_utf8_lossy(&out.stdout);
            if let Ok(mut parsed) = serde_json::from_str::<Vec<ProjectMeta>>(&stdout) {
                sort_projects(&mut parsed);
                return Ok(parsed);
            }
        }
    }

    // Path 2 — fallback: scan worktrees on disk.
    let worktrees = invisible_home().join("worktrees");
    if !worktrees.exists() {
        return Ok(Vec::new());
    }

    let mut out: Vec<ProjectMeta> = Vec::new();
    let entries = match std::fs::read_dir(&worktrees) {
        Ok(e) => e,
        Err(_) => return Ok(Vec::new()),
    };
    for entry in entries.flatten() {
        let project = entry.file_name().to_string_lossy().into_owned();
        let checkpoint_path = entry
            .path()
            .join("feature")
            .join(".invisible-checkpoint.json");
        if !checkpoint_path.exists() {
            continue;
        }
        let body = match std::fs::read_to_string(&checkpoint_path) {
            Ok(b) => b,
            Err(_) => continue,
        };
        let cp: serde_json::Value = match serde_json::from_str(&body) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let mut meta = ProjectMeta {
            project: project.clone(),
            state: cp
                .get("state")
                .and_then(|v| v.as_str())
                .unwrap_or("idle")
                .to_string(),
            iter: cp.get("iter").and_then(|v| v.as_i64()).unwrap_or(0) as i32,
            max_iters: cp.get("max_iters").and_then(|v| v.as_i64()).unwrap_or(0) as i32,
            verdict: cp
                .get("verdict")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            summary: cp
                .get("summary")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            host: cp
                .get("host")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            updated_at: cp
                .get("updated_at")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            started_at: cp
                .get("started_at")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            age: String::new(),
            cost_usd: cp.get("cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0),
            task_first: cp
                .get("task_first")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
        };
        meta.age = humanize_age(&meta.updated_at);
        out.push(meta);
    }
    sort_projects(&mut out);
    Ok(out)
}

fn sort_projects(items: &mut Vec<ProjectMeta>) {
    // Active runs first; then updated_at descending.
    items.sort_by(|a, b| {
        let a_active = a.state == "RUN";
        let b_active = b.state == "RUN";
        b_active
            .cmp(&a_active)
            .then_with(|| b.updated_at.cmp(&a.updated_at))
    });
}

fn humanize_age(updated_at: &str) -> String {
    // Best-effort: if updated_at is missing or unparseable, return empty.
    // Otherwise emit a short hint like "3m ago" / "1h ago" / "yesterday".
    if updated_at.is_empty() {
        return String::new();
    }
    // ISO 8601: "YYYY-MM-DDTHH:MM:SS[.fff]Z" — we only need approximate diff.
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let then = iso_to_secs(updated_at).unwrap_or(now);
    let diff = now.saturating_sub(then);
    if diff < 60 {
        "just now".to_string()
    } else if diff < 3_600 {
        format!("{}m ago", diff / 60)
    } else if diff < 86_400 {
        format!("{}h ago", diff / 3_600)
    } else if diff < 172_800 {
        "yesterday".to_string()
    } else {
        format!("{}d ago", diff / 86_400)
    }
}

fn iso_to_secs(s: &str) -> Option<u64> {
    // Parse "YYYY-MM-DDTHH:MM:SS" (ignoring optional fractional seconds + Z).
    let core = s.split('.').next().unwrap_or(s).trim_end_matches('Z');
    let (date, time) = core.split_once('T')?;
    let mut d = date.split('-');
    let year: i32 = d.next()?.parse().ok()?;
    let month: u32 = d.next()?.parse().ok()?;
    let day: u32 = d.next()?.parse().ok()?;
    let mut t = time.split(':');
    let h: u32 = t.next()?.parse().ok()?;
    let m: u32 = t.next()?.parse().ok()?;
    let sec: u32 = t.next()?.parse().ok()?;
    Some(ymd_hms_to_secs(year, month, day, h, m, sec))
}

fn ymd_hms_to_secs(year: i32, month: u32, day: u32, h: u32, m: u32, s: u32) -> u64 {
    // Compute days from 1970-01-01 to (year, month, day), then add hms.
    let mut days: i64 = 0;
    if year >= 1970 {
        for y in 1970..year {
            days += if is_leap(y) { 366 } else { 365 };
        }
        let month_lens: [i64; 12] = [
            31,
            if is_leap(year) { 29 } else { 28 },
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ];
        for (idx, &ml) in month_lens.iter().enumerate() {
            if (idx as u32) + 1 >= month {
                break;
            }
            days += ml;
        }
        days += (day as i64).saturating_sub(1);
    }
    let secs = (days as u64) * 86_400 + (h as u64) * 3_600 + (m as u64) * 60 + (s as u64);
    secs
}

// ─────────────────────────────────────────────────────────────────────────
// run_orchestrator
// ─────────────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn run_orchestrator(
    app: AppHandle,
    project: String,
    task: Option<String>,
) -> Result<RunHandle, String> {
    // Clone owned data into the async task BEFORE consuming `project` for the
    // RunHandle. The async block must own its `project` copy for emit payloads,
    // and the app handle must be cloneable too.
    let project_for_task = project.clone();
    let app_handle = app.clone();

    let mut args: Vec<String> = vec![project.clone()];
    if let Some(t) = task {
        args.push("--task".into());
        args.push(t);
    }

    let (mut rx, child) = app
        .shell()
        .command("invisible-review")
        .args(&args)
        .spawn()
        .map_err(|e| e.to_string())?;

    let pid = child.pid();

    tauri::async_runtime::spawn(async move {
        let project = project_for_task; // owned by this task
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let _ = app_handle.emit(
                        "run:stdout",
                        serde_json::json!({
                            "project": project,
                            "line": String::from_utf8_lossy(&line),
                        }),
                    );
                }
                CommandEvent::Stderr(line) => {
                    let _ = app_handle.emit(
                        "run:stderr",
                        serde_json::json!({
                            "project": project,
                            "line": String::from_utf8_lossy(&line),
                        }),
                    );
                }
                CommandEvent::Terminated(payload) => {
                    let _ = app_handle.emit(
                        "run:exit",
                        serde_json::json!({
                            "project": project,
                            "code": payload.code,
                        }),
                    );
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(RunHandle { pid, project })
}

// ─────────────────────────────────────────────────────────────────────────
// kill_run
// ─────────────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn kill_run(app: AppHandle, project: String) -> Result<(), String> {
    let out = app
        .shell()
        .command("invisible-review")
        .args([&project, "--stop"])
        .output()
        .await
        .map_err(|e| e.to_string())?;
    if out.status.success() {
        Ok(())
    } else {
        Err(String::from_utf8_lossy(&out.stderr).into_owned())
    }
}

// ─────────────────────────────────────────────────────────────────────────
// tail_log — path-traversal-safe
// ─────────────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn tail_log(project: String, lines: u32) -> Result<String, String> {
    // Clamp the requested line count to a sane ceiling (T-INV02-03).
    let lines = lines.clamp(1, 10_000) as usize;

    // SECURITY (T-INV02-02): sanitise `project` to its last path component
    // only. `Path::new("../etc/passwd").file_name()` → Some("passwd"),
    // eliminating every traversal segment. Empty/dot inputs are rejected.
    let safe_project = std::path::Path::new(&project)
        .file_name()
        .and_then(|s| s.to_str())
        .ok_or_else(|| "invalid project name".to_string())?
        .to_string();
    if safe_project.is_empty() || safe_project.starts_with('.') {
        return Err("invalid project name".to_string());
    }

    let path = invisible_home()
        .join("logs")
        .join(format!("{}.log", safe_project));

    if !path.exists() {
        return Ok(String::new());
    }

    // Simple full-read tail. For the expected log sizes (a few MB) this is
    // fine; if logs ever exceed ~50MB Phase 3 can swap in a BufReader ring.
    let body = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let kept: Vec<&str> = body.lines().rev().take(lines).collect();
    Ok(kept.into_iter().rev().collect::<Vec<_>>().join("\n"))
}

// ─────────────────────────────────────────────────────────────────────────
// status
// ─────────────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn status(app: AppHandle) -> Result<StatusReport, String> {
    // Path 1 — preferred.
    if let Ok(out) = app
        .shell()
        .command("invisible-status")
        .args(["--json"])
        .output()
        .await
    {
        if out.status.success() {
            let stdout = String::from_utf8_lossy(&out.stdout);
            if let Ok(projects) = serde_json::from_str::<Vec<ProjectMeta>>(&stdout) {
                return Ok(StatusReport {
                    projects,
                    fetched_at: iso8601_now(),
                    source: "invisible-status".to_string(),
                });
            }
        }
    }

    // Path 2 — fallback: `invisible-ps` for liveness signal, then
    // synthesise via list_projects (the worktree scan).
    let ps_ok = app
        .shell()
        .command("invisible-ps")
        .args::<[&str; 0], &str>([])
        .output()
        .await
        .map(|o| o.status.success())
        .unwrap_or(false);

    // Even if invisible-ps failed, try one more synthesis from disk before
    // we surrender. The frontend gets a degraded-state indicator via `source`.
    let projects = list_projects(app).await.unwrap_or_default();
    if ps_ok || !projects.is_empty() {
        return Ok(StatusReport {
            projects,
            fetched_at: iso8601_now(),
            source: "fallback:invisible-ps".to_string(),
        });
    }

    Err("status: both invisible-status and invisible-ps failed and no worktree snapshot is available".to_string())
}
