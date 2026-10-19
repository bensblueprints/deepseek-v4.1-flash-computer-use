---
name: computer-use
description: "Drive a Windows desktop: move a visible agent cursor, click, type, screenshot, and record cursor-visible screen captures for tutorials. Use when the user asks to show where to click, automate a GUI, record a walkthrough, or operate an app that has no CLI."
---

# Computer Use

Scripted desktop control through the CUA driver, wrapped by `cua.py`.

Run every command from the repo root. Requires `cua-driver serve` (the wrapper
starts it automatically if it is not running).

## Core loop

1. **Look** — `python cua.py shot --out screen.png`, then view `screen.png`.
2. **Find** — `python cua.py windows` for `pid` / `window_id` pairs.
3. **Act** — move, click, type.
4. **Verify** — screenshot again; never assume a click landed.

## Commands

```powershell
python cua.py status
python cua.py shot --out screen.png               # whole desktop
python cua.py shot --out win.png --window <pid>:<wid>   # one window (needed on Wayland)
python cua.py windows
python cua.py move 400 300 --window <pid>:<wid>     # visible agent cursor
python cua.py move 400 300 --desktop                 # real OS pointer
python cua.py click 960 540 --desktop                # absolute screen coords
python cua.py type "text" --pid <pid> --wid <wid>
python cua.py key Tab --pid <pid> --wid <wid>
python cua.py record start --out take.mkv
python cua.py record stop
```

## Coordinate spaces

| Call | Space |
|---|---|
| `get_window_state` screenshot | window-local pixels, origin at window top-left |
| `get_desktop_state` screenshot | screen pixels, origin at primary top-left |
| `click --desktop` | absolute screen pixels |
| `move … --window` | window-local pixels |

Get absolute coords for a window-local point with:
`absolute = window.bounds.x + local_x`, same for `y`.

## Hard rules

- **Never pass `scope` together with `target`** — `invalid_action_target`.
  With a window target, omit `scope`. Use `scope: "desktop"` only when moving
  the real pointer.
- **Chromium/Electron needs `delivery_mode: "foreground"`** for typing and
  clicking. The wrapper already sets it for `type`/`key`. For browser pixel
  clicks, retry with foreground when the driver reports
  `background_unavailable`.
- **Do not rely on `element_token` across CLI calls** — snapshots do not
  survive between processes. Use pixels, or open one MCP session.
- **Verify after every destructive or navigation action** with a fresh
  screenshot.
- **Stop before irreversible steps** (submitting forms, account creation,
  payments, deletions) and hand control back to the user.

## Tutorial recording

```powershell
python cua.py record start --out take.mkv
python cua.py move 500 300 --window <pid>:<wid>
python cua.py click 900 500 --desktop
python cua.py record stop
```

- `ddagrab` captures the agent cursor; OBS on some machines does not.
- Make the target window full-screen on the captured monitor first.
- Pin the cursor so it does not fade: call `set_agent_cursor_motion` with
  `idle_hide_ms: 0` and `effects` on (glow, ripple, trail).

## Linux

Same commands; the display stack differs. Verified on Pop!_OS 24.04 / COSMIC
(Wayland + XWayland).

```bash
# install (user scope, no sudo)
/bin/bash -c "$(curl -fsSL https://cua.ai/driver/install.sh)"

# a non-interactive SSH shell has no display env — set it explicitly
export DISPLAY=:1 XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-1
cua-driver serve
```

- **`list_windows`, `get_window_state`, `type_text`, `press_key`,
  desktop-scope `click`, `move_cursor` — all work on XWayland.**
- **`get_desktop_state` fails** under XWayland (`X11 GetImage BadMatch`). Use
  `cua shot --window <pid>:<wid>`; that path works.
- **Window-target `click` fails** with `screenshot_context_missing` — the CLI
  cannot carry a snapshot between processes. Use `click X Y --desktop` with
  absolute coordinates (`bounds.x + local_x`).
- Window captures come back **scaled** (`frame_scale`, e.g. 0.758). Divide the
  PNG coordinates by it to get real window pixels.
- The **first keystroke after a focus change can be dropped** — send a throwaway
  key or re-focus before typing anything that matters.
- Recording needs `wf-recorder` (`sudo apt install wf-recorder`); without it the
  wrapper warns and falls back to `x11grab`, which produced a **black frame**
  under COSMIC. Do not treat x11grab as a fallback there.
- **Headless**: `Xvfb :99 -screen 0 1920x1080x24 &` then `export DISPLAY=:99`.

Run `cua-driver doctor` first on an unfamiliar box — it reports whether the
X11 connection and AT-SPI bus are reachable.

## Safety

- Ask before clicking anything that changes account state, spends money, or
  deletes data.
- Never enter real credentials, phone numbers, or payment details on the user's
  behalf.
- Screenshots capture the whole screen — only take them when the task needs it.
