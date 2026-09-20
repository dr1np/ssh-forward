use super::model::{ForwardProfile, TunnelStatus};
use std::collections::HashMap;
use std::time::{Duration, Instant};

#[derive(Debug, Clone)]
pub struct TunnelRecord {
    id: String,
    profile: ForwardProfile,
    status: TunnelStatus,
    started_at: Instant,
    ended_at: Option<Instant>,
    last_error: String,
}

impl TunnelRecord {
    pub fn id(&self) -> &str {
        &self.id
    }
    pub fn profile(&self) -> &ForwardProfile {
        &self.profile
    }
    pub fn status(&self) -> TunnelStatus {
        self.status
    }
    pub fn last_error(&self) -> &str {
        &self.last_error
    }
    pub fn elapsed(&self, now: Instant) -> Duration {
        self.ended_at
            .unwrap_or(now)
            .saturating_duration_since(self.started_at)
    }
}

#[derive(Debug, Default)]
pub struct TunnelRegistry {
    tunnels: HashMap<String, TunnelRecord>,
    accepting_starts: bool,
}

impl TunnelRegistry {
    pub fn new() -> Self {
        Self {
            tunnels: HashMap::new(),
            accepting_starts: true,
        }
    }
    pub fn register(&mut self, profile: ForwardProfile, now: Instant) -> Result<String, String> {
        if !self.accepting_starts {
            return Err("application is shutting down".into());
        }
        profile.validate()?;
        let id = uuid::Uuid::new_v4().simple().to_string();
        self.tunnels.insert(
            id.clone(),
            TunnelRecord {
                id: id.clone(),
                profile,
                status: TunnelStatus::Connecting,
                started_at: now,
                ended_at: None,
                last_error: String::new(),
            },
        );
        Ok(id)
    }
    pub fn get(&self, id: &str) -> Option<&TunnelRecord> {
        self.tunnels.get(id)
    }
    pub fn mark_running(&mut self, id: &str, process_alive: bool, listener_ready: bool) -> bool {
        let Some(tunnel) = self.tunnels.get_mut(id) else {
            return false;
        };
        if tunnel.status == TunnelStatus::Running {
            return process_alive;
        }
        if tunnel.status != TunnelStatus::Connecting || !process_alive || !listener_ready {
            return false;
        }
        tunnel.status = TunnelStatus::Running;
        true
    }
    pub fn begin_stop(&mut self, id: &str) -> bool {
        let Some(tunnel) = self.tunnels.get_mut(id) else {
            return false;
        };
        match tunnel.status {
            TunnelStatus::Connecting | TunnelStatus::Running => {
                tunnel.status = TunnelStatus::Stopping;
                true
            }
            TunnelStatus::Stopping => true,
            TunnelStatus::Stopped | TunnelStatus::Failed => false,
        }
    }
    pub fn finish_process(
        &mut self,
        id: &str,
        exit_code: i32,
        error: impl Into<String>,
        ended_at: Instant,
    ) -> bool {
        let Some(tunnel) = self.tunnels.get_mut(id) else {
            return false;
        };
        tunnel.ended_at = Some(ended_at);
        let error = error.into();
        if !error.is_empty() {
            tunnel.last_error = error;
        }
        tunnel.status = if tunnel.status == TunnelStatus::Stopping || exit_code == 0 {
            TunnelStatus::Stopped
        } else {
            TunnelStatus::Failed
        };
        true
    }
    pub fn remove_finished(&mut self, id: &str) -> bool {
        if self
            .tunnels
            .get(id)
            .is_some_and(|t| matches!(t.status, TunnelStatus::Stopped | TunnelStatus::Failed))
        {
            self.tunnels.remove(id).is_some()
        } else {
            false
        }
    }
    pub fn shutdown(&mut self) -> Vec<String> {
        self.accepting_starts = false;
        self.tunnels
            .values_mut()
            .filter_map(|t| {
                if matches!(t.status, TunnelStatus::Connecting | TunnelStatus::Running) {
                    t.status = TunnelStatus::Stopping;
                    Some(t.id.clone())
                } else {
                    None
                }
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::TunnelRegistry;
    use crate::backend::model::{ForwardProfile, TunnelStatus};
    use std::time::{Duration, Instant};
    fn profile() -> ForwardProfile {
        ForwardProfile::new("test", "server", 18080, "127.0.0.1", 80)
    }
    #[test]
    fn requires_live_process_and_listener_before_running() {
        let start = Instant::now();
        let mut registry = TunnelRegistry::new();
        let id = registry.register(profile(), start).unwrap();
        assert!(!registry.mark_running(&id, false, true));
        assert_eq!(
            registry.get(&id).unwrap().status(),
            TunnelStatus::Connecting
        );
        assert!(!registry.mark_running(&id, true, false));
        assert_eq!(
            registry.get(&id).unwrap().status(),
            TunnelStatus::Connecting
        );
        assert!(registry.mark_running(&id, true, true));
        assert_eq!(registry.get(&id).unwrap().status(), TunnelStatus::Running);
    }
    #[test]
    fn stop_and_finish_freezes_elapsed_time() {
        let start = Instant::now();
        let ended = start + Duration::from_secs(17);
        let mut registry = TunnelRegistry::new();
        let id = registry.register(profile(), start).unwrap();
        registry.mark_running(&id, true, true);
        assert!(registry.begin_stop(&id));
        registry.finish_process(&id, 0, "", ended);
        let tunnel = registry.get(&id).unwrap();
        assert_eq!(tunnel.status(), TunnelStatus::Stopped);
        assert_eq!(
            tunnel.elapsed(ended + Duration::from_secs(100)),
            Duration::from_secs(17)
        );
    }
    #[test]
    fn unexpected_failure_preserves_error_and_can_be_removed() {
        let start = Instant::now();
        let mut registry = TunnelRegistry::new();
        let id = registry.register(profile(), start).unwrap();
        registry.finish_process(
            &id,
            255,
            "Permission denied",
            start + Duration::from_secs(1),
        );
        assert_eq!(registry.get(&id).unwrap().status(), TunnelStatus::Failed);
        assert_eq!(registry.get(&id).unwrap().last_error(), "Permission denied");
        assert!(registry.remove_finished(&id));
        assert!(registry.get(&id).is_none());
    }
    #[test]
    fn shutdown_is_idempotent_and_blocks_new_tunnels() {
        let now = Instant::now();
        let mut registry = TunnelRegistry::new();
        let id = registry.register(profile(), now).unwrap();
        registry.mark_running(&id, true, true);
        assert_eq!(registry.shutdown(), vec![id]);
        assert!(registry.shutdown().is_empty());
        assert!(registry.register(profile(), now).is_err());
    }
}
