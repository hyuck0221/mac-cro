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
import ctypes

mode = sys.argv[1] if len(sys.argv) > 1 else ""


def accessibility_trusted() -> bool:
    try:
        app_services = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/"
            "ApplicationServices"
        )
        app_services.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(app_services.AXIsProcessTrusted())
    except Exception:
        return False


def prompt_accessibility() -> bool:
    return accessibility_trusted()

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

# ── 재생 모드 ─────────────────────────────────────────────────────────────────
elif mode == "play":
    # argv: play <events.json path> <fixed_ms>
    path = sys.argv[2] if len(sys.argv) > 2 else ""
    try:
        fixed_ms = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    except ValueError:
        fixed_ms = 0.0

    if not path:
        print("ERROR:no path", flush=True)
        sys.exit(1)

    try:
        with open(path) as f:
            events = json.load(f)
    except Exception as e:
        print(f"ERROR:read {e}", flush=True)
        sys.exit(1)

    if not accessibility_trusted():
        print("ERROR:accessibility", flush=True)
        sys.exit(1)

    try:
        from pynput.keyboard import Key, Controller
        kb = Controller()
    except Exception as e:
        print(f"ERROR:controller {e}", flush=True)
        sys.exit(1)

    def parse_key(raw):
        if raw.startswith("Key."):
            return getattr(Key, raw[4:], raw)
        return raw[0] if len(raw) == 1 else raw

    print("READY", flush=True)

    fixed = fixed_ms / 1000.0
    prev = 0.0
    sent = 0
    for i, ev in enumerate(events):
        if i > 0:
            wait = fixed if fixed > 0 else (ev["delay"] - prev)
            if wait > 0:
                time.sleep(wait)
        prev = ev["delay"]
        try:
            key = parse_key(ev["key"])
            if ev["type"] == "press":
                kb.press(key)
            else:
                kb.release(key)
            sent += 1
        except Exception as e:
            print(f"WARN:{e}", flush=True)
    print(f"DONE:{sent}", flush=True)

# ── 재생 권한 테스트 모드 ─────────────────────────────────────────────────────
elif mode == "accessibility":
    print("OK" if accessibility_trusted() else "FAIL", flush=True)

elif mode == "prompt_accessibility":
    print("OK" if prompt_accessibility() else "FAIL", flush=True)

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
