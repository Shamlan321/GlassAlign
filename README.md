# GlassAlign

A desktop tool for CNC glass grinding alignment. Load a G-code file, visualise the toolpath, and automatically calculate three physical reference points so an operator can manually align and centre a glass workpiece on the machine — no probing required.

Built with Python, PyQt6, and Matplotlib. Connects directly to GRBL-based CNC controllers via serial.

---

## Installation

### Option 1 — Download compiled executable (Windows)

Download the latest `GlassAlign.exe` from the [Releases page](https://github.com/Shamlan321/GlassAlign/releases). No Python or dependencies required — just run it.

### Option 2 — Clone and run from source

**Requirements:** Python 3.11+

```bash
git clone https://github.com/Shamlan321/GlassAlign.git
cd GlassAlign
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
python main.py
```

---

## Usage

1. Click **Load G-code File** and select a `.nc`, `.tap`, `.gcode`, or `.cnc` file.
2. The toolpath is parsed and rendered in the canvas. Zoom with the scroll wheel; pan by clicking and dragging.
3. The sidebar shows bounding box dimensions, detected shape type, and the three computed reference points (P1, P2, P3).
4. Adjust **Clearance** (mm) and click **Update** to shift the reference points outward from the shape boundary.
5. Optionally connect to a GRBL controller (enter port and baud rate, then click **Connect**). Use the jog controls to move the machine, or click **→ P1 / P2 / P3** to drive the spindle directly to each reference point.
6. Use **Export Report** to save a `.txt` alignment report, or **Copy Points** to copy coordinates to the clipboard.

### What the reference points mean

| Point | Position | Operator action |
|-------|----------|-----------------|
| P1 | Left of shape, at mid-height | Align left edge of glass here |
| P2 | Top of shape, at mid-width | Align top edge of glass here |
| P3 | Bottom of shape, at mid-width | Verify bottom edge alignment |

After aligning to all three points, clamp the glass and run the G-code.

---

## How It Works

### G-code parsing (`gcode_parser.py`)

- Full modal state tracking: `G0/G1/G2/G3`, `G90/G91` (absolute/relative), `G20/G21` (inch/mm).
- Arc interpolation for both **I/J** (centre-offset) and **R** (radius) arcs — arcs are tessellated into line segments for accurate bounding-box calculation.
- Z-plane filtering: identifies the dominant cutting depth and discards Z-transition moves, so only the actual cut contour is used for geometry.

### Reference point calculation (`reference_calc.py`)

- Computes the bounding box of the cutting path.
- Detects shape type from aspect ratio and arc presence (Circle, Oval, Rectangle, Wide/Tall Rectangle, Complex).
- Places three axis-aligned reference points at configurable clearance from the bounding box edges.

### Visualisation (`renderer.py`)

- Matplotlib canvas embedded in PyQt6 with native zoom and pan.
- Rapid moves (`G0`) shown in light grey; cutting moves (`G1/G2/G3`) in blue.
- Bounding box, centre crosshair, and reference points overlaid.

### Machine control (`cnc_controller.py`)

- Thin wrapper around `grbl-streamer`.
- Supports manual jogging (X/Y/Z), work-coordinate zeroing (`G92`), and automatic move-to-reference sequences (raise to safe Z → rapid XY → feed to touch Z).

---

## Project Structure

```
GlassAlign/
├── main.py            # Entry point
├── ui_main.py         # PyQt6 main window and all UI wiring
├── gcode_parser.py    # Stateful G-code parser and toolpath summary
├── renderer.py        # Matplotlib canvas (toolpath + reference points)
├── reference_calc.py  # Bounding box, shape detection, reference points
├── cnc_controller.py  # GRBL serial connection and machine control
├── exporter.py        # Text alignment report generator
├── config.py          # JSON-backed user preferences
├── build.spec         # PyInstaller build configuration
├── requirements.txt
└── test_files/        # Sample G-code programs
```

---

## Supported G-code

| Code | Function |
|------|----------|
| G0 | Rapid move |
| G1 | Linear feed move |
| G2 / G3 | Clockwise / counter-clockwise arc (I/J or R) |
| G17 | XY plane (default) |
| G20 / G21 | Inch / millimetre mode |
| G90 / G91 | Absolute / relative positioning |

---

## Requirements

| Package | Version |
|---------|---------|
| Python | ≥ 3.11 |
| PyQt6 | ≥ 6.6.0 |
| matplotlib | ≥ 3.8.0 |
| numpy | ≥ 1.26.0 |
| grbl-streamer | ≥ 2.0.2 |
| pyserial | ≥ 3.5 |

---

## Contributing

Pull requests are welcome. For significant changes, please open an issue first to discuss what you'd like to change.

1. Fork the repo and create a feature branch.
2. Keep changes focused — one concern per PR.
3. Ensure the app runs from source (`python main.py`) before submitting.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
