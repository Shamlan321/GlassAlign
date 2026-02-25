from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np


@dataclass
class GCodeMove:
    """
    Represents a single movement in the XY plane for visualization and analysis.
    """

    start: Tuple[float, float]
    end: Tuple[float, float]
    mode: str  # "G0", "G1", "G2", "G3"


@dataclass
class ToolpathSummary:
    points: np.ndarray  # shape (N, 2)
    moves: List[GCodeMove]
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    units: str  # "mm" or "inch"
    total_moves: int
    has_arcs: bool


class GCodeParserError(Exception):
    pass


@dataclass
class Segment:
    type: str  # 'LINE' or 'ARC'
    start: Tuple[float, float, float]
    end: Tuple[float, float, float]
    params: Dict[str, float]
    line_number: int
    original_text: str


def _arc_points_from_center(
    start: Tuple[float, float, float],
    end: Tuple[float, float, float],
    cx: float,
    cy: float,
    radius: float,
    cw: bool,
) -> List[Tuple[float, float]]:
    """
    Helper to generate arc points from an explicit circle center.
    Ported from offset_calc's geometry helper.
    """
    x1, y1 = start[:2]
    x2, y2 = end[:2]

    start_angle = math.atan2(y1 - cy, x1 - cx)
    end_angle = math.atan2(y2 - cy, x2 - cx)

    if cw:
        if end_angle > start_angle:
            end_angle -= 2 * math.pi
    else:
        if end_angle < start_angle:
            end_angle += 2 * math.pi

    angle_diff = abs(end_angle - start_angle)
    steps = max(int(angle_diff * max(radius, 1.0) * 2), 4)

    angles = np.linspace(start_angle, end_angle, steps + 1)
    pts: List[Tuple[float, float]] = []
    for ang in angles:
        px = cx + radius * math.cos(ang)
        py = cy + radius * math.sin(ang)
        pts.append((px, py))
    return pts


def _arc_to_points_from_segment(seg: Segment) -> List[Tuple[float, float]]:
    """
    Approximates an arc Segment with a series of line segments.
    Mirrors the behaviour of offset_calc's arc_to_points_from_segment.
    """
    x1, y1 = seg.start[:2]
    x2, y2 = seg.end[:2]
    I = seg.params.get("I", 0.0)
    J = seg.params.get("J", 0.0)
    R = seg.params.get("R", 0.0)
    cw = seg.params.get("CW", 0.0) == 1.0

    # Prefer I/J when available (or when R is not meaningful)
    if abs(I) > 1e-9 or abs(J) > 1e-9 or abs(R) < 1e-9:
        cx = x1 + I
        cy = y1 + J
        radius = math.hypot(I, J)
        if radius < 1e-9:
            # Degenerate, fall back to straight line
            return [seg.start[:2], seg.end[:2]]
        return _arc_points_from_center(seg.start, seg.end, cx, cy, radius, cw)

    # --- R-mode arc: reconstruct circle center ---
    dx = x2 - x1
    dy = y2 - y1
    d = math.hypot(dx, dy)
    if d < 1e-9:
        # Start and end coincide, nothing to draw
        return [seg.start[:2], seg.end[:2]]

    Rabs = abs(R)
    # Ensure R is large enough for the chord
    if d / 2.0 > Rabs:
        Rabs = d / 2.0

    mx = (x1 + x2) / 2.0
    my = (y1 + y2) / 2.0

    h_sq = max(Rabs * Rabs - (d / 2.0) ** 2, 0.0)
    h = math.sqrt(h_sq)

    # Unit perpendicular to chord
    nx = -dy / d
    ny = dx / d

    # Two possible centers
    candidates = [
        (mx + nx * h, my + ny * h),
        (mx - nx * h, my - ny * h),
    ]

    best_points: Optional[List[Tuple[float, float]]] = None
    best_angle: Optional[float] = None

    for cx, cy in candidates:
        pts = _arc_points_from_center(seg.start, seg.end, cx, cy, Rabs, cw)
        sx, sy = pts[0]
        ex, ey = pts[-1]
        sa = math.atan2(sy - cy, sx - cx)
        ea = math.atan2(ey - cy, ex - cx)
        if cw:
            if ea > sa:
                ea -= 2 * math.pi
        else:
            if ea < sa:
                ea += 2 * math.pi
        sweep = abs(ea - sa)

        # Prefer smaller sweep (typical CAM arcs)
        if best_angle is None or sweep < best_angle:
            best_angle = sweep
            best_points = pts

    return best_points or [seg.start[:2], seg.end[:2]]


class GCodeParser:
    """
    G-code parser ported from offset_calc:
    - Modal G0/G1/G2/G3 tracking
    - G90/G91 absolute/relative
    - G20/G21 units
    - Robust regex-based line parsing
    - Arc interpolation using I/J or R
    """

    def __init__(self) -> None:
        self.segments: List[Segment] = []
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.absolute_mode = True  # G90 default
        self.current_motion_mode: Optional[str] = None  # 'G0', 'G1', 'G2', 'G3'
        self.units: str = "mm"

        # Same regex as offset_calc
        self.command_pattern = re.compile(r"([GXYZIJR])\s*(-?\d*\.?\d+)")

    # Public API -----------------------------------------------------------------
    def parse_file(self, lines: Iterable[str]) -> ToolpathSummary:
        self._reset_state()

        raw_lines = list(lines)
        for i, line in enumerate(raw_lines):
            self._parse_line(i, line)

        if not self.segments:
            raise GCodeParserError("No movement commands found in file.")

        # Keep only segments on dominant Z plane (cutting plane)
        filtered = self._filter_segments_by_z(self.segments)

        # Bounding box should be based on non-rapid moves where possible
        bbox_segments = [s for s in filtered if s.params.get("MOTION") not in ("G0", "G00")]
        if not bbox_segments:
            bbox_segments = filtered

        if not bbox_segments:
            raise GCodeParserError("No movement commands found in file.")

        # Convert segments to continuous polyline and GCodeMove list
        all_points: List[Tuple[float, float]] = []
        moves: List[GCodeMove] = []

        first_seg = bbox_segments[0]
        last_xy = first_seg.start[:2]
        all_points.append(last_xy)

        for seg in bbox_segments:
            motion = seg.params.get("MOTION", "G1")

            if seg.type == "ARC":
                pts = _arc_to_points_from_segment(seg)
            else:
                pts = [seg.start[:2], seg.end[:2]]

            for pt in pts[1:]:
                moves.append(GCodeMove(start=last_xy, end=pt, mode=motion))
                all_points.append(pt)
                last_xy = pt

        pts_arr = np.array(all_points, dtype=float)
        min_x = float(np.min(pts_arr[:, 0]))
        max_x = float(np.max(pts_arr[:, 0]))
        min_y = float(np.min(pts_arr[:, 1]))
        max_y = float(np.max(pts_arr[:, 1]))

        if max_x - min_x == 0 or max_y - min_y == 0:
            raise GCodeParserError("Shape has zero dimensions.")

        has_arcs = any(seg.type == "ARC" for seg in filtered)

        return ToolpathSummary(
            points=pts_arr,
            moves=moves,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
            units=self.units,
            total_moves=len(moves),
            has_arcs=has_arcs,
        )

    # Internal helpers -----------------------------------------------------------
    def _reset_state(self) -> None:
        self.segments = []
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.absolute_mode = True
        self.current_motion_mode = None
        self.units = "mm"

    def _parse_line(self, line_index: int, raw_line: str) -> None:
        original_line = raw_line.strip()
        if not original_line:
            return

        # Remove comments: (...) and ';'
        clean_line = re.sub(r"\(.*?\)", "", original_line).split(";", 1)[0].strip()
        if not clean_line:
            return

        upper = clean_line.upper()
        if "G20" in upper:
            self.units = "inch"
        elif "G21" in upper:
            self.units = "mm"

        commands = self._parse_line_commands(clean_line)

        # Modal changes
        if "G90" in upper:
            self.absolute_mode = True
        elif "G91" in upper:
            self.absolute_mode = False

        # Determine motion command
        explicit_motion: Optional[str] = None
        if "G0" in commands:
            explicit_motion = "G0"
        if "G00" in commands:
            explicit_motion = "G00"
        if "G1" in commands:
            explicit_motion = "G1"
        if "G01" in commands:
            explicit_motion = "G01"
        if "G2" in commands:
            explicit_motion = "G2"
        if "G02" in commands:
            explicit_motion = "G02"
        if "G3" in commands:
            explicit_motion = "G3"
        if "G03" in commands:
            explicit_motion = "G03"

        if explicit_motion:
            self.current_motion_mode = explicit_motion

        has_coords = any(k in commands for k in ["X", "Y", "Z", "I", "J", "R"])

        active_motion = (
            explicit_motion
            if explicit_motion
            else (self.current_motion_mode if has_coords else None)
        )
        if not active_motion:
            return

        start_point = (self.current_x, self.current_y, self.current_z)

        x_val = commands.get("X")
        y_val = commands.get("Y")
        z_val = commands.get("Z")

        target_x = self.current_x
        target_y = self.current_y
        target_z = self.current_z

        if self.absolute_mode:
            if x_val is not None:
                target_x = x_val
            if y_val is not None:
                target_y = y_val
            if z_val is not None:
                target_z = z_val
        else:
            if x_val is not None:
                target_x += x_val
            if y_val is not None:
                target_y += y_val
            if z_val is not None:
                target_z += z_val

        end_point = (target_x, target_y, target_z)

        # Update state
        self.current_x, self.current_y, self.current_z = end_point

        seg_type = "LINE"
        params: Dict[str, float] = {}

        # Normalize G00->G0, etc for logic
        mode_normalized = active_motion
        if "0" in mode_normalized and len(mode_normalized) > 2:
            mode_normalized = mode_normalized.replace("0", "")
        if mode_normalized in ("G00", "G01", "G02", "G03"):
            mode_normalized = mode_normalized[:2]

        if mode_normalized in ["G2", "G3"]:
            seg_type = "ARC"
            params["I"] = commands.get("I", 0.0)
            params["J"] = commands.get("J", 0.0)
            params["R"] = commands.get("R", 0.0)
            params["CW"] = 1.0 if mode_normalized == "G2" else 0.0

        params["MOTION"] = mode_normalized

        seg = Segment(
            type=seg_type,
            start=start_point,
            end=end_point,
            params=params,
            line_number=line_index + 1,
            original_text=original_line,
        )
        self.segments.append(seg)

    def _parse_line_commands(self, line: str) -> Dict[str, float]:
        """Extract X, Y, Z, I, J, R and G codes from a line."""
        commands: Dict[str, float] = {}
        matches = self.command_pattern.findall(line)
        for letter, value in matches:
            try:
                commands[letter] = float(value)
            except ValueError:
                continue

        upper_line = line.upper()
        if "G0 " in upper_line or "G00" in upper_line:
            commands["G0"] = True
        elif "G1 " in upper_line or "G01" in upper_line:
            commands["G1"] = True
        elif "G2 " in upper_line or "G02" in upper_line:
            commands["G2"] = True
        elif "G3 " in upper_line or "G03" in upper_line:
            commands["G3"] = True
        if line.endswith("G0") or line.endswith("G00"):
            commands["G0"] = True
        if line.endswith("G1") or line.endswith("G01"):
            commands["G1"] = True

        g_matches = re.findall(r"G(\d+)", upper_line)
        for g_val in g_matches:
            try:
                g_int = int(g_val)
            except ValueError:
                continue
            if g_int == 0:
                commands["G0"] = True
            if g_int == 1:
                commands["G1"] = True
            if g_int == 2:
                commands["G2"] = True
            if g_int == 3:
                commands["G3"] = True
            if g_int == 90:
                commands["G90"] = True
            if g_int == 91:
                commands["G91"] = True

        return commands

    @staticmethod
    def _filter_segments_by_z(segments: List[Segment]) -> List[Segment]:
        if not segments:
            return []

        from collections import Counter

        z_samples: List[float] = []
        for s in segments:
            z_samples.append(round(s.start[2], 3))
            z_samples.append(round(s.end[2], 3))
        z_mode, _ = Counter(z_samples).most_common(1)[0]

        filtered: List[Segment] = []
        for s in segments:
            if abs(s.start[2] - z_mode) < 1e-3 and abs(s.end[2] - z_mode) < 1e-3:
                filtered.append(s)
        return filtered

