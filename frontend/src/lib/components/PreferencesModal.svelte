<script lang="ts">
  import { untrack } from "svelte";
  import Icon from "./Icon.svelte";
  import type { AppPreferences, DefaultLocalBind } from "../preferences";

  interface Props {
    initial: AppPreferences;
    onCancel: () => void;
    onSave: (preferences: AppPreferences) => void;
  }

  let { initial, onCancel, onSave }: Props = $props();
  let confirmOnExit = $state(untrack(() => initial.confirmOnExit));
  let defaultLocalBind = $state<DefaultLocalBind>(untrack(() => initial.defaultLocalBind));
  let autoSelectPort = $state(untrack(() => initial.autoSelectPort));

  const save = () => onSave({ confirmOnExit, defaultLocalBind, autoSelectPort });
</script>

<div class="modal-backdrop" role="presentation" onclick={(event) => event.target === event.currentTarget && onCancel()}>
  <div class="dialog-card preferences-dialog" role="dialog" aria-modal="true" aria-labelledby="preferences-title" tabindex="-1">
    <div class="dialog-heading dialog-heading--with-icon">
      <div class="dialog-icon"><Icon name="sliders" size={19} /></div>
      <div>
        <span class="section-kicker">本机设置</span>
        <h2 id="preferences-title">偏好设置</h2>
      </div>
    </div>
    <p class="dialog-message">这些选项只影响本机使用体验，不会修改 SSH 配置文件。</p>

    <div class="preference-list">
      <label class="preference-row">
        <span><strong>退出前确认</strong><small>有转发运行时，关闭窗口前先询问。</small></span>
        <input class="toggle-input" type="checkbox" bind:checked={confirmOnExit} />
      </label>
      <label class="preference-row preference-row--field" for="default-bind">
        <span><strong>默认监听地址</strong><small>新建转发时使用的本地地址。</small></span>
        <select id="default-bind" bind:value={defaultLocalBind}>
          <option value="127.0.0.1">127.0.0.1 · 仅本机</option>
          <option value="::1">::1 · IPv6 本机</option>
          <option value="0.0.0.0">0.0.0.0 · 局域网</option>
        </select>
      </label>
      <label class="preference-row">
        <span><strong>新建时自动选端口</strong><small>重置表单时自动寻找空闲本地端口。</small></span>
        <input class="toggle-input" type="checkbox" bind:checked={autoSelectPort} />
      </label>
    </div>

    <div class="dialog-actions">
      <button class="button button--quiet" type="button" onclick={onCancel}>取消</button>
      <button class="button button--primary" type="button" onclick={save}>保存设置</button>
    </div>
  </div>
</div>
