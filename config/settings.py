"""
settings.py

User-configurable settings with load/save capability.

These are the tunable preferences that a user changes in the options
menu: volume, mouse sensitivity, graphics quality, etc.  Settings
are persisted to a JSON file so they survive game restarts.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import Constants

logger = logging.getLogger(__name__)


class Settings:
    """
    User preferences manager.

    Settings are stored internally as a dictionary and can be
    serialized to / deserialized from a JSON file.  Every key
    has a sensible default so the game runs even if the config
    file is missing or corrupted.

    Parameters
    ----------
    config_path : Path, optional
        Where to read / write the settings file.  If not provided,
        a default location next to the game executable is used.

    Examples
    --------
    >>> s = Settings()
    >>> s.get("master_volume")
    0.8
    >>> s.set("master_volume", 0.5)
    >>> s.save()
    """

    #: Default settings dictionary.  Add new keys here; they will
    #: automatically be available with their default values.
    DEFAULTS: Dict[str, Any] = {
        "master_volume": Constants.DEFAULT_MASTER_VOLUME,
        "sfx_volume": Constants.DEFAULT_SFX_VOLUME,
        "music_volume": Constants.DEFAULT_MUSIC_VOLUME,
        "mouse_sensitivity": Constants.DEFAULT_MOUSE_SENSITIVITY,
        "fov": Constants.DEFAULT_FOV_SETTING,
        "fullscreen": False,
        "window_width": 1280,
        "window_height": 720,
        "vsync": True,
        "graphics_quality": "high",  # "low", "medium", "high", "ultra"
    }

    def __init__(self, config_path: Optional[Path] = None) -> None:
        if config_path is None:
            # Default to a well-known location.
            config_path = Path.home() / ".sharifa" / "settings.json"

        self.config_path: Path = config_path

        # Start with a deep copy of defaults so we never accidentally
        # mutate the class-level DEFAULTS dict.
        self._data: Dict[str, Any] = deepcopy(self.DEFAULTS)

        # Try to load existing settings; fall back gracefully.
        self.load()

    # ------------------------------------------------------------------ #
    #  Persistence                                                        #
    # ------------------------------------------------------------------ #

    def load(self) -> None:
        """
        Load settings from the JSON config file.

        If the file does not exist or is corrupted, the current
        in-memory settings (defaults) are preserved.
        """
        if not self.config_path.exists():
            logger.info("No settings file found at %s; using defaults.", self.config_path)
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            logger.warning("Settings file is corrupted (%s); using defaults.", exc)
            return
        except OSError as exc:
            logger.warning("Cannot read settings file (%s); using defaults.", exc)
            return

        # Merge loaded values over defaults — any missing keys
        # retain their default values.
        for key, default_val in self.DEFAULTS.items():
            if key in data:
                self._data[key] = data[key]
            else:
                # Key missing from file — ensure it has the default.
                self._data[key] = deepcopy(default_val)

        logger.info("Settings loaded successfully from %s.", self.config_path)

    def save(self) -> None:
        """
        Persist current settings to the JSON config file.

        Creates parent directories if needed.
        """
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, sort_keys=True)
            logger.info("Settings saved to %s.", self.config_path)
        except OSError as exc:
            logger.error("Failed to save settings: %s", exc)

    # ------------------------------------------------------------------ #
    #  Get / set                                                          #
    # ------------------------------------------------------------------ #

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a setting value.

        Parameters
        ----------
        key : str
            The setting key.
        default : Any, optional
            Value to return if the key is not found.  If omitted,
            a ``KeyError`` is raised for unknown keys.

        Returns
        -------
        The setting value.
        """
        if key in self._data:
            return self._data[key]
        if default is not None:
            return default
        raise KeyError(f"Unknown setting '{key}'")

    def set(self, key: str, value: Any) -> None:
        """
        Set a setting value.

        Parameters
        ----------
        key : str
            The setting key.
        value : Any
            The new value.
        """
        if key not in self.DEFAULTS:
            logger.warning("Setting '%s' is not in defaults; creating it anyway.", key)
        self._data[key] = deepcopy(value)

    def reset(self) -> None:
        """Reset all settings to their default values (in memory only)."""
        self._data = deepcopy(self.DEFAULTS)

    def all(self) -> Dict[str, Any]:
        """Return a copy of all current settings."""
        return deepcopy(self._data)
