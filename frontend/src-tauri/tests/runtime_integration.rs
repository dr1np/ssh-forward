#![cfg(feature = "test-helper")]

use ssh_forwarder_lib::backend::model::{ForwardProfile, TunnelStatus};
use ssh_forwarder_lib::backend::runtime::{RuntimeTunnelManager, TunnelView};
use std::net::TcpListener;
use std::path::PathBuf;
use std::thread;
use std::time::{Duration, Instant};

fn helper_path() -> PathBuf {
    PathBuf::from(env!("CARGO_BIN_EXE_ssh_forwarder_test_helper"))
}

fn free_port() -> u32 {
    TcpListener::bind(("127.0.0.1", 0))
        .unwrap()
        .local_addr()
        .unwrap()
        .port() as u32
}

fn profile(name: &str, port: u32, host: &str) -> ForwardProfile {
    ForwardProfile::new(name, host, port, "127.0.0.1", 80)
}

fn wait_for_status(manager: &RuntimeTunnelManager, id: &str, expected: TunnelStatus) -> TunnelView {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        manager.refresh_readiness();
        let view = manager.view(id).expect("tunnel should remain registered");
        if view.status == expected {
            return view;
        }
        if matches!(view.status, TunnelStatus::Failed | TunnelStatus::Stopped)
            && view.status != expected
        {
            panic!(
                "unexpected terminal status {:?}: {}",
                view.status, view.last_error
            );
        }
        assert!(
            Instant::now() < deadline,
            "timed out waiting for {expected:?}: {view:?}"
        );
        thread::sleep(Duration::from_millis(20));
    }
}

#[test]
fn runs_stops_and_changes_ports_without_a_python_process() {
    let manager = RuntimeTunnelManager::new(Some(helper_path()));
    let first = manager
        .start(profile("first", free_port(), "fake"), None)
        .unwrap();
    let running = wait_for_status(&manager, &first.id, TunnelStatus::Running);
    assert_eq!(running.profile.name, "first");

    let same_port = manager
        .change_port(&first.id, running.profile.local_port, None)
        .unwrap();
    assert_eq!(same_port.id, first.id);

    let occupied = TcpListener::bind(("127.0.0.1", 0)).unwrap();
    let occupied_port = occupied.local_addr().unwrap().port() as u32;
    assert!(manager.change_port(&first.id, occupied_port, None).is_err());
    assert_eq!(
        manager.view(&first.id).unwrap().status,
        TunnelStatus::Running
    );

    let replacement = manager.change_port(&first.id, free_port(), None).unwrap();
    assert_ne!(replacement.id, first.id);
    assert!(manager.view(&first.id).is_none());
    assert_eq!(
        manager.view(&replacement.id).unwrap().status,
        TunnelStatus::Running
    );

    manager.stop(&replacement.id).unwrap();
    let stopped = wait_for_status(&manager, &replacement.id, TunnelStatus::Stopped);
    assert!(stopped.elapsed.starts_with("00:"));
    assert!(manager.clear_finished() >= 1);
    assert!(manager.shutdown().is_empty());

    let events = manager.drain_events();
    assert!(events.iter().any(|event| event.event_type == "connected"));
    assert!(events.iter().any(|event| event.event_type == "stopped"));
}

#[test]
fn reports_a_failed_ssh_process_without_marking_it_running() {
    let manager = RuntimeTunnelManager::new(Some(helper_path()));
    let failed = manager
        .start(profile("failure", free_port(), "fail"), None)
        .unwrap();
    let view = wait_for_status(&manager, &failed.id, TunnelStatus::Failed);
    assert_eq!(view.status, TunnelStatus::Failed);
    assert!(view.last_error.contains("simulated authentication failure"));
    assert!(manager
        .drain_events()
        .iter()
        .any(|event| event.event_type == "log"));
    assert!(manager.shutdown().is_empty());
}
