"""Custom rounded Tk widgets for the Organic visual direction.

Tk's native ttk controls are square, so the rounded look is drawn on
Canvas-backed widgets. All widgets keep standard Tk semantics so the rest
of the app does not need to know they are custom.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk


RADIUS = 16


def _round_rectangle_points(x1: float, y1: float, x2: float, y2: float, radius: float) -> list[float]:
    radius = max(0.0, min(radius, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    return [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]


class RoundedButton(tk.Canvas):
    """A canvas-drawn button with rounded corners and a hover state."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        text: str,
        command,
        background: str,
        hover_background: str,
        foreground: str,
        font,
        radius: int = RADIUS,
        height: int = 40,
        **kwargs,
    ) -> None:
        requested_width = kwargs.get("width")
        if requested_width is None:
            measured = tkfont.Font(font=font).measure(text) + 34
            kwargs["width"] = max(72, measured)
        super().__init__(
            master,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            background="#FFFFFF",
            cursor="hand2",
            **kwargs,
        )
        self._container_background = self._parent_background(master)
        self._command = command
        self._background = background
        self._hover_background = hover_background
        self._foreground = foreground
        self._font = font
        self._radius = radius
        self._shape_id = None
        self._text_id = None
        self._text = text
        self._focused = False
        self.configure(bg=self._container_background)
        self.bind("<Configure>", lambda _event: self._redraw())
        self.bind("<Button-1>", lambda _event: self._invoke())
        self.bind("<Enter>", lambda _event: self._set_hover(True))
        self.bind("<Leave>", lambda _event: self._set_hover(False))
        self.configure(takefocus=1)
        self.bind("<Return>", lambda _event: self._invoke())
        self.bind("<space>", lambda _event: self._invoke())
        self.bind("<FocusIn>", lambda _event: self._set_focus(True))
        self.bind("<FocusOut>", lambda _event: self._set_focus(False))
        self._redraw()

    @staticmethod
    def _parent_background(master: tk.Misc) -> str:
        try:
            return str(master.cget("background"))
        except tk.TclError:
            return "#FFFFFF"

    def _invoke(self) -> None:
        if self._command:
            self._command()

    def _set_hover(self, hovering: bool) -> None:
        if self._focused:
            return
        color = self._hover_background if hovering else self._background
        if self._shape_id is not None:
            self.itemconfigure(self._shape_id, fill=color)

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        if self._shape_id is not None:
            self.itemconfigure(
                self._shape_id,
                fill=self._hover_background if focused else self._background,
            )

    def _redraw(self) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        points = _round_rectangle_points(0.5, 0.5, width - 0.5, height - 0.5, self._radius)
        self._shape_id = self.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill=self._background,
            outline="",
        )
        self._text_id = self.create_text(
            width / 2,
            height / 2,
            text=self._text,
            fill=self._foreground,
            font=self._font,
        )

    def set_text(self, text: str) -> None:
        self._text = text
        if self._text_id is not None:
            self.itemconfigure(self._text_id, text=text)


class RoundedEntry(tk.Canvas):
    """A rounded entry that hosts a real Tk Entry for text editing."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        textvariable=None,
        font=None,
        radius: int = RADIUS,
        height: int = 40,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            background="#FFFFFF",
            **kwargs,
        )
        self._radius = radius
        self._font = font
        self._focused = False
        self.entry = tk.Entry(
            self,
            textvariable=textvariable,
            font=font,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            background="#FFFFFF",
            foreground="#3E3A33",
            insertbackground="#3E3A33",
            justify="left",
        )
        self.bind("<Configure>", lambda _event: self._layout())
        self.entry.bind("<FocusIn>", lambda _event: self._set_focus(True))
        self.entry.bind("<FocusOut>", lambda _event: self._set_focus(False))
        self._layout()

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._layout()

    def _layout(self) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        points = _round_rectangle_points(0.5, 0.5, width - 0.5, height - 0.5, self._radius)
        self.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill="#FFFFFF",
            outline="#D9CDB8" if not self._focused else "#C66B3D",
            width=1.4 if not self._focused else 2,
        )
        self.entry.place(x=13, y=1, relwidth=1.0, relheight=1.0, width=-25, height=-2)

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)


class RoundedCombobox(tk.Canvas):
    """A rounded combobox: a real ttk.Combobox hosted inside a rounded frame."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        textvariable=None,
        values=(),
        font=None,
        radius: int = RADIUS,
        height: int = 40,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            background="#FFFFFF",
            **kwargs,
        )
        self._radius = radius
        self._font = font
        self._focused = False
        self.combobox = ttk.Combobox(
            self,
            textvariable=textvariable,
            values=values,
            state="normal",
            cursor="hand2",
        )
        self.combobox.configure(font=font)
        self.bind("<Configure>", lambda _event: self._layout())
        self.combobox.bind("<FocusIn>", lambda _event: self._set_focus(True))
        self.combobox.bind("<FocusOut>", lambda _event: self._set_focus(False))
        self._layout()

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._layout()

    def _layout(self) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        points = _round_rectangle_points(0.5, 0.5, width - 0.5, height - 0.5, self._radius)
        self.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill="#FFFFFF",
            outline="#D9CDB8" if not self._focused else "#C66B3D",
            width=1.4 if not self._focused else 2,
        )
        self.combobox.place(x=9, y=0, relwidth=1.0, relheight=1.0, width=-18)

    def configure_values(self, values) -> None:
        self.combobox.configure(values=values)


def apply_rounded_treeview_style(style: ttk.Style) -> None:
    """Keep Treeview rows and headings visually consistent with rounded cards."""

    style.configure(
        "Rounded.Treeview",
        rowheight=38,
        background="#FBF7EE",
        fieldbackground="#FBF7EE",
        foreground="#3E3A33",
        borderwidth=0,
        font=("Microsoft YaHei UI", 10),
    )
    style.configure(
        "Rounded.Treeview.Heading",
        font=("Microsoft YaHei UI", 10, "bold"),
        foreground="#6B6355",
        background="#EFE7D5",
        padding=(8, 9),
        relief="flat",
    )
    style.map(
        "Rounded.Treeview",
        background=[("selected", "#E4D7BE")],
        foreground=[("selected", "#3E3A33")],
    )
