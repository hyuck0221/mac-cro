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

SAVE_FILE = os.path.expanduser("~/.mac_macros.json")
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker.py")
PYTHON = sys.executable   # 현재 실행 중인 Python (의존성 있는 것)

# ── subprocess 헬퍼 ──────────────────────────────────────────────────────────
def _spawn(*args) -> subprocess.Popen:
    return subprocess.Popen(
        [PYTHON, WORKER] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )

def _check_permission() -> bool:
    """별도 프로세스에서 권한 테스트. 크래시해도 메인 프로세스 안전."""
    try:
        proc = _spawn("test")
        line = proc.stdout.readline()
        proc.terminate()
        proc.wait(timeout=1)
        return "OK" in line
    except Exception:
        return False

def _open_perm_settings():
    subprocess.Popen([
        "open",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
    ])

# ── 재생 (pynput Controller는 권한 별개라 직접 사용 가능) ─────────────────────
from pynput.keyboard import Key, Controller as KbController
_kb = KbController()

def _parse_key(raw: str):
    if raw.startswith("Key."):
        return getattr(Key, raw[4:], raw)
    return raw[0] if len(raw) == 1 else raw

def _play_events(events: list, fixed_delay_ms: float = 0):
    """fixed_delay_ms > 0 이면 이벤트 사이 간격을 해당 ms로 고정."""
    fixed = fixed_delay_ms / 1000.0
    prev = 0.0
    for i, ev in enumerate(events):
        if i > 0:
            wait = fixed if fixed > 0 else (ev["delay"] - prev)
            if wait > 0:
                time.sleep(wait)
        prev = ev["delay"]
        try:
            key = _parse_key(ev["key"])
            (_kb.press if ev["type"] == "press" else _kb.release)(key)
        except Exception:
            pass

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
        self.resizable(False, False)
        self.store = MacroStore()
        self._rec_proc: subprocess.Popen | None = None
        self._rec_thread: threading.Thread | None = None
        self._rec_events: list = []
        self._rec_name: str = ""
        self._hotkey_procs: dict = {}   # name -> Popen
        self._playing: set = set()
        self._perm_ok: bool | None = None   # None=미확인

        self._build_ui()
        self._refresh_list()
        self.after(200, self._async_check_perm)

    # ── 권한 확인 (별도 스레드) ───────────────────────────────────────────
    def _async_check_perm(self):
        self.status_var.set("권한 확인 중...")
        self.update()

        def check():
            ok = _check_permission()
            self.after(0, lambda: self._on_perm_result(ok))

        threading.Thread(target=check, daemon=True).start()

    def _on_perm_result(self, ok: bool):
        self._perm_ok = ok
        if ok:
            self.status_var.set("준비 완료  (더블클릭으로 매크로 재생)")
            self._start_hotkey_watchers()
        else:
            self.status_var.set("⚠ Input Monitoring 권한 필요")
            self.perm_btn.pack(side="left", padx=(0, 6))

    # ── 레이아웃 ──────────────────────────────────────────────────────────
    def _build_ui(self):
        top = tk.Frame(self, padx=12, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="Mac Macro Recorder",
                 font=("SF Pro Display", 18, "bold")).pack(anchor="w")
        tk.Label(top, text="키보드 매크로를 기록하고 단축키로 실행하세요",
                 fg="#666", font=("SF Pro Text", 11)).pack(anchor="w")

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        lf = tk.Frame(self, padx=12, pady=8)
        lf.pack(fill="both", expand=True)
        cols = ("name", "keys", "shortcut")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings", height=8)
        self.tree.heading("name", text="매크로 이름")
        self.tree.heading("keys", text="키 수")
        self.tree.heading("shortcut", text="단축키")
        self.tree.column("name", width=160)
        self.tree.column("keys", width=80, anchor="center")
        self.tree.column("shortcut", width=180, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._play_selected())

        ttk.Separator(self, orient="horizontal").pack(fill="x")
        bf = tk.Frame(self, padx=12, pady=8)
        bf.pack(fill="x")

        self.rec_btn = tk.Button(
            bf, text="● 녹화 시작", bg="#e74c3c", fg="white",
            font=("SF Pro Text", 12, "bold"), relief="flat",
            padx=10, pady=6, command=self._toggle_record)
        self.rec_btn.pack(side="left", padx=(0, 6))

        tk.Button(bf, text="▶ 재생", font=("SF Pro Text", 12),
                  relief="flat", padx=10, pady=6,
                  command=self._play_selected).pack(side="left", padx=(0, 6))

        tk.Button(bf, text="단축키 설정", font=("SF Pro Text", 12),
                  relief="flat", padx=10, pady=6,
                  command=self._set_shortcut).pack(side="left", padx=(0, 6))

        tk.Button(bf, text="삭제", font=("SF Pro Text", 12),
                  relief="flat", padx=10, pady=6,
                  command=self._delete_selected).pack(side="right")

        # 권한 버튼 (초기 숨김)
        self.perm_btn = tk.Button(
            bf, text="권한 설정 열기", bg="#f39c12", fg="white",
            font=("SF Pro Text", 11), relief="flat",
            padx=8, pady=6, command=self._guide_permission)

        # ── 딜레이 설정 행 ──────────────────────────────────────────────
        ttk.Separator(self, orient="horizontal").pack(fill="x")
        delay_row = tk.Frame(self, padx=12, pady=6)
        delay_row.pack(fill="x")

        tk.Label(delay_row, text="재생 딜레이:",
                 font=("SF Pro Text", 11)).pack(side="left")

        self.delay_var = tk.StringVar(value="0")
        delay_spin = tk.Spinbox(
            delay_row, from_=0, to=9999, increment=10,
            textvariable=self.delay_var, width=6,
            font=("SF Pro Text", 11))
        delay_spin.pack(side="left", padx=(6, 2))

        tk.Label(delay_row, text="ms  (0 = 원본 그대로)",
                 fg="#666", font=("SF Pro Text", 10)).pack(side="left")

        self.status_var = tk.StringVar(value="시작 중...")
        tk.Label(self, textvariable=self.status_var, fg="#555",
                 font=("SF Pro Text", 10), anchor="w",
                 padx=12, pady=4).pack(fill="x")

    def _guide_permission(self):
        messagebox.showinfo(
            "Input Monitoring 권한 설정",
            "1. 지금 열리는 시스템 설정에서\n"
            "   개인정보 보호 > 입력 모니터링 을 여세요\n\n"
            "2. 자물쇠를 클릭해 잠금 해제\n\n"
            "3. 목록에서 Terminal 또는 Python을 체크\n\n"
            "4. 앱을 완전히 종료 후 다시 실행하세요",
            parent=self
        )
        _open_perm_settings()

    # ── 리스트 ────────────────────────────────────────────────────────────
    def _refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        for name in self.store.macro_names():
            events = self.store.get_events(name)
            sc = self.store.get_shortcut(name) or "없음"
            self.tree.insert("", "end", iid=name,
                             values=(name, len(events), sc))

    def _selected_name(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    # ── 녹화 ─────────────────────────────────────────────────────────────
    def _toggle_record(self):
        if self._rec_proc is None:
            # 권한 확인
            if self._perm_ok is False:
                self._guide_permission()
                return
            if self._perm_ok is None:
                messagebox.showinfo("잠시만요", "권한 확인 중입니다. 잠시 후 다시 시도하세요.")
                return

            name = simpledialog.askstring(
                "매크로 이름", "저장할 매크로 이름을 입력하세요:", parent=self)
            if not name:
                return

            self._rec_name = name
            self._rec_events = []

            try:
                self._rec_proc = _spawn("record")
                # READY 줄 확인 (타임아웃 3초)
                self._rec_proc.stdout.readline()   # blocks briefly
            except Exception as e:
                self._rec_proc = None
                self.status_var.set(f"녹화 시작 실패: {e}")
                return

            # 백그라운드에서 이벤트 읽기
            self._rec_thread = threading.Thread(
                target=self._read_record_events, daemon=True)
            self._rec_thread.start()

            self.rec_btn.config(text="■ 녹화 중단", bg="#c0392b")
            self.rec_btn.unbind("<space>")
            self.rec_btn.unbind("<Return>")
            self.rec_btn.bind("<space>", lambda e: "break")
            self.rec_btn.bind("<Return>", lambda e: "break")
            self.status_var.set(f"녹화 중: {name}  (다른 앱에서 키를 누르세요)")
        else:
            self._stop_record()

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
                self._rec_events.append(ev)
            except Exception:
                pass

    def _stop_record(self):
        if self._rec_proc:
            try:
                self._rec_proc.terminate()
                self._rec_proc.wait(timeout=2)
            except Exception:
                pass
            self._rec_proc = None

        self.rec_btn.config(text="● 녹화 시작", bg="#e74c3c")
        self.rec_btn.unbind("<space>")
        self.rec_btn.unbind("<Return>")
        events = list(self._rec_events)

        if events:
            self.store.set_events(self._rec_name, events)
            self.store.save()
            self.status_var.set(
                f"저장 완료: {self._rec_name} ({len(events)}개 이벤트)")
        else:
            self.status_var.set("녹화된 키가 없습니다.")
        self._refresh_list()

    # ── 재생 ─────────────────────────────────────────────────────────────
    def _play_selected(self):
        name = self._selected_name()
        if not name:
            messagebox.showinfo("알림", "재생할 매크로를 선택하세요.")
            return
        self._play(name)

    def _play(self, name: str):
        if name in self._playing:
            return
        events = self.store.get_events(name)
        if not events:
            return
        try:
            fixed_ms = float(self.delay_var.get())
        except Exception:
            fixed_ms = 0
        self._playing.add(name)
        self.status_var.set(f"재생 중: {name}")

        def run():
            _play_events(events, fixed_delay_ms=fixed_ms)
            self._playing.discard(name)
            self.after(0, lambda: self.status_var.set(f"재생 완료: {name}"))

        threading.Thread(target=run, daemon=True).start()

    # ── 단축키 설정 ───────────────────────────────────────────────────────
    def _set_shortcut(self):
        name = self._selected_name()
        if not name:
            messagebox.showinfo("알림", "단축키를 설정할 매크로를 선택하세요.")
            return
        if not self._perm_ok:
            self._guide_permission()
            return

        dlg = ShortcutDialog(self, name)
        self.wait_window(dlg)
        if dlg.result is not None:
            self.store.set_shortcut(name, dlg.result)
            self.store.save()
            self._refresh_list()
            self._start_hotkey_watchers()
            msg = f"{name} 단축키: {dlg.result}" if dlg.result else f"{name} 단축키 제거됨"
            self.status_var.set(msg)

    # ── 삭제 ─────────────────────────────────────────────────────────────
    def _delete_selected(self):
        name = self._selected_name()
        if not name:
            return
        if messagebox.askyesno("삭제 확인", f"'{name}' 매크로를 삭제할까요?"):
            self.store.delete(name)
            self.store.save()
            self._refresh_list()
            self._start_hotkey_watchers()

    # ── 전역 단축키 감시 (각 단축키마다 subprocess) ───────────────────────
    def _start_hotkey_watchers(self):
        # 기존 프로세스 종료
        for proc in list(self._hotkey_procs.values()):
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                pass
        self._hotkey_procs = {}

        if not self._perm_ok:
            return

        for name in self.store.macro_names():
            sc = self.store.get_shortcut(name)
            if not sc:
                continue
            try:
                combo = _to_pynput_combo(sc)
                proc = _spawn("hotkey", combo)
                # READY 줄 읽기 (별도 스레드)
                def watch(p, n):
                    line = p.stdout.readline()  # READY
                    if "READY" not in line:
                        return
                    for hit in p.stdout:
                        if "HIT" in hit:
                            self.after(0, lambda n=n: self._play(n))
                threading.Thread(target=watch, args=(proc, name), daemon=True).start()
                self._hotkey_procs[name] = proc
            except Exception:
                pass


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


# ── 단축키 입력 다이얼로그 ────────────────────────────────────────────────────
class ShortcutDialog(tk.Toplevel):
    def __init__(self, parent, macro_name: str):
        super().__init__(parent)
        self.title("단축키 설정")
        self.resizable(False, False)
        self.result = None
        self._display = tk.StringVar(value="키를 눌러주세요...")
        self._captured: str | None = None
        self._proc: subprocess.Popen | None = None

        tk.Label(self, text=f"'{macro_name}' 단축키",
                 font=("SF Pro Text", 13, "bold"), padx=20, pady=10).pack()
        tk.Label(self, text="원하는 키 조합을 누르세요 (예: cmd+shift+1)",
                 fg="#555", font=("SF Pro Text", 11), padx=20).pack()
        tk.Label(self, textvariable=self._display, bg="#f0f0f0",
                 font=("SF Pro Mono", 14, "bold"),
                 padx=20, pady=12, relief="flat", width=22).pack(padx=20, pady=10)

        bf = tk.Frame(self, padx=20, pady=10)
        bf.pack(fill="x")
        tk.Button(bf, text="확인", width=8, command=self._confirm).pack(side="left", padx=4)
        tk.Button(bf, text="취소", width=8, command=self.destroy).pack(side="left", padx=4)
        tk.Button(bf, text="단축키 제거", command=self._remove).pack(side="right", padx=4)

        self._start_record_listener()
        self.grab_set()

    def _start_record_listener(self):
        """임시 record subprocess로 키 조합을 캡처."""
        try:
            self._proc = _spawn("record")
            self._proc.stdout.readline()   # READY

            def read():
                pressed = {}
                for line in self._proc.stdout:
                    line = line.strip()
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    key = ev["key"]
                    if ev["type"] == "press":
                        pressed[key] = True
                    else:
                        pressed.pop(key, None)
                    if pressed:
                        label = _combo_label(list(pressed.keys()))
                        self._captured = label.replace(" ", "")
                        self._display.set(label)

            threading.Thread(target=read, daemon=True).start()
        except Exception:
            self._display.set("캡처 불가")

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
    parts = list(dict.fromkeys(parts))  # 중복 제거
    parts.sort(key=lambda x: (order.get(x, 99), x))
    return "+".join(parts)


import json as _json_module
json = _json_module

if __name__ == "__main__":
    app = App()
    app.mainloop()
