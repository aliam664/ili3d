"""
save_manager.py

Save/load system for the SHARIFA 3D FPS game.

This module provides:
- ``SaveManager`` — the central class that coordinates saving and loading
  of player progress, statistics, and settings.
- ``SaveSlotInfo`` — metadata describing a save file for UI display.
- ``PlayerSaveData`` — the complete serializable save structure.
- Automatic save corruption handling with backup/restore.
- Auto-save at checkpoints (via ``checkpoint()``).
- Platform-aware save path resolution (``~/.config/sharifa/`` on Linux,
  ``%APPDATA%\\Sharifa\\`` on Windows, etc.).

Two separate JSON files are used:
1. ``settings.json`` — user preferences (read/written by ``Settings``).
2. ``savegame_<slot>.json`` — game progress (player stats, progression,
   achievements, weapon mastery, mission data).

Integration
-----------
The game's main class (``core/game.py``) should create a ``SaveManager``
early in startup, call ``load_or_new()`` (or ``load()``), and then call
``checkpoint()`` at save points (level transitions, objective completions,
etc.).

Author: SHARIFA Game Development Team
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Guard against import errors so the module can be used even if
# submodules have issues.  The dataclass modules are imported so we
# can reference their types for serialization.
from systems.stats import PlayerStats
from systems.progression import (
    PlayerProgression,
    WeaponMasteryTracker,
    AchievementTracker,
    MissionRating,
)

logger = logging.getLogger(__name__)


# ===========================================================================
#  Save file constants
# ===========================================================================

#: Save-file format version — bumped when the save format changes.
SAVE_FILE_VERSION: str = "1.0"

#: Filename used for the default / quick-save slot.
DEFAULT_SAVE_SLOT: str = "quicksave"

#: Maximum number of backup copies to keep per save slot.
MAX_BACKUPS: int = 3


# ===========================================================================
#  Platform-aware path resolution
# ===========================================================================


def get_config_dir() -> Path:
    """
    Return the platform-appropriate configuration directory.

    - Linux:  ``~/.config/sharifa``
    - macOS:  ``~/Library/Application Support/Sharifa``
    - Windows: ``%APPDATA%\\Sharifa``

    The directory is created if it does not exist.
    """
    if sys.platform.startswith("linux"):
        base = Path.home() / ".config"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"

    config_dir = base / "sharifa"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_save_path(slot: str = DEFAULT_SAVE_SLOT) -> Path:
    """
    Return the full path to a specific save slot file.

    Parameters
    ----------
    slot : str
        Save slot name (e.g. "quicksave", "autosave", "slot1").

    Returns
    -------
    Path
        ``<config_dir>/savegame_<slot>.json``
    """
    safe_slot = slot.replace("/", "_").replace("\\", "_")
    return get_config_dir() / f"savegame_{safe_slot}.json"


def get_settings_path() -> Path:
    """Return the path to the settings JSON file."""
    return get_config_dir() / "settings.json"


# ===========================================================================
#  Save slot metadata
# ===========================================================================


@dataclass
class SaveSlotInfo:
    """
    Metadata describing a save file on disk.

    Not serialized itself — reconstructed by scanning the config directory
    for ``savegame_*.json`` files.  Used by the load-game UI.
    """

    slot_name: str
    file_path: Path
    exists: bool
    last_modified: Optional[datetime] = None
    save_version: str = ""
    player_level: int = 0
    player_name: str = "Unknown"
    current_mission: str = ""
    playtime_seconds: float = 0.0
    thumbnail_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """Lightweight serialization for UI / list views."""
        return {
            "slot_name": self.slot_name,
            "exists": self.exists,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "save_version": self.save_version,
            "player_level": self.player_level,
            "player_name": self.player_name,
            "current_mission": self.current_mission,
            "playtime_seconds": self.playtime_seconds,
        }


# ---------------------------------------------------------------------------
#  Player profile container (the actual save data)
# ---------------------------------------------------------------------------


@dataclass
class PlayerSaveData:
    """
    Complete serializable player save data.

    This is the top-level structure written to ``savegame_<slot>.json``.
    It aggregates ``PlayerStats``, ``PlayerProgression``,
    ``WeaponMasteryTracker``, ``AchievementTracker``, and session-level
    information (current mission, difficulty, playtime, timestamp).
    """

    # -- Identification --
    save_version: str = SAVE_FILE_VERSION
    player_name: str = "Player"
    created_at: str = ""  # ISO timestamp of first save
    last_saved_at: str = ""  # ISO timestamp of most recent save

    # -- Session / current game state ---
    current_difficulty: str = "normal"
    current_mission_id: str = ""
    campaign_progress: Dict[str, bool] = field(default_factory=dict)
    unlocked_weapons: List[str] = field(default_factory=list)
    unlocked_attachments: List[str] = field(default_factory=list)
    unlocked_cosmetics: List[str] = field(default_factory=list)
    unlocked_content: List[str] = field(default_factory=list)
    settings_preferences: Dict[str, Any] = field(default_factory=dict)

    # -- Core stats and progression --
    stats: PlayerStats = field(default_factory=PlayerStats)
    progression: PlayerProgression = field(default_factory=PlayerProgression)
    weapon_mastery: WeaponMasteryTracker = field(default_factory=WeaponMasteryTracker)
    achievements: AchievementTracker = field(default_factory=AchievementTracker)

    # -- Mission records --
    #: mission_id -> {time, score, medal, difficulty, completed, total_score, ...}
    completed_missions: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # -- Runtime session stats (not persisted across sessions) --
    session_playtime: float = 0.0  # seconds played in this session

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.last_saved_at:
            self.last_saved_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Full serialization to a JSON-compatible dictionary."""
        return {
            "save_version": self.save_version,
            "player_name": self.player_name,
            "created_at": self.created_at,
            "last_saved_at": self.last_saved_at,
            "current_difficulty": self.current_difficulty,
            "current_mission_id": self.current_mission_id,
            "campaign_progress": self.campaign_progress,
            "unlocked_weapons": self.unlocked_weapons,
            "unlocked_attachments": self.unlocked_attachments,
            "unlocked_cosmetics": self.unlocked_cosmetics,
            "unlocked_content": self.unlocked_content,
            "settings_preferences": self.settings_preferences,
            "stats": self.stats.to_dict(),
            "progression": self.progression.to_dict(),
            "weapon_mastery": self.weapon_mastery.to_dict(),
            "achievements": self.achievements.to_dict(),
            "completed_missions": self.completed_missions,
            "session_playtime": self.session_playtime,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerSaveData":
        """
        Deserialize from a dictionary.

        Missing or corrupted sub-sections fall back to empty defaults,
        so a partially corrupted save is still recoverable.
        """
        # -- Stats --
        stats_data = data.get("stats", {})
        stats = PlayerStats.from_dict(stats_data) if isinstance(stats_data, dict) else PlayerStats()

        # -- Progression --
        prog_data = data.get("progression", {})
        progression = PlayerProgression.from_dict(prog_data) if isinstance(prog_data, dict) else PlayerProgression()

        # -- Weapon Mastery --
        wm_data = data.get("weapon_mastery", {})
        weapon_mastery = WeaponMasteryTracker.from_dict(wm_data) if isinstance(wm_data, dict) else WeaponMasteryTracker()

        # -- Achievements --
        ach_data = data.get("achievements", {})
        achievements = AchievementTracker.from_dict(ach_data) if isinstance(ach_data, dict) else AchievementTracker()

        # -- Completed missions --
        completed = data.get("completed_missions", {})
        if not isinstance(completed, dict):
            completed = {}

        return cls(
            save_version=data.get("save_version", SAVE_FILE_VERSION),
            player_name=data.get("player_name", "Player"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_saved_at=data.get("last_saved_at", datetime.now().isoformat()),
            current_difficulty=data.get("current_difficulty", "normal"),
            current_mission_id=data.get("current_mission_id", ""),
            campaign_progress=dict(data.get("campaign_progress", {})),
            unlocked_weapons=list(data.get("unlocked_weapons", [])),
            unlocked_attachments=list(data.get("unlocked_attachments", [])),
            unlocked_cosmetics=list(data.get("unlocked_cosmetics", [])),
            unlocked_content=list(data.get("unlocked_content", [])),
            settings_preferences=dict(data.get("settings_preferences", {})),
            stats=stats,
            progression=progression,
            weapon_mastery=weapon_mastery,
            achievements=achievements,
            completed_missions=completed,
            session_playtime=data.get("session_playtime", 0.0),
        )


# ---------------------------------------------------------------------------
#  Main SaveManager
# ---------------------------------------------------------------------------


class SaveManager:
    """
    Central save/load coordinator.

    Parameters
    ----------
    slot : str
        Default save slot name (default: ``"quicksave"``).
    auto_save_interval : float
        Minimum seconds between automatic saves (default 60s).
    max_backups : int
        Number of backup copies per slot (default 3).

    Examples
    --------
    >>> sm = SaveManager()
    >>> data = sm.load_or_new(player_name="Hero")
    >>> data.stats.total_victories
    0
    >>> sm.checkpoint()  # auto-saves
    True
    """

    def __init__(
        self,
        slot: str = DEFAULT_SAVE_SLOT,
        auto_save_interval: float = 60.0,
        max_backups: int = MAX_BACKUPS,
    ) -> None:
        self.default_slot: str = slot
        self.auto_save_interval: float = auto_save_interval
        self.max_backups: int = max_backups

        #: The currently loaded save data (or None if not loaded).
        self._data: Optional[PlayerSaveData] = None

        #: Timestamp of the last auto-save (epoch seconds).
        self._last_auto_save: float = 0.0

    # ------------------------------------------------------------------ #
    #  Properties                                                        #
    # ------------------------------------------------------------------ -->

    @property
    def data(self) -> Optional[PlayerSaveData]:
        """Return the currently loaded save data, or None."""
        return self._data

    @property
    def config_dir(self) -> Path:
        """Return the config directory path."""
        return get_config_dir()

    # ------------------------------------------------------------------ #
    #  Saving                                                            #
    # ------------------------------------------------------------------ -->

    def save(self, slot: Optional[str] = None, create_backup: bool = True) -> bool:
        """
        Write the current save data to disk.

        Parameters
        ----------
        slot : str, optional
            Save slot name.  Uses the default slot if not provided.
        create_backup : bool
            Whether to create a backup copy before overwriting.

        Returns
        -------
        bool
            ``True`` if the save was written successfully.
        """
        if self._data is None:
            logger.error("Cannot save: no data loaded. Call load_or_new() first.")
            return False

        slot_name = slot or self.default_slot
        save_path = get_save_path(slot_name)

        # Update metadata.
        self._data.last_saved_at = datetime.now().isoformat()

        # Create backup before overwriting (if file exists).
        if create_backup and save_path.exists():
            self._create_backup(save_path, slot_name)

        try:
            # Write to a temp file first, then rename — atomic on most
            # filesystems for same-directory renames.
            tmp_path = save_path.with_suffix(".json.tmp")
            save_path.parent.mkdir(parents=True, exist_ok=True)

            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(self._data.to_dict(), fh, indent=2, sort_keys=True)

            # Atomic rename.
            tmp_path.replace(save_path)
            logger.info("Game saved to %s", save_path)
            return True

        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.error("Failed to save game to %s: %s", save_path, exc)
            return False

    def save_or_new(
        self,
        slot: Optional[str] = None,
        player_name: str = "Player",
        overwrite: bool = False,
    ) -> bool:
        """
        Save to disk, creating fresh data if no save is loaded.

        If ``overwrite`` is True and a save exists, it is replaced.
        If a save already exists and ``overwrite`` is False, this method
        returns False (the existing save is preserved).
        """
        slot_name = slot or self.default_slot
        save_path = get_save_path(slot_name)

        if save_path.exists() and not overwrite:
            logger.info("Save exists at %s; not overwriting. Use save() instead.", save_path)
            return False

        if self._data is None:
            self._data = PlayerSaveData(player_name=player_name)

        self._data.player_name = player_name
        return self.save(slot=slot_name, create_backup=False)

    def checkpoint(self, force: bool = False) -> bool:
        """
        Auto-save the current game state.

        Called by the game at checkpoints (level transitions, objective
        completions, etc.).  If ``force`` is True, the auto-save interval
        is ignored.

        Returns
        -------
        bool
            ``True`` if an auto-save was written.
        """
        now = time.time()
        if not force and (now - self._last_auto_save) < self.auto_save_interval:
            return False

        if self._data is None:
            logger.warning("Auto-save called but no data loaded.")
            return False

        # Update timestamp.
        self._data.last_saved_at = datetime.now().isoformat()

        # Save to the "autosave" slot.
        success = self.save(slot="autosave", create_backup=True)
        if success:
            self._last_auto_save = now
        return success

    # ------------------------------------------------------------------ #
    #  Loading                                                           #
    # ------------------------------------------------------------------ -->

    def load(self, slot: Optional[str] = None) -> Optional[PlayerSaveData]:
        """
        Load save data from disk into memory.

        Parameters
        ----------
        slot : str, optional
            Save slot name.  Uses the default slot if not provided.

        Returns
        -------
        Optional[PlayerSaveData]
            The loaded data, or ``None`` if loading failed.
        """
        slot_name = slot or self.default_slot
        save_path = get_save_path(slot_name)

        if not save_path.exists():
            logger.info("No save file at %s", save_path)
            return None

        try:
            with open(save_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)

            if not isinstance(raw, dict):
                logger.error("Save file %s is not a JSON object.", save_path)
                return self._try_load_backup(slot_name)

            self._data = PlayerSaveData.from_dict(raw)

            # Version check.
            if self._data.save_version != SAVE_FILE_VERSION:
                logger.warning(
                    "Save version mismatch: file=%s, current=%s. Attempting to load anyway.",
                    self._data.save_version, SAVE_FILE_VERSION,
                )

            logger.info("Game loaded from %s", save_path)
            return self._data

        except json.JSONDecodeError as exc:
            logger.error("Save file %s is corrupted (JSON): %s", save_path, exc)
            return self._try_load_backup(slot_name)

        except (OSError, KeyError, TypeError, ValueError) as exc:
            logger.error("Failed to load save from %s: %s", save_path, exc)
            return self._try_load_backup(slot_name)

    def load_or_new(
        self,
        slot: Optional[str] = None,
        player_name: str = "Player",
    ) -> PlayerSaveData:
        """
        Load from disk; if no save exists, create a fresh one.

        This is the typical entry point at game startup.
        """
        data = self.load(slot=slot)
        if data is None:
            self._data = PlayerSaveData(player_name=player_name)
            logger.info("No save found; starting fresh as '%s'.", player_name)
        return self._data

    def _try_load_backup(self, slot: str) -> Optional[PlayerSaveData]:
        """
        Attempt to load from the most recent backup of *slot*.

        Called when the primary save file is corrupted.
        """
        backups = self._list_backups(slot)
        if not backups:
            logger.error("No backups available for slot '%s'.", slot)
            return None

        backup_path = backups[-1]  # most recent
        logger.info("Attempting to restore from backup: %s", backup_path)

        try:
            with open(backup_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self._data = PlayerSaveData.from_dict(raw)
            logger.info("Restored from backup successfully.")

            # Try to restore the primary file from this backup.
            primary_path = get_save_path(slot)
            shutil.copy2(backup_path, primary_path)
            logger.info("Restored primary save from backup.")

            return self._data

        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Backup restore failed: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    #  Save slot listing                                                  #
    # ------------------------------------------------------------------ -->

    def list_save_slots(self) -> List[SaveSlotInfo]:
        """
        Scan the config directory for all save files and return metadata.

        Returns
        -------
        List[SaveSlotInfo]
            One entry per save file, sorted by last-modified descending.
        """
        config_dir = get_config_dir()
        slots: List[SaveSlotInfo] = []

        for save_file in config_dir.glob("savegame_*.json"):
            slot_name = save_file.stem.replace("savegame_", "")

            info = SaveSlotInfo(
                slot_name=slot_name,
                file_path=save_file,
                exists=True,
            )

            try:
                mtime = save_file.stat().st_mtime
                info.last_modified = datetime.fromtimestamp(mtime)

                # Try to read minimal metadata from the file header.
                with open(save_file, "r", encoding="utf-8") as fh:
                    partial = json.load(fh)
                    if isinstance(partial, dict):
                        info.save_version = partial.get("save_version", "")
                        info.player_name = partial.get("player_name", "Unknown")
                        info.current_mission = partial.get("current_mission_id", "")
                        stats = partial.get("stats", {})
                        if isinstance(stats, dict):
                            info.playtime_seconds = stats.get("total_playtime", 0.0)
                        else:
                            prog = partial.get("progression", {})
                            if isinstance(prog, dict):
                                info.player_level = prog.get("current_level", 0)

            except (OSError, json.JSONDecodeError, KeyError) as exc:
                logger.warning("Could not read save metadata from %s: %s", save_file, exc)
                info.exists = True
                info.last_modified = None

            slots.append(info)

        # Sort by last modified, most recent first.
        slots.sort(key=lambda s: s.last_modified or datetime.min, reverse=True)
        return slots

    def delete_save(self, slot: str) -> bool:
        """
        Delete a save file and all its backups.

        Returns
        -------
        bool
            ``True`` if the file was deleted (or didn't exist).
        """
        save_path = get_save_path(slot)
        try:
            if save_path.exists():
                save_path.unlink()
            # Delete backups.
            for backup in self._list_backups(slot):
                backup.unlink(missing_ok=True)
            logger.info("Deleted save slot '%s' and its backups.", slot)
            return True
        except OSError as exc:
            logger.error("Failed to delete save '%s': %s", slot, exc)
            return False

    # ------------------------------------------------------------------ #
    #  Settings persistence                                               #
    # ------------------------------------------------------------------ -->

    def save_settings(self, settings_data: Dict[str, Any]) -> bool:
        """
        Write user settings/preferences to the settings JSON file.

        Parameters
        ----------
        settings_data : Dict[str, Any]
            The settings dictionary to persist.

        Returns
        -------
        bool
        """
        settings_path = get_settings_path()
        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_path, "w", encoding="utf-8") as fh:
                json.dump(settings_data, fh, indent=2, sort_keys=True)
            logger.info("Settings saved to %s", settings_path)
            return True
        except (OSError, TypeError, ValueError) as exc:
            logger.error("Failed to save settings: %s", exc)
            return False

    def load_settings(self) -> Dict[str, Any]:
        """
        Load user settings from the settings JSON file.

        Returns
        -------
        Dict[str, Any]
            The loaded settings, or an empty dict if the file is
            missing or corrupted.
        """
        settings_path = get_settings_path()
        if not settings_path.exists():
            logger.info("No settings file at %s; returning defaults.", settings_path)
            return {}

        try:
            with open(settings_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                logger.warning("Settings file is not a dict; returning empty.")
                return {}
            logger.info("Settings loaded from %s", settings_path)
            return data
        except json.JSONDecodeError as exc:
            logger.warning("Settings file is corrupted (%s); returning defaults.", exc)
            return {}
        except OSError as exc:
            logger.warning("Could not read settings file (%s); returning defaults.", exc)
            return {}

    # ------------------------------------------------------------------ #
    #  Backup management                                                  #
    # ------------------------------------------------------------------ -->

    def _create_backup(self, save_path: Path, slot: str) -> None:
        """
        Copy the current save file to a numbered backup before overwriting.

        Backups are named ``savegame_<slot>.bak0``, ``savegame_<slot>.bak1``,
        etc., with the newest backup always at index 0.
        """
        backups = self._list_backups(slot)

        # If we already have the max number of backups, remove the oldest.
        if len(backups) >= self.max_backups:
            oldest = backups[-1]
            try:
                oldest.unlink(missing_ok=True)
            except OSError:
                pass

        # Shift existing backups: bak0 → bak1, bak1 → bak2, etc.
        for i in range(len(backups) - 1, -1, -1):
            old_path = Path(str(save_path) + f".bak{i}")
            new_path = Path(str(save_path) + f".bak{i + 1}")
            try:
                if old_path.exists():
                    old_path.rename(new_path)
            except OSError:
                pass

        # Copy current save to .bak0
        backup_path = Path(str(save_path) + ".bak0")
        try:
            shutil.copy2(save_path, backup_path)
            logger.debug("Backup created: %s", backup_path)
        except OSError as exc:
            logger.warning("Failed to create backup: %s", exc)

    def _list_backups(self, slot: str) -> List[Path]:
        """
        Return a list of backup file paths for *slot*, oldest first.

        Returns
        -------
        List[Path]
            Sorted list of backup paths (oldest → newest).
        """
        save_path = get_save_path(slot)
        base_str = str(save_path)
        backups: List[Path] = []
        i = 0
        while True:
            backup_path = Path(f"{base_str}.bak{i}")
            if backup_path.exists():
                backups.append(backup_path)
                i += 1
            else:
                break
        # Sort by modification time (oldest first).
        backups.sort(key=lambda p: p.stat().st_mtime)
        return backups

    # ------------------------------------------------------------------ #
    #  Convenience wrappers for common operations                         #
    # ------------------------------------------------------------------ -->

    def get_stats(self) -> Optional[PlayerStats]:
        """Return the ``PlayerStats`` from the loaded save data."""
        if self._data is None:
            return None
        return self._data.stats

    def get_progression(self) -> Optional[PlayerProgression]:
        """Return the ``PlayerProgression`` from the loaded save data."""
        if self._data is None:
            return None
        return self._data.progression

    def get_weapon_mastery(self) -> Optional[WeaponMasteryTracker]:
        """Return the ``WeaponMasteryTracker`` from the loaded save data."""
        if self._data is None:
            return None
        return self._data.weapon_mastery

    def get_achievement_tracker(self) -> Optional[AchievementTracker]:
        """Return the ``AchievementTracker`` from the loaded save data."""
        if self._data is None:
            return None
        return self._data.achievements

    def get_completed_mission(
        self, mission_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Return the stored record for a completed mission.

        The returned dict contains keys like ``time``, ``score``,
        ``medal``, ``difficulty``, ``completed``, and ``total_score``.

        Returns ``None`` if the mission has not been completed.
        """
        if self._data is None:
            return None
        return self._data.completed_missions.get(mission_id)

    def record_mission_completion(
        self,
        mission_id: str,
        difficulty: str,
        completion_time: float,
        score: int,
        rating: MissionRating,
    ) -> Dict[str, Any]:
        """
        Store a mission completion record and update relevant stats.

        Parameters
        ----------
        mission_id : str
            The mission's unique identifier.
        difficulty : str
            The difficulty the mission was played on.
        completion_time : float
            Time in seconds to complete the mission.
        score : int
            Score earned.
        rating : MissionRating
            The rating object (already populated with performance metrics).

        Returns
        -------
        Dict[str, Any]
            The stored mission record.
        """
        if self._data is None:
            logger.warning("Cannot record mission completion: no save loaded.")
            return {}

        medal = rating.get_medal()

        record: Dict[str, Any] = {
            "mission_id": mission_id,
            "difficulty": difficulty,
            "time": completion_time,
            "score": score,
            "medal": medal,
            "total_score": rating.calculate_total_score(),
            "accuracy": rating.accuracy,
            "deaths": rating.deaths,
            "enemies_killed": rating.enemies_killed,
            "objectives_completed": rating.objectives_completed,
            "damage_taken": rating.damage_taken,
            "completed": True,
            "timestamp": datetime.now().isoformat(),
        }

        self._data.completed_missions[mission_id] = record

        # Update stats via PlayerStats record_mission_completion method.
        is_victory = medal != "none"
        self._data.stats.record_mission_completion(
            mission_id=mission_id,
            difficulty=difficulty,
            victory=is_victory,
            completion_time=completion_time if is_victory else 0,
            score=score,
            enemies_killed=rating.enemies_killed,
        )

        # Mark campaign progress if this is a story mission.
        if mission_id not in self._data.campaign_progress:
            self._data.campaign_progress[mission_id] = is_victory

        return record

    def update_current_difficulty(self, difficulty: str) -> None:
        """Set the current difficulty in the save data."""
        if self._data is not None:
            self._data.current_difficulty = difficulty

    def sync_from_components(
        self,
        stats: Optional[PlayerStats] = None,
        progression: Optional[PlayerProgression] = None,
        weapon_mastery: Optional[WeaponMasteryTracker] = None,
        achievements: Optional[AchievementTracker] = None,
    ) -> None:
        """
        Replace the save data's component systems with new instances.

        This is useful when the game creates its own instances of
        ``PlayerStats``, ``PlayerProgression``, etc. and wants to
        sync them into the save data for persistence.
        """
        if self._data is None:
            self._data = PlayerSaveData()
        if stats is not None:
            self._data.stats = stats
        if progression is not None:
            self._data.progression = progression
        if weapon_mastery is not None:
            self._data.weapon_mastery = weapon_mastery
        if achievements is not None:
            self._data.achievements = achievements

    def get_player_level(self) -> int:
        """Return the player's current level from progression data."""
        if self._data is None:
            return 1
        return self._data.progression.current_level


__all__ = [
    # Core
    "SaveManager",
    "PlayerSaveData",
    "SaveSlotInfo",

    # Helpers
    "get_config_dir",
    "get_save_path",
    "get_settings_path",

    # Constants
    "SAVE_FILE_VERSION",
    "DEFAULT_SAVE_SLOT",
    "MAX_BACKUPS",
]
