use fs2::available_space;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashSet,
    fs::{self, File},
    io::{self, Read, Seek, SeekFrom, Write},
    path::{Component, Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, RwLock,
    },
};
use tauri::{AppHandle, Manager};
use tokio::sync::Mutex as AsyncMutex;
use uuid::Uuid;
use zip::ZipArchive;

const BUFFER_SIZE: usize = 1024 * 1024;
const SAFETY_MARGIN_PERCENT: u64 = 10;
const MINIMUM_SAFETY_BYTES: u64 = 512 * 1024 * 1024;

#[derive(Debug, Clone, Deserialize)]
struct PackagePart {
    index: u32,
    file: String,
    size_bytes: u64,
    sha256: String,
}

#[derive(Debug, Clone, Deserialize)]
struct PackageComponent {
    version: String,
    archive_format: String,
    archive_size_bytes: u64,
    unpacked_size_bytes: u64,
    archive_sha256: String,
    parts: Vec<PackagePart>,
}

#[derive(Debug, Clone, Deserialize)]
struct PackageComponents {
    vlm_runtime: PackageComponent,
    vlm_models: PackageComponent,
}

#[derive(Debug, Clone, Deserialize)]
struct AdvancedAIManifest {
    schema_version: u32,
    component: String,
    package_version: String,
    platform: String,
    architecture: String,
    components: PackageComponents,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActiveComponentRegistry {
    pub schema_version: u32,
    pub vlm_runtime_version: String,
    pub vlm_runtime_directory: String,
    pub vlm_models_version: String,
    pub vlm_models_directory: String,
}

#[derive(Debug, Clone)]
pub struct ManagedVLMPaths {
    pub python_executable: PathBuf,
    pub models_directory: PathBuf,
    pub model_revision: String,
    pub model_bundle_version: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct AdvancedAIPackageInfo {
    pub package_version: String,
    pub runtime_version: String,
    pub model_version: String,
    pub source_bytes: u64,
    pub installed_bytes: u64,
    pub required_free_bytes: u64,
    pub available_free_bytes: u64,
    pub disk_space_sufficient: bool,
    pub part_count: usize,
    pub validation_status: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct AdvancedAIInstallStatus {
    pub state: String,
    pub package_version: Option<String>,
    pub bytes_completed: u64,
    pub bytes_total: u64,
    pub runtime_version: Option<String>,
    pub model_version: Option<String>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
}

impl Default for AdvancedAIInstallStatus {
    fn default() -> Self {
        Self {
            state: "NotInstalled".into(),
            package_version: None,
            bytes_completed: 0,
            bytes_total: 0,
            runtime_version: None,
            model_version: None,
            error_code: None,
            error_message: None,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct AdvancedAIInstallResult {
    pub package_version: String,
    pub runtime_version: String,
    pub model_version: String,
    pub validation_status: String,
}

#[derive(Debug, Serialize)]
struct InstallError {
    code: String,
    message: String,
}

impl InstallError {
    fn new(code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
        }
    }

    fn json(&self) -> String {
        serde_json::to_string(self).unwrap_or_else(|_| self.message.clone())
    }
}

type InstallResult<T> = Result<T, InstallError>;

pub struct AdvancedAIInstaller {
    app: AppHandle,
    operation: AsyncMutex<()>,
    status: Arc<RwLock<AdvancedAIInstallStatus>>,
    cancelled: Arc<AtomicBool>,
}

impl AdvancedAIInstaller {
    pub fn new(app: AppHandle) -> Arc<Self> {
        Arc::new(Self {
            app,
            operation: AsyncMutex::new(()),
            status: Arc::new(RwLock::new(AdvancedAIInstallStatus::default())),
            cancelled: Arc::new(AtomicBool::new(false)),
        })
    }

    pub fn status(&self) -> AdvancedAIInstallStatus {
        self.status
            .read()
            .expect("advanced AI install status poisoned")
            .clone()
    }

    pub async fn inspect(&self, manifest: String) -> Result<AdvancedAIPackageInfo, String> {
        let data = self
            .app
            .path()
            .app_local_data_dir()
            .map_err(|e| e.to_string())?;
        tauri::async_runtime::spawn_blocking(move || {
            inspect_package(&PathBuf::from(manifest), &data)
        })
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.json())
    }

    pub async fn inspect_online(&self) -> Result<AdvancedAIPackageInfo, String> {
        let resources = self.app.path().resource_dir().map_err(|e| e.to_string())?;
        let manifest_path = resources.join("bootstrap/advanced-ai-bootstrap-manifest.json");
        let data = self
            .app
            .path()
            .app_local_data_dir()
            .map_err(|e| e.to_string())?;
        tauri::async_runtime::spawn_blocking(move || inspect_online_manifest(&manifest_path, &data))
            .await
            .map_err(|e| e.to_string())?
            .map_err(|e| e.json())
    }

    pub async fn install_online(&self) -> Result<AdvancedAIInstallResult, String> {
        let _guard = self.operation.lock().await;
        self.cancelled.store(false, Ordering::SeqCst);
        let resources = self.app.path().resource_dir().map_err(|e| e.to_string())?;
        let data = self
            .app
            .path()
            .app_local_data_dir()
            .map_err(|e| e.to_string())?;
        let status = Arc::clone(&self.status);
        let cancelled = Arc::clone(&self.cancelled);
        let result = tauri::async_runtime::spawn_blocking(move || {
            install_online_bootstrap(&resources, &data, &status, &cancelled)
        })
        .await
        .map_err(|e| e.to_string())?;
        match result {
            Ok(value) => Ok(value),
            Err(error) => {
                let state = if error.code == "ADVANCED_AI_INSTALL_CANCELLED" {
                    "Cancelled"
                } else {
                    "Failed"
                };
                let current = self.status();
                update_status(
                    &self.status,
                    state,
                    None,
                    current.bytes_completed,
                    current.bytes_total,
                    Some((error.code.clone(), error.message.clone())),
                );
                Err(error.json())
            }
        }
    }

    pub async fn install(&self, manifest: String) -> Result<AdvancedAIInstallResult, String> {
        let _guard = self.operation.lock().await;
        self.cancelled.store(false, Ordering::SeqCst);
        update_status(&self.status, "validating", None, 0, 0, None);
        let data = self
            .app
            .path()
            .app_local_data_dir()
            .map_err(|e| e.to_string())?;
        let status = Arc::clone(&self.status);
        let cancelled = Arc::clone(&self.cancelled);
        let result = tauri::async_runtime::spawn_blocking(move || {
            install_package(&PathBuf::from(manifest), &data, &status, &cancelled)
        })
        .await
        .map_err(|e| e.to_string())?;
        match result {
            Ok(value) => {
                let total = self.status().bytes_total;
                update_status(&self.status, "ready", Some(&value), total, total, None);
                Ok(value)
            }
            Err(error) => {
                let state = if error.code == "ADVANCED_AI_INSTALL_CANCELLED" {
                    "cancelled"
                } else {
                    "failed"
                };
                let current = self.status();
                update_status(
                    &self.status,
                    state,
                    None,
                    current.bytes_completed,
                    current.bytes_total,
                    Some((error.code.to_string(), error.message.clone())),
                );
                Err(error.json())
            }
        }
    }

    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::SeqCst);
    }

    pub async fn uninstall(&self) -> Result<(), String> {
        let _guard = self.operation.lock().await;
        update_status(&self.status, "Removing", None, 0, 0, None);
        let data = self
            .app
            .path()
            .app_local_data_dir()
            .map_err(|e| e.to_string())?;
        let result = tauri::async_runtime::spawn_blocking(move || uninstall_active(&data))
            .await
            .map_err(|e| e.to_string())?;
        match result {
            Ok(()) => {
                *self.status.write().expect("advanced AI status poisoned") =
                    AdvancedAIInstallStatus::default();
                Ok(())
            }
            Err(error) => {
                update_status(
                    &self.status,
                    "Failed",
                    None,
                    0,
                    0,
                    Some((error.code.clone(), error.message.clone())),
                );
                Err(error.json())
            }
        }
    }

    pub async fn rollback(&self) -> Result<(), String> {
        let _guard = self.operation.lock().await;
        update_status(&self.status, "Updating", None, 0, 0, None);
        let data = self
            .app
            .path()
            .app_local_data_dir()
            .map_err(|e| e.to_string())?;
        let result = tauri::async_runtime::spawn_blocking(move || rollback_active(&data))
            .await
            .map_err(|e| e.to_string())?;
        match result {
            Ok(()) => {
                update_status(&self.status, "Ready", None, 0, 0, None);
                Ok(())
            }
            Err(error) => {
                update_status(
                    &self.status,
                    "Failed",
                    None,
                    0,
                    0,
                    Some((error.code.clone(), error.message.clone())),
                );
                Err(error.json())
            }
        }
    }
}

fn inspect_online_manifest(
    manifest_path: &Path,
    data_dir: &Path,
) -> InstallResult<AdvancedAIPackageInfo> {
    let payload: serde_json::Value = serde_json::from_slice(
        &fs::read(manifest_path).map_err(io_error("ADVANCED_AI_BOOTSTRAP_MANIFEST_MISSING"))?,
    )
    .map_err(|e| InstallError::new("ADVANCED_AI_BOOTSTRAP_MANIFEST_INVALID", e.to_string()))?;
    if payload.get("schema_version").and_then(|v| v.as_u64()) != Some(1)
        || payload.get("distribution_mode").and_then(|v| v.as_str()) != Some("online-bootstrap")
    {
        return Err(InstallError::new(
            "ADVANCED_AI_BOOTSTRAP_MANIFEST_INVALID",
            "Unsupported online bootstrap manifest.",
        ));
    }
    let estimates = payload.get("estimates").ok_or_else(|| {
        InstallError::new(
            "ADVANCED_AI_BOOTSTRAP_MANIFEST_INVALID",
            "Size estimates are missing.",
        )
    })?;
    let download = estimates
        .get("download_bytes")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let installed = estimates
        .get("installed_bytes")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let temporary = estimates
        .get("temporary_bytes")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let margin = estimates
        .get("safety_margin_bytes")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    fs::create_dir_all(data_dir).map_err(io_error("ADVANCED_AI_INSPECT_FAILED"))?;
    let available = available_space(data_dir).map_err(io_error("ADVANCED_AI_INSPECT_FAILED"))?;
    let required = installed.saturating_add(temporary).saturating_add(margin);
    Ok(AdvancedAIPackageInfo {
        package_version: payload["environment_version"]
            .as_str()
            .unwrap_or("unknown")
            .into(),
        runtime_version: format!(
            "Python {}",
            payload["python"]["version"].as_str().unwrap_or("unknown")
        ),
        model_version: payload["model"]["bundle_version"]
            .as_str()
            .unwrap_or("unknown")
            .into(),
        source_bytes: download,
        installed_bytes: installed,
        required_free_bytes: required,
        available_free_bytes: available,
        disk_space_sufficient: available >= required,
        part_count: 0,
        validation_status: "official_sources_pinned".into(),
    })
}

fn install_online_bootstrap(
    resources: &Path,
    data_dir: &Path,
    status: &Arc<RwLock<AdvancedAIInstallStatus>>,
    cancelled: &Arc<AtomicBool>,
) -> InstallResult<AdvancedAIInstallResult> {
    let manifest = resources.join("bootstrap/advanced-ai-bootstrap-manifest.json");
    let info = inspect_online_manifest(&manifest, data_dir)?;
    if !info.disk_space_sufficient {
        return Err(InstallError::new(
            "ADVANCED_AI_DISK_SPACE_INSUFFICIENT",
            "Not enough disk space for the managed Advanced AI environment.",
        ));
    }
    let wheel_root = resources.join("bootstrap/packages");
    let wheel = find_wheel(&wheel_root).ok_or_else(|| {
        InstallError::new(
            "BOOTSTRAP_PACKAGE_MISSING",
            "Bundled VisionGuard VLM wheel is missing.",
        )
    })?;
    let core = crate::models::active_runtime_executable(data_dir)
        .or_else(|| {
            let candidate = resources.join("components/core-runtime/visionguard-core-runtime.exe");
            candidate.is_file().then_some(candidate)
        })
        .ok_or_else(|| {
            InstallError::new("RUNTIME_COMPONENT_MISSING", "Core Runtime is missing.")
        })?;
    let status_file = data_dir.join("advanced-ai/bootstrap-status.json");
    let cancel_file = data_dir.join("advanced-ai/bootstrap.cancel");
    let _ = fs::remove_file(&cancel_file);
    let prompts = resources.join("bootstrap/prompts/vlm");
    if !prompts.is_dir() {
        return Err(InstallError::new(
            "BOOTSTRAP_PACKAGE_MISSING",
            "Bundled VLM prompt resources are missing.",
        ));
    }
    update_status(status, "Preparing", None, 0, info.source_bytes, None);
    let mut command = Command::new(core);
    command
        .arg("bootstrap-advanced-ai")
        .args(["--manifest"])
        .arg(&manifest)
        .args(["--data-dir"])
        .arg(data_dir)
        .args(["--status-file"])
        .arg(&status_file)
        .args(["--wheel"])
        .arg(wheel)
        .args(["--prompts"])
        .arg(prompts)
        .args(["--cancel-file"])
        .arg(&cancel_file)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    let mut child = command
        .spawn()
        .map_err(|e| InstallError::new("ADVANCED_AI_BOOTSTRAP_FAILED", e.to_string()))?;
    let mut cancel_requested_at: Option<std::time::Instant> = None;
    loop {
        if cancelled.load(Ordering::SeqCst) {
            if cancel_requested_at.is_none() {
                fs::write(&cancel_file, b"cancel")
                    .map_err(io_error("ADVANCED_AI_INSTALL_CANCELLED"))?;
                cancel_requested_at = Some(std::time::Instant::now());
            } else if cancel_requested_at.is_some_and(|value| value.elapsed().as_secs() >= 15) {
                let _ = child.kill();
            }
        }
        if let Ok(payload) = fs::read(&status_file) {
            if let Ok(value) = serde_json::from_slice::<serde_json::Value>(&payload) {
                if let Some(state) = value.get("state").and_then(|item| item.as_str()) {
                    let completed = value
                        .get("bytes_completed")
                        .and_then(|item| item.as_u64())
                        .unwrap_or(0);
                    let total = value
                        .get("bytes_total")
                        .and_then(|item| item.as_u64())
                        .unwrap_or(info.source_bytes);
                    update_status(status, state, None, completed, total, None);
                }
            }
        }
        if let Some(exit) = child
            .try_wait()
            .map_err(io_error("ADVANCED_AI_BOOTSTRAP_FAILED"))?
        {
            if !exit.success() {
                if cancelled.load(Ordering::SeqCst) {
                    let _ = fs::remove_file(&cancel_file);
                    return Err(InstallError::new(
                        "ADVANCED_AI_INSTALL_CANCELLED",
                        "Installation cancelled safely.",
                    ));
                }
                let bootstrap_error = fs::read(&status_file)
                    .ok()
                    .and_then(|payload| serde_json::from_slice::<serde_json::Value>(&payload).ok())
                    .and_then(|payload| {
                        let code = payload.get("error_code")?.as_str()?.to_string();
                        let message = payload.get("error_message")?.as_str()?.to_string();
                        Some((code, message))
                    })
                    .unwrap_or_else(|| {
                        (
                            "ADVANCED_AI_BOOTSTRAP_FAILED".into(),
                            format!("Bootstrap process exited with {exit}."),
                        )
                    });
                return Err(InstallError::new(bootstrap_error.0, bootstrap_error.1));
            }
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(250));
    }
    let _ = fs::remove_file(cancel_file);
    update_status(
        status,
        "Ready",
        None,
        info.source_bytes,
        info.source_bytes,
        None,
    );
    Ok(AdvancedAIInstallResult {
        package_version: info.package_version,
        runtime_version: info.runtime_version,
        model_version: info.model_version,
        validation_status: "ready".into(),
    })
}

fn find_wheel(root: &Path) -> Option<PathBuf> {
    let matches = fs::read_dir(root)
        .ok()?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.is_file()
                && path.extension().is_some_and(|ext| ext == "whl")
                && path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .is_some_and(|name| name.starts_with("visionguard_moderation-"))
        })
        .collect::<Vec<_>>();
    (matches.len() == 1).then(|| matches[0].clone())
}

pub fn active_vlm_paths(data_dir: &Path) -> Option<(PathBuf, PathBuf, ActiveComponentRegistry)> {
    let root = data_dir.join("components");
    let registry: ActiveComponentRegistry =
        serde_json::from_slice(&fs::read(root.join("components.json")).ok()?).ok()?;
    if registry.schema_version != 1
        || !safe_relative(&registry.vlm_runtime_directory)
        || !safe_relative(&registry.vlm_models_directory)
    {
        return None;
    }
    let runtime = root.join(&registry.vlm_runtime_directory);
    let models = root.join(&registry.vlm_models_directory);
    (runtime.is_dir() && models.is_dir()).then_some((runtime, models, registry))
}

pub fn active_managed_vlm_paths(data_dir: &Path) -> Option<ManagedVLMPaths> {
    let registry: serde_json::Value =
        serde_json::from_slice(&fs::read(data_dir.join("components/components.json")).ok()?)
            .ok()?;
    if registry.get("schema_version")?.as_u64()? != 2
        || registry.get("distribution_mode")?.as_str()? != "online_bootstrap"
    {
        return None;
    }
    let python_relative = registry.get("python_executable")?.as_str()?;
    let models_relative = registry.get("vlm_models_directory")?.as_str()?;
    if !safe_relative(python_relative)
        || !safe_relative(models_relative)
        || !Path::new(python_relative).starts_with("advanced-ai/envs")
        || !Path::new(models_relative).starts_with("advanced-ai/models")
    {
        return None;
    }
    let python_executable = data_dir.join(python_relative);
    let models_directory = data_dir.join(models_relative);
    let model_revision = registry.get("model_revision")?.as_str()?.to_string();
    let model_bundle_version = registry.get("vlm_models_version")?.as_str()?.to_string();
    if model_revision.len() != 40
        || !model_revision.bytes().all(|byte| byte.is_ascii_hexdigit())
        || !safe_version(&model_bundle_version)
    {
        return None;
    }
    (python_executable.is_file() && models_directory.is_dir()).then(|| ManagedVLMPaths {
        python_executable,
        models_directory,
        model_revision,
        model_bundle_version,
    })
}

fn inspect_package(manifest_path: &Path, data_dir: &Path) -> InstallResult<AdvancedAIPackageInfo> {
    let manifest = load_manifest(manifest_path)?;
    validate_manifest(manifest_path, &manifest)?;
    let components = [
        &manifest.components.vlm_runtime,
        &manifest.components.vlm_models,
    ];
    let active = active_vlm_paths(data_dir).map(|(_, _, registry)| registry);
    let runtime_changed = active
        .as_ref()
        .is_none_or(|value| value.vlm_runtime_version != manifest.components.vlm_runtime.version);
    let models_changed = active
        .as_ref()
        .is_none_or(|value| value.vlm_models_version != manifest.components.vlm_models.version);
    let selected = components
        .iter()
        .enumerate()
        .filter(|(index, _)| (*index == 0 && runtime_changed) || (*index == 1 && models_changed))
        .map(|(_, component)| *component)
        .collect::<Vec<_>>();
    let source_bytes = selected.iter().map(|item| item.archive_size_bytes).sum();
    let installed_bytes: u64 = selected.iter().map(|item| item.unpacked_size_bytes).sum();
    let margin = (installed_bytes * SAFETY_MARGIN_PERCENT / 100).max(MINIMUM_SAFETY_BYTES);
    let required_free_bytes = installed_bytes.saturating_add(margin);
    let components_root = data_dir.join("components");
    fs::create_dir_all(&components_root).map_err(io_error("ADVANCED_AI_INSPECT_FAILED"))?;
    let available_free_bytes =
        available_space(&components_root).map_err(io_error("ADVANCED_AI_INSPECT_FAILED"))?;
    Ok(AdvancedAIPackageInfo {
        package_version: manifest.package_version,
        runtime_version: manifest.components.vlm_runtime.version.clone(),
        model_version: manifest.components.vlm_models.version.clone(),
        source_bytes,
        installed_bytes,
        required_free_bytes,
        available_free_bytes,
        disk_space_sufficient: available_free_bytes >= required_free_bytes,
        part_count: selected.iter().map(|item| item.parts.len()).sum(),
        validation_status: "manifest_valid".into(),
    })
}

fn install_package(
    manifest_path: &Path,
    data_dir: &Path,
    status: &Arc<RwLock<AdvancedAIInstallStatus>>,
    cancelled: &Arc<AtomicBool>,
) -> InstallResult<AdvancedAIInstallResult> {
    let info = inspect_package(manifest_path, data_dir)?;
    if !info.disk_space_sufficient {
        return Err(InstallError::new(
            "ADVANCED_AI_DISK_SPACE_INSUFFICIENT",
            format!(
                "Advanced AI requires {} bytes free; {} bytes are available.",
                info.required_free_bytes, info.available_free_bytes
            ),
        ));
    }
    let manifest = load_manifest(manifest_path)?;
    let active = active_vlm_paths(data_dir);
    let runtime_changed = active.as_ref().is_none_or(|(_, _, registry)| {
        registry.vlm_runtime_version != manifest.components.vlm_runtime.version
    });
    let models_changed = active.as_ref().is_none_or(|(_, _, registry)| {
        registry.vlm_models_version != manifest.components.vlm_models.version
    });
    if !runtime_changed && !models_changed {
        return Ok(AdvancedAIInstallResult {
            package_version: manifest.package_version,
            runtime_version: manifest.components.vlm_runtime.version,
            model_version: manifest.components.vlm_models.version,
            validation_status: "ready_reused".into(),
        });
    }
    let source_root = manifest_path.parent().unwrap_or_else(|| Path::new("."));
    let verification_bytes = info.source_bytes;
    let total = verification_bytes.saturating_add(info.installed_bytes);
    update_status(status, "validating", None, 0, total, None);
    let mut completed = 0_u64;
    if runtime_changed {
        verify_parts(
            source_root,
            &manifest.components.vlm_runtime,
            status,
            cancelled,
            &mut completed,
            total,
        )?;
    }
    if models_changed {
        verify_parts(
            source_root,
            &manifest.components.vlm_models,
            status,
            cancelled,
            &mut completed,
            total,
        )?;
    }

    let root = data_dir.join("components");
    let id = Uuid::new_v4().simple().to_string();
    let staging = root.join(format!(".staging-{id}"));
    let staged_runtime = staging.join("vlm-runtime");
    let staged_models = staging.join("vlm-models");
    fs::create_dir_all(&staged_runtime).map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
    fs::create_dir_all(&staged_models).map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
    let result = (|| {
        update_status(status, "installing", None, completed, total, None);
        if runtime_changed {
            extract_component(
                source_root,
                &manifest.components.vlm_runtime,
                &staged_runtime,
                status,
                cancelled,
                &mut completed,
                total,
            )?;
            validate_runtime_payload(&staged_runtime)?;
        }
        if models_changed {
            extract_component(
                source_root,
                &manifest.components.vlm_models,
                &staged_models,
                status,
                cancelled,
                &mut completed,
                total,
            )?;
            validate_model_payload(&staged_models)?;
        }
        check_cancelled(cancelled)?;
        update_status(status, "activating", None, completed, total, None);
        activate_components(
            &root,
            &staged_runtime,
            &staged_models,
            &manifest,
            &id,
            runtime_changed,
            models_changed,
        )?;
        Ok(AdvancedAIInstallResult {
            package_version: manifest.package_version.clone(),
            runtime_version: manifest.components.vlm_runtime.version.clone(),
            model_version: manifest.components.vlm_models.version.clone(),
            validation_status: "ready".into(),
        })
    })();
    if staging.exists() {
        let _ = fs::remove_dir_all(&staging);
    }
    result
}

fn load_manifest(path: &Path) -> InstallResult<AdvancedAIManifest> {
    if path.file_name().and_then(|name| name.to_str()) != Some("advanced-ai-manifest.json") {
        return Err(InstallError::new(
            "ADVANCED_AI_MANIFEST_INVALID",
            "Select advanced-ai-manifest.json.",
        ));
    }
    serde_json::from_slice(&fs::read(path).map_err(io_error("ADVANCED_AI_MANIFEST_INVALID"))?)
        .map_err(|e| InstallError::new("ADVANCED_AI_MANIFEST_INVALID", e.to_string()))
}

fn validate_manifest(path: &Path, manifest: &AdvancedAIManifest) -> InstallResult<()> {
    if manifest.schema_version != 1
        || manifest.component != "advanced_ai"
        || !manifest.platform.eq_ignore_ascii_case("windows")
        || !manifest.architecture.eq_ignore_ascii_case("x86_64")
        || !safe_version(&manifest.package_version)
    {
        return Err(InstallError::new(
            "ADVANCED_AI_MANIFEST_INCOMPATIBLE",
            "Advanced AI package is not compatible with this Windows build.",
        ));
    }
    let root = path.parent().unwrap_or_else(|| Path::new("."));
    for component in [
        &manifest.components.vlm_runtime,
        &manifest.components.vlm_models,
    ] {
        validate_component(root, component)?;
    }
    Ok(())
}

fn validate_component(root: &Path, component: &PackageComponent) -> InstallResult<()> {
    let mut names = HashSet::new();
    if component.archive_format != "zip"
        || !safe_version(&component.version)
        || !valid_hash(&component.archive_sha256)
        || component.parts.is_empty()
        || component.unpacked_size_bytes == 0
    {
        return Err(InstallError::new(
            "ADVANCED_AI_MANIFEST_INVALID",
            "Component metadata is invalid.",
        ));
    }
    let mut archive_size = 0_u64;
    for (offset, part) in component.parts.iter().enumerate() {
        if part.index != (offset + 1) as u32
            || !safe_file_name(&part.file)
            || !valid_hash(&part.sha256)
            || part.size_bytes == 0
            || !names.insert(&part.file)
        {
            return Err(InstallError::new(
                "ADVANCED_AI_PART_ORDER_INVALID",
                "Parts must be unique, consecutive, and safely named.",
            ));
        }
        let target = root.join(&part.file);
        let actual = target
            .metadata()
            .map_err(|_| InstallError::new("ADVANCED_AI_PART_MISSING", &part.file))?;
        if !actual.is_file() || actual.len() != part.size_bytes {
            return Err(InstallError::new(
                "ADVANCED_AI_PART_SIZE_MISMATCH",
                &part.file,
            ));
        }
        archive_size = archive_size.saturating_add(part.size_bytes);
    }
    if archive_size != component.archive_size_bytes {
        return Err(InstallError::new(
            "ADVANCED_AI_MANIFEST_INVALID",
            "Component archive size does not equal the sum of its parts.",
        ));
    }
    Ok(())
}

fn verify_parts(
    root: &Path,
    component: &PackageComponent,
    status: &Arc<RwLock<AdvancedAIInstallStatus>>,
    cancelled: &Arc<AtomicBool>,
    completed: &mut u64,
    total: u64,
) -> InstallResult<()> {
    let mut archive_digest = Sha256::new();
    for part in &component.parts {
        check_cancelled(cancelled)?;
        let mut input =
            File::open(root.join(&part.file)).map_err(io_error("ADVANCED_AI_PART_MISSING"))?;
        let mut part_digest = Sha256::new();
        let mut buffer = vec![0_u8; BUFFER_SIZE];
        loop {
            check_cancelled(cancelled)?;
            let count = input
                .read(&mut buffer)
                .map_err(io_error("ADVANCED_AI_PART_READ_FAILED"))?;
            if count == 0 {
                break;
            }
            part_digest.update(&buffer[..count]);
            archive_digest.update(&buffer[..count]);
            *completed = completed.saturating_add(count as u64);
            update_status(status, "validating", None, *completed, total, None);
        }
        if format!("{:x}", part_digest.finalize()) != part.sha256 {
            return Err(InstallError::new(
                "ADVANCED_AI_PART_HASH_MISMATCH",
                &part.file,
            ));
        }
    }
    if format!("{:x}", archive_digest.finalize()) != component.archive_sha256 {
        return Err(InstallError::new(
            "ADVANCED_AI_ARCHIVE_HASH_MISMATCH",
            "Combined component archive SHA-256 does not match the manifest.",
        ));
    }
    Ok(())
}

struct PartReader {
    parts: Vec<(File, u64, u64)>,
    length: u64,
    position: u64,
}

impl PartReader {
    fn open(root: &Path, component: &PackageComponent) -> InstallResult<Self> {
        let mut start = 0_u64;
        let mut parts = Vec::new();
        for part in &component.parts {
            parts.push((
                File::open(root.join(&part.file)).map_err(io_error("ADVANCED_AI_PART_MISSING"))?,
                start,
                part.size_bytes,
            ));
            start += part.size_bytes;
        }
        Ok(Self {
            parts,
            length: start,
            position: 0,
        })
    }
}

impl Read for PartReader {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        if self.position >= self.length || buffer.is_empty() {
            return Ok(0);
        }
        let index = self
            .parts
            .iter()
            .position(|(_, start, length)| {
                self.position >= *start && self.position < start + length
            })
            .ok_or_else(|| io::Error::new(io::ErrorKind::UnexpectedEof, "multipart position"))?;
        let (file, start, length) = &mut self.parts[index];
        let local = self.position - *start;
        file.seek(SeekFrom::Start(local))?;
        let limit = buffer.len().min((*length - local) as usize);
        let count = file.read(&mut buffer[..limit])?;
        self.position += count as u64;
        Ok(count)
    }
}

impl Seek for PartReader {
    fn seek(&mut self, position: SeekFrom) -> io::Result<u64> {
        let next = match position {
            SeekFrom::Start(value) => value as i128,
            SeekFrom::End(value) => self.length as i128 + value as i128,
            SeekFrom::Current(value) => self.position as i128 + value as i128,
        };
        if next < 0 || next > self.length as i128 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "multipart seek",
            ));
        }
        self.position = next as u64;
        Ok(self.position)
    }
}

fn extract_component(
    source_root: &Path,
    component: &PackageComponent,
    destination: &Path,
    status: &Arc<RwLock<AdvancedAIInstallStatus>>,
    cancelled: &Arc<AtomicBool>,
    completed: &mut u64,
    total: u64,
) -> InstallResult<()> {
    let reader = PartReader::open(source_root, component)?;
    let mut archive = ZipArchive::new(reader)
        .map_err(|e| InstallError::new("ADVANCED_AI_ARCHIVE_INVALID", e.to_string()))?;
    for index in 0..archive.len() {
        check_cancelled(cancelled)?;
        let mut item = archive
            .by_index(index)
            .map_err(|e| InstallError::new("ADVANCED_AI_ARCHIVE_INVALID", e.to_string()))?;
        if item.enclosed_name().is_none()
            || item
                .unix_mode()
                .is_some_and(|mode| mode & 0o170000 == 0o120000)
        {
            return Err(InstallError::new(
                "ADVANCED_AI_ARCHIVE_UNSAFE",
                "Archive contains an unsafe path or symbolic link.",
            ));
        }
        let path = item
            .enclosed_name()
            .expect("checked enclosed name")
            .to_path_buf();
        let target = destination.join(path);
        if item.is_dir() {
            fs::create_dir_all(&target).map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
            continue;
        }
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent).map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
        }
        let mut output = File::create(&target).map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
        let mut buffer = vec![0_u8; BUFFER_SIZE];
        loop {
            check_cancelled(cancelled)?;
            let count = item
                .read(&mut buffer)
                .map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
            if count == 0 {
                break;
            }
            output
                .write_all(&buffer[..count])
                .map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
            *completed = completed.saturating_add(count as u64);
            update_status(status, "installing", None, *completed, total, None);
        }
        output
            .sync_all()
            .map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
    }
    Ok(())
}

fn locate_single(root: &Path, marker: &str) -> InstallResult<PathBuf> {
    if root.join(marker).exists() {
        return Ok(root.to_path_buf());
    }
    let candidates: Vec<_> = fs::read_dir(root)
        .map_err(io_error("ADVANCED_AI_COMPONENT_INVALID"))?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.is_dir() && path.join(marker).exists())
        .collect();
    if candidates.len() == 1 {
        Ok(candidates[0].clone())
    } else {
        Err(InstallError::new(
            "ADVANCED_AI_COMPONENT_INVALID",
            format!("Component must contain exactly one {marker}."),
        ))
    }
}

fn validate_runtime_payload(root: &Path) -> InstallResult<PathBuf> {
    let located = locate_single(root, "runtime-manifest.json")?;
    if !located.join("visionguard-vlm-runtime.exe").is_file() {
        return Err(InstallError::new(
            "ADVANCED_AI_RUNTIME_INVALID",
            "VLM runtime executable is missing.",
        ));
    }
    let manifest: serde_json::Value = serde_json::from_slice(
        &fs::read(located.join("runtime-manifest.json"))
            .map_err(io_error("ADVANCED_AI_RUNTIME_INVALID"))?,
    )
    .map_err(|e| InstallError::new("ADVANCED_AI_RUNTIME_INVALID", e.to_string()))?;
    if manifest.get("component").and_then(|value| value.as_str()) != Some("advanced_ai") {
        return Err(InstallError::new(
            "ADVANCED_AI_RUNTIME_INVALID",
            "Runtime manifest component is not advanced_ai.",
        ));
    }
    validate_manifest_files(&located, manifest.get("files"), None)?;
    Ok(located)
}

fn validate_model_payload(root: &Path) -> InstallResult<PathBuf> {
    let located = locate_single(root, "manifest.json")?;
    if !located.join("vlm").is_dir() {
        return Err(InstallError::new(
            "ADVANCED_AI_MODELS_INVALID",
            "VLM model directory is missing.",
        ));
    }
    let manifest: serde_json::Value = serde_json::from_slice(
        &fs::read(located.join("manifest.json")).map_err(io_error("ADVANCED_AI_MODELS_INVALID"))?,
    )
    .map_err(|e| InstallError::new("ADVANCED_AI_MODELS_INVALID", e.to_string()))?;
    let vlm = manifest
        .get("models")
        .and_then(|value| value.get("vlm"))
        .ok_or_else(|| {
            InstallError::new(
                "ADVANCED_AI_MODELS_INVALID",
                "Model manifest does not declare the VLM component.",
            )
        })?;
    let prefix = vlm.get("path").and_then(|value| value.as_str());
    validate_manifest_files(&located, vlm.get("files"), prefix)?;
    Ok(located)
}

fn validate_manifest_files(
    root: &Path,
    files: Option<&serde_json::Value>,
    prefix: Option<&str>,
) -> InstallResult<()> {
    let entries = files.and_then(|value| value.as_array()).ok_or_else(|| {
        InstallError::new(
            "ADVANCED_AI_COMPONENT_INVALID",
            "Component manifest file list is missing.",
        )
    })?;
    if entries.is_empty() {
        return Err(InstallError::new(
            "ADVANCED_AI_COMPONENT_INVALID",
            "Component manifest file list is empty.",
        ));
    }
    for entry in entries {
        let relative = entry
            .get("path")
            .and_then(|value| value.as_str())
            .ok_or_else(|| {
                InstallError::new("ADVANCED_AI_COMPONENT_INVALID", "File path is missing.")
            })?;
        if !safe_relative(relative) || prefix.is_some_and(|value| !safe_relative(value)) {
            return Err(InstallError::new(
                "ADVANCED_AI_COMPONENT_INVALID",
                "Component manifest contains an unsafe path.",
            ));
        }
        let target = prefix.map_or_else(
            || root.join(relative),
            |value| root.join(value).join(relative),
        );
        let expected_size = entry
            .get("size_bytes")
            .and_then(|value| value.as_u64())
            .ok_or_else(|| {
                InstallError::new("ADVANCED_AI_COMPONENT_INVALID", "File size is missing.")
            })?;
        let expected_hash = entry
            .get("sha256")
            .and_then(|value| value.as_str())
            .filter(|value| valid_hash(value))
            .ok_or_else(|| {
                InstallError::new("ADVANCED_AI_COMPONENT_INVALID", "File hash is missing.")
            })?;
        let metadata = target
            .metadata()
            .map_err(|_| InstallError::new("ADVANCED_AI_COMPONENT_HASH_MISMATCH", relative))?;
        if !metadata.is_file()
            || metadata.len() != expected_size
            || sha256_file(&target)? != expected_hash
        {
            return Err(InstallError::new(
                "ADVANCED_AI_COMPONENT_HASH_MISMATCH",
                relative,
            ));
        }
    }
    Ok(())
}

fn sha256_file(path: &Path) -> InstallResult<String> {
    let mut input = File::open(path).map_err(io_error("ADVANCED_AI_COMPONENT_HASH_MISMATCH"))?;
    let mut digest = Sha256::new();
    let mut buffer = vec![0_u8; BUFFER_SIZE];
    loop {
        let count = input
            .read(&mut buffer)
            .map_err(io_error("ADVANCED_AI_COMPONENT_HASH_MISMATCH"))?;
        if count == 0 {
            break;
        }
        digest.update(&buffer[..count]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn activate_components(
    components_root: &Path,
    staged_runtime: &Path,
    staged_models: &Path,
    manifest: &AdvancedAIManifest,
    id: &str,
    install_runtime: bool,
    install_models: bool,
) -> InstallResult<()> {
    let runtime_source = install_runtime
        .then(|| validate_runtime_payload(staged_runtime))
        .transpose()?;
    let models_source = install_models
        .then(|| validate_model_payload(staged_models))
        .transpose()?;
    let runtime_directory = format!("vlm-runtime/{}", manifest.components.vlm_runtime.version);
    let models_directory = format!("vlm-models/{}", manifest.components.vlm_models.version);
    let runtime_destination = components_root.join(&runtime_directory);
    let models_destination = components_root.join(&models_directory);
    fs::create_dir_all(runtime_destination.parent().expect("runtime parent"))
        .map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
    fs::create_dir_all(models_destination.parent().expect("models parent"))
        .map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
    let runtime_backup = components_root.join(format!(".replaced-runtime-{id}"));
    let models_backup = components_root.join(format!(".replaced-models-{id}"));
    if install_runtime && runtime_destination.exists() {
        fs::rename(&runtime_destination, &runtime_backup)
            .map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
    }
    if install_models && models_destination.exists() {
        fs::rename(&models_destination, &models_backup)
            .map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
    }
    let activation = (|| {
        if let Some(runtime_source) = runtime_source {
            fs::rename(runtime_source, &runtime_destination)
                .map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
        }
        if let Some(models_source) = models_source {
            fs::rename(models_source, &models_destination)
                .map_err(io_error("ADVANCED_AI_INSTALL_FAILED"))?;
        }
        let registry = ActiveComponentRegistry {
            schema_version: 1,
            vlm_runtime_version: manifest.components.vlm_runtime.version.clone(),
            vlm_runtime_directory: runtime_directory,
            vlm_models_version: manifest.components.vlm_models.version.clone(),
            vlm_models_directory: models_directory,
        };
        write_registry(components_root, &registry)
    })();
    if activation.is_err() {
        if install_runtime {
            let _ = fs::remove_dir_all(&runtime_destination);
        }
        if install_models {
            let _ = fs::remove_dir_all(&models_destination);
        }
        if runtime_backup.exists() {
            let _ = fs::rename(&runtime_backup, &runtime_destination);
        }
        if models_backup.exists() {
            let _ = fs::rename(&models_backup, &models_destination);
        }
    } else {
        let _ = fs::remove_dir_all(runtime_backup);
        let _ = fs::remove_dir_all(models_backup);
    }
    activation
}

fn write_registry(root: &Path, registry: &ActiveComponentRegistry) -> InstallResult<()> {
    let active = root.join("components.json");
    let previous = root.join("components.previous.json");
    let temporary = root.join(format!("components.{}.tmp", Uuid::new_v4().simple()));
    fs::write(
        &temporary,
        serde_json::to_vec_pretty(registry).expect("registry serializes"),
    )
    .map_err(io_error("ADVANCED_AI_ACTIVATION_FAILED"))?;
    if active.exists() {
        let _ = fs::remove_file(&previous);
        fs::rename(&active, &previous).map_err(io_error("ADVANCED_AI_ACTIVATION_FAILED"))?;
    }
    if let Err(error) = fs::rename(&temporary, &active) {
        if previous.exists() {
            let _ = fs::rename(&previous, &active);
        }
        return Err(InstallError::new(
            "ADVANCED_AI_ACTIVATION_FAILED",
            error.to_string(),
        ));
    }
    Ok(())
}

fn rollback_active(data_dir: &Path) -> InstallResult<()> {
    let root = data_dir.join("components");
    let active = root.join("components.json");
    let previous = root.join("components.previous.json");
    let registry: serde_json::Value = serde_json::from_slice(
        &fs::read(&previous).map_err(io_error("ADVANCED_AI_ROLLBACK_UNAVAILABLE"))?,
    )
    .map_err(|e| InstallError::new("ADVANCED_AI_ROLLBACK_UNAVAILABLE", e.to_string()))?;
    if !registry_paths_exist(data_dir, &root, &registry) {
        return Err(InstallError::new(
            "ADVANCED_AI_ROLLBACK_UNAVAILABLE",
            "Previous component files are no longer available.",
        ));
    }
    let swap = root.join("components.rollback.tmp");
    fs::rename(&active, &swap).map_err(io_error("ADVANCED_AI_ROLLBACK_FAILED"))?;
    fs::rename(&previous, &active).map_err(io_error("ADVANCED_AI_ROLLBACK_FAILED"))?;
    fs::rename(&swap, &previous).map_err(io_error("ADVANCED_AI_ROLLBACK_FAILED"))?;
    Ok(())
}

fn uninstall_active(data_dir: &Path) -> InstallResult<()> {
    let root = data_dir.join("components");
    if let Some(managed) = active_managed_vlm_paths(data_dir) {
        let environment = managed.python_executable.parent().ok_or_else(|| {
            InstallError::new("ADVANCED_AI_UNINSTALL_FAILED", "Invalid environment path.")
        })?;
        fs::remove_dir_all(environment).map_err(io_error("ADVANCED_AI_UNINSTALL_FAILED"))?;
        fs::remove_dir_all(managed.models_directory)
            .map_err(io_error("ADVANCED_AI_UNINSTALL_FAILED"))?;
        let _ = fs::remove_dir_all(data_dir.join("advanced-ai"));
    } else if let Some((runtime, models, _)) = active_vlm_paths(data_dir) {
        fs::remove_dir_all(runtime).map_err(io_error("ADVANCED_AI_UNINSTALL_FAILED"))?;
        fs::remove_dir_all(models).map_err(io_error("ADVANCED_AI_UNINSTALL_FAILED"))?;
    } else {
        return Ok(());
    }
    let _ = fs::remove_file(root.join("components.json"));
    let _ = fs::remove_file(root.join("components.previous.json"));
    Ok(())
}

fn registry_paths_exist(data_dir: &Path, legacy_root: &Path, registry: &serde_json::Value) -> bool {
    if registry
        .get("schema_version")
        .and_then(|value| value.as_u64())
        == Some(2)
    {
        let Some(python) = registry
            .get("python_executable")
            .and_then(|value| value.as_str())
        else {
            return false;
        };
        let Some(models) = registry
            .get("vlm_models_directory")
            .and_then(|value| value.as_str())
        else {
            return false;
        };
        return safe_relative(python)
            && safe_relative(models)
            && data_dir.join(python).is_file()
            && data_dir.join(models).is_dir();
    }
    let Some(runtime) = registry
        .get("vlm_runtime_directory")
        .and_then(|value| value.as_str())
    else {
        return false;
    };
    let Some(models) = registry
        .get("vlm_models_directory")
        .and_then(|value| value.as_str())
    else {
        return false;
    };
    safe_relative(runtime)
        && safe_relative(models)
        && legacy_root.join(runtime).is_dir()
        && legacy_root.join(models).is_dir()
}

fn update_status(
    status: &Arc<RwLock<AdvancedAIInstallStatus>>,
    state: &str,
    result: Option<&AdvancedAIInstallResult>,
    completed: u64,
    total: u64,
    error: Option<(String, String)>,
) {
    let mut current = status.write().expect("advanced AI install status poisoned");
    current.state = state.into();
    current.bytes_completed = completed.min(total);
    current.bytes_total = total;
    if let Some(result) = result {
        current.package_version = Some(result.package_version.clone());
        current.runtime_version = Some(result.runtime_version.clone());
        current.model_version = Some(result.model_version.clone());
    }
    current.error_code = error.as_ref().map(|value| value.0.clone());
    current.error_message = error.map(|value| value.1);
}

fn check_cancelled(cancelled: &AtomicBool) -> InstallResult<()> {
    if cancelled.load(Ordering::SeqCst) {
        Err(InstallError::new(
            "ADVANCED_AI_INSTALL_CANCELLED",
            "Advanced AI installation was cancelled safely.",
        ))
    } else {
        Ok(())
    }
}

fn safe_file_name(value: &str) -> bool {
    Path::new(value).file_name().and_then(|name| name.to_str()) == Some(value)
        && safe_relative(value)
}

fn safe_relative(value: &str) -> bool {
    !value.is_empty()
        && !Path::new(value).is_absolute()
        && Path::new(value)
            .components()
            .all(|component| matches!(component, Component::Normal(_)))
}

fn safe_version(value: &str) -> bool {
    !value.is_empty()
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-'))
}

fn valid_hash(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
}

fn io_error(code: &'static str) -> impl FnOnce(io::Error) -> InstallError {
    move |error| InstallError::new(code, error.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn manifest_part_names_cannot_escape_package_directory() {
        assert!(safe_file_name("runtime.zip.part01"));
        assert!(!safe_file_name("../runtime.zip.part01"));
        assert!(!safe_file_name("nested/runtime.zip.part01"));
    }

    #[test]
    fn multipart_reader_crosses_part_boundaries() {
        let root = std::env::temp_dir().join(format!("visionguard-parts-{}", Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap();
        fs::write(root.join("one"), b"abc").unwrap();
        fs::write(root.join("two"), b"defg").unwrap();
        let component = PackageComponent {
            version: "v1".into(),
            archive_format: "zip".into(),
            archive_size_bytes: 7,
            unpacked_size_bytes: 7,
            archive_sha256: "0".repeat(64),
            parts: vec![
                PackagePart {
                    index: 1,
                    file: "one".into(),
                    size_bytes: 3,
                    sha256: "0".repeat(64),
                },
                PackagePart {
                    index: 2,
                    file: "two".into(),
                    size_bytes: 4,
                    sha256: "0".repeat(64),
                },
            ],
        };
        let mut reader = PartReader::open(&root, &component).unwrap();
        let mut payload = Vec::new();
        reader.read_to_end(&mut payload).unwrap();
        assert_eq!(payload, b"abcdefg");
        reader.seek(SeekFrom::Start(2)).unwrap();
        let mut tail = [0_u8; 3];
        reader.read_exact(&mut tail).unwrap();
        assert_eq!(&tail, b"cde");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn managed_registry_only_resolves_expected_application_paths() {
        let root = std::env::temp_dir().join(format!("visionguard-managed-{}", Uuid::new_v4()));
        let python = root.join("advanced-ai/envs/vlm-v1/python.exe");
        let models = root.join("advanced-ai/models/vlm-models-v1");
        fs::create_dir_all(python.parent().unwrap()).unwrap();
        fs::create_dir_all(&models).unwrap();
        fs::create_dir_all(root.join("components")).unwrap();
        fs::write(&python, b"fixture").unwrap();
        fs::write(
            root.join("components/components.json"),
            serde_json::to_vec(&serde_json::json!({
                "schema_version": 2,
                "distribution_mode": "online_bootstrap",
                "python_executable": "advanced-ai/envs/vlm-v1/python.exe",
                "vlm_models_directory": "advanced-ai/models/vlm-models-v1",
                "vlm_models_version": "vlm-models-v1",
                "model_revision": "89644892e4d85e24eaac8bacfd4f463576704203"
            }))
            .unwrap(),
        )
        .unwrap();
        let resolved = active_managed_vlm_paths(&root).unwrap();
        assert_eq!(resolved.python_executable, python);
        assert_eq!(resolved.models_directory, models);
        fs::remove_dir_all(root).unwrap();
    }
}
