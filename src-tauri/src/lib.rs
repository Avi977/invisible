//! Invisible Tauri shell — entrypoint and builder. Wires the 5 invoke
//! handlers, builds the system tray (Open / Hide / Quit) and installs the
//! close-to-hide window event. The SSE bridge spawn is added in Task 4.

pub mod commands;
pub mod overlay;
pub mod sse;

use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::Duration;

use tauri::menu::{Menu, MenuItem};
use tauri::path::BaseDirectory;
use tauri::tray::TrayIconBuilder;
use tauri::{Manager, WindowEvent};

fn dashboard_port_open() -> bool {
    let addr: SocketAddr = match "127.0.0.1:8765".parse() {
        Ok(addr) => addr,
        Err(_) => return false,
    };
    TcpStream::connect_timeout(&addr, Duration::from_millis(250)).is_ok()
}

fn source_tree_root() -> PathBuf {
    std::env::var("INVISIBLE_REPO_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .unwrap_or_else(|| std::path::Path::new("."))
                .to_path_buf()
        })
}

fn dashboard_script(app: &tauri::App) -> Option<PathBuf> {
    if let Ok(path) = app
        .path()
        .resolve("bin/invisible-dashboard", BaseDirectory::Resource)
    {
        if path.exists() {
            return Some(path);
        }
    }
    let fallback = source_tree_root().join("bin").join("invisible-dashboard");
    fallback.exists().then_some(fallback)
}

fn spawn_local_dashboard(app: &tauri::App) {
    if dashboard_port_open() {
        return;
    }
    let Some(script) = dashboard_script(app) else {
        eprintln!("[envy] bundled invisible-dashboard script not found");
        return;
    };
    let repo_root = script
        .parent()
        .and_then(|p| p.parent())
        .map(PathBuf::from)
        .unwrap_or_else(source_tree_root);

    let mut cmd = Command::new("py");
    cmd.arg("-3")
        .arg(&script)
        .args(["--host", "127.0.0.1", "--port", "8765", "--no-auth"])
        .current_dir(repo_root)
        .env("INVISIBLE_DESKTOP", "1")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    if let Err(err) = cmd.spawn() {
        eprintln!("[envy] failed to start local dashboard: {err}");
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            commands::list_projects,
            commands::run_orchestrator,
            commands::kill_run,
            commands::tail_log,
            commands::status,
        ])
        .setup(|app| {
            spawn_local_dashboard(app);

            // ── Alt+Space overlay ─────────────────────────────────────
            // Global shortcut onto the router. Non-fatal: a shortcut the
            // OS or another app already owns must not stop Envy booting.
            if let Err(err) = overlay::install(app) {
                eprintln!("[envy] overlay shortcut unavailable: {err}");
            }

            // ── Tray (Open / Hide / Quit) ─────────────────────────────
            let open_i = MenuItem::with_id(app, "open", "Open", true, None::<&str>)?;
            let hide_i = MenuItem::with_id(app, "hide", "Hide", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open_i, &hide_i, &quit_i])?;

            let _tray = TrayIconBuilder::with_id("main")
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Envy")
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.unminimize();
                            let _ = win.set_focus();
                        }
                    }
                    "hide" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.hide();
                        }
                    }
                    "quit" => {
                        // Phase 2: clean exit. Phase 3 polish may kill
                        // running orchestrators first.
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            // ── Close-to-hide ─────────────────────────────────────────
            // Mirrors bin/invisible-app:264-271 (the pywebview
            // _on_window_closing that returns False to prevent destroy
            // and calls window.hide() instead).
            let main_window = app
                .get_webview_window("main")
                .expect("main window must exist");
            let window_for_close = main_window.clone();
            main_window.on_window_event(move |event| {
                if let WindowEvent::CloseRequested { api, .. } = event {
                    let _ = window_for_close.hide();
                    api.prevent_close();
                }
            });

            // ── SSE bridge (long-lived background task) ──────────────
            // Resolves $INVISIBLE_SERVER_URL else http://127.0.0.1:8765;
            // tries SSE first, falls back to polling /api/projects on
            // 404 (the local invisible-dashboard does not expose
            // /api/stream today). Exponential backoff capped at 10s on
            // connection errors. Never panics; loop is infinite.
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                crate::sse::run_bridge(app_handle).await;
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
