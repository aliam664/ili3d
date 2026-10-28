"""
worlds package

World / level system:
- world_base:      Base World class that loads geometry, lighting, and sky.
- cyberpunk_city:  World 1 -- Neon-soaked megacity.
- wasteland:       World 2 -- Post-apocalyptic wasteland.
- military_facility: World 3 -- Secret military base.
- jungle:          World 4 -- Overgrown jungle ruins.
- arctic:          World 5 -- Frozen research station.
- space_station:   World 6 -- Derelict space station.
- fantasy:         World 7 -- Ancient fantasy realm.
"""

from .world_base import World
from .cyberpunk_city import CyberpunkCity
from .wasteland import Wasteland
from .military_facility import MilitaryFacility
from .jungle import Jungle
from .arctic import Arctic
from .space_station import SpaceStation
from .fantasy import Fantasy

__all__ = [
    "World",
    "CyberpunkCity",
    "Wasteland",
    "MilitaryFacility",
    "Jungle",
    "Arctic",
    "SpaceStation",
    "Fantasy",
]
