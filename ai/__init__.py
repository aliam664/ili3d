"""
SHARIFA Game - AI Package

This package provides a complete enemy AI system for the Panda3D 3D FPS engine,
including base enemy classes, specialized enemy types, and multi-phase boss fights.

Modules:
    ai.enemy         - Base Enemy class with full AI state machine, detection,
                       navigation, combat, and visual representation.
    ai.enemy_types   - Eight distinct enemy type classes with unique behaviors.
    ai.bosses        - Six multi-phase boss classes for world-end encounters.

The system integrates with:
    - config.constants.Constants for collision masks and physics params.
    - weapons.weapon for AI weapon handling and combat.
    - worlds.world_base for scene management and pathfinding.

Example:
    from ai import EnemyManager, StandardInfantry, CyberneticOverlord

    manager = EnemyManager(base)
    infantry = manager.spawn_enemy(StandardInfantry, pos=(10, 10, 0))
    boss = manager.spawn_boss(CyberneticOverlord, pos=(50, 50, 0))

Author: SHARIFA Game Development Team
"""

from ai.enemy import (
    Enemy,
    EnemyState,
    AlertLevel,
    SoundType,
    EnemyData,
    PatrolPoint,
    CoverPoint,
    SoundEvent,
    AlertEvent,
    SquadManager,
    EnemyManager,
    create_sound_event,
    line_of_sight_check,
)
from ai.enemy_types import (
    StandardInfantry,
    FastAssault,
    HeavySoldier,
    Sniper,
    StealthEnemy,
    CombatDrone,
    EliteCommander,
    ExperimentalCreature,
)
from ai.bosses import (
    Boss,
    BossPhase,
    CyberneticOverlord,
    WarBeast,
    SecurityCore,
    Guardian,
    Xenomorph,
    NightmareLord,
)

__all__ = [
    # enemy.py
    "Enemy",
    "EnemyState",
    "AlertLevel",
    "SoundType",
    "EnemyData",
    "PatrolPoint",
    "CoverPoint",
    "SoundEvent",
    "AlertEvent",
    "SquadManager",
    "EnemyManager",
    "create_sound_event",
    "line_of_sight_check",
    # enemy_types.py
    "StandardInfantry",
    "FastAssault",
    "HeavySoldier",
    "Sniper",
    "StealthEnemy",
    "CombatDrone",
    "EliteCommander",
    "ExperimentalCreature",
    # bosses.py
    "Boss",
    "BossPhase",
    "CyberneticOverlord",
    "WarBeast",
    "SecurityCore",
    "Guardian",
    "Xenomorph",
    "NightmareLord",
]

__version__ = "1.0.0"
__author__ = "SHARIFA Game Development Team"
