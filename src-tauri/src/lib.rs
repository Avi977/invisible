//! Invisible Tauri shell — entrypoint and builder. Tray + SSE bridge are
//! wired in subsequent tasks.

pub mod commands;
pub mod sse;

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
        // Tray and SSE bridge added in Tasks 3 + 4 via .setup(...).
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
