# DeepSeek v4.1 Flash — Computer Use

A small, working **computer-use skill pack**: move the cursor, click, type, take
screenshots, and record a cursor-visible screen capture — all from the command
line, so an agent can drive a desktop turn by turn.

It wraps the excellent open-source [CUA driver](https://github.com/trycua/cua)
(`cua-driver`) and encodes the patterns that actually work, including the ones
the docs don't make obvious.

> **Unofficial.** Not affiliated with or endorsed by DeepSeek or trycua.
> "DeepSeek v4.1 Flash" is the model this pack was developed and tested against
> inside an agent CLI; the computer-use capability comes from the CUA driver.

---

## What it does

| Capability | Tool |
|---|---|
| Screenshot the desktop | `get_desktop_state` → PNG |
| List windows + PIDs | `list_windows` |
| Move a **visible agent cursor** | `move_cursor` (window target) |
| Move the **real OS pointer** | `move_cursor` (`scope: desktop`) |
| Click, double-click, right-click, drag, scroll | `click`, `double_click`, … |
| Type / press keys | `type_text`, `press_key`, `hotkey` |
| Accessibility tree per window | `get_window_state` |
| Record screen **with the cursor** | `ffmpeg ddagrab` |

## Requirements

- Windows 10/11, macOS, or Linux (x86_64 / arm64)
- The CUA driver:

  ```bash
  # Windows (PowerShell)
  irm https://cua.ai/driver/install.ps1 | iex

  # Linux / macOS
  /bin/bash -c "$(curl -fsSL https://cua.ai/driver/install.sh)"

  cua-driver serve
  ```
- Python 3.10+
- `ffmpeg` on PATH (for recording only)

## Install

```powershell
git clone https://github.com/bensblueprints/deepseek-v4.1-flash-computer-use
cd deepseek-v4.1-flash-computer-use
python cua.py status
```

## Quickstart

```powershell
# 1. see the screen
python cua.py shot --out screen.png

# 2. find the window you want
python cua.py windows

# 3. move the visible agent cursor inside that window
python cua.py move 400 300 --window 1234:5678

# 4. click at absolute screen coordinates
python cua.py click 960 540 --desktop

# 5. type into a browser/app
python cua.py type "hello world" --pid 1234 --wid 5678

# 6. record a tutorial take with the cursor visible
python cua.py record start --out take.mkv
#    ... drive the UI ...
python cua.py record stop
```

## Linux

Same CLI, same tool calls — the differences are all in the **display stack** and
the **recorder**, because `ddagrab` is Windows-only.

### Install

```bash
/bin/bash -c "$(curl -fsSL https://cua.ai/driver/install.sh)"
cua-driver serve
```

This installs to `~/.local/bin/cua-driver` (override with `--bin-dir`, e.g.
`/usr/local/bin` which needs `sudo`). The wrapper already looks there.

Linux builds are published as `linux-x86_64` and `linux-arm64`. Upstream labels
them **preview** builds — check yours with `cua-driver doctor` and
`cua-driver list-tools` before relying on it.

### Display server

| Session | Input | Window capture | Desktop capture |
|---|---|---|---|
| **X11** | XTest | works | works |
| **Wayland + XWayland** (COSMIC, GNOME, KDE) | XTest into XWayland clients | **works** | **fails** — `X11 GetImage BadMatch` |
| **Headless** | `Xvfb` + `DISPLAY=:99` | works | works |

**Use window capture on Wayland.** Whole-desktop capture (`get_desktop_state`)
is the one thing that breaks under XWayland — everything else works.

### Tested on Pop!_OS 24.04 / COSMIC (Wayland + XWayland)

Measured, not assumed:

| Operation | Result |
|---|---|
| `install.sh` | ok → `~/.local/bin/cua-driver` |
| `cua-driver doctor` | `display server: Wayland+XWayland`, `X11 connection: connected` |
| `list_windows` | works (X11/XWayland clients) |
| `get_window_state` | **works** — 1456×713 from a 1920-wide window (`frame_scale: 0.758`) |
| `get_desktop_state` | **fails** — `X11 error: Match (GetImage, BadMatch)` |
| `type_text` | works (pty/XTest) — the first keystroke after a focus change can be dropped |
| `press_key` | works |
| `move_cursor` (window target) | accepted (`synthetic_events`) |
| `click` (window target) | `screenshot_context_missing` — needs an in-process snapshot |
| `click` (`scope: desktop`) | works — send screen-absolute coordinates |
| `get_screen_size` | reported 3000×1920 |
| `wf-recorder` / `grim` / `obs` | **not installed** by default; `ffmpeg` is |

Practical consequences:

- Use `cua shot --window <pid>:<wid>` on Wayland; plain `cua shot` will error.
- Drive clicks with `cua click X Y --desktop` using absolute coordinates
  (`window.bounds.x + local_x`).
- Window captures are **scaled** — `frame_scale` tells you the ratio between the
  PNG and the real window. Divide by it before converting back.
- Recording needs `wf-recorder` installed (`sudo apt install wf-recorder`), or
  `x11grab` will only see XWayland surfaces.

### Recording on Linux

`cua.py record start` picks the right backend automatically:

```python
# Windows
ffmpeg ... ddagrab=output_idx=0 ...
# Wayland with wf-recorder installed
wf-recorder -f take.mp4 -r 30
# X11 (or Wayland without wf-recorder — warns, and only sees XWayland surfaces)
ffmpeg -f x11grab -framerate 30 -video_size 1920x1080 -i $DISPLAY ...
```

Install the Wayland recorder first:

```bash
sudo apt install wf-recorder     # or: yay -S wf-recorder
```

Multi-monitor: override the grab size with `CUA_CAPTURE_SIZE=2560x1440`, and the
display with `DISPLAY=:1`.

The agent cursor overlay is a separate always-on-top window. X11 compositors
show it; some Wayland compositors ignore always-on-top/click-through requests,
so **verify the cursor is in the first recorded frame** before doing a long take.
I could not visually confirm the overlay on COSMIC from a headless SSH session —
treat that as unverified on Wayland and check it yourself.

### Headless box (no monitor)

```bash
sudo apt install -y xvfb ffmpeg
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
cua-driver serve
python cua.py shot --out screen.png
python cua.py record start --out take.mkv
```

Useful for CI or a server-side 3090 box: run the app under Xvfb, drive it, record
it, no physical display needed.

### What does not carry over

- `ddagrab` — Windows only; use `x11grab` / `wf-recorder`
- `taskkill` — the wrapper sends `SIGINT` on POSIX
- **`get_desktop_state` under XWayland** — use `shot --window` instead
- Windows-specific window concepts (`window_id` is still returned, but treat it
  as opaque)



1. **`scope` and `target` are mutually exclusive.**
   `move_cursor` with `target: {kind: window, …}` must *omit* `scope`. Passing
   both returns `invalid_action_target`. Omit the target and pass
   `scope: "desktop"` to move the real pointer instead.

2. **Chromium/Electron swallows background input.**
   `type_text` and `click` need `delivery_mode: "foreground"` for browser
   content. The driver usually tells you with `background_unavailable` — let it
   be your signal instead of guessing.

3. **Element tokens die between CLI processes.**
   `get_window_state` returns a snapshot id, and `element_token` is only valid
   for that snapshot — in the same process. Spawned CLI calls each get a new
   lease, so `element_token` always reads as `stale_element_token`. Use pixel
   coordinates (window-local for `get_window_state`, absolute for
   `scope: desktop`) or keep one long-lived MCP session.

4. **The agent cursor fades after 15 seconds.**
   For recording, pin it:
   ```python
   call("set_agent_cursor_motion", {"idle_hide_ms": 0,
        "effects": {"glow": "on", "ripple": "on", "trail": "on"}})
   ```

5. **`ddagrab` records the cursor; OBS does not.**
   On the machine this was built on, OBS 32.2.2 (WGC *and* DXGI with
   `capture_cursor: true`) produced cursorless captures, while
   `ffmpeg -f lavfi -i ddagrab=output_idx=0` captured the agent cursor perfectly.
   If your tutorial needs a visible pointer, record with `ddagrab`.

## Recording tutorials

`record start` runs:

```
ffmpeg -f lavfi -i ddagrab=output_idx=0:framerate=30 \
       -vf hwdownload,format=bgra \
       -c:v libx264 -preset ultrafast -crf 20 -pix_fmt yuv420p take.mkv
```

Notes:
- `output_idx` selects the monitor (0 = first output). Make sure the window you
  are driving is on that monitor, or move it there first.
- MKV survives a hard stop; MP4 does not. Convert afterwards:
  `ffmpeg -i take.mkv -c copy take.mp4`
- Static screens compress to almost nothing — a 5-minute UI session can be a
  couple of MB.

## Using it as an agent skill

Copy `SKILL.md` into your agent's skills directory, or point your MCP client at
`cua-driver mcp`. The skill file is written for Kimi Code / Claude Code style
skill loading.

## Layout

```
cua.py                      wrapper CLI (this is the useful part)
SKILL.md                    agent skill definition
examples/hello_cursor.py    smallest possible demo
examples/tutorial_recording.md  end-to-end tutorial capture workflow
```

## License

MIT — see `LICENSE`.
