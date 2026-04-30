#!/usr/bin/env python3
"""
Mac Macro Recorder - 키보드 매크로 기록 및 재생
메인 GUI 프로세스 (pynput 직접 사용 없음 → SIGTRAP 걱정 없음)
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
import json
import os
import sys
import subprocess
import copy

SAVE_FILE = os.path.expanduser("~/.mac_macros.json")
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker.py")
PYTHON = sys.executable

# ── Design Tokens (Dark) ─────────────────────────────────────────────────────
BG             = "#1c1c1e"   # 앱 배경
SURFACE        = "#2c2c2e"   # 카드 배경
SURFACE_2      = "#3a3a3c"   # 호버 / secondary
BORDER         = "#3a3a3c"
BORDER_2       = "#48484a"
TEXT           = "#f5f5f7"
TEXT_MUTED     = "#a1a1a6"
TEXT_SUBTLE    = "#6e6e73"
ACCENT         = "#ffffff"   # primary 버튼 (밝은 강조)
ACCENT_HOV     = "#d1d1d6"
ACCENT_FG      = "#1c1c1e"
DANGER         = "#ff453a"
DANGER_HOV     = "#ff6961"
DANGER_PRESSED = "#d92e25"
DANGER_BG      = "#3a1a1a"
SUCCESS        = "#30d158"
SUCCESS_BG     = "#1e3a23"
WARN           = "#ff9f0a"
WARN_BG        = "#3a2c1a"
WARN_BORDER    = "#5c4a1f"
WARN_TEXT2     = "#fbbf24"
SELECT_BG      = "#3a3a3c"
KEYCAP_BG      = "#3a3a3c"
KEYCAP_BORDER  = "#5e5e63"
# 버튼은 라이트 톤 배경 + 검정 텍스트로 통일 (다크 앱 위에서 강조)
BTN_FG         = "#0a0a0a"
BTN_LIGHT      = "#e5e5e7"
BTN_LIGHT_HOV  = "#d1d1d6"
BTN_BORDER_LT  = "#c7c7cc"
DANGER_TINT    = "#ffd9d6"   # 삭제 호버용 연한 핑크

FAM_TEXT    = "SF Pro Text"
FAM_DISPLAY = "SF Pro Display"
FAM_MONO    = "SF Mono"

F_H1        = (FAM_DISPLAY, 18, "bold")
F_SUB       = (FAM_TEXT, 11)
F_BODY      = (FAM_TEXT, 12)
F_BTN       = (FAM_TEXT, 12)
F_SMALL     = (FAM_TEXT, 10)
F_HEAD      = (FAM_TEXT, 10, "bold")
F_KEY       = (FAM_DISPLAY, 17, "bold")
F_KEY_SM    = (FAM_DISPLAY, 13, "bold")
F_DLG_TITLE = (FAM_DISPLAY, 15, "bold")


# ── subprocess 헬퍼 ──────────────────────────────────────────────────────────
def _spawn(*args, merge_stderr: bool = False) -> subprocess.Popen:
    return subprocess.Popen(
        [PYTHON, WORKER] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge_stderr else subprocess.DEVNULL,
        text=True,
    )

def _check_input_monitoring() -> bool:
    try:
        proc = _spawn("test")
        line = proc.stdout.readline()
        proc.terminate()
        proc.wait(timeout=1)
        return "OK" in line
    except Exception:
        return False

def _check_accessibility() -> bool:
    try:
        proc = _spawn("accessibility")
        line = proc.stdout.readline()
        proc.terminate()
        proc.wait(timeout=1)
        return "OK" in line
    except Exception:
        return False

def _prompt_accessibility():
    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to key code 53'],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        pass

def _open_perm_settings():
    _prompt_accessibility()
    # Input Monitoring
    subprocess.Popen([
        "open",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
    ])
    # Accessibility (재생용 키 송출)
    subprocess.Popen([
        "open",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
    ])

# ── 위젯 헬퍼 ────────────────────────────────────────────────────────────────
def make_button(parent, text, command=None, kind="secondary", icon="",
                fg_override=None, **kw):
    palette = {
        "primary":   (ACCENT,    BTN_FG, ACCENT_HOV,    None),
        "danger":    (DANGER,    BTN_FG, DANGER_HOV,    None),
        "danger_o":  (BTN_LIGHT, BTN_FG, DANGER_TINT,   DANGER),
        "secondary": (BTN_LIGHT, BTN_FG, BTN_LIGHT_HOV, BTN_BORDER_LT),
        "ghost":     (BTN_LIGHT, BTN_FG, BTN_LIGHT_HOV, BTN_BORDER_LT),
    }
    bg, fg, hov, border = palette.get(kind, palette["secondary"])
    if fg_override:
        fg = fg_override
    label = (icon + "  " + text).strip() if icon else text
    btn = tk.Button(
        parent, text=label, command=command,
        bg=bg, fg=fg,
        activebackground=hov, activeforeground=fg,
        font=F_BTN, relief="flat", bd=0,
        cursor="hand2", padx=14, pady=8,
        highlightthickness=1 if border else 0,
        highlightbackground=border or bg,
        highlightcolor=border or bg,
        **kw,
    )
    def on_enter(_): btn.config(bg=hov)
    def on_leave(_): btn.config(bg=bg)
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def make_card(parent, **kw):
    return tk.Frame(parent, bg=BG,
                    highlightthickness=1,
                    highlightbackground=BORDER,
                    highlightcolor=BORDER, **kw)


# ── 매크로 저장소 ─────────────────────────────────────────────────────────────
class MacroStore:
    def __init__(self):
        self.data: dict = {}
        self._load()

    def _load(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE) as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def save(self):
        with open(SAVE_FILE, "w") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def macro_names(self):
        return [k for k in self.data if not k.startswith("__sc__")]

    def get_events(self, name: str) -> list:
        return self.data.get(name, [])

    def get_shortcut(self, name: str) -> str:
        return self.data.get(f"__sc__{name}", "")

    def set_shortcut(self, name: str, sc: str):
        if sc:
            self.data[f"__sc__{name}"] = sc
        else:
            self.data.pop(f"__sc__{name}", None)

    def set_events(self, name: str, events: list):
        self.data[name] = events

    def delete(self, name: str):
        self.data.pop(name, None)
        self.data.pop(f"__sc__{name}", None)


# ── GUI ───────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mac Macro Recorder")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.geometry("980x680")
        self.minsize(900, 620)

        self.store = MacroStore()
        self._rec_proc: subprocess.Popen | None = None
        self._rec_thread: threading.Thread | None = None
        self._rec_events: list = []
        self._rec_name: str = ""
        self._rec_started_at: float = 0.0
        self._rec_paused: bool = False
        self._rec_pause_started_at: float = 0.0
        self._rec_paused_total: float = 0.0
        self._record_dialog = None
        self._hotkey_procs: dict = {}
        self._playing: set = set()
        self._input_ok: bool | None = None
        self._accessibility_ok: bool | None = None

        self._setup_style()
        self._build_ui()
        self._refresh_list()
        self.after(200, self._async_check_perm)

    # ── 스타일 ────────────────────────────────────────────────────────────
    def _setup_style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass

        s.configure("Modern.Treeview",
                    background=BG, fieldbackground=BG, foreground=TEXT,
                    borderwidth=0, relief="flat",
                    rowheight=36, font=F_BODY)
        s.configure("Modern.Treeview.Heading",
                    background=SURFACE, foreground=TEXT_MUTED,
                    borderwidth=0, relief="flat",
                    font=F_HEAD, padding=(10, 8))
        s.map("Modern.Treeview",
              background=[("selected", SELECT_BG)],
              foreground=[("selected", TEXT)])
        s.layout("Modern.Treeview", [
            ("Treeview.treearea", {"sticky": "nswe"})
        ])

        s.configure("Modern.TSpinbox",
                    fieldbackground=BG, background=BG,
                    foreground=TEXT, borderwidth=1,
                    arrowsize=10, padding=4)

    # ── 권한 ─────────────────────────────────────────────────────────────
    def _async_check_perm(self):
        self._set_status("권한 확인 중...", "muted")
        self.update_idletasks()

        def check():
            input_ok = _check_input_monitoring()
            accessibility_ok = _check_accessibility()
            self.after(0, lambda: self._on_perm_result(
                input_ok, accessibility_ok))

        threading.Thread(target=check, daemon=True).start()

    def _on_perm_result(self, input_ok: bool, accessibility_ok: bool):
        self._input_ok = input_ok
        self._accessibility_ok = accessibility_ok
        self._render_permission_state()
        if input_ok and accessibility_ok:
            self._set_status("준비 완료 · 더블클릭으로 매크로 재생", "muted")
            self.perm_card.pack_forget()
            self._start_hotkey_watchers()
        else:
            missing = []
            if not input_ok:
                missing.append("입력 모니터링")
            if not accessibility_ok:
                missing.append("손쉬운 사용")
            self._set_status(f"{', '.join(missing)} 권한이 필요합니다", "warn")
            self.perm_card.pack(fill="x", padx=20, pady=(0, 12))
            self._start_hotkey_watchers()

    # ── 레이아웃 ──────────────────────────────────────────────────────────
    def _build_ui(self):
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True, padx=18, pady=(18, 0))

        top = tk.Frame(shell, bg=BG)
        top.pack(fill="x", pady=(0, 12))
        title_block = tk.Frame(top, bg=BG)
        title_block.pack(side="left")
        tk.Label(title_block, text="Macro Studio", bg=BG,
                 fg=TEXT, font=(FAM_DISPLAY, 22, "bold")).pack(anchor="w")
        tk.Label(title_block, text="매크로를 선택하고 실행 흐름을 편집하세요",
                 bg=BG, fg=TEXT_MUTED, font=F_SUB).pack(anchor="w", pady=(2, 0))

        self.perm_card = tk.Frame(self, bg=WARN_BG,
                                  highlightthickness=1,
                                  highlightbackground=WARN_BORDER)
        inner = tk.Frame(self.perm_card, bg=WARN_BG, padx=14, pady=12)
        inner.pack(fill="x")
        tk.Label(inner, text="macOS 권한 확인이 필요합니다",
                 bg=WARN_BG, fg=WARN, font=(FAM_TEXT, 11, "bold")).pack(anchor="w")
        tk.Label(inner, text="녹화, 전역 단축키, 재생은 각각 시스템 권한을 사용합니다",
                 bg=WARN_BG, fg=WARN_TEXT2, font=F_SMALL).pack(anchor="w", pady=(2, 8))
        self.input_perm_var = tk.StringVar(value="입력 모니터링 확인 중")
        self.access_perm_var = tk.StringVar(value="손쉬운 사용 확인 중")
        tk.Label(inner, textvariable=self.input_perm_var,
                 bg=WARN_BG, fg=TEXT, font=F_SMALL).pack(anchor="w")
        tk.Label(inner, textvariable=self.access_perm_var,
                 bg=WARN_BG, fg=TEXT, font=F_SMALL).pack(anchor="w", pady=(2, 8))
        perm_btn_row = tk.Frame(inner, bg=WARN_BG)
        perm_btn_row.pack(anchor="w")
        make_button(perm_btn_row, "권한 설정 열기",
                    command=self._guide_permission, kind="primary").pack(side="left")
        make_button(perm_btn_row, "다시 확인",
                    command=self._async_check_perm, kind="secondary"
                    ).pack(side="left", padx=(8, 0))

        content = tk.Frame(shell, bg=BG)
        content.pack(fill="both", expand=True)

        sidebar = make_card(content)
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar_inner = tk.Frame(sidebar, bg=BG, padx=12, pady=12)
        sidebar_inner.pack(fill="both", expand=True)

        list_head = tk.Frame(sidebar_inner, bg=BG)
        list_head.pack(fill="x", pady=(0, 10))
        tk.Label(list_head, text="매크로", bg=BG, fg=TEXT,
                 font=(FAM_TEXT, 13, "bold")).pack(side="left")
        self.macro_count_var = tk.StringVar(value="0개")
        tk.Label(list_head, textvariable=self.macro_count_var,
                 bg=BG, fg=TEXT_MUTED, font=F_SMALL).pack(side="right", pady=(2, 0))

        list_toolbar = tk.Frame(sidebar_inner, bg=BG)
        list_toolbar.pack(fill="x", pady=(0, 10))
        make_button(list_toolbar, "추가", icon="+",
                    command=self._toggle_record, kind="primary"
                    ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        make_button(list_toolbar, "삭제",
                    command=self._delete_selected, kind="danger_o"
                    ).pack(side="left", fill="x", expand=True, padx=(5, 0))

        cols = ("name", "shortcut")
        self.tree = ttk.Treeview(sidebar_inner, columns=cols, show="headings",
                                  height=18, style="Modern.Treeview")
        self.tree.heading("name", text="매크로")
        self.tree.heading("shortcut", text="단축키")
        self.tree.column("name", width=210, anchor="w")
        self.tree.column("shortcut", width=90, anchor="center")
        self.tree.pack(fill="y")
        self.tree.bind("<Double-1>", lambda e: self._play_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_macro_select())

        self.empty_label = tk.Label(
            sidebar_inner,
            text="매크로 없음\n녹화로 새 매크로를 만드세요",
            bg=BG, fg=TEXT_SUBTLE, font=F_BODY, justify="center")

        side_actions = tk.Frame(sidebar_inner, bg=BG)
        side_actions.pack(fill="x", pady=(12, 0))
        self.rec_btn = make_button(side_actions, "새 매크로 녹화", icon="●",
                                   command=self._toggle_record, kind="danger")
        self.rec_btn.pack(fill="x")

        main = tk.Frame(content, bg=BG)
        main.pack(side="left", fill="both", expand=True)

        detail_card = make_card(main)
        detail_card.pack(fill="x", pady=(0, 12))
        detail = tk.Frame(detail_card, bg=BG, padx=18, pady=16)
        detail.pack(fill="x")

        detail_top = tk.Frame(detail, bg=BG)
        detail_top.pack(fill="x")
        name_block = tk.Frame(detail_top, bg=BG)
        name_block.pack(side="left")
        self.detail_name_var = tk.StringVar(value="매크로를 선택하세요")
        tk.Label(name_block, textvariable=self.detail_name_var, bg=BG,
                 fg=TEXT, font=(FAM_DISPLAY, 20, "bold")).pack(anchor="w")
        self.detail_sub_var = tk.StringVar(value="왼쪽 목록에서 매크로를 선택하면 설정과 입력 흐름이 표시됩니다")
        tk.Label(name_block, textvariable=self.detail_sub_var, bg=BG,
                 fg=TEXT_MUTED, font=F_SUB).pack(anchor="w", pady=(2, 0))

        action_bar = tk.Frame(detail_top, bg=BG)
        action_bar.pack(side="right")
        make_button(action_bar, "실행", icon="▶",
                    command=self._play_selected, kind="primary").pack(side="left", padx=(0, 8))
        make_button(action_bar, "입력 편집", icon="⌨",
                    command=self._edit_selected_events, kind="secondary").pack(side="left", padx=(0, 8))
        make_button(action_bar, "단축키 변경", icon="⌘",
                    command=self._set_shortcut, kind="secondary").pack(side="left", padx=(0, 8))
        make_button(action_bar, "삭제",
                    command=self._delete_selected, kind="danger_o").pack(side="left")

        stats = tk.Frame(detail, bg=BG)
        stats.pack(fill="x", pady=(18, 0))
        self.stat_events_var = tk.StringVar(value="0")
        self.stat_duration_var = tk.StringVar(value="0.00s")
        self.stat_shortcut_var = tk.StringVar(value="—")
        self.stat_delay_var = tk.StringVar(value="원본")
        self._make_stat(stats, "이벤트", self.stat_events_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._make_stat(stats, "길이", self.stat_duration_var).pack(side="left", fill="x", expand=True, padx=8)
        self._make_stat(stats, "단축키", self.stat_shortcut_var).pack(side="left", fill="x", expand=True, padx=8)
        self._make_stat(stats, "딜레이", self.stat_delay_var).pack(side="left", fill="x", expand=True, padx=(8, 0))

        preview_card = make_card(main)
        preview_card.pack(fill="both", expand=True)
        preview = tk.Frame(preview_card, bg=BG, padx=14, pady=12)
        preview.pack(fill="both", expand=True)
        preview_head = tk.Frame(preview, bg=BG)
        preview_head.pack(fill="x", pady=(0, 10))
        tk.Label(preview_head, text="입력 이벤트", bg=BG, fg=TEXT,
                 font=(FAM_TEXT, 13, "bold")).pack(side="left")
        tk.Label(preview_head, text="더블클릭하거나 입력 편집에서 키와 타이밍을 수정",
                 bg=BG, fg=TEXT_MUTED, font=F_SMALL).pack(side="right", pady=(3, 0))

        event_cols = ("idx", "type", "key", "delay", "gap")
        self.event_tree = ttk.Treeview(preview, columns=event_cols,
                                       show="headings", height=12,
                                       style="Modern.Treeview")
        for col, title, width, anchor in [
            ("idx", "#", 50, "center"),
            ("type", "동작", 90, "center"),
            ("key", "키", 220, "w"),
            ("delay", "시점", 120, "center"),
            ("gap", "간격", 120, "center"),
        ]:
            self.event_tree.heading(col, text=title)
            self.event_tree.column(col, width=width, anchor=anchor)
        self.event_tree.pack(fill="both", expand=True)
        self.event_tree.bind("<Double-1>", lambda e: self._edit_selected_events())

        option_row = tk.Frame(main, bg=BG)
        option_row.pack(fill="x", pady=(12, 0))
        delay_label = tk.Frame(option_row, bg=BG)
        delay_label.pack(side="left")
        tk.Label(delay_label, text="재생 딜레이", bg=BG, fg=TEXT,
                 font=(FAM_TEXT, 11, "bold")).pack(anchor="w")
        tk.Label(delay_label, text="0이면 녹화한 타이밍 그대로 재생",
                 bg=BG, fg=TEXT_MUTED, font=F_SMALL).pack(anchor="w")

        self.delay_var = tk.StringVar(value="0")
        self.delay_var.trace_add("write", lambda *_: self._sync_detail())
        delay_box = tk.Frame(option_row, bg=BG)
        delay_box.pack(side="right")
        tk.Spinbox(delay_box, from_=0, to=9999, increment=10,
                   textvariable=self.delay_var, width=6,
                   font=F_BODY, relief="flat",
                   bg=SURFACE, fg=TEXT,
                   insertbackground=TEXT,
                   readonlybackground=SURFACE,
                   buttonbackground=SURFACE_2,
                   highlightthickness=1,
                   highlightbackground=BORDER_2,
                   highlightcolor=BORDER_2,
                   ).pack(side="left")
        tk.Label(delay_box, text="ms", bg=BG, fg=TEXT_MUTED,
                 font=F_SMALL).pack(side="left", padx=(6, 0))
        make_button(delay_box, "선택 매크로에 적용",
                    command=self._apply_playback_delay_to_selected,
                    kind="secondary").pack(side="left", padx=(10, 0))

        status_bar = tk.Frame(self, bg=SURFACE,
                              highlightthickness=1,
                              highlightbackground=BORDER)
        status_bar.pack(fill="x", side="bottom")
        self._status_dot = tk.Label(status_bar, text="●", bg=SURFACE,
                                    fg=TEXT_SUBTLE, font=(FAM_TEXT, 11))
        self._status_dot.pack(side="left", padx=(14, 6), pady=8)
        self.status_var = tk.StringVar(value="시작 중...")
        tk.Label(status_bar, textvariable=self.status_var, bg=SURFACE,
                 fg=TEXT_MUTED, font=F_SMALL).pack(side="left", pady=8)

    def _set_status(self, text: str, kind: str = "muted"):
        colors = {
            "muted":   TEXT_SUBTLE,
            "info":    "#2563eb",
            "success": SUCCESS,
            "warn":    WARN,
            "danger":  DANGER,
            "rec":     DANGER,
        }
        self._status_dot.config(fg=colors.get(kind, TEXT_SUBTLE))
        self.status_var.set(text)

    def _make_stat(self, parent, title: str, variable: tk.StringVar):
        box = tk.Frame(parent, bg=SURFACE,
                       highlightthickness=1,
                       highlightbackground=BORDER)
        tk.Label(box, text=title, bg=SURFACE, fg=TEXT_MUTED,
                 font=F_SMALL).pack(anchor="w", padx=12, pady=(9, 0))
        tk.Label(box, textvariable=variable, bg=SURFACE, fg=TEXT,
                 font=(FAM_DISPLAY, 15, "bold")).pack(anchor="w", padx=12, pady=(2, 9))
        return box

    def _render_permission_state(self):
        def label(ok, name):
            if ok is None:
                return f"• {name}: 확인 중"
            return f"{'✓' if ok else '×'} {name}: {'허용됨' if ok else '권한 필요'}"

        self.input_perm_var.set(label(self._input_ok, "입력 모니터링"))
        self.access_perm_var.set(label(self._accessibility_ok, "손쉬운 사용"))

    def _update_status_hint(self):
        if self._input_ok and self._rec_proc is None:
            sel = self._selected_name()
            if sel:
                self._set_status(f"선택: {sel}", "muted")

    def _on_macro_select(self):
        self._update_status_hint()
        self._sync_detail()

    def _sync_detail(self):
        name = self._selected_name()
        if not name:
            self.detail_name_var.set("매크로를 선택하세요")
            self.detail_sub_var.set("왼쪽 목록에서 매크로를 선택하면 설정과 입력 흐름이 표시됩니다")
            self.stat_events_var.set("0")
            self.stat_duration_var.set("0.00s")
            self.stat_shortcut_var.set("—")
            self.stat_delay_var.set(self._delay_label())
            self._refresh_event_preview([])
            return

        events = self.store.get_events(name)
        sc = _format_combo(self.store.get_shortcut(name)) or "—"
        duration = _macro_duration(events)
        self.detail_name_var.set(name)
        self.detail_sub_var.set(_event_summary(events))
        self.stat_events_var.set(str(len(events)))
        self.stat_duration_var.set(f"{duration:.2f}s")
        self.stat_shortcut_var.set(sc)
        self.stat_delay_var.set(self._delay_label())
        self._refresh_event_preview(events)

    def _delay_label(self):
        try:
            ms = float(self.delay_var.get())
        except Exception:
            ms = 0
        return "원본" if ms <= 0 else f"{ms:g}ms"

    def _apply_playback_delay_to_selected(self):
        name = self._selected_name()
        if not name:
            self._set_status("딜레이를 적용할 매크로를 선택하세요", "muted")
            return
        try:
            ms = float(self.delay_var.get())
        except Exception:
            self._set_status("딜레이는 ms 숫자로 입력하세요", "warn")
            return
        if ms <= 0:
            self._set_status("저장 적용할 딜레이는 1ms 이상이어야 합니다", "warn")
            return
        events = copy.deepcopy(self.store.get_events(name))
        if not events:
            return
        gap = ms / 1000.0
        for idx, ev in enumerate(events):
            ev["delay"] = idx * gap
        self.store.set_events(name, _normalized_events(events))
        self.store.save()
        self._refresh_list()
        self._set_status(f"딜레이 일괄 적용됨 · {name} · {ms:g}ms", "success")

    def _refresh_event_preview(self, events: list):
        self.event_tree.delete(*self.event_tree.get_children())
        for idx, ev in enumerate(events[:200], start=1):
            prev = events[idx - 2]["delay"] if idx > 1 else 0
            gap = max(0, float(ev.get("delay", 0)) - float(prev))
            self.event_tree.insert(
                "", "end", iid=str(idx - 1),
                values=(
                    idx,
                    _event_type_label(ev.get("type", "")),
                    _display_key(ev.get("key", "")),
                    f"{float(ev.get('delay', 0)):.3f}s",
                    f"{gap:.3f}s",
                )
            )

    def _guide_permission(self):
        messagebox.showinfo(
            "필요 권한 안내",
            "Mac Macro Recorder는 두 가지 권한이 필요합니다:\n\n"
            "1) 입력 모니터링 (Input Monitoring)\n"
            "   → 키 녹화 및 전역 단축키 감지\n\n"
            "2) 손쉬운 사용 (Accessibility)\n"
            "   → 매크로 재생 (키 송출)\n\n"
            "목록에 Terminal 또는 Python 이 없으면, 지금 뜨는 macOS\n"
            "권한 확인 팝업에서 허용하거나 설정 화면의 + 버튼으로\n"
            "Terminal 앱을 직접 추가한 뒤 앱을 재실행하세요.",
            parent=self,
        )
        _open_perm_settings()

    # ── 리스트 ────────────────────────────────────────────────────────────
    def _refresh_list(self):
        selected = self._selected_name()
        self.tree.delete(*self.tree.get_children())
        names = self.store.macro_names()
        for name in names:
            sc = _format_combo(self.store.get_shortcut(name)) or "—"
            self.tree.insert("", "end", iid=name,
                             values=(name, sc))
        if names:
            self.empty_label.place_forget()
            if selected in names:
                self.tree.selection_set(selected)
            elif not self.tree.selection():
                self.tree.selection_set(names[0])
        else:
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.macro_count_var.set(f"{len(names)}개")
        self._sync_detail()

    def _selected_name(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    # ── 녹화 ─────────────────────────────────────────────────────────────
    def _toggle_record(self):
        if self._rec_proc is not None:
            if self._record_dialog:
                self._record_dialog.lift()
                self._record_dialog.focus_force()
            return

        if self._input_ok is False:
            self._guide_permission()
            return
        if self._input_ok is None:
            messagebox.showinfo("잠시만요", "권한 확인 중입니다.",
                                parent=self)
            return

        name = simpledialog.askstring(
            "매크로 이름", "저장할 매크로 이름을 입력하세요:", parent=self)
        if not name:
            return

        self._rec_name = name
        self._rec_events = []
        self._rec_started_at = time.time()
        self._rec_paused = False
        self._rec_pause_started_at = 0.0
        self._rec_paused_total = 0.0

        try:
            self._rec_proc = _spawn("record")
            self._rec_proc.stdout.readline()  # READY
        except Exception as e:
            self._rec_proc = None
            self._set_status(f"녹화 시작 실패: {e}", "danger")
            return

        self._rec_thread = threading.Thread(
            target=self._read_record_events, daemon=True)
        self._rec_thread.start()

        self.rec_btn.config(text="●  녹화 중", bg=DANGER_PRESSED)
        self.rec_btn.unbind("<Enter>")
        self.rec_btn.unbind("<Leave>")
        self.rec_btn.bind("<Enter>", lambda e: self.rec_btn.config(bg=DANGER))
        self.rec_btn.bind("<Leave>", lambda e: self.rec_btn.config(bg=DANGER_PRESSED))

        self._record_dialog = RecordingDialog(self, name)
        self._set_status(f"녹화 중 · {name}", "rec")

    def _read_record_events(self):
        proc = self._rec_proc
        if proc is None:
            return
        for line in proc.stdout:
            line = line.strip()
            if not line or line == "READY":
                continue
            try:
                ev = json.loads(line)
                if self._rec_paused:
                    continue
                ev["delay"] = max(0.0, float(ev.get("delay", 0)) - self._rec_paused_total)
                self._rec_events.append(ev)
                if self._record_dialog:
                    self.after(0, self._record_dialog.refresh)
            except Exception:
                pass

    def _set_record_paused(self, paused: bool):
        if self._rec_proc is None or self._rec_paused == paused:
            return
        now = time.time()
        if paused:
            self._rec_paused = True
            self._rec_pause_started_at = now
            self._set_status(f"녹화 일시정지 · {self._rec_name}", "warn")
        else:
            if self._rec_pause_started_at:
                self._rec_paused_total += now - self._rec_pause_started_at
            self._rec_pause_started_at = 0.0
            self._rec_paused = False
            self._set_status(f"녹화 중 · {self._rec_name}", "rec")
        if self._record_dialog:
            self._record_dialog.refresh()

    def _record_elapsed(self) -> float:
        if not self._rec_started_at:
            return 0.0
        paused_total = self._rec_paused_total
        if self._rec_paused and self._rec_pause_started_at:
            paused_total += time.time() - self._rec_pause_started_at
        return max(0.0, time.time() - self._rec_started_at - paused_total)

    def _stop_record(self):
        if self._rec_proc:
            try:
                self._rec_proc.terminate()
                self._rec_proc.wait(timeout=2)
            except Exception:
                pass
            self._rec_proc = None

        if self._record_dialog:
            dlg = self._record_dialog
            self._record_dialog = None
            try:
                dlg.destroy()
            except Exception:
                pass

        self._rec_paused = False
        self._rec_pause_started_at = 0.0

        self.rec_btn.config(text="●  새 매크로 녹화", bg=DANGER)
        self.rec_btn.unbind("<Enter>")
        self.rec_btn.unbind("<Leave>")
        self.rec_btn.bind("<Enter>", lambda e: self.rec_btn.config(bg=DANGER_HOV))
        self.rec_btn.bind("<Leave>", lambda e: self.rec_btn.config(bg=DANGER))

        events = list(self._rec_events)
        if events:
            self.store.set_events(self._rec_name, events)
            self.store.save()
            self._set_status(
                f"저장 완료 · {self._rec_name} · {len(events)}개 이벤트",
                "success")
        else:
            self._set_status("녹화된 키가 없습니다", "muted")
        self._refresh_list()

    # ── 재생 ─────────────────────────────────────────────────────────────
    def _play_selected(self):
        name = self._selected_name()
        if not name:
            self._set_status("재생할 매크로를 선택하세요", "muted")
            return
        self._play(name)

    def _play(self, name: str):
        if name in self._playing:
            return
        if self._accessibility_ok is False:
            self._set_status("재생하려면 손쉬운 사용 권한이 필요합니다", "warn")
            self._guide_permission()
            return
        if self._accessibility_ok is None:
            self._set_status("권한 확인 후 다시 재생하세요", "muted")
            self._async_check_perm()
            return
        events = self.store.get_events(name)
        if not events:
            return
        try:
            fixed_ms = float(self.delay_var.get())
        except Exception:
            fixed_ms = 0.0
        self._playing.add(name)

        self._set_status(f"재생 중 · {name}", "rec")

        def run():
            import tempfile
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8")
            try:
                json.dump(events, tmp, ensure_ascii=False)
                tmp.close()
                proc = _spawn("play", tmp.name, str(fixed_ms),
                              merge_stderr=True)
                ready = (proc.stdout.readline() or "").strip()
                if ready.startswith("ERROR"):
                    msg = ready.split(":", 1)[-1]
                    self.after(0, lambda m=msg: self._on_play_error(m))
                    proc.wait(timeout=5)
                    return
                done = ""
                for line in proc.stdout:
                    line = line.strip()
                    if line.startswith("DONE"):
                        done = line
                        break
                    if line.startswith("ERROR"):
                        msg = line.split(":", 1)[-1]
                        self.after(0, lambda m=msg: self._on_play_error(m))
                        return
                proc.wait(timeout=5)
                if done:
                    sent = done.split(":", 1)[-1] if ":" in done else "?"
                    self.after(0, lambda: self._set_status(
                        f"재생 완료 · {name} · {sent}개 키", "success"))
                else:
                    self.after(0, lambda: self._set_status(
                        "재생 종료 · 손쉬운 사용(Accessibility) 권한을 확인하세요",
                        "warn"))
            except Exception as e:
                self.after(0, lambda e=e: self._set_status(
                    f"재생 오류 · {e}", "danger"))
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
                self.after(0, lambda: self._playing.discard(name))

        threading.Thread(target=run, daemon=True).start()

    def _on_play_error(self, msg: str):
        if msg == "accessibility":
            self._accessibility_ok = False
            self._render_permission_state()
            self.perm_card.pack(fill="x", padx=20, pady=(0, 12))
            self._set_status("재생 실패 · 손쉬운 사용 권한을 확인하세요", "danger")
        else:
            self._set_status(f"재생 실패 · {msg}", "danger")

    # ── 이벤트 편집 ─────────────────────────────────────────────────────
    def _edit_selected_events(self):
        name = self._selected_name()
        if not name:
            self._set_status("편집할 매크로를 선택하세요", "muted")
            return
        dlg = MacroEditorDialog(self, name, self.store.get_events(name))
        self.wait_window(dlg)
        if dlg.result is not None:
            self.store.set_events(name, dlg.result)
            self.store.save()
            self._refresh_list()
            self._set_status(f"입력 편집 저장됨 · {name}", "success")

    # ── 단축키 설정 ───────────────────────────────────────────────────────
    def _set_shortcut(self):
        name = self._selected_name()
        if not name:
            self._set_status("단축키를 설정할 매크로를 선택하세요", "muted")
            return
        if not self._input_ok:
            self._guide_permission()
            return

        existing = self.store.get_shortcut(name)
        dlg = ShortcutDialog(self, name, existing)
        self.wait_window(dlg)
        if dlg.result is not None:
            self.store.set_shortcut(name, dlg.result)
            self.store.save()
            self._refresh_list()
            self._start_hotkey_watchers()
            if dlg.result:
                self._set_status(
                    f"단축키 등록됨 · {name} · {_format_combo(dlg.result)}",
                    "success")
            else:
                self._set_status(f"단축키 제거됨 · {name}", "muted")

    # ── 삭제 ─────────────────────────────────────────────────────────────
    def _delete_selected(self):
        name = self._selected_name()
        if not name:
            return
        if messagebox.askyesno(
            "삭제 확인", f"'{name}' 매크로를 삭제할까요?", parent=self):
            self.store.delete(name)
            self.store.save()
            self._refresh_list()
            self._start_hotkey_watchers()
            self._set_status(f"삭제됨 · {name}", "muted")

    # ── 전역 단축키 감시 ───────────────────────────────────────────────────
    def _start_hotkey_watchers(self):
        for proc in list(self._hotkey_procs.values()):
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                pass
        self._hotkey_procs = {}

        if not self._input_ok:
            return

        for name in self.store.macro_names():
            sc = self.store.get_shortcut(name)
            if not sc:
                continue
            try:
                combo = _to_pynput_combo(sc)
                proc = _spawn("hotkey", combo)
                def watch(p, n):
                    line = p.stdout.readline()
                    if "READY" not in line:
                        return
                    for hit in p.stdout:
                        if "HIT" in hit:
                            self.after(0, lambda n=n: self._play(n))
                threading.Thread(target=watch, args=(proc, name), daemon=True).start()
                self._hotkey_procs[name] = proc
            except Exception:
                pass


# ── 단축키 변환 ─────────────────────────────────────────────────────────────
def _to_pynput_combo(sc: str) -> str:
    """'cmd+shift+a' → '<cmd>+<shift>+a'"""
    modmap = {
        "cmd": "<cmd>", "ctrl": "<ctrl>", "alt": "<alt>", "shift": "<shift>",
        "command": "<cmd>", "control": "<ctrl>", "option": "<alt>",
    }
    result = []
    for p in sc.lower().split("+"):
        p = p.strip()
        result.append(modmap.get(p) or (p if len(p) == 1 else f"<{p}>"))
    return "+".join(result)


_SYM_MAP = {
    "cmd": "⌘", "command": "⌘",
    "ctrl": "⌃", "control": "⌃",
    "alt": "⌥", "option": "⌥",
    "shift": "⇧",
    "enter": "↵", "return": "↵",
    "esc": "⎋", "escape": "⎋",
    "tab": "⇥",
    "space": "Space",
    "backspace": "⌫",
    "delete": "⌦",
    "up": "↑", "down": "↓", "left": "←", "right": "→",
}

def _key_symbol(part: str) -> str:
    p = part.lower().strip()
    if p in _SYM_MAP:
        return _SYM_MAP[p]
    if len(p) == 1:
        return p.upper()
    return p.capitalize()

def _format_combo(combo: str) -> str:
    if not combo:
        return ""
    parts = [_key_symbol(p) for p in combo.split("+")]
    return " ".join(parts)


def _event_type_label(kind: str) -> str:
    return "누름" if kind == "press" else "뗌" if kind == "release" else kind


def _display_key(raw: str) -> str:
    if not raw:
        return ""
    return _key_symbol(raw.replace("Key.", ""))


def _macro_duration(events: list) -> float:
    if not events:
        return 0.0
    try:
        return max(float(ev.get("delay", 0)) for ev in events)
    except Exception:
        return 0.0


def _event_summary(events: list) -> str:
    if not events:
        return "입력 이벤트가 없습니다"
    keys = []
    for ev in events:
        if ev.get("type") == "press":
            key = _display_key(ev.get("key", ""))
            if key and key not in keys:
                keys.append(key)
        if len(keys) >= 8:
            break
    sample = " · ".join(keys) if keys else "키 입력"
    return f"{len(events)}개 이벤트 · {_macro_duration(events):.2f}초 · {sample}"


def _normalized_events(events: list) -> list:
    cleaned = []
    for ev in events:
        try:
            delay = max(0.0, float(ev.get("delay", 0)))
        except Exception:
            delay = 0.0
        kind = ev.get("type") if ev.get("type") in ("press", "release") else "press"
        key = str(ev.get("key", "")).strip()
        if key:
            cleaned.append({"type": kind, "key": key, "delay": delay})
    cleaned.sort(key=lambda item: item["delay"])
    return cleaned


# ── 녹화 컨트롤 다이얼로그 ─────────────────────────────────────────────────────
class RecordingDialog(tk.Toplevel):
    def __init__(self, parent, macro_name: str):
        super().__init__(parent)
        self.parent = parent
        self.title("녹화 중")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("420x250")
        self.protocol("WM_DELETE_WINDOW", self._stop)

        self.state_var = tk.StringVar(value="녹화 중")
        self.name_var = tk.StringVar(value=macro_name)
        self.elapsed_var = tk.StringVar(value="00:00.0")
        self.count_var = tk.StringVar(value="0")
        self.pause_var = tk.StringVar(value="일시정지")

        self._build_ui()
        self.transient(parent)
        self.attributes("-topmost", True)
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            w = self.winfo_width()
            self.geometry(f"+{px + (pw - w)//2}+{py + 80}")
        except Exception:
            pass
        self.refresh()

    def _build_ui(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=22, pady=(20, 12))
        state_row = tk.Frame(header, bg=BG)
        state_row.pack(fill="x")
        self.dot = tk.Label(state_row, text="●", bg=BG, fg=DANGER,
                            font=(FAM_TEXT, 13, "bold"))
        self.dot.pack(side="left", padx=(0, 8))
        tk.Label(state_row, textvariable=self.state_var, bg=BG, fg=TEXT,
                 font=(FAM_DISPLAY, 18, "bold")).pack(side="left")
        tk.Label(header, textvariable=self.name_var, bg=BG, fg=TEXT_MUTED,
                 font=F_SUB).pack(anchor="w", pady=(4, 0))

        stats = tk.Frame(self, bg=BG)
        stats.pack(fill="x", padx=22, pady=(4, 16))
        self._stat(stats, "시간", self.elapsed_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._stat(stats, "이벤트", self.count_var).pack(side="left", fill="x", expand=True, padx=(8, 0))

        actions = tk.Frame(self, bg=BG)
        actions.pack(fill="x", padx=22, pady=(4, 20), side="bottom")
        make_button(actions, "녹화 종료", command=self._stop,
                    kind="danger").pack(side="right")
        make_button(actions, "", command=self._toggle_pause,
                    kind="secondary", textvariable=self.pause_var).pack(side="right", padx=(0, 8))

        tk.Label(self, text="필요한 앱으로 이동해 키를 입력하세요. 종료하면 자동 저장됩니다.",
                 bg=BG, fg=TEXT_SUBTLE, font=F_SMALL).pack(anchor="w", padx=22)

    def _stat(self, parent, title: str, variable: tk.StringVar):
        box = tk.Frame(parent, bg=SURFACE,
                       highlightthickness=1,
                       highlightbackground=BORDER)
        tk.Label(box, text=title, bg=SURFACE, fg=TEXT_MUTED,
                 font=F_SMALL).pack(anchor="w", padx=12, pady=(9, 0))
        tk.Label(box, textvariable=variable, bg=SURFACE, fg=TEXT,
                 font=(FAM_DISPLAY, 18, "bold")).pack(anchor="w", padx=12, pady=(2, 10))
        return box

    def refresh(self):
        if not self.winfo_exists():
            return
        paused = self.parent._rec_paused
        self.state_var.set("일시정지 중" if paused else "녹화 중")
        self.pause_var.set("재개" if paused else "일시정지")
        self.dot.config(fg=WARN if paused else DANGER)
        elapsed = self.parent._record_elapsed()
        minutes = int(elapsed // 60)
        seconds = elapsed - minutes * 60
        self.elapsed_var.set(f"{minutes:02d}:{seconds:04.1f}")
        self.count_var.set(str(len(self.parent._rec_events)))
        if self.parent._rec_proc is not None:
            self.after(200, self.refresh)

    def _toggle_pause(self):
        self.parent._set_record_paused(not self.parent._rec_paused)

    def _stop(self):
        self.parent._stop_record()


# ── 매크로 입력 편집 다이얼로그 ────────────────────────────────────────────────
class MacroEditorDialog(tk.Toplevel):
    def __init__(self, parent, macro_name: str, events: list):
        super().__init__(parent)
        self.title("입력 편집")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.geometry("880x640")
        self.minsize(820, 590)
        self.result = None
        self.events = _normalized_events(copy.deepcopy(events))

        self._build_ui(macro_name)
        self._refresh()

        self.transient(parent)
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            self.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")
        except Exception:
            pass

    def _build_ui(self, macro_name: str):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=22, pady=(20, 12))
        tk.Label(header, text="입력 이벤트 편집", bg=BG, fg=TEXT,
                 font=F_DLG_TITLE).pack(anchor="w")
        tk.Label(header, text=f"'{macro_name}' 매크로의 키와 타이밍을 수정합니다",
                 bg=BG, fg=TEXT_MUTED, font=F_SUB).pack(anchor="w", pady=(2, 0))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=22)

        table_card = make_card(body)
        table_card.pack(side="left", fill="both", expand=True, padx=(0, 12))
        table_inner = tk.Frame(table_card, bg=BG, padx=2, pady=2)
        table_inner.pack(fill="both", expand=True)
        cols = ("idx", "type", "key", "delay", "gap")
        self.tree = ttk.Treeview(table_inner, columns=cols, show="headings",
                                 height=14, style="Modern.Treeview")
        for col, title, width, anchor in [
            ("idx", "#", 44, "center"),
            ("type", "동작", 78, "center"),
            ("key", "키", 180, "w"),
            ("delay", "시점", 90, "center"),
            ("gap", "간격", 90, "center"),
        ]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor=anchor)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._load_selected())
        self.tree.bind("<Double-1>", lambda e: self._load_selected())

        editor = make_card(body, width=250)
        editor.pack(side="right", fill="y")
        editor.pack_propagate(False)
        form = tk.Frame(editor, bg=BG, padx=14, pady=14)
        form.pack(fill="both", expand=True)
        tk.Label(form, text="선택 이벤트", bg=BG, fg=TEXT,
                 font=(FAM_TEXT, 13, "bold")).pack(anchor="w", pady=(0, 12))

        self.type_var = tk.StringVar(value="press")
        self.key_var = tk.StringVar(value="")
        self.delay_ms_var = tk.StringVar(value="0")
        self.bulk_gap_ms_var = tk.StringVar(value="50")

        self._form_label(form, "동작")
        type_row = tk.Frame(form, bg=BG)
        type_row.pack(fill="x", pady=(0, 12))
        tk.Radiobutton(type_row, text="누름", value="press",
                       variable=self.type_var, bg=BG, fg=TEXT,
                       selectcolor=SURFACE, activebackground=BG,
                       activeforeground=TEXT).pack(side="left")
        tk.Radiobutton(type_row, text="뗌", value="release",
                       variable=self.type_var, bg=BG, fg=TEXT,
                       selectcolor=SURFACE, activebackground=BG,
                       activeforeground=TEXT).pack(side="left", padx=(10, 0))

        self._form_label(form, "키")
        tk.Entry(form, textvariable=self.key_var, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 font=F_BODY, width=18).pack(fill="x", ipady=7, pady=(0, 12))

        self._form_label(form, "시점(ms)")
        tk.Entry(form, textvariable=self.delay_ms_var, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 font=F_BODY, width=18).pack(fill="x", ipady=7, pady=(0, 14))

        make_button(form, "변경 적용", command=self._apply_selected,
                    kind="primary").pack(fill="x", pady=(0, 8))
        make_button(form, "행 추가", command=self._add_event,
                    kind="secondary").pack(fill="x", pady=(0, 8))
        make_button(form, "선택 삭제", command=self._delete_event,
                    kind="danger_o").pack(fill="x", pady=(0, 14))

        move_row = tk.Frame(form, bg=BG)
        move_row.pack(fill="x", pady=(0, 16))
        make_button(move_row, "위로", command=lambda: self._move_event(-1),
                    kind="secondary").pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=2)
        make_button(move_row, "아래로", command=lambda: self._move_event(1),
                    kind="secondary").pack(side="left", fill="x", expand=True, padx=(5, 0), ipady=2)

        bulk = tk.Frame(form, bg=SURFACE,
                        highlightthickness=1,
                        highlightbackground=BORDER)
        bulk.pack(fill="x", pady=(0, 14))
        bulk_inner = tk.Frame(bulk, bg=SURFACE, padx=10, pady=10)
        bulk_inner.pack(fill="x")
        tk.Label(bulk_inner, text="딜레이 일괄 변경", bg=SURFACE, fg=TEXT,
                 font=(FAM_TEXT, 11, "bold")).pack(anchor="w")
        tk.Label(bulk_inner, text="모든 이벤트 간격을 같은 값으로 정렬",
                 bg=SURFACE, fg=TEXT_MUTED, font=F_SMALL).pack(anchor="w", pady=(2, 8))
        gap_row = tk.Frame(bulk_inner, bg=SURFACE)
        gap_row.pack(fill="x")
        tk.Entry(gap_row, textvariable=self.bulk_gap_ms_var, bg=BG, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 font=F_BODY, width=8).pack(side="left", ipady=6)
        tk.Label(gap_row, text="ms", bg=SURFACE, fg=TEXT_MUTED,
                 font=F_SMALL).pack(side="left", padx=(6, 0))
        make_button(bulk_inner, "일괄 적용", command=self._apply_bulk_gap,
                    kind="primary").pack(fill="x", pady=(10, 0))

        tk.Label(form, text="키 예: a, 1, Key.enter, Key.space",
                 bg=BG, fg=TEXT_SUBTLE, font=F_SMALL,
                 wraplength=215, justify="left").pack(anchor="w")

        footer = tk.Frame(self, bg=BG)
        footer.pack(fill="x", padx=22, pady=(14, 18))
        self.summary_var = tk.StringVar(value="")
        tk.Label(footer, textvariable=self.summary_var, bg=BG,
                 fg=TEXT_MUTED, font=F_SMALL).pack(side="left")
        make_button(footer, "저장", command=self._save,
                    kind="primary").pack(side="right")
        make_button(footer, "취소", command=self.destroy,
                    kind="ghost").pack(side="right", padx=(0, 8))

    def _form_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG, fg=TEXT_MUTED,
                 font=F_SMALL).pack(anchor="w", pady=(0, 4))

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def _refresh(self, keep_index=None):
        self.events = _normalized_events(self.events)
        self.tree.delete(*self.tree.get_children())
        for idx, ev in enumerate(self.events):
            prev = self.events[idx - 1]["delay"] if idx > 0 else 0
            gap = max(0, ev["delay"] - prev)
            self.tree.insert("", "end", iid=str(idx),
                             values=(idx + 1, _event_type_label(ev["type"]),
                                     _display_key(ev["key"]),
                                     f"{ev['delay'] * 1000:.0f}ms",
                                     f"{gap * 1000:.0f}ms"))
        self.summary_var.set(
            f"{len(self.events)}개 이벤트 · 총 {_macro_duration(self.events):.2f}초")
        if self.events:
            idx = keep_index if keep_index is not None else 0
            idx = max(0, min(idx, len(self.events) - 1))
            self.tree.selection_set(str(idx))
            self.tree.see(str(idx))
            self._load_selected()
        else:
            self.key_var.set("")
            self.delay_ms_var.set("0")

    def _load_selected(self):
        idx = self._selected_index()
        if idx is None or idx >= len(self.events):
            return
        ev = self.events[idx]
        self.type_var.set(ev["type"])
        self.key_var.set(ev["key"])
        self.delay_ms_var.set(f"{ev['delay'] * 1000:.0f}")

    def _read_form_event(self):
        key = self.key_var.get().strip()
        if not key:
            messagebox.showinfo("입력 필요", "키 값을 입력하세요.", parent=self)
            return None
        try:
            delay_ms = max(0.0, float(self.delay_ms_var.get()))
        except Exception:
            messagebox.showinfo("입력 오류", "시점은 ms 숫자로 입력하세요.", parent=self)
            return None
        return {
            "type": self.type_var.get(),
            "key": key,
            "delay": delay_ms / 1000.0,
        }

    def _apply_selected(self):
        idx = self._selected_index()
        if idx is None:
            return
        ev = self._read_form_event()
        if ev is None:
            return
        self.events[idx] = ev
        self._refresh(idx)

    def _add_event(self):
        ev = self._read_form_event()
        if ev is None:
            return
        self.events.append(ev)
        self._refresh(len(self.events) - 1)

    def _delete_event(self):
        idx = self._selected_index()
        if idx is None:
            return
        self.events.pop(idx)
        self._refresh(max(0, idx - 1))

    def _move_event(self, direction: int):
        idx = self._selected_index()
        if idx is None:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.events):
            return
        self.events[idx]["delay"], self.events[new_idx]["delay"] = (
            self.events[new_idx]["delay"], self.events[idx]["delay"])
        self.events[idx], self.events[new_idx] = self.events[new_idx], self.events[idx]
        self._refresh(new_idx)

    def _apply_bulk_gap(self):
        if not self.events:
            return
        try:
            gap_ms = max(0.0, float(self.bulk_gap_ms_var.get()))
        except Exception:
            messagebox.showinfo("입력 오류", "일괄 딜레이는 ms 숫자로 입력하세요.", parent=self)
            return
        gap = gap_ms / 1000.0
        for idx, ev in enumerate(self.events):
            ev["delay"] = idx * gap
        self._refresh(self._selected_index() or 0)

    def _save(self):
        self.result = _normalized_events(self.events)
        self.destroy()


# ── 단축키 입력 다이얼로그 ────────────────────────────────────────────────────
class ShortcutDialog(tk.Toplevel):
    def __init__(self, parent, macro_name: str, existing: str = ""):
        super().__init__(parent)
        self.title("단축키 설정")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("460x380")

        self.result = None
        self._captured: str | None = None
        self._last_combo: str | None = None
        self._proc: subprocess.Popen | None = None
        self._pressed: dict = {}
        self._locked = False

        self._build_ui(macro_name, existing)
        self._start_record_listener()

        self.transient(parent)
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())

        # 위치 가운데 정렬
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            self.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")
        except Exception:
            pass

    def _build_ui(self, macro_name: str, existing: str):
        # 헤더
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=24, pady=(20, 4))
        tk.Label(header, text="단축키 설정", bg=BG,
                 fg=TEXT, font=F_DLG_TITLE).pack(anchor="w")
        tk.Label(header, text=f"'{macro_name}' 매크로에 단축키를 연결합니다",
                 bg=BG, fg=TEXT_MUTED, font=F_SUB).pack(anchor="w", pady=(2, 0))

        # 캡처 영역 (큰 카드)
        capture_card = tk.Frame(self, bg=SURFACE,
                                highlightthickness=1,
                                highlightbackground=BORDER)
        capture_card.pack(fill="x", padx=24, pady=(16, 10))

        self._badge_area = tk.Frame(capture_card, bg=SURFACE,
                                    height=80)
        self._badge_area.pack(fill="x", padx=20, pady=(20, 8))
        self._badge_area.pack_propagate(False)

        self._hint_var = tk.StringVar()
        self._hint_label = tk.Label(capture_card, textvariable=self._hint_var,
                                     bg=SURFACE, fg=TEXT_MUTED,
                                     font=F_SMALL)
        self._hint_label.pack(pady=(0, 16))

        # 안내 문구
        tip = tk.Frame(self, bg=BG)
        tip.pack(fill="x", padx=24, pady=(0, 4))
        tk.Label(tip, text="원하는 키 조합을 동시에 누르세요",
                 bg=BG, fg=TEXT, font=(FAM_TEXT, 11, "bold")
                 ).pack(anchor="w")
        tk.Label(tip,
                 text="키를 떼면 자동으로 인식됩니다 · macOS의 다른 단축키와 충돌하지 않게 주의",
                 bg=BG, fg=TEXT_MUTED, font=F_SMALL).pack(anchor="w", pady=(2, 0))

        # 기존 단축키 표시
        if existing:
            existing_row = tk.Frame(self, bg=BG)
            existing_row.pack(fill="x", padx=24, pady=(8, 0))
            tk.Label(existing_row, text="현재 설정:",
                     bg=BG, fg=TEXT_MUTED, font=F_SMALL
                     ).pack(side="left")
            tk.Label(existing_row, text=_format_combo(existing),
                     bg=BG, fg=TEXT, font=(FAM_MONO, 11, "bold")
                     ).pack(side="left", padx=(6, 0))

        # 버튼 행
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill="x", padx=24, pady=(16, 18), side="bottom")

        if existing:
            make_button(bf, "단축키 제거",
                        command=self._remove,
                        kind="danger_o").pack(side="left")

        self._save_btn = make_button(bf, "저장",
                                     command=self._confirm,
                                     kind="primary")
        self._save_btn.pack(side="right")
        self._save_btn.config(state="disabled")

        make_button(bf, "취소", command=self.destroy,
                    kind="ghost").pack(side="right", padx=(0, 8))

        self._reset_btn = make_button(bf, "다시 입력",
                                      command=self._reset_capture,
                                      kind="secondary")
        # 처음에는 숨김; 캡처되면 노출
        self._reset_visible = False

        self._render_badges(None, "키를 누르면 여기에 표시됩니다")

    # ── 캡처 ─────────────────────────────────────────────────────────────
    def _start_record_listener(self):
        try:
            self._proc = _spawn("record")
            self._proc.stdout.readline()  # READY
            threading.Thread(target=self._read_loop, daemon=True).start()
            self._set_hint("● 입력 대기 중", DANGER)
        except Exception:
            self._render_badges(None, "캡처 불가 — 권한을 확인하세요")
            self._set_hint("권한 오류", DANGER)

    def _read_loop(self):
        for line in self._proc.stdout:
            line = line.strip()
            try:
                ev = json.loads(line)
            except Exception:
                continue
            self.after(0, lambda e=ev: self._handle_event(e))

    def _handle_event(self, ev: dict):
        if self._locked:
            return
        key = ev["key"]
        if ev["type"] == "press":
            self._pressed[key] = True
            combo = _combo_label(list(self._pressed.keys())).replace(" ", "")
            self._last_combo = combo
            self._render_badges(combo, "키를 떼면 인식됩니다")
            self._set_hint("● 입력 중", DANGER)
        else:
            self._pressed.pop(key, None)
            if not self._pressed and self._last_combo:
                self._lock_combo(self._last_combo)

    def _lock_combo(self, combo: str):
        self._captured = combo
        self._locked = True
        self._render_badges(combo, "")
        self._set_hint("✓ 인식 완료 · 저장을 눌러 적용하세요", SUCCESS)
        self._save_btn.config(state="normal")
        if not self._reset_visible:
            self._reset_btn.pack(side="right", padx=(0, 8),
                                 before=self._save_btn)
            self._reset_visible = True

    def _reset_capture(self):
        self._captured = None
        self._last_combo = None
        self._pressed = {}
        self._locked = False
        self._save_btn.config(state="disabled")
        if self._reset_visible:
            self._reset_btn.pack_forget()
            self._reset_visible = False
        self._render_badges(None, "키를 누르면 여기에 표시됩니다")
        self._set_hint("● 입력 대기 중", DANGER)

    # ── 렌더 ─────────────────────────────────────────────────────────────
    def _render_badges(self, combo: str | None, placeholder: str):
        for w in self._badge_area.winfo_children():
            w.destroy()

        if not combo:
            tk.Label(self._badge_area, text=placeholder,
                     bg=SURFACE, fg=TEXT_SUBTLE, font=F_BODY
                     ).pack(expand=True)
            return

        inner = tk.Frame(self._badge_area, bg=SURFACE)
        inner.pack(expand=True)

        parts = combo.split("+")
        for i, p in enumerate(parts):
            if i > 0:
                tk.Label(inner, text="+", bg=SURFACE, fg=TEXT_SUBTLE,
                         font=(FAM_DISPLAY, 16, "bold")
                         ).pack(side="left", padx=8)
            self._make_kbd_badge(inner, _key_symbol(p)).pack(side="left")

    def _make_kbd_badge(self, parent, label: str):
        outer = tk.Frame(parent, bg=KEYCAP_BG,
                         highlightthickness=1,
                         highlightbackground=KEYCAP_BORDER)
        font = F_KEY if len(label) <= 2 else F_KEY_SM
        tk.Label(outer, text=label, bg=KEYCAP_BG, fg=TEXT,
                 font=font, padx=14, pady=6).pack()
        return outer

    def _set_hint(self, text: str, color: str):
        self._hint_var.set(text)
        self._hint_label.config(fg=color)

    # ── 종료 ─────────────────────────────────────────────────────────────
    def _confirm(self):
        if self._captured:
            self.result = self._captured
        self.destroy()

    def _remove(self):
        self.result = ""
        self.destroy()

    def destroy(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1)
            except Exception:
                pass
        super().destroy()


def _combo_label(keys: list) -> str:
    modmap = {"Key.cmd": "cmd", "Key.cmd_l": "cmd", "Key.cmd_r": "cmd",
              "Key.ctrl": "ctrl", "Key.ctrl_l": "ctrl", "Key.ctrl_r": "ctrl",
              "Key.alt": "alt", "Key.alt_l": "alt", "Key.alt_r": "alt",
              "Key.shift": "shift", "Key.shift_l": "shift", "Key.shift_r": "shift"}
    order = {"cmd": 0, "ctrl": 1, "alt": 2, "shift": 3}
    parts = []
    for k in keys:
        if k in modmap:
            parts.append(modmap[k])
        elif k and len(k) == 1:
            parts.append(k)
        else:
            parts.append(k.replace("Key.", ""))
    parts = list(dict.fromkeys(parts))
    parts.sort(key=lambda x: (order.get(x, 99), x))
    return "+".join(parts)


import json as _json_module
json = _json_module

if __name__ == "__main__":
    app = App()
    app.mainloop()
