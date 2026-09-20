use std::env;
use std::path::PathBuf;

pub fn data_file() -> PathBuf {
    if let Some(override_dir) = env::var_os("SSH_FORWARDER_DATA_DIR") {
        return PathBuf::from(override_dir).join("settings.json");
    }
    #[cfg(windows)]
    let base = env::var_os("APPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| home_dir().join("AppData").join("Roaming"));
    #[cfg(target_os = "macos")]
    let base = home_dir().join("Library").join("Application Support");
    #[cfg(all(unix, not(target_os = "macos")))]
    let base = env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| home_dir().join(".config"));
    base.join("SSHForwarder").join("settings.json")
}

pub fn ssh_config_file() -> Option<PathBuf> {
    env::var_os("SSH_FORWARDER_SSH_CONFIG")
        .map(PathBuf::from)
        .or_else(|| Some(home_dir().join(".ssh").join("config")))
}

pub fn ssh_executable() -> Option<PathBuf> {
    let path = env::var_os("PATH")?;
    for directory in env::split_paths(&path) {
        for name in if cfg!(windows) {
            vec!["ssh.exe", "ssh"]
        } else {
            vec!["ssh"]
        } {
            let candidate = directory.join(name);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

fn home_dir() -> PathBuf {
    env::var_os("HOME")
        .or_else(|| env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}
