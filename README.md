# HotCornerPy

Windows hot corners utility with tray control, multi-monitor top-left corner support, and fail-safe recovery paths.

## Tray Controls

The tray menu supports:

- enable or disable hot corners
- enable or disable startup launch
- reload config
- open the config file
- open the log file
- open this README
- quit

## Recovery & Emergency Instructions

There are two different recovery levels. Use the lighter one first.

### 1. In-app emergency hotkeys

Use these when the app is still running normally, and you need to stop or exit it quickly.

- `Ctrl+Alt+Shift+F12`: disable hot corners immediately but keep the app running
- `Ctrl+Alt+Shift+F11`: quit the app completely

Use `F12` if hot corners are misbehaving, but you still want access to the tray, logs, and config.

Use `F11` if you want the whole app gone right away and the in-app hotkeys still respond.

### 2. Windows keyboard-only emergency stop

Use this if the tray cannot be trusted, the app UI is not responding, or mouse behavior is so broken that you want an OS-level kill path.

Preferred path:

1. Press the Windows key.
2. Type `HotCornerPy Emergency Stop`.
3. Press `Enter`.

Local fallback path that is always generated in the repo runtime directory:

1. Press `Win+R`.
2. Run:

```text
.runtime\hot_corners_emergency_stop.cmd
```

Use the Start Menu entry first when Windows search is responsive. Use the local `.cmd` fallback when Start Menu search is unavailable or you specifically want a known local command in the project directory.

Both recovery paths use the stored PID file to stop the running instance without needing the mouse.

## Local Runtime Files

Local runtime artifacts are kept under `.runtime/`, including:

- local config
- log file
- PID file
- local emergency stop script
