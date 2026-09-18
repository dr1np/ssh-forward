use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, State};

type PendingMap = Arc<Mutex<HashMap<String, Sender<Result<Value, String>>>>>;

struct BackendConnection {
    child: Mutex<Child>,
    stdin: Mutex<ChildStdin>,
    pending: PendingMap,
}

#[derive(Default)]
struct BackendState {
    connection: Mutex<Option<Arc<BackendConnection>>>,
    next_request_id: AtomicU64,
}

impl BackendState {
    fn shutdown(&self) {
        let connection = self
            .connection
            .lock()
            .ok()
            .and_then(|mut guard| guard.take());
        let Some(connection) = connection else {
            return;
        };
        if let Ok(mut stdin) = connection.stdin.lock() {
            let shutdown = json!({
                "id": "window-close",
                "method": "shutdown",
                "params": {},
            });
            if let Ok(mut encoded) = serde_json::to_vec(&shutdown) {
                encoded.push(b'\n');
                let _ = stdin.write_all(&encoded);
                let _ = stdin.flush();
            }
        }
        let deadline = Instant::now() + Duration::from_secs(3);
        loop {
            let finished = connection
                .child
                .lock()
                .ok()
                .and_then(|mut child| child.try_wait().ok())
                .flatten()
                .is_some();
            if finished || Instant::now() >= deadline {
                break;
            }
            thread::sleep(Duration::from_millis(50));
        }
        if let Ok(mut child) = connection.child.lock() {
            if child.try_wait().ok().flatten().is_none() {
                let _ = child.kill();
            }
            let _ = child.wait();
        };
    }
}

fn repository_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
}

fn spawn_backend(app: &AppHandle) -> Result<Arc<BackendConnection>, String> {
    let root = repository_root();
    let candidates = [
        ("python", vec!["-u", "-m", "ssh_forwarder.service"]),
        ("python3", vec!["-u", "-m", "ssh_forwarder.service"]),
        ("py", vec!["-3", "-u", "-m", "ssh_forwarder.service"]),
    ];
    let mut last_error = String::from("未找到 Python 解释器");
    let mut child = None;

    for (executable, args) in candidates {
        match Command::new(executable)
            .args(args)
            .current_dir(&root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
        {
            Ok(process) => {
                child = Some(process);
                break;
            }
            Err(error) => {
                last_error = format!("无法启动 {executable}：{error}");
            }
        }
    }

    let mut child = child.ok_or(last_error)?;
    let stdin = child
        .stdin
        .take()
        .ok_or_else(|| "Python 服务没有可写入的 stdin。".to_string())?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "Python 服务没有可读取的 stdout。".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "Python 服务没有可读取的 stderr。".to_string())?;
    let pending: PendingMap = Arc::new(Mutex::new(HashMap::new()));

    let pending_reader = Arc::clone(&pending);
    let app_reader = app.clone();
    thread::spawn(move || {
        for line in BufReader::new(stdout).split(b'\n') {
            let Ok(line) = line else { break };
            let line = String::from_utf8_lossy(&line);
            let Ok(message) = serde_json::from_str::<Value>(&line) else {
                let _ = app_reader.emit(
                    "backend:event",
                    json!({"event": "protocol_error", "message": line}),
                );
                continue;
            };
            if let Some(request_id) = message.get("id").and_then(Value::as_str) {
                let response = if message.get("ok").and_then(Value::as_bool) == Some(true) {
                    Ok(message.get("result").cloned().unwrap_or(Value::Null))
                } else {
                    Err(message
                        .get("error")
                        .and_then(Value::as_str)
                        .unwrap_or("Python 服务返回了未知错误")
                        .to_string())
                };
                if let Ok(mut waiting) = pending_reader.lock() {
                    if let Some(sender) = waiting.remove(request_id) {
                        let _ = sender.send(response);
                    }
                }
            } else {
                let _ = app_reader.emit("backend:event", message);
            }
        }

        if let Ok(mut waiting) = pending_reader.lock() {
            for (_, sender) in waiting.drain() {
                let _ = sender.send(Err("Python 服务已退出。".to_string()));
            }
        }
        let _ = app_reader.emit(
            "backend:event",
            json!({"event": "backend_exited", "message": "Python 服务已退出。"}),
        );
    });

    let app_stderr = app.clone();
    thread::spawn(move || {
        for line in BufReader::new(stderr).split(b'\n').map_while(Result::ok) {
            let line = String::from_utf8_lossy(&line);
            if !line.trim().is_empty() {
                let _ = app_stderr.emit("backend:stderr", json!({"message": line}));
            }
        }
    });

    Ok(Arc::new(BackendConnection {
        child: Mutex::new(child),
        stdin: Mutex::new(stdin),
        pending,
    }))
}

fn connection_for(app: &AppHandle, state: &BackendState) -> Result<Arc<BackendConnection>, String> {
    let mut guard = state
        .connection
        .lock()
        .map_err(|_| "Python 服务状态锁已损坏。".to_string())?;
    if let Some(connection) = guard.as_ref() {
        return Ok(Arc::clone(connection));
    }
    let connection = spawn_backend(app)?;
    *guard = Some(Arc::clone(&connection));
    Ok(connection)
}

#[tauri::command]
fn backend_request(
    app: AppHandle,
    state: State<'_, BackendState>,
    method: String,
    params: Value,
) -> Result<Value, String> {
    let connection = connection_for(&app, &state)?;
    let request_id = state
        .next_request_id
        .fetch_add(1, Ordering::Relaxed)
        .to_string();
    let (sender, receiver) = mpsc::channel();

    connection
        .pending
        .lock()
        .map_err(|_| "Python 服务等待队列已损坏。".to_string())?
        .insert(request_id.clone(), sender);

    let request = json!({
        "id": request_id,
        "method": method,
        "params": params,
    });
    let mut encoded = serde_json::to_vec(&request).map_err(|error| error.to_string())?;
    encoded.push(b'\n');
    if let Err(error) = connection
        .stdin
        .lock()
        .map_err(|_| "Python 服务 stdin 锁已损坏。".to_string())
        .and_then(|mut stdin| {
            stdin
                .write_all(&encoded)
                .map_err(|error| error.to_string())?;
            stdin.flush().map_err(|error| error.to_string())
        })
    {
        if let Ok(mut waiting) = connection.pending.lock() {
            waiting.remove(&request_id);
        }
        return Err(format!("无法写入 Python 服务：{error}"));
    }

    match receiver.recv_timeout(Duration::from_secs(30)) {
        Ok(response) => response,
        Err(RecvTimeoutError::Timeout) => Err("等待 Python 服务响应超时。".to_string()),
        Err(RecvTimeoutError::Disconnected) => Err("Python 服务已断开。".to_string()),
    }
}

pub fn run() {
    let app = tauri::Builder::default()
        .manage(BackendState::default())
        .invoke_handler(tauri::generate_handler![backend_request])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            app.handle().plugin(tauri_plugin_dialog::init())?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Tauri application");

    app.run(|app_handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            if let Some(state) = app_handle.try_state::<BackendState>() {
                state.shutdown();
            }
        }
    });
}
