#[cfg(test)]
mod tests {
    use super::build_ssh_command;
    use crate::backend::model::ForwardProfile;

    #[test]
    fn config_profile_uses_alias_and_forward_options() {
        let profile = ForwardProfile::new("db", "production", 15432, "127.0.0.1", 5432);
        let command = build_ssh_command("ssh", &profile, None).unwrap();
        assert_eq!(command.first().unwrap(), "ssh");
        assert!(command.windows(2).any(|items| items == ["-N", "-T"]));
        assert!(command.iter().any(|item| item == "BatchMode=yes"));
        assert!(command
            .iter()
            .any(|item| item == "ExitOnForwardFailure=yes"));
        assert!(command
            .windows(2)
            .any(|items| items == ["-L", "127.0.0.1:15432:127.0.0.1:5432"]));
        assert_eq!(command.last().unwrap(), "production");
    }

    #[test]
    fn custom_profile_includes_user_port_key_and_config_file() {
        let profile = ForwardProfile::new_custom(
            "web",
            "10.0.0.8",
            2222,
            "alice",
            "C:/keys/work key",
            8080,
            "internal.example",
            80,
        );
        let command = build_ssh_command("ssh.exe", &profile, Some("C:/tmp/ssh_config")).unwrap();
        assert!(command.windows(2).any(|items| items == ["-p", "2222"]));
        assert!(command
            .windows(2)
            .any(|items| items == ["-i", "C:/keys/work key"]));
        assert!(command
            .windows(2)
            .any(|items| items == ["-F", "C:/tmp/ssh_config"]));
        assert_eq!(command.last().unwrap(), "alice@10.0.0.8");
    }

    #[test]
    fn ipv6_forward_spec_is_bracketed() {
        let mut profile = ForwardProfile::new("v6", "server", 8080, "2001:db8::1", 443);
        profile.local_bind = crate::backend::model::LocalBind::LoopbackV6;
        let command = build_ssh_command("ssh", &profile, None).unwrap();
        assert!(command
            .windows(2)
            .any(|items| items == ["-L", "[::1]:8080:[2001:db8::1]:443"]));
    }
}
use super::endpoint::format_forward_spec;
use super::model::{ConnectionType, ForwardProfile};
use std::path::PathBuf;

pub fn build_ssh_command(
    ssh_executable: &str,
    profile: &ForwardProfile,
    config_file: Option<&str>,
) -> Result<Vec<String>, String> {
    profile.validate()?;
    let mut command = vec![
        ssh_executable.to_string(),
        "-N".into(),
        "-T".into(),
        "-o".into(),
        "ExitOnForwardFailure=yes".into(),
        "-o".into(),
        "BatchMode=yes".into(),
        "-o".into(),
        "StrictHostKeyChecking=accept-new".into(),
        "-o".into(),
        "ServerAliveInterval=30".into(),
        "-o".into(),
        "ServerAliveCountMax=3".into(),
        "-o".into(),
        "ConnectTimeout=10".into(),
        "-L".into(),
        format_forward_spec(
            profile.local_bind.as_str(),
            profile.local_port,
            &profile.remote_host,
            profile.remote_port,
        ),
    ];
    if let Some(path) = config_file.filter(|path| !path.trim().is_empty()) {
        command.extend(["-F".into(), path.to_string()]);
    }
    if profile.connection_type == ConnectionType::Custom {
        command.extend(["-p".into(), profile.ssh_port.to_string()]);
        if !profile.identity_file.trim().is_empty() {
            command.extend(["-i".into(), expand_identity_path(&profile.identity_file)]);
        }
    }
    command.push(profile.ssh_destination());
    Ok(command)
}

fn expand_identity_path(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed == "~" {
        return home_dir().to_string_lossy().into_owned();
    }
    if let Some(rest) = trimmed
        .strip_prefix("~/")
        .or_else(|| trimmed.strip_prefix("~\\"))
    {
        return home_dir().join(rest).to_string_lossy().into_owned();
    }
    trimmed.to_string()
}

fn home_dir() -> PathBuf {
    std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}
