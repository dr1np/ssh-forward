<script lang="ts">
  import { untrack } from "svelte";
  import Icon from "./Icon.svelte";

  interface Props {
    currentPort: number;
    onCancel: () => void;
    onConfirm: (port: number) => void | Promise<void>;
  }

  let { currentPort, onCancel, onConfirm }: Props = $props();
  let value = $state(untrack(() => String(currentPort)));
  let error = $state("");

  const submit = () => {
    const port = Number(value.trim());
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      error = "请输入 1 到 65535 之间的整数。";
      return;
    }
    onConfirm(port);
  };
</script>

<div class="modal-backdrop" role="presentation" onclick={(event) => event.target === event.currentTarget && onCancel()}>
  <div class="dialog-card" role="dialog" aria-modal="true" aria-labelledby="port-dialog-title" tabindex="-1">
    <div class="dialog-heading dialog-heading--with-icon">
      <div class="dialog-icon"><Icon name="tune" size={19} /></div>
      <div>
        <span class="section-kicker">连接设置</span>
        <h2 id="port-dialog-title">更改本地端口</h2>
      </div>
    </div>
    <p class="dialog-message">更换端口会先停止当前通道，再用新端口重新建立连接。</p>
    <label class="dialog-field" for="next-local-port">
      <span>新的本地端口</span>
      <input id="next-local-port" bind:value={value} inputmode="numeric" aria-invalid={Boolean(error)} onkeydown={(event) => event.key === "Enter" && submit()} />
    </label>
    {#if error}<p class="dialog-error">{error}</p>{/if}
    <div class="dialog-actions">
      <button class="button button--quiet" type="button" onclick={onCancel}>取消</button>
      <button class="button button--primary" type="button" onclick={submit}>应用端口</button>
    </div>
  </div>
</div>
