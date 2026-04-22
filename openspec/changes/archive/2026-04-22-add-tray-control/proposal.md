## Why

The current hot-corner script behaves like a background utility but still depends on console-style lifecycle control. That makes it awkward to enable, disable, reload, or quit in normal desktop use, so it needs a lightweight OS-native control surface.

## What Changes

- Add a system tray icon while the app is running.
- Add tray actions to enable or disable hot corners, reload configuration, open the local config file, and quit the app.
- Replace console-first lifecycle control with a tray-first background-app model while preserving safe hook shutdown.
- Exclude a full settings UI from this change and keep configuration file editing as the control path for tuning values.

## Capabilities

### New Capabilities

### Modified Capabilities
- `dynamic-hot-corners`: Add tray-based runtime control, background lifecycle handling, and config-file access for the existing hot-corner utility.

## Impact

- Affects application lifecycle, process startup mode, and shutdown behavior.
- Reuses the existing `pystray` and `Pillow` dependencies for tray integration.
- Requires coordination between tray actions and the hook engine so enable/disable and quit remain safe.
