"""
player package

Provides the first-person player controller:
- controller:  FPS movement, mouse look, collision detection.
- hands:   First-person hands / weapon model holder.
"""

from .controller import PlayerController
from .hands import HandsController

__all__ = [
    "PlayerController",
    "HandsController",
]
