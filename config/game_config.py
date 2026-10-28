"""
game_config.py

Global, immutable game configuration.

Unlike ``Settings`` (which stores user preferences and can change
at runtime), ``GameConfig`` holds static build / launch-time data
such as the game title, version, asset search paths, and other
metadata about the game itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class GameConfig:
    """
    Immutable game configuration loaded at startup.

    Attributes
    ----------
    game_title : str
        The window title and display name of the game.
    version : str
        Semantic version string of the build.
    base_path : Path
        Root directory of the game installation.
    asset_paths : List[Path]
        Directories searched for game assets, in priority order.
    model_paths : List[Path]
        Directories specifically for 3D models.
    texture_paths : List[Path]
        Directories specifically for textures.
    audio_paths : List[Path]
        Directories for sound and music files.
    window_width : int
        Default window width in pixels.
    window_height : int
        Default window height in pixels.
    """

    game_title: str = "SHARIFA"
    version: str = "0.1.0-alpha"

    #: Root of the game directory (the folder that contains run_game.py).
    base_path: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)

    #: Search paths for models.
    model_paths: List[str] = field(default_factory=lambda: ["assets/models"])

    #: Search paths for textures.
    texture_paths: List[str] = field(default_factory=lambda: ["assets/textures"])

    #: Search paths for audio.
    audio_paths: List[str] = field(default_factory=lambda: ["assets/audio"])

    #: Search paths for general assets (config files, etc.).
    asset_paths: List[str] = field(default_factory=lambda: ["assets"])

    #: Default window dimensions.
    window_width: int = 1280
    window_height: int = 720

    @property
    def window_size(self) -> tuple[int, int]:
        """Return (width, height) as a tuple."""
        return (self.window_width, self.window_height)

    def get_model_dirs(self) -> List[str]:
        """Return absolute model search directories."""
        return [str(self.base_path / p) for p in self.model_paths]

    def get_texture_dirs(self) -> List[str]:
        """Return absolute texture search directories."""
        return [str(self.base_path / p) for p in self.texture_paths]

    def get_audio_dirs(self) -> List[str]:
        """Return absolute audio search directories."""
        return [str(self.base_path / p) for p in self.audio_paths]
