export type ConnectionType = "config" | "custom";

export type TunnelStatus =
  | "connecting"
  | "running"
  | "stopping"
  | "stopped"
  | "failed";

export type WorkspaceTab = "running" | "favorites" | "logs";

export interface ForwardProfile {
  id: string;
  name: string;
  connectionType: ConnectionType;
  sshHost: string;
  sshPort: number;
  sshUser: string;
  identityFile: string;
  localBind: "127.0.0.1" | "0.0.0.0" | "::1";
  localPort: number;
  remoteHost: string;
  remotePort: number;
  isSample?: boolean;
}

export interface ActiveTunnel {
  id: string;
  profile: ForwardProfile;
  status: TunnelStatus;
  elapsed: string;
  lastError?: string;
  isSample?: boolean;
}

export interface LogEntry {
  id: string;
  time: string;
  level: "info" | "success" | "error";
  message: string;
}
