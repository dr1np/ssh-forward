<script lang="ts">
  import { untrack } from "svelte";
  import Icon from "./Icon.svelte";
  import type { ConnectionType, ForwardProfile } from "../types";

  interface Props {
    initialProfile: ForwardProfile;
    hostAliases: string[];
    onSave: (profile: ForwardProfile) => void;
    onStart: (profile: ForwardProfile) => void;
  }

  let { initialProfile, hostAliases, onSave, onStart }: Props = $props();
  const initial = structuredClone(untrack(() => initialProfile));
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

  const buildProfile = (): ForwardProfile => ({
    ...initial,
    name: name.trim() || "未命名转发",
    connectionType,
    sshHost: sshHost.trim(),
    sshPort: Number(sshPort) || 22,
    sshUser: sshUser.trim(),
    identityFile: identityFile.trim(),
    localBind,
    localPort: Number(localPort) || 8080,
    remoteHost: remoteHost.trim(),
    remotePort: Number(remotePort) || 80,
  });
</script>

<section class="editor-card">
  <div class="section-heading">
    <div>
      <span class="section-kicker">连接配置</span>
      <h2>新建转发</h2>
    </div>
    <span class="section-index">01</span>
  </div>

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
      <div class="field-with-action">
        <select id="config-host" bind:value={sshHost}>
          {#each hostAliases as alias}
            <option value={alias}>{alias}{alias === "production" ? " · 示例" : ""}</option>
          {/each}
        </select>
        <button class="small-button" type="button" title="刷新 SSH Config" aria-label="刷新 SSH Config"><Icon name="refresh" size={16} /></button>
      </div>
      <p class="field-help">列表来自用户 SSH 配置文件，可直接选择别名。</p>
    </div>
  {:else}
    <div class="field-grid field-grid--host">
      <div class="field-block">
        <label for="custom-host">主机 / IP</label>
        <input id="custom-host" bind:value={sshHost} placeholder="例如 192.0.2.10" />
      </div>
      <div class="field-block">
        <label for="ssh-port">SSH 端口</label>
        <input id="ssh-port" bind:value={sshPort} inputmode="numeric" />
      </div>
    </div>
    <div class="field-grid field-grid--host">
      <div class="field-block">
        <label for="ssh-user">用户名</label>
        <input id="ssh-user" bind:value={sshUser} placeholder="可选" />
      </div>
      <div class="field-block">
        <label for="identity-file">私钥路径</label>
        <input id="identity-file" bind:value={identityFile} placeholder="可选" />
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
        <input id="local-port" bind:value={localPort} inputmode="numeric" />
        <button class="small-button small-button--text" type="button" onclick={() => (localPort = "${Math.floor(10000 + Math.random() * 2000)}")}>自动</button>
      </div>
    </div>
  </div>

  <div class="field-grid">
    <div class="field-block">
      <label for="remote-host">目标主机</label>
      <input id="remote-host" bind:value={remoteHost} placeholder="127.0.0.1" />
    </div>
    <div class="field-block">
      <label for="remote-port">目标端口</label>
      <input id="remote-port" bind:value={remotePort} inputmode="numeric" />
    </div>
  </div>

  <p class="form-note"><Icon name="link" size={15} /> 目标地址由 SSH 服务器解析，适合访问服务器内网服务。</p>

  <div class="editor-actions">
    <button class="button button--primary" type="button" onclick={() => onStart(buildProfile())}><Icon name="play" size={16} /> 启动转发</button>
    <button class="button button--secondary" type="button" onclick={() => onSave(buildProfile())}><Icon name="book" size={16} /> 保存收藏</button>
  </div>
</section>
