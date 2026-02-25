from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import matplotlib

matplotlib.use("Qt5Agg")  # Works with PyQt6
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
import numpy as np  # noqa: E402

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy

from gcode_parser import GCodeMove, ToolpathSummary
from reference_calc import ReferencePoint


@dataclass
class CanvasState:
    toolpath: Optional[ToolpathSummary] = None
    reference_points: Optional[List[ReferencePoint]] = None
    clearance: float = 5.0


class ToolpathCanvas(FigureCanvas):
    """
    Matplotlib-backed canvas embedded in PyQt6.
    Handles zoom, pan, and drawing of:
      - Toolpath (rapid / cut / arcs)
      - Bounding box
      - Center marker
      - Reference points
    """

    def __init__(self, parent=None) -> None:
        self.fig: Figure = Figure()
        super().__init__(self.fig)
        self.setParent(parent)

        self.ax = self.fig.add_subplot(111)
        self.ax.set_aspect("equal", adjustable="datalim")
        self.ax.set_facecolor("white")
        self.fig.patch.set_facecolor("#f0f0f0")

        self.state = CanvasState()

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.updateGeometry()

        self._connect_events()
        self._draw_empty()

    # Public API -----------------------------------------------------------------
    def set_toolpath(self, summary: ToolpathSummary) -> None:
        self.state.toolpath = summary
        self._redraw()

    def set_reference_points(self, points: List[ReferencePoint], clearance: float) -> None:
        self.state.reference_points = points
        self.state.clearance = clearance
        self._redraw()

    def clear(self) -> None:
        self.state = CanvasState()
        self._draw_empty()

    # Internal drawing -----------------------------------------------------------
    def _draw_empty(self) -> None:
        self.ax.clear()
        self.ax.text(
            0.5,
            0.5,
            "Load a G-code file to begin",
            transform=self.ax.transAxes,
            ha="center",
            va="center",
            fontsize=12,
            color="gray",
        )
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.draw_idle()

    def _redraw(self) -> None:
        self.ax.clear()
        if not self.state.toolpath:
            self._draw_empty()
            return

        tp = self.state.toolpath
        pts = tp.points

        # Compute extents and padding
        min_x, max_x = tp.min_x, tp.max_x
        min_y, max_y = tp.min_y, tp.max_y

        width = max_x - min_x
        height = max_y - min_y
        pad_x = width * 0.1 if width > 0 else 10
        pad_y = height * 0.1 if height > 0 else 10

        self.ax.set_xlim(min_x - pad_x, max_x + pad_x)
        self.ax.set_ylim(min_y - pad_y, max_y + pad_y)

        # Draw grid
        self.ax.grid(True, linestyle="--", color="#e0e0e0", linewidth=0.5)

        # Draw bounding box
        bbox_x = [min_x, max_x, max_x, min_x, min_x]
        bbox_y = [min_y, min_y, max_y, max_y, min_y]
        self.ax.plot(
            bbox_x,
            bbox_y,
            linestyle="--",
            color="gray",
            linewidth=1.0,
            label="Bounding Box",
        )

        # Draw toolpath by move type
        for move in tp.moves:
            xs = [move.start[0], move.end[0]]
            ys = [move.start[1], move.end[1]]
            if move.mode == "G0":
                self.ax.plot(
                    xs,
                    ys,
                    linestyle=(0, (4, 4)),
                    color="#cccccc",
                    linewidth=1.0,
                )
            else:  # G1/G2/G3 cutting moves
                self.ax.plot(
                    xs,
                    ys,
                    linestyle="-",
                    color="#0066cc",
                    linewidth=2.0,
                )

        # Center crosshair
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        cross_size = max(width, height) * 0.03
        self.ax.plot(
            [cx - cross_size, cx + cross_size],
            [cy, cy],
            color="green",
            linewidth=1.5,
        )
        self.ax.plot(
            [cx, cx],
            [cy - cross_size, cy + cross_size],
            color="green",
            linewidth=1.5,
            label="Center",
        )

        # Reference points
        if self.state.reference_points:
            for p in self.state.reference_points:
                self._draw_reference_point(p, (cx, cy))

        self.ax.set_xlabel(f"X ({tp.units})")
        self.ax.set_ylabel(f"Y ({tp.units})")
        self.ax.set_title("G-code Toolpath")

        self.ax.legend(loc="upper right", fontsize=8)
        self.fig.tight_layout()
        self.draw_idle()

    def _draw_reference_point(
        self, point: ReferencePoint, center: Tuple[float, float]
    ) -> None:
        px, py = point.x, point.y
        cx, cy = center

        # Line from point to center
        self.ax.plot(
            [px, cx],
            [py, cy],
            linestyle=(0, (4, 4)),
            color="red",
            linewidth=1.0,
        )

        # Red circle marker
        self.ax.scatter(
            [px],
            [py],
            s=80,
            color="red",
            edgecolor="black",
            zorder=5,
        )

        # Label near point
        label = f"{point.id}"
        dx = (px - cx) * 0.05
        dy = (py - cy) * 0.05
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            dx, dy = 0.0, 0.0
        self.ax.text(
            px + dx,
            py + dy,
            label,
            fontsize=9,
            color="black",
            ha="center",
            va="center",
            bbox=dict(boxstyle="circle,pad=0.2", fc="white", ec="black", lw=0.5),
        )

    # Interaction ----------------------------------------------------------------
    def _connect_events(self) -> None:
        self.mpl_connect("scroll_event", self._on_scroll)
        self.mpl_connect("button_press_event", self._on_button_press)
        self.mpl_connect("button_release_event", self._on_button_release)
        self.mpl_connect("motion_notify_event", self._on_mouse_move)

        self._is_panning = False
        self._last_pan_xy: Optional[Tuple[float, float]] = None

    def _on_scroll(self, event) -> None:
        if event.inaxes != self.ax:
            return
        scale_factor = 1.1 if event.button == "up" else 0.9

        xdata = event.xdata
        ydata = event.ydata
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        new_width = (xlim[1] - xlim[0]) * scale_factor
        new_height = (ylim[1] - ylim[0]) * scale_factor

        rel_x = (xdata - xlim[0]) / (xlim[1] - xlim[0])
        rel_y = (ydata - ylim[0]) / (ylim[1] - ylim[0])

        new_xmin = xdata - rel_x * new_width
        new_xmax = xdata + (1 - rel_x) * new_width
        new_ymin = ydata - rel_y * new_height
        new_ymax = ydata + (1 - rel_y) * new_height

        self.ax.set_xlim(new_xmin, new_xmax)
        self.ax.set_ylim(new_ymin, new_ymax)
        self.draw_idle()

    def _on_button_press(self, event) -> None:
        if event.button == 1 and event.inaxes == self.ax:
            self._is_panning = True
            self._last_pan_xy = (event.xdata, event.ydata)

    def _on_button_release(self, event) -> None:
        self._is_panning = False
        self._last_pan_xy = None

    def _on_mouse_move(self, event) -> None:
        if self._is_panning and event.inaxes == self.ax and self._last_pan_xy:
            dx = self._last_pan_xy[0] - event.xdata
            dy = self._last_pan_xy[1] - event.ydata

            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()

            self.ax.set_xlim(xlim[0] + dx, xlim[1] + dx)
            self.ax.set_ylim(ylim[0] + dy, ylim[1] + dy)

            self._last_pan_xy = (event.xdata, event.ydata)
            self.draw_idle()

