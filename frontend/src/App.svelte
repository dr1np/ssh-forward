<script lang="ts">
  import Icon from "./lib/components/Icon.svelte";
  import LogPanel from "./lib/components/LogPanel.svelte";
  import ProfileEditor from "./lib/components/ProfileEditor.svelte";
  import StatusBadge from "./lib/components/StatusBadge.svelte";
  import TunnelCard from "./lib/components/TunnelCard.svelte";
  import { sampleLogs, sampleProfiles, sampleTunnels } from "./lib/mock";
  import type { ActiveTunnel, ForwardProfile, LogEntry, WorkspaceTab } from "./lib/types";

  let activeTab = $state<WorkspaceTab>("running");
  let profiles = $state<ForwardProfile[]>([...sampleProfiles]);
  let tunnels = $state<ActiveTunnel[]>([...sampleTunnels]);
  let logs = $state<LogEntry[]>([...sampleLogs]);
  let selectedTunnelId = $state("sample-tunnel-production");
  let selectedProfile = $state<ForwardProfile>(sampleProfiles[0]);
  let editorKey = $state(0);
  let copiedEndpoint = $state("");

  const hostAliases = ["production", "staging", "bastion"];

  const addLog = (level: LogEntry["level"], message: string) => {
    const now = new Date();
    const time = now.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    logs = [{ id: `${Date.now()}-${Math.random()}`, time, level, message }, ...logs];
  };

  const selectTunnel = (id: string) => {
    selectedTunnelId = id;
  };

  const selectProfile = (profile: ForwardProfile) => {
    selectedProfile = { ...profile };
    editorKey += 1;
    activeTab = "running";
  };

  const saveProfile = (profile: ForwardProfile) => {
    const existing = profiles.some((item) => item.id === profile.id);
    profiles = existing ? profiles.map((item) => (item.id === profile.id ? profile : item)) : [profile, ...profiles];
    selectedProfile = { ...profile };
    editorKey += 1;
    activeTab = "favorites";
    addLog("success", `已保存收藏“${profile.name}”。`);
  };

  const startTunnel = (profile: ForwardProfile) => {
    const newTunnel: ActiveTunnel = {
      id: `demo-tunnel-${Date.now()}`,
      profile: { ...profile },
      status: "connecting",
      elapsed: "00:00",
      isSample: true,
    };
    tunnels = [newTunnel, ...tunnels];
    selectedTunnelId = newTunnel.id;
    activeTab = "running";
    addLog("info", `正在启动“${profile.name}”：localhost:${profile.localPort} → ${profile.remoteHost}:${profile.remotePort}。`);
    window.setTimeout(() => {
      tunnels = tunnels.map((tunnel) => (tunnel.id === newTunnel.id ? { ...tunnel, status: "running", elapsed: "00:01" } : tunnel));
      addLog("success", `“${profile.name}”已开始转发。`);
    }, 850);
  };

  const stopTunnel = (tunnel: ActiveTunnel) => {
    tunnels = tunnels.map((item) => (item.id === tunnel.id ? { ...item, status: "stopped" } : item));
    addLog("info", `已停止“${tunnel.profile.name}”。`);
  };

  const changePort = (tunnel: ActiveTunnel) => {
    const nextPort = tunnel.profile.localPort + 1;
    const profile = { ...tunnel.profile, localPort: nextPort };
    tunnels = tunnels.map((item) => (item.id === tunnel.id ? { ...item, profile } : item));
    addLog("success", `已将“${tunnel.profile.name}”的本地端口改为 ${nextPort}。`);
  };

  const copyEndpoint = async (tunnel: ActiveTunnel) => {
    const endpoint = tunnel.profile.localBind === "::1" ? `[${tunnel.profile.localBind}]:${tunnel.profile.localPort}` : `localhost:${tunnel.profile.localPort}`;
    copiedEndpoint = endpoint;
    addLog("success", `已复制本地地址：${endpoint}。`);
    try {
      await navigator.clipboard?.writeText(endpoint);
    } catch {
      // Clipboard permission is not available in every preview environment.
    }
    window.setTimeout(() => (copiedEndpoint = ""), 2200);
  };

  const clearLogs = () => {
    logs = [];
  };
</script>

<svelte:head>
  <meta name="description" content="集中管理 SSH 本地端口转发。" />
</svelte:head>

<div class="app-shell">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark"><span></span><span></span><span></span></div>
      <div>
        <strong>SSH Forwarder</strong>
        <span>端口转发助手</span>
      </div>
    </div>

    <div class="sidebar-demo-note"><span class="demo-dot"></span> 前端预览 · 演示数据</div>

    <nav class="sidebar-nav" aria-label="工作区导航">
      <button class:active={activeTab === "running"} type="button" onclick={() => (activeTab = "running")}><Icon name="link" size={17} /> 运行中的转发 <span>{tunnels.filter((item) => item.status === "running" || item.status === "connecting").length}</span></button>
      <button class:active={activeTab === "favorites"} type="button" onclick={() => (activeTab = "favorites")}><Icon name="book" size={17} /> 收藏 <span>{profiles.length}</span></button>
      <button class:active={activeTab === "logs"} type="button" onclick={() => (activeTab = "logs")}><Icon name="file" size={17} /> 日志 <span>{logs.length}</span></button>
    </nav>

    <div class="sidebar-section-label">系统</div>
    <div class="sidebar-nav sidebar-nav--secondary">
      <button type="button"><Icon name="server" size={17} /> OpenSSH <small>就绪</small></button>
      <button type="button"><Icon name="sliders" size={17} /> 偏好设置</button>
    </div>

    <div class="sidebar-footer">
      <div class="sidebar-footer__status"><span class="status-dot status-dot--green"></span><span>本机服务正常</span></div>
      <div class="sidebar-footer__meta">Windows OpenSSH · 预览版</div>
    </div>
  </aside>

  <main class="main-content">
    <header class="topbar">
      <div>
        <span class="section-kicker">本地开发工具</span>
        <h1>管理你的 SSH 连接</h1>
      </div>
      <div class="topbar-actions">
        {#if copiedEndpoint}<span class="toast"><Icon name="check" size={15} /> 已复制 {copiedEndpoint}</span>{/if}
        <button class="icon-button icon-button--large" type="button" title="切换主题" aria-label="切换主题"><Icon name="sun" size={18} /></button>
        <button class="profile-chip" type="button" aria-label="打开应用菜单"><span class="profile-avatar">T</span><span>本机</span><Icon name="chevron" size={15} /></button>
      </div>
    </header>

    <div class="content-grid">
      <div class="editor-column">
        {#key editorKey}
          <ProfileEditor initialProfile={selectedProfile} {hostAliases} onSave={saveProfile} onStart={startTunnel} />
        {/key}
      </div>

      <section class="workspace-column">
        <div class="workspace-header">
          <div>
            <span class="section-kicker">工作区</span>
            <h2>{activeTab === "running" ? "运行中的转发" : activeTab === "favorites" ? "收藏配置" : "运行日志"}</h2>
          </div>
          {#if activeTab === "running"}
            <div class="workspace-summary"><span class="summary-number">{tunnels.filter((item) => item.status === "running").length}</span><span>条连接正在运行</span></div>
          {:else if activeTab === "favorites"}
            <button class="button button--secondary" type="button" onclick={() => (activeTab = "running")}><Icon name="plus" size={16} /> 新建转发</button>
          {/if}
        </div>

        {#if activeTab === "running"}
          <div class="tunnel-list">
            {#each tunnels as tunnel (tunnel.id)}
              <TunnelCard tunnel={tunnel} selected={selectedTunnelId === tunnel.id} onSelect={selectTunnel} onCopy={copyEndpoint} onPortChange={changePort} onStop={stopTunnel} />
            {:else}
              <div class="empty-state">
                <span class="empty-state__icon"><Icon name="link" size={22} /></span>
                <h3>暂无运行中的转发</h3>
                <p>在左侧填写连接信息，然后启动第一条本地隧道。</p>
              </div>
            {/each}
          </div>
        {:else if activeTab === "favorites"}
          <div class="favorites-list">
            {#each profiles as profile (profile.id)}
              <article class="favorite-row">
                <div class="favorite-icon"><Icon name="book" size={17} /></div>
                <div class="favorite-main">
                  <div class="eyebrow-row"><h3>{profile.name}</h3>{#if profile.isSample}<span class="sample-label">演示数据</span>{/if}</div>
                  <p>{profile.sshHost} · localhost:{profile.localPort} → {profile.remoteHost}:{profile.remotePort}</p>
                </div>
                <div class="favorite-actions">
                  <button class="icon-button" type="button" title="编辑配置" aria-label="编辑配置" onclick={() => selectProfile(profile)}><Icon name="edit" size={16} /></button>
                  <button class="button button--primary button--small" type="button" onclick={() => startTunnel(profile)}><Icon name="play" size={14} /> 启动</button>
                </div>
              </article>
            {/each}
          </div>
        {:else}
          <LogPanel logs={logs} onClear={clearLogs} />
        {/if}
      </section>
    </div>
  </main>
</div>
