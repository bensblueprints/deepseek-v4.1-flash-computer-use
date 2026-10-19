#!/usr/bin/env python3
"""
cua.py - a small, scriptable wrapper around the CUA driver (trycua/cua).

Why this exists: the driver ships a great CLI, but a few things are easy to get
wrong. This wrapper encodes the working patterns:

  * window-targeted moves/clicks must OMIT `scope` and pass `target`
  * Chromium/Electron drops background input -> type_text needs delivery_mode=foreground
  * element_token snapshots do not survive across CLI processes -> prefer pixels
  * the agent cursor fades after 15s -> set idle_hide_ms=0 for recording

Usage:
  cua.py status
  cua.py shot [--out path.png]
  cua.py windows
  cua.py move 900 500 --window 1234:5678
  cua.py move 900 500 --desktop
  cua.py click 900 500 --desktop
  cua.py type "hello" --pid 1234 --wid 5678
  cua.py key Tab --pid 1234 --wid 5678
  cua.py record start --out take.mkv
  cua.py record stop
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time

CANDIDATES = [
    # Windows
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Cua\cua-driver\bin\cua-driver.exe"),
    os.path.expanduser(r"~/.cua-driver/packages/current/cua-driver.exe"),
    # Linux / macOS
    os.path.expanduser("~/.local/bin/cua-driver"),
    "/usr/local/bin/cua-driver",
    "/opt/homebrew/bin/cua-driver",
    shutil.which("cua-driver"),
]


def driver() -> str:
    for path in CANDIDATES:
        if path and os.path.exists(path):
            return path
    raise SystemExit(
        "cua-driver not found. Install it first:\n"
        "  powershell -c \"irm https://cua.ai/driver/install.ps1 | iex\"\n"
        "  cua-driver serve"
    )


def call(tool: str, payload: dict | None = None) -> dict:
    """Invoke one driver tool and return its JSON response."""
    proc = subprocess.run(
        [driver(), "call", tool, json.dumps(payload or {})],
        capture_output=True,
        text=True,
    )
    raw = proc.stdout.strip()
    if not raw:
        raise SystemExit(f"{tool} failed: {proc.stderr.strip()}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit(f"{tool} returned non-JSON: {raw[:400]}")
    if isinstance(data, dict) and data.get("code"):
        raise SystemExit(f"{tool} refused: {data['code']} — {data.get('reason', '')}")
    return data


def ensure_daemon() -> None:
    status = subprocess.run([driver(), "status"], capture_output=True, text=True).stdout
    if "not running" in status.lower():
        subprocess.Popen(
            [driver(), "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x00000008 if os.name == "nt" else 0,  # DETACHED_PROCESS
        )
        time.sleep(3)


def shot(out: str = "screen.png") -> str:
    """Capture the desktop and write a real PNG. Returns the path."""
    data = call("get_desktop_state")
    with open(out, "wb") as fh:
        fh.write(base64.b64decode(data["screenshot_png_b64"]))
    return out


def window_target(args) -> dict | None:
    if getattr(args, "window", None):
        pid, wid = args.window.split(":")
        return {"kind": "window", "pid": int(pid), "window_id": int(wid)}
    if getattr(args, "desktop", False):
        return {"kind": "desktop", "display_id": "primary"}
    return None


def capture_cmd(out: str, fps: int) -> list[str]:
    """Pick a recorder that keeps the cursor visible on this platform.

    Windows : ddagrab (DXGI) - captures the agent cursor overlay
    Wayland : wf-recorder when available (wlroots compositors)
    X11     : ffmpeg x11grab
    """
    if sys.platform == "win32":
        return [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"ddagrab=output_idx=0:framerate={fps}",
            "-vf", "hwdownload,format=bgra",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
            "-pix_fmt", "yuv420p", out,
        ]

    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wf-recorder"):
        return ["wf-recorder", "-f", out, "-r", str(fps)]

    display = os.environ.get("DISPLAY", ":0")
    size = os.environ.get("CUA_CAPTURE_SIZE", "1920x1080")
    return [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "x11grab", "-framerate", str(fps), "-video_size", size, "-i", display,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
        "-pix_fmt", "yuv420p", out,
    ]


def stop_process(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        import signal
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Scripted computer use via the CUA driver")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    p = sub.add_parser("shot"); p.add_argument("--out", default="screen.png")
    sub.add_parser("windows")

    p = sub.add_parser("move")
    p.add_argument("x", type=int); p.add_argument("y", type=int)
    p.add_argument("--window"); p.add_argument("--desktop", action="store_true")
    p.add_argument("--session", default=None)

    p = sub.add_parser("click")
    p.add_argument("x", type=int); p.add_argument("y", type=int)
    p.add_argument("--window"); p.add_argument("--desktop", action="store_true")

    p = sub.add_parser("type")
    p.add_argument("text"); p.add_argument("--pid", type=int, required=True)
    p.add_argument("--wid", type=int, required=True)

    p = sub.add_parser("key")
    p.add_argument("key"); p.add_argument("--pid", type=int, required=True)
    p.add_argument("--wid", type=int, required=True)

    p = sub.add_parser("record")
    p.add_argument("action", choices=["start", "stop"])
    p.add_argument("--out", default="take.mkv")
    p.add_argument("--fps", type=int, default=30)

    args = ap.parse_args()
    ensure_daemon()

    if args.cmd == "status":
        print(subprocess.run([driver(), "status"], capture_output=True, text=True).stdout.strip())

    elif args.cmd == "shot":
        print(shot(args.out))

    elif args.cmd == "windows":
        data = call("list_windows")
        print(json.dumps(data, indent=1))

    elif args.cmd == "move":
        payload = {"x": args.x, "y": args.y}
        target = window_target(args)
        if args.session:
            payload["session"] = args.session
        if target:
            payload["target"] = target          # NOTE: no "scope" when target is set
        else:
            payload["scope"] = "desktop"        # real OS pointer
        print(json.dumps(call("move_cursor", payload), indent=1))

    elif args.cmd == "click":
        target = window_target(args)
        payload = {"x": args.x, "y": args.y}
        if target:
            payload["target"] = target
        else:
            payload["scope"] = "desktop"
        print(json.dumps(call("click", payload), indent=1))

    elif args.cmd == "type":
        print(json.dumps(call("type_text", {
            "pid": args.pid, "window_id": args.wid,
            "text": args.text, "delivery_mode": "foreground",
        }), indent=1))

    elif args.cmd == "key":
        print(json.dumps(call("press_key", {
            "pid": args.pid, "window_id": args.wid,
            "key": args.key, "delivery_mode": "foreground",
        }), indent=1))

    elif args.cmd == "record":
        pid_file = ".cua-record.pid"
        if args.action == "start":
            proc = subprocess.Popen(capture_cmd(args.out, args.fps),
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open(pid_file, "w") as fh:
                fh.write(str(proc.pid))
            print(f"recording -> {args.out} (pid {proc.pid})")
        else:
            try:
                pid = int(open(pid_file).read().strip())
                stop_process(pid)
                os.remove(pid_file)
                print("stopped (mkv is playable even after a hard stop)")
            except FileNotFoundError:
                print("no recording in progress")


if __name__ == "__main__":
    main()
