## MODIFIED Requirements

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
