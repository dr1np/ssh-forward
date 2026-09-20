use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

pub fn discover_ssh_hosts(config_path: &Path) -> Vec<String> {
    let mut hosts = Vec::new();
    let mut seen_hosts = HashSet::new();
    let mut visited = HashSet::new();
    parse_file(config_path, &mut hosts, &mut seen_hosts, &mut visited);
    hosts
}

fn parse_file(
    path: &Path,
    hosts: &mut Vec<String>,
    seen_hosts: &mut HashSet<String>,
    visited: &mut HashSet<PathBuf>,
) {
    let Ok(resolved) = fs::canonicalize(path) else {
        return;
    };
    if !visited.insert(resolved.clone()) {
        return;
    }
    let Ok(text) = fs::read_to_string(&resolved) else {
        return;
    };
    for line in text.lines() {
        let normalized = line.replace('=', " = ");
        let parts: Vec<&str> = normalized.split_whitespace().collect();
        if parts.is_empty() || parts[0].starts_with('#') {
            continue;
        }
        let key_value = parts[0].split_once('=').map(|(key, value)| (key, value));
        let key = key_value
            .map(|(key, _)| key)
            .unwrap_or(parts[0])
            .to_ascii_lowercase();
        let values: Vec<String> = if let Some((_, value)) = key_value {
            std::iter::once(value.to_string())
                .chain(parts.iter().skip(1).map(|v| (*v).to_string()))
                .collect()
        } else if parts.get(1) == Some(&"=") {
            parts.iter().skip(2).map(|v| (*v).to_string()).collect()
        } else {
            parts.iter().skip(1).map(|v| (*v).to_string()).collect()
        };
        if key == "include" {
            for pattern in values {
                let include = if Path::new(&pattern).is_absolute() {
                    PathBuf::from(&pattern)
                } else {
                    resolved.parent().unwrap_or(Path::new(".")).join(&pattern)
                };
                if pattern.contains('*') || pattern.contains('?') {
                    if let Ok(entries) = glob_paths(&include) {
                        for entry in entries {
                            parse_file(&entry, hosts, seen_hosts, visited);
                        }
                    }
                } else {
                    parse_file(&include, hosts, seen_hosts, visited);
                }
            }
        } else if key == "host" {
            for host in values {
                if host.starts_with('!') || host.chars().any(|c| "*?![".contains(c)) {
                    continue;
                }
                let normalized = host.to_ascii_lowercase();
                if seen_hosts.insert(normalized) {
                    hosts.push(host);
                }
            }
        }
    }
}

fn glob_paths(pattern: &Path) -> Result<Vec<PathBuf>, ()> {
    let Some(parent) = pattern.parent() else {
        return Ok(Vec::new());
    };
    let Some(name) = pattern.file_name().and_then(|name| name.to_str()) else {
        return Ok(Vec::new());
    };
    let mut result = Vec::new();
    for entry in fs::read_dir(parent).map_err(|_| ())? {
        let entry = entry.map_err(|_| ())?;
        let candidate = entry.file_name().to_string_lossy().to_string();
        if wildcard_match(name, &candidate) {
            result.push(entry.path());
        }
    }
    result.sort();
    Ok(result)
}

fn wildcard_match(pattern: &str, value: &str) -> bool {
    if pattern == value {
        return true;
    }
    if let Some((prefix, suffix)) = pattern.split_once('*') {
        return value.starts_with(prefix) && value.ends_with(suffix);
    }
    pattern == value
}

#[cfg(test)]
mod tests {
    use super::discover_ssh_hosts;
    use std::fs;

    #[test]
    fn follows_relative_include_and_deduplicates_case_insensitively() {
        let root = std::env::temp_dir().join(format!(
            "ssh-forwarder-rust-config-{}",
            uuid::Uuid::new_v4()
        ));
        fs::create_dir_all(&root).unwrap();
        let config = root.join("config");
        let included = root.join("work.conf");
        fs::write(
            &config,
            "Host alpha beta\nHost *.example !blocked\nInclude work.conf\n",
        )
        .unwrap();
        fs::write(&included, "Host=gamma\nHost = delta\nHost ALPHA\n").unwrap();
        assert_eq!(
            discover_ssh_hosts(&config),
            vec!["alpha", "beta", "gamma", "delta"]
        );
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn ignores_include_cycles_and_missing_files() {
        let root =
            std::env::temp_dir().join(format!("ssh-forwarder-rust-cycle-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap();
        let first = root.join("first");
        let second = root.join("second");
        fs::write(&first, "Include second\nHost first\n").unwrap();
        fs::write(&second, "Include first\nHost second\n").unwrap();
        assert_eq!(discover_ssh_hosts(&first), vec!["second", "first"]);
        assert!(discover_ssh_hosts(&root.join("missing")).is_empty());
        let _ = fs::remove_dir_all(root);
    }
}
