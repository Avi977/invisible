//! Invisible Tauri shell — entrypoint and builder. Wires the 5 invoke
//! handlers, builds the system tray (Open / Hide / Quit) and installs the
//! close-to-hide window event. The SSE bridge spawn is added in Task 4.

pub mod commands;
pub mod sse;

use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Manager, WindowEvent};

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
            // ── Tray (Open / Hide / Quit) ─────────────────────────────
            let open_i = MenuItem::with_id(app, "open", "Open", true, None::<&str>)?;
            let hide_i = MenuItem::with_id(app, "hide", "Hide", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open_i, &hide_i, &quit_i])?;

            let _tray = TrayIconBuilder::with_id("main")
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Invisible")
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

            // SSE bridge spawn — added in Task 4.
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
