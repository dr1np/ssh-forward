<script lang="ts">
  export type IconName =
    | "book"
    | "check"
    | "chevron"
    | "clipboard"
    | "edit"
    | "file"
    | "link"
    | "moon"
    | "play"
    | "plus"
    | "refresh"
    | "server"
    | "sliders"
    | "stop"
    | "sun"
    | "trash"
    | "tune";

  let { name, size = 18, strokeWidth = 1.8 }: { name: IconName; size?: number; strokeWidth?: number } = $props();
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width={strokeWidth}
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#if name === "book"}
    <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5z" />
    <path d="M4 5.5v16M8 7h8M8 11h7" />
  {:else if name === "check"}
    <path d="m5 12 4 4L19 6" />
  {:else if name === "chevron"}
    <path d="m8 10 4 4 4-4" />
  {:else if name === "clipboard"}
    <rect x="6" y="5" width="12" height="15" rx="2" />
    <path d="M9 5V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1M9 10h6M9 14h4" />
  {:else if name === "edit"}
    <path d="m4 16.5-.8 3.3 3.3-.8L18.8 6.7a2.1 2.1 0 0 0-3-3z" />
    <path d="m14.5 5.5 3 3" />
  {:else if name === "file"}
    <path d="M6 3h8l4 4v14H6z" />
    <path d="M14 3v5h4M9 12h6M9 16h6" />
  {:else if name === "link"}
    <path d="M10 13.5a4 4 0 0 0 5.7.1l2.1-2.1a4 4 0 0 0-5.7-5.7L11 6.9" />
    <path d="M14 10.5a4 4 0 0 0-5.7-.1l-2.1 2.1a4 4 0 0 0 5.7 5.7l1.1-1.1" />
  {:else if name === "moon"}
    <path d="M20.5 15.3A8.5 8.5 0 0 1 8.7 3.5 8.5 8.5 0 1 0 20.5 15.3z" />
  {:else if name === "play"}
    <path d="m8 5 11 7-11 7z" />
  {:else if name === "plus"}
    <path d="M12 5v14M5 12h14" />
  {:else if name === "refresh"}
    <path d="M20 11a8 8 0 0 0-14.8-3L3 11" />
    <path d="M3 5v6h6M4 13a8 8 0 0 0 14.8 3L21 13" />
    <path d="M21 19v-6h-6" />
  {:else if name === "server"}
    <rect x="4" y="4" width="16" height="6" rx="2" />
    <rect x="4" y="14" width="16" height="6" rx="2" />
    <path d="M8 7h.01M8 17h.01M12 7h5M12 17h5" />
  {:else if name === "sliders"}
    <path d="M4 6h16M4 12h16M4 18h16" />
    <path d="M8 4v4M16 10v4M10 16v4" />
  {:else if name === "stop"}
    <rect x="6" y="6" width="12" height="12" rx="2" />
  {:else if name === "sun"}
    <circle cx="12" cy="12" r="3.5" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  {:else if name === "trash"}
    <path d="M4 7h16M10 11v5M14 11v5M6 7l1 13h10l1-13M9 7V4h6v3" />
  {:else if name === "tune"}
    <path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h10M18 18h2" />
    <circle cx="16" cy="6" r="2" fill="currentColor" stroke="none" />
    <circle cx="8" cy="12" r="2" fill="currentColor" stroke="none" />
    <circle cx="16" cy="18" r="2" fill="currentColor" stroke="none" />
  {/if}
</svg>
