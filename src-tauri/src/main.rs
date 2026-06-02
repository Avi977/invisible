fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("invisible_tauri=info".parse().unwrap()),
        )
        .init();
    invisible_tauri::run();
}
