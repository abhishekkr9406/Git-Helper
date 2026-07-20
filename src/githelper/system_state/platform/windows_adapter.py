"""Windows adapter.

Handles WM_QUERYENDSESSION, WM_ENDSESSION, WM_POWERBROADCAST via Qt native event filters.
"""

from typing import Callable
from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QByteArray
import ctypes

# Windows Message Constants
WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016
WM_POWERBROADCAST = 0x021B
PBT_APMSUSPEND = 0x0004
PBT_APMRESUMEAUTOMATIC = 0x0012


class WindowsNativeEventFilter(QAbstractNativeEventFilter):
    """Intercepts Windows native messages before they reach Qt."""
    
    def __init__(
        self,
        on_shutdown_requested: Callable[[], None],
        on_sleep: Callable[[], None],
        on_resume: Callable[[], None]
    ):
        super().__init__()
        self.on_shutdown_requested = on_shutdown_requested
        self.on_sleep = on_sleep
        self.on_resume = on_resume
        self._shutdown_handled = False

    def nativeEventFilter(self, eventType: QByteArray, message: int) -> tuple[bool, int]:
        """Process native Windows messages."""
        if eventType != b"windows_generic_MSG":
            return False, 0
            
        # Parse the MSG structure. We only need the message and wParam.
        # MSG struct: (hwnd, message, wParam, lParam, time, pt)
        # message pointer points to the MSG struct memory.
        try:
            # We can use ctypes to cast the memory address to an array
            # message is actually a pointer to a MSG struct.
            # In PySide6, 'message' is a sip.voidptr or int. Let's cast it safely.
            msg_ptr = ctypes.cast(int(message), ctypes.POINTER(ctypes.c_uint))
            # The second field (index 1) is the message type
            msg_type = msg_ptr[1]
            # The third field (index 2 or 2/3 depending on 32/64 bit) is wParam.
            # A safer way to read it:
            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", ctypes.c_void_p),
                    ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_void_p),
                    ("lParam", ctypes.c_void_p),
                    ("time", ctypes.c_uint),
                    ("pt_x", ctypes.c_long),
                    ("pt_y", ctypes.c_long),
                ]
            msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
            
            if msg.message == WM_QUERYENDSESSION:
                if not self._shutdown_handled:
                    self.on_shutdown_requested()
                    self._shutdown_handled = True
                # Return True (non-zero) to allow shutdown
                return True, 1
                
            elif msg.message == WM_ENDSESSION:
                if msg.wParam and not self._shutdown_handled:
                    self.on_shutdown_requested()
                    self._shutdown_handled = True
                return False, 0
                
            elif msg.message == WM_POWERBROADCAST:
                if msg.wParam == PBT_APMSUSPEND:
                    self.on_sleep()
                elif msg.wParam == PBT_APMRESUMEAUTOMATIC:
                    self.on_resume()
                return True, 1
                
        except Exception:
            # Native parsing failed, just ignore
            pass
            
        return False, 0


def install_windows_filter(
    app: QCoreApplication,
    on_shutdown: Callable[[], None],
    on_sleep: Callable[[], None],
    on_resume: Callable[[], None]
) -> WindowsNativeEventFilter:
    """Install the Windows native event filter on the Qt application."""
    evt_filter = WindowsNativeEventFilter(on_shutdown, on_sleep, on_resume)
    app.installNativeEventFilter(evt_filter)
    return evt_filter
