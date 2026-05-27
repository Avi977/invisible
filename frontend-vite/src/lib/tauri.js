// Tauri runtime bridge — used by future pages to talk to the Rust
// backend and consume dashboard:event from the Rust-side SSE bridge.
//
// Safe to import in plain-browser dev: helpers no-op or throw with a
// clear message when window.__TAURI__ is absent. Designed to be lazy
// (dynamic imports) so the @tauri-apps/api ESM chunk is only loaded
// when actually needed inside Tauri's WKWebView.
//
// This file is ADDITIVE. No existing .jsx in frontend-vite/src/ is
// modified by Phase 2. Phase 3 (or a future M1 wiring task) imports
// from here to swap mock data for live Rust-driven state.

export const isTauri = () =>
  typeof window !== 'undefined' && '__TAURI__' in window;

/**
 * Invoke a Tauri command from the frontend. Throws if not running
 * under Tauri (callers should check isTauri() first or accept the
 * Error and fall back to a non-Tauri code path).
 */
export async function tauriInvoke(cmd, args = undefined) {
  if (!isTauri()) {
    throw new Error(`tauriInvoke('${cmd}'): not running under Tauri`);
  }
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke(cmd, args);
}

/**
 * Subscribe to dashboard:event from the Rust-side bridge.
 *
 *   const unsubscribe = await subscribeDashboard(payload => { ... });
 *   // ...later:
 *   unsubscribe();
 *
 * In a plain browser the return value is a no-op unsubscribe so
 * callers don't have to branch on isTauri() at every call-site.
 */
export async function subscribeDashboard(cb) {
  if (!isTauri()) {
    return () => {};
  }
  const { listen } = await import('@tauri-apps/api/event');
  const unlisten = await listen('dashboard:event', e => {
    try {
      cb(e.payload);
    } catch (err) {
      // Defensive: a throwing handler must not break Tauri's event loop.
      // eslint-disable-next-line no-console
      console.error('dashboard:event handler threw:', err);
    }
  });
  return unlisten;
}
