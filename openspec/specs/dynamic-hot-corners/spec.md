## ADDED Requirements

### Requirement: Detect top-left corners on all active monitors
The system SHALL treat the top-left corner of every active monitor as a potential hot-corner region. Corner detection MUST be based on the current monitor rectangles reported by the operating system rather than on the virtual desktop origin alone.

#### Scenario: Pointer enters the top-left of a secondary monitor
- **WHEN** the pointer enters the configured corner zone at the top-left edge of a non-primary active monitor
- **THEN** the system recognizes that monitor corner as an eligible hot-corner region

#### Scenario: Negative monitor coordinates remain valid
- **WHEN** a monitor’s top-left coordinate is negative in virtual desktop space
- **THEN** the system still evaluates that monitor’s top-left corner correctly using the monitor’s actual rectangle

### Requirement: Adapt to monitor layout changes without restart
The system SHALL refresh its monitor topology while running so that hot-corner detection remains correct when monitors are added, removed, enabled, disabled, or repositioned.

#### Scenario: New monitor is connected while the process is running
- **WHEN** a monitor topology change occurs after startup
- **THEN** the system updates its active monitor corner set during runtime without requiring the process to restart

#### Scenario: Monitor is disconnected while the process is running
- **WHEN** an active monitor is removed from the desktop topology
- **THEN** the system stops treating the removed monitor’s top-left coordinate as a valid hot-corner region

### Requirement: Provide configurable trigger thresholds
The system SHALL support configuration of the trigger thresholds used by hot-corner evaluation, including corner zone size, dwell time, cooldown time, click suppression duration, and rearm distances used to prevent immediate re-triggering. The system MUST validate configured values and fall back to safe defaults when values are missing or invalid.

#### Scenario: Valid configuration overrides defaults
- **WHEN** the user provides valid threshold values through the supported configuration mechanism
- **THEN** the system applies those values during hot-corner evaluation

#### Scenario: Invalid configuration is supplied
- **WHEN** the user provides a threshold value that is missing, malformed, or outside the supported range
- **THEN** the system ignores the invalid value and continues with a safe default for that threshold

### Requirement: Avoid triggering during ordinary top-left clicks
The system SHALL reduce accidental activation when the user is attempting to click UI near a monitor’s top-left corner. At minimum, the system MUST support click suppression so recent button activity in the corner prevents an immediate hot-corner trigger.

#### Scenario: User clicks a top-left UI control
- **WHEN** the pointer is in a monitor’s top-left corner region and the user performs a mouse click there
- **THEN** the system suppresses hot-corner triggering for at least the configured click suppression interval

#### Scenario: User intentionally dwells in the corner without clicking
- **WHEN** the pointer enters a monitor’s top-left corner region and remains there for at least the configured dwell time without disqualifying click activity
- **THEN** the system marks the corner visit as eligible for one trigger

### Requirement: Prevent immediate retriggering after activation
The system SHALL require the pointer to move out of the corner rearm area and far enough away from the original trigger point before the same or another hot corner can trigger again.

#### Scenario: Pointer lingers near the trigger point after activation
- **WHEN** the hot corner has triggered and the pointer remains near the corner or near the original trigger point
- **THEN** the system does not trigger again

#### Scenario: Pointer moves away before rearming
- **WHEN** the hot corner has triggered and the pointer has left the corner rearm area and moved beyond the configured retrigger guard distance
- **THEN** the system may arm a later hot-corner visit again

### Requirement: Fail safely under hook errors
The system SHALL never obstruct normal pointer movement due to internal hot-corner failures. If the hook pipeline encounters an unrecoverable internal fault, the system MUST disable hot-corner triggering and release hook resources cleanly. The running application MUST remain controllable through its normal runtime control surface where feasible.

#### Scenario: Callback-level fault occurs repeatedly
- **WHEN** the hook processing path detects repeated internal faults that make continued operation unsafe
- **THEN** the system disables the hot-corner feature instead of continuing to process input in a degraded state

#### Scenario: Feature is disabled after a fatal fault
- **WHEN** the hot-corner feature has been disabled due to an internal fault
- **THEN** normal mouse movement and clicking continue without application interference

### Requirement: Provide tray-based runtime control
The system SHALL provide a system tray icon while the utility is running. The tray menu MUST allow the user to enable or disable hot corners, reload configuration, open the local configuration file, and quit the application.

#### Scenario: User disables hot corners from the tray
- **WHEN** the user selects the disable action from the tray
- **THEN** hot-corner triggering stops while the application remains running

#### Scenario: User re-enables hot corners from the tray
- **WHEN** the user selects the enable action from the tray after disabling the feature
- **THEN** hot-corner processing resumes without requiring a full application restart

#### Scenario: User opens config from the tray
- **WHEN** the user selects the open-config action from the tray
- **THEN** the system opens the local configuration file for editing and creates it from defaults first if it does not already exist

#### Scenario: User reloads config from the tray
- **WHEN** the user selects the reload-config action from the tray
- **THEN** the system reloads configuration values for subsequent hot-corner evaluation

#### Scenario: User quits from the tray
- **WHEN** the user selects quit from the tray
- **THEN** the application shuts down cleanly and releases hook resources
