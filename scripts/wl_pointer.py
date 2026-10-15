"""A virtual mouse for a wlroots compositor (zwlr_virtual_pointer_v1), standard library only.

`wlrctl pointer …` creates a pointer device, moves it and destroys it at once, so the seat loses
its pointer and XWayland its cursor right after. This keeps one device alive for as long as the
object lives, and talks the Wayland wire protocol directly (no pywayland to install in CI).
Used by scripts/e2e_wayland.py.
"""

import os
import socket
import struct
import time

BTN_LEFT = 0x110
DISPLAY_ID = 1


def _string(text: str) -> bytes:
    data = text.encode() + b"\0"
    return struct.pack("<I", len(data)) + data + b"\0" * (-len(data) % 4)


class VirtualPointer:
    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        path = os.path.join(os.environ["XDG_RUNTIME_DIR"], os.environ["WAYLAND_DISPLAY"])
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(path)
        self.buffer = b""
        self.next_id = 2
        registry = self._new_id()
        self._send(DISPLAY_ID, 1, struct.pack("<I", registry))  # wl_display.get_registry
        globals_: dict[str, tuple[int, int]] = {}
        for object_id, opcode, payload in self._roundtrip():
            if object_id == registry and opcode == 0:  # wl_registry.global
                name, length = struct.unpack_from("<II", payload)
                interface = payload[8 : 8 + length - 1].decode()
                (version,) = struct.unpack_from("<I", payload, 8 + length + (-length % 4))
                globals_[interface] = (name, version)
        manager_name = "zwlr_virtual_pointer_manager_v1"
        if manager_name not in globals_:
            raise RuntimeError(f"the compositor has no {manager_name}")
        name, _ = globals_[manager_name]
        manager = self._new_id()
        self._send(  # wl_registry.bind(name, interface, version, new_id)
            registry,
            0,
            struct.pack("<I", name) + _string(manager_name) + struct.pack("<II", 1, manager),
        )
        self.pointer = self._new_id()
        # create_virtual_pointer(seat = null: the default seat, new_id)
        self._send(manager, 0, struct.pack("<II", 0, self.pointer))
        self._roundtrip()

    def move_to(self, x: int, y: int) -> None:
        self._send(
            self.pointer, 1, struct.pack("<IIIII", self._now(), x, y, self.width, self.height)
        )
        self._frame()

    def click(self) -> None:
        for state in (1, 0):  # pressed, released
            self._send(self.pointer, 2, struct.pack("<III", self._now(), BTN_LEFT, state))
            self._frame()
            time.sleep(0.05)

    def close(self) -> None:
        self._send(self.pointer, 8, b"")  # destroy
        self._roundtrip()
        self.sock.close()

    def _frame(self) -> None:
        self._send(self.pointer, 4, b"")
        self._roundtrip()

    def _now(self) -> int:
        return int(time.monotonic() * 1000) & 0xFFFFFFFF

    def _new_id(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def _send(self, object_id: int, opcode: int, payload: bytes) -> None:
        header = struct.pack("<II", object_id, ((8 + len(payload)) << 16) | opcode)
        self.sock.sendall(header + payload)

    def _roundtrip(self) -> list[tuple[int, int, bytes]]:
        """wl_display.sync, then every event up to its callback's `done`."""
        callback = self._new_id()
        self._send(DISPLAY_ID, 0, struct.pack("<I", callback))
        events = []
        while True:
            while len(self.buffer) < 8:
                self._receive()
            object_id, size_opcode = struct.unpack_from("<II", self.buffer)
            size, opcode = size_opcode >> 16, size_opcode & 0xFFFF
            while len(self.buffer) < size:
                self._receive()
            payload, self.buffer = self.buffer[8:size], self.buffer[size:]
            if object_id == DISPLAY_ID and opcode == 0:  # wl_display.error
                _, code, length = struct.unpack_from("<III", payload)
                message = payload[12 : 12 + length - 1].decode(errors="replace")
                raise RuntimeError(f"Wayland error {code}: {message}")
            if object_id == callback:
                return events
            events.append((object_id, opcode, payload))

    def _receive(self) -> None:
        chunk = self.sock.recv(65536)
        if not chunk:
            raise RuntimeError("the compositor closed the connection")
        self.buffer += chunk
