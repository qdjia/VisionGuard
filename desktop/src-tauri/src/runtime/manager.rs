use super::state::{RuntimeError, RuntimeSnapshot, RuntimeState};
use crate::models::{active_bundle_path, active_runtime_executable};
use reqwest::Client;
use serde::Deserialize;
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::atomic::{AtomicBool, Ordering},
    sync::{Arc, Mutex, RwLock},
    time::{Duration, Instant},
};
use tauri::{AppHandle, Manager};
use tokio::sync::Mutex as AsyncMutex;
use uuid::Uuid;

const API_VERSION: &str = "v1";
const LAUNCH_TIMEOUT: Duration = Duration::from_secs(10);
const READY_TIMEOUT: Duration = Duration::from_secs(120);
const POLL_INTERVAL: Duration = Duration::from_millis(500);
const STOP_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, Deserialize)]
struct ModelManifest {
    bundle_version: String,
    models: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Deserialize)]
struct RuntimeFileStatus {
    state: String,
    pid: u32,
    endpoint: Option<String>,
    runtime_version: String,
    api_version: String,
    model_bundle_version: Option<String>,
    model_validation: Option<ModelValidation>,
    diagnostics: serde_json::Value,
    error_code: Option<String>,
    error_message: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ModelValidation {
    components: HashMap<String, String>,
}

#[derive(Debug, Deserialize)]
struct MetaResponse {
    api_version: String,
    runtime_version: Option<String>,
    model_bundle_version: Option<String>,
}

pub struct RuntimeManager {
    app: AppHandle,
    status: Arc<RwLock<RuntimeSnapshot>>,
    child: Arc<Mutex<Option<Child>>>,
    operation: AsyncMutex<()>,
    started: Mutex<Option<Instant>>,
    control_token: Mutex<Option<String>>,
    cancel_requested: AtomicBool,
}

impl RuntimeManager {
    pub fn new(app: AppHandle) -> Arc<Self> {
        let mode = std::env::var("VISIONGUARD_BACKEND_MODE")
            .unwrap_or_else(|_| "sidecar".to_string())
            .to_lowercase();
        Arc::new(Self {
            app,
            status: Arc::new(RwLock::new(RuntimeSnapshot::initial(mode))),
            child: Arc::new(Mutex::new(None)),
            operation: AsyncMutex::new(()),
            started: Mutex::new(None),
            control_token: Mutex::new(None),
            cancel_requested: AtomicBool::new(false),
        })
    }

    pub fn snapshot(&self) -> RuntimeSnapshot {
        let mut snapshot = self.status.read().expect("runtime status poisoned").clone();
        if let Some(started) = *self.started.lock().expect("runtime timer poisoned") {
            snapshot.elapsed_ms = started.elapsed().as_millis() as u64;
        }
        snapshot
    }

    pub fn endpoint(&self) -> Result<String, RuntimeError> {
        let snapshot = self.snapshot();
        snapshot.endpoint.ok_or_else(|| {
            RuntimeError::new(
                "RUNTIME_NOT_READY",
                format!(
                    "runtime endpoint unavailable while state={:?}",
                    snapshot.state
                ),
            )
        })
    }

    pub async fn start(self: &Arc<Self>) -> Result<(), RuntimeError> {
        let _guard = self.operation.lock().await;
        self.cancel_requested.store(false, Ordering::SeqCst);
        *self.started.lock().expect("runtime timer poisoned") = Some(Instant::now());
        self.reset_for_start();
        if self.snapshot().backend_mode == "external" {
            return self.start_external().await;
        }
        let first = self.start_sidecar_once().await;
        if let Err(error) = first {
            if self.cancel_requested.load(Ordering::SeqCst) {
                self.force_kill();
                return Err(RuntimeError::new(
                    "RUNTIME_EXITED",
                    "runtime startup cancelled",
                ));
            }
            if matches!(
                error.code,
                "RUNTIME_COMPONENT_MISSING" | "MODEL_BUNDLE_MISSING" | "MODEL_BUNDLE_INVALID"
            ) {
                self.fail(&error);
                return Err(error);
            }
            self.force_kill();
            tokio::time::sleep(Duration::from_millis(250)).await;
            if let Err(retry_error) = self.start_sidecar_once().await {
                self.fail(&retry_error);
                return Err(retry_error);
            }
        }
        Ok(())
    }

    pub async fn restart(self: &Arc<Self>) -> Result<(), RuntimeError> {
        self.stop().await;
        self.start().await
    }

    pub async fn stop(self: &Arc<Self>) {
        self.cancel_requested.store(true, Ordering::SeqCst);
        let _guard = self.operation.lock().await;
        self.stop_inner().await;
    }

    async fn start_external(&self) -> Result<(), RuntimeError> {
        let endpoint = std::env::var("VISIONGUARD_API_URL")
            .unwrap_or_else(|_| "http://127.0.0.1:8000".to_string());
        self.update(|state| {
            state.state = RuntimeState::WaitingForLive;
            state.endpoint = Some(endpoint.clone());
        });
        self.wait_for_health(&endpoint, READY_TIMEOUT, None).await?;
        self.update(|state| state.state = RuntimeState::Ready);
        Ok(())
    }

    async fn start_sidecar_once(&self) -> Result<(), RuntimeError> {
        let data_dir = self
            .app
            .path()
            .app_local_data_dir()
            .map_err(|error| RuntimeError::new("RUNTIME_START_FAILED", error.to_string()))?;
        let runtime_executable = self.resolve_runtime_executable(&data_dir)?;
        self.update(|state| state.state = RuntimeState::ValidatingModels);
        let model_dir = self.resolve_model_bundle(&data_dir);
        let manifest = self.quick_validate_manifest(&model_dir)?;
        self.update(|state| {
            state.model_bundle_version = Some(manifest.bundle_version.clone());
            state.model_components = component_statuses(&manifest);
            state.state = RuntimeState::Launching;
        });

        let runtime_dir = data_dir.join("runtime");
        let log_dir = data_dir.join("logs");
        let artifact_dir = data_dir.join("artifacts");
        let cache_dir = data_dir.join("cache");
        for path in [&runtime_dir, &log_dir, &artifact_dir, &cache_dir] {
            std::fs::create_dir_all(path)
                .map_err(|error| RuntimeError::new("RUNTIME_START_FAILED", error.to_string()))?;
        }
        let run_id = Uuid::new_v4().simple().to_string();
        let config_path = runtime_dir.join(format!("runtime-{run_id}.json"));
        let status_path = runtime_dir.join(format!("status-{run_id}.json"));
        let config = serde_json::json!({
            "host": "127.0.0.1",
            "port": 0,
            "model_bundle_path": model_dir,
            "user_data_dir": data_dir,
            "artifact_root": artifact_dir,
            "log_root": log_dir,
            "cache_root": cache_dir,
            "max_concurrent_inference": 1,
            "save_artifacts": false,
            "warmup_on_startup": false,
            "model_validation": "quick",
            "runtime_edition": "gpu",
            "minimum_free_disk_bytes": 536870912
        });
        std::fs::write(
            &config_path,
            serde_json::to_vec_pretty(&config).expect("runtime config is serializable"),
        )
        .map_err(|error| RuntimeError::new("RUNTIME_START_FAILED", error.to_string()))?;

        let token = Uuid::new_v4().simple().to_string();
        let mut command = Command::new(runtime_executable);
        command
            .args(["--config"])
            .arg(&config_path)
            .args(["--status-file"])
            .arg(&status_path)
            .env("VISIONGUARD_CONTROL_TOKEN", &token)
            .env("YOLO_AUTOINSTALL", "false")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let child = command
            .spawn()
            .map_err(|error| RuntimeError::new("RUNTIME_START_FAILED", error.to_string()))?;
        let pid = child.id();
        *self.child.lock().expect("runtime child poisoned") = Some(child);
        *self.control_token.lock().expect("runtime token poisoned") = Some(token);
        self.update(|state| state.pid = Some(pid));

        let status = Arc::clone(&self.status);
        let child = Arc::clone(&self.child);
        tauri::async_runtime::spawn(async move {
            loop {
                let exit_code = {
                    let mut current = child.lock().expect("runtime child poisoned");
                    current
                        .as_mut()
                        .and_then(|process| process.try_wait().ok().flatten())
                        .map(|exit| exit.code())
                };
                if let Some(exit_code) = exit_code {
                    child.lock().expect("runtime child poisoned").take();
                    let mut snapshot = status.write().expect("runtime status poisoned");
                    snapshot.last_exit_code = exit_code;
                    snapshot.pid = None;
                    if snapshot.state == RuntimeState::Stopping {
                        snapshot.state = RuntimeState::Stopped;
                    } else if snapshot.state != RuntimeState::Stopped {
                        snapshot.state = RuntimeState::Failed;
                        snapshot.error_code = Some("RUNTIME_EXITED".to_string());
                        snapshot.error_message =
                            Some("VisionGuard AI Runtime stopped unexpectedly.".to_string());
                    }
                    break;
                }
                tokio::time::sleep(Duration::from_millis(200)).await;
            }
        });

        let endpoint = self.wait_for_handshake(&status_path).await?;
        self.update(|state| {
            state.state = RuntimeState::WaitingForLive;
            state.endpoint = Some(endpoint.clone());
        });
        self.wait_for_health(&endpoint, READY_TIMEOUT, Some(&status_path))
            .await
    }

    async fn wait_for_handshake(&self, path: &Path) -> Result<String, RuntimeError> {
        let started = Instant::now();
        while started.elapsed() < LAUNCH_TIMEOUT {
            if self.cancel_requested.load(Ordering::SeqCst) {
                return Err(RuntimeError::new(
                    "RUNTIME_EXITED",
                    "runtime startup cancelled",
                ));
            }
            if let Ok(content) = std::fs::read_to_string(path) {
                if let Ok(file_status) = serde_json::from_str::<RuntimeFileStatus>(&content) {
                    self.absorb_file_status(&file_status);
                    if file_status.state == "failed" {
                        return Err(runtime_file_error(&file_status));
                    }
                    if let Some(endpoint) = file_status.endpoint {
                        return Ok(endpoint);
                    }
                }
            }
            if self.snapshot().state == RuntimeState::Failed {
                return Err(RuntimeError::new(
                    "RUNTIME_EXITED",
                    "runtime exited before publishing its endpoint",
                ));
            }
            tokio::time::sleep(POLL_INTERVAL).await;
        }
        Err(RuntimeError::new(
            "RUNTIME_START_FAILED",
            "runtime launch handshake timed out",
        ))
    }

    async fn wait_for_health(
        &self,
        endpoint: &str,
        ready_timeout: Duration,
        status_path: Option<&Path>,
    ) -> Result<(), RuntimeError> {
        let client = Client::builder()
            .timeout(Duration::from_secs(2))
            .build()
            .map_err(|error| RuntimeError::new("RUNTIME_START_FAILED", error.to_string()))?;
        let live_started = Instant::now();
        loop {
            if self.cancel_requested.load(Ordering::SeqCst) {
                return Err(RuntimeError::new(
                    "RUNTIME_EXITED",
                    "runtime startup cancelled",
                ));
            }
            if client
                .get(format!("{endpoint}/health/live"))
                .send()
                .await
                .is_ok_and(|response| response.status().is_success())
            {
                break;
            }
            if live_started.elapsed() >= LAUNCH_TIMEOUT {
                return Err(RuntimeError::new(
                    "RUNTIME_START_FAILED",
                    "runtime liveness timeout",
                ));
            }
            tokio::time::sleep(POLL_INTERVAL).await;
        }
        self.update(|state| state.state = RuntimeState::WaitingForReady);
        let ready_started = Instant::now();
        loop {
            if self.cancel_requested.load(Ordering::SeqCst) {
                return Err(RuntimeError::new(
                    "RUNTIME_EXITED",
                    "runtime startup cancelled",
                ));
            }
            if let Some(path) = status_path {
                if let Ok(content) = std::fs::read_to_string(path) {
                    if let Ok(file_status) = serde_json::from_str::<RuntimeFileStatus>(&content) {
                        self.absorb_file_status(&file_status);
                        if file_status.state == "failed" {
                            return Err(runtime_file_error(&file_status));
                        }
                    }
                }
            }
            if self.snapshot().state == RuntimeState::Failed {
                return Err(RuntimeError::new(
                    "RUNTIME_EXITED",
                    "runtime exited while loading models",
                ));
            }
            if client
                .get(format!("{endpoint}/health/ready"))
                .send()
                .await
                .is_ok_and(|response| response.status().is_success())
            {
                let meta = client
                    .get(format!("{endpoint}/v1/meta"))
                    .send()
                    .await
                    .map_err(|error| RuntimeError::new("RUNTIME_NOT_READY", error.to_string()))?
                    .json::<MetaResponse>()
                    .await
                    .map_err(|error| RuntimeError::new("RUNTIME_NOT_READY", error.to_string()))?;
                if meta.api_version != API_VERSION {
                    return Err(RuntimeError::new(
                        "RUNTIME_VERSION_MISMATCH",
                        format!(
                            "desktop expects {API_VERSION}, runtime returned {}",
                            meta.api_version
                        ),
                    ));
                }
                self.update(|state| {
                    state.state = RuntimeState::Ready;
                    state.api_version = Some(meta.api_version);
                    state.runtime_version = meta.runtime_version;
                    state.model_bundle_version = meta.model_bundle_version;
                });
                return Ok(());
            }
            if ready_started.elapsed() >= ready_timeout {
                return Err(RuntimeError::new(
                    "RUNTIME_NOT_READY",
                    "AI models did not become ready before the startup timeout",
                ));
            }
            tokio::time::sleep(Duration::from_secs(1)).await;
        }
    }

    async fn stop_inner(&self) {
        if self.snapshot().backend_mode == "external" {
            self.update(|state| state.state = RuntimeState::Stopped);
            return;
        }
        self.update(|state| state.state = RuntimeState::Stopping);
        let endpoint = self.snapshot().endpoint;
        let token = self
            .control_token
            .lock()
            .expect("runtime token poisoned")
            .clone();
        if let (Some(endpoint), Some(token)) = (endpoint, token) {
            let _ = Client::new()
                .post(format!("{endpoint}/_runtime/shutdown"))
                .header("X-VisionGuard-Control", token)
                .timeout(Duration::from_secs(2))
                .send()
                .await;
        }
        let started = Instant::now();
        while started.elapsed() < STOP_TIMEOUT {
            if self.snapshot().state == RuntimeState::Stopped {
                break;
            }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        if self.snapshot().state != RuntimeState::Stopped {
            self.force_kill();
            tokio::time::sleep(Duration::from_millis(100)).await;
        } else {
            self.child.lock().expect("runtime child poisoned").take();
        }
        *self.control_token.lock().expect("runtime token poisoned") = None;
        self.update(|state| {
            state.state = RuntimeState::Stopped;
            state.endpoint = None;
            state.pid = None;
        });
    }

    fn force_kill(&self) {
        if let Some(mut child) = self.child.lock().expect("runtime child poisoned").take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }

    fn resolve_runtime_executable(&self, data_dir: &Path) -> Result<PathBuf, RuntimeError> {
        if let Ok(path) = std::env::var("VISIONGUARD_RUNTIME_EXECUTABLE") {
            let path = PathBuf::from(path);
            if path.is_file() {
                return Ok(path);
            }
        }
        if let Some(path) = active_runtime_executable(data_dir) {
            return Ok(path);
        }
        #[cfg(debug_assertions)]
        {
            let triple = option_env!("TAURI_ENV_TARGET_TRIPLE").unwrap_or("x86_64-pc-windows-msvc");
            let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("binaries")
                .join(format!("visionguard-runtime-{triple}.exe"));
            if source.is_file() {
                return Ok(source);
            }
        }
        Err(RuntimeError::new(
            "RUNTIME_COMPONENT_MISSING",
            "VisionGuard GPU Runtime is not installed.",
        ))
    }

    fn resolve_model_bundle(&self, data_dir: &Path) -> PathBuf {
        if let Ok(path) = std::env::var("VISIONGUARD_MODEL_BUNDLE") {
            return PathBuf::from(path);
        }
        if let Some(active) = active_bundle_path(data_dir) {
            return active;
        }
        let installed = data_dir.join("models").join("models-v1");
        if installed.is_dir() {
            return installed;
        }
        #[cfg(debug_assertions)]
        {
            let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("..")
                .join("..")
                .join("models")
                .join("models-v1");
            if source.is_dir() {
                return source;
            }
        }
        installed
    }

    fn quick_validate_manifest(&self, model_dir: &Path) -> Result<ModelManifest, RuntimeError> {
        let path = model_dir.join("manifest.json");
        let bytes = std::fs::read(&path).map_err(|_| {
            RuntimeError::new(
                "MODEL_BUNDLE_MISSING",
                "VisionGuard AI models are not installed.",
            )
        })?;
        let manifest: ModelManifest = serde_json::from_slice(&bytes).map_err(|_| {
            RuntimeError::new("MODEL_BUNDLE_INVALID", "Model bundle manifest is invalid.")
        })?;
        let required = [
            "detector",
            "ocr_detection",
            "ocr_recognition",
            "ocr_orientation",
            "baseline",
            "vlm",
        ];
        if required
            .iter()
            .any(|name| !manifest.models.contains_key(*name))
        {
            return Err(RuntimeError::new(
                "MODEL_BUNDLE_INVALID",
                "Model bundle manifest is incomplete.",
            ));
        }
        Ok(manifest)
    }

    fn absorb_file_status(&self, file: &RuntimeFileStatus) {
        self.update(|state| {
            state.pid = Some(file.pid);
            state.runtime_version = Some(file.runtime_version.clone());
            state.api_version = Some(file.api_version.clone());
            state.model_bundle_version = file.model_bundle_version.clone();
            state.diagnostics = file.diagnostics.clone();
            state.error_code = file.error_code.clone();
            state.error_message = file.error_message.clone();
            if let Some(validation) = &file.model_validation {
                state.model_components = validation.components.clone();
            }
        });
    }

    fn reset_for_start(&self) {
        self.update(|state| {
            state.state = RuntimeState::Starting;
            state.endpoint = None;
            state.pid = None;
            state.error_code = None;
            state.error_message = None;
            state.last_exit_code = None;
        });
    }

    fn fail(&self, error: &RuntimeError) {
        self.update(|state| {
            state.state = RuntimeState::Failed;
            state.error_code = Some(error.code.to_string());
            state.error_message = Some(error.message.clone());
        });
    }

    fn update(&self, operation: impl FnOnce(&mut RuntimeSnapshot)) {
        operation(&mut self.status.write().expect("runtime status poisoned"));
    }
}

fn component_statuses(manifest: &ModelManifest) -> HashMap<String, String> {
    let ready = |name: &str| {
        if manifest.models.contains_key(name) {
            "ready".to_string()
        } else {
            "missing".to_string()
        }
    };
    HashMap::from([
        ("detector".to_string(), ready("detector")),
        (
            "ocr".to_string(),
            if ["ocr_detection", "ocr_recognition", "ocr_orientation"]
                .iter()
                .all(|name| manifest.models.contains_key(*name))
            {
                "ready".to_string()
            } else {
                "missing".to_string()
            },
        ),
        ("baseline".to_string(), ready("baseline")),
        ("vlm".to_string(), ready("vlm")),
    ])
}

fn runtime_file_error(status: &RuntimeFileStatus) -> RuntimeError {
    let code = match status.error_code.as_deref() {
        Some("MODEL_BUNDLE_MISSING") => "MODEL_BUNDLE_MISSING",
        Some("MODEL_BUNDLE_INVALID") => "MODEL_BUNDLE_INVALID",
        Some("MODEL_VALIDATION_FAILED") => "MODEL_VALIDATION_FAILED",
        Some("RUNTIME_VERSION_MISMATCH") => "RUNTIME_VERSION_MISMATCH",
        Some("RUNTIME_NOT_READY") => "RUNTIME_NOT_READY",
        Some("GPU_REQUIREMENT_NOT_SATISFIED") => "GPU_REQUIREMENT_NOT_SATISFIED",
        Some("PLATFORM_NOT_SUPPORTED") => "PLATFORM_NOT_SUPPORTED",
        Some("RUNTIME_DISK_SPACE_INSUFFICIENT") => "RUNTIME_DISK_SPACE_INSUFFICIENT",
        _ => "RUNTIME_START_FAILED",
    };
    RuntimeError::new(
        code,
        status
            .error_message
            .clone()
            .unwrap_or_else(|| "runtime startup failed".to_string()),
    )
}
