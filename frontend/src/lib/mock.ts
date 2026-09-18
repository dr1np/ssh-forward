import type { ActiveTunnel, ForwardProfile, LogEntry } from "./types";

export const sampleProfiles: ForwardProfile[] = [
  {
    id: "sample-production",
    name: "示例配置 · production",
    connectionType: "config",
    sshHost: "production",
    sshPort: 22,
    sshUser: "",
    identityFile: "",
    localBind: "127.0.0.1",
    localPort: 15432,
    remoteHost: "127.0.0.1",
    remotePort: 5432,
    isSample: true,
  },
  {
    id: "sample-staging",
    name: "示例配置 · staging",
    connectionType: "config",
    sshHost: "staging",
    sshPort: 22,
    sshUser: "",
    identityFile: "",
    localBind: "127.0.0.1",
    localPort: 18080,
    remoteHost: "127.0.0.1",
    remotePort: 8080,
    isSample: true,
  },
];

export const sampleTunnels: ActiveTunnel[] = [
  {
    id: "sample-tunnel-production",
    profile: sampleProfiles[0],
    status: "running",
    elapsed: "18:42",
    isSample: true,
  },
  {
    id: "sample-tunnel-staging",
    profile: sampleProfiles[1],
    status: "connecting",
    elapsed: "00:08",
    isSample: true,
  },
];

export const sampleLogs: LogEntry[] = [
  {
    id: "sample-log-1",
    time: "演示",
    level: "info",
    message: "后端接入后，这里会显示 SSH 原始输出。",
  },
  {
    id: "sample-log-2",
    time: "示例",
    level: "success",
    message: "本地端口 15432 已映射到 production:127.0.0.1:5432。",
  },
];
