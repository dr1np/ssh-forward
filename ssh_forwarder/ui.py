from __future__ import annotations

import ctypes
import os
import queue
import re
import threading
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from uuid import uuid4

from .models import ForwardProfile
from .rounded_widgets import RoundedButton, apply_rounded_treeview_style
from .ssh_config import discover_ssh_hosts
from .storage import ProfileStore
from .tunnel_manager import TunnelManager, find_available_port


COLORS = {
    "navy": "#3E3A33",
    "blue": "#C66B3D",
    "blue_hover": "#B25A2E",
    "green": "#606C38",
    "red": "#A84B3B",
    "amber": "#B08E3A",
    "ink": "#3E3A33",
    "muted": "#756B58",
    "line": "#E2D8C4",
    "surface": "#EFE7D5",
    "tab_hover": "#F5EEDF",
    "sand": "#E8DCC7",
    "oat": "#F6F0E3",
    "white": "#FFFFFF",
}


class AutoHideScrollbar(ttk.Scrollbar):
    """Hide the track when its target fits, keeping the table uncluttered."""

    def set(self, first: str, last: str) -> None:
        first_value = float(first)
        last_value = float(last)
        if first_value <= 0.0 and last_value >= 1.0:
            self.grid_remove()
        else:
            self.grid()
        super().set(first, last)


def enable_windows_dpi_awareness() -> None:
    """Prevent Windows from bitmap-scaling Tk, which makes text look blurry."""

    if os.name != "nt":
        return
    try:
        per_monitor_v2 = ctypes.c_void_p(-4 & ((1 << (ctypes.sizeof(ctypes.c_void_p) * 8)) - 1))
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(per_monitor_v2):
            return
    except (AttributeError, OSError):
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def configure_tk_scaling(root: tk.Tk) -> None:
    """Match Tk point sizes to the monitor's real DPI after DPI awareness is set."""

    if os.name != "nt":
        return
    try:
        root.update_idletasks()
        dpi = ctypes.windll.user32.GetDpiForWindow(root.winfo_id())
        if dpi:
            root.tk.call("tk", "scaling", round(dpi / 72.0, 3))
    except (AttributeError, OSError, tk.TclError):
        pass


class SSHForwarderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SSH 端口转发助手")
        try:
            tk_scale = float(self.root.tk.call("tk", "scaling"))
            self.ui_scale = max(1.0, min(3.0, tk_scale / (96 / 72)))
        except (tk.TclError, TypeError, ValueError):
            self.ui_scale = 1.0
        self.root.minsize(round(1000 * self.ui_scale), round(650 * self.ui_scale))
        self.root.geometry(f"{round(1120 * self.ui_scale)}x{round(720 * self.ui_scale)}")

        self.manager = TunnelManager()
        self.store = ProfileStore()
        self.host_aliases: list[str] = []
        self.editing_favorite_id: str | None = None
        self._startup_error = ""
        self._async_results: queue.Queue[tuple[str, str, object]] = queue.Queue()

        try:
            self.store.load()
        except ValueError as exc:
            self._startup_error = str(exc)

        self._create_variables()
        self._configure_fonts()
        self._configure_styles()
        self._build_ui()
        self._restore_window()
        self.refresh_ssh_hosts(first_load=True)
        self.refresh_favorites()
        self._update_connection_fields()
        self._update_header_status()

        if self._startup_error:
            self.log(self._startup_error, "错误")
        if not self.manager.ssh_executable:
            self.log("未检测到 OpenSSH 客户端；安装后重新启动本工具即可。", "错误")
        else:
            self.log(f"OpenSSH 已就绪：{self.manager.ssh_executable}")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(250, self._poll_events)

    def _configure_fonts(self) -> None:
        available = {name.casefold(): name for name in tkfont.families(self.root)}
        preferred = (
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "Segoe UI Variable Text",
            "Segoe UI",
        )
        self.font_family = next(
            (available[name.casefold()] for name in preferred if name.casefold() in available),
            "TkDefaultFont",
        )
        self.mono_family = next(
            (
                available[name.casefold()]
                for name in ("Cascadia Mono", "Consolas", "Courier New")
                if name.casefold() in available
            ),
            self.font_family,
        )
        self.font_regular = (self.font_family, 10)
        self.font_small = (self.font_family, 9)
        self.font_semibold = (self.font_family, 10, "bold")
        self.font_heading = (self.font_family, 14, "bold")
        self.font_title = (self.font_family, 19, "bold")

        for named_font in (
            "TkDefaultFont",
            "TkTextFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            try:
                tkfont.nametofont(named_font).configure(family=self.font_family, size=10)
            except tk.TclError:
                continue
        try:
            tkfont.nametofont("TkFixedFont").configure(family=self.mono_family, size=10)
        except tk.TclError:
            pass

    def _create_variables(self) -> None:
        self.connection_type = tk.StringVar(value="config")
        self.config_host = tk.StringVar()
        self.custom_host = tk.StringVar()
        self.ssh_port = tk.StringVar(value="22")
        self.ssh_user = tk.StringVar()
        self.identity_file = tk.StringVar()
        self.profile_name = tk.StringVar()
        self.local_bind = tk.StringVar(value="127.0.0.1")
        self.local_port = tk.StringVar(value="8080")
        self.remote_host = tk.StringVar(value="127.0.0.1")
        self.remote_port = tk.StringVar(value="80")
        self.editor_title = tk.StringVar(value="新建转发")
        self.header_status = tk.StringVar(value="正在检查 OpenSSH…")
        self.footer_status = tk.StringVar(value="0 个转发正在运行")

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.root.configure(background=COLORS["surface"])
        style.configure("App.TFrame", background=COLORS["surface"])
        self.root.option_add("*TCombobox*Listbox.font", self.font_regular)
        self.root.option_add("*TCombobox*Listbox.background", "#FBF7EE")
        self.root.option_add("*TCombobox*Listbox.foreground", COLORS["ink"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#E4D7BE")
        self.root.option_add("*TCombobox*Listbox.selectForeground", COLORS["ink"])
        style.configure(
            "Organic.TEntry",
            padding=(8, 7),
            fieldbackground="#FFFFFF",
            foreground=COLORS["ink"],
            bordercolor="#D9CDB8",
            lightcolor="#D9CDB8",
            darkcolor="#D9CDB8",
            borderwidth=1,
            relief="flat",
            font=self.font_regular,
        )
        style.map(
            "Organic.TEntry",
            bordercolor=[("focus", COLORS["blue"])],
            lightcolor=[("focus", COLORS["blue"])],
            darkcolor=[("focus", COLORS["blue"])],
        )
        style.configure(
            "Organic.TCombobox",
            padding=(8, 6),
            fieldbackground="#FFFFFF",
            foreground=COLORS["ink"],
            bordercolor="#D9CDB8",
            lightcolor="#D9CDB8",
            darkcolor="#D9CDB8",
            borderwidth=1,
            arrowsize=14,
            font=self.font_regular,
        )
        style.map(
            "Organic.TCombobox",
            bordercolor=[("focus", COLORS["blue"])],
            lightcolor=[("focus", COLORS["blue"])],
            darkcolor=[("focus", COLORS["blue"])],
        )
        style.configure(
            "Organic.Vertical.TScrollbar",
            width=8,
            troughcolor="#F4ECDD",
            background="#D4C5A9",
            bordercolor="#F4ECDD",
            lightcolor="#F4ECDD",
            darkcolor="#F4ECDD",
            arrowcolor="#8A7D66",
        )
        apply_rounded_treeview_style(style)

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, background=COLORS["navy"], padx=22, pady=14)
        header.pack(fill="x")
        self.header_frame = header
        title_box = tk.Frame(header, background=COLORS["navy"])
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_box,
            text="SSH 端口转发助手",
            background=COLORS["navy"],
            foreground=COLORS["white"],
            font=self.font_title,
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="集中管理本地转发 · 复用 SSH Config · 一键启停常用通道",
            background=COLORS["navy"],
            foreground="#CBBFA8",
            font=self.font_small,
        ).pack(anchor="w", pady=(2, 0))
        tk.Label(
            header,
            textvariable=self.header_status,
            background="#4A463C",
            foreground="#EDE4CF",
            font=self.font_small,
            padx=12,
            pady=7,
        ).pack(side="right")

        body = tk.Frame(self.root, background=COLORS["surface"], padx=16, pady=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=375)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.editor = tk.Frame(body, background=COLORS["white"], padx=18, pady=16)
        self.editor.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.editor.columnconfigure(0, weight=1)
        self._build_editor(self.editor)

        workspace = tk.Frame(body, background=COLORS["oat"], padx=10, pady=10)
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)
        self.workspace_container = workspace
        self._build_workspace(workspace)

        footer = tk.Frame(self.root, background=COLORS["surface"], padx=18, pady=2)
        footer.pack(fill="x")
        tk.Label(
            footer,
            textvariable=self.footer_status,
            background=COLORS["surface"],
            foreground="#756B58",
            font=self.font_small,
        ).pack(side="left")
        tk.Label(
            footer,
            text="关闭窗口时会安全停止所有转发",
            background=COLORS["surface"],
            foreground="#756B58",
            font=self.font_small,
        ).pack(side="right")

    def _build_editor(self, parent: tk.Frame) -> None:
        heading = tk.Frame(parent, background=COLORS["white"])
        heading.grid(row=0, column=0, sticky="ew")
        tk.Label(
            heading,
            textvariable=self.editor_title,
            background=COLORS["white"],
            foreground=COLORS["ink"],
            font=self.font_heading,
        ).pack(side="left")
        self._rounded_button(
            heading,
            "清空",
            self.reset_form,
            "secondary",
            height=32,
        ).pack(side="right")

        tk.Label(
            parent,
            text="SSH 连接",
            background=COLORS["white"],
            foreground="#756B58",
            font=self.font_semibold,
        ).grid(row=1, column=0, sticky="w", pady=(16, 6))
        connection_choice = tk.Frame(parent, background=COLORS["white"])
        connection_choice.grid(row=2, column=0, sticky="ew")
        tk.Radiobutton(
            connection_choice,
            text="SSH Config",
            variable=self.connection_type,
            value="config",
            command=self._update_connection_fields,
            background=COLORS["white"],
            activebackground=COLORS["white"],
            selectcolor="#F2E5D0",
            foreground=COLORS["ink"],
            activeforeground=COLORS["blue"],
            font=self.font_regular,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        ).pack(side="left")
        tk.Radiobutton(
            connection_choice,
            text="自定义主机",
            variable=self.connection_type,
            value="custom",
            command=self._update_connection_fields,
            background=COLORS["white"],
            activebackground=COLORS["white"],
            selectcolor="#F2E5D0",
            foreground=COLORS["ink"],
            activeforeground=COLORS["blue"],
            font=self.font_regular,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        ).pack(side="left", padx=(16, 0))

        self.config_frame = tk.Frame(parent, background=COLORS["white"])
        self.config_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.config_frame.columnconfigure(0, weight=1)
        self.config_host_combo = ttk.Combobox(
            self.config_frame,
            textvariable=self.config_host,
            style="Organic.TCombobox",
        )
        self.config_host_combo.grid(row=0, column=0, sticky="ew")
        self._rounded_button(
            self.config_frame,
            "刷新",
            self.refresh_ssh_hosts,
            "secondary",
            height=38,
        ).grid(row=0, column=1, padx=(7, 0))
        tk.Label(
            self.config_frame,
            text="可直接输入别名；列表来自 ~/.ssh/config",
            background=COLORS["white"],
            foreground="#8A7D66",
            font=self.font_small,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.custom_frame = tk.Frame(parent, background=COLORS["white"])
        self.custom_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.custom_frame.columnconfigure(0, weight=3)
        self.custom_frame.columnconfigure(1, weight=1)
        self._labeled_entry(self.custom_frame, "主机 / IP", self.custom_host, 0, 0)
        self._labeled_entry(self.custom_frame, "SSH 端口", self.ssh_port, 0, 1, padx=(8, 0))
        self._labeled_entry(self.custom_frame, "用户名（可选）", self.ssh_user, 2, 0)
        key_box = tk.Frame(self.custom_frame, background=COLORS["white"])
        key_box.grid(row=2, column=1, rowspan=2, sticky="nsew", padx=(8, 0), pady=(8, 0))
        key_box.columnconfigure(0, weight=1)
        tk.Label(
            key_box,
            text="私钥（可选）",
            background=COLORS["white"],
            foreground=COLORS["ink"],
            font=self.font_regular,
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(key_box, textvariable=self.identity_file, style="Organic.TEntry").grid(row=1, column=0, sticky="ew")
        self._rounded_button(
            key_box,
            "…",
            self.choose_identity_file,
            "secondary",
            height=38,
            width=38,
        ).grid(row=1, column=1, padx=(4, 0))

        tk.Frame(parent, background="#E5DBC7", height=1).grid(row=4, column=0, sticky="ew", pady=(15, 10))
        tk.Label(
            parent,
            text="转发规则",
            background=COLORS["white"],
            foreground="#756B58",
            font=self.font_semibold,
        ).grid(row=5, column=0, sticky="w", pady=(0, 6))

        form = tk.Frame(parent, background=COLORS["white"])
        form.grid(row=6, column=0, sticky="ew")
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        self._labeled_entry(form, "配置名称", self.profile_name, 0, 0, columnspan=2)

        bind_box = tk.Frame(form, background=COLORS["white"])
        bind_box.grid(row=2, column=0, sticky="ew", pady=(9, 0), padx=(0, 5))
        bind_box.columnconfigure(0, weight=1)
        tk.Label(
            bind_box,
            text="监听地址",
            background=COLORS["white"],
            foreground=COLORS["ink"],
            font=self.font_regular,
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Combobox(
            bind_box,
            textvariable=self.local_bind,
            values=("127.0.0.1", "0.0.0.0", "::1"),
            style="Organic.TCombobox",
        ).grid(row=1, column=0, sticky="ew")

        local_port_box = tk.Frame(form, background=COLORS["white"])
        local_port_box.grid(row=2, column=1, sticky="ew", pady=(9, 0), padx=(5, 0))
        local_port_box.columnconfigure(0, weight=1)
        tk.Label(
            local_port_box,
            text="本地端口",
            background=COLORS["white"],
            foreground=COLORS["ink"],
            font=self.font_regular,
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(local_port_box, textvariable=self.local_port, style="Organic.TEntry").grid(row=1, column=0, sticky="ew")
        self._rounded_button(
            local_port_box,
            "自动",
            self.choose_free_port,
            "secondary",
            height=38,
        ).grid(row=1, column=1, padx=(5, 0))

        self._labeled_entry(form, "目标主机", self.remote_host, 4, 0, padx=(0, 5))
        self._labeled_entry(form, "目标端口", self.remote_port, 4, 1, padx=(5, 0))
        tk.Label(
            form,
            text="目标主机和目标端口是 SSH 远程服务端的目标地址。\n例如 127.0.0.1:5432 表示访问远程服务端的 PostgreSQL。",
            background=COLORS["white"],
            foreground="#8A7D66",
            font=self.font_small,
            anchor="w",
            justify="left",
        ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        actions = tk.Frame(parent, background=COLORS["white"])
        actions.grid(row=7, column=0, sticky="sew", pady=(18, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self._rounded_button(
            actions,
            "启动转发",
            self.start_from_form,
            "primary",
            height=42,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self._rounded_button(
            actions,
            "保存收藏",
            self.save_favorite_from_form,
            "secondary",
            height=42,
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self._rounded_button(
            actions,
            "启动并收藏",
            self.start_and_save,
            "secondary",
            height=42,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _rounded_button(
        self,
        parent: tk.Misc,
        text: str,
        command,
        kind: str,
        *,
        height: int = 40,
        width: int | None = None,
    ) -> RoundedButton:
        palette = {
            "primary": (COLORS["blue"], COLORS["blue_hover"], "#FFF9EE"),
            "secondary": ("#EFE4CE", "#E4D5B8", "#5A4F3B"),
            "danger": ("#F1DDD2", "#EACBC0", COLORS["red"]),
        }
        background, hover, foreground = palette[kind]
        return RoundedButton(
            parent,
            text=text,
            command=command,
            background=background,
            hover_background=hover,
            foreground=foreground,
            font=self.font_semibold if kind == "primary" else self.font_regular,
            height=height,
            width=width,
        )

    def _labeled_entry(
        self,
        parent: tk.Misc,
        label: str,
        variable: tk.StringVar,
        row: int,
        column: int,
        *,
        columnspan: int = 1,
        padx: tuple[int, int] = (0, 0),
    ) -> None:
        box = tk.Frame(parent, background=COLORS["white"])
        box.grid(row=row, column=column, columnspan=columnspan, sticky="ew", padx=padx, pady=(0 if row == 0 else 9, 0))
        box.columnconfigure(0, weight=1)
        tk.Label(
            box,
            text=label,
            background=COLORS["white"],
            foreground=COLORS["ink"],
            font=self.font_regular,
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(box, textvariable=variable, style="Organic.TEntry").grid(row=1, column=0, sticky="ew")

    def _build_workspace(self, parent: tk.Frame) -> None:
        parent.rowconfigure(1, weight=1)
        tab_bar = tk.Frame(parent, background=COLORS["oat"], height=54)
        tab_bar.grid(row=0, column=0, sticky="ew", padx=(3, 3))
        tab_bar.grid_propagate(False)
        tk.Frame(tab_bar, background="#E5DBC7", height=1).pack(side="bottom", fill="x")

        content = tk.Frame(parent, background=COLORS["white"])
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        active_tab = tk.Frame(content, background=COLORS["white"], padx=8, pady=14)
        favorite_tab = tk.Frame(content, background=COLORS["white"], padx=8, pady=14)
        log_tab = tk.Frame(content, background=COLORS["white"], padx=8, pady=14)
        for tab in (active_tab, favorite_tab, log_tab):
            tab.grid(row=0, column=0, sticky="nsew")

        self.workspace_tabs: dict[str, tuple[tk.Frame, tk.Label, tk.Frame, tk.Frame]] = {}
        for key, title, tab in (
            ("active", "运行中的转发", active_tab),
            ("favorites", "收藏", favorite_tab),
            ("log", "日志", log_tab),
        ):
            item = tk.Frame(tab_bar, background=COLORS["oat"], cursor="hand2")
            item.pack(side="left", fill="y")
            label = tk.Label(
                item,
                text=title,
                background=COLORS["oat"],
                foreground=COLORS["muted"],
                font=self.font_regular,
                padx=18,
                pady=10,
                cursor="hand2",
            )
            label.pack(fill="both", expand=True)
            indicator = tk.Frame(item, background=COLORS["oat"], height=3)
            indicator.pack(side="bottom", fill="x")
            for widget in (item, label, indicator):
                widget.bind("<Button-1>", lambda _event, tab_key=key: self._select_workspace_tab(tab_key))
                widget.bind("<Enter>", lambda _event, tab_key=key: self._set_tab_hover(tab_key, True))
                widget.bind("<Leave>", lambda _event, tab_key=key: self._set_tab_hover(tab_key, False))
            self.workspace_tabs[key] = (item, label, indicator, tab)

        self.active_workspace_tab = "active"
        self._select_workspace_tab("active")

        self._build_active_tab(active_tab)
        self._build_favorite_tab(favorite_tab)
        self._build_log_tab(log_tab)

    def _select_workspace_tab(self, selected_key: str) -> None:
        if selected_key not in self.workspace_tabs:
            return
        self.active_workspace_tab = selected_key
        for key, (item, label, indicator, tab) in self.workspace_tabs.items():
            selected = key == selected_key
            background = COLORS["oat"]
            item.configure(background=background)
            label.configure(
                background=background,
                foreground=COLORS["blue"] if selected else COLORS["muted"],
                font=self.font_semibold if selected else self.font_regular,
            )
            indicator.configure(background=COLORS["blue"] if selected else COLORS["oat"])
            if selected:
                tab.tkraise()

    def _set_tab_hover(self, tab_key: str, hovering: bool) -> None:
        if tab_key == self.active_workspace_tab or tab_key not in self.workspace_tabs:
            return
        item, label, _indicator, _tab = self.workspace_tabs[tab_key]
        background = COLORS["tab_hover"] if hovering else COLORS["oat"]
        item.configure(background=background)
        label.configure(
            background=background,
            foreground=COLORS["ink"] if hovering else COLORS["muted"],
        )

    def _make_tree(self, parent: tk.Frame, columns: tuple[str, ...]) -> ttk.Treeview:
        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            selectmode="browse",
            style="Rounded.Treeview",
        )
        scrollbar = AutoHideScrollbar(
            parent,
            orient="vertical",
            command=tree.yview,
            style="Organic.Vertical.TScrollbar",
        )
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=1, column=0, sticky="nsew", padx=(0, 4))
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 1))
        return tree

    def _build_active_tab(self, tab: tk.Frame) -> None:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        tk.Label(
            tab,
            text="选择一条转发后，可立即更改端口或停止。连接异常会保留在列表中便于查看。",
            background=COLORS["white"],
            foreground="#8A7D66",
            font=self.font_small,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        columns = ("status", "name", "local", "target", "via", "time")
        self.active_tree = self._make_tree(tab, columns)
        headings = {
            "status": ("状态", 76),
            "name": ("名称", 105),
            "local": ("本地", 118),
            "target": ("目标", 125),
            "via": ("经由 SSH", 105),
            "time": ("已运行", 84),
        }
        for key, (title, width) in headings.items():
            self.active_tree.heading(key, text=title)
            is_time = key == "time"
            self.active_tree.column(
                key,
                width=width,
                minwidth=84 if is_time else 55,
                anchor="center" if is_time else "w",
                stretch=is_time or key in {"name", "target", "via"},
            )
        self.active_tree.tag_configure("running", foreground="#606C38")
        self.active_tree.tag_configure("failed", foreground="#A84B3B")
        self.active_tree.tag_configure("pending", foreground="#B08E3A")
        self.active_tree.bind("<Double-1>", lambda _event: self.copy_selected_endpoint())

        buttons = tk.Frame(tab, background=COLORS["white"])
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._rounded_button(buttons, "复制本地地址", self.copy_selected_endpoint, "secondary", height=36).pack(side="left")
        self._rounded_button(buttons, "更改本地端口", self.change_selected_port, "secondary", height=36).pack(side="left", padx=(7, 0))
        self._rounded_button(buttons, "停止", self.stop_selected, "danger", height=36).pack(side="right")
        self._rounded_button(buttons, "清理已结束", self.clear_finished, "secondary", height=36).pack(side="right", padx=(0, 7))

    def _build_favorite_tab(self, tab: tk.Frame) -> None:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        tk.Label(
            tab,
            text="双击收藏即可启动；“编辑”会把配置载入左侧。",
            background=COLORS["white"],
            foreground="#8A7D66",
            font=self.font_small,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        columns = ("name", "local", "target", "via")
        self.favorite_tree = self._make_tree(tab, columns)
        headings = {
            "name": ("名称", 130),
            "local": ("本地", 125),
            "target": ("目标", 145),
            "via": ("经由 SSH", 125),
        }
        for key, (title, width) in headings.items():
            self.favorite_tree.heading(key, text=title)
            self.favorite_tree.column(key, width=width, minwidth=70, anchor="w", stretch=True)
        self.favorite_tree.bind("<Double-1>", lambda _event: self.start_selected_favorite())

        buttons = tk.Frame(tab, background=COLORS["white"])
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._rounded_button(buttons, "启动", self.start_selected_favorite, "primary", height=36).pack(side="left")
        self._rounded_button(buttons, "编辑", self.edit_selected_favorite, "secondary", height=36).pack(side="left", padx=(7, 0))
        self._rounded_button(buttons, "删除", self.delete_selected_favorite, "danger", height=36).pack(side="right")

    def _build_log_tab(self, tab: tk.Frame) -> None:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        self.log_text = tk.Text(
            tab,
            wrap="word",
            relief="flat",
            background="#FBF7EE",
            foreground="#4B453A",
            insertbackground="white",
            font=(self.mono_family, 10),
            padx=14,
            pady=12,
            state="disabled",
        )
        scrollbar = AutoHideScrollbar(
            tab,
            orient="vertical",
            command=self.log_text.yview,
            style="Organic.Vertical.TScrollbar",
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.tag_configure("错误", foreground="#A84B3B")
        self.log_text.tag_configure("成功", foreground="#606C38")
        self.log_text.tag_configure("普通", foreground="#4B453A")
        self._rounded_button(tab, "清空日志", self.clear_log, "secondary", height=36).grid(row=1, column=0, sticky="e", pady=(8, 0))

    def _update_connection_fields(self) -> None:
        if self.connection_type.get() == "config":
            self.custom_frame.grid_remove()
            self.config_frame.grid()
        else:
            self.config_frame.grid_remove()
            self.custom_frame.grid()

    def _update_header_status(self) -> None:
        if self.manager.ssh_executable:
            self.header_status.set(f"● OpenSSH 就绪  ·  {len(self.host_aliases)} 个配置主机")
        else:
            self.header_status.set("● 未找到 OpenSSH 客户端")

    def refresh_ssh_hosts(self, first_load: bool = False) -> None:
        current = self.config_host.get()
        self.host_aliases = discover_ssh_hosts()
        self.config_host_combo.configure(values=self.host_aliases)
        if current:
            self.config_host.set(current)
        elif self.host_aliases:
            self.config_host.set(self.host_aliases[0])
        self._update_header_status()
        if not first_load:
            self.log(f"已刷新 SSH Config，发现 {len(self.host_aliases)} 个可用别名。")

    def choose_identity_file(self) -> None:
        initial = Path.home() / ".ssh"
        selected = filedialog.askopenfilename(
            title="选择 SSH 私钥",
            initialdir=str(initial if initial.exists() else Path.home()),
            filetypes=(("所有文件", "*.*"),),
        )
        if selected:
            self.identity_file.set(selected)

    def choose_free_port(self) -> None:
        try:
            port = find_available_port(self.local_bind.get())
            self.local_port.set(str(port))
            self.log(f"已选择可用本地端口 {port}。")
        except OSError as exc:
            messagebox.showerror("无法选择端口", str(exc), parent=self.root)

    @staticmethod
    def _as_port(value: str, label: str) -> int:
        try:
            port = int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{label}必须是数字。") from exc
        if not 1 <= port <= 65535:
            raise ValueError(f"{label}必须在 1 到 65535 之间。")
        return port

    def profile_from_form(self) -> ForwardProfile:
        remote_host = self.remote_host.get().strip()
        remote_port = self._as_port(self.remote_port.get(), "目标端口")
        name = self.profile_name.get().strip() or f"{remote_host}:{remote_port}"
        kind = self.connection_type.get()
        ssh_host = self.config_host.get().strip() if kind == "config" else self.custom_host.get().strip()
        profile = ForwardProfile(
            id=self.editing_favorite_id or uuid4().hex,
            name=name,
            connection_type=kind,
            ssh_host=ssh_host,
            ssh_port=self._as_port(self.ssh_port.get(), "SSH 端口"),
            ssh_user=self.ssh_user.get().strip(),
            identity_file=self.identity_file.get().strip(),
            local_bind=self.local_bind.get(),
            local_port=self._as_port(self.local_port.get(), "本地端口"),
            remote_host=remote_host,
            remote_port=remote_port,
        )
        profile.validate()
        return profile

    def _confirm_network_exposure(self, profile: ForwardProfile) -> bool:
        if profile.local_bind != "0.0.0.0":
            return True
        return messagebox.askyesno(
            "确认对局域网开放",
            "监听 0.0.0.0 会让同一网络中的其他设备也可能访问此端口。\n\n确定继续吗？",
            icon="warning",
            parent=self.root,
        )

    def start_from_form(self) -> None:
        try:
            profile = self.profile_from_form()
        except ValueError as exc:
            messagebox.showerror("配置不完整", str(exc), parent=self.root)
            return
        self.start_profile(profile)

    def start_profile(self, profile: ForwardProfile) -> bool:
        if not self._confirm_network_exposure(profile):
            return False
        try:
            active = self.manager.start(profile)
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("无法启动转发", str(exc), parent=self.root)
            self.log(str(exc), "错误")
            return False

        self.active_tree.insert(
            "",
            "end",
            iid=active.id,
            values=(
                active.status,
                active.profile.name,
                active.profile.local_endpoint,
                active.profile.target_endpoint,
                active.profile.ssh_destination,
                "00:00",
            ),
            tags=("pending",),
        )
        self.active_tree.selection_set(active.id)
        self._select_workspace_tab("active")
        self.log(
            f"正在启动“{profile.name}”：{profile.local_endpoint} → {profile.target_endpoint}，经由 {profile.ssh_destination}。"
        )
        self.root.after(900, lambda tunnel_id=active.id: self._confirm_started(tunnel_id))
        self._refresh_running_count()
        return True

    def _confirm_started(self, tunnel_id: str) -> None:
        if self.manager.mark_connected_if_running(tunnel_id):
            tunnel = self.manager.tunnels.get(tunnel_id)
            if tunnel:
                self.log(f"“{tunnel.profile.name}”已开始转发。", "成功")
            self._refresh_active_rows()

    def save_favorite_from_form(self, *, quiet: bool = False) -> bool:
        try:
            profile = self.profile_from_form()
            self.store.upsert(profile)
        except (ValueError, OSError) as exc:
            messagebox.showerror("无法保存收藏", str(exc), parent=self.root)
            self.log(f"收藏保存失败：{exc}", "错误")
            return False
        self.editing_favorite_id = profile.id
        self.editor_title.set(f"编辑收藏 · {profile.name}")
        self.refresh_favorites(select_id=profile.id)
        if not quiet:
            self.log(f"已保存收藏“{profile.name}”。", "成功")
        return True

    def start_and_save(self) -> None:
        try:
            profile = self.profile_from_form()
        except ValueError as exc:
            messagebox.showerror("配置不完整", str(exc), parent=self.root)
            return
        if not self.start_profile(profile):
            return
        try:
            self.store.upsert(profile)
            self.editing_favorite_id = profile.id
            self.editor_title.set(f"编辑收藏 · {profile.name}")
            self.refresh_favorites(select_id=profile.id)
            self.log(f"同时收藏了“{profile.name}”。", "成功")
        except (ValueError, OSError) as exc:
            self.log(f"转发已启动，但收藏保存失败：{exc}", "错误")
            messagebox.showwarning("收藏保存失败", f"转发已经启动，但未能保存收藏：\n{exc}", parent=self.root)

    def reset_form(self) -> None:
        self.editing_favorite_id = None
        self.editor_title.set("新建转发")
        self.profile_name.set("")
        self.local_bind.set("127.0.0.1")
        self.local_port.set("8080")
        self.remote_host.set("127.0.0.1")
        self.remote_port.set("80")
        self.ssh_port.set("22")
        self.ssh_user.set("")
        self.identity_file.set("")
        if self.host_aliases and not self.config_host.get():
            self.config_host.set(self.host_aliases[0])

    def refresh_favorites(self, select_id: str | None = None) -> None:
        for item in self.favorite_tree.get_children():
            self.favorite_tree.delete(item)
        for profile in self.store.favorites:
            self.favorite_tree.insert(
                "",
                "end",
                iid=profile.id,
                values=(
                    profile.name,
                    profile.local_endpoint,
                    profile.target_endpoint,
                    profile.ssh_destination,
                ),
            )
        if select_id and self.favorite_tree.exists(select_id):
            self.favorite_tree.selection_set(select_id)
            self.favorite_tree.see(select_id)

    def _selected_favorite(self) -> ForwardProfile | None:
        selected = self.favorite_tree.selection()
        if not selected:
            messagebox.showinfo("请选择收藏", "请先在收藏列表中选择一项。", parent=self.root)
            return None
        return self.store.get(selected[0])

    def start_selected_favorite(self) -> None:
        profile = self._selected_favorite()
        if profile:
            self.start_profile(profile)

    def edit_selected_favorite(self) -> None:
        profile = self._selected_favorite()
        if not profile:
            return
        self.editing_favorite_id = profile.id
        self.editor_title.set(f"编辑收藏 · {profile.name}")
        self.connection_type.set(profile.connection_type)
        self.config_host.set(profile.ssh_host if profile.connection_type == "config" else self.config_host.get())
        self.custom_host.set(profile.ssh_host if profile.connection_type == "custom" else "")
        self.ssh_port.set(str(profile.ssh_port))
        self.ssh_user.set(profile.ssh_user)
        self.identity_file.set(profile.identity_file)
        self.profile_name.set(profile.name)
        self.local_bind.set(profile.local_bind)
        self.local_port.set(str(profile.local_port))
        self.remote_host.set(profile.remote_host)
        self.remote_port.set(str(profile.remote_port))
        self._update_connection_fields()
        self.log(f"已将收藏“{profile.name}”载入编辑区。")

    def delete_selected_favorite(self) -> None:
        profile = self._selected_favorite()
        if not profile:
            return
        if not messagebox.askyesno("删除收藏", f"确定删除“{profile.name}”吗？", parent=self.root):
            return
        try:
            self.store.delete(profile.id)
        except OSError as exc:
            messagebox.showerror("删除失败", str(exc), parent=self.root)
            return
        if self.editing_favorite_id == profile.id:
            self.reset_form()
        self.refresh_favorites()
        self.log(f"已删除收藏“{profile.name}”。")

    def _selected_tunnel_id(self, *, require_running: bool = False) -> str | None:
        selected = self.active_tree.selection()
        if not selected:
            messagebox.showinfo("请选择转发", "请先在运行列表中选择一项。", parent=self.root)
            return None
        tunnel_id = selected[0]
        tunnel = self.manager.tunnels.get(tunnel_id)
        if not tunnel:
            return None
        if require_running and tunnel.process.poll() is not None:
            messagebox.showinfo("转发已结束", "这条转发已结束，请启动新的转发。", parent=self.root)
            return None
        return tunnel_id

    def stop_selected(self) -> None:
        tunnel_id = self._selected_tunnel_id(require_running=True)
        if not tunnel_id:
            return
        tunnel = self.manager.tunnels[tunnel_id]
        self.log(f"正在停止“{tunnel.profile.name}”…")
        threading.Thread(target=self._stop_worker, args=(tunnel_id,), daemon=True).start()

    def _stop_worker(self, tunnel_id: str) -> None:
        try:
            self.manager.stop(tunnel_id)
        except Exception as exc:  # defensive boundary around OS process control
            self._async_results.put(("error", tunnel_id, str(exc)))

    def clear_finished(self) -> None:
        removed = 0
        for tunnel_id in list(self.manager.tunnels):
            tunnel = self.manager.tunnels[tunnel_id]
            if tunnel.process.poll() is not None:
                self.manager.remove_finished(tunnel_id)
                if self.active_tree.exists(tunnel_id):
                    self.active_tree.delete(tunnel_id)
                removed += 1
        if removed:
            self.log(f"已清理 {removed} 条结束记录。")
        self._refresh_running_count()

    def copy_selected_endpoint(self) -> None:
        tunnel_id = self._selected_tunnel_id()
        if not tunnel_id:
            return
        endpoint = self.manager.tunnels[tunnel_id].profile.local_endpoint
        self.root.clipboard_clear()
        self.root.clipboard_append(endpoint)
        self.log(f"已复制本地地址：{endpoint}", "成功")

    def change_selected_port(self) -> None:
        tunnel_id = self._selected_tunnel_id(require_running=True)
        if not tunnel_id:
            return
        tunnel = self.manager.tunnels[tunnel_id]
        new_port = simpledialog.askinteger(
            "更改本地端口",
            f"当前端口：{tunnel.profile.local_port}\n请输入新端口：",
            initialvalue=tunnel.profile.local_port,
            minvalue=1,
            maxvalue=65535,
            parent=self.root,
        )
        if new_port is None or new_port == tunnel.profile.local_port:
            return
        replacement = tunnel.profile.clone(keep_id=False)
        replacement.local_port = new_port
        self.log(f"正在将“{replacement.name}”的本地端口改为 {new_port}…")
        threading.Thread(
            target=self._change_port_worker,
            args=(tunnel_id, replacement),
            daemon=True,
        ).start()

    def _change_port_worker(self, old_id: str, replacement: ForwardProfile) -> None:
        try:
            self.manager.stop(old_id)
            self.manager.remove_finished(old_id)
            new_tunnel = self.manager.start(replacement)
            self._async_results.put(("port_changed", old_id, new_tunnel))
        except (RuntimeError, ValueError, OSError) as exc:
            self._async_results.put(("port_error", old_id, str(exc)))

    def _handle_async_results(self) -> None:
        while True:
            try:
                event, tunnel_id, payload = self._async_results.get_nowait()
            except queue.Empty:
                return
            if event == "port_changed":
                active = payload
                if self.active_tree.exists(tunnel_id):
                    self.active_tree.delete(tunnel_id)
                self.active_tree.insert(
                    "",
                    "end",
                    iid=active.id,
                    values=(
                        active.status,
                        active.profile.name,
                        active.profile.local_endpoint,
                        active.profile.target_endpoint,
                        active.profile.ssh_destination,
                        "00:00",
                    ),
                    tags=("pending",),
                )
                self.active_tree.selection_set(active.id)
                self.log(f"本地端口已改为 {active.profile.local_port}，正在重新连接。", "成功")
                self.root.after(900, lambda item_id=active.id: self._confirm_started(item_id))
            elif event == "port_error":
                if self.active_tree.exists(tunnel_id):
                    self.active_tree.delete(tunnel_id)
                self.log(f"更改端口失败：{payload}", "错误")
                messagebox.showerror(
                    "更改端口失败",
                    f"原转发已停止，但新端口未能启动：\n{payload}",
                    parent=self.root,
                )
            elif event == "error":
                self.log(f"停止转发时发生错误：{payload}", "错误")

    def _poll_events(self) -> None:
        self._handle_async_results()
        while True:
            try:
                event, tunnel_id, message = self.manager.events.get_nowait()
            except queue.Empty:
                break
            tunnel = self.manager.tunnels.get(tunnel_id)
            name = tunnel.profile.name if tunnel else "转发"
            if event == "log":
                self.log(f"[{name}] {message}", "错误")
            elif event == "exited":
                self.log(f"“{name}”已结束：{message}", "错误")
            elif event == "stopped":
                self.log(f"“{name}”已停止。")
        self._refresh_active_rows()
        self._refresh_running_count()
        self.root.after(500, self._poll_events)

    def _refresh_active_rows(self) -> None:
        now = datetime.now()
        for tunnel_id, tunnel in list(self.manager.tunnels.items()):
            if not self.active_tree.exists(tunnel_id):
                continue
            seconds = max(0, int((now - tunnel.started_at).total_seconds()))
            elapsed = f"{seconds // 60:02d}:{seconds % 60:02d}"
            tag = "running" if tunnel.status == "运行中" else ("failed" if tunnel.process.poll() is not None else "pending")
            self.active_tree.item(
                tunnel_id,
                values=(
                    tunnel.status,
                    tunnel.profile.name,
                    tunnel.profile.local_endpoint,
                    tunnel.profile.target_endpoint,
                    tunnel.profile.ssh_destination,
                    elapsed,
                ),
                tags=(tag,),
            )

    def _refresh_running_count(self) -> None:
        count = self.manager.running_count()
        favorite_count = len(self.store.favorites)
        self.footer_status.set(f"{count} 个转发正在运行  ·  {favorite_count} 个收藏")

    def log(self, message: str, level: str = "普通") -> None:
        if not hasattr(self, "log_text"):
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{stamp}] {message}\n", level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _restore_window(self) -> None:
        geometry = self.store.preferences.get("window_geometry")
        if isinstance(geometry, str) and "x" in geometry:
            try:
                legacy_geometry = not self.store.preferences.get("dpi_aware_v2", False)
                match = re.match(r"^(\d+)x(\d+)", geometry)
                if legacy_geometry and self.ui_scale > 1.05 and match:
                    width = round(int(match.group(1)) * self.ui_scale)
                    height = round(int(match.group(2)) * self.ui_scale)
                    self.root.geometry(f"{width}x{height}")
                else:
                    self.root.geometry(geometry)
            except tk.TclError:
                pass

    def on_close(self) -> None:
        count = self.manager.running_count()
        if count and not messagebox.askyesno(
            "退出并停止转发",
            f"当前有 {count} 个转发正在运行。退出会全部停止，确定继续吗？",
            icon="warning",
            parent=self.root,
        ):
            return
        self.store.preferences["window_geometry"] = self.root.geometry()
        self.store.preferences["dpi_aware_v2"] = True
        try:
            self.store.save()
        except OSError:
            pass
        self.manager.stop_all()
        self.root.destroy()


def run() -> None:
    enable_windows_dpi_awareness()
    root = tk.Tk()
    configure_tk_scaling(root)
    SSHForwarderApp(root)
    root.mainloop()
