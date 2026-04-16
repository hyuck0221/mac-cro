#!/usr/bin/env python3
"""
subprocess 워커 - pynput 직접 사용 (권한 없으면 이 프로세스만 죽음)
사용법:
  python worker.py record
  python worker.py hotkey <combo>   # combo 예: <cmd>+<shift>+a
"""
import sys
import json
import time

mode = sys.argv[1] if len(sys.argv) > 1 else ""

# ── 녹화 모드 ─────────────────────────────────────────────────────────────────
if mode == "record":
    from pynput import keyboard

    start = time.time()

    def on_press(key):
        delay = time.time() - start
        try:
            ev = {"type": "press", "key": key.char, "delay": delay}
        except AttributeError:
            ev = {"type": "press", "key": str(key), "delay": delay}
        print(json.dumps(ev), flush=True)

    def on_release(key):
        delay = time.time() - start
        try:
            ev = {"type": "release", "key": key.char, "delay": delay}
        except AttributeError:
            ev = {"type": "release", "key": str(key), "delay": delay}
        print(json.dumps(ev), flush=True)

    try:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as lst:
            print("READY", flush=True)
            lst.join()
    except Exception as e:
        print(f"ERROR:{e}", flush=True)

# ── 단축키 감시 모드 ──────────────────────────────────────────────────────────
elif mode == "hotkey":
    combo = sys.argv[2] if len(sys.argv) > 2 else ""
    if not combo:
        sys.exit(1)

    from pynput import keyboard

    def on_activate():
        print("HIT", flush=True)

    try:
        with keyboard.GlobalHotKeys({combo: on_activate}) as h:
            print("READY", flush=True)
            h.join()
    except Exception as e:
        print(f"ERROR:{e}", flush=True)

# ── 권한 테스트 모드 ──────────────────────────────────────────────────────────
elif mode == "test":
    from pynput import keyboard
    import time

    try:
        l = keyboard.Listener(on_press=lambda k: None, on_release=lambda k: None)
        l.start()
        time.sleep(0.3)
        l.stop()
        print("OK", flush=True)
    except Exception:
        print("FAIL", flush=True)
