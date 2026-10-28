"""
core package

Contains the central engine classes:
- states:     Game state enum and StateManager singleton.
- game:       Main Game class that extends ShowBase.
- scene:      SceneGraph-level helpers (lighting, skybox, etc.).
- audio:      AudioManager for SFX, music, and spatial audio.
"""

from .states import GameState, StateManager
from .game import Game
from .scene import SceneManager
from .audio import AudioManager

__all__ = [
    "GameState",
    "StateManager",
    "Game",
    "SceneManager",
    "AudioManager",
]
