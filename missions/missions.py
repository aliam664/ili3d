"""
missions.py

Mission system: defines Mission and MissionObjective dataclasses,
mission data, and the MissionManager that tracks active/completed missions.

A Mission is tied to a specific World and contains a set of objectives.
Objectives can be of various types: ELIMINATE_ENEMIES, REACH_POSITION,
COLLECT_ITEM, SURVIVE_TIME, DEFEND_POSITION, EXTRACT.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from panda3d.core import Vec3

logger = logging.getLogger(__name__)


class ObjectiveType(Enum):
    """Types of mission objectives."""
    ELIMINATE_ENEMIES = "eliminate_enemies"
    REACH_POSITION = "reach_position"
    COLLECT_ITEM = "collect_item"
    SURVIVE_TIME = "survive_time"
    DEFEND_POSITION = "defend_position"
    EXTRACT = "extract"
    HACK_TERMINAL = "hack_terminal"
    DESTROY_OBJECT = "destroy_object"


class MissionStatus(Enum):
    """Status of a mission."""
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MissionObjective:
    """
    A single objective within a mission.

    Attributes:
        description: Human-readable objective text.
        obj_type: What kind of objective this is.
        target_value: Numeric target (e.g. number of enemies to kill).
        current_value: Current progress toward the target.
        position: For position-based objectives, the target location.
        world_id: Which world this objective is on (for multi-world missions).
        completed: Whether this objective has been completed.
    """
    description: str
    obj_type: ObjectiveType
    target_value: int = 1
    current_value: int = 0
    position: Optional[tuple[float, float, float]] = None
    world_id: Optional[str] = None
    completed: bool = False

    def is_complete(self) -> bool:
        """Check if this objective is complete."""
        if self.obj_type in (ObjectiveType.REACH_POSITION,
                             ObjectiveType.DEFEND_POSITION,
                             ObjectiveType.EXTRACT,
                             ObjectiveType.HACK_TERMINAL):
            return self.completed
        return self.current_value >= self.target_value

    def update_progress(self, value: int = 1, position: Optional[tuple[float, float, float]] = None):
        """Update progress on this objective."""
        self.current_value += value
        if position is not None and self.position is not None:
            # Check if we reached the position.
            pos = Vec3(*position)
            target = Vec3(*self.position)
            dist_sq = (pos - target).lengthSquared()
            if dist_sq < 4.0:  # within 2 units
                self.completed = True
        elif self.is_complete():
            self.completed = True

    def to_dict(self) -> dict:
        """Serialize for saving."""
        return {
            "description": self.description,
            "obj_type": self.obj_type.value,
            "target_value": self.target_value,
            "current_value": self.current_value,
            "position": list(self.position) if self.position else None,
            "world_id": self.world_id,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MissionObjective":
        """Deserialize from saved data."""
        obj_type = ObjectiveType(data["obj_type"])
        return cls(
            description=data["description"],
            obj_type=obj_type,
            target_value=data.get("target_value", 1),
            current_value=data.get("current_value", 0),
            position=tuple(data["position"]) if data.get("position") else None,
            world_id=data.get("world_id"),
            completed=data.get("completed", False),
        )


@dataclass
class Mission:
    """
    A complete mission with objectives and rewards.

    Attributes:
        mission_id: Unique identifier.
        title: Display name.
        description: Mission briefing.
        world_id: Which world this mission takes place on.
        difficulty: Recommended difficulty (1-5).
        objectives: List of objectives to complete.
        xp_reward: XP awarded on completion.
        credits_reward: Credits awarded on completion.
        unlock_reward: IDs of weapons/items unlocked.
        status: Current mission status.
        story_text: Optional story narrative.
    """
    mission_id: str
    title: str
    description: str
    world_id: str
    difficulty: int = 1
    objectives: list = field(default_factory=list)
    xp_reward: int = 100
    credits_reward: int = 50
    unlock_reward: list = field(default_factory=list)
    status: MissionStatus = MissionStatus.AVAILABLE
    story_text: str = ""

    def is_complete(self) -> bool:
        """Check if all objectives are complete."""
        return all(obj.is_complete() for obj in self.objectives)

    def is_active(self) -> bool:
        return self.status == MissionStatus.ACTIVE

    def start(self):
        """Mark mission as active."""
        if self.status == MissionStatus.AVAILABLE:
            self.status = MissionStatus.ACTIVE
            logger.info("Mission '%s' started.", self.title)

    def complete(self):
        """Mark mission as completed."""
        self.status = MissionStatus.COMPLETED
        logger.info("Mission '%s' completed!", self.title)

    def fail(self):
        """Mark mission as failed."""
        self.status = MissionStatus.FAILED
        logger.info("Mission '%s' failed.", self.title)

    def update_objective(self, value: int = 1, position=None):
        """Update progress on all relevant objectives."""
        for obj in self.objectives:
            obj.update_progress(value, position)

    def to_dict(self) -> dict:
        """Serialize for saving."""
        return {
            "mission_id": self.mission_id,
            "status": self.status.value,
            "objectives": [obj.to_dict() for obj in self.objectives],
        }

    @classmethod
    def from_dict(cls, data: dict, templates: dict[str, "Mission"]) -> "Mission":
        """Reconstruct from saved data using templates."""
        mission_id = data["mission_id"]
        template = templates.get(mission_id)
        if template is None:
            logger.warning("Mission template '%s' not found for load.", mission_id)
            return None

        mission = template.__class__(
            mission_id=template.mission_id,
            title=template.title,
            description=template.description,
            world_id=template.world_id,
            difficulty=template.difficulty,
            objectives=[MissionObjective.from_dict(od) for od in data.get("objectives", [])],
            xp_reward=template.xp_reward,
            credits_reward=template.credits_reward,
            unlock_reward=template.unlock_reward,
            story_text=template.story_text,
        )
        mission.status = MissionStatus(data.get("status", "available"))
        return mission


# ---------------------------------------------------------------------------
# Mission templates
# ---------------------------------------------------------------------------

MISSION_TEMPLATES: dict[str, Mission] = {
    # Cyberpunk City Missions
    "cp_01": Mission(
        mission_id="cp_01",
        title="Corporate Uprising",
        description="A rebellion has erupted in the corporate district. Eliminate the resistance leaders.",
        world_id="cyberpunk_city",
        difficulty=1,
        objectives=[
            MissionObjective("Eliminate 10 resistance fighters", ObjectiveType.ELIMINATE_ENEMIES, target_value=10),
            MissionObjective("Reach the extraction point", ObjectiveType.REACH_POSITION, position=(0, 0, 0)),
        ],
        xp_reward=150,
        credits_reward=75,
        story_text=(
            "The year is 2087. Neo-Sharifa Corp has ruled the city with an iron fist. "
            "Tonight, the resistance strikes. Your mission: neutralize their leadership "
            "and create an opening for civilian evacuation."
        ),
    ),

    "cp_02": Mission(
        mission_id="cp_02",
        title="Data Heist",
        description="Infiltrate the corporate tower and steal encrypted data files.",
        world_id="cyberpunk_city",
        difficulty=2,
        objectives=[
            MissionObjective("Hack the security terminal", ObjectiveType.HACK_TERMINAL),
            MissionObjective("Eliminate 5 security guards", ObjectiveType.ELIMINATE_ENEMIES, target_value=5),
            MissionObjective("Extract to the rooftop", ObjectiveType.EXTRACT),
        ],
        xp_reward=250,
        credits_reward=150,
        unlock_reward=["ar_smg_wasp"],
        story_text="Corporate secrets must be exposed. Infiltrate, acquire, and escape."
    ),

    "cp_03": Mission(
        mission_id="cp_03",
        title="Boss: Cybernetic Overlord",
        description="Confront the Cybernetic Overlord in its tower stronghold.",
        world_id="cyberpunk_city",
        difficulty=5,
        objectives=[
            MissionObjective("Survive the security gauntlet", ObjectiveType.SURVIVE_TIME, target_value=60),
            MissionObjective("Defeat the Cybernetic Overlord", ObjectiveType.ELIMINATE_ENEMIES, target_value=1),
        ],
        xp_reward=1000,
        credits_reward=500,
        unlock_reward=["ar_99_reaper"],
        story_text="The Overlord has merged with the city's AI core. End its reign."
    ),

    # Wasteland Missions
    "wl_01": Mission(
        mission_id="wl_01",
        title="Scavenger Hunt",
        description="Locate and collect 5 supply crates scattered across the wasteland.",
        world_id="wasteland",
        difficulty=2,
        objectives=[
            MissionObjective("Collect supply crates", ObjectiveType.COLLECT_ITEM, target_value=5),
            MissionObjective("Survive for 120 seconds", ObjectiveType.SURVIVE_TIME, target_value=120),
        ],
        xp_reward=200,
        credits_reward=100,
        story_text="The wastes are rich with pre-war technology. Find what others have lost."
    ),

    "wl_02": Mission(
        mission_id="wl_02",
        title="Bandit Camp Clearout",
        description="Eliminate all bandits in the outpost.",
        world_id="wasteland",
        difficulty=3,
        objectives=[
            MissionObjective("Eliminate 15 bandits", ObjectiveType.ELIMINATE_ENEMIES, target_value=15),
            MissionObjective("Destroy the bandit leader's armor cache", ObjectiveType.DESTROY_OBJECT),
        ],
        xp_reward=350,
        credits_reward=200,
        unlock_reward=["m87_pump"],
        story_text="Raiders have established a camp. Make them pay for their crimes."
    ),

    # Military Facility Missions
    "mil_01": Mission(
        mission_id="mil_01",
        title="Infiltration",
        description="Infiltrate the military facility and disable the defense systems.",
        world_id="military_facility",
        difficulty=3,
        objectives=[
            MissionObjective("Hack the facility's main terminal", ObjectiveType.HACK_TERMINAL),
            MissionObjective("Eliminate 8 guards", ObjectiveType.ELIMINATE_ENEMIES, target_value=8),
        ],
        xp_reward=300,
        credits_reward=150,
        story_text="A military base holds the key to stopping the Sharifi Initiative."
    ),

    "mil_02": Mission(
        mission_id="mil_02",
        title="Boss: Security Core",
        description="Shut down the facility's AI security core.",
        world_id="military_facility",
        difficulty=4,
        objectives=[
            MissionObjective("Reach the core chamber", ObjectiveType.REACH_POSITION),
            MissionObjective("Defeat the Security Core", ObjectiveType.ELIMINATE_ENEMIES, target_value=1),
        ],
        xp_reward=600,
        credits_reward=300,
        unlock_reward=["m5_thumper"],
        story_text="The AI has gone rogue. Terminate its processing core."
    ),

    # Jungle Missions
    "jun_01": Mission(
        mission_id="jun_01",
        title="Predator Hunt",
        description="Track and eliminate hostile creatures in the jungle ruins.",
        world_id="jungle",
        difficulty=3,
        objectives=[
            MissionObjective("Eliminate 12 jungle creatures", ObjectiveType.ELIMINATE_ENEMIES, target_value=12),
            MissionObjective("Locate the ancient temple", ObjectiveType.REACH_POSITION),
        ],
        xp_reward=350,
        credits_reward=175,
        story_text="Something ancient stirs in the canopy. Prove your worth as a hunter."
    ),

    # Arctic Missions
    "arc_01": Mission(
        mission_id="arc_01",
        title="Facility Recon",
        description="Conduct reconnaissance at the abandoned research station.",
        world_id="arctic",
        difficulty=2,
        objectives=[
            MissionObjective("Reach 3 observation points", ObjectiveType.REACH_POSITION, target_value=3),
            MissionObjective("Survive harsh conditions", ObjectiveType.SURVIVE_TIME, target_value=90),
        ],
        xp_reward=250,
        credits_reward=125,
        story_text="A research station went dark three days ago. Investigate and report."
    ),

    # Space Station Missions
    "spc_01": Mission(
        mission_id="spc_01",
        title="Zero-G Sabotage",
        description="Board the derelict space station and disable its weapons array.",
        world_id="space_station",
        difficulty=4,
        objectives=[
            MissionObjective("Disable 3 power nodes", ObjectiveType.HACK_TERMINAL, target_value=3),
            MissionObjective("Eliminate 6 security drones", ObjectiveType.ELIMINATE_ENEMIES, target_value=6),
        ],
        xp_reward=500,
        credits_reward=250,
        unlock_reward=["laser_rifle_solaris"],
        story_text="The station's weapons are locked on a civilian colony. Stop them."
    ),

    # Fantasy Missions
    "fan_01": Mission(
        mission_id="fan_01",
        title="The Awakening",
        description="Investigate the ancient temple and banish the Nightmare Lord.",
        world_id="fantasy",
        difficulty=5,
        objectives=[
            MissionObjective("Reach the temple altar", ObjectiveType.REACH_POSITION),
            MissionObjective("Defeat the Nightmare Lord", ObjectiveType.ELIMINATE_ENEMIES, target_value=1),
        ],
        xp_reward=800,
        credits_reward=400,
        unlock_reward=["plasma_rifle_nova"],
        story_text="Ancient magic stirs in the realm of Aethermoor. A great evil awakens."
    ),
}


class MissionManager:
    """
    Manages mission lifecycle: available, active, completed, failed.

    Parameters
    ----------
    game : Game
        Reference to the parent game instance.
    """

    def __init__(self, game):
        self.game = game
        self._templates: dict[str, Mission] = dict(MISSION_TEMPLATES)
        self._missions: dict[str, Mission] = {}
        self._active_mission: Optional[Mission] = None
        self._completed_mission_count: int = 0

        # Initialize missions from templates.
        for mission_id, template in self._templates.items():
            self._missions[mission_id] = Mission(
                mission_id=template.mission_id,
                title=template.title,
                description=template.description,
                world_id=template.world_id,
                difficulty=template.difficulty,
                objectives=[MissionObjective(
                    obj.description, obj.obj_type, obj.target_value,
                    position=obj.position, world_id=obj.world_id
                ) for obj in template.objectives],
                xp_reward=template.xp_reward,
                credits_reward=template.credits_reward,
                unlock_reward=template.unlock_reward,
                story_text=template.story_text,
            )

    @property
    def active_mission(self) -> Optional[Mission]:
        return self._active_mission

    @property
    def completed_count(self) -> int:
        return self._completed_mission_count

    def get_missions_by_world(self, world_id: str) -> list[Mission]:
        """Return all missions that take place in the given world."""
        return [m for m in self._missions.values() if m.world_id == world_id]

    def get_available_missions(self, world_id: str = None) -> list[Mission]:
        """Return available or completed missions (for display)."""
        result = []
        for m in self._missions.values():
            if world_id and m.world_id != world_id:
                continue
            if m.status in (MissionStatus.AVAILABLE, MissionStatus.COMPLETED):
                result.append(m)
        return result

    def start_mission(self, mission_id: str) -> bool:
        """Start a mission by ID."""
        mission = self._missions.get(mission_id)
        if mission is None:
            logger.warning("Mission '%s' not found.", mission_id)
            return False
        if mission.status != MissionStatus.AVAILABLE:
            logger.warning("Mission '%s' is not available (status: %s).",
                           mission_id, mission.status)
            return False
        mission.start()
        self._active_mission = mission
        return True

    def update_objective(self, obj_type_value: int = 1, position=None):
        """Update objectives of the active mission."""
        if self._active_mission:
            self._active_mission.update_objective(obj_type_value, position)
            if self._active_mission.is_complete():
                self.complete_mission()

    def complete_mission(self):
        """Complete the active mission."""
        if self._active_mission:
            self._active_mission.complete()
            self._completed_mission_count += 1

            # Award XP and credits.
            if self.game and hasattr(self.game, 'progression'):
                self.game.progression.add_xp(self._active_mission.xp_reward)
            if self.game and hasattr(self.game, 'stats'):
                self.game.stats.record_mission_completion()

            # Unlock rewards.
            for weapon_id in self._active_mission.unlock_reward:
                if self.game and hasattr(self.game, 'weapon_mgr'):
                    self.game.weapon_mgr.unlock_weapon(weapon_id)

            logger.info("Mission '%s' completed! Rewards: %d XP, %d credits.",
                        self._active_mission.title,
                        self._active_mission.xp_reward,
                        self._active_mission.credits_reward)

            self._active_mission = None

    def fail_mission(self):
        """Fail the active mission."""
        if self._active_mission:
            self._active_mission.fail()
            logger.info("Mission '%s' failed.", self._active_mission.title)
            self._active_mission = None

    def cancel_mission(self):
        """Cancel the active mission (goes back to available)."""
        if self._active_mission:
            self._active_mission.status = MissionStatus.AVAILABLE
            self._active_mission = None

    def save(self) -> dict:
        """Serialize all missions for saving."""
        return {
            mission_id: m.to_dict() for mission_id, m in self._missions.items()
        }

    def load(self, data: dict):
        """Load missions from saved data."""
        for mission_id, m_data in data.items():
            mission = Mission.from_dict(m_data, self._templates)
            if mission:
                self._missions[mission_id] = mission

        self._completed_mission_count = sum(
            1 for m in self._missions.values()
            if m.status == MissionStatus.COMPLETED
        )

    def update(self, dt: float):
        """Per-frame update for the mission system."""
        pass


__all__ = [
    "ObjectiveType",
    "MissionStatus",
    "MissionObjective",
    "Mission",
    "MissionManager",
    "MISSION_TEMPLATES",
]
