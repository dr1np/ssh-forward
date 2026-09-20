use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConnectionType {
    Config,
    Custom,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LocalBind {
    #[serde(rename = "127.0.0.1")]
    LoopbackV4,
    #[serde(rename = "0.0.0.0")]
    AnyV4,
    #[serde(rename = "::1")]
    LoopbackV6,
}

impl LocalBind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::LoopbackV4 => "127.0.0.1",
            Self::AnyV4 => "0.0.0.0",
            Self::LoopbackV6 => "::1",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TunnelStatus {
    Connecting,
    Running,
    Stopping,
    Stopped,
    Failed,
}

impl TunnelStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Connecting => "connecting",
            Self::Running => "running",
            Self::Stopping => "stopping",
            Self::Stopped => "stopped",
            Self::Failed => "failed",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ForwardProfile {
    pub id: String,
    pub name: String,
    pub connection_type: ConnectionType,
    pub ssh_host: String,
    pub ssh_port: u32,
    pub ssh_user: String,
    pub identity_file: String,
    pub local_bind: LocalBind,
    pub local_port: u32,
    pub remote_host: String,
    pub remote_port: u32,
}

impl ForwardProfile {
    pub fn new(
        name: &str,
        ssh_host: &str,
        local_port: u32,
        remote_host: &str,
        remote_port: u32,
    ) -> Self {
        Self {
            id: uuid::Uuid::new_v4().simple().to_string(),
            name: name.into(),
            connection_type: ConnectionType::Config,
            ssh_host: ssh_host.into(),
            ssh_port: 22,
            ssh_user: String::new(),
            identity_file: String::new(),
            local_bind: LocalBind::LoopbackV4,
            local_port,
            remote_host: remote_host.into(),
            remote_port,
        }
    }

    pub fn new_custom(
        name: &str,
        ssh_host: &str,
        ssh_port: u32,
        ssh_user: &str,
        identity_file: &str,
        local_port: u32,
        remote_host: &str,
        remote_port: u32,
    ) -> Self {
        Self {
            id: uuid::Uuid::new_v4().simple().to_string(),
            name: name.into(),
            connection_type: ConnectionType::Custom,
            ssh_host: ssh_host.into(),
            ssh_port,
            ssh_user: ssh_user.into(),
            identity_file: identity_file.into(),
            local_bind: LocalBind::LoopbackV4,
            local_port,
            remote_host: remote_host.into(),
            remote_port,
        }
    }

    pub fn ssh_destination(&self) -> String {
        if self.connection_type == ConnectionType::Custom && !self.ssh_user.trim().is_empty() {
            format!("{}@{}", self.ssh_user.trim(), self.ssh_host.trim())
        } else {
            self.ssh_host.trim().to_string()
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.name.trim().is_empty() {
            return Err("configuration name is required".into());
        }
        if self.ssh_host.trim().is_empty() {
            return Err("SSH host is required".into());
        }
        if self.remote_host.trim().is_empty() {
            return Err("remote host is required".into());
        }
        for host in [&self.ssh_host, &self.remote_host] {
            if host.chars().any(char::is_whitespace) || host.starts_with('-') || host.contains('\0')
            {
                return Err("host contains invalid characters".into());
            }
        }
        for port in [self.ssh_port, self.local_port, self.remote_port] {
            if !(1..=65535).contains(&port) {
                return Err("port must be between 1 and 65535".into());
            }
        }
        if self.id.trim().is_empty() {
            return Err("profile id is required".into());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::{ConnectionType, ForwardProfile, LocalBind, TunnelStatus};

    #[test]
    fn validates_a_config_profile_and_builds_destination() {
        let profile = ForwardProfile::new("db", "production", 15432, "127.0.0.1", 5432);
        profile.validate().unwrap();
        assert_eq!(profile.ssh_destination(), "production");
        assert_eq!(profile.local_bind, LocalBind::LoopbackV4);
        assert_eq!(profile.connection_type, ConnectionType::Config);
    }

    #[test]
    fn builds_custom_user_destination() {
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
        profile.validate().unwrap();
        assert_eq!(profile.ssh_destination(), "alice@10.0.0.8");
    }

    #[test]
    fn rejects_invalid_ports_and_host_arguments() {
        let mut profile = ForwardProfile::new("bad", "server", 1, "localhost", 80);
        profile.local_port = 0;
        assert!(profile.validate().is_err());
        profile.local_port = 65536;
        assert!(profile.validate().is_err());
        profile.local_port = 8080;
        profile.ssh_host = "-oProxyCommand=bad".into();
        assert!(profile.validate().is_err());
        profile.ssh_host = "two hosts".into();
        assert!(profile.validate().is_err());
    }

    #[test]
    fn serializes_frontend_status_values() {
        assert_eq!(TunnelStatus::Connecting.as_str(), "connecting");
        assert_eq!(TunnelStatus::Running.as_str(), "running");
        assert_eq!(TunnelStatus::Stopping.as_str(), "stopping");
        assert_eq!(TunnelStatus::Stopped.as_str(), "stopped");
        assert_eq!(TunnelStatus::Failed.as_str(), "failed");
        assert_eq!(
            serde_json::to_string(&TunnelStatus::Running).unwrap(),
            "\"running\""
        );
    }
}
