# WinHotCornerPy

Windows hot corners utility with tray control, multi-monitor top-left corner support, and fail-safe recovery paths.

> **AI Disclaimer**
> This project was created with significant AI assistance.
> AI was used for ideation, specification drafting, implementation support, refactoring, debugging, and documentation.
> Use this project with caution, especially because this project interacts with global mouse hooks, startup behavior, and recovery paths.

## What It Is

WinHotCornerPy brings a GNOME-style hot-corner workflow to Windows.

When enabled, moving the mouse into the top-left corner of a monitor can trigger Windows Task View via `Win+Tab`.
The project is designed for multi-monitor setups, tray-based background use, and careful recovery behavior if anything goes wrong.

## What It Does

- supports the top-left corner of all active monitors
- adapts to monitor changes while running
- runs in the background with a tray icon
- supports delayed startup after login
- keeps configurable trigger thresholds in a local config file
- provides keyboard-only recovery paths if mouse interaction becomes unreliable

## Installation

Clone the repository:

```powershell
git clone https://github.com/Velyn-N/WinHotCornerPy.git
cd WinHotCornerPy
```

Install the Python dependencies:

```powershell
pip install -r requirements.txt
```

## Usage

Start the app normally:

```powershell
python hot_corners.py
```

Useful development and test modes:

```powershell
python hot_corners.py --no-tray
python hot_corners.py --dry-run --no-tray --verbose
```

The normal app mode runs in the tray and enables hot corners immediately unless startup delay behavior is being used through the startup launcher.

## Configuration

Local configuration lives at:

```text
.runtime\hot_corners_config.json
```

The file is created automatically when needed. You only need to set the values you want to override. Missing values fall back to built-in defaults.

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

## Project Note

This repository was also used as an experiment in AI-assisted software development with Claude, Codex, and OpenSpec working together across exploration, specification, implementation, debugging, and iteration.
