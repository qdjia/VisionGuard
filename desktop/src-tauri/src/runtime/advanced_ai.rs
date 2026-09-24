use super::RuntimeManager;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::{
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{Arc, Mutex, RwLock},
    time::{Duration, Instant},
};
use tauri::{AppHandle, Manager};
use tokio::sync::Mutex as AsyncMutex;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum AdvancedAIState {
    NotInstalled,
    Installed,
    Stopped,
    Starting,
    LoadingModel,
    Ready,
    Failed,
    Stopping,
}

#[derive(Debug, Clone, Serialize)]
pub struct AdvancedAISnapshot {
    pub state: AdvancedAIState,
    pub endpoint: Option<String>,
    pub pid: Option<u32>,
    pub runtime_version: Option<String>,
    pub model_bundle_version: Option<String>,
    pub model_loaded: bool,
    pub model_init_count: u32,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
}

#[derive(Deserialize)]
struct StatusFile {
    state: String,
    endpoint: Option<String>,
    pid: u32,
    runtime_version: String,
    model_bundle_version: Option<String>,
    error_code: Option<String>,
    error_message: Option<String>,
}

#[derive(Deserialize)]
struct Health {
    status: String,
    model_loaded: bool,
    model_init_count: u32,
}

pub struct AdvancedAIManager {
    app: AppHandle,
    core: Arc<RuntimeManager>,
    status: RwLock<AdvancedAISnapshot>,
    child: Mutex<Option<Child>>,
    token: Mutex<Option<String>>,
    operation: AsyncMutex<()>,
}

impl AdvancedAIManager {
    pub fn new(app: AppHandle, core: Arc<RuntimeManager>) -> Arc<Self> {
        Arc::new(Self {
            app,
            core,
            status: RwLock::new(AdvancedAISnapshot {
                state: AdvancedAIState::Stopped,
                endpoint: None,
                pid: None,
                runtime_version: None,
                model_bundle_version: None,
                model_loaded: false,
                model_init_count: 0,
                error_code: None,
                error_message: None,
            }),
            child: Mutex::new(None),
            token: Mutex::new(None),
            operation: AsyncMutex::new(()),
        })
    }

    pub fn snapshot(&self) -> AdvancedAISnapshot {
        self.status
            .read()
            .expect("advanced AI status poisoned")
            .clone()
    }

    pub async fn start(&self) -> Result<(), String> {
        let _guard = self.operation.lock().await;
        if matches!(
            self.snapshot().state,
            AdvancedAIState::Starting | AdvancedAIState::Ready
        ) {
            return Ok(());
        }
        let data = self
            .app
            .path()
            .app_local_data_dir()
            .map_err(|e| e.to_string())?;
        let executable = self.resolve_executable(&data).ok_or_else(|| {
            self.set_failure("VLM_NOT_INSTALLED", "Advanced AI Runtime is not installed");
            "VLM_NOT_INSTALLED".to_string()
        })?;
        let model = self.resolve_model(&data).ok_or_else(|| {
            self.set_failure("VLM_MODEL_MISSING", "Advanced AI model is not installed");
            "VLM_MODEL_MISSING".to_string()
        })?;
        self.update(|s| {
            s.state = AdvancedAIState::Starting;
            s.error_code = None;
        });
        let run = data.join("advanced-ai").join("run");
        std::fs::create_dir_all(&run).map_err(|e| e.to_string())?;
        let id = Uuid::new_v4().simple().to_string();
        let config = run.join(format!("config-{id}.yaml"));
        let status = run.join(format!("status-{id}.json"));
        let packaged_prompts = executable
            .parent()
            .unwrap_or(Path::new("."))
            .join("_internal/resources/prompts/vlm");
        let prompts = std::env::var("VISIONGUARD_VLM_PROMPTS")
            .map(PathBuf::from)
            .unwrap_or(packaged_prompts);
        let yaml = format!(
            "host: 127.0.0.1\nport: 0\nmodel_path: '{} '\ncache_root: '{} '\nlog_root: '{} '\nprompts_dir: '{} '\nprompt_version: v1\nmodel_bundle_version: vlm-models-v1\ndevice: auto\ndtype: auto\ntimeout_seconds: 120\nload_timeout_seconds: 300\nmax_new_tokens: 512\n",
            path_text(&model), path_text(&data.join("cache/vlm")),
            path_text(&data.join("logs/vlm")), path_text(&prompts),
        ).replace("' ", "'");
        std::fs::write(&config, yaml).map_err(|e| e.to_string())?;
        let token = Uuid::new_v4().simple().to_string();
        let mut command = Command::new(executable);
        command
            .args(["--config"])
            .arg(config)
            .args(["--status-file"])
            .arg(&status)
            .env("VISIONGUARD_VLM_SESSION_TOKEN", &token)
            .env("HF_HUB_OFFLINE", "1")
            .env("TRANSFORMERS_OFFLINE", "1")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let child = command.spawn().map_err(|e| e.to_string())?;
        let pid = child.id();
        *self.child.lock().expect("advanced AI child poisoned") = Some(child);
        *self.token.lock().expect("advanced AI token poisoned") = Some(token.clone());
        self.update(|s| s.pid = Some(pid));
        let deadline = Instant::now() + Duration::from_secs(20);
        while Instant::now() < deadline {
            if let Ok(payload) = std::fs::read(&status) {
                if let Ok(file) = serde_json::from_slice::<StatusFile>(&payload) {
                    if let Some(endpoint) = file.endpoint {
                        if let Err(error) = self.core.register_vlm(&endpoint, &token).await {
                            self.set_failure("VLM_CONTRACT_INCOMPATIBLE", &error.to_string());
                            self.force_kill();
                            return Err(error.to_string());
                        }
                        self.update(|s| {
                            s.state = AdvancedAIState::Installed;
                            s.endpoint = Some(endpoint);
                            s.pid = Some(file.pid);
                            s.runtime_version = Some(file.runtime_version);
                            s.model_bundle_version = file.model_bundle_version;
                        });
                        return Ok(());
                    }
                    if file.state == "failed" {
                        self.set_failure(
                            file.error_code
                                .as_deref()
                                .unwrap_or("VLM_RUNTIME_START_FAILED"),
                            file.error_message
                                .as_deref()
                                .unwrap_or("Advanced AI failed"),
                        );
                        return Err("VLM_RUNTIME_START_FAILED".into());
                    }
                }
            }
            tokio::time::sleep(Duration::from_millis(200)).await;
        }
        self.set_failure("VLM_RUNTIME_START_TIMEOUT", "Advanced AI startup timed out");
        self.force_kill();
        Err("VLM_RUNTIME_START_TIMEOUT".into())
    }

    pub async fn refresh(&self) -> AdvancedAISnapshot {
        let snap = self.snapshot();
        let token = {
            self.token
                .lock()
                .expect("advanced AI token poisoned")
                .clone()
        };
        if let (Some(endpoint), Some(token)) = (snap.endpoint, token) {
            match Client::new()
                .get(format!("{endpoint}/health/ready"))
                .header("X-VisionGuard-Session", token)
                .timeout(Duration::from_secs(2))
                .send()
                .await
            {
                Ok(response) => {
                    if let Ok(health) = response.json::<Health>().await {
                        self.update(|s| {
                            s.model_loaded = health.model_loaded;
                            s.model_init_count = health.model_init_count;
                            s.state = if health.status == "loading" {
                                AdvancedAIState::LoadingModel
                            } else if health.model_loaded {
                                AdvancedAIState::Ready
                            } else {
                                AdvancedAIState::Installed
                            };
                        });
                    }
                }
                Err(_) => {
                    self.core.unregister_vlm().await;
                    self.set_failure(
                        "VLM_RUNTIME_EXITED",
                        "Advanced AI stopped unexpectedly; Fast Review remains available",
                    );
                }
            }
        }
        self.snapshot()
    }

    pub async fn restart(&self) -> Result<(), String> {
        self.stop().await;
        self.start().await
    }

    pub async fn stop(&self) {
        let _guard = self.operation.lock().await;
        self.update(|s| s.state = AdvancedAIState::Stopping);
        self.core.unregister_vlm().await;
        let snap = self.snapshot();
        let token = {
            self.token
                .lock()
                .expect("advanced AI token poisoned")
                .clone()
        };
        if let (Some(endpoint), Some(token)) = (snap.endpoint, token) {
            let _ = Client::new()
                .post(format!("{endpoint}/_runtime/shutdown"))
                .header("X-VisionGuard-Session", token)
                .timeout(Duration::from_secs(2))
                .send()
                .await;
        }
        tokio::time::sleep(Duration::from_millis(300)).await;
        self.force_kill();
        *self.token.lock().expect("advanced AI token poisoned") = None;
        self.update(|s| {
            s.state = AdvancedAIState::Stopped;
            s.endpoint = None;
            s.pid = None;
            s.model_loaded = false;
        });
    }

    fn resolve_executable(&self, data: &Path) -> Option<PathBuf> {
        std::env::var("VISIONGUARD_VLM_RUNTIME_EXECUTABLE")
            .ok()
            .map(PathBuf::from)
            .filter(|p| p.is_file())
            .or_else(|| {
                let p = data.join("components/vlm-runtime/visionguard-vlm-runtime.exe");
                p.is_file().then_some(p)
            })
    }
    fn resolve_model(&self, data: &Path) -> Option<PathBuf> {
        std::env::var("VISIONGUARD_VLM_MODEL_BUNDLE")
            .ok()
            .map(PathBuf::from)
            .filter(|p| p.is_dir())
            .or_else(|| {
                let p = data.join("components/vlm-models/vlm-models-v1/vlm");
                p.is_dir().then_some(p)
            })
    }
    fn force_kill(&self) {
        if let Some(mut child) = self
            .child
            .lock()
            .expect("advanced AI child poisoned")
            .take()
        {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
    fn set_failure(&self, code: &str, message: &str) {
        self.update(|s| {
            s.state = if code == "VLM_NOT_INSTALLED" {
                AdvancedAIState::NotInstalled
            } else {
                AdvancedAIState::Failed
            };
            s.error_code = Some(code.into());
            s.error_message = Some(message.into());
        });
    }
    fn update(&self, op: impl FnOnce(&mut AdvancedAISnapshot)) {
        op(&mut self.status.write().expect("advanced AI status poisoned"));
    }
}

fn path_text(path: &Path) -> String {
    path.to_string_lossy()
        .replace('\\', "/")
        .replace('\'', "''")
}
