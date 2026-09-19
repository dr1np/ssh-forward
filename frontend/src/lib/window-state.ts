import { PhysicalPosition, LogicalSize } from "@tauri-apps/api/dpi";
import { availableMonitors, getCurrentWindow } from "@tauri-apps/api/window";

const STORAGE_KEY = "ssh-forwarder.window-state-v2";

interface WindowState {
  width: number;
  height: number;
  x?: number;
  y?: number;
}

export async function restoreWindowState(): Promise<void> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw) as WindowState;
    const window = getCurrentWindow();
    const monitors = await availableMonitors();
    const monitor = monitors.find((item) => typeof saved.x === "number" && typeof saved.y === "number"
      && saved.x >= item.position.x && saved.y >= item.position.y
      && saved.x + 100 < item.position.x + item.size.width && saved.y + 40 < item.position.y + item.size.height);
    if (!monitor) return;
    if (Number.isFinite(saved.width) && Number.isFinite(saved.height)) {
      await window.setSize(new LogicalSize(
        Math.max(960, Math.min(saved.width, monitor.size.width / monitor.scaleFactor)),
        Math.max(640, Math.min(saved.height, monitor.size.height / monitor.scaleFactor - 48)),
      ));
    }
    const x = saved.x;
    const y = saved.y;
    if (typeof x === "number" && typeof y === "number" && Number.isFinite(x) && Number.isFinite(y)) {
      await window.setPosition(new PhysicalPosition(x, y));
    }
  } catch {
    // Window restoration is best effort; an invalid monitor geometry must not block startup.
  }
}

export async function saveWindowState(): Promise<void> {
  try {
    const window = getCurrentWindow();
    if (await window.isMaximized()) return;
    const [size, position, scale] = await Promise.all([window.innerSize(), window.outerPosition(), window.scaleFactor()]);
    const saved: WindowState = {
      width: size.width / scale,
      height: size.height / scale,
      x: position.x,
      y: position.y,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  } catch {
    // The window may already be closing; persistence is non-critical.
  }
}
