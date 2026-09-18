<script lang="ts">
  import { onMount } from "svelte";
  import { getCurrentWindow } from "@tauri-apps/api/window";
  import ConfirmDialog from "./lib/components/ConfirmDialog.svelte";
  import Icon from "./lib/components/Icon.svelte";
  import LogPanel from "./lib/components/LogPanel.svelte";
  import PortDialog from "./lib/components/PortDialog.svelte";
  import PreferencesModal from "./lib/components/PreferencesModal.svelte";
  import ProfileEditor from "./lib/components/ProfileEditor.svelte";
  import StatusBadge from "./lib/components/StatusBadge.svelte";
  import TunnelCard from "./lib/components/TunnelCard.svelte";
  import {
    backendLogToEntry,
    changeTunnelPort,
    chooseIdentityFile,
    clearFinishedTunnels,
    deleteProfile as deleteBackendProfile,
    deleteTunnel as deleteBackendTunnel,
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
  import { formatLocalEndpoint, formatRemoteEndpoint } from "./lib/endpoints";
  import type { ActiveTunnel, ForwardProfile, LogEntry, WorkspaceTab } from "./lib/types";
  import { readPreferences, writePreferences, type AppPreferences } from "./lib/preferences";
  import { restoreWindowState, saveWindowState } from "./lib/window-state";

  const desktopRuntime = isDesktopRuntime();
  let preferences = $state<AppPreferences>(readPreferences());
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
  let preferencesOpen = $state(false);
  let portDialogTunnel = $state<ActiveTunnel | null>(null);
  let profileToDelete = $state<ForwardProfile | null>(null);
  let tunnelToDelete = $state<ActiveTunnel | null>(null);
  let exposureDialogOpen = $state(false);
  let exposureResolver: ((confirmed: boolean) => void) | null = null;
  let closeDialogCount = $state(0);
  let closeDialogOpen = $state(false);
  let closeDialogPending = false;

  function makeBlankProfile(host = ""): ForwardProfile {
    return {
      id: globalThis.crypto?.randomUUID?.() ?? `profile-${Date.now()}`,
      name: "",
      connectionType: "config",
      sshHost: host,
      sshPort: 22,
      sshUser: "",
      identityFile: "",
      localBind: preferences.defaultLocalBind,
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

  const resetEditor = () => {
    selectedProfile = makeBlankProfile(hostAliases[0] ?? "");
    editorKey += 1;
  };

  const savePreferences = (next: AppPreferences) => {
    preferences = next;
    writePreferences(next);
    preferencesOpen = false;
    if (!selectedProfile.name) {
      selectedProfile = { ...selectedProfile, localBind: next.defaultLocalBind };
      editorKey += 1;
    }
    addLog("success", "偏好设置已保存。");
  };

  const askNetworkExposure = (): Promise<boolean> => {
    exposureDialogOpen = true;
    return new Promise((resolve) => {
      exposureResolver = resolve;
    });
  };

  const resolveNetworkExposure = (confirmed: boolean) => {
    exposureDialogOpen = false;
    exposureResolver?.(confirmed);
    exposureResolver = null;
  };

  const cancelClose = () => {
    closeDialogOpen = false;
    closeDialogCount = 0;
  };

  const confirmClose = async () => {
    closeDialogOpen = false;
    closeDialogPending = true;
    try {
      await getCurrentWindow().close();
    } catch {
      closeDialogPending = false;
    }
  };

  const requestDeleteProfile = (profile: ForwardProfile) => {
    profileToDelete = profile;
  };

  const confirmDeleteProfile = async () => {
    const profile = profileToDelete;
    profileToDelete = null;
    if (!profile) return;
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

  const requestDeleteTunnel = (tunnel: ActiveTunnel) => {
    if (tunnel.status === "running" || tunnel.status === "connecting") return;
    tunnelToDelete = tunnel;
  };

  const confirmDeleteTunnel = async () => {
    const tunnel = tunnelToDelete;
    tunnelToDelete = null;
    if (!tunnel) return;
    try {
      if (desktopRuntime) await deleteBackendTunnel(tunnel.id);
      tunnels = tunnels.filter((item) => item.id !== tunnel.id);
      if (selectedTunnelId === tunnel.id) selectedTunnelId = "";
      addLog("info", `已删除“${tunnel.profile.name}”的结束记录。`);
    } catch (error) {
      backendError = String(error);
      addLog("error", `删除转发记录失败：${backendError}`);
    }
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
    void getCurrentWindow().setTitle("SSH 端口转发助手");
    const closeListener = getCurrentWindow().onCloseRequested((event) => {
      const runningCount = tunnels.filter((item) => item.status === "running" || item.status === "connecting").length;
      if (closeDialogPending) {
        closeDialogPending = false;
        return;
      }
      if (preferences.confirmOnExit && runningCount > 0) {
        event.preventDefault();
        closeDialogCount = runningCount;
        closeDialogOpen = true;
      }
    });
    void restoreWindowState();
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
      void closeListener.then((unlisten) => unlisten());
      void saveWindowState();
    };
  });

  const saveProfile = async (profile: ForwardProfile): Promise<boolean> => {
    try {
      const saved = desktopRuntime ? await saveBackendProfile(profile) : profile;
      const existing = profiles.some((item) => item.id === saved.id);
      profiles = existing ? profiles.map((item) => (item.id === saved.id ? saved : item)) : [saved, ...profiles];
      selectedProfile = { ...saved };
      editorKey += 1;
      activeTab = "favorites";
      addLog("success", `已保存收藏“${saved.name}”。`);
      return true;
    } catch (error) {
      backendError = String(error);
      addLog("error", `收藏保存失败：${backendError}`);
      return false;
    }
  };

  const startAndSave = async (profile: ForwardProfile) => {
    if (await saveProfile(profile)) await startTunnel(profile);
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

  const clearFinished = async () => {
    try {
      if (desktopRuntime) await clearFinishedTunnels();
      tunnels = tunnels.filter((item) => item.status === "running" || item.status === "connecting");
      addLog("info", "已清理结束的转发记录。" );
    } catch (error) {
      backendError = String(error);
      addLog("error", `清理结束记录失败：${backendError}`);
    }
  };

  const chooseIdentityPath = async () => {
    return chooseIdentityFile();
  };

  const startTunnel = async (profile: ForwardProfile) => {
    if (profile.localBind === "0.0.0.0" && !(await askNetworkExposure())) {
      return;
    }
    if (desktopRuntime) {
      try {
        const active = await startBackendTunnel(profile);
        tunnels = [active, ...tunnels.filter((item) => item.id !== active.id)];
        selectedTunnelId = active.id;
        activeTab = "running";
        addLog("info", `正在启动“${profile.name}”：${formatLocalEndpoint(profile)} → ${formatRemoteEndpoint(profile)}。`);
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
    addLog("info", `正在启动“${profile.name}”：${formatLocalEndpoint(profile)} → ${formatRemoteEndpoint(profile)}。`);
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

  const restartTunnel = async (tunnel: ActiveTunnel) => {
    if (tunnel.status === "running" || tunnel.status === "connecting") return;
    if (tunnel.profile.localBind === "0.0.0.0" && !(await askNetworkExposure())) return;

    if (desktopRuntime) {
      try {
        const active = await startBackendTunnel(tunnel.profile);
        try {
          await deleteBackendTunnel(tunnel.id);
        } catch (error) {
          backendError = String(error);
          addLog("error", `旧结束记录清理失败：${backendError}`);
        }
        tunnels = tunnels.map((item) => (item.id === tunnel.id ? active : item));
        selectedTunnelId = active.id;
        activeTab = "running";
        addLog("info", `已恢复“${tunnel.profile.name}”：${formatLocalEndpoint(tunnel.profile)} → ${formatRemoteEndpoint(tunnel.profile)}。`);
      } catch (error) {
        backendError = String(error);
        addLog("error", `恢复转发失败：${backendError}`);
      }
      return;
    }

    const restored: ActiveTunnel = {
      ...tunnel,
      id: `demo-tunnel-${Date.now()}`,
      status: "connecting",
      elapsed: "00:00",
      lastError: "",
      isSample: true,
    };
    tunnels = tunnels.map((item) => (item.id === tunnel.id ? restored : item));
    selectedTunnelId = restored.id;
    activeTab = "running";
    addLog("info", `正在恢复“${tunnel.profile.name}”。`);
    window.setTimeout(() => {
      tunnels = tunnels.map((item) => (item.id === restored.id ? { ...item, status: "running", elapsed: "00:01" } : item));
      addLog("success", `“${tunnel.profile.name}”已恢复转发。`);
    }, 850);
  };

  const changePort = async (tunnel: ActiveTunnel) => {
    if (tunnel.status !== "running" && tunnel.status !== "connecting") return;
    portDialogTunnel = tunnel;
  };

  const submitPortChange = async (nextPort: number) => {
    const tunnel = portDialogTunnel;
    portDialogTunnel = null;
    if (!tunnel) return;
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
    const endpoint = formatLocalEndpoint(tunnel.profile);
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

  const minimizeWindow = () => {
    if (desktopRuntime) void getCurrentWindow().minimize();
  };

  const toggleMaximizeWindow = () => {
    if (desktopRuntime) void getCurrentWindow().toggleMaximize();
  };

  const closeWindow = () => {
    if (desktopRuntime) void getCurrentWindow().close();
  };
</script>

<svelte:head>
  <meta name="description" content="集中管理 SSH 本地端口转发。" />
</svelte:head>

<div class="app-window">
  <div class="window-titlebar" data-tauri-drag-region>
    <div class="window-titlebar__identity" data-tauri-drag-region>
      <span class="window-titlebar__mark"><Icon name="link" size={13} /></span>
      <span>SSH Forwarder</span>
    </div>
    <div class="window-controls">
      <button class="window-control" type="button" aria-label="最小化" title="最小化" onclick={minimizeWindow}><Icon name="minus" size={14} /></button>
      <button class="window-control" type="button" aria-label="最大化" title="最大化" onclick={toggleMaximizeWindow}><Icon name="maximize" size={12} /></button>
      <button class="window-control window-control--close" type="button" aria-label="关闭" title="关闭" onclick={closeWindow}><Icon name="close" size={14} /></button>
    </div>
  </div>

  <div class="app-shell">
  <aside class="sidebar">

    <div class="sidebar-demo-note"><span class:demo-dot--green={desktopRuntime && backendReady} class="demo-dot"></span> {desktopRuntime ? (backendReady ? "桌面后端 · 已连接" : "桌面后端 · 连接中") : "前端预览 · 演示数据"}</div>

    <nav class="sidebar-nav" aria-label="工作区导航">
      <button class:active={activeTab === "running"} type="button" onclick={() => (activeTab = "running")}><Icon name="link" size={17} /> 运行中的转发 <span>{tunnels.filter((item) => item.status === "running" || item.status === "connecting").length}</span></button>
      <button class:active={activeTab === "favorites"} type="button" onclick={() => (activeTab = "favorites")}><Icon name="book" size={17} /> 收藏 <span>{profiles.length}</span></button>
      <button class:active={activeTab === "logs"} type="button" onclick={() => (activeTab = "logs")}><Icon name="file" size={17} /> 日志 <span>{logs.length}</span></button>
    </nav>

    <div class="sidebar-section-label">系统</div>
    <div class="sidebar-nav sidebar-nav--secondary">
      <button type="button"><Icon name="server" size={17} /> OpenSSH <small>{desktopRuntime && backendReady ? "已连接" : "预览"}</small></button>
      <button type="button" onclick={() => (preferencesOpen = true)}><Icon name="sliders" size={17} /> 偏好设置</button>
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
        <button class="icon-button icon-button--large" type="button" title="打开偏好设置" aria-label="打开偏好设置" onclick={() => (preferencesOpen = true)}><Icon name="sliders" size={18} /></button>
        <button class="profile-chip" type="button" aria-label="打开应用菜单"><span class="profile-avatar">T</span><span>本机</span><Icon name="chevron" size={15} /></button>
      </div>
    </header>

    {#if backendError}
      <div class="backend-banner"><span class="status-dot"></span><span>{backendError}</span><button type="button" onclick={() => (backendError = "")} aria-label="关闭错误提示"><Icon name="close" size={15} /></button></div>
    {/if}

    <div class="content-grid">
      <div class="editor-column">
        {#key editorKey}
          <ProfileEditor initialProfile={selectedProfile} {hostAliases} autoSelectPort={preferences.autoSelectPort} onSave={saveProfile} onStart={startTunnel} onRefreshHosts={refreshHosts} onFindPort={getFreePort} onChooseIdentityFile={chooseIdentityPath} onReset={resetEditor} onStartAndSave={startAndSave} />
        {/key}
      </div>

      <section class="workspace-column">
        <div class="workspace-header">
          <div>
            <span class="section-kicker">工作区</span>
            <h2>{activeTab === "running" ? "运行中的转发" : activeTab === "favorites" ? "收藏配置" : "运行日志"}</h2>
          </div>
          {#if activeTab === "running"}
            <div class="workspace-summary"><span class="summary-number">{tunnels.filter((item) => item.status === "running").length}</span><span>条连接正在运行</span>{#if tunnels.some((item) => item.status === "stopped" || item.status === "failed")}<button class="button button--quiet" type="button" onclick={clearFinished}>清理已结束</button>{/if}</div>
          {:else if activeTab === "favorites"}
            <button class="button button--secondary" type="button" onclick={() => (activeTab = "running")}><Icon name="plus" size={16} /> 新建转发</button>
          {/if}
        </div>

        {#if activeTab === "running"}
          <div class="tunnel-list">
            {#each tunnels as tunnel (tunnel.id)}
              <TunnelCard tunnel={tunnel} selected={selectedTunnelId === tunnel.id} onSelect={selectTunnel} onCopy={copyEndpoint} onPortChange={changePort} onStop={stopTunnel} onRestart={restartTunnel} onDelete={requestDeleteTunnel} />
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
              <article class="favorite-row" ondblclick={() => startTunnel(profile)}>
                <div class="favorite-icon"><Icon name="book" size={17} /></div>
                <div class="favorite-main">
                  <div class="eyebrow-row"><h3>{profile.name}</h3>{#if profile.isSample}<span class="sample-label">演示数据</span>{/if}</div>
                  <p>{profile.sshHost} · {formatLocalEndpoint(profile)} → {formatRemoteEndpoint(profile)}</p>
                </div>
                <div class="favorite-actions">
                  <button class="icon-button" type="button" title="编辑配置" aria-label="编辑配置" onclick={() => selectProfile(profile)}><Icon name="edit" size={16} /></button>
                  <button class="icon-button icon-button--danger" type="button" title="删除收藏" aria-label="删除收藏" onclick={() => requestDeleteProfile(profile)}><Icon name="trash" size={16} /></button>
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
</div>

{#if portDialogTunnel}
  <PortDialog currentPort={portDialogTunnel.profile.localPort} onCancel={() => (portDialogTunnel = null)} onConfirm={submitPortChange} />
{/if}

{#if profileToDelete}
  <ConfirmDialog title="删除收藏" message={`确定删除收藏“${profileToDelete.name}”吗？`} confirmLabel="删除收藏" danger onCancel={() => (profileToDelete = null)} onConfirm={confirmDeleteProfile} />
{/if}

{#if tunnelToDelete}
  <ConfirmDialog title="删除结束记录" message={`删除“${tunnelToDelete.profile.name}”后，这条连接记录将从列表中移除。`} confirmLabel="删除记录" danger onCancel={() => (tunnelToDelete = null)} onConfirm={confirmDeleteTunnel} />
{/if}

{#if exposureDialogOpen}
  <ConfirmDialog title="确认局域网监听" message="监听 0.0.0.0 会让同一网络中的其他设备也可能访问此端口。" confirmLabel="继续启动" onCancel={() => resolveNetworkExposure(false)} onConfirm={() => resolveNetworkExposure(true)} />
{/if}

{#if closeDialogOpen}
  <ConfirmDialog title="退出并停止转发" message={`当前有 ${closeDialogCount} 个转发正在运行。退出会全部停止，确定继续吗？`} confirmLabel="退出应用" onCancel={cancelClose} onConfirm={confirmClose} />
{/if}

{#if preferencesOpen}
  <PreferencesModal initial={preferences} onCancel={() => (preferencesOpen = false)} onSave={savePreferences} />
{/if}
