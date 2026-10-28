"""
stats.py

Player statistics tracking system for the SHARIFA 3D FPS game.

This module provides:
- A comprehensive ``PlayerStats`` dataclass that tracks every in-game statistic.
- Per-mission and per-difficulty breakdowns.
- Derived metric calculations (accuracy, win rate, K/D ratio) with
  proper zero-denominator handling.
- Serialization helpers so stats can be stored to / loaded from JSON.

Integration
-----------
The main ``PlayerStats`` class is designed to be owned by the game's
``PlayerController`` (or a dedicated ``StatsManager``).  Weapon and combat
systems should call ``record_kill``, ``record_shot_fired``,
``record_shot_hit``, ``record_death``, and ``record_mission_completion``
as events occur.  The ``SaveManager`` (see ``save_manager.py``) serializes
the stats alongside progression data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Difficulty levels
# ---------------------------------------------------------------------------

#: Ordered list of supported difficulty levels.  Lower index = easier.
DIFFICULTY_LEVELS: Tuple[str, ...] = (
    "easy",
    "normal",
    "hard",
    "nightmare",
    "apocalypse",
)

#: Maps a difficulty name to its numeric tier (0 = easiest).
DIFFICULTY_TIERS: Dict[str, int] = {
    name: idx for idx, name in enumerate(DIFFICULTY_LEVELS)
}


def normalize_difficulty(value: str) -> str:
    """
    Normalize a difficulty string to one of the canonical names.

    Parameters
    ----------
    value : str
        The difficulty string to normalize (case-insensitive).

    Returns
    -------
    str
        The canonical difficulty name, or ``"normal"`` if unrecognized.
    """
    v = str(value).strip().lower()
    if v in DIFFICULTY_TIERS:
        return v
    # Accept numeric indices too.
    if v.isdigit() and 0 <= int(v) < len(DIFFICULTY_LEVELS):
        return DIFFICULTY_LEVELS[int(v)]
    return "normal"


def difficulty_tier(difficulty: str) -> int:
    """Return the numeric tier (0-based) of a difficulty name."""
    return DIFFICULTY_TIERS.get(normalize_difficulty(difficulty), 1)


# ---------------------------------------------------------------------------
#  Per-mission breakdown
# ---------------------------------------------------------------------------


@dataclass
class MissionStats:
    """
    Statistics tracked for a single mission.

    These are accumulated across all *attempts* on a given mission.
    A separate ``MissionRun`` (not persisted here) tracks a single
    play-through for medal calculation.
    """

    mission_id: str = ""
    attempts: int = 0
    completions: int = 0
    defeats: int = 0
    kills: int = 0
    headshots: int = 0
    shots_fired: int = 0
    shots_hit: int = 0
    deaths: int = 0
    bosses_defeated: int = 0
    collectibles_found: int = 0
    total_playtime: float = 0.0  # seconds
    best_time: float = 0.0       # seconds (0 = not set)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict suitable for JSON."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MissionStats":
        """Deserialize from a dict (as produced by ``to_dict``)."""
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
                # No default; use a type-appropriate zero/None.
                kwargs[f_name] = _default_for_field(f_name)
        return cls(**kwargs)


def _default_for_field(field_name: str):
    """Return a sensible default for a known field name (used in from_dict)."""
    defaults: Dict[str, Any] = {
        "mission_id": "",
        "attempts": 0,
        "completions": 0,
        "defeats": 0,
        "kills": 0,
        "headshots": 0,
        "shots_fired": 0,
        "shots_hit": 0,
        "deaths": 0,
        "bosses_defeated": 0,
        "collectibles_found": 0,
        "total_playtime": 0.0,
        "best_time": 0.0,
    }
    return defaults.get(field_name, None)


# ---------------------------------------------------------------------------
#  Per-difficulty breakdown
# ---------------------------------------------------------------------------


@dataclass
class DifficultyStats:
    """
    Statistics tracked for a single difficulty level.

    Tracks aggregate combat and mission metrics so players can see how
    they perform on each difficulty tier.
    """

    difficulty: str = "normal"
    victories: int = 0
    defeats: int = 0
    missions_attempted: int = 0
    missions_completed: int = 0
    enemies_eliminated: int = 0
    headshots: int = 0
    shots_fired: int = 0
    shots_hit: int = 0
    deaths: int = 0
    bosses_defeated: int = 0
    collectibles_discovered: int = 0
    total_playtime: float = 0.0  # seconds
    best_mission_time: float = 0.0  # seconds (0 = not set)
    longest_kill_streak: int = 0
    highest_score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict suitable for JSON."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DifficultyStats":
        """Deserialize from a dict (as produced by ``to_dict``)."""
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
                kwargs[f_name] = _default_for_difficulty_field(f_name)
        return cls(**kwargs)


def _default_for_difficulty_field(field_name: str):
    """Return a sensible default for a known DifficultyStats field."""
    defaults: Dict[str, Any] = {
        "difficulty": "normal",
        "victories": 0,
        "defeats": 0,
        "missions_attempted": 0,
        "missions_completed": 0,
        "enemies_eliminated": 0,
        "headshots": 0,
        "shots_fired": 0,
        "shots_hit": 0,
        "deaths": 0,
        "bosses_defeated": 0,
        "collectibles_discovered": 0,
        "total_playtime": 0.0,
        "best_mission_time": 0.0,
        "longest_kill_streak": 0,
        "highest_score": 0,
    }
    return defaults.get(field_name, None)


# ---------------------------------------------------------------------------
#  Main statistics container
# ---------------------------------------------------------------------------


@dataclass
class PlayerStats:
    """
    Comprehensive player statistics tracking.

    All numeric stats are integers (or floats for time / score) that
    accumulate over the player's career.  Per-mission and per-difficulty
    breakdowns are stored in ``missions`` and ``per_difficulty``.

    Derived metrics — accuracy, win rate, K/D ratio — are exposed as
    computed properties and never stored directly, ensuring they are
    always consistent with the raw counters.
    """

    # -- Overall summary ----------------------------------------------------
    total_victories: int = 0
    total_defeats: int = 0
    missions_attempted: int = 0
    missions_completed: int = 0
    enemies_eliminated: int = 0
    headshots: int = 0
    shots_fired: int = 0
    shots_hit: int = 0
    death_count: int = 0
    total_playtime: float = 0.0  # seconds
    best_mission_time: float = 0.0  # seconds (0 = not set)
    longest_kill_streak: int = 0
    highest_score: int = 0
    bosses_defeated: int = 0
    highest_difficulty_completed: str = ""
    collectibles_discovered: int = 0
    achievements_unlocked: int = 0

    # -- Breakdowns ---------------------------------------------------------
    #: mission_id -> MissionStats
    missions: Dict[str, MissionStats] = field(default_factory=dict)
    #: difficulty_name -> DifficultyStats
    per_difficulty: Dict[str, DifficultyStats] = field(default_factory=dict)

    # -- Kill-streak tracking (runtime, persisted) --------------------------
    #: Current consecutive kills without dying.
    current_kill_streak: int = 0

    # ------------------------------------------------------------------ #
    #  Derived metrics — always computed, never stored                     #
    # ------------------------------------------------------------------ #

    @property
    def overall_win_rate(self) -> float:
        """
        Victory rate as a percentage (0–100).

        Returns 0.0 if no missions have been attempted, avoiding a
        division-by-zero error.
        """
        denominator = self.total_victories + self.total_defeats
        if denominator == 0:
            return 0.0
        return (self.total_victories / denominator) * 100.0

    @property
    def accuracy(self) -> float:
        """
        Accuracy percentage (Shots Hit / Shots Fired × 100).

        Returns 0.0 if no shots have been fired.
        """
        if self.shots_fired == 0:
            return 0.0
        return (self.shots_hit / self.shots_fired) * 100.0

    @property
    def kill_death_ratio(self) -> float:
        """
        Kill / death ratio.

        Returns 0.0 if the player has never died.
        """
        if self.death_count == 0:
            return 0.0
        return self.enemies_eliminated / self.death_count

    @property
    def headshot_percentage(self) -> float:
        """Headshots as a percentage of total kills (0–100)."""
        if self.enemies_eliminated == 0:
            return 0.0
        return (self.headshots / self.enemies_eliminated) * 100.0

    @property
    def survival_rate(self) -> float:
        """
        Mission survival rate (completions / attempts × 100).

        A *mission completed* counts as a survival.  Returns 0.0 if
        no missions have been attempted.
        """
        if self.missions_attempted == 0:
            return 0.0
        return (self.missions_completed / self.missions_attempted) * 100.0

    # ------------------------------------------------------------------ #
    #  Event recording methods                                             #
    # ------------------------------------------------------------------ #

    def record_kill(
        self,
        weapon: str = "",
        is_headshot: bool = False,
        difficulty: str = "",
        mission_id: str = "",
    ) -> int:
        """
        Record an enemy kill.

        Parameters
        ----------
        weapon : str
            The weapon that dealt the killing blow (for future use).
        is_headshot : bool
            Whether the kill was a headshot.
        difficulty : str
            The current difficulty level.
        mission_id : str
            The ID of the mission where the kill occurred.

        Returns
        -------
        int
            The updated current kill streak.
        """
        self.enemies_eliminated += 1
        self.current_kill_streak += 1

        if self.current_kill_streak > self.longest_kill_streak:
            self.longest_kill_streak = self.current_kill_streak

        if is_headshot:
            self.headshots += 1

        # Update per-difficulty breakdown.
        diff = normalize_difficulty(difficulty) if difficulty else ""
        if diff:
            self._ensure_difficulty_stats(diff).enemies_eliminated += 1
            if is_headshot:
                self._ensure_difficulty_stats(diff).headshots += 1
            if self.current_kill_streak > self._ensure_difficulty_stats(diff).longest_kill_streak:
                self._ensure_difficulty_stats(diff).longest_kill_streak = self.current_kill_streak

        # Update per-mission breakdown.
        if mission_id:
            self._ensure_mission_stats(mission_id).kills += 1
            if is_headshot:
                self._ensure_mission_stats(mission_id).headshots += 1

        return self.current_kill_streak

    def record_death(self, difficulty: str = "", mission_id: str = "") -> None:
        """
        Record a player death.

        Resets the current kill streak to zero.

        Parameters
        ----------
        difficulty : str
            The current difficulty level.
        mission_id : str
            The ID of the mission where the death occurred.
        """
        self.death_count += 1
        self.current_kill_streak = 0

        diff = normalize_difficulty(difficulty) if difficulty else ""
        if diff:
            self._ensure_difficulty_stats(diff).deaths += 1

        if mission_id:
            self._ensure_mission_stats(mission_id).deaths += 1

    def record_shot_fired(
        self,
        weapon: str = "",
        difficulty: str = "",
        mission_id: str = "",
    ) -> None:
        """Record a shot fired (weapon discharged)."""
        self.shots_fired += 1

        diff = normalize_difficulty(difficulty) if difficulty else ""
        if diff:
            self._ensure_difficulty_stats(diff).shots_fired += 1

        if mission_id:
            self._ensure_mission_stats(mission_id).shots_fired += 1

    def record_shot_hit(
        self,
        weapon: str = "",
        is_headshot: bool = False,
        difficulty: str = "",
        mission_id: str = "",
    ) -> None:
        """
        Record a shot that hit a target.

        This is called *before* ``record_kill`` so that shot accuracy
        reflects all hits, including non-lethal shots.

        Parameters
        ----------
        weapon : str
            The weapon that fired the shot.
        is_headshot : bool
            Whether the hit was a headshot.
        difficulty : str
            The current difficulty level.
        mission_id : str
            The ID of the mission where the hit occurred.
        """
        self.shots_hit += 1

        diff = normalize_difficulty(difficulty) if difficulty else ""
        if diff:
            d = self._ensure_difficulty_stats(diff)
            d.shots_hit += 1

        if mission_id:
            self._ensure_mission_stats(mission_id).shots_hit += 1

    def record_boss_kill(
        self, boss_name: str = "", difficulty: str = "", mission_id: str = ""
    ) -> None:
        """Record a boss defeat."""
        self.bosses_defeated += 1

        diff = normalize_difficulty(difficulty) if difficulty else ""
        if diff:
            self._ensure_difficulty_stats(diff).bosses_defeated += 1

        if mission_id:
            self._ensure_mission_stats(mission_id).bosses_defeated += 1

        logger.debug("Boss defeated: %s", boss_name or "(unnamed)")

    def record_collectible(self, difficulty: str = "", mission_id: str = "") -> None:
        """Record discovery of a collectible."""
        self.collectibles_discovered += 1

        diff = normalize_difficulty(difficulty) if difficulty else ""
        if diff:
            self._ensure_difficulty_stats(diff).collectibles_discovered += 1

        if mission_id:
            self._ensure_mission_stats(mission_id).collectibles_found += 1

    def record_achievement_unlock(self) -> None:
        """Increment the count of unlocked achievements."""
        self.achievements_unlocked += 1

    def record_playtime(self, seconds: float) -> None:
        """Add *seconds* to total playtime."""
        self.total_playtime += seconds

    def record_score(self, score: int, difficulty: str = "") -> None:
        """
        Record a mission score.

        Updates ``highest_score`` if *score* exceeds the current record.
        Also updates the per-difficulty highest score.
        """
        if score > self.highest_score:
            self.highest_score = score

        diff = normalize_difficulty(difficulty) if difficulty else ""
        if diff:
            d = self._ensure_difficulty_stats(diff)
            if score > d.highest_score:
                d.highest_score = score

    def record_mission_completion(
        self,
        mission_id: str,
        difficulty: str,
        victory: bool,
        completion_time: float = 0.0,
        score: int = 0,
        enemies_killed: int = 0,
        is_boss_mission: bool = False,
    ) -> None:
        """
        Record the outcome of a completed or failed mission.

        Parameters
        ----------
        mission_id : str
            Unique identifier for the mission.
        difficulty : str
            Difficulty level the mission was played on.
        victory : bool
            ``True`` for a win, ``False`` for a defeat.
        completion_time : float
            Time in seconds to complete the mission (0 if not completed).
        score : int
            Score earned for this mission.
        enemies_killed : int
            Number of enemies killed in this mission run.
        is_boss_mission : bool
            Whether this mission featured a boss.
        """
        diff = normalize_difficulty(difficulty)
        ms = self._ensure_mission_stats(mission_id)
        ds = self._ensure_difficulty_stats(diff)

        # -- Overall stats --
        self.missions_attempted += 1

        if victory:
            self.total_victories += 1
            self.missions_completed += 1
            ms.completions += 1
            ms.attempts += 1
            ds.victories += 1
            ds.missions_completed += 1
        else:
            self.total_defeats += 1
            ms.defeats += 1
            ms.attempts += 1
            ds.defeats += 1

        ds.missions_attempted += 1

        # -- Kill counts --
        self.enemies_eliminated += enemies_killed
        ms.kills += enemies_killed
        ds.enemies_eliminated += enemies_killed

        # -- Score --
        if score > 0:
            self.record_score(score, diff)

        # -- Best time --
        if victory and completion_time > 0:
            if self.best_mission_time == 0 or completion_time < self.best_mission_time:
                self.best_mission_time = completion_time
            if ms.best_time == 0 or completion_time < ms.best_time:
                ms.best_time = completion_time
            if ds.best_mission_time == 0 or completion_time < ds.best_mission_time:
                ds.best_mission_time = completion_time

        # -- Highest difficulty --
        if victory:
            current_best = self.highest_difficulty_completed
            current_tier = difficulty_tier(current_best) if current_best else -1
            new_tier = difficulty_tier(diff)
            if new_tier > current_tier:
                self.highest_difficulty_completed = diff

        # -- Boss tracking --
        if is_boss_mission and victory and enemies_killed >= 0:
            # The boss kill is recorded via record_boss_kill; here we just
            # ensure the difficulty-level boss count is consistent.
            pass

    def update_longest_kill_streak(self, new_streak: int) -> None:
        """
        Force-update the longest kill streak.

        Used when a streak ends (e.g. on death or mission end) to ensure
        the persisted record reflects the peak.
        """
        if new_streak > self.longest_kill_streak:
            self.longest_kill_streak = new_streak

    def reset_kill_streak(self) -> None:
        """Reset the current kill streak (called on death or mission end)."""
        self.current_kill_streak = 0

    # ------------------------------------------------------------------ #
    #  Helpers for nested stats management                               #
    # ------------------------------------------------------------------ #

    def _ensure_mission_stats(self, mission_id: str) -> MissionStats:
        """Get or create the ``MissionStats`` for *mission_id*."""
        if mission_id not in self.missions:
            self.missions[mission_id] = MissionStats(mission_id=mission_id)
        return self.missions[mission_id]

    def _ensure_difficulty_stats(self, difficulty: str) -> DifficultyStats:
        """Get or create the ``DifficultyStats`` for *difficulty*."""
        if difficulty not in self.per_difficulty:
            self.per_difficulty[difficulty] = DifficultyStats(difficulty=difficulty)
        return self.per_difficulty[difficulty]

    # ------------------------------------------------------------------ #
    #  Serialization                                                       #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> Dict[str, Any]:
        """
        Full serialization to a JSON-serializable dictionary.

        Returns
        -------
        Dict[str, Any]
            All scalar stats plus nested ``missions`` and
            ``per_difficulty`` dicts.
        """
        data = asdict(self)
        # asdict already handles nested dataclasses recursively.
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerStats":
        """
        Deserialize from a dictionary produced by ``to_dict``.

        Missing keys fall back to their defaults, making the format
        forward-compatible with new fields added in future versions.
        """
        if not isinstance(data, dict):
            logger.warning("PlayerStats.from_dict received non-dict; using defaults.")
            return cls()

        field_names = cls.__dataclass_fields__
        kwargs: Dict[str, Any] = {}

        for f_name in field_names:
            if f_name in ("missions", "per_difficulty"):
                # Handle nested dicts.
                raw = data.get(f_name, {})
                if f_name == "missions":
                    kwargs[f_name] = {
                        k: MissionStats.from_dict(v) if isinstance(v, dict) else v
                        for k, v in raw.items()
                    }
                else:
                    kwargs[f_name] = {
                        k: DifficultyStats.from_dict(v) if isinstance(v, dict) else v
                        for k, v in raw.items()
                    }
            else:
                default = getattr(cls, f_name, None)
                if isinstance(default, type) and hasattr(default, "__dataclass_fields__"):
                    kwargs[f_name] = data.get(f_name, default())
                else:
                    kwargs[f_name] = data.get(f_name, default)

        return cls(**kwargs)


__all__ = [
    "PlayerStats",
    "MissionStats",
    "DifficultyStats",
    "DIFFICULTY_LEVELS",
    "DIFFICULTY_TIERS",
    "normalize_difficulty",
    "difficulty_tier",
]
