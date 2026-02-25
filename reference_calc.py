from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, sqrt
from typing import List, Tuple


@dataclass
class ReferencePoint:
    id: int
    label: str
    x: float
    y: float
    description: str

    @property
    def coord_tuple(self) -> Tuple[float, float]:
        return self.x, self.y


@dataclass
class ShapeInfo:
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    has_arcs: bool
    units: str  # "mm" or "inch"

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) / 2.0

    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) / 2.0

    @property
    def aspect_ratio(self) -> float:
        if self.height == 0:
            return 0.0
        return self.width / self.height


def detect_shape_type(shape: ShapeInfo) -> str:
    """
    Very lightweight shape-type detection using aspect ratio and arc presence.
    """
    ar = shape.aspect_ratio

    if shape.has_arcs:
        if 0.9 <= ar <= 1.1:
            return "Circle"
        return "Oval"

    if 0.8 <= ar <= 1.2:
        return "Rectangle"
    elif ar > 1.2:
        return "Wide Rectangle"
    elif ar < 0.8:
        return "Tall Rectangle"
    return "Complex"


def compute_reference_points(shape: ShapeInfo, clearance: float) -> List[ReferencePoint]:
    """
    Compute three reference points around the shape using the shared formula
    based on the bounding box and clearance.

    The same geometry is used for all shapes; only labels/descriptions adapt.
    """
    cx = shape.center_x
    cy = shape.center_y

    p1_x = shape.min_x - clearance
    p1_y = cy

    p2_x = cx
    p2_y = shape.max_y + clearance

    p3_x = cx
    p3_y = shape.min_y - clearance

    shape_type = detect_shape_type(shape)

    if shape_type in {"Rectangle", "Wide Rectangle", "Tall Rectangle"}:
        p1_label = "P1 - Left Edge"
        p2_label = "P2 - Top Center"
        p3_label = "P3 - Bottom Center"
    elif shape_type in {"Circle", "Oval"}:
        p1_label = "P1 - Left of {}" .format(shape_type.lower())
        p2_label = "P2 - Top of {}" .format(shape_type.lower())
        p3_label = "P3 - Bottom of {}" .format(shape_type.lower())
    else:
        p1_label = "P1 - Left Reference"
        p2_label = "P2 - Top Reference"
        p3_label = "P3 - Bottom Reference"

    points = [
        ReferencePoint(
            id=1,
            label=p1_label,
            x=p1_x,
            y=p1_y,
            description="{} {} from shape's left edge, at center height".format(
                _fmt_mm(clearance), _unit_word(shape.units, clearance)
            ),
        ),
        ReferencePoint(
            id=2,
            label=p2_label,
            x=p2_x,
            y=p2_y,
            description="{} {} above shape's top edge, at center width".format(
                _fmt_mm(clearance), _unit_word(shape.units, clearance)
            ),
        ),
        ReferencePoint(
            id=3,
            label=p3_label,
            x=p3_x,
            y=p3_y,
            description="{} {} below shape's bottom edge, at center width".format(
                _fmt_mm(clearance), _unit_word(shape.units, clearance)
            ),
        ),
    ]
    return points


def distances_from_center_and_origin(
    shape: ShapeInfo, points: List[ReferencePoint]
) -> List[dict]:
    """
    Compute helper metrics:
      - distance from shape center
      - distance and bearing from G-code origin (0,0)
    """
    results: List[dict] = []
    cx, cy = shape.center_x, shape.center_y

    for p in points:
        dx_c = p.x - cx
        dy_c = p.y - cy
        dist_center = sqrt(dx_c * dx_c + dy_c * dy_c)

        dx_o = p.x
        dy_o = p.y
        dist_origin = sqrt(dx_o * dx_o + dy_o * dy_o)
        angle_origin = degrees(atan2(dy_o, dx_o))
        if angle_origin < 0:
            angle_origin += 360.0

        results.append(
            {
                "id": p.id,
                "label": p.label,
                "distance_from_center": dist_center,
                "distance_from_origin": dist_origin,
                "bearing_from_origin_deg": angle_origin,
            }
        )
    return results


def _fmt_mm(value: float) -> str:
    return f"{value:.2f}"


def _unit_word(units: str, value: float) -> str:
    if units == "inch":
        return "inch" if abs(value) == 1.0 else "inches"
    return "mm"

