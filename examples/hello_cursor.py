"""Smallest possible demo: draw a cursor path and take a screenshot.

Run from the repo root:
    python examples/hello_cursor.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cua  # noqa: E402

SESSION = "demo"

cua.ensure_daemon()
print(cua.call("start_session", {"session": SESSION}))

# Pin the cursor so it stays visible while we record.
cua.call("set_agent_cursor_motion", {
    "session": SESSION,
    "idle_hide_ms": 0,
    "effects": {"glow": "on", "ripple": "on", "trail": "on"},
})
cua.call("set_agent_cursor_enabled", {"session": SESSION, "enabled": True})

# Walk a small square with the visible overlay cursor.
wins = cua.call("list_windows").get("windows", [])
target = next((w for w in wins if w.get("is_on_screen") and w.get("title")), None)
if not target:
    raise SystemExit("no on-screen window found")

pid, wid = target["pid"], target["window_id"]
print(f"drawing inside {target.get('title')!r} ({pid}:{wid})")

for x, y in [(200, 200), (600, 200), (600, 450), (200, 450), (200, 200)]:
    cua.call("move_cursor", {
        "session": SESSION, "x": x, "y": y,
        "target": {"kind": "window", "pid": pid, "window_id": wid},
    })
    time.sleep(0.6)

print(cua.shot("hello_cursor.png"))
