use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

pub(crate) mod backend;

use serde_json::{json, Value};
use tauri::menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, State};
#[cfg(windows)]
use std::os::windows::process::CommandExt;

use std::sync::atomic::AtomicBool;

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

#[derive(Default)]
struct TrayState {
    available: AtomicBool,
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
    let mut commands = Vec::new();
    if cfg!(debug_assertions) {
        for (exe, args) in [
            ("python", vec!["-u", "-m", "ssh_forwarder.service"]),
            ("python3", vec!["-u", "-m", "ssh_forwarder.service"]),
            ("py", vec!["-3", "-u", "-m", "ssh_forwarder.service"]),
        ] {
            let mut command = Command::new(exe);
            command.args(args).current_dir(repository_root());
            commands.push(command);
        }
    } else {
        let executable = std::env::current_exe().map_err(|error| error.to_string())?;
        let directory = executable.parent().ok_or("无法定位应用目录")?;
        let sidecar = directory.join(if cfg!(windows) {
            "ssh-forwarder-service.exe"
        } else {
            "ssh-forwarder-service"
        });
        commands.push(Command::new(sidecar));
    }
    let mut last_error = String::from("无法启动后端服务");
    let mut child = None;
    for mut command in commands {
        command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped());
        #[cfg(windows)]
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW, retain JSONL pipes.
        match command.spawn() {
            Ok(process) => { child = Some(process); break; }
            Err(error) => last_error = format!("无法启动后端服务：{error}"),
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
        let running = connection.child.lock()
            .map_err(|_| "后端进程锁已损坏")?
            .try_wait().map_err(|error| error.to_string())?.is_none();
        if running { return Ok(Arc::clone(connection)); }
    }
    let connection = spawn_backend(app)?;
    *guard = Some(Arc::clone(&connection));
    Ok(connection)
}

#[tauri::command]
async fn backend_request(app: AppHandle, method: String, params: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let state = app.state::<BackendState>();
        request_blocking(&app, &state, method, params)
    }).await.map_err(|error| error.to_string())?
}

#[tauri::command]
fn tray_status(state: State<'_, TrayState>) -> bool {
    state.available.load(Ordering::Relaxed)
}

fn request_blocking(app: &AppHandle, state: &BackendState, method: String, params: Value) -> Result<Value, String> {
    let connection = connection_for(app, state)?;
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

    let result = match receiver.recv_timeout(Duration::from_secs(30)) {
        Ok(response) => response,
        Err(RecvTimeoutError::Timeout) => Err("等待 Python 服务响应超时。".to_string()),
        Err(RecvTimeoutError::Disconnected) => Err("Python 服务已断开。".to_string()),
    };
    if let Ok(mut waiting) = connection.pending.lock() { waiting.remove(&request_id); }
    result
}

pub fn run() {
    let app = tauri::Builder::default()
        .manage(BackendState::default())
        .manage(TrayState::default())
        .invoke_handler(tauri::generate_handler![backend_request, tray_status])
        .setup(|app| {
            app.handle().plugin(tauri_plugin_dialog::init())?;

            let show_window = MenuItemBuilder::with_id("show-window", "显示窗口").build(app)?;
            let separator = PredefinedMenuItem::separator(app)?;
            let quit = MenuItemBuilder::with_id("quit-app", "退出并停止转发").build(app)?;
            let menu = MenuBuilder::new(app)
                .items(&[&show_window, &separator, &quit])
                .build()?;

            // TrayIconBuilder waits for the main-thread task it posts. Starting it
            // from the Ready callback would block that same event loop, so defer the
            // builder to a worker thread and let the event loop service the request.
            let app_handle = app.handle().clone();
            let main_window = app.get_webview_window("main");
            thread::spawn(move || {
                thread::sleep(Duration::from_millis(100));
                if let Some(window) = main_window {
                    let _ = window.show();
                    let _ = window.unminimize();
                    let _ = window.set_focus();
                }
            });
            thread::spawn(move || {
                let result = app_handle
                    .default_window_icon()
                    .cloned()
                    .ok_or_else(|| "应用缺少托盘图标".to_string())
                    .and_then(|icon| {
                        TrayIconBuilder::with_id("main")
                            .icon(icon)
                            .menu(&menu)
                            .show_menu_on_left_click(false)
                            .tooltip("SSH 端口转发助手")
                            .on_menu_event(|app, event| match event.id().as_ref() {
                                "show-window" => show_main_window(app),
                                "quit-app" => app.exit(0),
                                _ => {}
                            })
                            .on_tray_icon_event(|tray, event| {
                                if let TrayIconEvent::Click {
                                    button: MouseButton::Left,
                                    button_state: MouseButtonState::Up,
                                    ..
                                } = event
                                {
                                    show_main_window(tray.app_handle());
                                }
                            })
                            .build(&app_handle)
                            .map(|_| ())
                            .map_err(|error| error.to_string())
                    });
                if result.is_ok() {
                    app_handle.state::<TrayState>().available.store(true, Ordering::Relaxed);
                } else if let Err(error) = result {
                    eprintln!("无法创建系统托盘，关闭窗口将直接退出：{error}");
                }
            });
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

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}
