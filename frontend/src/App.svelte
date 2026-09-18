<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "./lib/components/Icon.svelte";
  import LogPanel from "./lib/components/LogPanel.svelte";
  import ProfileEditor from "./lib/components/ProfileEditor.svelte";
  import StatusBadge from "./lib/components/StatusBadge.svelte";
  import TunnelCard from "./lib/components/TunnelCard.svelte";
  import {
    backendLogToEntry,
    changeTunnelPort,
    chooseIdentityFile,
    deleteProfile as deleteBackendProfile,
    findAvailablePort,
    isDesktopRuntime,
    loadHosts,
    loadSnapshot,
    loadTunnels,
    saveProfile as saveBackendProfile,
    startTunnel as startBackendTunnel,
    stopTunnel as stopBackendTunnel,
    subscribeBackendEvents,
  } from "./lib/backend";
  import { sampleLogs, sampleProfiles, sampleTunnels } from "./lib/mock";
  import type { ActiveTunnel, ForwardProfile, LogEntry, WorkspaceTab } from "./lib/types";

  const desktopRuntime = isDesktopRuntime();
  let activeTab = $state<WorkspaceTab>("running");
  let profiles = $state<ForwardProfile[]>([...sampleProfiles]);
  let tunnels = $state<ActiveTunnel[]>([...sampleTunnels]);
  let logs = $state<LogEntry[]>([...sampleLogs]);
  let selectedTunnelId = $state("sample-tunnel-production");
  let selectedProfile = $state<ForwardProfile>(desktopRuntime ? makeBlankProfile() : sampleProfiles[0]);
  let editorKey = $state(0);
  let copiedEndpoint = $state("");
  let backendReady = $state(!desktopRuntime);
  let backendError = $state("");
  let hostAliases = $state(["production", "staging", "bastion"]);

  function makeBlankProfile(host = ""): ForwardProfile {
    return {
      id: globalThis.crypto?.randomUUID?.() ?? `profile-${Date.now()}`,
      name: "",
      connectionType: "config",
      sshHost: host,
      sshPort: 22,
      sshUser: "",
      identityFile: "",
      localBind: "127.0.0.1",
      localPort: 8080,
      remoteHost: "127.0.0.1",
      remotePort: 80,
    };
  }

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

  const hydrateDesktop = async () => {
    try {
      const snapshot = await loadSnapshot();
      hostAliases = snapshot.hosts;
      profiles = snapshot.profiles;
      tunnels = snapshot.tunnels;
      logs = [];
      selectedProfile = profiles[0] ? { ...profiles[0] } : makeBlankProfile(hostAliases[0] ?? "");
      editorKey += 1;
      backendReady = true;
      if (snapshot.warning) addLog("error", snapshot.warning);
    } catch (error) {
      backendError = String(error);
      addLog("error", `无法连接桌面后端：${backendError}`);
    }
  };

  const refreshDesktopTunnels = async () => {
    if (!desktopRuntime || !backendReady) return;
    try {
      tunnels = await loadTunnels();
    } catch (error) {
      backendError = String(error);
    }
  };

  const handleBackendEvent = (event: Parameters<typeof backendLogToEntry>[0]) => {
    if (event.tunnel) {
      const tunnel = event.tunnel;
      const converted = {
        id: tunnel.id,
        profile: {
          id: tunnel.profile.id,
          name: tunnel.profile.name,
          connectionType: tunnel.profile.connection_type,
          sshHost: tunnel.profile.ssh_host,
          sshPort: tunnel.profile.ssh_port,
          sshUser: tunnel.profile.ssh_user,
          identityFile: tunnel.profile.identity_file,
          localBind: tunnel.profile.local_bind,
          localPort: tunnel.profile.local_port,
          remoteHost: tunnel.profile.remote_host,
          remotePort: tunnel.profile.remote_port,
        },
        status: tunnel.status,
        elapsed: tunnel.elapsed,
        lastError: tunnel.last_error,
      } satisfies ActiveTunnel;
      tunnels = tunnels.some((item) => item.id === converted.id)
        ? tunnels.map((item) => (item.id === converted.id ? converted : item))
        : [converted, ...tunnels];
    }
    const entry = backendLogToEntry(event);
    if (entry) logs = [entry, ...logs];
    if (event.event === "backend_exited") {
      backendReady = false;
      backendError = event.message ?? "桌面后端已退出。";
    }
  };

  let unlistenBackend: (() => void) | undefined;
  onMount(() => {
    if (!desktopRuntime) return;
    void (async () => {
      try {
        unlistenBackend = await subscribeBackendEvents(handleBackendEvent);
      } catch (error) {
        backendError = String(error);
      }
      await hydrateDesktop();
    })();
    const timer = window.setInterval(() => void refreshDesktopTunnels(), 1000);
    return () => {
      window.clearInterval(timer);
      unlistenBackend?.();
    };
  });

  const saveProfile = async (profile: ForwardProfile) => {
    try {
      const saved = desktopRuntime ? await saveBackendProfile(profile) : profile;
      const existing = profiles.some((item) => item.id === saved.id);
      profiles = existing ? profiles.map((item) => (item.id === saved.id ? saved : item)) : [saved, ...profiles];
      selectedProfile = { ...saved };
      editorKey += 1;
      activeTab = "favorites";
      addLog("success", `已保存收藏“${saved.name}”。`);
    } catch (error) {
      backendError = String(error);
      addLog("error", `收藏保存失败：${backendError}`);
    }
  };

  const deleteProfile = async (profile: ForwardProfile) => {
    if (!window.confirm(`确定删除收藏“${profile.name}”吗？`)) return;
    try {
      if (desktopRuntime) await deleteBackendProfile(profile.id);
      profiles = profiles.filter((item) => item.id !== profile.id);
      if (selectedProfile.id === profile.id) {
        selectedProfile = makeBlankProfile(hostAliases[0] ?? "");
        editorKey += 1;
      }
      addLog("info", `已删除收藏“${profile.name}”。`);
    } catch (error) {
      backendError = String(error);
      addLog("error", `删除收藏失败：${backendError}`);
    }
  };

  const refreshHosts = async () => {
    if (!desktopRuntime) return;
    try {
      hostAliases = await loadHosts();
      addLog("info", `已刷新 SSH Config，发现 ${hostAliases.length} 个别名。`);
    } catch (error) {
      backendError = String(error);
      addLog("error", `刷新 SSH Config 失败：${backendError}`);
    }
  };

  const getFreePort = async (bindAddress: string) => {
    if (desktopRuntime) return findAvailablePort(bindAddress);
    return Math.floor(10000 + Math.random() * 2000);
  };

  const chooseIdentityPath = async () => {
    return chooseIdentityFile();
  };

  const startTunnel = async (profile: ForwardProfile) => {
    if (profile.localBind === "0.0.0.0" && !window.confirm("监听 0.0.0.0 会让局域网内的其他设备也可能访问此端口。\n\n确定继续吗？")) {
      return;
    }
    if (desktopRuntime) {
      try {
        const active = await startBackendTunnel(profile);
        tunnels = [active, ...tunnels.filter((item) => item.id !== active.id)];
        selectedTunnelId = active.id;
        activeTab = "running";
        addLog("info", `正在启动“${profile.name}”：localhost:${profile.localPort} → ${profile.remoteHost}:${profile.remotePort}。`);
      } catch (error) {
        backendError = String(error);
        addLog("error", `无法启动转发：${backendError}`);
      }
      return;
    }

    const existing = profiles.some((item) => item.id === profile.id);
    if (!existing && profile.name) profiles = [profile, ...profiles];
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

  const stopTunnel = async (tunnel: ActiveTunnel) => {
    if (desktopRuntime) {
      try {
        await stopBackendTunnel(tunnel.id);
        addLog("info", `已停止“${tunnel.profile.name}”。`);
      } catch (error) {
        backendError = String(error);
        addLog("error", `停止转发失败：${backendError}`);
      }
      return;
    }
    tunnels = tunnels.map((item) => (item.id === tunnel.id ? { ...item, status: "stopped" } : item));
    addLog("info", `已停止“${tunnel.profile.name}”。`);
  };

  const changePort = async (tunnel: ActiveTunnel) => {
    const entered = window.prompt("请输入新的本地端口：", String(tunnel.profile.localPort));
    if (entered === null) return;
    const nextPort = Number(entered.trim());
    if (!Number.isInteger(nextPort) || nextPort < 1 || nextPort > 65535) {
      backendError = "本地端口必须是 1 到 65535 之间的整数。";
      return;
    }
    if (desktopRuntime) {
      try {
        const replacement = await changeTunnelPort(tunnel.id, nextPort);
        tunnels = tunnels.map((item) => (item.id === tunnel.id ? replacement : item));
        addLog("success", `已将“${tunnel.profile.name}”的本地端口改为 ${nextPort}。`);
      } catch (error) {
        backendError = String(error);
        addLog("error", `更改端口失败：${backendError}`);
      }
      return;
    }
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

    <div class="sidebar-demo-note"><span class:demo-dot--green={desktopRuntime && backendReady} class="demo-dot"></span> {desktopRuntime ? (backendReady ? "桌面后端 · 已连接" : "桌面后端 · 连接中") : "前端预览 · 演示数据"}</div>

    <nav class="sidebar-nav" aria-label="工作区导航">
      <button class:active={activeTab === "running"} type="button" onclick={() => (activeTab = "running")}><Icon name="link" size={17} /> 运行中的转发 <span>{tunnels.filter((item) => item.status === "running" || item.status === "connecting").length}</span></button>
      <button class:active={activeTab === "favorites"} type="button" onclick={() => (activeTab = "favorites")}><Icon name="book" size={17} /> 收藏 <span>{profiles.length}</span></button>
      <button class:active={activeTab === "logs"} type="button" onclick={() => (activeTab = "logs")}><Icon name="file" size={17} /> 日志 <span>{logs.length}</span></button>
    </nav>

    <div class="sidebar-section-label">系统</div>
    <div class="sidebar-nav sidebar-nav--secondary">
      <button type="button"><Icon name="server" size={17} /> OpenSSH <small>{desktopRuntime && backendReady ? "已连接" : "预览"}</small></button>
      <button type="button"><Icon name="sliders" size={17} /> 偏好设置</button>
    </div>

    <div class="sidebar-footer">
      <div class="sidebar-footer__status"><span class="status-dot status-dot--green"></span><span>本机服务正常</span></div>
      <div class="sidebar-footer__meta">{desktopRuntime ? "Python bridge · 开发版" : "Windows OpenSSH · 预览版"}</div>
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

    {#if backendError}
      <div class="backend-banner"><span class="status-dot"></span><span>{backendError}</span><button type="button" onclick={() => (backendError = "")} aria-label="关闭错误提示"><Icon name="close" size={15} /></button></div>
    {/if}

    <div class="content-grid">
      <div class="editor-column">
        {#key editorKey}
          <ProfileEditor initialProfile={selectedProfile} {hostAliases} onSave={saveProfile} onStart={startTunnel} onRefreshHosts={refreshHosts} onFindPort={getFreePort} onChooseIdentityFile={chooseIdentityPath} />
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
                  <button class="icon-button icon-button--danger" type="button" title="删除收藏" aria-label="删除收藏" onclick={() => deleteProfile(profile)}><Icon name="trash" size={16} /></button>
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
