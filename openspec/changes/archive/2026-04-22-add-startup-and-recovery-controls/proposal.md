## Why

The utility is now useful enough to run continuously in the background, but startup and recovery are not yet safe enough for daily unattended use. If it launches automatically at login, it must remain observable and recoverable even in failure cases where mouse input becomes unreliable.

## What Changes

- Add support for starting the utility automatically after user login with a delayed startup option.
- Add tray access to runtime logs so the user can inspect behavior without launching a separate console workflow.
- Add explicit keyboard-only emergency recovery controls so the user can disable or kill the utility even if mouse interaction is impaired.
- Define startup and recovery behavior as part of the main hot-corner capability rather than as optional operational guidance.

## Capabilities

### New Capabilities

### Modified Capabilities
- `dynamic-hot-corners`: Add background startup behavior, runtime log access, and keyboard-only recovery requirements for safe unattended use.

## Impact

- Affects process startup strategy, likely through a Windows logon integration path.
- Adds runtime control surface requirements beyond the existing tray menu.
- Introduces safety-driven shutdown and recovery behavior that must remain available without mouse input.
