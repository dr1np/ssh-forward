use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::Duration;

pub mod backend;

use backend::protocol::BackendCore;
use serde_json::Value;
use tauri::menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, State};

#[derive(Default)]
struct TrayState {
    available: AtomicBool,
}

#[tauri::command]
async fn backend_request(app: AppHandle, method: String, params: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let core = app.state::<BackendCore>();
        let result = core.request(&method, params);
        for event in core.drain_events() {
            let _ = app.emit("backend:event", event);
        }
        result
    })
    .await
    .map_err(|error| error.to_string())?
}

#[tauri::command]
fn tray_status(state: State<'_, TrayState>) -> bool {
    state.available.load(Ordering::Relaxed)
}

pub fn run() {
    let app = tauri::Builder::default()
        .manage(BackendCore::new())
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
                    app_handle
                        .state::<TrayState>()
                        .available
                        .store(true, Ordering::Relaxed);
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
            if let Some(core) = app_handle.try_state::<BackendCore>() {
                core.shutdown();
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
