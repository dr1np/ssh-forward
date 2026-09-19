/** Keep keyboard navigation inside a modal and restore the opening control. */
export function dialogFocus(node: HTMLElement, onCancel: () => void) {
  const previous = document.activeElement as HTMLElement | null;
  const controls = () => Array.from(node.querySelectorAll<HTMLElement>(
    'button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]',
  ));
  const frame = requestAnimationFrame(() => (controls()[0] ?? node).focus());
  const keydown = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      onCancel();
    } else if (event.key === "Tab") {
      const items = controls();
      const first = items[0] ?? node;
      const last = items.at(-1) ?? node;
      if (event.shiftKey && (document.activeElement === first || !node.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !node.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    }
  };
  document.addEventListener("keydown", keydown, true);
  return { destroy() {
    cancelAnimationFrame(frame);
    document.removeEventListener("keydown", keydown, true);
    if (previous?.isConnected) previous.focus();
  } };
}
