use fs2::available_space;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashSet,
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
const BUFFER_SIZE: usize = 1024 * 1024;

#[derive(Debug, Clone, Deserialize)]
struct RuntimeFile {
    path: String,
    size_bytes: u64,
    sha256: String,
}

#[derive(Debug, Clone, Deserialize)]
struct RuntimeManifest {
    schema_version: u32,
    runtime_version: String,
    platform: String,
    architecture: String,
    entrypoint: String,
    files: Vec<RuntimeFile>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ActiveRuntimePointer {
    schema_version: u32,
    runtime_version: String,
    directory: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct RuntimePackageInfo {
    pub source_kind: String,
    pub runtime_version: String,
    pub platform: String,
    pub architecture: String,
    pub compatible: bool,
    pub compressed_size_bytes: u64,
    pub uncompressed_size_bytes: u64,
    pub validation_status: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct RuntimeInstallResult {
    pub runtime_version: String,
    pub validation_status: String,
    pub reused_existing: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct RuntimeInstallStatus {
    pub state: String,
    pub runtime_version: Option<String>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
}

impl Default for RuntimeInstallStatus {
    fn default() -> Self {
        Self {
            state: "idle".to_string(),
            runtime_version: None,
            error_code: None,
            error_message: None,
        }
    }
}

#[derive(Debug, Serialize)]
struct RuntimePackageError {
    code: &'static str,
    message: String,
}

impl RuntimePackageError {
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

type PackageResult<T> = Result<T, RuntimePackageError>;

pub struct RuntimeInstaller {
    app: AppHandle,
    operation: AsyncMutex<()>,
    status: Arc<RwLock<RuntimeInstallStatus>>,
}

impl RuntimeInstaller {
    pub fn new(app: AppHandle) -> Arc<Self> {
        Arc::new(Self {
            app,
            operation: AsyncMutex::new(()),
            status: Arc::new(RwLock::new(RuntimeInstallStatus::default())),
        })
    }

    pub fn status(&self) -> RuntimeInstallStatus {
        self.status
            .read()
            .expect("runtime install status poisoned")
            .clone()
    }

    pub async fn inspect(&self, source: String) -> Result<RuntimePackageInfo, String> {
        tauri::async_runtime::spawn_blocking(move || inspect_source(&PathBuf::from(source)))
            .await
            .map_err(|error| error.to_string())?
            .map_err(|error| error.json())
    }

    pub async fn install(&self, source: String) -> Result<RuntimeInstallResult, String> {
        let _guard = self.operation.lock().await;
        self.update("inspecting", None, None);
        let data_dir = self
            .app
            .path()
            .app_local_data_dir()
            .map_err(|error| error.to_string())?;
        let shared = Arc::clone(&self.status);
        let result = tauri::async_runtime::spawn_blocking(move || {
            install_source(&PathBuf::from(source), &data_dir, &shared)
        })
        .await
        .map_err(|error| error.to_string())?;
        match result {
            Ok(value) => {
                self.update("ready", Some(value.runtime_version.clone()), None);
                Ok(value)
            }
            Err(error) => {
                self.update(
                    "failed",
                    None,
                    Some((error.code.to_string(), error.message.clone())),
                );
                Err(error.json())
            }
        }
    }

    fn update(&self, state: &str, version: Option<String>, error: Option<(String, String)>) {
        update_status(&self.status, state, version, error);
    }
}

pub fn active_runtime_executable(data_dir: &Path) -> Option<PathBuf> {
    let root = data_dir.join("runtime-components");
    let pointer: ActiveRuntimePointer =
        serde_json::from_slice(&fs::read(root.join("active.json")).ok()?).ok()?;
    if pointer.schema_version != 1 || !safe_relative(&pointer.directory) {
        return None;
    }
    let package = root.join(pointer.directory);
    let manifest = load_manifest(&package).ok()?;
    if manifest.runtime_version != pointer.runtime_version || validate_shape(&manifest).is_err() {
        return None;
    }
    let executable = safe_join(&package, &manifest.entrypoint).ok()?;
    executable.is_file().then_some(executable)
}

fn inspect_source(source: &Path) -> PackageResult<RuntimePackageInfo> {
    if source.is_dir() {
        let root = locate_root(source)?;
        let manifest = load_manifest(&root)?;
        validate_shape(&manifest)?;
        return Ok(RuntimePackageInfo {
            source_kind: "directory".to_string(),
            runtime_version: manifest.runtime_version.clone(),
            platform: manifest.platform.clone(),
            architecture: manifest.architecture.clone(),
            compatible: compatible(&manifest),
            compressed_size_bytes: directory_size(&root)?,
            uncompressed_size_bytes: manifest.files.iter().map(|item| item.size_bytes).sum(),
            validation_status: "selected".to_string(),
        });
    }
    if source.is_file()
        && source
            .extension()
            .is_some_and(|extension| extension.eq_ignore_ascii_case("zip"))
    {
        let mut archive =
            ZipArchive::new(File::open(source).map_err(io_error("RUNTIME_PACKAGE_INVALID"))?)
                .map_err(zip_error)?;
        let (manifest, _) = manifest_from_zip(&mut archive)?;
        validate_shape(&manifest)?;
        let mut size = 0_u64;
        for index in 0..archive.len() {
            let item = archive.by_index(index).map_err(zip_error)?;
            size = size.checked_add(item.size()).ok_or_else(|| {
                RuntimePackageError::new("RUNTIME_PACKAGE_INVALID", "Runtime 包体积字段溢出。")
            })?;
        }
        return Ok(RuntimePackageInfo {
            source_kind: "zip".to_string(),
            runtime_version: manifest.runtime_version.clone(),
            platform: manifest.platform.clone(),
            architecture: manifest.architecture.clone(),
            compatible: compatible(&manifest),
            compressed_size_bytes: source
                .metadata()
                .map_err(io_error("RUNTIME_PACKAGE_INVALID"))?
                .len(),
            uncompressed_size_bytes: size,
            validation_status: "selected".to_string(),
        });
    }
    Err(RuntimePackageError::new(
        "RUNTIME_PACKAGE_INVALID",
        "请选择 Runtime 目录或 .zip 包。",
    ))
}

fn install_source(
    source: &Path,
    data_dir: &Path,
    status: &Arc<RwLock<RuntimeInstallStatus>>,
) -> PackageResult<RuntimeInstallResult> {
    let info = inspect_source(source)?;
    if !info.compatible {
        return Err(RuntimePackageError::new(
            "RUNTIME_PACKAGE_INCOMPATIBLE",
            "Runtime 包与当前 Desktop 或操作系统不兼容。",
        ));
    }
    let root = data_dir.join("runtime-components");
    fs::create_dir_all(&root).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
    let directory_name = format!("runtime-v{}", info.runtime_version);
    let destination = root.join(&directory_name);
    if destination.exists() && validate_installed(&destination).is_ok() {
        activate(&root, &info.runtime_version, &directory_name)?;
        return Ok(RuntimeInstallResult {
            runtime_version: info.runtime_version,
            validation_status: "ready".to_string(),
            reused_existing: true,
        });
    }
    let required = info
        .uncompressed_size_bytes
        .saturating_add(info.uncompressed_size_bytes.saturating_mul(15) / 100);
    let available = available_space(&root).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
    if available < required {
        return Err(RuntimePackageError::new(
            "RUNTIME_DISK_SPACE_INSUFFICIENT",
            format!("Runtime 安装需要 {required} 字节空间，当前仅有 {available} 字节。"),
        ));
    }

    update_status(
        status,
        "installing",
        Some(info.runtime_version.clone()),
        None,
    );
    let id = Uuid::new_v4().simple().to_string();
    let staging = root.join(format!("{directory_name}.installing-{id}"));
    fs::create_dir_all(&staging).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
    let result = (|| {
        if source.is_dir() {
            copy_directory(&locate_root(source)?, &staging)?;
        } else {
            extract_zip(source, &staging)?;
        }
        update_status(
            status,
            "validating",
            Some(info.runtime_version.clone()),
            None,
        );
        let staged_root = locate_root(&staging)?;
        let manifest = validate_installed(&staged_root)?;
        if destination.exists() {
            let preserved = root.join(format!("{directory_name}.invalid-{id}"));
            fs::rename(&destination, preserved).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
        }
        fs::rename(&staged_root, &destination).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
        activate(&root, &manifest.runtime_version, &directory_name)?;
        Ok(RuntimeInstallResult {
            runtime_version: manifest.runtime_version,
            validation_status: "ready".to_string(),
            reused_existing: false,
        })
    })();
    if staging.exists() {
        let _ = fs::remove_dir_all(&staging);
    }
    result
}

fn update_status(
    status: &Arc<RwLock<RuntimeInstallStatus>>,
    state: &str,
    version: Option<String>,
    error: Option<(String, String)>,
) {
    let mut current = status.write().expect("runtime install status poisoned");
    current.state = state.to_string();
    current.runtime_version = version;
    current.error_code = error.as_ref().map(|item| item.0.clone());
    current.error_message = error.map(|item| item.1);
}

fn locate_root(source: &Path) -> PackageResult<PathBuf> {
    if source.join("runtime-manifest.json").is_file() {
        return Ok(source.to_path_buf());
    }
    let mut candidates = Vec::new();
    for entry in fs::read_dir(source).map_err(io_error("RUNTIME_PACKAGE_INVALID"))? {
        let entry = entry.map_err(io_error("RUNTIME_PACKAGE_INVALID"))?;
        if entry
            .file_type()
            .map_err(io_error("RUNTIME_PACKAGE_INVALID"))?
            .is_dir()
            && entry.path().join("runtime-manifest.json").is_file()
        {
            candidates.push(entry.path());
        }
    }
    if candidates.len() == 1 {
        return Ok(candidates.remove(0));
    }
    Err(RuntimePackageError::new(
        "RUNTIME_PACKAGE_INVALID",
        "Runtime 包必须包含且只能包含一个 runtime-manifest.json。",
    ))
}

fn load_manifest(root: &Path) -> PackageResult<RuntimeManifest> {
    serde_json::from_slice(
        &fs::read(root.join("runtime-manifest.json"))
            .map_err(io_error("RUNTIME_PACKAGE_INVALID"))?,
    )
    .map_err(|_| RuntimePackageError::new("RUNTIME_PACKAGE_INVALID", "Runtime manifest 无法解析。"))
}

fn validate_shape(manifest: &RuntimeManifest) -> PackageResult<()> {
    let mut paths = HashSet::new();
    if manifest.schema_version != 1
        || !safe_relative(&manifest.entrypoint)
        || manifest.files.is_empty()
        || manifest.files.iter().any(|item| {
            !safe_relative(&item.path)
                || item.size_bytes == 0
                || !valid_hash(&item.sha256)
                || !paths.insert(item.path.clone())
        })
        || !paths.contains(&manifest.entrypoint)
    {
        return Err(RuntimePackageError::new(
            "RUNTIME_PACKAGE_INVALID",
            "Runtime manifest 的版本、入口、路径或哈希无效。",
        ));
    }
    Ok(())
}

fn compatible(manifest: &RuntimeManifest) -> bool {
    manifest.runtime_version == RUNTIME_VERSION
        && manifest.platform.eq_ignore_ascii_case("windows")
        && manifest.architecture.eq_ignore_ascii_case("x86_64")
}

fn validate_installed(root: &Path) -> PackageResult<RuntimeManifest> {
    let manifest = load_manifest(root)?;
    validate_shape(&manifest)?;
    if !compatible(&manifest) {
        return Err(RuntimePackageError::new(
            "RUNTIME_PACKAGE_INCOMPATIBLE",
            "Runtime package is incompatible.",
        ));
    }
    for item in &manifest.files {
        let target = safe_join(root, &item.path)?;
        let metadata = target
            .metadata()
            .map_err(|_| RuntimePackageError::new("RUNTIME_HASH_MISMATCH", "Runtime 文件缺失。"))?;
        if !metadata.is_file()
            || metadata.len() != item.size_bytes
            || sha256(&target)? != item.sha256
        {
            return Err(RuntimePackageError::new(
                "RUNTIME_HASH_MISMATCH",
                "Runtime 文件大小或 SHA-256 不匹配。",
            ));
        }
    }
    Ok(manifest)
}

fn manifest_from_zip<R: Read + io::Seek>(
    archive: &mut ZipArchive<R>,
) -> PackageResult<(RuntimeManifest, PathBuf)> {
    let mut found = Vec::new();
    for index in 0..archive.len() {
        let item = archive.by_index(index).map_err(zip_error)?;
        reject_zip_entry(&item)?;
        let path = item.enclosed_name().ok_or_else(unsafe_zip)?.to_path_buf();
        if path
            .file_name()
            .is_some_and(|name| name == "runtime-manifest.json")
            && path.components().count() <= 2
        {
            found.push((index, path));
        }
    }
    if found.len() != 1 {
        return Err(RuntimePackageError::new(
            "RUNTIME_PACKAGE_INVALID",
            "ZIP 必须包含一个根级 runtime-manifest.json。",
        ));
    }
    let (index, path) = found.remove(0);
    let mut item = archive.by_index(index).map_err(zip_error)?;
    let mut payload = Vec::new();
    item.read_to_end(&mut payload)
        .map_err(io_error("RUNTIME_PACKAGE_INVALID"))?;
    let manifest = serde_json::from_slice(&payload).map_err(|_| {
        RuntimePackageError::new("RUNTIME_PACKAGE_INVALID", "Runtime manifest 无法解析。")
    })?;
    Ok((
        manifest,
        path.parent().unwrap_or_else(|| Path::new("")).to_path_buf(),
    ))
}

fn extract_zip(source: &Path, destination: &Path) -> PackageResult<()> {
    let mut archive =
        ZipArchive::new(File::open(source).map_err(io_error("RUNTIME_PACKAGE_INVALID"))?)
            .map_err(zip_error)?;
    let (_, prefix) = manifest_from_zip(&mut archive)?;
    for index in 0..archive.len() {
        let mut item = archive.by_index(index).map_err(zip_error)?;
        reject_zip_entry(&item)?;
        let path = item.enclosed_name().ok_or_else(unsafe_zip)?.to_path_buf();
        let relative = path.strip_prefix(&prefix).map_err(|_| unsafe_zip())?;
        if relative.as_os_str().is_empty() {
            continue;
        }
        let target = destination.join(relative);
        if !target.starts_with(destination) {
            return Err(unsafe_zip());
        }
        if item.is_dir() {
            fs::create_dir_all(&target).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
        } else {
            if let Some(parent) = target.parent() {
                fs::create_dir_all(parent).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
            }
            let mut output = File::create(&target).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
            io::copy(&mut item, &mut output).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
            output
                .sync_all()
                .map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
        }
    }
    Ok(())
}

fn reject_zip_entry(item: &zip::read::ZipFile<'_>) -> PackageResult<()> {
    if item.enclosed_name().is_none()
        || item
            .unix_mode()
            .is_some_and(|mode| mode & 0o170000 == 0o120000)
    {
        return Err(unsafe_zip());
    }
    Ok(())
}

fn copy_directory(source: &Path, destination: &Path) -> PackageResult<()> {
    let mut directories = vec![source.to_path_buf()];
    while let Some(directory) = directories.pop() {
        for entry in fs::read_dir(&directory).map_err(io_error("RUNTIME_PACKAGE_INVALID"))? {
            let entry = entry.map_err(io_error("RUNTIME_PACKAGE_INVALID"))?;
            let metadata =
                fs::symlink_metadata(entry.path()).map_err(io_error("RUNTIME_PACKAGE_INVALID"))?;
            if metadata.file_type().is_symlink() {
                return Err(RuntimePackageError::new(
                    "RUNTIME_PACKAGE_INVALID",
                    "Runtime 目录不能包含符号链接。",
                ));
            }
            let relative = entry
                .path()
                .strip_prefix(source)
                .map_err(|_| unsafe_zip())?
                .to_path_buf();
            let target = destination.join(relative);
            if metadata.is_dir() {
                fs::create_dir_all(&target).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
                directories.push(entry.path());
            } else if metadata.is_file() {
                if let Some(parent) = target.parent() {
                    fs::create_dir_all(parent).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
                }
                copy_file(&entry.path(), &target)?;
            }
        }
    }
    Ok(())
}

fn copy_file(source: &Path, target: &Path) -> PackageResult<()> {
    let mut input = File::open(source).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
    let mut output = File::create(target).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
    let mut buffer = vec![0_u8; BUFFER_SIZE];
    loop {
        let count = input
            .read(&mut buffer)
            .map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
        if count == 0 {
            break;
        }
        output
            .write_all(&buffer[..count])
            .map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
    }
    output
        .sync_all()
        .map_err(io_error("RUNTIME_INSTALL_FAILED"))
}

fn directory_size(root: &Path) -> PackageResult<u64> {
    let mut total = 0_u64;
    let mut directories = vec![root.to_path_buf()];
    while let Some(directory) = directories.pop() {
        for entry in fs::read_dir(directory).map_err(io_error("RUNTIME_PACKAGE_INVALID"))? {
            let entry = entry.map_err(io_error("RUNTIME_PACKAGE_INVALID"))?;
            let metadata =
                fs::symlink_metadata(entry.path()).map_err(io_error("RUNTIME_PACKAGE_INVALID"))?;
            if metadata.file_type().is_symlink() {
                return Err(RuntimePackageError::new(
                    "RUNTIME_PACKAGE_INVALID",
                    "Runtime 目录不能包含符号链接。",
                ));
            }
            if metadata.is_dir() {
                directories.push(entry.path());
            } else if metadata.is_file() {
                total = total.checked_add(metadata.len()).ok_or_else(|| {
                    RuntimePackageError::new("RUNTIME_PACKAGE_INVALID", "Runtime 体积溢出。")
                })?;
            }
        }
    }
    Ok(total)
}

fn activate(root: &Path, version: &str, directory: &str) -> PackageResult<()> {
    let pointer = ActiveRuntimePointer {
        schema_version: 1,
        runtime_version: version.to_string(),
        directory: directory.to_string(),
    };
    let temporary = root.join(format!("active.{}.tmp", Uuid::new_v4().simple()));
    fs::write(
        &temporary,
        serde_json::to_vec_pretty(&pointer).expect("runtime pointer serializes"),
    )
    .map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
    let active = root.join("active.json");
    let previous = root.join("active.previous.json");
    if active.exists() {
        let _ = fs::remove_file(&previous);
        fs::rename(&active, &previous).map_err(io_error("RUNTIME_INSTALL_FAILED"))?;
    }
    if let Err(error) = fs::rename(&temporary, &active) {
        if previous.exists() {
            let _ = fs::rename(&previous, &active);
        }
        return Err(RuntimePackageError::new(
            "RUNTIME_INSTALL_FAILED",
            error.to_string(),
        ));
    }
    Ok(())
}

fn sha256(path: &Path) -> PackageResult<String> {
    let mut input = File::open(path).map_err(io_error("RUNTIME_HASH_MISMATCH"))?;
    let mut digest = Sha256::new();
    let mut buffer = vec![0_u8; BUFFER_SIZE];
    loop {
        let count = input
            .read(&mut buffer)
            .map_err(io_error("RUNTIME_HASH_MISMATCH"))?;
        if count == 0 {
            break;
        }
        digest.update(&buffer[..count]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn safe_join(root: &Path, relative: &str) -> PackageResult<PathBuf> {
    if !safe_relative(relative) {
        return Err(unsafe_zip());
    }
    Ok(root.join(relative.replace('/', std::path::MAIN_SEPARATOR_STR)))
}

fn safe_relative(value: &str) -> bool {
    !value.is_empty()
        && !Path::new(value).is_absolute()
        && Path::new(value)
            .components()
            .all(|component| matches!(component, Component::Normal(_)))
}

fn valid_hash(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
}

fn io_error(code: &'static str) -> impl FnOnce(io::Error) -> RuntimePackageError {
    move |error| RuntimePackageError::new(code, error.to_string())
}

fn zip_error(error: zip::result::ZipError) -> RuntimePackageError {
    RuntimePackageError::new("RUNTIME_PACKAGE_INVALID", error.to_string())
}

fn unsafe_zip() -> RuntimePackageError {
    RuntimePackageError::new(
        "RUNTIME_PACKAGE_INVALID",
        "Runtime ZIP 包含不安全路径或链接。",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;
    use zip::{write::SimpleFileOptions, ZipWriter};

    #[test]
    fn active_runtime_pointer_rejects_path_escape() {
        let root = std::env::temp_dir().join(format!("visionguard-runtime-{}", Uuid::new_v4()));
        fs::create_dir_all(root.join("runtime-components")).unwrap();
        fs::write(
            root.join("runtime-components/active.json"),
            r#"{"schema_version":1,"runtime_version":"0.1.0","directory":"../escape"}"#,
        )
        .unwrap();
        assert!(active_runtime_executable(&root).is_none());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn runtime_manifest_requires_its_entrypoint() {
        let manifest = RuntimeManifest {
            schema_version: 1,
            runtime_version: "0.1.0".to_string(),
            platform: "windows".to_string(),
            architecture: "x86_64".to_string(),
            entrypoint: "visionguard-runtime.exe".to_string(),
            files: vec![],
        };
        assert!(validate_shape(&manifest).is_err());
    }

    #[test]
    fn full_runtime_validation_detects_tampering() {
        let root = std::env::temp_dir().join(format!("visionguard-runtime-{}", Uuid::new_v4()));
        fs::create_dir_all(root.join("_internal")).unwrap();
        fs::write(root.join("visionguard-runtime.exe"), b"exe").unwrap();
        fs::write(root.join("_internal/support.dll"), b"dll").unwrap();
        let manifest = serde_json::json!({
            "schema_version": 1,
            "runtime_version": "0.1.0",
            "platform": "windows",
            "architecture": "x86_64",
            "entrypoint": "visionguard-runtime.exe",
            "files": [
                {"path": "visionguard-runtime.exe", "size_bytes": 3, "sha256": format!("{:x}", Sha256::digest(b"exe"))},
                {"path": "_internal/support.dll", "size_bytes": 3, "sha256": format!("{:x}", Sha256::digest(b"dll"))}
            ]
        });
        fs::write(
            root.join("runtime-manifest.json"),
            serde_json::to_vec(&manifest).unwrap(),
        )
        .unwrap();
        assert!(validate_installed(&root).is_ok());
        fs::write(root.join("_internal/support.dll"), b"bad").unwrap();
        assert_eq!(
            validate_installed(&root).unwrap_err().code,
            "RUNTIME_HASH_MISMATCH"
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn runtime_zip_rejects_traversal() {
        let cursor = Cursor::new(Vec::new());
        let mut writer = ZipWriter::new(cursor);
        writer
            .start_file("../outside.dll", SimpleFileOptions::default())
            .unwrap();
        writer.write_all(b"x").unwrap();
        writer
            .start_file("runtime-manifest.json", SimpleFileOptions::default())
            .unwrap();
        writer.write_all(b"{}").unwrap();
        let bytes = writer.finish().unwrap().into_inner();
        let mut archive = ZipArchive::new(Cursor::new(bytes)).unwrap();
        assert!(manifest_from_zip(&mut archive).is_err());
    }
}
