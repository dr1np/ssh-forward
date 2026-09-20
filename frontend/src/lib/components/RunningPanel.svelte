<script lang="ts">
  import Icon from "./Icon.svelte";
  import TunnelCard from "./TunnelCard.svelte";
  import type { ActiveTunnel } from "../types";

  interface Props {
    tunnels: ActiveTunnel[];
    selectedTunnelId: string;
    pendingTunnels: string[];
    emptyMessage: string;
    onSelect: (id: string) => void;
    onCopy: (tunnel: ActiveTunnel) => void;
    onPortChange: (tunnel: ActiveTunnel) => void;
    onStop: (tunnel: ActiveTunnel) => void | Promise<void>;
    onRestart: (tunnel: ActiveTunnel) => void | Promise<void>;
    onDelete: (tunnel: ActiveTunnel) => void;
    onClear: () => void | Promise<void>;
  }

  let {
    tunnels,
    selectedTunnelId,
    pendingTunnels,
    emptyMessage,
    onSelect,
    onCopy,
    onPortChange,
    onStop,
    onRestart,
    onDelete,
    onClear,
  }: Props = $props();

  const activeCount = () => tunnels.filter((item) => item.status === "running" || item.status === "connecting").length;
  const runningCount = () => tunnels.filter((item) => item.status === "running").length;
  const hasFinished = () => tunnels.some((item) => item.status === "stopped" || item.status === "failed");
</script>

<section class="workspace-column page-panel running-panel">
  <div class="workspace-header">
    <div>
      <span class="section-kicker">连接状态</span>
      <h2>运行中的转发</h2>
    </div>
    <div class="workspace-summary">
      <span class="summary-number">{runningCount()}</span>
      <span>条连接正在运行</span>
      {#if hasFinished()}
        <button class="button button--quiet" type="button" onclick={onClear}>清理已结束</button>
      {/if}
    </div>
  </div>

  <div class="running-panel__meta">
    <span><span class="status-dot status-dot--green"></span> 当前活动 {activeCount()}</span>
    <span>本地端口由 SSH 客户端直接监听</span>
  </div>

  <div class="tunnel-list">
    {#each tunnels as tunnel (tunnel.id)}
      <TunnelCard
        busy={pendingTunnels.includes(tunnel.id)}
        {tunnel}
        selected={selectedTunnelId === tunnel.id}
        {onSelect}
        {onCopy}
        {onPortChange}
        {onStop}
        {onRestart}
        {onDelete}
      />
    {:else}
      <div class="empty-state">
        <span class="empty-state__icon"><Icon name="link" size={22} /></span>
        <h3>暂无运行中的转发</h3>
        <p>{emptyMessage}</p>
      </div>
    {/each}
  </div>
</section>
