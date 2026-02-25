from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from grbl_streamer import GrblStreamer


class CncConnectionError(Exception):
    pass


@dataclass
class JogSettings:
    step_mm: float = 1.0
    feed_mm_min: float = 1000.0


@dataclass
class ZSettings:
    safe_z: float = 5.0      # height to rapid at before XY moves
    touch_z: float = 0.0     # height to move down to at reference point
    touch_feed: float = 200  # feed for Z touch move


class CncController:
    """
    Thin wrapper around grbl-streamer providing just enough control for:
      - Connecting / disconnecting to a GRBL controller
      - Manual jogging in X/Y/Z
      - Zeroing all axes
      - Moving to absolute reference points and touching Z
    """

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None) -> None:
        self._grbl: Optional[GrblStreamer] = None
        self._connected: bool = False
        self._log_cb = log_callback

        self.jog_settings = JogSettings()
        self.z_settings = ZSettings()

    # Connection -----------------------------------------------------------------
    def connect(self, port: str, baud: int = 115200) -> None:
        if self._connected:
            self.disconnect()

        try:
            self._grbl = GrblStreamer(self._on_event)
            self._grbl.setup_logging()
            self._grbl.cnect(port, baud)
            self._grbl.poll_start()
            self._connected = True
            self._log(f"Connected to GRBL on {port} @ {baud}")
        except Exception as exc:  # pragma: no cover - defensive
            self._grbl = None
            self._connected = False
            raise CncConnectionError(f"Failed to connect to GRBL: {exc}") from exc

    def disconnect(self) -> None:
        if self._grbl is not None:
            try:
                self._grbl.disconnect()
            except Exception:
                pass
        self._grbl = None
        self._connected = False
        self._log("Disconnected from GRBL")

    @property
    def is_connected(self) -> bool:
        return self._connected and self._grbl is not None

    # Low-level send -------------------------------------------------------------
    def _send(self, line: str) -> None:
        if not self.is_connected:
            raise CncConnectionError("Not connected to any GRBL controller.")
        # grbl-streamer adds newline internally
        self._log(f"SEND: {line}")
        self._grbl.send_immediately(line)

    def _log(self, msg: str) -> None:
        if self._log_cb:
            self._log_cb(msg)

    # Jogging --------------------------------------------------------------------
    def jog(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> None:
        if abs(dx) < 1e-9 and abs(dy) < 1e-9 and abs(dz) < 1e-9:
            return

        feed = max(self.jog_settings.feed_mm_min, 1.0)

        # Relative rapid move then restore absolute mode
        self._send("G91")  # incremental
        cmd = "G0"
        if abs(dx) > 1e-9:
            cmd += f" X{dx:.3f}"
        if abs(dy) > 1e-9:
            cmd += f" Y{dy:.3f}"
        if abs(dz) > 1e-9:
            cmd += f" Z{dz:.3f}"
        cmd += f" F{feed:.0f}"
        self._send(cmd)
        self._send("G90")  # back to absolute

    def zero_all(self) -> None:
        # Set current location as work origin
        self._send("G92 X0 Y0 Z0")
        self._log("Zeroed X, Y, Z using G92.")

    # Reference point moves ------------------------------------------------------
    def move_to_reference_point(self, x: float, y: float) -> None:
        """
        Move to an absolute XY reference point and perform a Z touch-down using
        configured Z settings.
        """
        zs = self.z_settings

        self._send("G90")  # absolute mode

        # Raise to safe Z first
        self._send(f"G0 Z{zs.safe_z:.3f}")

        # Rapid in XY to reference point
        self._send(f"G0 X{x:.3f} Y{y:.3f}")

        # Move Z down to touch height at controlled feed
        self._send(f"G1 Z{zs.touch_z:.3f} F{zs.touch_feed:.0f}")

    # Event callback from grbl-streamer -----------------------------------------
    def _on_event(self, eventstring, *data) -> None:  # pragma: no cover - passthrough
        # For now we simply surface a few events as log lines.
        if eventstring in {"on_error", "on_alarm", "on_log"}:
            self._log(f"{eventstring}: {data!r}")

