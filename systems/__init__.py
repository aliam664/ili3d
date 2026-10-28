"""
systems package

Player progression and statistics systems for the SHARIFA 3D FPS game.

This package provides a complete player progression framework:
- ``stats``        — comprehensive statistics tracking (kills, accuracy,
                      win rate, K/D ratio, per-mission and per-difficulty
                      breakdowns).
- ``progression``  — XP accumulation, level thresholds, skill trees,
                      weapon mastery, achievements, and mission ratings.
- ``save_manager`` — save/load system with JSON persistence, auto-save
                      at checkpoints, corruption recovery, and backup
                      management.

Usage
-----
>>> from systems import SaveManager, PlayerStats, PlayerProgression
>>>
>>> # At game startup:
>>> sm = SaveManager()
>>> data = sm.load_or_new(player_name="Hero")
>>>
>>> # During gameplay, record events:
>>> data.stats.record_kill(is_headshot=True, difficulty="normal")
>>> data.progression.xp_kill(difficulty="normal")
>>>
>>> # At a checkpoint:
>>> sm.checkpoint()
"""

from __future__ import annotations

# -- Statistics system --
from systems.stats import (
    PlayerStats,
    MissionStats,
    DifficultyStats,
    DIFFICULTY_LEVELS,
    DIFFICULTY_TIERS,
    normalize_difficulty,
    difficulty_tier,
)

# -- Progression system --
from systems.progression import (
    PlayerProgression,
    XPEntry,
    xp_for_level,
    level_from_xp,
    LEVEL_UP_BASE_XP,
    LEVEL_UP_XP_EXPONENT,
    SKILL_POINTS_PER_LEVEL,
    SKILL_TREES,
    MAX_SKILL_POINTS_PER_TREE,
    SkillNode,
    WeaponMastery,
    WeaponMasteryTracker,
    MAX_WEAPON_LEVEL,
    weapon_xp_for_level,
    weapon_level_from_xp,
    Achievement,
    AchievementTracker,
    ACHIEVEMENT_CATEGORIES,
    MissionRating,
    MEDAL_TIERS,
)

# -- Save system --
from systems.save_manager import (
    SaveManager,
    PlayerSaveData,
    SaveSlotInfo,
    SAVE_FILE_VERSION,
    DEFAULT_SAVE_SLOT,
    MAX_BACKUPS,
    get_config_dir,
    get_save_path,
    get_settings_path,
)

__all__ = [
    # -- stats.py --
    "PlayerStats",
    "MissionStats",
    "DifficultyStats",
    "DIFFICULTY_LEVELS",
    "DIFFICULTY_TIERS",
    "normalize_difficulty",
    "difficulty_tier",

    # -- progression.py --
    "PlayerProgression",
    "XPEntry",
    "xp_for_level",
    "level_from_xp",
    "LEVEL_UP_BASE_XP",
    "LEVEL_UP_XP_EXPONENT",
    "SKILL_POINTS_PER_LEVEL",
    "SKILL_TREES",
    "MAX_SKILL_POINTS_PER_TREE",
    "SkillNode",
    "WeaponMastery",
    "WeaponMasteryTracker",
    "MAX_WEAPON_LEVEL",
    "weapon_xp_for_level",
    "weapon_level_from_xp",
    "Achievement",
    "AchievementTracker",
    "ACHIEVEMENT_CATEGORIES",
    "MissionRating",
    "MEDAL_TIERS",

    # -- save_manager.py --
    "SaveManager",
    "PlayerSaveData",
    "SaveSlotInfo",
    "SAVE_FILE_VERSION",
    "DEFAULT_SAVE_SLOT",
    "MAX_BACKUPS",
    "get_config_dir",
    "get_save_path",
    "get_settings_path",
]

__version__ = "1.0.0"
__author__ = "SHARIFA Game Development Team"
