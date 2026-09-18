<script lang="ts">
  import Icon from "./Icon.svelte";
  import type { LogEntry } from "../types";

  let { logs, onClear }: { logs: LogEntry[]; onClear: () => void } = $props();
</script>

<section class="log-panel">
  <div class="panel-header">
    <div>
      <span class="section-kicker">运行记录</span>
      <h2>日志</h2>
    </div>
    <button class="button button--quiet" type="button" onclick={onClear}><Icon name="trash" size={15} /> 清空日志</button>
  </div>
  <div class="log-stream">
    {#each logs as entry (entry.id)}
      <div class:log-success={entry.level === "success"} class:log-error={entry.level === "error"} class="log-line">
        <time>{entry.time}</time>
        <span class="log-marker"></span>
        <p>{entry.message}</p>
      </div>
    {:else}
      <div class="empty-state empty-state--small">
        <span class="empty-state__icon"><Icon name="file" size={20} /></span>
        <p>暂无日志</p>
      </div>
    {/each}
  </div>
</section>
