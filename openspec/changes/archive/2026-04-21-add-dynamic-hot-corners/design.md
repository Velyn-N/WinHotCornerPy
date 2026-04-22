## Context

The project aims to recreate GNOME-style top-left hot corners on Windows using Python with minimal performance impact. A stripped-down `WH_MOUSE_LL` probe has already shown that Python can receive global mouse move and button events reliably when the Win32 hook is declared correctly and the callback remains simple.

The main technical challenges are not basic event capture but safe operation under a global mouse hook, correct behavior across multiple monitors, and avoiding accidental activation when the pointer is near interactive UI in the top-left area. The monitor layout may change while the process is running as displays are connected, disconnected, docked, or rearranged, so the system cannot assume a fixed desktop geometry at startup.

## Goals / Non-Goals

**Goals:**
- Detect the top-left corner of every active monitor rather than only the virtual desktop origin.
- Refresh monitor geometry at runtime without requiring a process restart.
- Keep the hook callback lightweight and fail-safe so mouse input is never obstructed by application faults.
- Support configurable trigger thresholds such as corner zone size, dwell time, cooldown, and click suppression duration.
- Distinguish intentional corner activation from ordinary top-left clicking closely enough to be usable in daily work.

**Non-Goals:**
- Supporting arbitrary corner actions beyond the initial hot-corner command in the first change.
- Building a full tray UI or advanced settings editor in the first implementation.
- Perfect parity with GNOME’s internal heuristics on the first pass.
- Solving every special environment up front, such as games, remote desktop sessions, or elevated desktop contexts.

## Decisions

### Use a low-level global mouse hook for event capture
The implementation will use `WH_MOUSE_LL` rather than polling. The hook probe already demonstrated that Python can receive the required events safely when `ctypes` signatures are correct.

Alternatives considered:
- Polling cursor position: simpler, but it does not prove the final architecture and wastes work on a separate event model.
- Third-party input libraries: faster to prototype, but they hide the Win32 details that matter most for safety and monitor handling.

### Track monitor-specific top-left corners from live monitor enumeration
The implementation will maintain a current set of monitor rectangles and derive one active hot corner per monitor from each monitor’s top-left coordinate. The process will refresh this topology periodically while running so monitor changes are picked up without requiring a restart.

Alternatives considered:
- Treat the virtual desktop origin as the only hot corner: incorrect for multi-monitor use and incompatible with the requirement to support all monitor top-left corners.
- Recompute monitor layout on every mouse event: correct but unnecessary overhead on the hook path.

### Keep hook processing minimal and move all non-trivial work out of the callback
The hook callback will only normalize the event, update small in-memory state, and decide whether to enqueue a trigger request. Any slower work, including emitting the final action or reloading configuration, will occur outside the callback.

Alternatives considered:
- Trigger the final action directly inside the callback: simpler code but unacceptable risk if the action blocks or throws.
- Add broad logging in the callback: useful for debugging but too noisy and potentially expensive in the hot path.

### Make trigger thresholds externally configurable with safe defaults
The feature will expose a small configuration surface for values such as `corner_zone_px`, `dwell_ms`, `cooldown_ms`, `click_suppression_ms`, `rearm_distance_px`, and `retrigger_guard_distance_px`. Defaults will favor safety and low accidental activation.

Alternatives considered:
- Hard-coded values only: simpler, but it prevents practical tuning across different pointer speeds, monitor sizes, and user expectations.
- Fully dynamic UI-based configuration first: useful later, but not necessary to validate core behavior.

### Fail closed on internal hook faults
If the hook logic encounters repeated internal faults or loses confidence in its own state, the application will unhook and disable the hot-corner feature rather than continue operating in a degraded state.

Alternatives considered:
- Continue running after repeated callback errors: risky because global input behavior is safety-critical.
- Crash the entire process immediately on the first callback error: safer than silent corruption, but unnecessarily harsh when the feature can simply self-disable.

## Risks / Trade-offs

- [Accidental activation near top-left UI] → Mitigate with dwell, click suppression, and one-trigger-per-visit semantics.
- [Incorrect corner classification on negative monitor coordinates] → Mitigate by comparing against enumerated monitor rectangles, not a naïve `x <= zone and y <= zone` test.
- [Hook bugs affecting global input] → Mitigate with explicit `ctypes` signatures, minimal callback work, and fail-closed shutdown.
- [Display topology changes not propagating fast enough] → Mitigate by periodic topology refresh with a configurable interval.
- [Configuration values that make the feature unusable] → Mitigate with documented defaults and value validation at load time.

## Migration Plan

This is a new capability, so no external migration is required. Implementation can proceed behind the existing single-script entry point. If a configuration file is introduced, the application should start with built-in defaults when the file is missing or invalid.

Rollback is straightforward: restore the current diagnostic script or disable the hook-based hot-corner feature entry point.

## Open Questions

- Which configuration source should be introduced first: command-line flags, environment variables, or a small local config file?
- Should the feature suppress itself automatically while a monitor is in fullscreen exclusive mode?
- Should the initial action remain fixed to `Win+Tab`, or should action configurability be deferred explicitly to a later change?
