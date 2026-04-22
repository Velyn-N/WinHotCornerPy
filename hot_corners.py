"""
GNOME-style top-left hot corners for Windows.

This version uses a global low-level mouse hook, tracks the top-left corner of
every active monitor, and adapts to monitor layout changes while running.

Configuration is loaded from `hot_corners_config.json` in the same directory if
the file exists. Any missing or invalid values fall back to safe defaults.

Exit with Ctrl+C.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "hot_corners_config.json",
)
LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "hot_corners.log",
)

WH_MOUSE_LL = 14
HC_ACTION = 0

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_QUIT = 0x0012

KEYEVENTF_KEYUP = 0x0002
VK_LWIN = 0x5B
VK_TAB = 0x09

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t
HHOOK = ctypes.c_void_p
HMONITOR = ctypes.c_void_p
HDC = ctypes.c_void_p

BUTTON_DOWN_MESSAGES = (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN)
BUTTON_UP_MESSAGES = (WM_LBUTTONUP, WM_RBUTTONUP, WM_MBUTTONUP)

DEFAULTS = {
    "corner_zone_px": 2,
    "rearm_distance_px": 40,
    "retrigger_guard_distance_px": 160,
    "dwell_ms": 20,
    "cooldown_ms": 400,
    "click_suppression_ms": 150,
    "monitor_refresh_ms": 300000,
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

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = ctypes.wintypes.DWORD


@dataclass(frozen=True)
class Config:
    corner_zone_px: int
    rearm_distance_px: int
    retrigger_guard_distance_px: int
    dwell_ms: int
    cooldown_ms: int
    click_suppression_ms: int
    monitor_refresh_ms: int
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


class HotCornersApp:
    def __init__(self, dry_run: bool, run_for_seconds: Optional[float]) -> None:
        self.dry_run = dry_run
        self.run_for_seconds = run_for_seconds
        self.stop_event = threading.Event()
        self.trigger_event = threading.Event()
        self.action_queue: "queue.Queue[str]" = queue.Queue()
        self.state_lock = threading.Lock()
        self.monitor_callback = MONITORENUMPROC(self._monitor_enum_proc)

        self.config = self._load_config()
        self.config_mtime: Optional[float] = None
        self.callback_error_count = 0
        self.feature_enabled = True

        self.monitors: List[MonitorCorner] = []
        self.states: Dict[Tuple[int, int, int, int], CornerVisitState] = {}
        self.last_position: Optional[Tuple[int, int]] = None
        self.last_global_trigger_ms = 0
        self.awaiting_corner_exit = False
        self.last_trigger_point: Optional[Tuple[int, int]] = None

        self.hook_handle = HHOOK()
        self.hook_callback = HOOKPROC(self._mouse_proc)
        self.hook_thread_id = 0

    def _load_config(self) -> Config:
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

    def _refresh_config_if_needed(self, force: bool = False) -> None:
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
        monitors = sorted(self._enumerated_monitors, key=lambda item: (item.top, item.left))
        return monitors

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

    def _disable_feature(self, reason: str) -> None:
        with self.state_lock:
            if not self.feature_enabled:
                return
            self.feature_enabled = False
        logging.error("Disabling hot corners: %s", reason)
        self.stop_event.set()
        self.trigger_event.set()
        self.action_queue.put("stop")
        if self.hook_thread_id:
            user32.PostThreadMessageW(self.hook_thread_id, WM_QUIT, 0, 0)

    def _record_callback_fault(self, exc: Exception) -> None:
        should_disable = False
        with self.state_lock:
            self.callback_error_count += 1
            count = self.callback_error_count
            limit = self.config.max_callback_errors
            should_disable = count >= limit
        logging.exception("Mouse hook callback failed (%s/%s): %s", count, limit, exc)
        if should_disable:
            self._disable_feature("too many callback failures")

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
            if not self.feature_enabled:
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
            self._disable_feature("hook loop failed")
        finally:
            if self.hook_handle:
                user32.UnhookWindowsHookEx(self.hook_handle)
                self.hook_handle = HHOOK()
                logging.info("Mouse hook removed")

    def _monitor_refresh_loop(self) -> None:
        while not self.stop_event.is_set():
            with self.state_lock:
                interval_seconds = max(self.config.monitor_refresh_ms / 1000.0, 0.25)
            if self.stop_event.wait(interval_seconds):
                break
            try:
                self._refresh_config_if_needed()
                self._refresh_monitors()
            except Exception as exc:
                logging.exception("Monitor refresh failed: %s", exc)

    def _trigger_loop(self) -> None:
        while not self.stop_event.is_set():
            self.trigger_event.wait(timeout=0.05)
            self.trigger_event.clear()

            with self.state_lock:
                if not self.feature_enabled:
                    continue

                now_ms = self._now_ms()
                config = self.config

                if now_ms - self.last_global_trigger_ms < config.cooldown_ms:
                    continue

                trigger_key: Optional[Tuple[int, int, int, int]] = None
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
                    trigger_key = monitor.key
                    break

            if trigger_key is not None:
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

    def run(self) -> None:
        self._refresh_config_if_needed(force=True)
        self._refresh_monitors()

        logging.info(
            "Starting hot corners (%s mode)",
            "dry-run" if self.dry_run else "live",
        )

        threads = [
            threading.Thread(target=self._action_loop, name="action-worker", daemon=True),
            threading.Thread(target=self._trigger_loop, name="trigger-worker", daemon=True),
            threading.Thread(target=self._monitor_refresh_loop, name="monitor-refresh", daemon=True),
            threading.Thread(target=self._run_hook_loop, name="mouse-hook", daemon=True),
        ]

        for thread in threads:
            thread.start()

        started_at = time.monotonic()
        try:
            while not self.stop_event.is_set():
                if self.run_for_seconds is not None:
                    if time.monotonic() - started_at >= self.run_for_seconds:
                        logging.info("Run duration reached, stopping")
                        break

                hook_thread = threads[-1]
                if not hook_thread.is_alive():
                    logging.error("Hook thread stopped unexpectedly")
                    break

                time.sleep(0.2)
        except KeyboardInterrupt:
            logging.info("Ctrl+C received, stopping")
        finally:
            self.stop_event.set()
            self.trigger_event.set()
            self.action_queue.put("stop")
            if self.hook_thread_id:
                user32.PostThreadMessageW(self.hook_thread_id, WM_QUIT, 0, 0)

            for thread in threads:
                thread.join(timeout=2.0)

            logging.info("Hot corners stopped")

    @staticmethod
    def _now_ms() -> int:
        return int(time.monotonic() * 1000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Windows hot corners")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="capture events and evaluate triggers without sending Win+Tab",
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
    handlers = [
        logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"),
        logging.StreamHandler(),
    ]
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    app = HotCornersApp(dry_run=args.dry_run, run_for_seconds=args.run_for_seconds)
    app.run()


if __name__ == "__main__":
    main()
