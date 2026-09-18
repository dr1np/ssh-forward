<script lang="ts">
  import Icon from "./Icon.svelte";
  import StatusBadge from "./StatusBadge.svelte";
  import type { ActiveTunnel } from "../types";

  interface Props {
    tunnel: ActiveTunnel;
    selected?: boolean;
    onSelect: (id: string) => void;
    onCopy: (tunnel: ActiveTunnel) => void;
    onPortChange: (tunnel: ActiveTunnel) => void;
    onStop: (tunnel: ActiveTunnel) => void;
  }

  let { tunnel, selected = false, onSelect, onCopy, onPortChange, onStop }: Props = $props();
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
        <p>经由 SSH Config · {tunnel.profile.sshHost}</p>
      </div>
    </div>
    <StatusBadge status={tunnel.status} />
  </div>

  <div class="tunnel-route" class:route-running={tunnel.status === "running"}>
    <div class="route-endpoint">
      <span class="route-label">本地监听</span>
      <strong>{tunnel.profile.localBind === "::1" ? `[${tunnel.profile.localBind}]:${tunnel.profile.localPort}` : `localhost:${tunnel.profile.localPort}`}</strong>
    </div>
    <div class="route-track" aria-hidden="true">
      <span class="route-line"></span>
      <span class="route-pulse"></span>
    </div>
    <div class="route-endpoint route-endpoint--target">
      <span class="route-label">远程目标</span>
      <strong>{tunnel.profile.remoteHost}:{tunnel.profile.remotePort}</strong>
    </div>
  </div>

  <div class="tunnel-card__footer">
    <span class="elapsed"><span class="elapsed-caption">连接时间</span>{tunnel.elapsed}</span>
    <div class="card-actions">
      <button class="icon-button" type="button" title="复制本地地址" aria-label="复制本地地址" onclick={() => onCopy(tunnel)}><Icon name="clipboard" size={16} /></button>
      <button class="icon-button" type="button" title="更改本地端口" aria-label="更改本地端口" onclick={() => onPortChange(tunnel)}><Icon name="tune" size={16} /></button>
      <button class="icon-button icon-button--danger" type="button" title="停止转发" aria-label="停止转发" onclick={() => onStop(tunnel)}><Icon name="stop" size={16} /></button>
    </div>
  </div>
</article>
