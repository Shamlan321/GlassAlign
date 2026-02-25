from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QCloseEvent, QGuiApplication, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import AppConfig
from exporter import generate_report_text
from gcode_parser import GCodeParser, GCodeParserError
from reference_calc import ReferencePoint, ShapeInfo, compute_reference_points, detect_shape_type
from renderer import ToolpathCanvas
from cnc_controller import CncController, CncConnectionError


# ---------------------------------------------------------------------------
# Style sheets
# ---------------------------------------------------------------------------

_APP_STYLE = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #2d2d4e;
    border-radius: 8px;
    margin-top: 10px;
    padding: 6px 6px 4px 6px;
    background-color: #16213e;
    color: #c0c8e0;
    font-weight: 600;
    font-size: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #7b9cff;
}

QLabel {
    color: #c0c8e0;
    font-size: 12px;
}

QLineEdit, QDoubleSpinBox {
    background-color: #0f3460;
    border: 1px solid #2d4a8a;
    border-radius: 5px;
    padding: 4px 6px;
    color: #e0e8ff;
    selection-background-color: #7b9cff;
    font-size: 12px;
}
QLineEdit:focus, QDoubleSpinBox:focus {
    border: 1px solid #7b9cff;
}

QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #0f3460;
    border: none;
    width: 14px;
}

QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: #1a1a2e;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #3a3a6e;
    border-radius: 3px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QTextEdit {
    background-color: #0f3460;
    border: 1px solid #2d4a8a;
    border-radius: 6px;
    color: #a0b8e0;
    font-size: 11px;
    padding: 4px;
}

QStatusBar {
    background-color: #10102a;
    color: #7b9cff;
}

QMenuBar {
    background-color: #10102a;
    color: #c0c8e0;
}
QMenuBar::item:selected {
    background-color: #2d2d4e;
}
QMenu {
    background-color: #1a1a2e;
    border: 1px solid #2d2d4e;
    color: #c0c8e0;
}
QMenu::item:selected {
    background-color: #0f3460;
}
"""

_BTN_PRIMARY = """
QPushButton {
    background-color: #0f3460;
    color: #7bd3ff;
    border: 1px solid #1a5fa8;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #1a4a7a;
    border-color: #4a8fff;
    color: #c0e8ff;
}
QPushButton:pressed {
    background-color: #0a2840;
}
QPushButton:disabled {
    background-color: #1a1a2e;
    color: #444466;
    border-color: #2a2a4e;
}
"""

_BTN_SUCCESS = """
QPushButton {
    background-color: #0a3a28;
    color: #4dffa0;
    border: 1px solid #1a7a50;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #0f5038;
    border-color: #30c070;
    color: #80ffcc;
}
QPushButton:pressed {
    background-color: #062018;
}
QPushButton:disabled {
    background-color: #1a1a2e;
    color: #444466;
    border-color: #2a2a4e;
}
"""

_BTN_DANGER = """
QPushButton {
    background-color: #3a0a0a;
    color: #ff7b7b;
    border: 1px solid #8a1a1a;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #5a1010;
    border-color: #cc3030;
    color: #ffaaaa;
}
QPushButton:pressed {
    background-color: #200a0a;
}
QPushButton:disabled {
    background-color: #1a1a2e;
    color: #444466;
    border-color: #2a2a4e;
}
"""

_BTN_JOG = """
QPushButton {
    background-color: #0a2040;
    color: #a0c8ff;
    border: 1px solid #1a3a6a;
    border-radius: 5px;
    padding: 4px 4px;
    font-weight: 700;
    font-size: 12px;
    min-height: 26px;
    min-width: 36px;
    max-width: 60px;
}
QPushButton:hover {
    background-color: #143060;
    border-color: #4a7ad0;
    color: #c8e4ff;
}
QPushButton:pressed {
    background-color: #081828;
}
QPushButton:disabled {
    background-color: #1a1a2e;
    color: #444466;
    border-color: #2a2a4e;
}
"""

_BTN_ACCENT = """
QPushButton {
    background-color: #1a0a40;
    color: #c0a0ff;
    border: 1px solid #4a2a8a;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #2a1060;
    border-color: #7a4aff;
    color: #dcc0ff;
}
QPushButton:pressed {
    background-color: #100828;
}
QPushButton:disabled {
    background-color: #1a1a2e;
    color: #444466;
    border-color: #2a2a4e;
}
"""

_BTN_LOAD = """
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a3a6a, stop:1 #0f2a50);
    color: #90d0ff;
    border: 1px solid #2a5aaa;
    border-radius: 7px;
    padding: 8px 20px;
    font-weight: 700;
    font-size: 13px;
    min-height: 32px;
    letter-spacing: 0.5px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #234a8a, stop:1 #183a70);
    border-color: #5a8fff;
    color: #c0e8ff;
}
QPushButton:pressed {
    background-color: #0a1c38;
}
"""


def _apply_style(btn: QPushButton, style: str) -> None:
    btn.setStyleSheet(style)


class MainWindow(QMainWindow):
    def __init__(self, app_config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = app_config
        self.setWindowTitle("GlassAlign")

        self._current_file: Optional[Path] = None
        self._shape_info: Optional[ShapeInfo] = None
        self._ref_points: List[ReferencePoint] = []

        # CNC control wrapper (lazy-init of GRBL connection)
        self.cnc = CncController(log_callback=self._log_message)

        # Apply global dark style
        self.setStyleSheet(_APP_STYLE)

        self._build_ui()
        self._restore_geometry()

    # ── UI construction ─────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 6, 8, 6)
        root_layout.setSpacing(6)

        # ── Top toolbar ──────────────────────────────────────────────────────
        load_btn = QPushButton("⟳  Load G-code File")
        _apply_style(load_btn, _BTN_LOAD)
        load_btn.clicked.connect(self._on_load_file)

        top_row = QHBoxLayout()
        top_row.addWidget(load_btn)
        top_row.addStretch(1)

        # App title label
        title_label = QLabel("GlassAlign")
        title_label.setStyleSheet(
            "color: #7b9cff; font-size: 18px; font-weight: 800; letter-spacing: 1.5px;"
        )
        top_row.addWidget(title_label)
        root_layout.addLayout(top_row)

        # ── Main content: canvas + sidebar ───────────────────────────────────
        main_layout = QHBoxLayout()
        main_layout.setSpacing(8)
        root_layout.addLayout(main_layout, stretch=1)

        # Left: canvas
        self.canvas = ToolpathCanvas(self)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.canvas, stretch=3)

        # Right: sidebar inside a scroll area so content never shrinks
        sidebar_widget = QWidget()
        sidebar_widget.setMinimumWidth(280)
        sidebar_widget.setMaximumWidth(340)
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(6)

        # ── File info ────────────────────────────────────────────────────────
        self.file_label = QLabel("File: (none)")
        self.units_label = QLabel("Units: –")
        self.moves_label = QLabel("Total moves: –")

        file_group = QGroupBox("File Information")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(2)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.units_label)
        file_layout.addWidget(self.moves_label)
        sidebar_layout.addWidget(file_group)

        # ── Shape dimensions ─────────────────────────────────────────────────
        self.dim_width = QLabel("Width: –")
        self.dim_height = QLabel("Height: –")
        self.dim_center = QLabel("Center: –")
        self.dim_type = QLabel("Type: –")

        dim_group = QGroupBox("Shape Dimensions")
        dim_layout = QVBoxLayout(dim_group)
        dim_layout.setSpacing(2)
        dim_layout.addWidget(self.dim_width)
        dim_layout.addWidget(self.dim_height)
        dim_layout.addWidget(self.dim_center)
        dim_layout.addWidget(self.dim_type)
        sidebar_layout.addWidget(dim_group)

        # ── Reference points + clearance ─────────────────────────────────────
        ref_group = QGroupBox("Reference Points")
        ref_layout = QGridLayout(ref_group)
        ref_layout.setSpacing(4)

        ref_layout.addWidget(QLabel("Clearance:"), 0, 0)
        self.clearance_spin = QDoubleSpinBox()
        self.clearance_spin.setRange(0.0, 1000.0)
        self.clearance_spin.setDecimals(2)
        self.clearance_spin.setValue(float(self.config.get("default_clearance_mm", 5.0)))
        self.clearance_spin.setSuffix(" mm")
        ref_layout.addWidget(self.clearance_spin, 0, 1)

        self.update_clearance_btn = QPushButton("Update")
        _apply_style(self.update_clearance_btn, _BTN_PRIMARY)
        ref_layout.addWidget(self.update_clearance_btn, 0, 2)

        self.p1_label = QLabel("P1: –")
        self.p2_label = QLabel("P2: –")
        self.p3_label = QLabel("P3: –")
        for lbl in (self.p1_label, self.p2_label, self.p3_label):
            lbl.setWordWrap(True)
        ref_layout.addWidget(self.p1_label, 1, 0, 1, 3)
        ref_layout.addWidget(self.p2_label, 2, 0, 1, 3)
        ref_layout.addWidget(self.p3_label, 3, 0, 1, 3)

        sidebar_layout.addWidget(ref_group)

        # ── Machine control ──────────────────────────────────────────────────
        machine_group = QGroupBox("Machine Control (GRBL)")
        machine_layout = QGridLayout(machine_group)
        machine_layout.setSpacing(5)

        # Connection status indicator row
        status_row = QHBoxLayout()
        conn_label = QLabel("Status:")
        conn_label.setStyleSheet("color: #8898bb; font-size: 11px;")
        status_row.addWidget(conn_label)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(
            "color: #cc3333; font-size: 18px; padding: 0 4px;"
        )
        status_row.addWidget(self.status_dot)

        self.machine_status_label = QLabel("Disconnected")
        self.machine_status_label.setStyleSheet("color: #cc5555; font-size: 12px; font-weight: 600;")
        status_row.addWidget(self.machine_status_label)
        status_row.addStretch(1)
        machine_layout.addLayout(status_row, 0, 0, 1, 4)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2d2d4e;")
        machine_layout.addWidget(sep, 1, 0, 1, 4)

        # Port / Baud
        machine_layout.addWidget(QLabel("Port:"), 2, 0)
        self.port_edit = QLineEdit("COM3")
        self.port_edit.setMaximumWidth(72)
        machine_layout.addWidget(self.port_edit, 2, 1)

        machine_layout.addWidget(QLabel("Baud:"), 2, 2)
        self.baud_edit = QLineEdit("115200")
        self.baud_edit.setMaximumWidth(70)
        machine_layout.addWidget(self.baud_edit, 2, 3)

        # Connect / Disconnect
        self.connect_btn = QPushButton("Connect")
        _apply_style(self.connect_btn, _BTN_SUCCESS)
        self.disconnect_btn = QPushButton("Disconnect")
        _apply_style(self.disconnect_btn, _BTN_DANGER)
        self.disconnect_btn.setEnabled(False)
        machine_layout.addWidget(self.connect_btn, 3, 0, 1, 2)
        machine_layout.addWidget(self.disconnect_btn, 3, 2, 1, 2)

        # Jog step / feed
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #2d2d4e;")
        machine_layout.addWidget(sep2, 4, 0, 1, 4)

        machine_layout.addWidget(QLabel("Jog step:"), 5, 0)
        self.jog_step_spin = QDoubleSpinBox()
        self.jog_step_spin.setRange(0.01, 100.0)
        self.jog_step_spin.setDecimals(2)
        self.jog_step_spin.setValue(1.0)
        self.jog_step_spin.setSuffix(" mm")
        machine_layout.addWidget(self.jog_step_spin, 5, 1)

        machine_layout.addWidget(QLabel("Feed:"), 5, 2)
        self.jog_feed_spin = QDoubleSpinBox()
        self.jog_feed_spin.setRange(10.0, 10000.0)
        self.jog_feed_spin.setDecimals(0)
        self.jog_feed_spin.setValue(1000.0)
        self.jog_feed_spin.setSuffix(" /min")
        machine_layout.addWidget(self.jog_feed_spin, 5, 3)

        # Jog buttons arranged as a D-pad
        self.jog_x_neg_btn = QPushButton("X–")
        self.jog_x_pos_btn = QPushButton("X+")
        self.jog_y_neg_btn = QPushButton("Y–")
        self.jog_y_pos_btn = QPushButton("Y+")
        self.jog_z_neg_btn = QPushButton("Z–")
        self.jog_z_pos_btn = QPushButton("Z+")

        for btn in (
            self.jog_x_neg_btn, self.jog_x_pos_btn,
            self.jog_y_neg_btn, self.jog_y_pos_btn,
            self.jog_z_neg_btn, self.jog_z_pos_btn,
        ):
            _apply_style(btn, _BTN_JOG)

        jog_layout = QGridLayout()
        jog_layout.setSpacing(3)
        jog_layout.addWidget(self.jog_y_pos_btn, 0, 1)
        jog_layout.addWidget(self.jog_x_neg_btn, 1, 0)
        jog_layout.addWidget(self.jog_x_pos_btn, 1, 2)
        jog_layout.addWidget(self.jog_y_neg_btn, 2, 1)
        jog_layout.addWidget(self.jog_z_pos_btn, 0, 3)
        jog_layout.addWidget(self.jog_z_neg_btn, 2, 3)
        machine_layout.addLayout(jog_layout, 6, 0, 1, 4)

        # Zero
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #2d2d4e;")
        machine_layout.addWidget(sep3, 7, 0, 1, 4)

        self.zero_btn = QPushButton("⊙  Zero X / Y / Z  (G92)")
        _apply_style(self.zero_btn, _BTN_ACCENT)
        machine_layout.addWidget(self.zero_btn, 8, 0, 1, 4)

        # Safe Z / Touch Z
        machine_layout.addWidget(QLabel("Safe Z:"), 9, 0)
        self.safe_z_spin = QDoubleSpinBox()
        self.safe_z_spin.setRange(-1000.0, 1000.0)
        self.safe_z_spin.setDecimals(2)
        self.safe_z_spin.setValue(5.0)
        self.safe_z_spin.setSuffix(" mm")
        machine_layout.addWidget(self.safe_z_spin, 9, 1)

        machine_layout.addWidget(QLabel("Touch Z:"), 9, 2)
        self.touch_z_spin = QDoubleSpinBox()
        self.touch_z_spin.setRange(-1000.0, 1000.0)
        self.touch_z_spin.setDecimals(2)
        self.touch_z_spin.setValue(0.0)
        self.touch_z_spin.setSuffix(" mm")
        machine_layout.addWidget(self.touch_z_spin, 9, 3)

        machine_layout.addWidget(QLabel("Z feed:"), 10, 0)
        self.touch_feed_spin = QDoubleSpinBox()
        self.touch_feed_spin.setRange(10.0, 5000.0)
        self.touch_feed_spin.setDecimals(0)
        self.touch_feed_spin.setValue(200.0)
        self.touch_feed_spin.setSuffix(" /min")
        machine_layout.addWidget(self.touch_feed_spin, 10, 1, 1, 3)

        # Go-to reference point buttons
        sep4 = QFrame()
        sep4.setFrameShape(QFrame.Shape.HLine)
        sep4.setStyleSheet("color: #2d2d4e;")
        machine_layout.addWidget(sep4, 11, 0, 1, 4)

        self.goto_p1_btn = QPushButton("→ P1")
        self.goto_p2_btn = QPushButton("→ P2")
        self.goto_p3_btn = QPushButton("→ P3")
        for btn in (self.goto_p1_btn, self.goto_p2_btn, self.goto_p3_btn):
            _apply_style(btn, _BTN_PRIMARY)

        goto_layout = QHBoxLayout()
        goto_layout.setSpacing(4)
        goto_layout.addWidget(self.goto_p1_btn)
        goto_layout.addWidget(self.goto_p2_btn)
        goto_layout.addWidget(self.goto_p3_btn)
        machine_layout.addLayout(goto_layout, 12, 0, 1, 4)

        sidebar_layout.addWidget(machine_group)

        # ── Instructions ─────────────────────────────────────────────────────
        instr_group = QGroupBox("Setup Instructions")
        instr_layout = QVBoxLayout(instr_group)
        self.instructions_edit = QTextEdit()
        self.instructions_edit.setReadOnly(True)
        self.instructions_edit.setMinimumHeight(100)
        instr_layout.addWidget(self.instructions_edit)
        sidebar_layout.addWidget(instr_group)

        # ── Export / copy buttons ─────────────────────────────────────────────
        self.export_btn = QPushButton("📄  Export Report")
        self.copy_btn = QPushButton("⧉  Copy Points")
        _apply_style(self.export_btn, _BTN_PRIMARY)
        _apply_style(self.copy_btn, _BTN_ACCENT)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.copy_btn)
        sidebar_layout.addLayout(btn_row)

        sidebar_layout.addStretch(1)

        # ── Scroll area wrapping the whole sidebar ────────────────────────────
        scroll = QScrollArea()
        scroll.setWidget(sidebar_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        scroll.setFixedWidth(320)

        main_layout.addWidget(scroll)

        # ── Status bar ────────────────────────────────────────────────────────
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #7b9cff; font-size: 12px;")
        status.addPermanentWidget(self.status_label, 1)

        # ── Menu ──────────────────────────────────────────────────────────────
        file_menu = self.menuBar().addMenu("&File")
        act_load = QAction("Load G-code...", self)
        act_load.triggered.connect(self._on_load_file)
        file_menu.addAction(act_load)

        act_export = QAction("Export Report...", self)
        act_export.triggered.connect(self._on_export_report)
        file_menu.addAction(act_export)

        file_menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # ── Wire signals ──────────────────────────────────────────────────────
        self.update_clearance_btn.clicked.connect(self._on_clearance_changed)
        self.export_btn.clicked.connect(self._on_export_report)
        self.copy_btn.clicked.connect(self._on_copy_points)

        self.connect_btn.clicked.connect(self._on_connect_cnc)
        self.disconnect_btn.clicked.connect(self._on_disconnect_cnc)
        self.jog_x_neg_btn.clicked.connect(lambda: self._on_jog(dx=-1))
        self.jog_x_pos_btn.clicked.connect(lambda: self._on_jog(dx=1))
        self.jog_y_neg_btn.clicked.connect(lambda: self._on_jog(dy=-1))
        self.jog_y_pos_btn.clicked.connect(lambda: self._on_jog(dy=1))
        self.jog_z_neg_btn.clicked.connect(lambda: self._on_jog(dz=-1))
        self.jog_z_pos_btn.clicked.connect(lambda: self._on_jog(dz=1))
        self.zero_btn.clicked.connect(self._on_zero_all)
        self.goto_p1_btn.clicked.connect(lambda: self._on_go_to_point(0))
        self.goto_p2_btn.clicked.connect(lambda: self._on_go_to_point(1))
        self.goto_p3_btn.clicked.connect(lambda: self._on_go_to_point(2))

    # ── Persistence ──────────────────────────────────────────────────────────
    def _restore_geometry(self) -> None:
        geom_hex = self.config.get("window_geometry")
        if geom_hex:
            try:
                self.restoreGeometry(bytes.fromhex(geom_hex))
            except Exception:
                pass

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        try:
            geom_hex = self.saveGeometry().toHex().data().decode("ascii")
            self.config.set("window_geometry", geom_hex)
            self.config.set("default_clearance_mm", float(self.clearance_spin.value()))
            self.config.save()
        except Exception:
            pass
        return super().closeEvent(event)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _on_load_file(self) -> None:
        last_dir = self.config.get("last_directory") or str(Path.home())
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open G-code File",
            last_dir,
            "G-code Files (*.nc *.tap *.gcode *.cnc);;All Files (*)",
        )
        if not path_str:
            return

        path = Path(path_str)
        if not path.exists():
            QMessageBox.warning(self, "File not found", f"File not found:\n{path}")
            return

        self.config.set("last_directory", str(path.parent))
        self.config.save()

        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                lines = list(f)
            parser = GCodeParser()
            summary = parser.parse_file(lines)
        except GCodeParserError as e:
            QMessageBox.critical(self, "G-code Parse Error", f"Failed to parse G-code:\n{e}")
            self.status_label.setText("Parse error")
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error while loading file:\n{e}")
            self.status_label.setText("Error loading file")
            return

        self._current_file = path
        self.canvas.set_toolpath(summary)
        self._update_from_summary(summary)
        self._recalculate_reference_points()
        self.status_label.setText(
            f"{path.name} loaded  |  "
            f"{self._shape_info.width:.2f}×{self._shape_info.height:.2f} {self._shape_info.units}  |  "
            f"{len(self._ref_points)} reference points"
        )

    def _update_from_summary(self, summary) -> None:
        self.file_label.setText(f"File: {self._current_file.name if self._current_file else '(none)'}")
        self.units_label.setText(
            "Units: Millimeters (mm)" if summary.units == "mm" else "Units: Inches (in)"
        )
        self.moves_label.setText(f"Total moves: {summary.total_moves}")

        shape = ShapeInfo(
            min_x=summary.min_x,
            max_x=summary.max_x,
            min_y=summary.min_y,
            max_y=summary.max_y,
            has_arcs=summary.has_arcs,
            units=summary.units,
        )
        self._shape_info = shape

        self.dim_width.setText(f"Width:  {shape.width:.2f} {shape.units}")
        self.dim_height.setText(f"Height: {shape.height:.2f} {shape.units}")
        self.dim_center.setText(f"Center: X={shape.center_x:.2f}, Y={shape.center_y:.2f}")
        self.dim_type.setText(f"Type:   {detect_shape_type(shape)}")

    def _recalculate_reference_points(self) -> None:
        if not self._shape_info:
            return
        clearance = float(self.clearance_spin.value())
        shape = self._shape_info

        max_dim = max(shape.width, shape.height)
        if clearance > max_dim / 4.0:
            QMessageBox.warning(
                self,
                "Clearance too large",
                "Clearance is larger than a quarter of the shape size.\n"
                "Reference points may be far from the shape.",
            )

        self._ref_points = compute_reference_points(shape, clearance)
        self.canvas.set_reference_points(self._ref_points, clearance)

        def fmt_p(p: ReferencePoint) -> str:
            return f"{p.label}: X={p.x:.2f} {shape.units}, Y={p.y:.2f} {shape.units}"

        if len(self._ref_points) >= 3:
            self.p1_label.setText(fmt_p(self._ref_points[0]))
            self.p2_label.setText(fmt_p(self._ref_points[1]))
            self.p3_label.setText(fmt_p(self._ref_points[2]))

        self._update_instructions()

    def _update_instructions(self) -> None:
        if not self._shape_info or len(self._ref_points) < 3:
            self.instructions_edit.setPlainText("")
            return

        p1, p2, p3 = self._ref_points[:3]
        s = []
        s.append("1. Set machine X0, Y0 at desired glass origin position.")
        s.append(
            f"2. Jog to {p1.label} at X={p1.x:.2f}, Y={p1.y:.2f}. "
            "Place left edge of glass here."
        )
        s.append(
            f"3. Jog to {p2.label} at X={p2.x:.2f}, Y={p2.y:.2f}. "
            "Place top edge of glass here."
        )
        s.append(
            f"4. Jog to {p3.label} at X={p3.x:.2f}, Y={p3.y:.2f}. "
            "Place bottom edge of glass here."
        )
        s.append("5. Clamp glass securely and run G-code.")
        self.instructions_edit.setPlainText("\n".join(s))

    def _on_clearance_changed(self) -> None:
        self._recalculate_reference_points()

    def _on_export_report(self) -> None:
        if not self._current_file or not self._shape_info or not self._ref_points:
            QMessageBox.information(
                self, "Nothing to export",
                "Load a G-code file and calculate reference points first.",
            )
            return

        report_text = generate_report_text(self._current_file, self._shape_info, self._ref_points)

        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Alignment Report",
            str(self._current_file.with_suffix(".txt")),
            "Text Files (*.txt);;All Files (*)",
        )
        if not path_str:
            return

        out_path = Path(path_str)
        try:
            with out_path.open("w", encoding="utf-8") as f:
                f.write(report_text)
        except Exception as e:
            QMessageBox.critical(self, "Error writing file", f"Failed to write report:\n{e}")
            return

        self.status_label.setText(f"Report exported to {out_path}")

    def _on_copy_points(self) -> None:
        if not self._shape_info or not self._ref_points:
            QMessageBox.information(
                self, "Nothing to copy",
                "Load a G-code file and calculate reference points first.",
            )
            return

        lines = []
        for p in self._ref_points:
            lines.append(
                f"{p.label}: X={p.x:.3f} {self._shape_info.units}, "
                f"Y={p.y:.3f} {self._shape_info.units}"
            )
        text = "\n".join(lines)
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        self.status_label.setText("Reference points copied to clipboard")

    # ── Connection status helper ──────────────────────────────────────────────
    def _set_connection_ui(self, connected: bool, port: str = "") -> None:
        if connected:
            self.status_dot.setStyleSheet(
                "color: #33ee88; font-size: 18px; padding: 0 4px;"
            )
            self.machine_status_label.setText(f"Connected  –  {port}")
            self.machine_status_label.setStyleSheet(
                "color: #33ee88; font-size: 12px; font-weight: 600;"
            )
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
        else:
            self.status_dot.setStyleSheet(
                "color: #cc3333; font-size: 18px; padding: 0 4px;"
            )
            self.machine_status_label.setText("Disconnected")
            self.machine_status_label.setStyleSheet(
                "color: #cc5555; font-size: 12px; font-weight: 600;"
            )
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)

    # ── CNC control handlers ──────────────────────────────────────────────────
    def _on_connect_cnc(self) -> None:
        port = self.port_edit.text().strip()
        if not port:
            QMessageBox.information(self, "Port required", "Enter a serial port (e.g. COM3).")
            return
        try:
            baud = int(self.baud_edit.text().strip() or "115200")
        except ValueError:
            QMessageBox.information(self, "Invalid baud", "Enter a valid baud rate (e.g. 115200).")
            return

        try:
            self.cnc.connect(port, baud)
        except CncConnectionError as exc:
            QMessageBox.critical(self, "Connection error", str(exc))
            self._set_connection_ui(False)
            return

        self._set_connection_ui(True, port)

    def _on_disconnect_cnc(self) -> None:
        self.cnc.disconnect()
        self._set_connection_ui(False)

    def _on_jog(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> None:
        if not self.cnc.is_connected:
            QMessageBox.information(self, "Not connected", "Connect to a GRBL controller first.")
            return
        step = float(self.jog_step_spin.value())
        feed = float(self.jog_feed_spin.value())
        self.cnc.jog_settings.step_mm = step
        self.cnc.jog_settings.feed_mm_min = feed
        try:
            self.cnc.jog(dx * step, dy * step, dz * step)
        except CncConnectionError as exc:
            QMessageBox.critical(self, "Jog error", str(exc))

    def _on_zero_all(self) -> None:
        if not self.cnc.is_connected:
            QMessageBox.information(self, "Not connected", "Connect to a GRBL controller first.")
            return
        try:
            self.cnc.zero_all()
        except CncConnectionError as exc:
            QMessageBox.critical(self, "Zero error", str(exc))

    def _on_go_to_point(self, index: int) -> None:
        if not self.cnc.is_connected:
            QMessageBox.information(self, "Not connected", "Connect to a GRBL controller first.")
            return
        if not self._ref_points or index >= len(self._ref_points):
            QMessageBox.information(
                self, "No reference point",
                "Load a G-code file and calculate reference points first.",
            )
            return

        p = self._ref_points[index]
        self.cnc.z_settings.safe_z = float(self.safe_z_spin.value())
        self.cnc.z_settings.touch_z = float(self.touch_z_spin.value())
        self.cnc.z_settings.touch_feed = float(self.touch_feed_spin.value())

        try:
            self.cnc.move_to_reference_point(p.x, p.y)
        except CncConnectionError as exc:
            QMessageBox.critical(self, "Move error", str(exc))

    # ── Logger used by CncController ──────────────────────────────────────────
    def _log_message(self, message: str) -> None:
        self.status_label.setText(message)
