## Context

The current implementation is functionally a background utility, but it still starts and stops like a console script. Users need a persistent control surface to toggle the feature, reload config, and quit cleanly without relying on the terminal. The repository already includes `pystray` and `Pillow`, which makes a tray-first model the most direct fit.

The main design constraint is keeping tray UI concerns separate from the hook engine. The hook logic is safety-sensitive and should remain small and deterministic, while the tray layer should orchestrate lifecycle commands such as enable, disable, reload, and quit.

## Goals / Non-Goals

**Goals:**
- Add a tray icon that remains available while the utility is running.
- Provide tray actions for enable/disable, reload config, open config file, and quit.
- Allow the app to remain running while hot corners are disabled, instead of forcing a full process exit.
- Preserve safe hook installation and teardown when the user toggles the feature or quits from the tray.

**Non-Goals:**
- Building an in-app settings window.
- Implementing startup-with-Windows behavior in this change.
- Adding notifications, onboarding, or other richer desktop UX beyond the tray control surface.

## Decisions

### Use a tray-first background application model
The app should run as a tray utility and expose lifecycle control from the system tray rather than through console interaction. The console can remain available for development flags, but it should not be the primary runtime control path.

Alternatives considered:
- Keep the console as the only control surface: too awkward for normal desktop usage.
- Add a standalone configuration window first: larger scope than needed for immediate OS integration.

### Keep the hook engine and tray controller separate
The tray layer should call explicit engine lifecycle methods such as enable, disable, reload_config, and stop. The hook implementation should not be tangled directly into tray callbacks beyond those control boundaries.

Alternatives considered:
- Let tray callbacks manipulate low-level hook state directly: simpler at first glance but riskier and harder to reason about.

### Open the config file instead of building a settings UI
This change should support configuration by opening the local config file and reloading it on demand. If the config file does not exist, the app can create it from defaults before opening it.

Alternatives considered:
- Build a settings form now: useful later, but unnecessary to deliver tray control.

## Risks / Trade-offs

- [Tray loop and hook lifecycle interfere with each other] → Mitigate with explicit app-state methods and clean thread boundaries.
- [Disable state still leaves hooks active] → Mitigate by making disable stop or bypass hook processing through a clear engine lifecycle path.
- [Config file open behavior differs across Windows setups] → Mitigate by using the OS-default file opening path and falling back cleanly if it fails.
- [Silent failures leave the tray running but the engine broken] → Mitigate with visible enabled/disabled state and conservative error handling in lifecycle transitions.

## Migration Plan

No data migration is required. Existing configuration continues to live in `hot_corners_config.json`. Runtime usage shifts from console-first to tray-first operation.

## Open Questions

- Whether disabled mode should fully unhook or keep the hook installed but inert.
- Whether the tray tooltip should reflect enabled/disabled status or error state explicitly.
