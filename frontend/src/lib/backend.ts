import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import type { ActiveTunnel, ForwardProfile, LogEntry } from "./types";

interface BackendProfile {
  id: string;
  name: string;
  connection_type: "config" | "custom";
  ssh_host: string;
  ssh_port: number;
  ssh_user: string;
  identity_file: string;
  local_bind: "127.0.0.1" | "0.0.0.0" | "::1";
  local_port: number;
  remote_host: string;
  remote_port: number;
}

interface BackendTunnel {
  id: string;
  profile: BackendProfile;
  status: ActiveTunnel["status"];
  elapsed: string;
  last_error?: string;
}

export interface BackendEvent {
  event?: string;
  type?: "log" | "exited" | "stopped" | "backend_exited" | "protocol_error";
  tunnel_id?: string;
  message?: string;
  tunnel?: BackendTunnel | null;
}

export interface BackendSnapshot {
  hosts: string[];
  profiles: ForwardProfile[];
  tunnels: ActiveTunnel[];
  warning?: string;
}

export const isDesktopRuntime = (): boolean =>
  typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

function toBackendProfile(profile: ForwardProfile): BackendProfile {
  return {
    id: profile.id,
    name: profile.name,
    connection_type: profile.connectionType,
    ssh_host: profile.sshHost,
    ssh_port: profile.sshPort,
    ssh_user: profile.sshUser,
    identity_file: profile.identityFile,
    local_bind: profile.localBind,
    local_port: profile.localPort,
    remote_host: profile.remoteHost,
    remote_port: profile.remotePort,
  };
}

function fromBackendProfile(profile: BackendProfile): ForwardProfile {
  return {
    id: profile.id,
    name: profile.name,
    connectionType: profile.connection_type,
    sshHost: profile.ssh_host,
    sshPort: profile.ssh_port,
    sshUser: profile.ssh_user,
    identityFile: profile.identity_file,
    localBind: profile.local_bind,
    localPort: profile.local_port,
    remoteHost: profile.remote_host,
    remotePort: profile.remote_port,
  };
}

function fromBackendTunnel(tunnel: BackendTunnel): ActiveTunnel {
  return {
    id: tunnel.id,
    profile: fromBackendProfile(tunnel.profile),
    status: tunnel.status,
    elapsed: tunnel.elapsed,
    lastError: tunnel.last_error,
  };
}

async function request<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
  return invoke<T>("backend_request", { method, params });
}

export async function loadSnapshot(): Promise<BackendSnapshot> {
  const [hosts, profilesResult, tunnels] = await Promise.all([
    loadHosts(),
    loadProfiles(),
    loadTunnels(),
  ]);
  return {
    hosts,
    profiles: profilesResult.profiles,
    tunnels,
    warning: profilesResult.warning,
  };
}

export async function loadHosts(): Promise<string[]> {
  const result = await request<{ hosts: string[] }>("list_ssh_hosts");
  return result.hosts;
}

export async function loadProfiles(): Promise<{ profiles: ForwardProfile[]; warning?: string }> {
  const result = await request<{ profiles: BackendProfile[]; warning?: string }>("load_profiles");
  return { profiles: result.profiles.map(fromBackendProfile), warning: result.warning };
}

export async function loadTunnels(): Promise<ActiveTunnel[]> {
  const result = await request<{ tunnels: BackendTunnel[] }>("get_tunnels");
  return result.tunnels.map(fromBackendTunnel);
}

export async function clearFinishedTunnels(): Promise<number> {
  const result = await request<{ removed: number }>("clear_finished");
  return result.removed;
}

export async function saveProfile(profile: ForwardProfile): Promise<ForwardProfile> {
  const result = await request<{ profile: BackendProfile }>("save_profile", {
    profile: toBackendProfile(profile),
  });
  return fromBackendProfile(result.profile);
}

export async function deleteProfile(profileId: string): Promise<void> {
  await request("delete_profile", { profile_id: profileId });
}

export async function findAvailablePort(bindAddress: string): Promise<number> {
  const result = await request<{ port: number }>("find_available_port", {
    bind_address: bindAddress,
  });
  return result.port;
}

export async function chooseIdentityFile(): Promise<string | null> {
  if (!isDesktopRuntime()) return null;
  const selected = await open({
    title: "选择 SSH 私钥",
    multiple: false,
    directory: false,
  });
  return typeof selected === "string" ? selected : null;
}

export async function startTunnel(profile: ForwardProfile): Promise<ActiveTunnel> {
  const result = await request<{ tunnel: BackendTunnel }>("start_tunnel", {
    profile: toBackendProfile(profile),
  });
  return fromBackendTunnel(result.tunnel);
}

export async function stopTunnel(tunnelId: string): Promise<void> {
  await request("stop_tunnel", { tunnel_id: tunnelId });
}

export async function changeTunnelPort(tunnelId: string, port: number): Promise<ActiveTunnel> {
  const result = await request<{ tunnel: BackendTunnel }>("change_tunnel_port", {
    tunnel_id: tunnelId,
    local_port: port,
  });
  return fromBackendTunnel(result.tunnel);
}

export async function subscribeBackendEvents(onEvent: (event: BackendEvent) => void): Promise<UnlistenFn> {
  const unlistenEvents = await listen<{ event?: string; data?: BackendEvent; message?: string }>("backend:event", (event) => {
    onEvent(event.payload.data ?? { event: event.payload.event, message: event.payload.message });
  });
  const unlistenStderr = await listen<{ message?: string }>("backend:stderr", (event) => {
    onEvent({ type: "protocol_error", event: "backend_stderr", message: event.payload.message });
  });
  return () => {
    unlistenEvents();
    unlistenStderr();
  };
}

export function backendLogToEntry(event: BackendEvent): LogEntry | null {
  if (!event.message) return null;
  const level: LogEntry["level"] = event.type === "stopped" ? "info" : event.type === "log" ? "error" : "info";
  return {
    id: `${Date.now()}-${Math.random()}`,
    time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    level,
    message: event.message,
  };
}
