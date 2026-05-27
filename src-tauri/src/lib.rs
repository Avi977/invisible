//! Invisible Tauri shell — entrypoint and builder. Tray + commands + SSE
//! bridge are wired in subsequent tasks.

pub mod commands;
pub mod sse;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
