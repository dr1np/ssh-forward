use std::collections::HashSet;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

const WILDCARD_MARKERS: &[char] = &['*', '?', '!', '['];

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
    let text = text.strip_prefix('\u{feff}').unwrap_or(&text);
    for line in text.lines() {
        let Some((key, values)) = split_config_line(line) else {
            continue;
        };
        if key == "include" {
            let parent = resolved.parent().unwrap_or_else(|| Path::new("."));
            for pattern in values {
                for included in expand_include(&pattern, parent) {
                    parse_file(&included, hosts, seen_hosts, visited);
                }
            }
        } else if key == "host" {
            for host in values {
                if host.starts_with('!') || host.chars().any(|ch| WILDCARD_MARKERS.contains(&ch)) {
                    continue;
                }
                let normalized = host.to_lowercase();
                if seen_hosts.insert(normalized) {
                    hosts.push(host);
                }
            }
        }
    }
}

fn split_config_line(line: &str) -> Option<(String, Vec<String>)> {
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut quote = None;
    let mut escaped = false;
    let mut started = false;

    for ch in line.chars() {
        if escaped {
            current.push(ch);
            escaped = false;
            started = true;
            continue;
        }

        match quote {
            Some('\'') => {
                if ch == '\'' {
                    quote = None;
                } else {
                    current.push(ch);
                }
            }
            Some('"') => {
                if ch == '"' {
                    quote = None;
                } else if ch == '\\' {
                    escaped = true;
                } else {
                    current.push(ch);
                }
            }
            Some(_) => unreachable!(),
            None => match ch {
                '\\' => {
                    escaped = true;
                    started = true;
                }
                '\'' | '"' => {
                    quote = Some(ch);
                    started = true;
                }
                '#' => break,
                ch if ch.is_whitespace() => {
                    if started {
                        tokens.push(std::mem::take(&mut current));
                        started = false;
                    }
                }
                _ => {
                    current.push(ch);
                    started = true;
                }
            },
        }
    }

    if quote.is_some() || escaped {
        return None;
    }
    if started {
        tokens.push(current);
    }
    if tokens.is_empty() {
        return None;
    }

    let first_token = tokens[0].clone();
    let (key, values) = if let Some((key, first)) = first_token.split_once('=') {
        let mut values = Vec::new();
        if !first.is_empty() {
            values.push(first.to_string());
        }
        values.extend(tokens.into_iter().skip(1));
        (key.to_ascii_lowercase(), values)
    } else if tokens.get(1).map(String::as_str) == Some("=") {
        (
            tokens[0].to_ascii_lowercase(),
            tokens.into_iter().skip(2).collect(),
        )
    } else {
        (
            tokens[0].to_ascii_lowercase(),
            tokens.into_iter().skip(1).collect(),
        )
    };

    Some((key, values))
}

fn expand_include(pattern: &str, parent: &Path) -> Vec<PathBuf> {
    let expanded = expand_variables_and_home(pattern);
    let path = PathBuf::from(expanded);
    let path = if path.is_absolute() {
        path
    } else {
        parent.join(path)
    };
    let pattern = path.to_string_lossy().into_owned();

    if !pattern.chars().any(|ch| ['*', '?', '['].contains(&ch)) {
        return vec![PathBuf::from(pattern)];
    }

    let mut paths = glob::glob(&pattern)
        .into_iter()
        .flat_map(|matches| matches.filter_map(Result::ok))
        .collect::<Vec<_>>();
    paths.sort();
    paths
}

fn expand_variables_and_home(value: &str) -> String {
    let mut expanded = String::with_capacity(value.len());
    let chars: Vec<char> = value.chars().collect();
    let mut index = 0;
    while index < chars.len() {
        match chars[index] {
            '$' => {
                let start = index;
                let (name, end) = if chars.get(index + 1) == Some(&'{') {
                    let mut end = index + 2;
                    while end < chars.len() && chars[end] != '}' {
                        end += 1;
                    }
                    if end >= chars.len() {
                        expanded.push('$');
                        index += 1;
                        continue;
                    }
                    (chars[index + 2..end].iter().collect::<String>(), end + 1)
                } else {
                    let mut end = index + 1;
                    while end < chars.len()
                        && (chars[end].is_ascii_alphanumeric() || chars[end] == '_')
                    {
                        end += 1;
                    }
                    (chars[index + 1..end].iter().collect::<String>(), end)
                };
                if name.is_empty() {
                    expanded.push('$');
                    index += 1;
                } else if let Some(replacement) = env::var_os(&name) {
                    expanded.push_str(&replacement.to_string_lossy());
                    index = end;
                } else {
                    for ch in &chars[start..end] {
                        expanded.push(*ch);
                    }
                    index = end;
                }
            }
            '%' => {
                let start = index;
                if let Some(end_offset) = chars[index + 1..].iter().position(|ch| *ch == '%') {
                    let end = index + 1 + end_offset;
                    let name: String = chars[index + 1..end].iter().collect();
                    if let Some(replacement) = env::var_os(&name) {
                        expanded.push_str(&replacement.to_string_lossy());
                        index = end + 1;
                    } else {
                        for ch in &chars[start..=end] {
                            expanded.push(*ch);
                        }
                        index = end + 1;
                    }
                } else {
                    expanded.push('%');
                    index += 1;
                }
            }
            ch => {
                expanded.push(ch);
                index += 1;
            }
        }
    }

    if expanded == "~" {
        return home_dir().to_string_lossy().into_owned();
    }
    if let Some(rest) = expanded
        .strip_prefix("~/")
        .or_else(|| expanded.strip_prefix("~\\"))
    {
        return home_dir().join(rest).to_string_lossy().into_owned();
    }
    expanded
}

fn home_dir() -> PathBuf {
    env::var_os("HOME")
        .or_else(|| env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
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
    fn follows_quoted_glob_includes_and_ignores_wildcard_hosts() {
        let root =
            std::env::temp_dir().join(format!("ssh-forwarder-rust-glob-{}", uuid::Uuid::new_v4()));
        let fragments = root.join("fragments");
        fs::create_dir_all(&fragments).unwrap();
        let config = root.join("config");
        fs::write(
            &config,
            "Include \"fragments/*.conf\"\nHost \"quoted alias\"\n",
        )
        .unwrap();
        fs::write(fragments.join("02.conf"), "Host second\n").unwrap();
        fs::write(fragments.join("01.conf"), "Host first\nHost ?\n").unwrap();
        assert_eq!(
            discover_ssh_hosts(&config),
            vec!["first", "second", "quoted alias"]
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
