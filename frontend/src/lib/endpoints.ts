import type { ForwardProfile } from "./types";

export function formatEndpoint(host: string, port: number): string {
  const value = host.trim();
  const displayHost = value.includes(":") && !(value.startsWith("[") && value.endsWith("]"))
    ? `[${value}]`
    : value;
  return `${displayHost}:${port}`;
}

export function formatLocalEndpoint(profile: Pick<ForwardProfile, "localBind" | "localPort">): string {
  const host = profile.localBind === "127.0.0.1" ? "localhost" : profile.localBind;
  return formatEndpoint(host, profile.localPort);
}

export function formatRemoteEndpoint(profile: Pick<ForwardProfile, "remoteHost" | "remotePort">): string {
  return formatEndpoint(profile.remoteHost, profile.remotePort);
}
