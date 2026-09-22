<script lang="ts">
  import { onMount } from "svelte";
  import { getCurrentWindow } from "@tauri-apps/api/window";
  import ConfirmDialog from "./lib/components/ConfirmDialog.svelte";
  import FavoritesPanel from "./lib/components/FavoritesPanel.svelte";
  import Icon from "./lib/components/Icon.svelte";
  import LogPanel from "./lib/components/LogPanel.svelte";
  import PortDialog from "./lib/components/PortDialog.svelte";
  import PreferencesModal from "./lib/components/PreferencesModal.svelte";
  import ProfileEditor from "./lib/components/ProfileEditor.svelte";
  import RunningPanel from "./lib/components/RunningPanel.svelte";
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
    loadTrayStatus,
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
  let activeTab = $state<WorkspaceTab>("create");
  let profiles = $state<ForwardProfile[]>(desktopRuntime ? [] : [...sampleProfiles]);
  let tunnels = $state<ActiveTunnel[]>(desktopRuntime ? [] : [...sampleTunnels]);
  let logs = $state<LogEntry[]>(desktopRuntime ? [] : [...sampleLogs]);
  let selectedTunnelId = $state("sample-tunnel-production");
  // 预览模式也用全新的 id 预填示例数据，保持“新建模式 = 全新配置”的语义一致。
  let selectedProfile = $state<ForwardProfile>(desktopRuntime ? makeBlankProfile() : { ...sampleProfiles[0], id: globalThis.crypto?.randomUUID?.() ?? "preview-profile" });
  let editingProfileId = $state<string | null>(null);
  // 保存成功后用于“启动并保存”：保存会把编辑器重置为空白新建，启动必须使用刚落库的配置。
  let lastSavedProfile = $state<ForwardProfile | null>(null);
  let editorKey = $state(0);
  let copiedEndpoint = $state("");
  let backendReady = $state(!desktopRuntime);
  let backendError = $state("");
  let trayAvailable = $state(!desktopRuntime);
  let hostAliases = $state<string[]>(desktopRuntime ? [] : ["production", "staging", "bastion"]);
  let sshAvailable = $state(false);
  let pendingStarts = $state<string[]>([]);
  let pendingTunnels = $state<string[]>([]);
  let refreshing = false;
  let preferencesOpen = $state(false);
  let localStatusOpen = $state(false);
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
    logs = [{ id: `${Date.now()}-${Math.random()}`, time, level, message }, ...logs].slice(0, 500);
  };

  const selectTunnel = (id: string) => {
    selectedTunnelId = id;
  };

  const selectProfile = (profile: ForwardProfile) => {
    selectedProfile = { ...profile };
    editingProfileId = profile.id;
    editorKey += 1;
    activeTab = "create";
  };

  const resetEditor = () => {
    selectedProfile = makeBlankProfile(hostAliases[0] ?? "");
    editingProfileId = null;
    editorKey += 1;
    activeTab = "create";
  };

  // 左侧“新建转发”必须回到全新的新建模式，避免继承已保存配置的 id 造成覆盖。
  const openCreateTab = () => {
    resetEditor();
  };

  // 编辑模式只有在目标收藏仍然存在时才成立，避免删除后误判为覆盖保存。
  const isEditingProfile = $derived(editingProfileId !== null && profiles.some((item) => item.id === editingProfileId));

  const savePreferences = (next: AppPreferences) => {
    preferences = next;
    writePreferences(next);
    preferencesOpen = false;
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
      await saveWindowState();
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
        editingProfileId = null;
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
      sshAvailable = snapshot.sshAvailable;
      backendError = "";
      profiles = snapshot.profiles;
      tunnels = snapshot.tunnels;
      logs = [];
      // 启动后一律停留在空白新建配置，避免新建模式继承收藏里的 id 而覆盖已保存配置。
      selectedProfile = makeBlankProfile(hostAliases[0] ?? "");
      editingProfileId = null;
      editorKey += 1;
      backendReady = true;
      if (snapshot.warning) addLog("error", snapshot.warning);
    } catch (error) {
      backendError = String(error);
      addLog("error", `无法连接桌面后端：${backendError}`);
    }
  };

  const refreshDesktopTunnels = async () => {
    if (!desktopRuntime || !backendReady || refreshing || pendingTunnels.length) return;
    refreshing = true;
    try {
      tunnels = await loadTunnels();
    } catch (error) {
      backendError = String(error);
    } finally {
      refreshing = false;
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
    if (entry) logs = [entry, ...logs].slice(0, 500);
    if (event.event === "backend_exited") {
      backendReady = false;
      backendError = event.message ?? "桌面后端已退出。";
    }
  };

  let unlistenBackend: (() => void) | undefined;
  onMount(() => {
    if (!desktopRuntime) return;
    void (async () => {
      const window = getCurrentWindow();
      await window.show();
      await window.unminimize();
      await window.setFocus();
      await window.setTitle("SSH 端口转发助手");
    })();
    const closeListener = getCurrentWindow().onCloseRequested(async (event) => {
      const runningCount = tunnels.filter((item) => item.status === "running" || item.status === "connecting").length;
      if (closeDialogPending) {
        closeDialogPending = false;
        return;
      }
      if (trayAvailable && preferences.closeToTray) {
        event.preventDefault();
        await saveWindowState();
        await getCurrentWindow().hide();
        return;
      }
      if (preferences.confirmOnExit && runningCount > 0) {
        event.preventDefault();
        closeDialogCount = runningCount;
        closeDialogOpen = true;
      } else {
        event.preventDefault();
        await saveWindowState();
        closeDialogPending = true;
        await getCurrentWindow().close();
      }
    });
    void restoreWindowState();
    void (async () => {
      try {
        unlistenBackend = await subscribeBackendEvents(handleBackendEvent);
        for (let attempt = 0; attempt < 20; attempt += 1) {
          trayAvailable = await loadTrayStatus();
          if (trayAvailable) break;
          await new Promise((resolve) => window.setTimeout(resolve, 100));
        }
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
      // 新建模式必须写入一个新的收藏 id；只有编辑模式才沿用原有 id 更新已有配置。
      const payload: ForwardProfile = isEditingProfile && editingProfileId !== null
        ? { ...profile, id: editingProfileId as string }
        : { ...profile, id: globalThis.crypto?.randomUUID?.() ?? `profile-${Date.now()}` };
      const saved = desktopRuntime ? await saveBackendProfile(payload) : payload;
      const existing = profiles.some((item) => item.id === saved.id);
      profiles = existing ? profiles.map((item) => (item.id === saved.id ? saved : item)) : [saved, ...profiles];
      // 保存完成后回到全新的新建模式，避免下一次保存覆盖刚刚写好的收藏。
      selectedProfile = makeBlankProfile(hostAliases[0] ?? "");
      editingProfileId = null;
      editorKey += 1;
      activeTab = "favorites";
      addLog("success", existing ? `已更新收藏“${saved.name}”。` : `已新增收藏“${saved.name}”。`);
      lastSavedProfile = saved;
      return true;
    } catch (error) {
      backendError = String(error);
      addLog("error", `收藏保存失败：${backendError}`);
      return false;
    }
  };

  const startAndSave = async (profile: ForwardProfile) => {
    // 保存会把编辑器重置为空白新建，因此这里启动刚落库的那份配置。
    if (await saveProfile(profile)) {
      const saved = lastSavedProfile;
      if (saved) await startTunnel({ ...saved });
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
    if (pendingStarts.includes(profile.id) || (desktopRuntime && !backendReady)) return;
    pendingStarts = [...pendingStarts, profile.id];
    try {
      await performStart(profile);
    } finally {
      pendingStarts = pendingStarts.filter((id) => id !== profile.id);
    }
  };

  const performStart = async (profile: ForwardProfile) => {
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
    if (pendingTunnels.includes(tunnel.id)) return;
    pendingTunnels = [...pendingTunnels, tunnel.id];
    try { await performStop(tunnel); } finally { pendingTunnels = pendingTunnels.filter((id) => id !== tunnel.id); }
  };

  const performStop = async (tunnel: ActiveTunnel) => {
    if (desktopRuntime) {
      try {
        await stopBackendTunnel(tunnel.id);
        tunnels = await loadTunnels();
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
    if (pendingTunnels.includes(tunnel.id)) return;
    pendingTunnels = [...pendingTunnels, tunnel.id];
    try { await performRestart(tunnel); } finally { pendingTunnels = pendingTunnels.filter((id) => id !== tunnel.id); }
  };

  const performRestart = async (tunnel: ActiveTunnel) => {
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
        tunnels = await loadTunnels();
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
    if (!tunnel) return;
    if (desktopRuntime) {
      try {
        const replacement = await changeTunnelPort(tunnel.id, nextPort);
        tunnels = await loadTunnels();
        selectedTunnelId = replacement.id;
        portDialogTunnel = null;
        addLog("success", `已将“${tunnel.profile.name}”的本地端口改为 ${nextPort}。`);
      } catch (error) {
        backendError = String(error);
        addLog("error", `更改端口失败：${backendError}`);
        throw error;
      }
      return;
    }
    portDialogTunnel = null;
    const profile = { ...tunnel.profile, localPort: nextPort };
    tunnels = tunnels.map((item) => (item.id === tunnel.id ? { ...item, profile } : item));
    addLog("success", `已将“${tunnel.profile.name}”的本地端口改为 ${nextPort}。`);
  };

  const copyEndpoint = async (tunnel: ActiveTunnel) => {
    const endpoint = formatLocalEndpoint(tunnel.profile);
    try {
      if (!navigator.clipboard) throw new Error("剪贴板不可用");
      await navigator.clipboard.writeText(endpoint);
      copiedEndpoint = endpoint;
      addLog("success", `已复制本地地址：${endpoint}。`);
    } catch (error) {
      backendError = `无法复制地址，请手动复制：${endpoint}。${String(error)}`;
      return;
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

<div class="app-window" class:desktop={desktopRuntime}>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-brand" data-tauri-drag-region="deep">
        <img class="sidebar-brand__logo" src="/ssh-forward-logo.svg" alt="" />
        <div><strong>SSH Forward</strong><span>端口转发工作台</span></div>
      </div>

      <div class="sidebar-section-label">工作区</div>
      <nav class="sidebar-nav" aria-label="工作区导航">
        <button class:active={activeTab === "create"} type="button" onclick={openCreateTab}><Icon name="plus" size={17} /> 新建转发</button>
        <button class:active={activeTab === "running"} type="button" onclick={() => (activeTab = "running")}><Icon name="link" size={17} /> 运行中的转发 <span>{tunnels.filter((item) => item.status === "running" || item.status === "connecting").length}</span></button>
        <button class:active={activeTab === "favorites"} type="button" onclick={() => (activeTab = "favorites")}><Icon name="book" size={17} /> 收藏 <span>{profiles.length}</span></button>
        <button class:active={activeTab === "logs"} type="button" onclick={() => (activeTab = "logs")}><Icon name="file" size={17} /> 日志 <span>{logs.length}</span></button>
      </nav>

      <div class="sidebar-actions">
        <div class="sidebar-section-label">工具</div>
        <button type="button" onclick={() => (preferencesOpen = true)}><Icon name="sliders" size={17} /> 偏好设置</button>
      </div>

      <section class="sidebar-status" aria-label="系统状态">
        <div class="sidebar-section-label">状态</div>
        <div class="sidebar-status-card">
          <div class="sidebar-status-row">
            <span class="sidebar-status-row__icon"><Icon name="server" size={15} /></span>
            <span><strong>Rust 后端</strong><small>{desktopRuntime ? (backendReady ? "已连接" : "未连接") : "预览模式"}</small></span>
            <span class="status-dot" class:status-dot--green={backendReady}></span>
          </div>
          <div class="sidebar-status-row">
            <span class="sidebar-status-row__icon"><Icon name="server" size={15} /></span>
            <span><strong>OpenSSH</strong><small>{desktopRuntime ? (backendReady ? (sshAvailable ? "可用" : "未安装") : "待检测") : "预览"}</small></span>
            <span class="status-dot" class:status-dot--green={sshAvailable}></span>
          </div>
        </div>
      </section>

      <div class="sidebar-footer">
        <div class="sidebar-footer__meta">{desktopRuntime ? "SSH Forward · v0.2.4" : "SSH Forward · 预览版"}</div>
      </div>
    </aside>

    <main class="main-content">
      {#if desktopRuntime}
        <div class="main-drag-region" data-tauri-drag-region aria-hidden="true"></div>
        <div class="window-controls" data-tauri-drag-region="false">
          <button class="window-control" type="button" aria-label="最小化" title="最小化" onclick={minimizeWindow}><Icon name="minus" size={14} /></button>
          <button class="window-control" type="button" aria-label="最大化" title="最大化" onclick={toggleMaximizeWindow}><Icon name="maximize" size={12} /></button>
          <button class="window-control window-control--close" type="button" aria-label="关闭" title="关闭" onclick={closeWindow}><Icon name="close" size={14} /></button>
        </div>
      {/if}

      <header class="topbar">
        <div>
          <span class="section-kicker">{activeTab === "create" ? "新建连接" : "工作区"}</span>
          <h1>{activeTab === "create" ? "新增 SSH 转发" : activeTab === "running" ? "运行中的转发" : activeTab === "favorites" ? "收藏配置" : "运行日志"}</h1>
        </div>
        <div class="topbar-actions">
          {#if copiedEndpoint}<span class="toast"><Icon name="check" size={15} /> 已复制 {copiedEndpoint}</span>{/if}
          <div class="local-status">
            <button class="profile-chip" class:profile-chip--open={localStatusOpen} type="button" aria-expanded={localStatusOpen} aria-controls="local-status-popover" onclick={() => (localStatusOpen = !localStatusOpen)}>
              <span class="profile-avatar"><Icon name="server" size={15} /></span><span>本机</span><Icon name="chevron" size={14} />
            </button>
            {#if localStatusOpen}
              <div id="local-status-popover" class="local-status-popover" role="status">
                <div class="local-status-popover__heading"><strong>本机状态</strong><span>当前环境</span></div>
                <div class="local-status-popover__row"><span>Rust 后端</span><strong>{backendReady ? "已连接" : "未连接"}</strong></div>
                <div class="local-status-popover__row"><span>OpenSSH</span><strong>{sshAvailable ? "可用" : "未检测到"}</strong></div>
                <div class="local-status-popover__row"><span>活动转发</span><strong>{tunnels.filter((item) => item.status === "running" || item.status === "connecting").length}</strong></div>
                {#if !backendReady}<button class="button button--secondary button--small" type="button" onclick={hydrateDesktop}>重新检测</button>{/if}
              </div>
            {/if}
          </div>
        </div>
      </header>

      {#if backendError}
        <div class="backend-banner" role="alert"><span class="status-dot"></span><span>{backendError}</span>{#if !backendReady}<button class="button button--secondary" type="button" onclick={hydrateDesktop}>重新连接</button>{/if}<button type="button" onclick={() => (backendError = "")} aria-label="关闭错误提示"><Icon name="close" size={15} /></button></div>
      {/if}

      {#if activeTab === "create"}
        <div class="content-grid content-grid--create">
          <div class="editor-column">
            {#key editorKey}
              <ProfileEditor disabled={!backendReady} editing={isEditingProfile} initialProfile={selectedProfile} {hostAliases} autoSelectPort={preferences.autoSelectPort} onSave={saveProfile} onStart={startTunnel} onRefreshHosts={refreshHosts} onFindPort={getFreePort} onChooseIdentityFile={chooseIdentityPath} onReset={resetEditor} onStartAndSave={startAndSave} />
            {/key}
          </div>
          <RunningPanel tunnels={tunnels.filter((item) => item.status === "running" || item.status === "connecting")} {selectedTunnelId} {pendingTunnels} emptyMessage="填写左侧配置并启动后，这里会显示正在运行的连接。" onSelect={selectTunnel} onCopy={copyEndpoint} onPortChange={changePort} onStop={stopTunnel} onRestart={restartTunnel} onDelete={requestDeleteTunnel} onClear={clearFinished} />
        </div>
      {:else if activeTab === "running"}
        <RunningPanel tunnels={tunnels} {selectedTunnelId} {pendingTunnels} emptyMessage="打开新建转发页面，填写连接信息后启动第一条本地隧道。" onSelect={selectTunnel} onCopy={copyEndpoint} onPortChange={changePort} onStop={stopTunnel} onRestart={restartTunnel} onDelete={requestDeleteTunnel} onClear={clearFinished} />
      {:else if activeTab === "favorites"}
        <FavoritesPanel {profiles} {backendReady} {pendingStarts} onEdit={selectProfile} onDelete={requestDeleteProfile} onStart={startTunnel} />
      {:else}
        <section class="page-panel page-panel--logs"><LogPanel logs={logs} onClear={clearLogs} /></section>
      {/if}
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
