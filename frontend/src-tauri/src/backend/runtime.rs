use super::model::{ForwardProfile, TunnelStatus};
use super::ssh::build_ssh_command;
use std::collections::HashMap;
use std::io::{BufRead, BufReader};
use std::net::TcpListener;
use std::path::Path;
use std::process::{Child, ChildStderr, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

#[derive(Debug, Clone)]
pub struct TunnelView {
    pub id: String,
    pub profile: ForwardProfile,
    pub status: TunnelStatus,
    pub elapsed: String,
    pub last_error: String,
}

#[derive(Debug, Clone)]
pub struct TunnelEvent {
    pub event_type: String,
    pub tunnel_id: String,
    pub message: String,
    pub tunnel: Option<TunnelView>,
}

struct RuntimeTunnel {
    id: String,
    profile: ForwardProfile,
    process: Arc<Mutex<Child>>,
    status: TunnelStatus,
    started_at: Instant,
    ended_at: Option<Instant>,
    last_error: String,
}

struct ManagerInner {
    tunnels: HashMap<String, RuntimeTunnel>,
    accepting_starts: bool,
}

pub struct RuntimeTunnelManager {
    inner: Arc<Mutex<ManagerInner>>,
    events: Arc<Mutex<Vec<TunnelEvent>>>,
    ssh_executable: Option<std::path::PathBuf>,
}

impl RuntimeTunnelManager {
    pub fn new(ssh_executable: Option<std::path::PathBuf>) -> Self {
        Self {
            inner: Arc::new(Mutex::new(ManagerInner {
                tunnels: HashMap::new(),
                accepting_starts: true,
            })),
            events: Arc::new(Mutex::new(Vec::new())),
            ssh_executable,
        }
    }

    pub fn ssh_available(&self) -> bool {
        self.ssh_executable.is_some()
    }

    pub fn start(
        &self,
        profile: ForwardProfile,
        config_file: Option<&Path>,
    ) -> Result<TunnelView, String> {
        profile.validate()?;
        let executable = self.ssh_executable.as_ref().ok_or_else(|| {
            "未找到 OpenSSH 客户端。请安装 OpenSSH 并确保 ssh 位于 PATH 中。".to_string()
        })?;
        let local_port =
            u16::try_from(profile.local_port).map_err(|_| "本地端口无效".to_string())?;
        if !local_port_available(profile.local_bind.as_str(), local_port) {
            return Err(format!(
                "本地端口 {}:{} 已被占用。",
                profile.local_bind.as_str(),
                local_port
            ));
        }
        let config = config_file.and_then(|path| path.to_str());
        let args = build_ssh_command(&executable.to_string_lossy(), &profile, config)?;
        let mut command = Command::new(&args[0]);
        command
            .args(&args[1..])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::piped());
        #[cfg(windows)]
        std::os::windows::process::CommandExt::creation_flags(&mut command, 0x08000000);
        let mut child = command
            .spawn()
            .map_err(|error| format!("无法启动 SSH：{error}"))?;
        let stderr = child.stderr.take();
        let process = Arc::new(Mutex::new(child));
        let id = uuid::Uuid::new_v4().simple().to_string();
        let now = Instant::now();
        {
            let mut inner = self
                .inner
                .lock()
                .map_err(|_| "转发状态锁已损坏".to_string())?;
            if !inner.accepting_starts {
                return Err("应用正在关闭，无法启动新的转发。".into());
            }
            inner.tunnels.insert(
                id.clone(),
                RuntimeTunnel {
                    id: id.clone(),
                    profile: profile.clone(),
                    process: process.clone(),
                    status: TunnelStatus::Connecting,
                    started_at: now,
                    ended_at: None,
                    last_error: String::new(),
                },
            );
        }
        self.spawn_watcher(id.clone(), process, stderr);
        Ok(self
            .view(&id)
            .ok_or_else(|| "转发状态创建失败".to_string())?)
    }

    fn spawn_watcher(&self, id: String, process: Arc<Mutex<Child>>, stderr: Option<ChildStderr>) {
        let inner = self.inner.clone();
        let events = self.events.clone();
        thread::spawn(move || {
            let mut messages = Vec::new();
            if let Some(stderr) = stderr {
                for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                    let clean = line.trim().to_string();
                    if !clean.is_empty() {
                        messages.push(clean);
                    }
                }
            }
            let exit_code = process
                .lock()
                .ok()
                .and_then(|mut child| child.wait().ok())
                .and_then(|status| status.code())
                .unwrap_or(-1);
            let ended = Instant::now();
            if let Ok(mut state) = inner.lock() {
                if let Some(tunnel) = state.tunnels.get_mut(&id) {
                    tunnel.ended_at = Some(ended);
                    if let Some(message) = messages.last() {
                        tunnel.last_error = message.clone();
                    }
                    if !matches!(tunnel.status, TunnelStatus::Stopping)
                        && exit_code != 0
                        && tunnel.last_error.is_empty()
                    {
                        tunnel.last_error = format!("SSH 已退出（代码 {exit_code}）");
                    }
                    tunnel.status =
                        if matches!(tunnel.status, TunnelStatus::Stopping) || exit_code == 0 {
                            TunnelStatus::Stopped
                        } else {
                            TunnelStatus::Failed
                        };
                    let message = if tunnel.status == TunnelStatus::Stopped {
                        "转发已停止".to_string()
                    } else {
                        tunnel.last_error.clone()
                    };
                    let view = view_of(tunnel, Instant::now());
                    if let Ok(mut pending) = events.lock() {
                        pending.push(TunnelEvent {
                            event_type: if view.status == TunnelStatus::Stopped {
                                "stopped".into()
                            } else {
                                "exited".into()
                            },
                            tunnel_id: id.clone(),
                            message,
                            tunnel: Some(view),
                        });
                    }
                }
            }
        });
    }

    pub fn refresh_readiness(&self) {
        let ids: Vec<String> = self
            .inner
            .lock()
            .ok()
            .map(|inner| {
                inner
                    .tunnels
                    .values()
                    .filter(|t| t.status == TunnelStatus::Connecting)
                    .map(|t| t.id.clone())
                    .collect()
            })
            .unwrap_or_default();
        for id in ids {
            self.mark_ready(&id);
        }
    }

    fn mark_ready(&self, id: &str) -> bool {
        let mut inner = match self.inner.lock() {
            Ok(value) => value,
            Err(_) => return false,
        };
        let Some(tunnel) = inner.tunnels.get_mut(id) else {
            return false;
        };
        let alive = tunnel
            .process
            .lock()
            .ok()
            .and_then(|mut child| child.try_wait().ok())
            .flatten()
            .is_none();
        if !alive {
            return false;
        }
        if tunnel.status == TunnelStatus::Running {
            return true;
        }
        if tunnel.status != TunnelStatus::Connecting
            || !listener_ready(
                tunnel.profile.local_bind.as_str(),
                tunnel.profile.local_port as u16,
            )
        {
            return false;
        }
        tunnel.status = TunnelStatus::Running;
        let view = view_of(tunnel, Instant::now());
        if let Ok(mut pending) = self.events.lock() {
            pending.push(TunnelEvent {
                event_type: "connected".into(),
                tunnel_id: id.into(),
                message: "SSH 本地监听已就绪".into(),
                tunnel: Some(view),
            });
        }
        true
    }

    pub fn stop(&self, id: &str) -> Result<(), String> {
        let process = {
            let mut inner = self.inner.lock().map_err(|_| "转发状态锁已损坏")?;
            let Some(tunnel) = inner.tunnels.get_mut(id) else {
                return Ok(());
            };
            if matches!(tunnel.status, TunnelStatus::Stopped | TunnelStatus::Failed) {
                return Ok(());
            }
            tunnel.status = TunnelStatus::Stopping;
            tunnel.process.clone()
        };
        let mut child = process.lock().map_err(|_| "SSH 进程锁已损坏")?;
        if child.try_wait().map_err(|e| e.to_string())?.is_none() {
            child.kill().map_err(|e| format!("无法停止 SSH：{e}"))?;
        }
        child
            .wait()
            .map_err(|e| format!("无法确认 SSH 已停止：{e}"))?;
        Ok(())
    }

    pub fn change_port(
        &self,
        id: &str,
        port: u32,
        config_file: Option<&Path>,
    ) -> Result<TunnelView, String> {
        let current = self
            .view(id)
            .ok_or_else(|| "找不到运行中的转发".to_string())?;
        if !matches!(
            current.status,
            TunnelStatus::Connecting | TunnelStatus::Running
        ) {
            return Err("找不到运行中的转发".into());
        }
        let mut replacement_profile = current.profile.clone();
        replacement_profile.local_port = port;
        let candidate = self.start(replacement_profile, config_file)?;
        let deadline = Instant::now() + Duration::from_secs(15);
        loop {
            self.mark_ready(&candidate.id);
            let view = self
                .view(&candidate.id)
                .ok_or_else(|| "新转发状态丢失".to_string())?;
            if view.status == TunnelStatus::Running {
                break;
            }
            if matches!(view.status, TunnelStatus::Failed | TunnelStatus::Stopped)
                || Instant::now() >= deadline
            {
                let _ = self.stop(&candidate.id);
                let _ = self.remove_finished(&candidate.id);
                return Err(view.last_error);
            }
            thread::sleep(Duration::from_millis(100));
        }
        self.stop(id)?;
        self.remove_finished(id);
        self.view(&candidate.id)
            .ok_or_else(|| "新转发状态丢失".to_string())
    }

    pub fn view(&self, id: &str) -> Option<TunnelView> {
        self.inner
            .lock()
            .ok()?
            .tunnels
            .get(id)
            .map(|t| view_of(t, Instant::now()))
    }
    pub fn snapshot(&self) -> Vec<TunnelView> {
        self.inner
            .lock()
            .map(|inner| {
                inner
                    .tunnels
                    .values()
                    .map(|t| view_of(t, Instant::now()))
                    .collect()
            })
            .unwrap_or_default()
    }
    pub fn remove_finished(&self, id: &str) -> bool {
        self.inner
            .lock()
            .ok()
            .and_then(|mut inner| {
                if inner.tunnels.get(id).is_some_and(|t| {
                    matches!(t.status, TunnelStatus::Stopped | TunnelStatus::Failed)
                }) {
                    Some(inner.tunnels.remove(id).is_some())
                } else {
                    Some(false)
                }
            })
            .unwrap_or(false)
    }
    pub fn clear_finished(&self) -> usize {
        let ids: Vec<String> = self
            .inner
            .lock()
            .ok()
            .map(|inner| {
                inner
                    .tunnels
                    .values()
                    .filter(|t| matches!(t.status, TunnelStatus::Stopped | TunnelStatus::Failed))
                    .map(|t| t.id.clone())
                    .collect()
            })
            .unwrap_or_default();
        ids.iter().filter(|id| self.remove_finished(id)).count()
    }
    pub fn shutdown(&self) -> Vec<String> {
        let ids: Vec<String> = self
            .inner
            .lock()
            .ok()
            .map(|mut inner| {
                inner.accepting_starts = false;
                inner
                    .tunnels
                    .values()
                    .filter(|t| {
                        matches!(t.status, TunnelStatus::Connecting | TunnelStatus::Running)
                    })
                    .map(|t| t.id.clone())
                    .collect()
            })
            .unwrap_or_default();
        ids.iter()
            .filter_map(|id| self.stop(id).err().map(|e| format!("{id}: {e}")))
            .collect()
    }
    pub fn drain_events(&self) -> Vec<TunnelEvent> {
        self.events
            .lock()
            .map(|mut events| std::mem::take(&mut *events))
            .unwrap_or_default()
    }
}

fn view_of(tunnel: &RuntimeTunnel, now: Instant) -> TunnelView {
    let end = tunnel.ended_at.unwrap_or(now);
    let elapsed = end.saturating_duration_since(tunnel.started_at).as_secs();
    TunnelView {
        id: tunnel.id.clone(),
        profile: tunnel.profile.clone(),
        status: tunnel.status,
        elapsed: format!("{:02}:{:02}", elapsed / 60, elapsed % 60),
        last_error: tunnel.last_error.clone(),
    }
}
fn local_port_available(bind: &str, port: u16) -> bool {
    TcpListener::bind((bind, port)).is_ok()
}
fn listener_ready(bind: &str, port: u16) -> bool {
    let probe = if bind == "0.0.0.0" { "127.0.0.1" } else { bind };
    std::net::TcpStream::connect((probe, port)).is_ok()
}
