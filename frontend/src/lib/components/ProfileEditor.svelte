<script lang="ts">
  import { onMount, untrack } from "svelte";
  import Icon from "./Icon.svelte";
  import type { ConnectionType, ForwardProfile } from "../types";

  interface Props {
    initialProfile: ForwardProfile;
    disabled?: boolean;
    hostAliases: string[];
    autoSelectPort: boolean;
    onSave: (profile: ForwardProfile) => void | Promise<void | boolean>;
    onStart: (profile: ForwardProfile) => void | Promise<void>;
    onRefreshHosts: () => void | Promise<void>;
    onFindPort: (bindAddress: ForwardProfile["localBind"]) => number | Promise<number>;
    onChooseIdentityFile: () => string | null | Promise<string | null>;
    onReset: () => void;
    onStartAndSave: (profile: ForwardProfile) => void | Promise<void>;
  }

  let { disabled = false, initialProfile, hostAliases, autoSelectPort, onSave, onStart, onRefreshHosts, onFindPort, onChooseIdentityFile, onReset, onStartAndSave }: Props = $props();
  const initial: ForwardProfile = { ...untrack(() => initialProfile) };
  let connectionType = $state<ConnectionType>(initial.connectionType);
  let name = $state(initial.name);
  let sshHost = $state(initial.sshHost);
  let sshPort = $state(String(initial.sshPort));
  let sshUser = $state(initial.sshUser);
  let identityFile = $state(initial.identityFile);
  let localBind = $state<ForwardProfile["localBind"]>(initial.localBind);
  let localPort = $state(String(initial.localPort));
  let remoteHost = $state(initial.remoteHost);
  let remotePort = $state(String(initial.remotePort));

  let error = $state("");
  let busy = $state(false);
  let findingPort = $state(false);
  let fieldErrors = $state<Record<string, string>>({});
  let hostPickerOpen = $state(false);
  let hostPickerQuery = $state("");

  const filteredHostAliases = $derived(
    hostAliases.filter((alias) => alias.toLowerCase().includes(hostPickerQuery.trim().toLowerCase())).slice(0, 100),
  );

  const openHostPicker = () => {
    hostPickerQuery = "";
    hostPickerOpen = true;
  };

  const toggleHostPicker = () => {
    hostPickerOpen = !hostPickerOpen;
    if (hostPickerOpen) hostPickerQuery = "";
  };

  const closeHostPicker = () => {
    window.setTimeout(() => (hostPickerOpen = false), 120);
  };

  const selectHost = (alias: string) => {
    sshHost = alias;
    hostPickerQuery = "";
    hostPickerOpen = false;
  };

  const findPort = async () => {
    if (findingPort || disabled) return;
    findingPort = true;
    error = "";
    const bind = localBind;
    const previous = localPort;
    try {
      const port = await onFindPort(bind);
      if (localBind === bind && localPort === previous) localPort = String(port);
    } catch (cause) { error = `无法选择空闲端口：${String(cause)}`; }
    finally { findingPort = false; }
  };
  onMount(() => {
    if (autoSelectPort && !initial.name) void findPort();
  });

  const submit = async (action: Props["onSave"] | Props["onStart"]) => {
    if (busy || disabled || findingPort) return;
    const errors: Record<string, string> = {};
    const hostId = connectionType === "config" ? "config-host" : "custom-host";
    if (!sshHost.trim() || /^-/.test(sshHost.trim()) || /\s/.test(sshHost.trim())) errors[hostId] = "请填写有效的 SSH 主机或别名。";
    if (!remoteHost.trim() || /^-/.test(remoteHost.trim()) || /\s/.test(remoteHost.trim())) errors["remote-host"] = "请填写有效的目标主机。";
    const ports = [["local-port", localPort, "本地端口"], ["remote-port", remotePort, "目标端口"]];
    if (connectionType === "custom") ports.push(["ssh-port", sshPort, "SSH 端口"]);
    for (const [id, value, label] of ports) {
      if (!/^\d+$/.test(value.trim()) || Number(value) < 1 || Number(value) > 65535) errors[id] = `${label}必须是 1 到 65535 之间的整数。`;
    }
    fieldErrors = errors;
    error = Object.values(errors)[0] ?? "";
    if (error) { document.getElementById(Object.keys(errors)[0])?.focus(); return; }
    busy = true;
    try { await action(buildProfile()); } catch (cause) { error = String(cause); }
    finally { busy = false; }
  };

  const buildProfile = (): ForwardProfile => ({
    ...initial,
    name: name.trim() || `${remoteHost.trim() || "目标服务"}:${Number.isFinite(Number(remotePort)) ? Number(remotePort) : remotePort.trim()}`,
    connectionType,
    sshHost: sshHost.trim(),
    sshPort: connectionType === "config" ? 22 : Number(sshPort),
    sshUser: sshUser.trim(),
    identityFile: identityFile.trim(),
    localBind,
    localPort: Number(localPort),
    remoteHost: remoteHost.trim(),
    remotePort: Number(remotePort),
  });
</script>

<section class="editor-card">
  <div class="section-heading">
    <div>
      <span class="section-kicker">连接配置</span>
      <h2>{initial.name ? "编辑配置" : "新建转发"}</h2>
    </div>
      <span class="section-index">01</span>
      <button class="button button--quiet editor-reset" type="button" disabled={busy} onclick={onReset}>新建</button>
  </div>

  <div class="editor-form-content">
    <div class="connection-tabs" role="tablist" aria-label="连接类型">
      <button class:active={connectionType === "config"} type="button" role="tab" aria-selected={connectionType === "config"} onclick={() => (connectionType = "config")}>
        <Icon name="file" size={16} /> SSH Config
      </button>
      <button class:active={connectionType === "custom"} type="button" role="tab" aria-selected={connectionType === "custom"} onclick={() => (connectionType = "custom")}>
        <Icon name="sliders" size={16} /> 自定义主机
      </button>
    </div>

  {#if connectionType === "config"}
    <div class="field-block">
      <label for="config-host">SSH Config 主机</label>
      <div class="host-picker" role="combobox" aria-expanded={hostPickerOpen} aria-controls="ssh-host-options">
        <div class="field-with-action">
          <input aria-invalid={Boolean(fieldErrors["config-host"])} aria-describedby={fieldErrors["config-host"] ? "editor-error" : undefined} id="config-host" autocomplete="off" bind:value={sshHost} placeholder="例如 production" onfocus={openHostPicker} oninput={() => { hostPickerQuery = sshHost; hostPickerOpen = true; }} onblur={closeHostPicker} />
          <button class:host-picker-toggle--open={hostPickerOpen} class="small-button host-picker-toggle" type="button" aria-label={hostPickerOpen ? "收起 SSH 主机列表" : "显示 SSH 主机列表"} aria-expanded={hostPickerOpen} onmousedown={(event) => event.preventDefault()} onclick={toggleHostPicker}><Icon name="chevron" size={16} /></button>
          <button class="small-button" type="button" title="刷新 SSH Config" aria-label="刷新 SSH Config" onclick={onRefreshHosts}><Icon name="refresh" size={16} /></button>
        </div>
        {#if hostPickerOpen}
          <div id="ssh-host-options" class="host-picker__menu" role="listbox" aria-label="SSH 主机列表">
            {#each filteredHostAliases as alias (alias)}
              <button class="host-picker__option" type="button" role="option" aria-selected={alias === sshHost} onmousedown={(event) => event.preventDefault()} onclick={() => selectHost(alias)}>{alias}</button>
            {:else}
              <span class="host-picker__empty">没有匹配的 SSH 主机</span>
            {/each}
          </div>
        {/if}
      </div>
      <p class="field-help">{hostAliases.length ? `已读取 ${hostAliases.length} 个具体 SSH 主机，可输入关键字筛选。` : "未发现 SSH 别名；可输入别名或切换自定义主机。"}</p>
    </div>
  {:else}
    <div class="field-grid field-grid--host">
      <div class="field-block">
        <label for="custom-host">主机 / IP</label>
        <input aria-invalid={Boolean(fieldErrors["custom-host"])} aria-describedby={fieldErrors["custom-host"] ? "editor-error" : undefined} id="custom-host" bind:value={sshHost} placeholder="例如 192.0.2.10" />
      </div>
      <div class="field-block">
        <label for="ssh-port">SSH 端口</label>
        <input aria-invalid={Boolean(fieldErrors["ssh-port"])} aria-describedby={fieldErrors["ssh-port"] ? "editor-error" : undefined} id="ssh-port" bind:value={sshPort} inputmode="numeric" />
      </div>
    </div>
    <div class="field-grid field-grid--host">
      <div class="field-block">
        <label for="ssh-user">用户名</label>
        <input id="ssh-user" bind:value={sshUser} placeholder="可选" />
      </div>
      <div class="field-block">
        <label for="identity-file">私钥路径</label>
        <div class="field-with-action">
          <input id="identity-file" bind:value={identityFile} placeholder="可选" />
          <button class="small-button" type="button" title="选择 SSH 私钥" aria-label="选择 SSH 私钥" onclick={async () => { try { const selected = await onChooseIdentityFile(); if (selected) identityFile = selected; } catch (cause) { error = String(cause); } }}><Icon name="file" size={16} /></button>
        </div>
      </div>
    </div>
  {/if}

  <div class="form-divider"></div>

  <div class="section-heading section-heading--compact">
    <div>
      <span class="section-kicker">转发规则</span>
      <h2>本地 → 远程</h2>
    </div>
    <span class="section-index">02</span>
  </div>

  <div class="field-block">
    <label for="profile-name">配置名称</label>
    <input id="profile-name" bind:value={name} placeholder="例如：本地 PostgreSQL" />
  </div>

  <div class="field-grid">
    <div class="field-block">
      <label for="local-bind">监听地址</label>
      <select id="local-bind" bind:value={localBind}>
        <option value="127.0.0.1">127.0.0.1 · 仅本机</option>
        <option value="::1">::1 · IPv6 本机</option>
        <option value="0.0.0.0">0.0.0.0 · 局域网</option>
      </select>
    </div>
    <div class="field-block">
      <label for="local-port">本地端口</label>
      <div class="field-with-action">
        <input aria-invalid={Boolean(fieldErrors["local-port"])} aria-describedby={fieldErrors["local-port"] ? "editor-error" : undefined} id="local-port" bind:value={localPort} inputmode="numeric" />
        <button class="small-button small-button--text" type="button" disabled={disabled || findingPort || busy} onclick={findPort}>{findingPort ? "查找中" : "自动"}</button>
      </div>
    </div>
  </div>

  <div class="field-grid">
    <div class="field-block">
      <label for="remote-host">目标主机</label>
      <input aria-invalid={Boolean(fieldErrors["remote-host"])} aria-describedby={fieldErrors["remote-host"] ? "editor-error" : undefined} id="remote-host" bind:value={remoteHost} placeholder="127.0.0.1" />
    </div>
    <div class="field-block">
      <label for="remote-port">目标端口</label>
      <input aria-invalid={Boolean(fieldErrors["remote-port"])} aria-describedby={fieldErrors["remote-port"] ? "editor-error" : undefined} id="remote-port" bind:value={remotePort} inputmode="numeric" />
    </div>
  </div>

    <p class="form-note"><Icon name="link" size={15} /> 目标地址由 SSH 服务器解析，适合访问服务器内网服务。</p>

    {#if error}<p id="editor-error" class="dialog-error editor-error" role="alert">{error}</p>{/if}
    {#if busy}<p class="field-help" role="status">正在处理，请稍候…</p>{/if}
  </div>

  <div class="editor-actions">
    <button class="button button--primary" type="button" disabled={disabled || busy || findingPort} onclick={() => submit(onStart)}><Icon name="play" size={16} /> 启动转发</button>
    <button class="button button--secondary" type="button" disabled={disabled || busy || findingPort} onclick={() => submit(onSave)}><Icon name="book" size={16} /> 保存收藏</button>
    <button class="button button--secondary editor-actions__wide" type="button" disabled={disabled || busy || findingPort} onclick={() => submit(onStartAndSave)}><Icon name="play" size={16} /> 启动并收藏</button>
  </div>
</section>
