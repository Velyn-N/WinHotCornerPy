## MODIFIED Requirements

### Requirement: Provide tray-based runtime control
The system SHALL provide a system tray icon while the utility is running. The tray menu MUST allow the user to enable or disable hot corners, reload configuration, open the local configuration file, open runtime logs, and quit the application.

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

#### Scenario: User opens logs from the tray
- **WHEN** the user selects the log action from the tray
- **THEN** the system opens the runtime log file or its containing folder for inspection

#### Scenario: User quits from the tray
- **WHEN** the user selects quit from the tray
- **THEN** the application shuts down cleanly and releases hook resources

## ADDED Requirements

### Requirement: Support delayed background startup
The system SHALL support automatic launch after user login and MUST allow delayed startup so hot-corner processing does not have to begin immediately on desktop sign-in.

#### Scenario: Delayed startup is configured
- **WHEN** automatic startup is enabled with a startup delay
- **THEN** the utility starts in the background after the configured post-login delay rather than immediately at login

#### Scenario: Startup is not enabled
- **WHEN** the user has not enabled automatic startup
- **THEN** the utility does not register itself to launch automatically at login

### Requirement: Provide keyboard-only emergency recovery
The system SHALL preserve a keyboard-only recovery path for cases where mouse input is impaired. Recovery MUST not depend solely on tray interaction or mouse control.

#### Scenario: User triggers in-app emergency disable
- **WHEN** the user activates the configured emergency keyboard shortcut
- **THEN** the utility disables hot-corner processing without requiring mouse interaction

#### Scenario: In-app recovery is unavailable
- **WHEN** the utility is unresponsive or the in-app recovery path cannot be used
- **THEN** the user can still terminate or disable the utility through a documented keyboard-only OS-level recovery path
