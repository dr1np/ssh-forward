<script lang="ts">
  import { dialogFocus } from "../dialog";
  import Icon from "./Icon.svelte";

  interface Props {
    title: string;
    message: string;
    confirmLabel?: string;
    danger?: boolean;
    onCancel: () => void;
    onConfirm: () => void | Promise<void>;
  }

  let { title, message, confirmLabel = "确认", danger = false, onCancel, onConfirm }: Props = $props();
</script>

<div class="modal-backdrop" role="presentation" onclick={(event) => event.target === event.currentTarget && onCancel()}>
  <div class="dialog-card dialog-card--compact" use:dialogFocus={onCancel} role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title" tabindex="-1">
    <div class="dialog-icon" class:dialog-icon--danger={danger}><Icon name={danger ? "trash" : "sliders"} size={19} /></div>
    <div class="dialog-heading">
      <span class="section-kicker">请确认</span>
      <h2 id="confirm-dialog-title">{title}</h2>
    </div>
    <p class="dialog-message">{message}</p>
    <div class="dialog-actions">
      <button class="button button--quiet" type="button" onclick={onCancel}>取消</button>
      <button class={`button ${danger ? "button--danger" : "button--primary"}`} type="button" onclick={onConfirm}>{confirmLabel}</button>
    </div>
  </div>
</div>
