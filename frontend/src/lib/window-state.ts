import { LogicalPosition, LogicalSize } from "@tauri-apps/api/dpi";
import { getCurrentWindow } from "@tauri-apps/api/window";

const STORAGE_KEY = "ssh-forwarder.window-state";

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
    if (Number.isFinite(saved.width) && Number.isFinite(saved.height)) {
      await window.setSize(new LogicalSize(saved.width, saved.height));
    }
    const x = saved.x;
    const y = saved.y;
    if (typeof x === "number" && typeof y === "number" && Number.isFinite(x) && Number.isFinite(y)) {
      await window.setPosition(new LogicalPosition(x, y));
    }
  } catch {
    // Window restoration is best effort; an invalid monitor geometry must not block startup.
  }
}

export async function saveWindowState(): Promise<void> {
  try {
    const window = getCurrentWindow();
    const [size, position] = await Promise.all([window.outerSize(), window.outerPosition()]);
    const saved: WindowState = {
      width: size.width,
      height: size.height,
      x: position.x,
      y: position.y,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  } catch {
    // The window may already be closing; persistence is non-critical.
  }
}
