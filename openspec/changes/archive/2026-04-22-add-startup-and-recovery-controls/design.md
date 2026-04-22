## Context

The app now has a tray-based runtime model, which makes continuous background use plausible. The next step is not just “start at login,” but “start at login without trapping the user if something goes wrong.” A low-level mouse hook utility needs stronger operational safety guarantees than a normal desktop app.

There are three intertwined concerns:
- automatic startup after login
- observability, especially access to logs without attaching a console
- emergency recovery that works even when the mouse cannot be trusted

The recovery constraint is the hardest one. Any in-app control is helpful, but must not be the only escape hatch because a broken hook or hung process could render the tray unusable.

## Goals / Non-Goals

**Goals:**
- Support automatic launch after user login.
- Allow delayed startup so the app does not claim input immediately at login.
- Make logs reachable from the tray.
- Preserve at least one keyboard-only in-app recovery path and one keyboard-only OS-level recovery path.

**Non-Goals:**
- Building a full installer in this change.
- Supporting startup behavior for all users on the machine.
- Solving packaging and distribution fully unless needed to strengthen recovery behavior.

## Decisions

### Prefer delayed automatic startup over immediate hook activation at login
Startup should support a configurable delay after user logon. That reduces risk by giving the user time to reach the desktop and intervene before the hook becomes active.

Alternatives considered:
- Immediate startup at logon: simpler, but increases the blast radius of startup failures.

### Expose logs through the tray rather than a live debug window
The tray should provide at least an `Open Log File` action, and optionally `Open Log Folder`, so the user can inspect behavior without needing a dedicated foreground console view.

Alternatives considered:
- Reintroduce a persistent console window: useful for development, but not ideal for background utility usage.
- Build a custom log viewer UI: too much scope for the value it provides right now.

### Require two layers of recovery
The design should include:
- an in-app keyboard-triggered emergency disable path
- a documented OS-level keyboard-only kill path that does not rely on the tray or mouse

Alternatives considered:
- Tray-only recovery: unacceptable because it depends on mouse interaction and app responsiveness.
- OS-level recovery only: workable, but too blunt for the most common failure modes.

### Strongly consider a stable process identity for recovery
If the app runs under a generic Python process name, OS-level keyboard kill commands become less precise. A future packaged executable or otherwise unique process identity materially improves safe recovery.

Alternatives considered:
- Keep generic interpreter-based process identity forever: simpler, but weakens reliable keyboard-only termination.

## Risks / Trade-offs

- [Startup integration causes immediate bad login experience] → Mitigate with delayed start and easy disable/removal path.
- [In-app emergency hotkey fails when the app is badly broken] → Mitigate by also defining an independent OS-level keyboard kill path.
- [Log access is still too hidden for debugging] → Mitigate with a direct tray action that opens the log file or folder.
- [Generic process naming makes kill commands ambiguous] → Mitigate by planning for a stable process identity or packaged binary.

## Migration Plan

Existing tray usage continues to work. Automatic startup should be opt-in and should create or update the chosen Windows startup mechanism without disrupting current manual launch behavior.

## Open Questions

- Whether startup should be implemented through Task Scheduler, Startup folder, or both.
- Whether the emergency disable hotkey should stop hooks only or fully terminate the process.
- Whether packaged executable support should be included in the same change or deferred.
