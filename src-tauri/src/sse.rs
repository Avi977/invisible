//! Bridge: invisible-dashboard / invisible-server event stream → Tauri
//! event bus. Tries SSE first; falls back to polling /api/projects when
//! the SSE endpoint is absent (the local `invisible-dashboard` daemon
//! does NOT expose /api/stream today — verified in
//! bin/invisible-dashboard:266-315). Exponential backoff capped at 10s
//! on connection errors. Never panics.

use std::time::Duration;

use eventsource_stream::Eventsource;
use futures_util::StreamExt;
use serde_json::Value;
use tauri::{AppHandle, Emitter};
use tracing::{info, warn};

const POLL_INTERVAL: Duration = Duration::from_secs(5);
const BACKOFF_STEPS: &[Duration] = &[
    Duration::from_secs(1),
    Duration::from_secs(2),
    Duration::from_secs(5),
    Duration::from_secs(10),
];

/// Resolve the dashboard base URL.
/// Prefers `$INVISIBLE_SERVER_URL` (the VPS daemon that DOES expose
/// SSE); falls back to the local `invisible-dashboard` daemon on
/// 127.0.0.1:8765.
fn dashboard_url() -> String {
    std::env::var("INVISIBLE_SERVER_URL")
        .ok()
        .unwrap_or_else(|| "http://127.0.0.1:8765".to_string())
        .trim_end_matches('/')
        .to_string()
}

/// Resolve the bearer token. Mirror the URL choice: server token when
/// $INVISIBLE_SERVER_URL is set, dashboard token otherwise. Either may
/// be empty (the daemons run with --no-auth in dev mode); we still send
/// the header but with an empty Bearer.
fn dashboard_token() -> String {
    if std::env::var("INVISIBLE_SERVER_URL").is_ok() {
        std::env::var("INVISIBLE_SERVER_TOKEN").unwrap_or_default()
    } else {
        std::env::var("INVISIBLE_DASHBOARD_TOKEN").unwrap_or_default()
    }
}

pub async fn run_bridge(app: AppHandle) {
    let mut backoff_idx: usize = 0;
    let mut prefer_polling = false;

    loop {
        let base = dashboard_url();
        let token = dashboard_token();

        let result = if prefer_polling {
            poll_loop(&app, &base, &token).await
        } else {
            sse_loop(&app, &base, &token).await
        };

        match result {
            Ok(()) => {
                // Neither path returns cleanly under normal conditions
                // (both are infinite loops); on the off chance they do,
                // reset backoff and continue.
                backoff_idx = 0;
            }
            Err(BridgeError::SseNotSupported) => {
                if !prefer_polling {
                    info!(
                        "invisible-dashboard does not expose /api/stream (404); \
                         falling back to polling /api/projects every {}s",
                        POLL_INTERVAL.as_secs()
                    );
                }
                prefer_polling = true;
                backoff_idx = 0; // immediate switch, no backoff
                continue;
            }
            Err(BridgeError::Transient(msg)) => {
                let wait = BACKOFF_STEPS[backoff_idx.min(BACKOFF_STEPS.len() - 1)];
                warn!("dashboard bridge: {msg}; retry in {:?}", wait);
                tokio::time::sleep(wait).await;
                backoff_idx = backoff_idx.saturating_add(1).min(BACKOFF_STEPS.len() - 1);
            }
        }
    }
}

#[derive(Debug)]
enum BridgeError {
    SseNotSupported,   // 404 on /api/stream → switch to polling
    Transient(String), // any other failure → backoff + retry
}

async fn sse_loop(app: &AppHandle, base: &str, token: &str) -> Result<(), BridgeError> {
    let url = format!("{base}/api/stream");
    let client = reqwest::Client::builder()
        .build()
        .map_err(|e| BridgeError::Transient(format!("client build: {e}")))?;

    let mut req = client.get(&url).header("Accept", "text/event-stream");
    if !token.is_empty() {
        req = req.header("Authorization", format!("Bearer {token}"));
    }

    let resp = req
        .send()
        .await
        .map_err(|e| BridgeError::Transient(format!("sse connect: {e}")))?;

    if resp.status().as_u16() == 404 {
        return Err(BridgeError::SseNotSupported);
    }
    if !resp.status().is_success() {
        return Err(BridgeError::Transient(format!(
            "sse http {}",
            resp.status()
        )));
    }

    // Some daemons return 200 but with a non-SSE content-type (e.g. JSON
    // 404-equivalent error pages); treat that as "not supported".
    let ct = resp
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_ascii_lowercase())
        .unwrap_or_default();
    if !ct.contains("text/event-stream") {
        return Err(BridgeError::SseNotSupported);
    }

    let mut stream = resp.bytes_stream().eventsource();
    while let Some(event) = stream.next().await {
        match event {
            Ok(ev) => {
                let payload: Value =
                    serde_json::from_str(&ev.data).unwrap_or(Value::String(ev.data.clone()));
                let _ = app.emit(
                    "dashboard:event",
                    serde_json::json!({
                        "source":  "sse",
                        "event":   ev.event,
                        "id":      ev.id,
                        "payload": payload,
                    }),
                );
            }
            Err(e) => return Err(BridgeError::Transient(format!("sse parse: {e}"))),
        }
    }
    Err(BridgeError::Transient("sse stream ended".into()))
}

async fn poll_loop(app: &AppHandle, base: &str, token: &str) -> Result<(), BridgeError> {
    let url = format!("{base}/api/projects");
    let client = reqwest::Client::new();
    let mut last_hash: Option<u64> = None;
    loop {
        let mut req = client.get(&url);
        if !token.is_empty() {
            req = req.header("Authorization", format!("Bearer {token}"));
        }
        match req.send().await {
            Ok(resp) if resp.status().is_success() => {
                let body = resp.text().await.unwrap_or_default();
                let h = hash_str(&body);
                if Some(h) != last_hash {
                    let payload: Value =
                        serde_json::from_str(&body).unwrap_or(Value::String(body));
                    let _ = app.emit(
                        "dashboard:event",
                        serde_json::json!({
                            "source":   "poll",
                            "endpoint": "/api/projects",
                            "payload":  payload,
                        }),
                    );
                    last_hash = Some(h);
                }
            }
            Ok(resp) => {
                warn!("poll {} → {}", url, resp.status());
            }
            Err(e) => {
                warn!("poll {}: {}", url, e);
                return Err(BridgeError::Transient("poll error".into()));
            }
        }
        tokio::time::sleep(POLL_INTERVAL).await;
    }
}

fn hash_str(s: &str) -> u64 {
    use std::hash::Hasher;
    let mut h = std::collections::hash_map::DefaultHasher::new();
    h.write(s.as_bytes());
    h.finish()
}
