"""Declare an X11 window's EWMH type, which Qt has no public API for (desktop.x11_window_kind).

libX11 through ctypes, no new dependency. Linux only, and only under the `xcb` Qt platform, on
the display in $DISPLAY (the one Qt uses). The type must be set before the window is mapped:
`QWidget.winId()` creates the X11 window without mapping it, then `show()` maps it.
"""

import ctypes
import ctypes.util

XA_ATOM = 4
PROP_MODE_REPLACE = 0
ANY_PROPERTY_TYPE = 0

DOCK = "_NET_WM_WINDOW_TYPE_DOCK"


def _libx11() -> ctypes.CDLL:
    """The system's libX11. A packaged build may not bundle it, and the dynamic loader finds the
    system one by its soname even when LD_LIBRARY_PATH points into the bundle."""
    library = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
    library.XOpenDisplay.restype = ctypes.c_void_p
    library.XOpenDisplay.argtypes = [ctypes.c_char_p]
    library.XInternAtom.restype = ctypes.c_ulong
    library.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    library.XChangeProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    library.XGetWindowProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_long,
        ctypes.c_long,
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    library.XGetAtomName.restype = ctypes.c_void_p
    library.XGetAtomName.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    for name in ("XFlush", "XCloseDisplay", "XFree"):
        getattr(library, name).argtypes = [ctypes.c_void_p]
    return library


def set_window_type(window: int, type_name: str = DOCK) -> str | None:
    """Replace the window's `_NET_WM_WINDOW_TYPE` with `type_name`. Returns why it failed, or
    None. Never raises: without it the panel still shows, the WM just treats it as a window."""
    try:
        x11 = _libx11()
    except OSError as error:
        return f"no libX11 ({error})"
    display = x11.XOpenDisplay(None)
    if not display:
        return "cannot open the X display"
    try:
        prop = x11.XInternAtom(display, b"_NET_WM_WINDOW_TYPE", 0)
        value = ctypes.c_ulong(x11.XInternAtom(display, type_name.encode(), 0))
        x11.XChangeProperty(
            display, window, prop, XA_ATOM, 32, PROP_MODE_REPLACE, ctypes.byref(value), 1
        )
        x11.XFlush(display)
    finally:
        x11.XCloseDisplay(display)
    return None


def window_types(window: int) -> list[str]:
    """The window's `_NET_WM_WINDOW_TYPE` atoms by name (for tests and the log)."""
    x11 = _libx11()
    display = x11.XOpenDisplay(None)
    if not display:
        return []
    try:
        prop = x11.XInternAtom(display, b"_NET_WM_WINDOW_TYPE", 0)
        actual_type, actual_format = ctypes.c_ulong(), ctypes.c_int()
        count, after, data = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_void_p()
        x11.XGetWindowProperty(
            display,
            window,
            prop,
            0,
            32,
            0,
            ANY_PROPERTY_TYPE,
            ctypes.byref(actual_type),
            ctypes.byref(actual_format),
            ctypes.byref(count),
            ctypes.byref(after),
            ctypes.byref(data),
        )
        if not data.value:
            return []
        try:
            # Format-32 properties come back as C longs, whatever the platform's word size.
            atoms = ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[: count.value]
        finally:
            x11.XFree(data)
        names = []
        for atom in atoms:
            pointer = x11.XGetAtomName(display, atom)
            names.append(ctypes.string_at(pointer).decode())
            x11.XFree(pointer)
        return names
    finally:
        x11.XCloseDisplay(display)
