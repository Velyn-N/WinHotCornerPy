## Why

The project needs a production-worthy definition of GNOME-style hot corners for Windows that remains safe under a global mouse hook and behaves correctly across changing monitor layouts. The recent hook probe showed that Python can capture the required mouse events reliably, so the next step is to define the feature and its operating constraints clearly enough to implement it safely.

## What Changes

- Add a global hot-corner feature that detects the top-left corner of every connected monitor, not just the virtual desktop origin.
- Require the running process to adapt to monitor layout changes without being restarted, including changing monitor counts and positions.
- Add configurable trigger thresholds such as corner zone size, dwell time, cooldown, and click suppression timing.
- Define safety requirements so hook faults disable the feature rather than interfering with pointer movement.
- Establish behavior for accidental clicks near monitor corners, multi-monitor coordinate handling, and clean process shutdown.

## Capabilities

### New Capabilities
- `dynamic-hot-corners`: Detect and trigger top-left hot corners across all active monitors, update live as monitor topology changes, and expose configurable trigger thresholds with safe failure behavior.

### Modified Capabilities

## Impact

- Affects the Python entry-point script and supporting hook/state management code.
- Adds monitor topology tracking and runtime configuration handling.
- Requires careful Win32 API usage for low-level mouse hooks and monitor enumeration.
- May add configuration file or command-line configuration support for threshold tuning.
