use fs2::available_space;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{HashMap, HashSet},
    fs::{self, File},
    io::{self, Read, Write},
    path::{Component, Path, PathBuf},
    sync::{Arc, RwLock},
};
use tauri::{AppHandle, Manager};
use tokio::sync::Mutex as AsyncMutex;
use uuid::Uuid;
use zip::ZipArchive;

const RUNTIME_VERSION: &str = "0.1.0";
const SAFETY_MARGIN_PERCENT: u64 = 15;
const COPY_BUFFER_SIZE: usize = 1024 * 1024;

#[derive(Debug, Clone, Deserialize)]
struct ManifestFile {
    path: String,
    size_bytes: u64,
    sha256: String,
}

#[derive(Debug, Clone, Deserialize)]
struct ModelArtifact {
    path: String,
    kind: String,
    #[serde(default)]
    required: bool,
    size_bytes: u64,
    sha256: Option<String>,
    #[serde(default)]
    files: Vec<ManifestFile>,
}

#[derive(Debug, Clone, Deserialize)]
struct RuntimeCompatibility {
    min_inclusive: String,
    max_exclusive: String,
}

#[derive(Debug, Clone, Deserialize)]
struct ModelManifest {
    schema_version: u32,
    bundle_version: String,
    compatible_runtime: RuntimeCompatibility,
    models: HashMap<String, ModelArtifact>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ActiveModelPointer {
    schema_version: u32,
    bundle_version: String,
    directory: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelBundleInfo {
    pub source_kind: String,
    pub bundle_version: String,
    pub runtime_min_inclusive: String,
    pub runtime_max_exclusive: String,
    pub runtime_compatible: bool,
    pub compressed_size_bytes: u64,
    pub uncompressed_size_bytes: u64,
    pub validation_status: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelInstallResult {
    pub bundle_version: String,
    pub validation_status: String,
    pub reused_existing: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelInstallStatus {
    pub state: String,
    pub bundle_version: Option<String>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
}

impl Default for ModelInstallStatus {
    fn default() -> Self {
        Self {
            state: "idle".to_string(),
            bundle_version: None,
            error_code: None,
            error_message: None,
        }
    }
}

#[derive(Debug, Serialize)]
struct ModelSetupError {
    code: &'static str,
    message: String,
}

impl ModelSetupError {
    fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }

    fn json(&self) -> String {
        serde_json::to_string(self).unwrap_or_else(|_| self.message.clone())
    }
}

type SetupResult<T> = Result<T, ModelSetupError>;

enum ModelSource {
    Directory(PathBuf),
    Zip(PathBuf),
}

pub struct ModelInstaller {
    app: AppHandle,
    operation: AsyncMutex<()>,
    status: Arc<RwLock<ModelInstallStatus>>,
}

impl ModelInstaller {
    pub fn new(app: AppHandle) -> Arc<Self> {
        Arc::new(Self {
            app,
            operation: AsyncMutex::new(()),
            status: Arc::new(RwLock::new(ModelInstallStatus::default())),
        })
    }

    pub fn status(&self) -> ModelInstallStatus {
        self.status
            .read()
            .expect("model setup status poisoned")
            .clone()
    }

    pub async fn inspect(&self, source: String) -> Result<ModelBundleInfo, String> {
        let source = PathBuf::from(source);
        tauri::async_runtime::spawn_blocking(move || inspect_source(&source))
            .await
            .map_err(|error| error.to_string())?
            .map_err(|error| error.json())
    }

    pub async fn install(&self, source: String) -> Result<ModelInstallResult, String> {
        let _guard = self.operation.lock().await;
        self.set_status("inspecting", None, None);
        let data_dir = self
            .app
            .path()
            .app_local_data_dir()
            .map_err(|error| error.to_string())?;
        let status = Arc::clone(&self.status);
        let result = tauri::async_runtime::spawn_blocking(move || {
            install_source(&PathBuf::from(source), &data_dir, &status)
        })
        .await
        .map_err(|error| error.to_string())?;
        match result {
            Ok(value) => {
                self.set_status("ready", Some(value.bundle_version.clone()), None);
                Ok(value)
            }
            Err(error) => {
                self.set_status(
                    "failed",
                    None,
                    Some((error.code.to_string(), error.message.clone())),
                );
                Err(error.json())
            }
        }
    }

    fn set_status(
        &self,
        state: &str,
        bundle_version: Option<String>,
        error: Option<(String, String)>,
    ) {
        let mut status = self.status.write().expect("model setup status poisoned");
        status.state = state.to_string();
        status.bundle_version = bundle_version;
        status.error_code = error.as_ref().map(|item| item.0.clone());
        status.error_message = error.map(|item| item.1);
    }
}

pub fn active_bundle_path(data_dir: &Path) -> Option<PathBuf> {
    let models_root = data_dir.join("models");
    let payload = fs::read(models_root.join("active.json")).ok()?;
    let pointer: ActiveModelPointer = serde_json::from_slice(&payload).ok()?;
    if pointer.schema_version != 1 || !safe_relative_path(&pointer.directory) {
        return None;
    }
    let target = models_root.join(pointer.directory);
    target.join("manifest.json").is_file().then_some(target)
}

fn source_type(path: &Path) -> SetupResult<ModelSource> {
    if path.is_dir() {
        return Ok(ModelSource::Directory(path.to_path_buf()));
    }
    if path.is_file()
        && path
            .extension()
            .is_some_and(|extension| extension.eq_ignore_ascii_case("zip"))
    {
        return Ok(ModelSource::Zip(path.to_path_buf()));
    }
    Err(ModelSetupError::new(
        "MODEL_BUNDLE_INVALID",
        "请选择模型目录或 .zip 模型包。",
    ))
}

fn inspect_source(path: &Path) -> SetupResult<ModelBundleInfo> {
    match source_type(path)? {
        ModelSource::Directory(directory) => {
            let manifest = load_directory_manifest(&directory)?;
            validate_manifest_shape(&manifest)?;
            let size = directory_size(&directory)?;
            Ok(ModelBundleInfo {
                source_kind: "directory".to_string(),
                bundle_version: manifest.bundle_version.clone(),
                runtime_min_inclusive: manifest.compatible_runtime.min_inclusive.clone(),
                runtime_max_exclusive: manifest.compatible_runtime.max_exclusive.clone(),
                runtime_compatible: runtime_compatible(&manifest)?,
                compressed_size_bytes: size,
                uncompressed_size_bytes: manifest_size(&manifest),
                validation_status: "selected".to_string(),
            })
        }
        ModelSource::Zip(archive) => {
            let file = File::open(&archive).map_err(io_error("MODEL_BUNDLE_INVALID"))?;
            let mut zip = ZipArchive::new(file).map_err(zip_error)?;
            let (manifest, _) = manifest_from_zip(&mut zip)?;
            validate_manifest_shape(&manifest)?;
            let mut uncompressed = 0_u64;
            for index in 0..zip.len() {
                let item = zip.by_index(index).map_err(zip_error)?;
                uncompressed = uncompressed.checked_add(item.size()).ok_or_else(|| {
                    ModelSetupError::new("MODEL_BUNDLE_INVALID", "模型包体积字段溢出。")
                })?;
            }
            Ok(ModelBundleInfo {
                source_kind: "zip".to_string(),
                bundle_version: manifest.bundle_version.clone(),
                runtime_min_inclusive: manifest.compatible_runtime.min_inclusive.clone(),
                runtime_max_exclusive: manifest.compatible_runtime.max_exclusive.clone(),
                runtime_compatible: runtime_compatible(&manifest)?,
                compressed_size_bytes: archive
                    .metadata()
                    .map_err(io_error("MODEL_BUNDLE_INVALID"))?
                    .len(),
                uncompressed_size_bytes: uncompressed,
                validation_status: "selected".to_string(),
            })
        }
    }
}

fn install_source(
    source: &Path,
    data_dir: &Path,
    status: &Arc<RwLock<ModelInstallStatus>>,
) -> SetupResult<ModelInstallResult> {
    let info = inspect_source(source)?;
    if !info.runtime_compatible {
        return Err(ModelSetupError::new(
            "MODEL_BUNDLE_INCOMPATIBLE",
            format!(
                "模型包要求 Runtime [{} , {})，当前版本为 {RUNTIME_VERSION}。",
                info.runtime_min_inclusive, info.runtime_max_exclusive
            ),
        ));
    }
    let models_root = data_dir.join("models");
    fs::create_dir_all(&models_root).map_err(io_error("MODEL_INSTALL_FAILED"))?;
    let required = info.uncompressed_size_bytes.saturating_add(
        info.uncompressed_size_bytes
            .saturating_mul(SAFETY_MARGIN_PERCENT)
            / 100,
    );
    let available = available_space(&models_root).map_err(io_error("MODEL_INSTALL_FAILED"))?;
    if available < required {
        return Err(ModelSetupError::new(
            "MODEL_DISK_SPACE_INSUFFICIENT",
            format!("模型安装至少需要 {required} 字节可用空间，当前仅有 {available} 字节。"),
        ));
    }

    set_shared_status(
        status,
        "installing",
        Some(info.bundle_version.clone()),
        None,
    );
    let installation_id = Uuid::new_v4().simple().to_string();
    let staging = models_root.join(format!(
        "{}.installing-{installation_id}",
        info.bundle_version
    ));
    if staging.exists() {
        return Err(ModelSetupError::new(
            "MODEL_INSTALL_FAILED",
            "模型安装 staging 目录已存在。",
        ));
    }
    fs::create_dir_all(&staging).map_err(io_error("MODEL_INSTALL_FAILED"))?;
    let install_result = (|| {
        match source_type(source)? {
            ModelSource::Directory(directory) => copy_directory(&directory, &staging)?,
            ModelSource::Zip(archive) => extract_zip(&archive, &staging)?,
        }
        set_shared_status(
            status,
            "validating",
            Some(info.bundle_version.clone()),
            None,
        );
        let staged_root = locate_manifest_root(&staging)?;
        let manifest = validate_installed_bundle(&staged_root)?;
        if manifest.bundle_version != info.bundle_version {
            return Err(ModelSetupError::new(
                "MODEL_BUNDLE_INVALID",
                "安装后的模型版本与预检结果不一致。",
            ));
        }

        let destination = models_root.join(&manifest.bundle_version);
        if destination.exists() {
            if validate_installed_bundle(&destination).is_ok() {
                activate_bundle(&models_root, &manifest.bundle_version)?;
                return Ok(ModelInstallResult {
                    bundle_version: manifest.bundle_version,
                    validation_status: "ready".to_string(),
                    reused_existing: true,
                });
            }
            let preserved = models_root.join(format!(
                "{}.invalid-{installation_id}",
                manifest.bundle_version
            ));
            fs::rename(&destination, preserved).map_err(io_error("MODEL_INSTALL_FAILED"))?;
        }
        fs::rename(&staged_root, &destination).map_err(io_error("MODEL_INSTALL_FAILED"))?;
        activate_bundle(&models_root, &manifest.bundle_version)?;
        Ok(ModelInstallResult {
            bundle_version: manifest.bundle_version,
            validation_status: "ready".to_string(),
            reused_existing: false,
        })
    })();
    if staging.exists() {
        let _ = fs::remove_dir_all(&staging);
    }
    install_result
}

fn set_shared_status(
    status: &Arc<RwLock<ModelInstallStatus>>,
    state: &str,
    bundle_version: Option<String>,
    error: Option<(String, String)>,
) {
    let mut current = status.write().expect("model setup status poisoned");
    current.state = state.to_string();
    current.bundle_version = bundle_version;
    current.error_code = error.as_ref().map(|item| item.0.clone());
    current.error_message = error.map(|item| item.1);
}

fn load_directory_manifest(directory: &Path) -> SetupResult<ModelManifest> {
    let root = locate_manifest_root(directory)?;
    let payload = fs::read(root.join("manifest.json")).map_err(io_error("MODEL_BUNDLE_INVALID"))?;
    serde_json::from_slice(&payload).map_err(|_| {
        ModelSetupError::new("MODEL_BUNDLE_INVALID", "模型包 manifest.json 无法解析。")
    })
}

fn locate_manifest_root(directory: &Path) -> SetupResult<PathBuf> {
    if directory.join("manifest.json").is_file() {
        return Ok(directory.to_path_buf());
    }
    let mut candidates = Vec::new();
    for entry in fs::read_dir(directory).map_err(io_error("MODEL_BUNDLE_INVALID"))? {
        let entry = entry.map_err(io_error("MODEL_BUNDLE_INVALID"))?;
        if entry
            .file_type()
            .map_err(io_error("MODEL_BUNDLE_INVALID"))?
            .is_dir()
            && entry.path().join("manifest.json").is_file()
        {
            candidates.push(entry.path());
        }
    }
    if candidates.len() == 1 {
        return Ok(candidates.remove(0));
    }
    Err(ModelSetupError::new(
        "MODEL_BUNDLE_INVALID",
        "模型包根目录必须包含且只能包含一个 manifest.json。",
    ))
}

fn validate_manifest_shape(manifest: &ModelManifest) -> SetupResult<()> {
    if manifest.schema_version != 1
        || !valid_bundle_version(&manifest.bundle_version)
        || !safe_relative_path(&manifest.bundle_version)
    {
        return Err(ModelSetupError::new(
            "MODEL_BUNDLE_INVALID",
            "模型包 manifest 版本字段无效。",
        ));
    }
    let required = HashSet::from([
        "detector",
        "ocr_detection",
        "ocr_recognition",
        "ocr_orientation",
        "baseline",
        "vlm",
    ]);
    if required
        .iter()
        .any(|name| !manifest.models.contains_key(*name))
    {
        return Err(ModelSetupError::new(
            "MODEL_BUNDLE_INVALID",
            "模型包缺少必需组件。",
        ));
    }
    for artifact in manifest.models.values() {
        if !safe_relative_path(&artifact.path)
            || !matches!(artifact.kind.as_str(), "file" | "directory")
            || artifact.required && artifact.size_bytes == 0
            || artifact.kind == "file"
                && artifact
                    .sha256
                    .as_ref()
                    .is_none_or(|hash| !valid_hash(hash))
            || artifact
                .files
                .iter()
                .any(|item| !safe_relative_path(&item.path) || !valid_hash(&item.sha256))
        {
            return Err(ModelSetupError::new(
                "MODEL_BUNDLE_INVALID",
                "模型包 manifest 包含无效路径、类型或哈希。",
            ));
        }
    }
    Ok(())
}

fn manifest_size(manifest: &ModelManifest) -> u64 {
    manifest
        .models
        .values()
        .map(|artifact| artifact.size_bytes)
        .sum()
}

fn runtime_compatible(manifest: &ModelManifest) -> SetupResult<bool> {
    Ok(version_tuple(&manifest.compatible_runtime.min_inclusive)?
        <= version_tuple(RUNTIME_VERSION)?
        && version_tuple(RUNTIME_VERSION)?
            < version_tuple(&manifest.compatible_runtime.max_exclusive)?)
}

fn version_tuple(value: &str) -> SetupResult<Vec<u64>> {
    value
        .split('.')
        .map(|part| {
            part.parse::<u64>().map_err(|_| {
                ModelSetupError::new("MODEL_BUNDLE_INVALID", "Runtime 兼容版本格式无效。")
            })
        })
        .collect()
}

fn directory_size(path: &Path) -> SetupResult<u64> {
    let mut total = 0_u64;
    for entry in walk_directory(path)? {
        total = total
            .checked_add(
                entry
                    .metadata()
                    .map_err(io_error("MODEL_BUNDLE_INVALID"))?
                    .len(),
            )
            .ok_or_else(|| ModelSetupError::new("MODEL_BUNDLE_INVALID", "模型目录体积溢出。"))?;
    }
    Ok(total)
}

fn walk_directory(root: &Path) -> SetupResult<Vec<fs::DirEntry>> {
    let mut files = Vec::new();
    let mut directories = vec![root.to_path_buf()];
    while let Some(directory) = directories.pop() {
        for entry in fs::read_dir(directory).map_err(io_error("MODEL_BUNDLE_INVALID"))? {
            let entry = entry.map_err(io_error("MODEL_BUNDLE_INVALID"))?;
            let metadata =
                fs::symlink_metadata(entry.path()).map_err(io_error("MODEL_BUNDLE_INVALID"))?;
            if metadata.file_type().is_symlink() {
                return Err(ModelSetupError::new(
                    "MODEL_BUNDLE_INVALID",
                    "模型目录不能包含符号链接。",
                ));
            }
            if metadata.is_dir() {
                directories.push(entry.path());
            } else if metadata.is_file() {
                files.push(entry);
            }
        }
    }
    Ok(files)
}

fn copy_directory(source: &Path, destination: &Path) -> SetupResult<()> {
    let root = locate_manifest_root(source)?;
    for entry in walk_directory(&root)? {
        let relative = entry
            .path()
            .strip_prefix(&root)
            .map_err(|_| ModelSetupError::new("MODEL_BUNDLE_INVALID", "模型目录路径越界。"))?
            .to_path_buf();
        let target = destination.join(relative);
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent).map_err(io_error("MODEL_INSTALL_FAILED"))?;
        }
        copy_file_buffered(&entry.path(), &target)?;
    }
    Ok(())
}

fn copy_file_buffered(source: &Path, destination: &Path) -> SetupResult<()> {
    let mut input = File::open(source).map_err(io_error("MODEL_INSTALL_FAILED"))?;
    let mut output = File::create(destination).map_err(io_error("MODEL_INSTALL_FAILED"))?;
    let mut buffer = vec![0_u8; COPY_BUFFER_SIZE];
    loop {
        let count = input
            .read(&mut buffer)
            .map_err(io_error("MODEL_INSTALL_FAILED"))?;
        if count == 0 {
            break;
        }
        output
            .write_all(&buffer[..count])
            .map_err(io_error("MODEL_INSTALL_FAILED"))?;
    }
    output.sync_all().map_err(io_error("MODEL_INSTALL_FAILED"))
}

fn manifest_from_zip<R: Read + io::Seek>(
    archive: &mut ZipArchive<R>,
) -> SetupResult<(ModelManifest, PathBuf)> {
    let mut manifests = Vec::new();
    for index in 0..archive.len() {
        let item = archive.by_index(index).map_err(zip_error)?;
        let enclosed = item
            .enclosed_name()
            .ok_or_else(zip_slip_error)?
            .to_path_buf();
        reject_zip_symlink(&item)?;
        if enclosed
            .file_name()
            .is_some_and(|name| name == "manifest.json")
            && enclosed.components().count() <= 2
        {
            manifests.push((index, enclosed));
        }
    }
    if manifests.len() != 1 {
        return Err(ModelSetupError::new(
            "MODEL_BUNDLE_INVALID",
            "ZIP 必须包含且只能包含一个根级 manifest.json。",
        ));
    }
    let (index, path) = manifests.remove(0);
    let mut item = archive.by_index(index).map_err(zip_error)?;
    let mut payload = Vec::new();
    item.read_to_end(&mut payload)
        .map_err(io_error("MODEL_BUNDLE_INVALID"))?;
    let manifest = serde_json::from_slice(&payload).map_err(|_| {
        ModelSetupError::new("MODEL_BUNDLE_INVALID", "ZIP 中的 manifest.json 无法解析。")
    })?;
    let prefix = path.parent().unwrap_or_else(|| Path::new("")).to_path_buf();
    Ok((manifest, prefix))
}

fn extract_zip(archive_path: &Path, destination: &Path) -> SetupResult<()> {
    let file = File::open(archive_path).map_err(io_error("MODEL_BUNDLE_INVALID"))?;
    let mut archive = ZipArchive::new(file).map_err(zip_error)?;
    let (_, prefix) = manifest_from_zip(&mut archive)?;
    for index in 0..archive.len() {
        let mut item = archive.by_index(index).map_err(zip_error)?;
        reject_zip_symlink(&item)?;
        let enclosed = item
            .enclosed_name()
            .ok_or_else(zip_slip_error)?
            .to_path_buf();
        let relative = enclosed
            .strip_prefix(&prefix)
            .map_err(|_| zip_slip_error())?;
        if relative.as_os_str().is_empty() {
            continue;
        }
        let target = destination.join(relative);
        if !target.starts_with(destination) {
            return Err(zip_slip_error());
        }
        if item.is_dir() {
            fs::create_dir_all(&target).map_err(io_error("MODEL_INSTALL_FAILED"))?;
        } else {
            if let Some(parent) = target.parent() {
                fs::create_dir_all(parent).map_err(io_error("MODEL_INSTALL_FAILED"))?;
            }
            let mut output = File::create(&target).map_err(io_error("MODEL_INSTALL_FAILED"))?;
            io::copy(&mut item, &mut output).map_err(io_error("MODEL_INSTALL_FAILED"))?;
            output
                .sync_all()
                .map_err(io_error("MODEL_INSTALL_FAILED"))?;
        }
    }
    Ok(())
}

fn reject_zip_symlink(item: &zip::read::ZipFile<'_>) -> SetupResult<()> {
    if item
        .unix_mode()
        .is_some_and(|mode| mode & 0o170000 == 0o120000)
    {
        return Err(ModelSetupError::new(
            "MODEL_BUNDLE_INVALID",
            "ZIP 模型包不能包含符号链接。",
        ));
    }
    Ok(())
}

fn validate_installed_bundle(root: &Path) -> SetupResult<ModelManifest> {
    let manifest = load_directory_manifest(root)?;
    validate_manifest_shape(&manifest)?;
    if !runtime_compatible(&manifest)? {
        return Err(ModelSetupError::new(
            "MODEL_BUNDLE_INCOMPATIBLE",
            "模型包与当前 Runtime 不兼容。",
        ));
    }
    for artifact in manifest.models.values() {
        let target = safe_join(root, &artifact.path)?;
        match artifact.kind.as_str() {
            "file" => validate_file(
                &target,
                artifact.size_bytes,
                artifact.sha256.as_deref().ok_or_else(|| {
                    ModelSetupError::new("MODEL_BUNDLE_INVALID", "模型文件缺少 SHA-256。")
                })?,
            )?,
            "directory" => {
                if !target.is_dir() {
                    return Err(ModelSetupError::new(
                        "MODEL_HASH_MISMATCH",
                        "模型组件目录缺失。",
                    ));
                }
                for file in &artifact.files {
                    validate_file(
                        &safe_join(&target, &file.path)?,
                        file.size_bytes,
                        &file.sha256,
                    )?;
                }
            }
            _ => unreachable!(),
        }
    }
    Ok(manifest)
}

fn validate_file(path: &Path, expected_size: u64, expected_hash: &str) -> SetupResult<()> {
    let metadata = path
        .metadata()
        .map_err(|_| ModelSetupError::new("MODEL_HASH_MISMATCH", "模型文件缺失或无法读取。"))?;
    if !metadata.is_file() || metadata.len() != expected_size || sha256(path)? != expected_hash {
        return Err(ModelSetupError::new(
            "MODEL_HASH_MISMATCH",
            "模型文件大小或 SHA-256 不匹配。",
        ));
    }
    Ok(())
}

fn sha256(path: &Path) -> SetupResult<String> {
    let mut input = File::open(path).map_err(io_error("MODEL_HASH_MISMATCH"))?;
    let mut digest = Sha256::new();
    let mut buffer = vec![0_u8; COPY_BUFFER_SIZE];
    loop {
        let count = input
            .read(&mut buffer)
            .map_err(io_error("MODEL_HASH_MISMATCH"))?;
        if count == 0 {
            break;
        }
        digest.update(&buffer[..count]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn activate_bundle(models_root: &Path, bundle_version: &str) -> SetupResult<()> {
    let pointer = ActiveModelPointer {
        schema_version: 1,
        bundle_version: bundle_version.to_string(),
        directory: bundle_version.to_string(),
    };
    let temporary = models_root.join(format!("active.{}.tmp", Uuid::new_v4().simple()));
    fs::write(
        &temporary,
        serde_json::to_vec_pretty(&pointer).expect("active model pointer serializes"),
    )
    .map_err(io_error("MODEL_INSTALL_FAILED"))?;
    let active = models_root.join("active.json");
    let previous = models_root.join("active.previous.json");
    if active.exists() {
        let _ = fs::remove_file(&previous);
        fs::rename(&active, &previous).map_err(io_error("MODEL_INSTALL_FAILED"))?;
    }
    if let Err(error) = fs::rename(&temporary, &active) {
        if previous.exists() {
            let _ = fs::rename(&previous, &active);
        }
        return Err(ModelSetupError::new(
            "MODEL_INSTALL_FAILED",
            error.to_string(),
        ));
    }
    Ok(())
}

fn safe_join(root: &Path, relative: &str) -> SetupResult<PathBuf> {
    if !safe_relative_path(relative) {
        return Err(ModelSetupError::new(
            "MODEL_BUNDLE_INVALID",
            "模型清单包含越界路径。",
        ));
    }
    Ok(root.join(relative.replace('/', std::path::MAIN_SEPARATOR_STR)))
}

fn safe_relative_path(value: &str) -> bool {
    let path = Path::new(value);
    !value.is_empty()
        && !path.is_absolute()
        && path
            .components()
            .all(|component| matches!(component, Component::Normal(_)))
}

fn valid_hash(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
}

fn valid_bundle_version(value: &str) -> bool {
    value.strip_prefix("models-v").is_some_and(|suffix| {
        !suffix.is_empty()
            && suffix
                .split('.')
                .all(|part| !part.is_empty() && part.bytes().all(|byte| byte.is_ascii_digit()))
    })
}

fn io_error(code: &'static str) -> impl FnOnce(io::Error) -> ModelSetupError {
    move |error| ModelSetupError::new(code, error.to_string())
}

fn zip_error(error: zip::result::ZipError) -> ModelSetupError {
    ModelSetupError::new("MODEL_BUNDLE_INVALID", error.to_string())
}

fn zip_slip_error() -> ModelSetupError {
    ModelSetupError::new(
        "MODEL_BUNDLE_INVALID",
        "ZIP 包含不安全路径或链接，已拒绝解压。",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;
    use zip::{write::SimpleFileOptions, ZipWriter};

    fn test_manifest(hash: &str) -> String {
        serde_json::json!({
            "schema_version": 1,
            "bundle_version": "models-v1",
            "compatible_runtime": {"min_inclusive": "0.1.0", "max_exclusive": "0.2.0"},
            "models": {
                "detector": {"path": "detector.bin", "kind": "file", "required": true, "size_bytes": 1, "sha256": hash, "files": []},
                "ocr_detection": {"path": "ocr-det.bin", "kind": "file", "required": true, "size_bytes": 1, "sha256": hash, "files": []},
                "ocr_recognition": {"path": "ocr-rec.bin", "kind": "file", "required": true, "size_bytes": 1, "sha256": hash, "files": []},
                "ocr_orientation": {"path": "ocr-ori.bin", "kind": "file", "required": true, "size_bytes": 1, "sha256": hash, "files": []},
                "baseline": {"path": "baseline.bin", "kind": "file", "required": true, "size_bytes": 1, "sha256": hash, "files": []},
                "vlm": {"path": "vlm.bin", "kind": "file", "required": true, "size_bytes": 1, "sha256": hash, "files": []}
            }
        }).to_string()
    }

    #[test]
    fn relative_paths_reject_traversal_and_absolute_paths() {
        assert!(safe_relative_path("vlm/model.safetensors"));
        assert!(!safe_relative_path("../outside"));
        assert!(!safe_relative_path("C:\\outside"));
        assert!(!safe_relative_path("/outside"));
    }

    #[test]
    fn active_pointer_cannot_escape_models_root() {
        let root = std::env::temp_dir().join(format!("visionguard-active-{}", Uuid::new_v4()));
        fs::create_dir_all(root.join("models")).unwrap();
        fs::write(
            root.join("models/active.json"),
            r#"{"schema_version":1,"bundle_version":"models-v1","directory":"../escape"}"#,
        )
        .unwrap();
        assert!(active_bundle_path(&root).is_none());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn zip_slip_entry_is_rejected() {
        let cursor = Cursor::new(Vec::new());
        let mut writer = ZipWriter::new(cursor);
        writer
            .start_file("../escape", SimpleFileOptions::default())
            .unwrap();
        writer.write_all(b"x").unwrap();
        writer
            .start_file("manifest.json", SimpleFileOptions::default())
            .unwrap();
        writer
            .write_all(test_manifest(&"0".repeat(64)).as_bytes())
            .unwrap();
        let bytes = writer.finish().unwrap().into_inner();
        let mut archive = ZipArchive::new(Cursor::new(bytes)).unwrap();
        assert!(manifest_from_zip(&mut archive).is_err());
    }

    #[test]
    fn full_validation_detects_tampered_model_file() {
        let root = std::env::temp_dir().join(format!("visionguard-models-{}", Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap();
        let hash = format!("{:x}", Sha256::digest(b"x"));
        fs::write(root.join("manifest.json"), test_manifest(&hash)).unwrap();
        for name in [
            "detector.bin",
            "ocr-det.bin",
            "ocr-rec.bin",
            "ocr-ori.bin",
            "baseline.bin",
            "vlm.bin",
        ] {
            fs::write(root.join(name), b"x").unwrap();
        }
        assert!(validate_installed_bundle(&root).is_ok());
        fs::write(root.join("vlm.bin"), b"tampered").unwrap();
        let error = validate_installed_bundle(&root).unwrap_err();
        assert_eq!(error.code, "MODEL_HASH_MISMATCH");
        fs::remove_dir_all(root).unwrap();
    }
}
