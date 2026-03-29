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
      │  _on_serial_data : read → forward to pymodbus via master_fd
      │  _on_pty_data    : read from master_fd → write to serial
      │                    → DISABLE serial reader for ECHO_WINDOW_S
      │                    → call_later: flush serial buffer + re-enable
      ↓
    [ /dev/pts/X ] (PTY slave)
      │
    pymodbus / StartAsyncSerialServer

Echo suppression strategy
-------------------------
Pattern-matching against ``sent_buffer`` is inherently racy in asyncio:
the echo can arrive on the physical port before ``_on_pty_data`` has had
a chance to populate ``sent_buffer``.

Instead we use the **reader-pause** approach — identical to what the
pymodbus *client* does internally with ``reset_input_buffer()``:

1. ``_on_pty_data`` writes bytes to the physical RS485 port.
2. Immediately removes the asyncio reader on the serial fd
   (so any echo bytes are ignored at the event-loop level).
3. Schedules ``_reenable_serial_reader`` via ``loop.call_later``
   after ``ECHO_WINDOW_S``.
4. ``_reenable_serial_reader`` flushes stale bytes from the OS serial
   input buffer (``reset_input_buffer``), then re-registers the reader.

This guarantees that echo bytes arriving within the window are never
delivered to pymodbus — without any byte-pattern matching.

Timing at 9600 baud 8E1 (≈ 1.146 ms/byte):
- 5-byte frame           ≈  5.7 ms transmission
- 8-byte FC16 response   ≈  9.2 ms
- USB echo round-trip    ≈  1–15 ms
- ECHO_WINDOW_S = 0.025  →  25 ms — catches echo, well below Modbus
  inter-frame silence (3.5 chars ≈ 4 ms + THOR processing ≥ 50 ms).
"""
from __future__ import annotations

import asyncio
import logging
import os

import serial

_LOGGER = logging.getLogger(__name__)


class AsyncEchoFilterProxy:
    """PTY-based echo filter for RS485 serial ports.

    Usage::

        proxy = AsyncEchoFilterProxy(
            "/dev/ttyACM2", baudrate=9600, bytesize=8, parity="E", stopbits=1
        )
        slave_path = proxy.start(asyncio.get_running_loop())
        # Pass slave_path to StartAsyncSerialServer instead of "/dev/ttyACM2"
        # ...
        proxy.stop()
    """

    #: Seconds after TX during which the serial reader is paused.
    #: Echo round-trip at 9600 baud over USB-serial ≈ 5–15 ms.
    #: 25 ms provides margin without blocking legitimate THOR requests
    #: (Modbus inter-frame gap + THOR processing ≥ ~50 ms).
    ECHO_WINDOW_S: float = 0.025

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

        self._loop: asyncio.AbstractEventLoop | None = None
        self._serial_reader_active: bool = False
        self._pending_reenable: asyncio.TimerHandle | None = None

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self, loop: asyncio.AbstractEventLoop) -> str:
        """Start the proxy.

        Returns the PTY slave device path to pass to ``StartAsyncSerialServer``
        instead of the physical port.

        Raises ``ImportError`` on non-Linux platforms (``pty`` unavailable).
        """
        import pty  # Linux stdlib — deferred so module is importable on Windows
        import tty  # Linux stdlib

        self._loop = loop

        # Open real serial port non-blocking.
        self._ser = serial.Serial(
            self._real_port,
            baudrate=self._baudrate,
            bytesize=self._bytesize,
            parity=self._parity,
            stopbits=self._stopbits,
            timeout=0,  # Non-blocking read
        )

        # Create PTY pair. Configure slave as raw (no terminal echo) before
        # closing it, so the setting persists when pyserial reopens it.
        master_fd, slave_fd = pty.openpty()
        tty.setraw(slave_fd)  # disable kernel terminal echo on the slave
        self._master_fd = master_fd
        self._slave_path = os.ttyname(slave_fd)
        os.close(slave_fd)

        # Register asyncio reader for physical serial port.
        loop.add_reader(self._ser.fileno(), self._on_serial_data)
        self._serial_reader_active = True

        # Register asyncio reader for PTY master (pymodbus writes via slave).
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
        if self._pending_reenable is not None:
            self._pending_reenable.cancel()
            self._pending_reenable = None

        if self._loop:
            if self._ser and self._serial_reader_active:
                try:
                    self._loop.remove_reader(self._ser.fileno())
                except Exception:
                    pass
            if self._master_fd >= 0:
                try:
                    self._loop.remove_reader(self._master_fd)
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
        """Physical serial port has data → forward to pymodbus via PTY master."""
        if self._ser is None:
            return
        try:
            data = self._ser.read(256)
        except Exception as exc:
            _LOGGER.error("EchoFilterProxy serial read: %s", exc)
            return
        if not data:
            return

        _LOGGER.debug("EchoFilterProxy serial→pty  %d bytes", len(data))
        try:
            os.write(self._master_fd, data)
        except OSError as exc:
            _LOGGER.error("EchoFilterProxy PTY write: %s", exc)

    def _on_pty_data(self) -> None:
        """pymodbus wrote response to PTY slave → forward to physical serial.

        After writing, the serial reader is paused for ``ECHO_WINDOW_S`` so
        that the hardware TX echo is silently discarded at OS level.
        """
        if self._ser is None:
            return
        try:
            data = os.read(self._master_fd, 256)
        except OSError as exc:
            _LOGGER.error("EchoFilterProxy PTY read: %s", exc)
            return
        if not data:
            return

        _LOGGER.debug(
            "EchoFilterProxy pty→serial  %d bytes  (pausing reader for %d ms)",
            len(data),
            int(self.ECHO_WINDOW_S * 1000),
        )

        # Write to physical serial port.
        try:
            self._ser.write(data)
        except Exception as exc:
            _LOGGER.error("EchoFilterProxy serial write: %s", exc)
            return

        # ── Pause serial reader for echo window ───────────────────────────
        # Remove the serial fd reader so that any echo bytes arriving during
        # ECHO_WINDOW_S are never delivered to _on_serial_data / pymodbus.
        assert self._loop is not None
        if self._serial_reader_active:
            try:
                self._loop.remove_reader(self._ser.fileno())
                self._serial_reader_active = False
            except Exception:
                pass

        # Cancel any previous pending re-enable (can happen if multiple
        # responses arrive before the window expires).
        if self._pending_reenable is not None:
            self._pending_reenable.cancel()

        self._pending_reenable = self._loop.call_later(
            self.ECHO_WINDOW_S, self._reenable_serial_reader
        )

    def _reenable_serial_reader(self) -> None:
        """Called after echo window expires — flush echo bytes and resume reading."""
        self._pending_reenable = None
        if self._ser is None or self._loop is None:
            return

        # Flush any echo bytes that accumulated in the OS serial input buffer
        # during the pause window.  This mirrors what pymodbus client does
        # internally with reset_input_buffer() before reading a response.
        try:
            waiting = self._ser.in_waiting
            if waiting:
                discarded = self._ser.read(waiting)
                _LOGGER.debug(
                    "EchoFilterProxy flushed %d echo byte(s) after window", len(discarded)
                )
        except Exception as exc:
            _LOGGER.warning("EchoFilterProxy flush error: %s", exc)

        # Re-register the serial reader for normal operation.
        if not self._serial_reader_active:
            try:
                self._loop.add_reader(self._ser.fileno(), self._on_serial_data)
                self._serial_reader_active = True
            except Exception as exc:
                _LOGGER.error("EchoFilterProxy failed to re-add serial reader: %s", exc)

