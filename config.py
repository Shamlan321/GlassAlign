import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "last_directory": "",
    # Default to 0 so reference points lie exactly on the shape extents
    "default_clearance_mm": 0.0,
    "window_geometry": None,  # QByteArray as hex string
    "grid_visible": True,
    "units": "mm",
}


class AppConfig:
    """
    Simple JSON-backed configuration.
    Stores small bits of UI state and user preferences between sessions.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is None:
            config_dir = Path.home() / ".glassalign"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "config.json"
        self._path = config_path
        self._data: Dict[str, Any] = DEFAULT_CONFIG.copy()
        self.load()

    @property
    def data(self) -> Dict[str, Any]:
        return self._data

    def load(self) -> None:
        if self._path.exists():
            try:
                with self._path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._data.update(raw)
            except Exception:
                # On any error, fall back to defaults
                self._data = DEFAULT_CONFIG.copy()

    def save(self) -> None:
        try:
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            # Silent failure is acceptable for non-critical preferences
            pass

    def get(self, key: str, default: Any | None = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

