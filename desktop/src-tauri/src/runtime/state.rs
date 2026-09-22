use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeState {
    Stopped,
    Starting,
    CheckingHardware,
    ValidatingModels,
    Launching,
    WaitingForLive,
    WaitingForReady,
    Ready,
    Unavailable,
    Failed,
    Stopping,
}

#[derive(Debug, Clone, Serialize)]
pub struct RuntimeSnapshot {
    pub state: RuntimeState,
    pub backend_mode: String,
    pub endpoint: Option<String>,
    pub pid: Option<u32>,
    pub elapsed_ms: u64,
    pub runtime_version: Option<String>,
    pub model_bundle_version: Option<String>,
    pub api_version: Option<String>,
    pub model_components: HashMap<String, String>,
    pub diagnostics: serde_json::Value,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
    pub last_exit_code: Option<i32>,
}

impl RuntimeSnapshot {
    pub fn initial(mode: impl Into<String>) -> Self {
        Self {
            state: RuntimeState::Stopped,
            backend_mode: mode.into(),
            endpoint: None,
            pid: None,
            elapsed_ms: 0,
            runtime_version: None,
            model_bundle_version: None,
            api_version: None,
            model_components: HashMap::new(),
            diagnostics: serde_json::json!({}),
            error_code: None,
            error_message: None,
            last_exit_code: None,
        }
    }
}

#[derive(Debug, Clone)]
pub struct RuntimeError {
    pub code: &'static str,
    pub message: String,
}

impl RuntimeError {
    pub fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
}

impl std::fmt::Display for RuntimeError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for RuntimeError {}
