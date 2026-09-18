<script lang="ts">
  import type { TunnelStatus } from "../types";

  let { status }: { status: TunnelStatus } = $props();

  const labels: Record<TunnelStatus, string> = {
    connecting: "正在连接",
    running: "运行中",
    stopping: "正在停止",
    stopped: "已停止",
    failed: "连接失败",
  };
</script>

<span class:status-running={status === "running"} class:status-connecting={status === "connecting"} class:status-stopping={status === "stopping"} class:status-stopped={status === "stopped"} class:status-failed={status === "failed"} class="status-badge">
  <span class="status-dot"></span>
  {labels[status]}
</span>
