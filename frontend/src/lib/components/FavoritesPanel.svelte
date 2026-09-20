<script lang="ts">
  import Icon from "./Icon.svelte";
  import type { ForwardProfile } from "../types";
  import { formatLocalEndpoint, formatRemoteEndpoint } from "../endpoints";

  interface Props {
    profiles: ForwardProfile[];
    backendReady: boolean;
    pendingStarts: string[];
    onEdit: (profile: ForwardProfile) => void;
    onDelete: (profile: ForwardProfile) => void;
    onStart: (profile: ForwardProfile) => void | Promise<void>;
  }

  let { profiles, backendReady, pendingStarts, onEdit, onDelete, onStart }: Props = $props();
</script>

<section class="page-panel page-panel--list">
  <div class="page-panel__header">
    <div>
      <span class="section-kicker">保存的连接</span>
      <h2>收藏配置</h2>
      <p>双击一条配置可以立即启动，也可以先编辑连接参数。</p>
    </div>
    <span class="page-panel__count">{profiles.length} 条</span>
  </div>

  <div class="favorites-list">
    {#each profiles as profile (profile.id)}
      <article class="favorite-row" ondblclick={(event) => { if (!(event.target as HTMLElement).closest("button")) void onStart(profile); }}>
        <div class="favorite-icon"><Icon name="book" size={17} /></div>
        <div class="favorite-main">
          <div class="eyebrow-row"><h3>{profile.name}</h3>{#if profile.isSample}<span class="sample-label">演示数据</span>{/if}</div>
          <p>{profile.sshHost} · {formatLocalEndpoint(profile)} → {formatRemoteEndpoint(profile)}</p>
        </div>
        <div class="favorite-actions">
          <button class="icon-button" type="button" title="编辑配置" aria-label="编辑配置" onclick={() => onEdit(profile)}><Icon name="edit" size={16} /></button>
          <button class="icon-button icon-button--danger" type="button" title="删除收藏" aria-label="删除收藏" onclick={() => onDelete(profile)}><Icon name="trash" size={16} /></button>
          <button class="button button--primary button--small" type="button" disabled={!backendReady || pendingStarts.includes(profile.id)} onclick={() => onStart(profile)}><Icon name="play" size={14} /> 启动</button>
        </div>
      </article>
    {:else}
      <div class="empty-state"><span class="empty-state__icon"><Icon name="book" size={22} /></span><h3>暂无收藏配置</h3><p>在新建转发页面填写配置并保存收藏，下次即可一键启动。</p></div>
    {/each}
  </div>
</section>
