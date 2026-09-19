<script lang="ts">
  import Icon from "./Icon.svelte";
  import StatusBadge from "./StatusBadge.svelte";
  import { formatLocalEndpoint, formatRemoteEndpoint } from "../endpoints";
  import type { ActiveTunnel } from "../types";

  interface Props {
    tunnel: ActiveTunnel;
    selected?: boolean;
    busy?: boolean;
    onSelect: (id: string) => void;
    onCopy: (tunnel: ActiveTunnel) => void;
    onPortChange: (tunnel: ActiveTunnel) => void;
    onStop: (tunnel: ActiveTunnel) => void;
    onRestart: (tunnel: ActiveTunnel) => void;
    onDelete: (tunnel: ActiveTunnel) => void;
  }

  let { tunnel, selected = false, busy = false, onSelect, onCopy, onPortChange, onStop, onRestart, onDelete }: Props = $props();
</script>

<article class:selected class:sample-card={tunnel.isSample} class="tunnel-card">
  <button class="card-hit-area" type="button" aria-label={`选择 ${tunnel.profile.name}`} onclick={() => onSelect(tunnel.id)}></button>

  <div class="tunnel-card__topline">
    <div class="tunnel-card__identity">
      <span class="server-mark"><Icon name="server" size={17} /></span>
      <div>
        <div class="eyebrow-row">
          <h3>{tunnel.profile.name}</h3>
          {#if tunnel.isSample}<span class="sample-label">演示数据</span>{/if}
        </div>
        <p>{tunnel.profile.connectionType === "config" ? "SSH Config" : "自定义主机"} · {tunnel.profile.sshHost}</p>
      </div>
    </div>
    <StatusBadge status={tunnel.status} />
  </div>

  <div class="tunnel-route" class:route-running={tunnel.status === "running"}>
    <div class="route-endpoint">
      <span class="route-label">本地监听</span>
      <strong>{formatLocalEndpoint(tunnel.profile)}</strong>
    </div>
    <div class="route-track" aria-hidden="true">
      <span class="route-line"></span>
      <span class="route-pulse"></span>
    </div>
    <div class="route-endpoint route-endpoint--target">
      <span class="route-label">远程目标</span>
      <strong>{formatRemoteEndpoint(tunnel.profile)}</strong>
    </div>
  </div>

  {#if tunnel.lastError}<p class="tunnel-error" role="status">{tunnel.lastError}</p>{/if}

  <div class="tunnel-card__footer">
    <span class="elapsed"><span class="elapsed-caption">连接时间</span>{tunnel.elapsed}</span>
    <div class="card-actions">
      <button class="icon-button" type="button" title="复制本地地址" aria-label="复制本地地址" onclick={() => onCopy(tunnel)}><Icon name="clipboard" size={16} /></button>
      <button class="icon-button" type="button" title="更改本地端口" aria-label="更改本地端口" disabled={busy || tunnel.status !== "running" && tunnel.status !== "connecting"} onclick={() => onPortChange(tunnel)}><Icon name="tune" size={16} /></button>
      <button class="icon-button icon-button--danger" type="button" title="停止转发" aria-label="停止转发" disabled={busy || tunnel.status !== "running" && tunnel.status !== "connecting"} onclick={() => onStop(tunnel)}><Icon name="stop" size={16} /></button>
      {#if tunnel.status === "stopped" || tunnel.status === "failed"}
        <button class="button button--secondary button--small tunnel-restart" type="button" disabled={busy} onclick={() => onRestart(tunnel)}><Icon name="refresh" size={14} /> 恢复转发</button>
        <button class="icon-button icon-button--danger" type="button" title="删除记录" aria-label="删除记录" onclick={() => onDelete(tunnel)}><Icon name="trash" size={16} /></button>
      {/if}
    </div>
  </div>
</article>
