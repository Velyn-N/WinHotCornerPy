## 1. Safe Hook Foundation

- [x] 1.1 Replace the diagnostic hook script with a production hook skeleton that keeps explicit Win32 signatures, a minimal callback path, and a reliable shutdown path.
- [x] 1.2 Add fail-safe error handling that disables hot-corner processing and unhooks cleanly after repeated internal callback faults.
- [x] 1.3 Remove the temporary console-input shutdown behavior that currently throws on `Ctrl+C` and replace it with a clean lifecycle strategy for the chosen runtime mode.

## 2. Monitor Topology Tracking

- [x] 2.1 Implement monitor enumeration and store the current rectangle for each active monitor.
- [x] 2.2 Derive one top-left hot-corner region per active monitor using monitor-local coordinates rather than the virtual desktop origin.
- [x] 2.3 Refresh the active monitor set while the process is running when displays are added, removed, or repositioned.

## 3. Trigger Evaluation And Configuration

- [x] 3.1 Implement configurable threshold loading with safe defaults and validation for corner zone size, dwell time, cooldown, and click suppression.
- [x] 3.2 Add per-corner visit state so the feature triggers at most once per visit and rearms only after leaving the active region.
- [x] 3.3 Add click suppression so top-left button activity prevents immediate hot-corner activation.

## 4. Action And Verification

- [x] 4.1 Reintroduce the hot-corner action execution outside the hook callback so triggering never blocks input processing.
- [x] 4.2 Validate behavior on single-monitor and multi-monitor layouts, including negative-coordinate monitors and hot-plug monitor changes.
- [x] 4.3 Verify that invalid configuration values fall back safely and that internal faults disable the feature without affecting normal mouse movement.
