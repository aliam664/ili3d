"""
progression.py

Player progression system for the SHARIFA 3D FPS game.

This module provides:
- ``PlayerProgression`` — XP accumulation, level thresholds, and
  skill-point rewards on level-up.  Supports 5 skill trees:
  Weapons, Armor, Mobility, Tactical, Utility.
- ``SkillNode`` — a perk in a skill tree with prerequisites and ranks.
- ``WeaponMastery`` / ``WeaponMasteryTracker`` — per-weapon XP, levels
  (1–10), perk unlocks, and visual skin rewards.
- ``Achievement`` / ``AchievementTracker`` — achievement definitions,
  progress tracking, and unlock detection across 5 categories.
- ``MissionRating`` — medal calculation (Bronze / Silver / Gold / Platinum)
  based on completion time, accuracy, deaths, kills, objectives, and
  damage taken.

Integration
-----------
The main ``Game`` instance owns a ``PlayerProgression`` and feeds it
XP events from combat, mission completion, accuracy, etc.  The
``SaveManager`` (see ``save_manager.py``) serializes progression alongside
stats.

Author: SHARIFA Game Development Team
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from systems.stats import normalize_difficulty, difficulty_tier

logger = logging.getLogger(__name__)


# ===========================================================================
#  XP Configuration
# ===========================================================================

#: XP required to reach level *n* (1-based).  Level 1 = 0 XP (starting).
#: Formula: cumulative XP to reach level L is the sum of BASE_XP * i^EXP
#: for i = 1 to L-1.
LEVEL_UP_BASE_XP: int = 500

#: Exponent for the XP growth curve.  Higher = steeper.
LEVEL_UP_XP_EXPONENT: float = 1.5

#: Skill points awarded per level-up (after level 1).
SKILL_POINTS_PER_LEVEL: int = 3

#: Maximum player level.
MAX_PLAYER_LEVEL: int = 100


def xp_for_level(level: int) -> int:
    """
    Total cumulative XP required to *reach* the given level (1-based).

    Level 1 = 0 XP (starting point).  Level 2 = 500.  Each subsequent
    level requires more XP, computed as::

        increment_for_level_n = BASE_XP * (n - 1) ** EXP

    """
    if level <= 1:
        return 0
    total = 0
    for lv in range(2, level + 1):
        total += int(LEVEL_UP_BASE_XP * ((lv - 1) ** LEVEL_UP_XP_EXPONENT))
    return total


def level_from_xp(total_xp: int) -> int:
    """Return the player level for a given total XP value (1-based)."""
    if total_xp <= 0:
        return 1
    level = 1
    while level < MAX_PLAYER_LEVEL and xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


# ===========================================================================
#  Skill Tree Definitions
# ===========================================================================

#: The five skill trees available to the player.
SKILL_TREES: Tuple[str, ...] = (
    "weapons",
    "armor",
    "mobility",
    "tactical",
    "utility",
)

MAX_SKILL_POINTS_PER_TREE: int = 20


@dataclass
class SkillNode:
    """
    A single node in a skill tree.

    Players spend skill points here to gain gameplay bonuses.  Each node
    can be upgraded up to ``max_rank`` times, and may have prerequisites
    that must be unlocked first.

    Attributes
    ----------
    node_id : str
        Unique identifier for this skill node.
    name : str
        Display name.
    description : str
        What the skill does.
    tree : str
        Which skill tree this belongs to.
    tier : int
        Position in the tree (1 = root, 5 = top).
    max_rank : int
        Maximum number of times this node can be upgraded.
    current_rank : int
        Current number of ranks invested.
    prerequisites : List[str]
        IDs of nodes that must be unlocked first.
    bonus_type : str
        ``"multiplicative"`` or ``"additive"``.
    bonus_value : float
        The bonus applied per rank.
    """

    node_id: str = ""
    name: str = ""
    description: str = ""
    tree: str = ""
    tier: int = 1
    max_rank: int = 3
    current_rank: int = 0
    prerequisites: List[str] = field(default_factory=list)
    bonus_type: str = "additive"
    bonus_value: float = 0.05

    def is_unlocked(self) -> bool:
        """Return True if the node has at least one rank invested."""
        return self.current_rank > 0

    def is_maxed(self) -> bool:
        """Return True if the node is at its maximum rank."""
        return self.current_rank >= self.max_rank

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillNode":
        if not isinstance(data, dict):
            return cls()
        kwargs = {}
        for f_name, f_info in cls.__dataclass_fields__.items():
            if f_name in data:
                kwargs[f_name] = data[f_name]
            elif f_info.default is not field.MISSING:
                kwargs[f_name] = f_info.default
            elif f_info.default_factory is not field.MISSING:  # type: ignore[misc]
                kwargs[f_name] = f_info.default_factory()  # type: ignore[misc]
            else:
                kwargs[f_name] = None
        return cls(**kwargs)


def _default_skill_nodes() -> List[SkillNode]:
    """
    Generate the default set of skill nodes across all five trees.

    This provides a full skill tree layout.  The game can extend or
    override it at runtime.
    """
    nodes: List[SkillNode] = []

    # --- Weapons ---
    nodes.append(SkillNode("weapon_damage", "Breach", "Increase weapon damage by 5% per rank.", "weapons", 1, 3, bonus_type="multiplicative", bonus_value=0.05))
    nodes.append(SkillNode("weapon_accuracy", "Steady Aim", "Reduce weapon spread by 5% per rank.", "weapons", 2, 3, bonus_type="multiplicative", bonus_value=0.05, prerequisites=["weapon_damage"]))
    nodes.append(SkillNode("weapon_fire_rate", "Rapid Fire", "Increase fire rate by 5% per rank.", "weapons", 3, 3, bonus_type="multiplicative", bonus_value=0.05, prerequisites=["weapon_accuracy"]))
    nodes.append(SkillNode("crit_damage", "Dead Eye", "Increase critical/headshot damage by 10% per rank.", "weapons", 4, 2, bonus_type="multiplicative", bonus_value=0.10, prerequisites=["weapon_fire_rate"]))
    nodes.append(SkillNode("ammo_capacity", "Deep Pockets", "Increase magazine size by 10% per rank.", "weapons", 5, 2, bonus_type="multiplicative", bonus_value=0.10, prerequisites=["crit_damage"]))

    # --- Armor ---
    nodes.append(SkillNode("armor_durability", "Reinforced", "Increase armor durability by 10% per rank.", "armor", 1, 3, bonus_type="multiplicative", bonus_value=0.10))
    nodes.append(SkillNode("damage_resistance", "Kevlar Weave", "Reduce incoming damage by 5% per rank.", "armor", 2, 3, bonus_type="multiplicative", bonus_value=0.05, prerequisites=["armor_durability"]))
    nodes.append(SkillNode("energy_shield", "Energy Shield", "Gain a regenerating energy shield that absorbs damage.", "armor", 3, 1, bonus_type="additive", bonus_value=25.0, prerequisites=["damage_resistance"]))
    nodes.append(SkillNode("excess_kinetic", "Kinetic Redirection", "Convert 20% of melee damage taken into stamina.", "armor", 4, 2, bonus_type="multiplicative", bonus_value=0.20, prerequisites=["energy_shield"]))
    nodes.append(SkillNode("adaptive_armor", "Adaptive Plating", "Armor reduces 15% more damage from the last damage type taken.", "armor", 5, 2, bonus_type="multiplicative", bonus_value=0.15, prerequisites=["excess_kinetic"]))

    # --- Mobility ---
    nodes.append(SkillNode("movement_speed", "Swift", "Increase movement speed by 5% per rank.", "mobility", 1, 3, bonus_type="multiplicative", bonus_value=0.05))
    nodes.append(SkillNode("jump_height", "Spring Jump", "Increase jump height by 10% per rank.", "mobility", 2, 2, bonus_type="multiplicative", bonus_value=0.10, prerequisites=["movement_speed"]))
    nodes.append(SkillNode("slide_distance", "Momentum Slide", "Slide distance increased by 15% per rank.", "mobility", 3, 2, bonus_type="multiplicative", bonus_value=0.15, prerequisites=["jump_height"]))
    nodes.append(SkillNode("wall_run", "Wall Run", "Briefly run along walls after jumping near them.", "mobility", 4, 1, bonus_type="additive", bonus_value=2.0, prerequisites=["slide_distance"]))
    nodes.append(SkillNode("air_control", "Air Control", "Gain 25% control while airborne.", "mobility", 5, 2, bonus_type="multiplicative", bonus_value=0.25, prerequisites=["wall_run"]))

    # --- Tactical ---
    nodes.append(SkillNode("grenade_damage", "Frag Out", "Increase grenade/explosive damage by 10% per rank.", "tactical", 1, 3, bonus_type="multiplicative", bonus_value=0.10))
    nodes.append(SkillNode("tactical_reload", "Fast Reload", "Reduce reload time by 5% per rank.", "tactical", 2, 3, bonus_type="multiplicative", bonus_value=0.05, prerequisites=["grenade_damage"]))
    nodes.append(SkillNode("quick_switch", "Quick Draw", "Switch weapons 15% faster.", "tactical", 3, 2, bonus_type="multiplicative", bonus_value=0.15, prerequisites=["tactical_reload"]))
    nodes.append(SkillNode("scan_pulse", "Tactical Scan", "Reveal nearby enemies through walls for 3 seconds.", "tactical", 4, 1, bonus_type="additive", bonus_value=5.0, prerequisites=["quick_switch"]))
    nodes.append(SkillNode("headshot_scan", "Weakpoint Analysis", "Headshots extend scan pulse duration by 2 seconds.", "tactical", 5, 1, bonus_type="additive", bonus_value=2.0, prerequisites=["scan_pulse"]))

    # --- Utility ---
    nodes.append(SkillNode("health_regen", "Adrenaline", "Health regenerates 10% faster.", "utility", 1, 3, bonus_type="multiplicative", bonus_value=0.10))
    nodes.append(SkillNode("stamina_pool", "Athlete", "Increase stamina pool by 15% per rank.", "utility", 2, 3, bonus_type="multiplicative", bonus_value=0.15, prerequisites=["health_regen"]))
    nodes.append(SkillNode("pickup_boosts", "Scavenger", "Ammo and health pickups restore 20% more.", "utility", 3, 2, bonus_type="multiplicative", bonus_value=0.20, prerequisites=["stamina_pool"]))
    nodes.append(SkillNode("melee_lifesteal", "Life Leech", "Melee kills restore 25% of max health.", "utility", 4, 2, bonus_type="multiplicative", bonus_value=0.25, prerequisites=["pickup_boosts"]))
    nodes.append(SkillNode("second_wind", "Second Wind", "Revive once per mission with 25% health after fatal damage.", "utility", 5, 1, bonus_type="additive", bonus_value=0.25, prerequisites=["melee_lifesteal"]))

    return nodes


# ===========================================================================
#  Weapon Mastery
# ===========================================================================

#: Maximum weapon mastery level.
MAX_WEAPON_LEVEL: int = 10

#: Base XP required to go from level 1 to level 2.
WEAPON_XP_BASE: int = 100

#: XP growth multiplier per weapon level.
WEAPON_XP_GROWTH: float = 1.2


def weapon_xp_for_level(level: int) -> int:
    """
    Total cumulative XP needed to *reach* the given weapon level.

    Level 1 = 0 XP (starting).
    """
    if level <= 1:
        return 0
    total = 0
    for lv in range(2, level + 1):
        total += int(WEAPON_XP_BASE * (WEAPON_XP_GROWTH ** (lv - 2)))
    return total


def weapon_level_from_xp(total_xp: int) -> int:
    """Return the weapon level for a given total XP (capped at MAX_WEAPON_LEVEL)."""
    if total_xp <= 0:
        return 1
    level = 1
    while level < MAX_WEAPON_LEVEL and weapon_xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


@dataclass
class WeaponMastery:
    """
    Per-weapon mastery progress.

    Each weapon earns XP independently.  Reaching levels 3, 5, 7, and 10
    unlocks perks and visual skins.

    Attributes
    ----------
    weapon_id : str
        Unique weapon identifier.
    total_xp : int
        Cumulative XP earned on this weapon.
    current_level : int
        Current mastery level (1–10).
    total_kills : int
        Total kills with this weapon.
    total_headshots : int
        Headshot kills with this weapon.
    total_shots_fired : int
        Total shots fired.
    total_shots_hit : int
        Total shots that hit a target.
    """

    weapon_id: str = ""
    total_xp: int = 0
    current_level: int = 1
    total_kills: int = 0
    total_headshots: int = 0
    total_shots_fired: int = 0
    total_shots_hit: int = 0

    def add_xp(self, amount: int) -> bool:
        """
        Add XP to this weapon's mastery.

        Returns
        -------
        bool
            ``True`` if the weapon leveled up.
        """
        if amount <= 0 or self.current_level >= MAX_WEAPON_LEVEL:
            return False

        before_level = self.current_level
        self.total_xp += amount

        new_level = weapon_level_from_xp(self.total_xp)
        if new_level > before_level:
            self.current_level = new_level
            logger.info(
                "Weapon '%s' leveled up to %d (total XP: %d)",
                self.weapon_id, new_level, self.total_xp,
            )
            return True
        return False

    def record_kill(self, is_headshot: bool = False) -> None:
        """Record a kill with this weapon, awarding XP."""
        self.total_kills += 1
        if is_headshot:
            self.total_headshots += 1
        xp = 10 + (5 if is_headshot else 0)
        self.add_xp(xp)

    def record_shot(self, hit: bool, is_headshot: bool = False) -> None:
        """Record a shot with this weapon, awarding XP on hit."""
        self.total_shots_fired += 1
        if hit:
            self.total_shots_hit += 1
            self.add_xp(2)

    @property
    def xp_to_next_level(self) -> int:
        """XP needed to reach the next weapon level (0 if max level)."""
        if self.current_level >= MAX_WEAPON_LEVEL:
            return 0
        return max(0, weapon_xp_for_level(self.current_level + 1) - self.total_xp)

    @property
    def progress_percent(self) -> float:
        """Progress toward next level as a percentage (0–100)."""
        if self.current_level >= MAX_WEAPON_LEVEL:
            return 100.0
        current_xp = weapon_xp_for_level(self.current_level)
        next_xp = weapon_xp_for_level(self.current_level + 1)
        if next_xp == current_xp:
            return 100.0
        return ((self.total_xp - current_xp) / (next_xp - current_xp)) * 100.0

    def get_perks_unlocked(self) -> List[str]:
        """Return the list of perk IDs unlocked at the current level."""
        perks: List[str] = []
        # Perks unlock at levels 3, 5, 7, 10
        unlock_levels = [3, 5, 7, 10]
        for unlock_level in unlock_levels:
            if self.current_level >= unlock_level:
                perks.append(f"{self.weapon_id}_perk_{unlock_level}")
        return perks

    def get_skins_unlocked(self) -> List[str]:
        """Return the list of skin IDs unlocked at the current level."""
        skins: List[str] = []
        # Skins unlock at levels 4, 6, 8, 10
        unlock_levels = [4, 6, 8, 10]
        for unlock_level in unlock_levels:
            if self.current_level >= unlock_level:
                skins.append(f"{self.weapon_id}_skin_{unlock_level}")
        return skins

    def is_max_level(self) -> bool:
        """Return True if the weapon is at its maximum level."""
        return self.current_level >= MAX_WEAPON_LEVEL

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeaponMastery":
        if not isinstance(data, dict):
            return cls()
        kwargs = {}
        for f_name, f_info in cls.__dataclass_fields__.items():
            if f_name in data:
                kwargs[f_name] = data[f_name]
            elif f_info.default is not field.MISSING:
                kwargs[f_name] = f_info.default
            elif f_info.default_factory is not field.MISSING:  # type: ignore[misc]
                kwargs[f_name] = f_info.default_factory()  # type: ignore[misc]
            else:
                kwargs[f_name] = None
        return cls(**kwargs)


@dataclass
class WeaponMasteryTracker:
    """
    Tracks mastery for all weapons.

    Provides convenience methods for recording XP from kills and
    shots, and for querying unlocked perks and skins.
    """

    weapons: Dict[str, WeaponMastery] = field(default_factory=dict)

    def get_or_create(self, weapon_id: str) -> WeaponMastery:
        """Get the ``WeaponMastery`` for *weapon_id*, creating it if needed."""
        if weapon_id not in self.weapons:
            self.weapons[weapon_id] = WeaponMastery(weapon_id=weapon_id)
        return self.weapons[weapon_id]

    def add_kill_xp(self, weapon_id: str, is_headshot: bool = False) -> None:
        """Award XP for a kill with *weapon_id*."""
        mastery = self.get_or_create(weapon_id)
        mastery.record_kill(is_headshot)

    def add_shot_hit_xp(self, weapon_id: str) -> None:
        """Award a small amount of XP for each hit."""
        mastery = self.get_or_create(weapon_id)
        mastery.record_shot(hit=True)

    def get_all_perks(self) -> List[str]:
        """Return all perk IDs unlocked across all weapons."""
        perks: List[str] = []
        for mastery in self.weapons.values():
            perks.extend(mastery.get_perks_unlocked())
        return perks

    def get_all_skins(self) -> List[str]:
        """Return all skin IDs unlocked across all weapons."""
        skins: List[str] = []
        for mastery in self.weapons.values():
            skins.extend(mastery.get_skins_unlocked())
        return skins

    def get_unlocked_weapon_ids(self) -> List[str]:
        """Return IDs of all weapons the player has earned XP with."""
        return list(self.weapons.keys())

    def to_dict(self) -> Dict[str, Any]:
        return {
            weapon_id: mastery.to_dict()
            for weapon_id, mastery in self.weapons.items()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeaponMasteryTracker":
        if not isinstance(data, dict):
            return cls()
        weapons: Dict[str, WeaponMastery] = {}
        for wid, wdata in data.items():
            if isinstance(wdata, dict):
                weapons[wid] = WeaponMastery.from_dict(wdata)
        return cls(weapons=weapons)


# ===========================================================================
#  Achievements
# ===========================================================================

#: Achievement categories.
ACHIEVEMENT_CATEGORIES: Tuple[str, ...] = (
    "combat",
    "stealth",
    "exploration",
    "difficulty",
    "multiplayer",
)


@dataclass
class Achievement:
    """
    Definition of a single achievement.

    Parameters
    ----------
    achievement_id : str
        Unique, stable identifier (used as save key).
    name : str
        Display name shown in the UI.
    description : str
        What the player needs to do.
    category : str
        One of ``ACHIEVEMENT_CATEGORIES``.
    hidden : bool
        If True, the achievement is invisible until unlocked.
    criteria_type : str
        The kind of progress this achievement tracks.  Must match
        a key handled by ``AchievementTracker.record_progress``.
        Examples: ``kill_count``, ``headshot_count``, ``accuracy``,
        ``win_streak``, ``difficulty_complete``, ``collectible_find``,
        ``mission_complete``, ``exploration_visit``, ``mastery_level``.
    criteria_target : int
        The threshold value for the criteria_type.
    xp_reward : int
        XP awarded on unlock.
    """

    achievement_id: str = ""
    name: str = ""
    description: str = ""
    category: str = "combat"
    hidden: bool = False
    criteria_type: str = ""
    criteria_target: int = 1
    xp_reward: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Achievement":
        if not isinstance(data, dict):
            return cls()
        kwargs = {}
        for f_name, f_info in cls.__dataclass_fields__.items():
            if f_name in data:
                kwargs[f_name] = data[f_name]
            elif f_info.default is not field.MISSING:
                kwargs[f_name] = f_info.default
            elif f_info.default_factory is not field.MISSING:  # type: ignore[misc]
                kwargs[f_name] = f_info.default_factory()  # type: ignore[misc]
            else:
                kwargs[f_name] = None
        return cls(**kwargs)


def _default_achievements() -> List[Achievement]:
    """Return the default set of achievements for the game."""
    return [
        # -- Combat --
        Achievement("first_blood", "First Blood", "Eliminate your first enemy.", "combat", False, "kill_count", 1, 100),
        Achievement("century_killer", "Century Killer", "Eliminate 100 enemies.", "combat", False, "kill_count", 100, 250),
        Achievement("master_markman", "Master Marksman", "Get 50 headshots.", "combat", False, "headshot_count", 50, 300),
        Achievement("deadly_precision", "Deadly Precision", "Kill 5 enemies in a row without missing a shot.", "combat", False, "kill_streak", 5, 200),
        Achievement("annihilation", "Annihilation", "Eliminate 10 enemies within 10 seconds.", "combat", True, "multi_kill", 10, 500),
        Achievement("pistol_whip", "Pistol Whip", "Kill 25 enemies with melee attacks.", "combat", False, "melee_kill", 25, 200),

        # -- Stealth --
        Achievement("ghost", "Ghost", "Complete a mission without being detected.", "stealth", False, "undetected_mission", 1, 250),
        Achievement("silent_but_deadly", "Silent But Deadly", "Get 30 silent kills.", "stealth", False, "silent_kill", 30, 300),
        Achievement("shadow_dancer", "Shadow Dancer", "Complete 5 missions in stealth.", "stealth", True, "undetected_mission", 5, 500),

        # -- Exploration --
        Achievement("explorer", "Explorer", "Discover 25 collectibles.", "exploration", False, "collectible_find", 25, 200),
        Achievement("tourist", "Tourist", "Visit all mission areas.", "exploration", True, "exploration_visit", 10, 300),
        Achievement("treasure_hunter", "Treasure Hunter", "Find all hidden caches in a single mission.", "exploration", True, "collectible_find", 10, 400),

        # -- Difficulty --
        Achievement("difficulty_easy", "Easy Victor", "Complete the game on Easy difficulty.", "difficulty", False, "difficulty_complete", 0, 200),
        Achievement("difficulty_normal", "Normal Victor", "Complete the game on Normal difficulty.", "difficulty", False, "difficulty_complete", 1, 300),
        Achievement("difficulty_hard", "Hardened", "Complete the game on Hard difficulty.", "difficulty", False, "difficulty_complete", 2, 500),
        Achievement("difficulty_nightmare", "Nightmare Slayer", "Complete the game on Nightmare difficulty.", "difficulty", True, "difficulty_complete", 3, 750),
        Achievement("difficulty_apocalypse", "Apocalypse", "Complete the game on Apocalypse difficulty.", "difficulty", True, "difficulty_complete", 4, 1000),

        # -- Multiplayer --
        Achievement("team_player", "Team Player", "Revive 10 teammates.", "multiplayer", False, "teammate_revive", 10, 200),
        Achievement("dominance", "Dominance", "Win 50 multiplayer matches.", "multiplayer", True, "match_win", 50, 500),
        Achievement("unstoppable", "Unstoppable", "Get a 20-kill streak in multiplayer.", "multiplayer", True, "kill_streak", 20, 1000),
    ]


@dataclass
class AchievementTracker:
    """
    Tracks achievement definitions and player progress.

    Parameters
    ----------
    achievements : Dict[str, Achievement]
        All defined achievements, keyed by ``achievement_id``.
    unlocked : set[str]
        Set of achievement IDs the player has unlocked.
    progress : Dict[str, int]
        Current progress value for tracked event types.
    """

    achievements: Dict[str, Achievement] = field(default_factory=dict)
    unlocked: set = field(default_factory=set)
    progress: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Populate default achievements if the dict is empty."""
        if not self.achievements:
            for ach in _default_achievements():
                self.achievements[ach.achievement_id] = ach

    def record_progress(self, event_type: str, value: int = 1) -> List[Achievement]:
        """
        Record progress for an event and return newly unlocked achievements.

        Parameters
        ----------
        event_type : str
            The criteria_type to update (e.g. "kill_count",
            "headshot_count", "collectible_find", etc.).
        value : int
            Amount to add to the progress counter (default 1).

        Returns
        -------
        List[Achievement]
            Achievements that were unlocked by this progress event.
        """
        if event_type not in self.progress:
            self.progress[event_type] = 0
        self.progress[event_type] += value

        newly_unlocked: List[Achievement] = []
        for ach in self.achievements.values():
            if ach.achievement_id in self.unlocked:
                continue
            if ach.criteria_type == event_type:
                if self.progress[event_type] >= ach.criteria_target:
                    self.unlock(ach.achievement_id)
                    newly_unlocked.append(ach)

        return newly_unlocked

    def unlock(self, achievement_id: str) -> bool:
        """
        Manually unlock an achievement by ID.

        Returns ``True`` if the achievement was newly unlocked.
        """
        if achievement_id in self.unlocked:
            return False
        ach = self.achievements.get(achievement_id)
        if ach is None:
            logger.warning("Attempted to unlock unknown achievement: %s", achievement_id)
            return False
        self.unlocked.add(achievement_id)
        logger.info("Achievement unlocked: %s - %s", ach.name, ach.description)
        return True

    def is_unlocked(self, achievement_id: str) -> bool:
        """Check if an achievement has been unlocked."""
        return achievement_id in self.unlocked

    def get_progress(self, achievement_id: str) -> Tuple[int, int]:
        """
        Get progress for an achievement.

        Returns
        -------
        Tuple[int, int]
            ``(current_progress, target_progress)``.
        """
        ach = self.achievements.get(achievement_id)
        if ach is None:
            return (0, 0)
        current = self.progress.get(ach.criteria_type, 0)
        return (current, ach.criteria_target)

    def get_visible_achievements(self) -> List[Achievement]:
        """Return achievements visible to the player (unlocked or non-hidden)."""
        result = []
        for ach in self.achievements.values():
            if not ach.hidden or ach.achievement_id in self.unlocked:
                result.append(ach)
        return result

    def get_unlocked_achievements(self) -> List[Achievement]:
        """Return all unlocked achievements sorted by category."""
        result = [
            self.achievements[aid]
            for aid in self.unlocked
            if aid in self.achievements
        ]
        result.sort(key=lambda a: (a.category, a.name))
        return result

    def get_total_achievements(self) -> int:
        """Return the total number of defined achievements."""
        return len(self.achievements)

    def get_unlocked_count(self) -> int:
        """Return the number of unlocked achievements."""
        return len(self.unlocked)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "achievements": {k: v.to_dict() for k, v in self.achievements.items()},
            "unlocked": list(self.unlocked),
            "progress": dict(self.progress),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AchievementTracker":
        if not isinstance(data, dict):
            return cls()

        achievements: Dict[str, Achievement] = {}
        for k, v in data.get("achievements", {}).items():
            if isinstance(v, dict):
                achievements[k] = Achievement.from_dict(v)

        unlocked = set(data.get("unlocked", []))
        progress = dict(data.get("progress", {}))

        return cls(
            achievements=achievements,
            unlocked=unlocked,
            progress=progress,
        )


# ===========================================================================
#  Mission Rating
# ===========================================================================

#: Medal tiers, ordered from best to worst.
MEDAL_TIERS: Tuple[str, ...] = ("platinum", "gold", "silver", "bronze", "none")


@dataclass
class MissionRating:
    """
    Calculates a mission completion rating (medal).

    The rating is determined by six performance metrics, each
    contributing a weighted score.  The total score maps to a medal:

    - Platinum: 90+ points
    - Gold:     75+
    - Silver:   50+
    - Bronze:   25+
    - None:     < 25

    Parameters
    ----------
    max_completion_time : float
        Time limit in seconds for the mission (from mission config).
    completion_time : float
        Actual time taken to complete the mission.
    accuracy : float
        Weapon accuracy percentage (0–100).
    deaths : int
        Number of times the player died.
    enemies_killed : int
        Number of enemies eliminated.
    total_enemies : int
        Total number of enemies in the mission.
    objectives_completed : int
        Number of objectives completed.
    total_objectives : int
        Total number of objectives in the mission.
    damage_taken : int
        Total damage the player received.
    max_damage_threshold : int
        Damage threshold above which points are deducted.
    """

    # Thresholds
    max_completion_time: float = 300.0
    completion_time: float = 0.0
    accuracy: float = 0.0
    deaths: int = 0
    enemies_killed: int = 0
    total_enemies: int = 1
    objectives_completed: int = 0
    total_objectives: int = 1
    damage_taken: int = 0
    max_damage_threshold: int = 50

    # Weights (must sum to 1.0 for a 0–100 score)
    _WEIGHTS: Dict[str, float] = field(
        default_factory=lambda: {
            "time": 0.25,
            "accuracy": 0.20,
            "deaths": 0.15,
            "kills": 0.15,
            "objectives": 0.15,
            "damage": 0.10,
        },
        repr=False,
    )

    def calculate_total_score(self) -> float:
        """
        Calculate the weighted total score (0–100).

        Uses the constants in ``_WEIGHTS``.
        """
        weights = self._WEIGHTS

        # 1. Time bonus: faster completion → more points.
        time_score = self._score_time()
        total = time_score * weights["time"]

        # 2. Accuracy.
        acc_score = min(max(self.accuracy, 0), 100)
        total += acc_score * weights["accuracy"]

        # 3. Deaths penalty.
        death_score = self._score_deaths()
        total += death_score * weights["deaths"]

        # 4. Kill ratio.
        kill_score = self._score_kills()
        total += kill_score * weights["kills"]

        # 5. Objectives.
        obj_score = self._score_objectives()
        total += obj_score * weights["objectives"]

        # 6. Damage taken.
        dmg_score = self._score_damage()
        total += dmg_score * weights["damage"]

        return round(total, 2)

    def _score_time(self) -> float:
        """Score for completion time (0–100)."""
        if self.max_completion_time <= 0 or self.completion_time <= 0:
            return 0.0
        ratio = self.completion_time / self.max_completion_time
        if ratio <= 1.0:
            return 100.0
        elif ratio <= 2.0:
            return 100.0 * (2.0 - ratio)
        else:
            return 0.0

    def _score_deaths(self) -> float:
        """Score for number of deaths (0 deaths = 100, 1 = 50, 2 = 25, 3+ = 0)."""
        if self.deaths <= 0:
            return 100.0
        elif self.deaths == 1:
            return 50.0
        elif self.deaths == 2:
            return 25.0
        else:
            return 0.0

    def _score_kills(self) -> float:
        """Score for enemies killed (0–100 based on kill ratio)."""
        if self.total_enemies <= 0:
            return 0.0
        ratio = min(self.enemies_killed / self.total_enemies, 1.0)
        return ratio * 100.0

    def _score_objectives(self) -> float:
        """Score for objectives completed (0–100)."""
        if self.total_objectives <= 0:
            return 0.0
        ratio = min(self.objectives_completed / self.total_objectives, 1.0)
        return ratio * 100.0

    def _score_damage(self) -> float:
        """
        Score for damage taken (0–100).

        No damage = 100 points.  Linear penalty up to
        ``max_damage_threshold``, then 0.
        """
        if self.damage_taken <= 0:
            return 100.0
        if self.max_damage_threshold <= 0:
            return 50.0
        ratio = min(self.damage_taken / self.max_damage_threshold, 1.0)
        return (1.0 - ratio) * 100.0

    def get_medal(self) -> str:
        """
        Determine the medal based on total score.

        Returns
        -------
        str
            One of ``"platinum"``, ``"gold"``, ``"silver"``, ``"bronze"``,
            ``"none"``.
        """
        score = self.calculate_total_score()
        if score >= 90:
            return "platinum"
        elif score >= 75:
            return "gold"
        elif score >= 50:
            return "silver"
        elif score >= 25:
            return "bronze"
        else:
            return "none"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MissionRating":
        if not isinstance(data, dict):
            return cls()
        # Remove any attempt to set _WEIGHTS from serialized data;
        # it always uses the class-level default factory.
        data.pop("_WEIGHTS", None)
        kwargs = {}
        for f_name, f_info in cls.__dataclass_fields__.items():
            if f_name == "_WEIGHTS":
                continue  # skip the weights field entirely
            if f_name in data:
                kwargs[f_name] = data[f_name]
            elif f_info.default is not field.MISSING:
                kwargs[f_name] = f_info.default
            elif f_info.default_factory is not field.MISSING:  # type: ignore[misc]
                kwargs[f_name] = f_info.default_factory()  # type: ignore[misc]
            else:
                # No default — use type-appropriate zero.
                kwargs[f_name] = 0 if isinstance(f_info.type, type) and issubclass(f_info.type, (int, float)) else None
        return cls(**kwargs)


# ===========================================================================
#  Player Progression (main class)
# ===========================================================================


@dataclass
class PlayerProgression:
    """
    Core player progression: XP, level, skill points, and skill tree state.

    Usage
    -----
    Create an instance at game start (or load from save), then call
    ``add_xp_*`` methods whenever the corresponding event occurs.

    Attributes
    ----------
    total_xp : int
        Cumulative XP earned across all activities.
    current_level : int
        Player's current level (1-based).
    skill_points : int
        Unspent skill points available for allocation.
    skill_nodes : Dict[str, SkillNode]
        All skill nodes keyed by ``node_id``.
    xp_history : List[XPEntry]
        Audit trail of every XP event.
    """

    total_xp: int = 0
    current_level: int = 1
    skill_points: int = 0
    skill_nodes: Dict[str, SkillNode] = field(default_factory=dict)
    xp_history: List["XPEntry"] = field(default_factory=list)

    # Weapon mastery is tracked separately by WeaponMasteryTracker,
    # but we keep a reference for convenience.
    weapon_mastery: Dict[str, WeaponMastery] = field(default_factory=dict)

    # Lock for level-up event to avoid re-entrancy.
    _leveling_up: bool = field(default=False, repr=False)

    # ------------------------------------------------------------------ #
    #  Initialization                                                     #
    # ------------------------------------------------------------------ #

    def __post_init__(self) -> None:
        """Populate skill nodes if the dict is empty."""
        if not self.skill_nodes:
            for node in _default_skill_nodes():
                self.skill_nodes[node.node_id] = node

    # ------------------------------------------------------------------ #
    #  XP Award Methods                                                  #
    # ------------------------------------------------------------------ -->

    def add_xp(
        self,
        amount: int,
        source: str = "",
        detail: str = "",
        timestamp: float = 0.0,
    ) -> bool:
        """
        Add *amount* of XP from a generic *source*.

        Parameters
        ----------
        amount : int
            XP to add.  Must be non-negative.
        source : str
            Short identifier for the XP category (e.g. "kill",
            "headshot", "mission_complete").
        detail : str
            Additional context string (weapon name, mission name, etc.).
        timestamp : float
            Game time or mission time when the XP was earned.

        Returns
        -------
        bool
            ``True`` if the player leveled up as a result.
        """
        if amount <= 0:
            return False

        before_level = self.current_level
        self.total_xp += amount

        self.xp_history.append(XPEntry(
            amount=amount,
            source=source,
            detail=detail,
            timestamp=timestamp,
        ))

        # Keep history from growing unbounded.
        max_history = 200
        if len(self.xp_history) > max_history:
            self.xp_history = self.xp_history[-max_history:]

        new_level = level_from_xp(self.total_xp)
        leveled_up = new_level > before_level

        if leveled_up:
            self.current_level = new_level
            # Award skill points: 3 per level gained.
            levels_gained = new_level - before_level
            self.skill_points += levels_gained * SKILL_POINTS_PER_LEVEL
            logger.info(
                "Level up! Now level %d (XP: %d, SP: %d)",
                new_level, self.total_xp, self.skill_points,
            )

        return leveled_up

    # -- Specific XP awarders ------------------------------------------

    def xp_kill(self, weapon_id: str = "", difficulty: str = "normal", is_headshot: bool = False) -> int:
        """
        XP for eliminating an enemy.

        Awards XP scaled by difficulty and weapon mastery.
        Also updates weapon mastery.
        """
        diff = normalize_difficulty(difficulty)
        diff_index = DIFFICULTY_LEVELS.index(diff)
        multiplier = 1.0 + (diff_index * 0.5)

        base_xp = 25
        amount = int(base_xp * multiplier)

        if is_headshot:
            amount += int(15 * multiplier)
            self.xp_headshot(difficulty)

        # Weapon mastery.
        if weapon_id:
            wm = self._get_weapon_mastery(weapon_id)
            wm.record_kill(is_headshot)

        self.add_xp(amount, "kill", detail=f"kill with {weapon_id or 'unknown'} on {diff}")
        return amount

    def xp_headshot(self, difficulty: str = "normal") -> int:
        """Bonus XP for a headshot."""
        diff = normalize_difficulty(difficulty)
        diff_index = DIFFICULTY_LEVELS.index(diff)
        multiplier = 1.0 + (diff_index * 0.5)
        amount = int(25 * multiplier)
        self.add_xp(amount, "headshot", detail=f"headshot on {diff}")
        return amount

    def xp_accuracy_bonus(self, accuracy: float) -> int:
        """
        XP bonus for high accuracy.

        Parameters
        ----------
        accuracy : float
            Accuracy percentage (0–100).

        Returns
        -------
        int
            XP awarded (0 if accuracy < 75%).
        """
        if accuracy < 75.0:
            return 0
        amount = int(10 * ((accuracy - 75) / 25.0))
        if amount > 0:
            self.add_xp(amount, "accuracy_bonus", detail=f"accuracy={accuracy:.1f}%")
        return amount

    def xp_mission_completion(
        self,
        mission_id: str = "",
        difficulty: str = "normal",
        is_primary_objective: bool = True,
        time_bonus: float = 0.0,
        stealth_bonus: bool = False,
        exploration_bonus: bool = False,
        score: int = 0,
    ) -> int:
        """
        XP for completing a mission.

        Parameters
        ----------
        mission_id : str
            The mission's identifier.
        difficulty : str
            Difficulty the mission was played on.
        is_primary_objective : bool
            Whether the main objective was completed.
        time_bonus : float
            Time remaining in seconds (converted to XP).
        stealth_bonus : bool
            Whether the player avoided detection.
        exploration_bonus : bool
            Whether exploration objectives were completed.
        score : int
            Mission score (contributes to XP).

        Returns
        -------
        int
            Total XP awarded for this mission.
        """
        diff = normalize_difficulty(difficulty)
        diff_index = DIFFICULTY_LEVELS.index(diff)
        multiplier = 1.0 + (diff_index * 0.5)

        total = 0

        # Base completion XP
        base = 100 if is_primary_objective else 50
        total += int(base * multiplier)

        # Time bonus (1 XP per 3 seconds remaining)
        if time_bonus > 0:
            total += int(time_bonus / 3.0)

        # Stealth bonus
        if stealth_bonus:
            total += int(75 * multiplier)

        # Exploration bonus
        if exploration_bonus:
            total += int(50 * multiplier)

        # Score contributes
        total += int(score / 10.0)

        if total > 0:
            self.add_xp(
                total, "mission_complete",
                detail=f"{diff} {'primary' if is_primary_objective else 'side'} mission",
            )

        return total

    def xp_objective_completed(self, objective_type: str, difficulty: str = "normal") -> int:
        """XP for completing a single objective."""
        diff = normalize_difficulty(difficulty)
        diff_index = DIFFICULTY_LEVELS.index(diff)
        multiplier = 1.0 + (diff_index * 0.5)
        amount = int(25 * multiplier)
        self.add_xp(amount, "objective", detail=objective_type)
        return amount

    def xp_boss_kill(self, boss_name: str, difficulty: str = "normal") -> int:
        """XP for defeating a boss."""
        diff = normalize_difficulty(difficulty)
        diff_index = DIFFICULTY_LEVELS.index(diff)
        multiplier = 1.0 + (diff_index * 0.5)
        amount = int(150 * multiplier)
        self.add_xp(amount, "boss_kill", detail=f"{boss_name} on {diff}")
        return amount

    def xp_exploration(self, collectible_name: str = "") -> int:
        """XP for discovering a collectible or hidden area."""
        amount = 15
        self.add_xp(amount, "exploration", detail=collectible_name)
        return amount

    def xp_weapon_mastery(self, weapon_id: str, new_level: int) -> int:
        """
        XP awarded when a weapon reaches a new mastery level.

        Called by ``WeaponMastery.add_xp`` indirectly.
        """
        amount = 50 * new_level
        self.add_xp(amount, "weapon_mastery", detail=f"{weapon_id} → level {new_level}")
        return amount

    # ------------------------------------------------------------------ #
    #  Level & Progression Queries                                       #
    # ------------------------------------------------------------------ -->

    @property
    def xp_to_next_level(self) -> int:
        """XP still needed to reach the next level."""
        next_level = self.current_level + 1
        return max(0, xp_for_level(next_level) - self.total_xp)

    @property
    def xp_progress_percent(self) -> float:
        """Progress towards next level as a percentage (0–100)."""
        current_xp = xp_for_level(self.current_level)
        next_xp = xp_for_level(self.current_level + 1)
        if next_xp == current_xp:
            return 100.0
        return ((self.total_xp - current_xp) / (next_xp - current_xp)) * 100.0

    @property
    def total_xp_for_current_level(self) -> int:
        """Total XP required to reach the current level."""
        return xp_for_level(self.current_level)

    def is_max_level(self) -> bool:
        """Return True if the player has reached the maximum level."""
        return self.current_level >= MAX_PLAYER_LEVEL

    # ------------------------------------------------------------------ #
    #  Skill Tree Management                                             #
    # ------------------------------------------------------------------ -->

    def can_unlock_node(self, node_id: str) -> bool:
        """
        Check whether a skill node can be upgraded.

        Returns True if the player has enough skill points, has
        met all prerequisites, and the node is not yet maxed.
        """
        node = self.skill_nodes.get(node_id)
        if node is None:
            return False
        if node.is_maxed():
            return False
        if self.skill_points < 1:
            return False
        for prereq in node.prerequisites:
            prereq_node = self.skill_nodes.get(prereq)
            if prereq_node is None or not prereq_node.is_unlocked():
                return False
        return True

    def unlock_node(self, node_id: str) -> bool:
        """
        Spend a skill point to increase the rank of *node_id*.

        Returns True if successful.
        """
        if not self.can_unlock_node(node_id):
            return False

        node = self.skill_nodes[node_id]
        node.current_rank += 1
        self.skill_points -= 1
        logger.info("Unlocked '%s' to rank %d/%d", node_id, node.current_rank, node.max_rank)
        return True

    def get_skill_bonus(self, tree: str, bonus_type: str = "multiplicative") -> float:
        """
        Calculate the total bonus for a given tree and bonus type.

        For multiplicative bonuses, returns ``1 + sum(values)``.
        For additive bonuses, returns ``sum(values)``.
        """
        bonus = 0.0
        for node in self.skill_nodes.values():
            if node.tree != tree:
                continue
            if not node.is_unlocked():
                continue
            if node.bonus_type == bonus_type:
                bonus += node.bonus_value * node.current_rank

        if bonus_type == "multiplicative":
            return 1.0 + bonus
        return bonus

    def get_all_bonuses(self) -> Dict[str, Dict[str, float]]:
        """
        Return a nested dict of all skill bonuses, organized by tree.

        Returns
        -------
        Dict[str, Dict[str, float]]
            ``{tree_name: {"multiplicative": float, "additive": float}}``
        """
        result: Dict[str, Dict[str, float]] = {}
        for tree in SKILL_TREES:
            result[tree] = {
                "multiplicative": self.get_skill_bonus(tree, "multiplicative"),
                "additive": self.get_skill_bonus(tree, "additive"),
            }
        return result

    def get_unlocked_skills(self) -> List[str]:
        """Return list of unlocked skill node IDs."""
        return [sid for sid, node in self.skill_nodes.items() if node.is_unlocked()]

    def reset_all_skills(self) -> None:
        """Reset all skill nodes to rank 0 and refund all skill points."""
        total_points = 0
        for node in self.skill_nodes.values():
            total_points += node.current_rank
            node.current_rank = 0
        self.skill_points += total_points

    # ------------------------------------------------------------------ #
    #  Weapon Mastery access                                             #
    # ------------------------------------------------------------------ -->

    def _get_weapon_mastery(self, weapon_id: str) -> WeaponMastery:
        """Get or create WeaponMastery for a weapon."""
        if weapon_id not in self.weapon_mastery:
            self.weapon_mastery[weapon_id] = WeaponMastery(weapon_id=weapon_id)
        return self.weapon_mastery[weapon_id]

    def get_weapon_level(self, weapon_id: str) -> int:
        """Return the current mastery level of a weapon (1–10)."""
        return self._get_weapon_mastery(weapon_id).current_level

    def get_weapon_mastery(self, weapon_id: str) -> WeaponMastery:
        """Return the WeaponMastery object for a weapon."""
        return self._get_weapon_mastery(weapon_id)

    def get_all_weapon_perks(self) -> List[str]:
        """Return all perk IDs unlocked across all weapons."""
        perks: List[str] = []
        for mastery in self.weapon_mastery.values():
            perks.extend(mastery.get_perks_unlocked())
        return perks

    def get_all_weapon_skins(self) -> List[str]:
        """Return all skin IDs unlocked across all weapons."""
        skins: List[str] = []
        for mastery in self.weapon_mastery.values():
            skins.extend(mastery.get_skins_unlocked())
        return skins

    # ------------------------------------------------------------------ #
    #  Unlocked content tracking                                         #
    # ------------------------------------------------------------------ -->

    def unlock_weapon(self, weapon_id: str) -> None:
        """Unlock a weapon (makes it available in the loadout)."""
        # Weapon unlocks are tracked in PlayerSaveData, but we also
        # track weapon mastery here for immediate access.
        self._get_weapon_mastery(weapon_id)

    def unlock_attachment(self, attachment_id: str) -> None:
        """Unlock an attachment. (No-op here; tracked in save data.)"""
        pass

    # ------------------------------------------------------------------ #
    #  Achievements                                                      #
    # ------------------------------------------------------------------ -->

    @staticmethod
    def get_default_achievements() -> List[Achievement]:
        """Return the default achievement list."""
        return _default_achievements()

    @staticmethod
    def get_achievement_categories() -> Tuple[str, ...]:
        """Return the tuple of achievement category names."""
        return ACHIEVEMENT_CATEGORIES

    # ------------------------------------------------------------------ #
    #  Serialization                                                       #
    # ------------------------------------------------------------------ -->

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "total_xp": self.total_xp,
            "current_level": self.current_level,
            "skill_points": self.skill_points,
            "skill_nodes": {k: v.to_dict() for k, v in self.skill_nodes.items()},
            "weapon_mastery": {k: v.to_dict() for k, v in self.weapon_mastery.items()},
            "xp_history": [asdict(e) for e in self.xp_history],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerProgression":
        """Deserialize from a dict produced by ``to_dict``."""
        if not isinstance(data, dict):
            return cls()

        skill_nodes: Dict[str, SkillNode] = {}
        for k, v in data.get("skill_nodes", {}).items():
            if isinstance(v, dict):
                skill_nodes[k] = SkillNode.from_dict(v)

        weapon_mastery_raw = data.get("weapon_mastery", {})
        weapon_mastery: Dict[str, WeaponMastery] = {}
        for wid, wd in weapon_mastery_raw.items():
            if isinstance(wd, dict):
                weapon_mastery[wid] = WeaponMastery.from_dict(wd)

        xp_history_raw = data.get("xp_history", [])
        xp_history: List[XPEntry] = []
        for entry in xp_history_raw:
            if isinstance(entry, dict):
                xp_history.append(XPEntry(**{
                    k: entry.get(k, getattr(XPEntry, k, None))
                    for k in XPEntry.__dataclass_fields__
                }))

        return cls(
            total_xp=data.get("total_xp", 0),
            current_level=data.get("current_level", 1),
            skill_points=data.get("skill_points", 0),
            skill_nodes=skill_nodes,
            weapon_mastery=weapon_mastery,
            xp_history=xp_history,
        )


# ===========================================================================
#  XP Entry (audit trail)
# ===========================================================================


@dataclass
class XPEntry:
    """
    A single XP gain event.

    Used for audit trails and UI display (e.g. floating XP numbers).
    """

    amount: int = 0
    source: str = ""
    detail: str = ""
    timestamp: float = 0.0


def calculate_xp_award(
    difficulty: str,
    kills: int,
    headshots: int,
    accuracy: float,
    time_taken: float,
    objectives_complete: int,
    stealth_bonus: bool = False,
) -> int:
    """
    Utility function to calculate total XP for a mission based on performance.

    Parameters
    ----------
    difficulty : str
        The difficulty level the mission was played on.
    kills : int
        Number of enemies killed.
    headshots : int
        Number of headshots.
    accuracy : float
        Accuracy percentage (0–100).
    time_taken : float
        Time taken to complete the mission in seconds.
    objectives_complete : int
        Number of objectives completed.
    stealth_bonus : bool
        Whether the stealth bonus condition was met.

    Returns
    -------
    int
        Total XP awarded.
    """
    diff = normalize_difficulty(difficulty)
    diff_index = DIFFICULTY_LEVELS.index(diff)
    mult = 1.0 + (diff_index * 0.5)

    xp = 0

    # Base kill XP.
    xp += int(kills * 25 * mult)
    xp += int(headshots * 25 * mult)

    # Accuracy bonus.
    if accuracy >= 95:
        xp += int(100 * 2 * mult)
    elif accuracy >= 85:
        xp += int(100 * mult)
    elif accuracy >= 75:
        xp += int(100 * 0.5 * mult)

    # Objective completion bonus.
    xp += int(objectives_complete * 25 * mult)

    # Stealth bonus.
    if stealth_bonus:
        xp += int(75 * mult)

    # Time bonus (completing under par).
    if time_taken > 0:
        if time_taken < 120:
            xp += int(200 * mult)
        elif time_taken < 300:
            xp += int(100 * mult)

    return xp


__all__ = [
    # XP / level
    "PlayerProgression",
    "XPEntry",
    "xp_for_level",
    "level_from_xp",
    "LEVEL_UP_BASE_XP",
    "LEVEL_UP_XP_EXPONENT",
    "SKILL_POINTS_PER_LEVEL",
    "MAX_PLAYER_LEVEL",
    "calculate_xp_award",

    # Skill trees
    "SKILL_TREES",
    "MAX_SKILL_POINTS_PER_TREE",
    "SkillNode",
    "_default_skill_nodes",

    # Weapon mastery
    "WeaponMastery",
    "WeaponMasteryTracker",
    "MAX_WEAPON_LEVEL",
    "weapon_xp_for_level",
    "weapon_level_from_xp",

    # Achievements
    "Achievement",
    "AchievementTracker",
    "ACHIEVEMENT_CATEGORIES",
    "_default_achievements",

    # Mission ratings
    "MissionRating",
    "MEDAL_TIERS",
]
