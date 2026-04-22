"""
GNOME-style top-left hot corners for Windows.

The default runtime model is a tray-controlled background utility. A tray icon
allows enabling/disabling the engine, reloading configuration, opening the
local config file, opening logs, viewing recovery instructions, configuring
startup integration, and quitting the application.

Configuration is loaded from `.runtime/hot_corners_config.json` if the file
exists. Any missing or invalid values fall back to safe defaults.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import json
import logging
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


APP_DIR = os.path.dirname(os.path.abspath(__file__))
README_PATH = os.path.join(APP_DIR, "README.md")
RUNTIME_DIR = os.path.join(APP_DIR, ".runtime")
CONFIG_PATH = os.path.join(RUNTIME_DIR, "hot_corners_config.json")
LOG_PATH = os.path.join(RUNTIME_DIR, "hot_corners.log")
PID_PATH = os.path.join(RUNTIME_DIR, "hot_corners.pid")

APPDATA_DIR = os.environ.get("APPDATA", "")
START_MENU_PROGRAMS_DIR = os.path.join(
    APPDATA_DIR,
    "Microsoft",
    "Windows",
    "Start Menu",
    "Programs",
)
STARTUP_DIR = os.path.join(START_MENU_PROGRAMS_DIR, "Startup")
STARTUP_SCRIPT_PATH = os.path.join(STARTUP_DIR, "HotCornerPy Startup.cmd")
RECOVERY_SCRIPT_PATH = os.path.join(START_MENU_PROGRAMS_DIR, "HotCornerPy Emergency Stop.cmd")
FALLBACK_RECOVERY_SCRIPT_PATH = os.path.join(RUNTIME_DIR, "hot_corners_emergency_stop.cmd")

WH_MOUSE_LL = 14
HC_ACTION = 0

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
WM_QUIT = 0x0012
WM_HOTKEY = 0x0312

KEYEVENTF_KEYUP = 0x0002
VK_LWIN = 0x5B
VK_TAB = 0x09
VK_F11 = 0x7A
VK_F12 = 0x7B

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

EMERGENCY_DISABLE_HOTKEY_ID = 1
EMERGENCY_QUIT_HOTKEY_ID = 2
EMERGENCY_QUIT_HOTKEY_TEXT = "Ctrl+Alt+Shift+F11"
EMERGENCY_DISABLE_HOTKEY_TEXT = "Ctrl+Alt+Shift+F12"

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t
HHOOK = ctypes.c_void_p
HMONITOR = ctypes.c_void_p
HDC = ctypes.c_void_p

BUTTON_DOWN_MESSAGES = (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN)

DEFAULTS = {
    "corner_zone_px": 2,
    "rearm_distance_px": 40,
    "retrigger_guard_distance_px": 160,
    "dwell_ms": 20,
    "cooldown_ms": 400,
    "click_suppression_ms": 150,
    "monitor_refresh_ms": 300000,
    "startup_delay_ms": 30000,
    "max_callback_errors": 5,
}

CONFIG_BOUNDS = {
    "corner_zone_px": (1, 50),
    "rearm_distance_px": (0, 100),
    "retrigger_guard_distance_px": (10, 1000),
    "dwell_ms": (0, 5000),
    "cooldown_ms": (0, 10000),
    "click_suppression_ms": (0, 5000),
    "monitor_refresh_ms": (250, 3600000),
    "startup_delay_ms": (0, 600000),
    "max_callback_errors": (1, 100),
}


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.wintypes.HWND),
        ("message", ctypes.wintypes.UINT),
        ("wParam", ctypes.wintypes.WPARAM),
        ("lParam", ctypes.wintypes.LPARAM),
        ("time", ctypes.wintypes.DWORD),
        ("pt", POINT),
        ("lPrivate", ctypes.wintypes.DWORD),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)
MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.BOOL,
    HMONITOR,
    HDC,
    ctypes.POINTER(RECT),
    ctypes.wintypes.LPARAM,
)


user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    ctypes.wintypes.HINSTANCE,
    ctypes.wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = HHOOK

user32.CallNextHookEx.argtypes = [
    HHOOK,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
user32.CallNextHookEx.restype = LRESULT

user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL

user32.GetMessageW.argtypes = [
    ctypes.POINTER(MSG),
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
]
user32.GetMessageW.restype = ctypes.c_int

user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = ctypes.wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT

user32.PostThreadMessageW.argtypes = [
    ctypes.wintypes.DWORD,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
user32.PostThreadMessageW.restype = ctypes.wintypes.BOOL

user32.EnumDisplayMonitors.argtypes = [
    HDC,
    ctypes.POINTER(RECT),
    MONITORENUMPROC,
    ctypes.wintypes.LPARAM,
]
user32.EnumDisplayMonitors.restype = ctypes.wintypes.BOOL

user32.GetMonitorInfoW.argtypes = [
    HMONITOR,
    ctypes.POINTER(MONITORINFO),
]
user32.GetMonitorInfoW.restype = ctypes.wintypes.BOOL

user32.keybd_event.argtypes = [
    ctypes.wintypes.BYTE,
    ctypes.wintypes.BYTE,
    ctypes.wintypes.DWORD,
    ULONG_PTR,
]
user32.keybd_event.restype = None

user32.RegisterHotKey.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.c_int,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
]
user32.RegisterHotKey.restype = ctypes.wintypes.BOOL

user32.UnregisterHotKey.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.c_int,
]
user32.UnregisterHotKey.restype = ctypes.wintypes.BOOL

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = ctypes.wintypes.DWORD

HANDLER_ROUTINE = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.DWORD)
kernel32.SetConsoleCtrlHandler.argtypes = [HANDLER_ROUTINE, ctypes.wintypes.BOOL]
kernel32.SetConsoleCtrlHandler.restype = ctypes.wintypes.BOOL

CTRL_C_EVENT = 0
CTRL_BREAK_EVENT = 1
CTRL_CLOSE_EVENT = 2
CTRL_LOGOFF_EVENT = 5
CTRL_SHUTDOWN_EVENT = 6


@dataclass(frozen=True)
class Config:
    corner_zone_px: int
    rearm_distance_px: int
    retrigger_guard_distance_px: int
    dwell_ms: int
    cooldown_ms: int
    click_suppression_ms: int
    monitor_refresh_ms: int
    startup_delay_ms: int
    max_callback_errors: int


@dataclass(frozen=True)
class MonitorCorner:
    key: Tuple[int, int, int, int]
    left: int
    top: int
    right: int
    bottom: int

    def contains_active_zone(self, x: int, y: int, zone_px: int) -> bool:
        return (
            self.left <= x <= self.left + zone_px
            and self.top <= y <= self.top + zone_px
        )

    def contains_rearm_zone(self, x: int, y: int, zone_px: int, rearm_px: int) -> bool:
        return (
            self.left <= x <= self.left + zone_px + rearm_px
            and self.top <= y <= self.top + zone_px + rearm_px
        )


@dataclass
class CornerVisitState:
    inside: bool = False
    triggered: bool = False
    entry_ms: int = 0
    last_click_ms: int = 0


def preferred_python_executable(gui: bool) -> str:
    executable = os.path.abspath(sys.executable)
    directory = os.path.dirname(executable)
    filename = os.path.basename(executable).lower()

    if gui and filename == "python.exe":
        candidate = os.path.join(directory, "pythonw.exe")
        if os.path.exists(candidate):
            return candidate
    if not gui and filename == "pythonw.exe":
        candidate = os.path.join(directory, "python.exe")
        if os.path.exists(candidate):
            return candidate
    return executable


def quote_cmd(value: str) -> str:
    return subprocess.list2cmdline([value])


def ensure_runtime_dir() -> None:
    os.makedirs(RUNTIME_DIR, exist_ok=True)


class WindowsIntegration:
    def __init__(self) -> None:
        self.gui_python = preferred_python_executable(gui=True)
        self.console_python = preferred_python_executable(gui=False)
        self.script_path = os.path.abspath(__file__)
        self.recovery_script_path = RECOVERY_SCRIPT_PATH

    @staticmethod
    def ensure_log_file() -> None:
        ensure_runtime_dir()
        if os.path.exists(LOG_PATH):
            return
        with open(LOG_PATH, "a", encoding="utf-8"):
            pass

    def open_log_file(self) -> None:
        self.ensure_log_file()
        os.startfile(LOG_PATH)

    @staticmethod
    def open_readme() -> None:
        os.startfile(README_PATH)

    def is_startup_enabled(self) -> bool:
        return os.path.exists(STARTUP_SCRIPT_PATH)

    def enable_startup(self) -> None:
        os.makedirs(STARTUP_DIR, exist_ok=True)
        command = (
            f"@echo off\r\n"
            f"{quote_cmd(self.gui_python)} {quote_cmd(self.script_path)} --startup-launch\r\n"
        )
        with open(STARTUP_SCRIPT_PATH, "w", encoding="utf-8", newline="") as handle:
            handle.write(command)
        logging.info("Enabled startup launcher at %s", STARTUP_SCRIPT_PATH)

    def disable_startup(self) -> None:
        try:
            os.remove(STARTUP_SCRIPT_PATH)
            logging.info("Disabled startup launcher")
        except FileNotFoundError:
            pass

    def ensure_recovery_artifacts(self) -> None:
        ensure_runtime_dir()
        recovery_script = (
            f"@echo off\r\n"
            f"{quote_cmd(self.console_python)} {quote_cmd(self.script_path)} --panic-stop\r\n"
        )

        with open(FALLBACK_RECOVERY_SCRIPT_PATH, "w", encoding="utf-8", newline="") as handle:
            handle.write(recovery_script)

        target_path = FALLBACK_RECOVERY_SCRIPT_PATH
        try:
            os.makedirs(START_MENU_PROGRAMS_DIR, exist_ok=True)
            with open(RECOVERY_SCRIPT_PATH, "w", encoding="utf-8", newline="") as handle:
                handle.write(recovery_script)
            target_path = RECOVERY_SCRIPT_PATH
        except OSError:
            pass

        self.recovery_script_path = target_path


def write_pid_file() -> None:
    ensure_runtime_dir()
    with open(PID_PATH, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))


def remove_pid_file() -> None:
    try:
        os.remove(PID_PATH)
    except FileNotFoundError:
        pass


def panic_stop_running_instance() -> int:
    try:
        with open(PID_PATH, "r", encoding="utf-8") as handle:
            pid = int(handle.read().strip())
    except (FileNotFoundError, ValueError):
        return 1

    if pid == os.getpid():
        return 1

    try:
        os.kill(pid, signal.SIGTERM)
        return 0
    except OSError:
        completed = subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode


def install_console_ctrl_handler(handler: Callable[[int], None]) -> HANDLER_ROUTINE:
    relevant_events = {
        CTRL_C_EVENT,
        CTRL_BREAK_EVENT,
        CTRL_CLOSE_EVENT,
        CTRL_LOGOFF_EVENT,
        CTRL_SHUTDOWN_EVENT,
    }

    @HANDLER_ROUTINE
    def console_handler(ctrl_type: int) -> bool:
        if ctrl_type not in relevant_events:
            return False
        threading.Thread(target=handler, args=(int(ctrl_type),), daemon=True).start()
        return True

    if not kernel32.SetConsoleCtrlHandler(console_handler, True):
        raise ctypes.WinError(ctypes.get_last_error())
    return console_handler


class HotCornersEngine:
    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run
        self.state_lock = threading.Lock()
        self.monitor_callback = MONITORENUMPROC(self._monitor_enum_proc)

        self.config = self._load_config()
        self.config_mtime: Optional[float] = None
        self.monitors: List[MonitorCorner] = []
        self.states: Dict[Tuple[int, int, int, int], CornerVisitState] = {}
        self.last_position: Optional[Tuple[int, int]] = None
        self.last_global_trigger_ms = 0
        self.awaiting_corner_exit = False
        self.last_trigger_point: Optional[Tuple[int, int]] = None
        self.callback_error_count = 0
        self.failure_reason: Optional[str] = None

        self.running = False
        self.enabled = False
        self.threads: List[threading.Thread] = []
        self.state_change_callback: Optional[Callable[[], None]] = None
        self.quit_request_callback: Optional[Callable[[], None]] = None

        self.stop_event = threading.Event()
        self.trigger_event = threading.Event()
        self.action_queue: "queue.Queue[str]" = queue.Queue()
        self.hook_handle = HHOOK()
        self.hook_callback = HOOKPROC(self._mouse_proc)
        self.hook_thread_id = 0
        self.hotkey_thread_id = 0

    @staticmethod
    def _now_ms() -> int:
        return int(time.monotonic() * 1000)

    def _reset_runtime_state(self) -> None:
        self.stop_event = threading.Event()
        self.trigger_event = threading.Event()
        self.action_queue = queue.Queue()
        self.threads = []
        self.hook_handle = HHOOK()
        self.hook_thread_id = 0
        self.hotkey_thread_id = 0
        self.last_position = None
        self.last_global_trigger_ms = 0
        self.awaiting_corner_exit = False
        self.last_trigger_point = None
        self.callback_error_count = 0
        self.failure_reason = None

    def _load_config(self) -> Config:
        ensure_runtime_dir()
        values = dict(DEFAULTS)
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if not isinstance(loaded, dict):
                    raise ValueError("config root must be a JSON object")
                values.update(loaded)
            except Exception as exc:
                logging.warning("Ignoring invalid config file: %s", exc)

        validated = {}
        for key, default_value in DEFAULTS.items():
            lower, upper = CONFIG_BOUNDS[key]
            raw_value = values.get(key, default_value)
            try:
                parsed = int(raw_value)
            except (TypeError, ValueError):
                logging.warning("%s=%r is invalid, using default %s", key, raw_value, default_value)
                parsed = default_value
            if parsed < lower or parsed > upper:
                logging.warning(
                    "%s=%r is outside [%s, %s], using default %s",
                    key,
                    raw_value,
                    lower,
                    upper,
                    default_value,
                )
                parsed = default_value
            validated[key] = parsed

        return Config(**validated)

    def reload_config(self, force: bool = False) -> None:
        try:
            current_mtime = os.path.getmtime(CONFIG_PATH)
        except OSError:
            current_mtime = None

        if not force and current_mtime == self.config_mtime:
            return

        config = self._load_config()
        with self.state_lock:
            self.config = config
        self.config_mtime = current_mtime
        logging.info("Configuration loaded: %s", config)

    def ensure_config_file(self) -> None:
        ensure_runtime_dir()
        if os.path.exists(CONFIG_PATH):
            return
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(DEFAULTS, handle, indent=2)
            handle.write("\n")
        logging.info("Created default config file at %s", CONFIG_PATH)

    def open_config_file(self) -> None:
        self.ensure_config_file()
        os.startfile(CONFIG_PATH)

    def is_enabled(self) -> bool:
        with self.state_lock:
            return self.enabled

    def is_running(self) -> bool:
        with self.state_lock:
            return self.running

    def set_state_change_callback(self, callback: Optional[Callable[[], None]]) -> None:
        with self.state_lock:
            self.state_change_callback = callback

    def set_quit_request_callback(self, callback: Optional[Callable[[], None]]) -> None:
        with self.state_lock:
            self.quit_request_callback = callback

    def _notify_state_change(self) -> None:
        with self.state_lock:
            callback = self.state_change_callback
        if callback is not None:
            try:
                callback()
            except Exception:
                logging.exception("State change callback failed")

    def _notify_quit_requested(self) -> None:
        with self.state_lock:
            callback = self.quit_request_callback
        if callback is not None:
            try:
                callback()
            except Exception:
                logging.exception("Quit request callback failed")

    def status_text(self) -> str:
        with self.state_lock:
            if self.enabled and self.running:
                return "Enabled"
            if self.failure_reason:
                return f"Disabled ({self.failure_reason})"
            return "Disabled"

    def startup_delay_seconds(self) -> float:
        with self.state_lock:
            return self.config.startup_delay_ms / 1000.0

    def enable(self) -> None:
        with self.state_lock:
            if self.enabled:
                return
            self.enabled = True
        self.start()
        self._notify_state_change()

    def disable(self, reason: str = "disabled") -> None:
        with self.state_lock:
            self.enabled = False
            self.failure_reason = reason
        self.stop()
        self._notify_state_change()

    def start(self) -> None:
        with self.state_lock:
            if self.running:
                return
            self.enabled = True
            self.running = True

        self._reset_runtime_state()
        self.reload_config(force=True)
        self._refresh_monitors()

        self.threads = [
            threading.Thread(target=self._action_loop, name="action-worker", daemon=True),
            threading.Thread(target=self._trigger_loop, name="trigger-worker", daemon=True),
            threading.Thread(target=self._monitor_refresh_loop, name="monitor-refresh", daemon=True),
            threading.Thread(target=self._run_hotkey_loop, name="emergency-hotkey", daemon=True),
            threading.Thread(target=self._run_hook_loop, name="mouse-hook", daemon=True),
        ]
        for thread in self.threads:
            thread.start()
        logging.info("Hot corners engine started")

    def stop(self) -> None:
        self._request_stop(join=True)

    def shutdown(self) -> None:
        with self.state_lock:
            self.enabled = False
            self.failure_reason = None
        self._request_stop(join=True)
        self._notify_state_change()

    def _request_stop(self, join: bool) -> None:
        with self.state_lock:
            if not self.running:
                return

        self.stop_event.set()
        self.trigger_event.set()
        self.action_queue.put("stop")
        if self.hook_thread_id:
            user32.PostThreadMessageW(self.hook_thread_id, WM_QUIT, 0, 0)
        if self.hotkey_thread_id:
            user32.PostThreadMessageW(self.hotkey_thread_id, WM_QUIT, 0, 0)

        if join:
            current = threading.current_thread()
            deadline = time.monotonic() + 1.0
            for thread in self.threads:
                if thread is current:
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                thread.join(timeout=remaining)
            with self.state_lock:
                self.running = False
            logging.info("Hot corners engine stopped")
            self._notify_state_change()

    def _request_stop_async(self) -> None:
        threading.Thread(target=self._request_stop, args=(True,), daemon=True).start()

    def _monitor_enum_proc(self, monitor_handle, _hdc, _rect, _lparam):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor_handle, ctypes.byref(info)):
            return True

        rect = info.rcMonitor
        monitor = MonitorCorner(
            key=(rect.left, rect.top, rect.right, rect.bottom),
            left=rect.left,
            top=rect.top,
            right=rect.right,
            bottom=rect.bottom,
        )
        self._enumerated_monitors.append(monitor)
        return True

    def _enumerate_monitors(self) -> List[MonitorCorner]:
        self._enumerated_monitors: List[MonitorCorner] = []
        if not user32.EnumDisplayMonitors(None, None, self.monitor_callback, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        return sorted(self._enumerated_monitors, key=lambda item: (item.top, item.left))

    def _refresh_monitors(self) -> None:
        monitors = self._enumerate_monitors()
        with self.state_lock:
            if monitors == self.monitors:
                return
            existing_states = self.states
            self.monitors = monitors
            self.states = {
                monitor.key: existing_states.get(monitor.key, CornerVisitState())
                for monitor in monitors
            }
        logging.info("Active monitor topology: %s", [monitor.key for monitor in monitors])

    def _record_callback_fault(self, exc: Exception) -> None:
        should_disable = False
        with self.state_lock:
            self.callback_error_count += 1
            count = self.callback_error_count
            limit = self.config.max_callback_errors
            should_disable = count >= limit
        logging.exception("Mouse hook callback failed (%s/%s): %s", count, limit, exc)
        if should_disable:
            with self.state_lock:
                self.enabled = False
                self.failure_reason = "hook fault"
            self._request_stop_async()
            self._notify_state_change()

    def _find_monitor_for_point(self, x: int, y: int, config: Config) -> Optional[MonitorCorner]:
        for monitor in self.monitors:
            if monitor.contains_active_zone(x, y, config.corner_zone_px):
                return monitor
        return None

    def _is_in_any_rearm_zone(self, x: int, y: int, config: Config) -> bool:
        for monitor in self.monitors:
            if monitor.contains_rearm_zone(x, y, config.corner_zone_px, config.rearm_distance_px):
                return True
        return False

    @staticmethod
    def _has_left_trigger_origin(
        x: int,
        y: int,
        trigger_point: Optional[Tuple[int, int]],
        minimum_distance_px: int,
    ) -> bool:
        if trigger_point is None:
            return True
        dx = x - trigger_point[0]
        dy = y - trigger_point[1]
        return (dx * dx) + (dy * dy) >= (minimum_distance_px * minimum_distance_px)

    def _update_corner_states(self, message: int, x: int, y: int, now_ms: int) -> None:
        with self.state_lock:
            if not self.enabled:
                return

            config = self.config
            self.last_position = (x, y)
            current_monitor = self._find_monitor_for_point(x, y, config)
            current_key = current_monitor.key if current_monitor else None

            if self.awaiting_corner_exit:
                if self._is_in_any_rearm_zone(x, y, config):
                    return
                if not self._has_left_trigger_origin(
                    x,
                    y,
                    self.last_trigger_point,
                    config.retrigger_guard_distance_px,
                ):
                    return
                self.awaiting_corner_exit = False
                self.last_trigger_point = None
                for state in self.states.values():
                    state.inside = False
                    state.triggered = False

            for monitor in self.monitors:
                state = self.states.setdefault(monitor.key, CornerVisitState())
                if monitor.key == current_key:
                    continue
                if state.inside and not monitor.contains_rearm_zone(
                    x,
                    y,
                    config.corner_zone_px,
                    config.rearm_distance_px,
                ):
                    state.inside = False
                    state.triggered = False

            if current_monitor is None:
                return

            state = self.states.setdefault(current_monitor.key, CornerVisitState())
            if message in BUTTON_DOWN_MESSAGES:
                state.last_click_ms = now_ms
                state.entry_ms = now_ms
                state.inside = True
                state.triggered = False
            elif message == WM_MOUSEMOVE and not state.inside:
                state.inside = True
                state.entry_ms = now_ms
                state.triggered = False

        self.trigger_event.set()

    def _mouse_proc(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            try:
                data = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                self._update_corner_states(
                    int(w_param),
                    int(data.pt.x),
                    int(data.pt.y),
                    self._now_ms(),
                )
            except Exception as exc:
                self._record_callback_fault(exc)

        return user32.CallNextHookEx(self.hook_handle, n_code, w_param, l_param)

    def _run_hook_loop(self) -> None:
        try:
            self.hook_thread_id = kernel32.GetCurrentThreadId()
            self.hook_handle = user32.SetWindowsHookExW(WH_MOUSE_LL, self.hook_callback, None, 0)
            if not self.hook_handle:
                raise ctypes.WinError(ctypes.get_last_error())
            logging.info("Mouse hook installed")

            msg = MSG()
            while not self.stop_event.is_set():
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == -1:
                    raise ctypes.WinError(ctypes.get_last_error())
                if result == 0 or msg.message == WM_QUIT:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as exc:
            logging.exception("Hook loop failed: %s", exc)
            with self.state_lock:
                self.enabled = False
                self.failure_reason = "hook loop failed"
            self._request_stop_async()
            self._notify_state_change()
        finally:
            if self.hook_handle:
                user32.UnhookWindowsHookEx(self.hook_handle)
                self.hook_handle = HHOOK()
                logging.info("Mouse hook removed")

    def _run_hotkey_loop(self) -> None:
        self.hotkey_thread_id = kernel32.GetCurrentThreadId()
        disable_registered = user32.RegisterHotKey(
            None,
            EMERGENCY_DISABLE_HOTKEY_ID,
            MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT,
            VK_F12,
        )
        quit_registered = user32.RegisterHotKey(
            None,
            EMERGENCY_QUIT_HOTKEY_ID,
            MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT,
            VK_F11,
        )
        if not disable_registered:
            logging.warning("Failed to register emergency hotkey %s", EMERGENCY_DISABLE_HOTKEY_TEXT)
        else:
            logging.info("Emergency disable hotkey registered: %s", EMERGENCY_DISABLE_HOTKEY_TEXT)
        if not quit_registered:
            logging.warning("Failed to register emergency hotkey %s", EMERGENCY_QUIT_HOTKEY_TEXT)
        else:
            logging.info("Emergency quit hotkey registered: %s", EMERGENCY_QUIT_HOTKEY_TEXT)
        if not disable_registered and not quit_registered:
            return

        try:
            msg = MSG()
            while not self.stop_event.is_set():
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == -1:
                    raise ctypes.WinError(ctypes.get_last_error())
                if result == 0 or msg.message == WM_QUIT:
                    break
                if msg.message != WM_HOTKEY:
                    continue
                if msg.wParam == EMERGENCY_DISABLE_HOTKEY_ID:
                    logging.warning("Emergency disable hotkey triggered")
                    self.disable("emergency hotkey")
                elif msg.wParam == EMERGENCY_QUIT_HOTKEY_ID:
                    logging.warning("Emergency quit hotkey triggered")
                    self.shutdown()
                    self._notify_quit_requested()
        except Exception as exc:
            logging.exception("Emergency hotkey loop failed: %s", exc)
        finally:
            if disable_registered:
                user32.UnregisterHotKey(None, EMERGENCY_DISABLE_HOTKEY_ID)
            if quit_registered:
                user32.UnregisterHotKey(None, EMERGENCY_QUIT_HOTKEY_ID)

    def _monitor_refresh_loop(self) -> None:
        while not self.stop_event.is_set():
            with self.state_lock:
                interval_seconds = max(self.config.monitor_refresh_ms / 1000.0, 0.25)
            if self.stop_event.wait(interval_seconds):
                break
            try:
                self.reload_config()
                self._refresh_monitors()
            except Exception as exc:
                logging.exception("Monitor refresh failed: %s", exc)

    def _trigger_loop(self) -> None:
        while not self.stop_event.is_set():
            self.trigger_event.wait(timeout=0.05)
            self.trigger_event.clear()

            with self.state_lock:
                if not self.enabled:
                    continue

                now_ms = self._now_ms()
                config = self.config
                if now_ms - self.last_global_trigger_ms < config.cooldown_ms:
                    continue

                should_trigger = False
                for monitor in self.monitors:
                    state = self.states.setdefault(monitor.key, CornerVisitState())
                    if not state.inside or state.triggered:
                        continue
                    if now_ms - state.entry_ms < config.dwell_ms:
                        continue
                    if now_ms - state.last_click_ms < config.click_suppression_ms:
                        continue
                    state.triggered = True
                    self.last_global_trigger_ms = now_ms
                    self.awaiting_corner_exit = True
                    self.last_trigger_point = self.last_position
                    should_trigger = True
                    break

            if should_trigger:
                self.action_queue.put("trigger")

    def _action_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                item = self.action_queue.get(timeout=0.25)
            except queue.Empty:
                continue

            if item == "stop":
                return

            try:
                if self.dry_run:
                    logging.info("Dry run: would trigger Win+Tab")
                else:
                    self._fire_task_view()
                    logging.info("Triggered Win+Tab")
            except Exception as exc:
                logging.exception("Trigger action failed: %s", exc)

    def _fire_task_view(self) -> None:
        user32.keybd_event(VK_LWIN, 0, 0, 0)
        user32.keybd_event(VK_TAB, 0, 0, 0)
        user32.keybd_event(VK_TAB, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)


class TrayController:
    def __init__(
        self,
        engine: HotCornersEngine,
        integration: WindowsIntegration,
        auto_quit_after: Optional[float],
    ) -> None:
        self.engine = engine
        self.integration = integration
        self.auto_quit_after = auto_quit_after
        self.icon = None

    def run(self) -> None:
        import pystray

        self.engine.set_state_change_callback(self._handle_engine_state_change)
        self.engine.set_quit_request_callback(self._handle_quit_request)
        self.icon = pystray.Icon(
            "HotCornerPy",
            self._build_icon_image(),
            self._title(),
            menu=pystray.Menu(
                pystray.MenuItem(self._toggle_text, self._toggle_enabled),
                pystray.MenuItem(self._startup_text, self._toggle_startup),
                pystray.MenuItem("Reload Config", self._reload_config),
                pystray.MenuItem("Open Config File", self._open_config),
                pystray.MenuItem("Open Log File", self._open_logs),
                pystray.MenuItem("Open README", self._open_readme),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._quit),
            ),
        )

        if self.auto_quit_after is not None:
            threading.Thread(target=self._auto_quit, name="tray-auto-quit", daemon=True).start()

        self.icon.run()

    def _auto_quit(self) -> None:
        time.sleep(self.auto_quit_after)
        if self.icon is not None:
            self._quit(self.icon)

    def _title(self) -> str:
        return f"HotCornerPy ({self.engine.status_text()})"

    @staticmethod
    def _build_icon_image():
        from PIL import Image, ImageDraw

        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = (0, 130, 90, 255)
        draw.rectangle([0, 0, 36, 9], fill=color)
        draw.rectangle([0, 0, 9, 36], fill=color)
        return image

    def _refresh_ui(self, icon) -> None:
        icon.title = self._title()
        icon.update_menu()

    def _handle_engine_state_change(self) -> None:
        if self.icon is not None:
            self._refresh_ui(self.icon)

    def _handle_quit_request(self) -> None:
        self.engine.set_state_change_callback(None)
        self.engine.set_quit_request_callback(None)
        if self.icon is not None:
            self.icon.stop()

    def _toggle_text(self, _item) -> str:
        if self.engine.is_enabled():
            return "Disable Hot Corners"
        return "Enable Hot Corners"

    def _startup_text(self, _item) -> str:
        if self.integration.is_startup_enabled():
            return "Disable Startup"
        return "Enable Startup"

    def _toggle_enabled(self, icon, _item=None) -> None:
        if self.engine.is_enabled():
            self.engine.disable("disabled by user")
        else:
            self.engine.enable()
        self._refresh_ui(icon)

    def _toggle_startup(self, icon, _item=None) -> None:
        if self.integration.is_startup_enabled():
            self.integration.disable_startup()
        else:
            self.integration.enable_startup()
        self._refresh_ui(icon)

    def _reload_config(self, icon, _item=None) -> None:
        self.engine.reload_config(force=True)
        self._refresh_ui(icon)

    def _open_config(self, icon, _item=None) -> None:
        try:
            self.engine.open_config_file()
        except Exception as exc:
            logging.exception("Failed to open config file: %s", exc)
        self._refresh_ui(icon)

    def _open_logs(self, icon, _item=None) -> None:
        try:
            self.integration.open_log_file()
        except Exception as exc:
            logging.exception("Failed to open log file: %s", exc)
        self._refresh_ui(icon)

    def _open_readme(self, icon, _item=None) -> None:
        try:
            self.integration.open_readme()
        except Exception as exc:
            logging.exception("Failed to open README: %s", exc)
        self._refresh_ui(icon)

    def _quit(self, icon, _item=None) -> None:
        self.shutdown()

    def shutdown(self) -> None:
        self.engine.shutdown()
        self.engine.set_state_change_callback(None)
        self.engine.set_quit_request_callback(None)
        if self.icon is not None:
            self.icon.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Windows hot corners")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="capture events and evaluate triggers without sending Win+Tab",
    )
    parser.add_argument(
        "--no-tray",
        action="store_true",
        help="run without the tray UI for development/debugging",
    )
    parser.add_argument(
        "--startup-launch",
        action="store_true",
        help="run as an automatic startup launch and honor startup delay",
    )
    parser.add_argument(
        "--panic-stop",
        action="store_true",
        help="kill the currently running HotCornerPy process using its PID file",
    )
    parser.add_argument(
        "--run-for-seconds",
        type=float,
        default=None,
        help="stop automatically after the given number of seconds",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="enable verbose console logging",
    )
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    ensure_runtime_dir()
    handlers = [
        logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"),
        logging.StreamHandler(),
    ]
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


def run_console_mode(engine: HotCornersEngine, run_for_seconds: Optional[float]) -> None:
    engine.enable()
    started_at = time.monotonic()
    try:
        while engine.is_running():
            if run_for_seconds is not None and time.monotonic() - started_at >= run_for_seconds:
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        logging.info("Ctrl+C received, stopping")
    finally:
        engine.shutdown()


def main() -> None:
    args = parse_args()

    if args.panic_stop:
        raise SystemExit(panic_stop_running_instance())

    configure_logging(args.verbose)
    integration = WindowsIntegration()
    integration.ensure_recovery_artifacts()
    write_pid_file()

    tray: Optional[TrayController] = None
    shutdown_started = threading.Event()
    console_ctrl_handler: Optional[HANDLER_ROUTINE] = None

    try:
        engine = HotCornersEngine(dry_run=args.dry_run)

        def request_shutdown(reason: int) -> None:
            if shutdown_started.is_set():
                return
            shutdown_started.set()
            logging.info("Received shutdown request %s, shutting down", reason)
            if tray is not None:
                tray.shutdown()
            else:
                engine.shutdown()

        def handle_shutdown_signal(signum, _frame) -> None:
            request_shutdown(int(signum))

        try:
            console_ctrl_handler = install_console_ctrl_handler(request_shutdown)
        except Exception as exc:
            logging.warning("Failed to install console control handler: %s", exc)

        signal.signal(signal.SIGINT, handle_shutdown_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handle_shutdown_signal)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, handle_shutdown_signal)

        if args.startup_launch:
            delay_seconds = engine.startup_delay_seconds()
            if delay_seconds > 0:
                logging.info("Startup launch delay: %.1f seconds", delay_seconds)
                time.sleep(delay_seconds)

        if args.no_tray:
            run_console_mode(engine, args.run_for_seconds)
            return

        engine.enable()
        tray = TrayController(
            engine=engine,
            integration=integration,
            auto_quit_after=args.run_for_seconds,
        )
        try:
            tray.run()
        except KeyboardInterrupt:
            handle_shutdown_signal(signal.SIGINT, None)
    finally:
        if console_ctrl_handler is not None:
            try:
                kernel32.SetConsoleCtrlHandler(console_ctrl_handler, False)
            except Exception:
                pass
        remove_pid_file()


if __name__ == "__main__":
    main()
