"""
game_modes.py

Game modes: defines the GameMode base class and concrete mode implementations.

Each mode defines its own rules, win conditions, scoring, and configuration
for a specific style of play:
- CampaignMode: Story-driven missions across all worlds.
- SurvivalMode: Endless waves of enemies.
- BossRushMode: Fight all bosses in sequence.
- TimeAttackMode: Race against the clock to complete objectives.
- TrainingRangeMode: Practice with unlimited ammo and no enemies.
- StealthOpsMode: Infiltrate without being detected.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class GameModeType(Enum):
    """Enumerates all available game modes."""
    CAMPAIGN = "campaign"
    SURVIVAL = "survival"
    BOSS_RUSH = "boss_rush"
    TIME_ATTACK = "time_attack"
    TRAINING_RANGE = "training_range"
    STEALTH_OPS = "stealth_ops"


@dataclass
class ModeConfig:
    """Configuration for a game mode."""
    name: str
    mode_type: GameModeType
    description: str
    icon: str = ""  # for UI display
    max_players: int = 1
    allows_save: bool = True
    allows_progress: bool = True
    allows_weapons: bool = True
    allows_difficulty_selection: bool = True


@dataclass
class ModeStats:
    """Runtime statistics for a game mode session."""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    score: int = 0
    enemies_killed: int = 0
    damage_dealt: int = 0
    damage_taken: int = 0
    accuracy: float = 0.0
    objectives_completed: int = 0
    time_elapsed: float = 0.0
    waves_survived: int = 0
    boss_count: int = 0
    stealth_rating: float = 0.0  # 0-100
    completed: bool = False


class GameMode(ABC):
    """
    Abstract base class for all game modes.

    Subclasses implement the specific rules and win/lose conditions
    for their mode.
    """

    def __init__(self, game, config: ModeConfig):
        self.game = game
        self.config = config
        self.stats: ModeStats = ModeStats()
        self._is_active: bool = False
        self._is_complete: bool = False
        self._is_failed: bool = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_complete(self) -> bool:
        return self._is_complete

    @property
    def is_failed(self) -> bool:
        return self._is_failed

    def start(self, world_id: str, difficulty: int = 1):
        """Begin the mode with a given world and difficulty."""
        self._is_active = True
        self.stats.start_time = time.time()
        logger.info("Game mode '%s' started on world '%s' (difficulty %d).",
                     self.config.name, world_id, difficulty)
        self._on_start(world_id, difficulty)

    def stop(self):
        """End the mode."""
        self._is_active = False
        self.stats.end_time = time.time()
        self.stats.time_elapsed = self.stats.end_time - self.stats.start_time

    def update(self, dt: float):
        """Per-frame update."""
        if self._is_active:
            self._on_update(dt)
            self._check_win_conditions()

    def complete(self):
        """Mark the mode as completed (won)."""
        self._is_active = False
        self._is_complete = True
        self.stats.completed = True
        self.stop()
        logger.info("Game mode '%s' completed with score: %d", self.config.name, self.stats.score)
        self._on_complete()

    def fail(self):
        """Mark the mode as failed."""
        self._is_active = False
        self._is_failed = True
        self.stop()
        logger.info("Game mode '%s' failed.", self.config.name)
        self._on_fail()

    @abstractmethod
    def _on_start(self, world_id: str, difficulty: int):
        """Called when the mode starts."""
        pass

    @abstractmethod
    def _on_update(self, dt: float):
        """Called each frame while the mode is active."""
        pass

    @abstractmethod
    def _on_complete(self):
        """Called when the mode is completed."""
        pass

    @abstractmethod
    def _on_fail(self):
        """Called when the mode fails."""
        pass

    def _check_win_conditions(self):
        """Check if win conditions are met."""
        pass

    def _check_lose_conditions(self):
        """Check if lose conditions are met."""
        pass

    # ------------------------------------------------------------------
    #  Stat recording
    # ------------------------------------------------------------------

    def record_kill(self, enemy_type: str = "unknown"):
        self.stats.enemies_killed += 1

    def record_damage_dealt(self, amount: int):
        self.stats.damage_dealt += amount

    def record_damage_taken(self, amount: int):
        self.stats.damage_taken += amount

    def record_hit(self):
        pass  # handled by accuracy calculator

    def record_shot(self):
        pass


class CampaignMode(GameMode):
    """Story-driven mode: play through missions in order."""

    def _on_start(self, world_id: str, difficulty: int):
        # Start the first available mission for this world.
        if self.game and hasattr(self.game, 'mission_mgr'):
            missions = self.game.mission_mgr.get_available_missions(world_id)
            if missions:
                self.game.mission_mgr.start_mission(missions[0].mission_id)

    def _on_update(self, dt: float):
        pass

    def _on_complete(self):
        # Award bonus XP for campaign completion.
        if self.game and hasattr(self.game, 'progression'):
            bonus = 500 * self.game.difficulty
            self.game.progression.add_xp(bonus)

    def _on_fail(self):
        pass

    def _check_win_conditions(self):
        if self.game and hasattr(self.game, 'mission_mgr'):
            active = self.game.mission_mgr.active_mission
            if active and active.is_complete():
                # Move to next mission if available.
                self.game.mission_mgr.complete_mission()
                next_missions = self.game.mission_mgr.get_available_missions()
                if next_missions:
                    self.game.mission_mgr.start_mission(next_missions[0].mission_id)
                else:
                    self.complete()


class SurvivalMode(GameMode):
    """Endless waves of enemies."""

    def __init__(self, game, config: ModeConfig):
        super().__init__(game, config)
        self.current_wave: int = 0
        self.enemies_remaining: int = 0
        self._waves: list[dict] = self._generate_waves()

    def _generate_waves(self) -> list[dict]:
        """Generate wave configurations."""
        waves = []
        for wave_num in range(1, 21):
            waves.append({
                "enemies": max(3, wave_num * 2),
                "enemy_types": self._get_enemy_types_for_wave(wave_num),
                "health_multiplier": 1.0 + (wave_num - 1) * 0.15,
                "damage_multiplier": 1.0 + (wave_num - 1) * 0.1,
            })
        return waves

    def _get_enemy_types_for_wave(self, wave_num: int) -> list[str]:
        """Return enemy types for a given wave number."""
        types = ["StandardInfantry", "FastAssault"]
        if wave_num >= 3:
            types.append("HeavySoldier")
        if wave_num >= 5:
            types.append("Sniper")
        if wave_num >= 8:
            types.append("CombatDrone")
        if wave_num >= 12:
            types.append("EliteCommander")
        return types

    def _on_start(self, world_id: str, difficulty: int):
        self.current_wave = 1
        self._spawn_wave()

    def _on_update(self, dt: float):
        if self.enemies_remaining <= 0 and self._is_active:
            self._advance_wave()

    def _on_complete(self):
        pass

    def _on_fail(self):
        pass

    def _spawn_wave(self):
        """Spawn enemies for the current wave."""
        if self.current_wave > len(self._waves):
            self.complete()
            return

        wave = self._waves[self.current_wave - 1]
        self.enemies_remaining = wave["enemies"]
        self.stats.waves_survived = self.current_wave - 1

        logger.info("Survival wave %d: %d enemies.", self.current_wave, self.enemies_remaining)

        # Spawn enemies (would use enemy manager in full implementation).
        if self.game and hasattr(self.game, 'ai_mgr'):
            for i in range(wave["enemies"]):
                enemy_type = wave["enemy_types"][i % len(wave["enemy_types"])]
                self.game.ai_mgr.spawn_enemy(enemy_type)

    def _advance_wave(self):
        """Advance to the next wave."""
        self.current_wave += 1
        self.stats.waves_survived = self.current_wave - 1

        # Calculate score for completing this wave.
        wave = self._waves[min(self.current_wave - 2, len(self._waves) - 1)]
        self.stats.score += 100 * self.current_wave * wave.get("health_multiplier", 1.0)

        if self.current_wave > len(self._waves):
            # Player survived all waves -- ultimate victory.
            self.complete()
        else:
            self._spawn_wave()

    def record_kill(self, enemy_type: str = "unknown"):
        super().record_kill(enemy_type)
        self.enemies_remaining -= 1
        self.stats.score += 50
        if self.game and hasattr(self.game, 'progression'):
            self.game.progression.add_xp(25)

    def _check_win_conditions(self):
        if self.current_wave > len(self._waves) and self._is_active:
            self.complete()


class BossRushMode(GameMode):
    """Fight all bosses in sequence."""

    def __init__(self, game, config: ModeConfig):
        super().__init__(game, config)
        self._bosses: list[str] = [
            "CyberneticOverlord",
            "WarBeard",
            "SecurityCore",
            "Guardians",
            "Xenomorph",
            "NightmareLord",
        ]
        self._current_boss_index: int = 0
        self._boss_spawned: bool = False

    def _on_start(self, world_id: str, difficulty: int):
        self._current_boss_index = 0
        self._boss_spawned = False

    def _on_update(self, dt: float):
        if not self._boss_spawned and self._is_active:
            self._spawn_boss()
            self._boss_spawned = True

    def _on_complete(self):
        if self.game and hasattr(self.game, 'progression'):
            self.game.progression.add_xp(1000)

    def _on_fail(self):
        pass

    def _spawn_boss(self):
        """Spawn the current boss."""
        if self._current_boss_index < len(self._bosses):
            boss_name = self._bosses[self._current_boss_index]
            logger.info("Spawning boss: %s", boss_name)
            if self.game and hasattr(self.game, 'ai_mgr'):
                self.game.ai_mgr.spawn_boss(boss_name)
            self.stats.boss_count = self._current_boss_index + 1

    def record_kill(self, enemy_type: str = "unknown"):
        super().record_kill(enemy_type)
        self.stats.score += 500

        # Check if we killed a boss.
        if self._current_boss_index < len(self._bosses):
            boss_name = self._bosses[self._current_boss_index]
            if enemy_type == boss_name or enemy_type == "boss":
                self._current_boss_index += 1
                if self._current_boss_index >= len(self._bosses):
                    self.complete()
                else:
                    self._boss_spawned = False  # spawn next boss


class TimeAttackMode(GameMode):
    """Race against the clock to complete objectives."""

    def __init__(self, game, config: ModeConfig):
        super().__init__(game, config)
        self._time_limit: float = 180.0  # 3 minutes default
        self._start_time: float = 0.0
        self._objectives_total: int = 5
        self._objectives_done: int = 0

    def _on_start(self, world_id: str, difficulty: int):
        self._time_limit = 120.0 + difficulty * 60.0
        self._start_time = time.time()

    def _on_update(self, dt: float):
        elapsed = time.time() - self._start_time
        remaining = self._time_limit - elapsed
        self.stats.time_elapsed = elapsed

        if remaining <= 0:
            self.fail()

    def _on_complete(self):
        # Bonus for finishing early.
        time_bonus = int(max(0, self._time_limit - self.stats.time_elapsed) * 10)
        self.stats.score += time_bonus

    def _on_fail(self):
        pass

    def record_objective_complete(self):
        self._objectives_done += 1
        self.stats.score += 200

        if self._objectives_done >= self._objectives_total:
            self.complete()

    def _check_win_conditions(self):
        if self._objectives_done >= self._objectives_total:
            self.complete()
        elif time.time() - self._start_time > self._time_limit:
            self.fail()


class TrainingRangeMode(GameMode):
    """Practice mode with unlimited ammo and no enemies."""

    def __init__(self, game, config: ModeConfig):
        super().__init__(game, config)
        self._shots_fired: int = 0
        self._shots_hit: int = 0
        self._damage_done: int = 0

    def _on_start(self, world_id: str, difficulty: int):
        # Enable infinite ammo.
        if self.game and hasattr(self.game, 'weapon_mgr'):
            self.game.weapon_mgr.set_infinite_ammo(True)

    def _on_update(self, dt: float):
        # Update accuracy calculation.
        if self._shots_fired > 0:
            self.stats.accuracy = (self._shots_hit / self._shots_fired) * 100

    def _on_complete(self):
        pass

    def _on_fail(self):
        pass

    def record_damage_dealt(self, amount: int):
        super().record_damage_dealt(amount)
        self._damage_done += amount
        self.stats.score += amount

    def set_shots(self, fired: int, hit: int):
        """Update shot statistics for accuracy calculation."""
        self._shots_fired = fired
        self._shots_hit = hit
        if fired > 0:
            self.stats.accuracy = (hit / fired) * 100

    def get_accuracy(self) -> float:
        if self._shots_fired > 0:
            return (self._shots_hit / self._shots_fired) * 100
        return 0.0


class StealthOpsMode(GameMode):
    """Stealth infiltration without being detected."""

    def __init__(self, game, config: ModeConfig):
        super().__init__(game, config)
        self._player_detected_count: int = 0
        self._max_detections: int = 3  # 3 detections = mission failed
        self._objectives_total: int = 4
        self._objectives_done: int = 0

    def _on_start(self, world_id: str, difficulty: int):
        self._max_detections = 5 - difficulty  # harder = fewer allowed detections
        self._player_detected_count = 0

    def _on_update(self, dt: float):
        if self._player_detected_count > self._max_detections:
            self.fail()

    def _on_complete(self):
        # Perfect stealth bonus.
        if self._player_detected_count == 0:
            self.stats.score += 1000
            if self.game and hasattr(self.game, 'stats'):
                self.game.stats.record_stealth_kill()

    def _on_fail(self):
        pass

    def record_detection(self):
        """Called when the player is spotted by an enemy."""
        self._player_detected_count += 1
        self.stats.score -= 50  # penalty for being detected

    def record_objective_complete(self):
        self._objectives_done += 1
        self.stats.score += 300

        if self._objectives_done >= self._objectives_total:
            self.complete()

    def _check_win_conditions(self):
        if self._objectives_done >= self._objectives_total:
            self.complete()


# ---------------------------------------------------------------------------
# Mode configurations
# ---------------------------------------------------------------------------

MODE_CONFIGS: dict[GameModeType, ModeConfig] = {
    GameModeType.CAMPAIGN: ModeConfig(
        name="Campaign",
        mode_type=GameModeType.CAMPAIGN,
        description="Experience the full story campaign across all worlds.",
        icon="🎯",
        max_players=1,
        allows_save=True,
        allows_progress=True,
        allows_weapons=True,
        allows_difficulty_selection=True,
    ),
    GameModeType.SURVIVAL: ModeConfig(
        name="Survival",
        mode_type=GameModeType.SURVIVAL,
        description="Survive endless waves of increasingly difficult enemies.",
        icon="🌊",
        max_players=1,
        allows_save=False,
        allows_progress=True,
        allows_weapons=True,
        allows_difficulty_selection=True,
    ),
    GameModeType.BOSS_RUSH: ModeConfig(
        name="Boss Rush",
        mode_type=GameModeType.BOSS_RUSH,
        description="Face all bosses in sequence without pause.",
        icon="👑",
        max_players=1,
        allows_save=False,
        allows_progress=True,
        allows_weapons=True,
        allows_difficulty_selection=True,
    ),
    GameModeType.TIME_ATTACK: ModeConfig(
        name="Time Attack",
        mode_type=GameModeType.TIME_ATTACK,
        description="Complete objectives as fast as possible against the clock.",
        icon="⏱️",
        max_players=1,
        allows_save=False,
        allows_progress=True,
        allows_weapons=True,
        allows_difficulty_selection=True,
    ),
    GameModeType.TRAINING_RANGE: ModeConfig(
        name="Training Range",
        mode_type=GameModeType.TRAINING_RANGE,
        description="Practice your aim with unlimited ammo and no enemies.",
        icon="🎯",
        max_players=1,
        allows_save=False,
        allows_progress=False,
        allows_weapons=True,
        allows_difficulty_selection=False,
    ),
    GameModeType.STEALTH_OPS: ModeConfig(
        name="Stealth Ops",
        mode_type=GameModeType.STEALTH_OPS,
        description="Infiltrate enemy territories without being detected.",
        icon="👤",
        max_players=1,
        allows_save=False,
        allows_progress=True,
        allows_weapons=True,
        allows_difficulty_selection=True,
    ),
}


class ModeManager:
    """
    Central manager for game modes.

    Handles mode selection, instantiation, and lifecycle.
    """

    def __init__(self, game):
        self.game = game
        self._current_mode: Optional[GameMode] = None
        self._configs: dict[GameModeType, ModeConfig] = dict(MODE_CONFIGS)
        self._mode_classes: dict[GameModeType, type[GameMode]] = {
            GameModeType.CAMPAIGN: CampaignMode,
            GameModeType.SURVIVAL: SurvivalMode,
            GameModeType.BOSS_RUSH: BossRushMode,
            GameModeType.TIME_ATTACK: TimeAttackMode,
            GameModeType.TRAINING_RANGE: TrainingRangeMode,
            GameModeType.STEALTH_OPS: StealthOpsMode,
        }

    @property
    def current_mode(self) -> Optional[GameMode]:
        return self._current_mode

    def get_available_modes(self) -> list[ModeConfig]:
        """Return all available mode configurations."""
        return list(self._configs.values())

    def get_mode_config(self, mode_type: GameModeType) -> Optional[ModeConfig]:
        return self._configs.get(mode_type)

    def start_mode(self, mode_type: GameModeType, world_id: str, difficulty: int = 1):
        """Start a game mode."""
        mode_cls = self._mode_classes.get(mode_type)
        config = self._configs.get(mode_type)

        if mode_cls and config:
            self._current_mode = mode_cls(self.game, config)
            self._current_mode.start(world_id, difficulty)
            return self._current_mode

        logger.error("Cannot start mode: %s not found.", mode_type)
        return None

    def stop_mode(self):
        """Stop the current mode if active."""
        if self._current_mode:
            self._current_mode.stop()
        self._current_mode = None

    def update(self, dt: float):
        """Per-frame update for the current mode."""
        if self._current_mode and self._current_mode.is_active:
            self._current_mode.update(dt)

    def is_mode_active(self) -> bool:
        return self._current_mode is not None and self._current_mode.is_active

    def record_kill(self, enemy_type: str = "unknown"):
        if self._current_mode:
            self._current_mode.record_kill(enemy_type)

    def record_damage_dealt(self, amount: int):
        if self._current_mode:
            self._current_mode.record_damage_dealt(amount)

    def record_damage_taken(self, amount: int):
        if self._current_mode:
            self._current_mode.record_damage_taken(amount)

    def record_detection(self):
        if self._current_mode:
            self._current_mode.record_detection()


__all__ = [
    "GameModeType",
    "ModeConfig",
    "ModeStats",
    "GameMode",
    "CampaignMode",
    "SurvivalMode",
    "BossRushMode",
    "TimeAttackMode",
    "TrainingRangeMode",
    "StealthOpsMode",
    "MODE_CONFIGS",
    "ModeManager",
]
