"""AsyncIO-based RS485 Echo Filter Proxy for HA Green / HAOS Linux.

Inserts a transparent PTY shim between pymodbus and the physical serial
port.  Any TX echo bytes looped back by the Waveshare CH348L hardware
adapter are stripped from the RX stream before pymodbus sees them.

Requires: Python stdlib ``pty`` module (Linux only; not available on
Windows; safe to import on Windows — failure deferred to ``start()``).

Architecture::

    THOR (bus master)
      │
    [ /dev/ttyACM2 ] ←── RS485 bus  +  hardware TX echo
      │
    [ AsyncEchoFilterProxy ]
      │  _on_serial_data : read → filter_echo → os.write(master_fd)
      │  _on_pty_data    : os.read(master_fd) → serial.write + track
      ↓
    [ /dev/pts/X ] (PTY slave)
      │
    pymodbus / StartAsyncSerialServer

Timing at 9600 baud 8E1 (11 bits/byte ≈ 1.146 ms/byte):

- FC04 response (2 floats = ~11 bytes) ≈ 12.6 ms transmission time
- ECHO_WINDOW_S = 0.060 (60 ms) — comfortable USB-serial latency margin

After our response frame has been transmitted the bus is idle until
THOR sends the next request.  All bytes arriving within ECHO_WINDOW_S
of our last write are treated as echo and discarded; bytes arriving
after the window pass through unchanged.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

import serial

_LOGGER = logging.getLogger(__name__)


class AsyncEchoFilterProxy:
    """PTY-based echo filter for RS485 serial ports.

    Usage::

        proxy = AsyncEchoFilterProxy(
            "/dev/ttyACM2", baudrate=9600, bytesize=8, parity="E", stopbits=1
        )
        slave_path = proxy.start(asyncio.get_event_loop())
        # Pass slave_path to StartAsyncSerialServer instead of "/dev/ttyACM2"
        # ...
        proxy.stop()
    """

    #: Seconds after last TX during which received bytes are treated as echo.
    ECHO_WINDOW_S: float = 0.060

    def __init__(
        self,
        real_port: str,
        baudrate: int = 9600,
        bytesize: int = 8,
        parity: str = "E",
        stopbits: int = 1,
    ) -> None:
        self._real_port = real_port
        self._baudrate = baudrate
        self._bytesize = bytesize
        self._parity = parity
        self._stopbits = stopbits

        self._ser: serial.Serial | None = None
        self._master_fd: int = -1
        self._slave_path: str = ""

        self._sent_buffer = bytearray()
        self._sent_time: float = 0.0

        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self, loop: asyncio.AbstractEventLoop) -> str:
        """Start the proxy.

        Returns the PTY slave device path to pass to ``StartAsyncSerialServer``
        instead of the physical port.

        Raises ``ImportError`` on non-Linux platforms (``pty`` unavailable).
        """
        import pty  # Linux stdlib — deferred so module is importable on Windows

        self._loop = loop

        # Open real serial port non-blocking.  No RS485Settings here — the
        # CH348L handles DE/RE automatically; we only need raw byte access.
        self._ser = serial.Serial(
            self._real_port,
            baudrate=self._baudrate,
            bytesize=self._bytesize,
            parity=self._parity,
            stopbits=self._stopbits,
            timeout=0,  # Non-blocking read
        )

        # Create PTY pair.  Keep master_fd; close slave_fd immediately —
        # the PTY stays alive as long as master_fd is open, and pyserial
        # will reopen the slave via its filesystem path.
        master_fd, slave_fd = pty.openpty()
        self._master_fd = master_fd
        self._slave_path = os.ttyname(slave_fd)
        os.close(slave_fd)

        # Register asyncio edge-triggered readers on the HA event loop
        loop.add_reader(self._ser.fileno(), self._on_serial_data)
        loop.add_reader(self._master_fd, self._on_pty_data)

        _LOGGER.info(
            "EchoFilterProxy started: %s → %s  (echo_window=%d ms)",
            self._real_port,
            self._slave_path,
            int(self.ECHO_WINDOW_S * 1000),
        )
        return self._slave_path

    def stop(self) -> None:
        """Remove asyncio readers and release file descriptors."""
        if self._loop:
            for fd_getter in (
                lambda: self._ser.fileno() if self._ser else -1,
                lambda: self._master_fd,
            ):
                fd = fd_getter()
                if fd >= 0:
                    try:
                        self._loop.remove_reader(fd)
                    except Exception:
                        pass

        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

        if self._master_fd >= 0:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = -1

        _LOGGER.info("EchoFilterProxy stopped.")

    # ── Asyncio callbacks ──────────────────────────────────────────────────

    def _on_serial_data(self) -> None:
        """Data on real serial port → filter echo → forward to PTY master."""
        if self._ser is None:
            return
        try:
            data = self._ser.read(256)
        except Exception as exc:
            _LOGGER.error("EchoFilterProxy serial read: %s", exc)
            return
        if not data:
            return

        filtered = self._filter_echo(data)
        _LOGGER.debug(
            "EchoFilterProxy serial→pty  raw=%d  filtered=%d bytes",
            len(data),
            len(filtered),
        )
        if filtered:
            try:
                os.write(self._master_fd, filtered)
            except OSError as exc:
                _LOGGER.error("EchoFilterProxy PTY write: %s", exc)

    def _on_pty_data(self) -> None:
        """pymodbus wrote to PTY slave → read from master, track + send to serial."""
        try:
            data = os.read(self._master_fd, 256)
        except OSError as exc:
            _LOGGER.error("EchoFilterProxy PTY read: %s", exc)
            return
        if not data:
            return

        # Record outgoing bytes for echo matching
        self._sent_buffer.extend(data)
        self._sent_time = time.monotonic()

        _LOGGER.debug(
            "EchoFilterProxy pty→serial  %d bytes  (sent_buffer=%d bytes)",
            len(data),
            len(self._sent_buffer),
        )
        if self._ser is None:
            return
        try:
            self._ser.write(data)
        except Exception as exc:
            _LOGGER.error("EchoFilterProxy serial write: %s", exc)

    # ── Echo filtering ─────────────────────────────────────────────────────

    def _filter_echo(self, data: bytes) -> bytes:
        """Remove TX echo bytes from *data*.

        Matches received bytes in order against ``_sent_buffer``.  A byte is
        treated as echo (and discarded) when it matches the next expected echo
        byte AND the last TX was within ``ECHO_WINDOW_S`` seconds.

        Handles fragmented echo delivery: partial matches consume the
        front of ``_sent_buffer`` and accumulate across multiple calls.

        On half-duplex RS485 the bus is idle between our response and the
        next request from THOR, so any byte arriving within the window is
        guaranteed to be echo — no legitimate data is discarded.
        """
        elapsed = time.monotonic() - self._sent_time

        # Outside echo window — clear stale buffer, pass data through
        if elapsed > self.ECHO_WINDOW_S or not self._sent_buffer:
            self._sent_buffer.clear()
            return data

        result = bytearray()
        i = 0  # number of sent_buffer bytes matched so far

        for byte in data:
            if i < len(self._sent_buffer) and byte == self._sent_buffer[i]:
                i += 1  # Echo byte matched → discard
            else:
                result.append(byte)  # Not echo → keep

        del self._sent_buffer[:i]  # Consume matched prefix
        return bytes(result)
