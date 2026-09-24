mod models;
mod runtime;

use models::{ModelBundleInfo, ModelInstallResult, ModelInstallStatus, ModelInstaller};
use models::{RuntimeInstallResult, RuntimeInstallStatus, RuntimeInstaller, RuntimePackageInfo};
use runtime::{AdvancedAIManager, AdvancedAISnapshot, RuntimeManager, RuntimeSnapshot};
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

#[tauri::command]
async fn get_advanced_ai_status(
    manager: tauri::State<'_, Arc<AdvancedAIManager>>,
) -> Result<AdvancedAISnapshot, String> {
    Ok(manager.refresh().await)
}

#[tauri::command]
async fn start_advanced_ai(
    manager: tauri::State<'_, Arc<AdvancedAIManager>>,
) -> Result<(), String> {
    manager.start().await
}

#[tauri::command]
async fn restart_advanced_ai(
    manager: tauri::State<'_, Arc<AdvancedAIManager>>,
) -> Result<(), String> {
    manager.restart().await
}

#[tauri::command]
async fn stop_advanced_ai(manager: tauri::State<'_, Arc<AdvancedAIManager>>) -> Result<(), String> {
    manager.stop().await;
    Ok(())
}

#[tauri::command]
fn get_model_install_status(
    installer: tauri::State<'_, Arc<ModelInstaller>>,
) -> ModelInstallStatus {
    installer.status()
}

#[tauri::command]
async fn inspect_model_bundle(
    source: String,
    installer: tauri::State<'_, Arc<ModelInstaller>>,
) -> Result<ModelBundleInfo, String> {
    installer.inspect(source).await
}

#[tauri::command]
async fn install_model_bundle(
    source: String,
    installer: tauri::State<'_, Arc<ModelInstaller>>,
    manager: tauri::State<'_, Arc<RuntimeManager>>,
) -> Result<ModelInstallResult, String> {
    manager.stop().await;
    installer.install(source).await
}

#[tauri::command]
fn get_runtime_install_status(
    installer: tauri::State<'_, Arc<RuntimeInstaller>>,
) -> RuntimeInstallStatus {
    installer.status()
}

#[tauri::command]
async fn inspect_runtime_bundle(
    source: String,
    installer: tauri::State<'_, Arc<RuntimeInstaller>>,
) -> Result<RuntimePackageInfo, String> {
    installer.inspect(source).await
}

#[tauri::command]
async fn install_runtime_bundle(
    source: String,
    installer: tauri::State<'_, Arc<RuntimeInstaller>>,
    manager: tauri::State<'_, Arc<RuntimeManager>>,
) -> Result<RuntimeInstallResult, String> {
    manager.stop().await;
    installer.install(source).await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_http::init())
        .invoke_handler(tauri::generate_handler![
            get_runtime_status,
            get_runtime_endpoint,
            restart_runtime,
            get_advanced_ai_status,
            start_advanced_ai,
            restart_advanced_ai,
            stop_advanced_ai,
            get_model_install_status,
            inspect_model_bundle,
            install_model_bundle,
            get_runtime_install_status,
            inspect_runtime_bundle,
            install_runtime_bundle
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
                let advanced = Arc::clone(handle.state::<Arc<AdvancedAIManager>>().inner());
                tauri::async_runtime::spawn(async move {
                    advanced.stop().await;
                    manager.stop().await;
                    handle.exit(0);
                });
            }
        })
        .setup(|app| {
            let manager = RuntimeManager::new(app.handle().clone());
            let advanced = AdvancedAIManager::new(app.handle().clone(), Arc::clone(&manager));
            let installer = ModelInstaller::new(app.handle().clone());
            let runtime_installer = RuntimeInstaller::new(app.handle().clone());
            app.manage(Arc::clone(&manager));
            app.manage(Arc::clone(&advanced));
            app.manage(installer);
            app.manage(runtime_installer);
            tauri::async_runtime::spawn(async move {
                if manager.start().await.is_ok() {
                    let _ = advanced.start().await;
                }
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
                if let Some(advanced) = handle.try_state::<Arc<AdvancedAIManager>>() {
                    let advanced = Arc::clone(advanced.inner());
                    tauri::async_runtime::block_on(async move { advanced.stop().await });
                }
                let manager = Arc::clone(manager.inner());
                tauri::async_runtime::block_on(async move { manager.stop().await });
            }
        }
    });
}
