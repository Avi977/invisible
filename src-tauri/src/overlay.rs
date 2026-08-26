//! Alt+Space overlay window: global shortcut, show/hide, dismiss-on-blur.
//!
//! The overlay is declared in tauri.conf.json as a second window (label
//! "overlay") that starts hidden. It is shown and hidden for the life of the
//! process rather than created and destroyed, so the webview stays warm and
//! Alt+Space is instant -- the cost is that the UI has to reset itself on
//! each open, which is what the overlay:opened event is for.

use tauri::{AppHandle, Emitter, Manager, Runtime, WindowEvent};
use tauri_plugin_global_shortcut::{
    Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState,
};

pub const WINDOW_LABEL: &str = "overlay";

/// Alt+Space. Free on Windows, and macOS spends Cmd+Space on Spotlight
/// rather than Alt+Space, so the same chord works on both.
fn shortcut() -> Shortcut {
    Shortcut::new(Some(Modifiers::ALT), Code::Space)
}

/// Show the overlay focused, or hide it if it is already up.
pub fn toggle<R: Runtime>(app: &AppHandle<R>) {
    let Some(window) = app.get_webview_window(WINDOW_LABEL) else {
        return;
    };
    if window.is_visible().unwrap_or(false) {
        let _ = window.hide();
        return;
    }
    let _ = window.show();
    let _ = window.unminimize();
    let _ = window.set_focus();
    let _ = window.emit("overlay:opened", ());
}

/// Register the shortcut and wire the overlay window's dismiss behaviour.
pub fn install(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let hotkey = shortcut();
    app.handle().plugin(
        tauri_plugin_global_shortcut::Builder::new()
            .with_handler(move |app, triggered, event| {
                if event.state() == ShortcutState::Pressed && triggered == &hotkey {
                    toggle(app);
                }
            })
            .build(),
    )?;
    app.global_shortcut().register(shortcut())?;

    if let Some(window) = app.get_webview_window(WINDOW_LABEL) {
        let for_events = window.clone();
        window.on_window_event(move |event| match event {
            // Clicking away dismisses it, the way Spotlight does.
            WindowEvent::Focused(false) => {
                let _ = for_events.hide();
            }
            // Never destroy it -- the same window serves every Alt+Space.
            WindowEvent::CloseRequested { api, .. } => {
                let _ = for_events.hide();
                api.prevent_close();
            }
            _ => {}
        });
    }
    Ok(())
}
