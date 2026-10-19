# Recording a tutorial with a visible cursor

End-to-end workflow used to produce a "how to sign up" style walkthrough.

## 0. Prep

- Put the app window **full-screen on the monitor you will capture**.
- Hide anything private (email inbox, account avatar, phone number).
- Confirm the capture monitor:

```powershell
# Windows
ffmpeg -y -f lavfi -i "ddagrab=output_idx=0:framerate=1" -frames:v 1 probe.png
```

```bash
# Linux / X11
ffmpeg -y -f x11grab -video_size 1920x1080 -i "$DISPLAY" -frames:v 1 probe.png
# Linux / Wayland
wf-recorder -f probe.mp4 -r 1 & sleep 1; kill %1
```

Open `probe.png` (or a frame from `probe.mp4`). If it shows the wrong display,
change `output_idx` (Windows) or `DISPLAY` / `CUA_CAPTURE_SIZE` (Linux).

## 1. Pin the cursor

```python
cua.call("set_agent_cursor_motion", {
    "idle_hide_ms": 0,
    "effects": {"glow": "on", "ripple": "on", "trail": "on"},
    "style": "signature_arc",
    "timing": "steady",
})
```

`steady` gives every move a 600 ms floor — slow enough to follow on video.

## 2. Roll

```powershell
python cua.py record start --out take.mkv
```

## 3. Drive slowly

For each step: screenshot → locate → move → pause → click → verify.

```powershell
python cua.py shot --out step1.png
python cua.py move 960 540 --desktop
python cua.py click 960 540 --desktop
python cua.py shot --out step1_after.png
```

Keep the pointer parked on the thing you are talking about for ~1 s before
clicking. That pause is what makes a tutorial readable.

## 4. Stop and convert

```powershell
python cua.py record stop
ffmpeg -i take.mkv -c copy take.mp4
```

MKV survives a hard stop; MP4 does not.

## 5. Post

- Concatenate takes, then add narration and captions:
  ```powershell
  ffmpeg -i silent.mp4 -i voiceover.wav -c:v copy -c:a aac -b:a 192k -ar 44100 -ac 2 -shortest final.mp4
  ```
- Keep the raw takes — `ddagrab` output is cheap (static screens compress hard).

## Gotchas seen in practice

- OBS 32.2.2 recorded cursorless video on one machine even with
  `capture_cursor: true` and both WGC and DXGI. `ddagrab` worked.
- Windows that are maximized must be restored before `set_window_frame`.
- A window on a different monitor will not appear in `output_idx=0`.
- On Linux, `ddagrab` does not exist — the wrapper falls back to `wf-recorder`
  (Wayland) or `x11grab` (X11). Check the first frame for the cursor.
- Under a bare Wayland session without the compositor plugin, capture or input
  may be refused outright. X11 or Xvfb is the reliable path.
