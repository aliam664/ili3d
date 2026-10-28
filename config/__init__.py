"""
Configuration package for the SHARIFA game.

Exports:
- GameConfig: Static game configuration (title, version, paths).
- Settings: User settings with load/save to JSON.
- Constants: Engine constants (collision masks, physics params, etc.).
"""

from .game_config import GameConfig
from .settings import Settings
from .constants import Constants

__all__ = [
    "GameConfig",
    "Settings",
    "Constants",
]
