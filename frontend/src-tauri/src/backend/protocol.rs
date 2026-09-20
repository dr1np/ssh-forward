use super::model::ForwardProfile;
use super::paths;
use super::runtime::{RuntimeTunnelManager, TunnelEvent, TunnelView};
use super::ssh_config::discover_ssh_hosts;
use super::storage::ProfileStore;
use serde_json::{json, Value};
use std::path::PathBuf;
use std::sync::Mutex;

pub struct BackendCore {
    store: Mutex<ProfileStore>,
    manager: RuntimeTunnelManager,
    ssh_config_file: Option<PathBuf>,
    command_config_file: Option<PathBuf>,
    load_error: Mutex<Option<String>>,
}

impl BackendCore {
    pub fn new() -> Self {
        let ssh_config_file = paths::ssh_config_file();
        let command_config_file = ssh_config_file.clone().filter(|path| path.is_file());
        Self::with_paths(
            paths::data_file(),
            ssh_config_file,
            command_config_file,
            paths::ssh_executable(),
        )
    }

    fn with_paths(
        data_file: PathBuf,
        ssh_config_file: Option<PathBuf>,
        command_config_file: Option<PathBuf>,
        ssh_executable: Option<PathBuf>,
    ) -> Self {
        let mut store = ProfileStore::new(data_file);
        let load_error = store.load().err();
        Self {
            store: Mutex::new(store),
            manager: RuntimeTunnelManager::new(ssh_executable),
            ssh_config_file,
            command_config_file,
            load_error: Mutex::new(load_error),
        }
    }

    pub fn request(&self, method: &str, params: Value) -> Result<Value, String> {
        self.manager.refresh_readiness();
        match method {
            "get_status" => Ok(json!({"ssh_available": self.manager.ssh_available()})),
            "list_ssh_hosts" => Ok(json!({
                "hosts": self
                    .ssh_config_file
                    .as_deref()
                    .map(discover_ssh_hosts)
                    .unwrap_or_default()
            })),
            "load_profiles" => {
                let store = self.store.lock().map_err(|_| "配置状态锁已损坏")?;
                Ok(
                    json!({"profiles": store.favorites(), "warning": self.load_error.lock().ok().and_then(|error| error.clone())}),
                )
            }
            "get_tunnels" => Ok(
                json!({"tunnels": self.manager.snapshot().iter().map(serialize_tunnel).collect::<Vec<_>>() }),
            ),
            "find_available_port" => {
                let bind = params
                    .get("bind_address")
                    .and_then(Value::as_str)
                    .unwrap_or("127.0.0.1");
                let listener =
                    std::net::TcpListener::bind((bind, 0)).map_err(|error| error.to_string())?;
                Ok(
                    json!({"port": listener.local_addr().map_err(|error| error.to_string())?.port()}),
                )
            }
            "save_profile" => {
                let profile: ForwardProfile =
                    serde_json::from_value(params.get("profile").cloned().ok_or("缺少 profile")?)
                        .map_err(|error| error.to_string())?;
                self.store
                    .lock()
                    .map_err(|_| "配置状态锁已损坏")?
                    .upsert(profile.clone())?;
                *self.load_error.lock().map_err(|_| "配置错误状态锁已损坏")? = None;
                Ok(json!({"profile": profile}))
            }
            "delete_profile" => {
                let id = params
                    .get("profile_id")
                    .and_then(Value::as_str)
                    .ok_or("缺少 profile_id")?;
                self.store
                    .lock()
                    .map_err(|_| "配置状态锁已损坏")?
                    .delete(id)?;
                Ok(json!({"deleted": true}))
            }
            "start_tunnel" => {
                let profile: ForwardProfile =
                    serde_json::from_value(params.get("profile").cloned().ok_or("缺少 profile")?)
                        .map_err(|error| error.to_string())?;
                let tunnel = self
                    .manager
                    .start(profile, self.command_config_file.as_deref())?;
                Ok(json!({"tunnel": serialize_tunnel(&tunnel)}))
            }
            "stop_tunnel" => {
                self.manager.stop(
                    params
                        .get("tunnel_id")
                        .and_then(Value::as_str)
                        .ok_or("缺少 tunnel_id")?,
                )?;
                Ok(json!({"stopped": true}))
            }
            "change_tunnel_port" => {
                let id = params
                    .get("tunnel_id")
                    .and_then(Value::as_str)
                    .ok_or("缺少 tunnel_id")?;
                let port = params
                    .get("local_port")
                    .and_then(Value::as_u64)
                    .ok_or("缺少 local_port")? as u32;
                let tunnel =
                    self.manager
                        .change_port(id, port, self.command_config_file.as_deref())?;
                Ok(json!({"tunnel": serialize_tunnel(&tunnel)}))
            }
            "delete_tunnel" => {
                let id = params
                    .get("tunnel_id")
                    .and_then(Value::as_str)
                    .ok_or("缺少 tunnel_id")?;
                if self.manager.remove_finished(id) || self.manager.view(id).is_none() {
                    Ok(json!({"deleted": true}))
                } else {
                    Err("运行中的转发不能删除，请先停止。".into())
                }
            }
            "clear_finished" => Ok(json!({"removed": self.manager.clear_finished()})),
            "shutdown" => {
                let errors = self.manager.shutdown();
                if errors.is_empty() {
                    Ok(json!({"stopped": true}))
                } else {
                    Err(errors.join("；"))
                }
            }
            _ => Err(format!("未知服务方法：{method}")),
        }
    }

    pub fn drain_events(&self) -> Vec<Value> {
        self.manager
            .drain_events()
            .into_iter()
            .map(serialize_event)
            .collect()
    }
    pub fn shutdown(&self) {
        let _ = self.manager.shutdown();
    }
}

fn serialize_tunnel(tunnel: &TunnelView) -> Value {
    json!({"id": tunnel.id, "profile": tunnel.profile, "status": tunnel.status.as_str(), "elapsed": tunnel.elapsed, "last_error": tunnel.last_error})
}
fn serialize_event(event: TunnelEvent) -> Value {
    json!({"event": "tunnel_event", "data": {"type": event.event_type, "tunnel_id": event.tunnel_id, "message": event.message, "tunnel": event.tunnel.map(|tunnel| serialize_tunnel(&tunnel))}})
}

#[cfg(test)]
mod tests {
    use super::BackendCore;
    use serde_json::json;
    use std::fs;
    #[test]
    fn reports_status_and_hosts_without_python() {
        let root = std::env::temp_dir().join(format!(
            "ssh-forwarder-rust-protocol-{}",
            uuid::Uuid::new_v4()
        ));
        fs::create_dir_all(&root).unwrap();
        let config = root.join("config");
        fs::write(&config, "Host integration\n").unwrap();
        let core = BackendCore::with_paths(root.join("settings.json"), Some(config), None, None);
        assert!(core
            .request("get_status", json!({}))
            .unwrap()
            .get("ssh_available")
            .is_some());
        assert_eq!(
            core.request("list_ssh_hosts", json!({})).unwrap()["hosts"],
            json!(["integration"])
        );
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn rejects_unknown_method() {
        let core = BackendCore::new();
        assert!(core.request("unknown", json!({})).is_err());
    }

    #[test]
    fn profile_methods_round_trip_through_the_protocol() {
        let root = std::env::temp_dir().join(format!(
            "ssh-forwarder-rust-protocol-store-{}",
            uuid::Uuid::new_v4()
        ));
        std::fs::create_dir_all(&root).unwrap();
        let core = BackendCore::with_paths(root.join("settings.json"), None, None, None);
        let profile = super::super::model::ForwardProfile::new(
            "database",
            "production",
            15432,
            "127.0.0.1",
            5432,
        );
        let saved = core
            .request("save_profile", json!({"profile": profile}))
            .unwrap();
        assert_eq!(saved["profile"]["name"], "database");
        let loaded = core.request("load_profiles", json!({})).unwrap();
        assert_eq!(loaded["profiles"].as_array().unwrap().len(), 1);
        let id = saved["profile"]["id"].as_str().unwrap();
        assert_eq!(
            core.request("delete_profile", json!({"profile_id": id}))
                .unwrap()["deleted"],
            true
        );
        assert!(
            core.request("load_profiles", json!({})).unwrap()["profiles"]
                .as_array()
                .unwrap()
                .is_empty()
        );
        let _ = std::fs::remove_dir_all(root);
    }
}
