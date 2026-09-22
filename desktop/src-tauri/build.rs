use std::{env, fs, path::Path};

fn is_current(source: &Path, target: &Path) -> std::io::Result<bool> {
    if !target.is_file() {
        return Ok(false);
    }
    let source_metadata = fs::metadata(source)?;
    let target_metadata = fs::metadata(target)?;
    Ok(source_metadata.len() == target_metadata.len()
        && target_metadata.modified()? >= source_metadata.modified()?)
}

fn copy_dir(source: &Path, target: &Path) -> std::io::Result<()> {
    fs::create_dir_all(target)?;
    for entry in fs::read_dir(source)? {
        let entry = entry?;
        let destination = target.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_dir(&entry.path(), &destination)?;
        } else {
            if is_current(&entry.path(), &destination)? {
                continue;
            }
            if destination.exists() {
                fs::remove_file(&destination)?;
            }
            fs::hard_link(entry.path(), &destination)
                .or_else(|_| fs::copy(entry.path(), destination).map(|_| ()))?;
        }
    }
    Ok(())
}

fn main() {
    tauri_build::build();
    let source = Path::new("binaries").join("_internal");
    if source.is_dir() {
        let output = env::var("OUT_DIR").expect("OUT_DIR");
        if let Some(profile_dir) = Path::new(&output).ancestors().nth(3) {
            let target = profile_dir.join("_internal");
            copy_dir(&source, &target).expect("copy PyInstaller runtime support");
        }
    }
}
