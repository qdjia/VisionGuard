mod runtime;

use runtime::{RuntimeManager, RuntimeSnapshot};
use std::sync::Arc;
use tauri::{Manager, WindowEvent};

#[tauri::command]
fn get_runtime_status(manager: tauri::State<'_, Arc<RuntimeManager>>) -> RuntimeSnapshot {
    manager.snapshot()
}

#[tauri::command]
fn get_runtime_endpoint(manager: tauri::State<'_, Arc<RuntimeManager>>) -> Result<String, String> {
    manager.endpoint().map_err(|error| error.to_string())
}

#[tauri::command]
async fn restart_runtime(manager: tauri::State<'_, Arc<RuntimeManager>>) -> Result<(), String> {
    let manager = Arc::clone(manager.inner());
    manager.restart().await.map_err(|error| error.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            get_runtime_status,
            get_runtime_endpoint,
            restart_runtime
        ])
        .on_window_event(|window, event| {
            if window.label() != "main" {
                return;
            }
            let should_stop = match event {
                WindowEvent::CloseRequested { api, .. } => {
                    api.prevent_close();
                    true
                }
                WindowEvent::Destroyed => true,
                _ => false,
            };
            if should_stop {
                let handle = window.app_handle().clone();
                let manager = Arc::clone(handle.state::<Arc<RuntimeManager>>().inner());
                tauri::async_runtime::spawn(async move {
                    manager.stop().await;
                    handle.exit(0);
                });
            }
        })
        .setup(|app| {
            let manager = RuntimeManager::new(app.handle().clone());
            app.manage(Arc::clone(&manager));
            tauri::async_runtime::spawn(async move {
                let _ = manager.start().await;
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building VisionGuard Desktop");
    app.run(|handle, event| {
        let app_exiting = matches!(
            event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        );
        if app_exiting {
            if let Some(manager) = handle.try_state::<Arc<RuntimeManager>>() {
                let manager = Arc::clone(manager.inner());
                tauri::async_runtime::block_on(async move { manager.stop().await });
            }
        }
    });
}
