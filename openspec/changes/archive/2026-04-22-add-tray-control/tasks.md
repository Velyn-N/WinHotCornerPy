## 1. Tray Lifecycle

- [x] 1.1 Introduce a tray controller that runs while the utility is active and exposes a tray icon with menu actions.
- [x] 1.2 Refactor app lifecycle so hot corners can be enabled, disabled, re-enabled, and quit cleanly without relying on the console loop.

## 2. Tray Actions

- [x] 2.1 Implement tray actions for enable/disable, reload config, open config file, and quit.
- [x] 2.2 Ensure opening the config file creates `hot_corners_config.json` from defaults when it does not already exist.

## 3. Verification

- [x] 3.1 Verify disabling from the tray stops triggering while the process remains running.
- [x] 3.2 Verify re-enabling from the tray resumes triggering without a full restart.
- [x] 3.3 Verify quit from the tray releases hook resources cleanly.
