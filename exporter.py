from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from reference_calc import ReferencePoint, ShapeInfo, detect_shape_type, distances_from_center_and_origin


def generate_report_text(
    file_path: Path,
    shape: ShapeInfo,
    points: List[ReferencePoint],
    operation: str = "Glass Grinding",
) -> str:
    """
    Create a human-readable alignment report as described in the spec.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    units_label = "Millimeters (mm)" if shape.units == "mm" else "Inches (in)"
    shape_type = detect_shape_type(shape)
    distances = {d["id"]: d for d in distances_from_center_and_origin(shape, points)}

    lines: List[str] = []
    lines.append("═══════════════════════════════════════════")
    lines.append("CNC REFERENCE POINT ALIGNMENT REPORT")
    lines.append(f"Generated: {timestamp}")
    lines.append("═══════════════════════════════════════════")
    lines.append("")
    lines.append(f"FILE: {file_path.name}")
    lines.append(f"UNITS: {units_label}")
    lines.append(f"OPERATION: {operation}")
    lines.append("")
    lines.append("SHAPE INFORMATION:")
    lines.append(
        f"  Bounding Box: X({shape.min_x:.2f} to {shape.max_x:.2f}), "
        f"Y({shape.min_y:.2f} to {shape.max_y:.2f})"
    )
    lines.append(f"  Width:  {shape.width:.2f} {shape.units}")
    lines.append(f"  Height: {shape.height:.2f} {shape.units}")
    lines.append(
        f"  Center: X={shape.center_x:.2f}{shape.units}, "
        f"Y={shape.center_y:.2f}{shape.units}"
    )
    lines.append(f"  Type: {shape_type}")
    lines.append("")
    lines.append("REFERENCE POINTS (relative to G-code origin):")
    lines.append("─────────────────────────────────────────────")

    for p in points:
        dist = distances.get(p.id)
        lines.append(f"{p.label}")
        lines.append(
            f"  Coordinate: X = {p.x:.2f} {shape.units}, "
            f"Y = {p.y:.2f} {shape.units}"
        )
        lines.append(f"  Position: {p.description}")
        lines.append(
            f"  Machine Action: Jog to X={p.x:.2f}, Y={p.y:.2f}"
        )
        if dist:
            lines.append(
                "  Distance from center: "
                f"{dist['distance_from_center']:.2f}{shape.units}"
            )
            lines.append(
                "  Distance from origin: "
                f"{dist['distance_from_origin']:.2f}{shape.units} at "
                f"{dist['bearing_from_origin_deg']:.1f}°"
            )
        lines.append("")

    lines.append("SETUP INSTRUCTIONS:")
    lines.append("─────────────────────────────────────────────")
    lines.append("1. Place glass roughly on machine table")
    lines.append("2. Set machine origin (X=0, Y=0) at intended glass origin")
    lines.append("3. Jog machine to P1 coordinates")
    lines.append("4. Measure/adjust glass so left edge aligns with tool")
    lines.append("5. Jog machine to P2 coordinates")
    lines.append("6. Measure/adjust glass so top edge aligns with tool")
    lines.append("7. Jog machine to P3 coordinates")
    lines.append("8. Verify bottom edge aligns with tool")
    lines.append("9. Clamp glass securely")
    lines.append("10. Run G-code - glass is correctly positioned ✓")
    lines.append("")
    lines.append("═══════════════════════════════════════════")

    return "\n".join(lines)

