"""
SHARIFA Game - Base Enemy AI System

This module implements the core Enemy class with a comprehensive AI system
including:
    - Finite state machine: PATROL, CHASE, ATTACK, FLEE, DEAD
    - Health/damage system with armor and ragdoll physics
    - Navigation with waypoint-based pathfinding
    - Vision cone detection (FOV, distance, line-of-sight)
    - Audio detection (gunfire, footsteps, explosions)
    - Dynamic cover system (find, seek, and use cover positions)
    - Animation state management (procedural, since no 3D models)
    - Squad coordination and tactical awareness
    - Suppressive fire, flanking, and reinforcement calls

The system is designed to integrate with:
    - config.constants.Constants (collision masks, physics params)
    - weapons.weapon.Weapon and WeaponData (for AI combat)
    - Panda3D's collision and task systems

Author: SHARIFA Game Development Team
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from panda3d.core import (
    BitMask32,
    CollisionNode,
    CollisionRay,
    CollisionSphere,
    CollisionTraverser,
    CollisionHandlerQueue,
    NodePath,
    Vec3,
    Vec4,
    Point3,
    Geom,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    GeomNode,
    Material,
    TransparencyAttrib,
    TextNode,
    ClockObject,
    Filename,
)

# globalClock is set by ShowBase after initialization.
globalClock = ClockObject.getGlobalClock()
from direct.task.Task import Task
from direct.showbase.DirectObject import DirectObject
from direct.actor.Actor import Actor

from config.constants import Constants

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class EnemyState(IntEnum):
    """
    Finite state machine states for enemy AI behavior.

    PATROL   - Moving between patrol waypoints on a predefined route.
    CHASE    - Pursuing the player after detecting them.
    ATTACK   - Engaged in combat, firing at the player.
    FLEE     - Retreating due to low health or overwhelming odds.
    DEAD     - Entity is dead and in ragdoll/free-fall state.
    """

    PATROL = 0
    CHASE = 1
    ATTACK = 2
    FLEE = 3
    DEAD = 4


class AlertLevel(IntEnum):
    """
    Alert levels representing how suspicious/confident the enemy is.

    SUSPICIOUS - Something unusual detected, investigating.
    ALERT      - Confirmed threat, actively searching.
    COMBAT     - Player located, engaged in battle.
    """

    SUSPICIOUS = 0
    ALERT = 1
    COMBAT = 2


class SoundType(Enum):
    """
    Types of audio events that can trigger AI detection.
    """

    FOOTSTEPS = "footsteps"
    GUNFIRE = "gunfire"
    EXPLOSION = "explosion"
    DEATH = "death"
    ALARM = "alarm"
    AMBIENT = "ambient"


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class EnemyData:
    """
    Static configuration for an enemy type.

    This dataclass holds all the tunable parameters that define how an
    enemy behaves and appears. Each enemy subclass should provide a
    class-level ENEMY_DATA instance.

    Attributes:
        name: Display name for this enemy type.
        health: Maximum health pool.
        armor: Damage reduction as a percentage (0.0 to 1.0).
        move_speed: Movement speed in world units per second.
        run_speed: Sprint/chase speed multiplier or absolute speed.
        turn_speed: Degrees per second for rotating toward targets.
        vision_angle: Horizontal field of view in degrees.
        vision_distance: Maximum detection distance for vision.
        hearing_distance: Base hearing radius (multiplied by sound type).
        accuracy: Base hit chance (0.0 to 1.0).
        damage: Base damage dealt per hit.
        fire_rate: Shots per second.
        attack_range: Optimal engagement distance.
        flee_threshold: Health percentage below which the enemy flees (0.0 to 1.0).
        color: RGBA color for the procedural model.
        size: (radius, height) of the enemy capsule.
        weapon_id: Identifier for the weapon this enemy uses.
    """

    name: str = "BasicEnemy"
    health: float = 100.0
    armor: float = 0.0
    move_speed: float = 5.0
    run_speed: float = 8.0
    turn_speed: float = 180.0

    vision_angle: float = 90.0
    vision_distance: float = 30.0
    hearing_distance: float = 25.0

    accuracy: float = 0.8
    damage: float = 25.0
    fire_rate: float = 1.0
    attack_range: float = 20.0

    flee_threshold: float = 0.25
    call_reinforcements: bool = True
    reinforcement_radius: float = 30.0

    color: Vec4 = field(default_factory=lambda: Vec4(0.8, 0.2, 0.2, 1.0))
    size: Tuple[float, float] = (0.4, 1.8)

    weapon_id: str = ""


@dataclass
class PatrolPoint:
    """
    A single waypoint in a patrol route.

    Attributes:
        position: World-space position of the waypoint.
        wait_time: Seconds to wait at this point before moving to the next.
        animation: Optional animation state to enter while waiting.
    """

    position: Vec3
    wait_time: float = 1.0
    animation: str = "idle"


@dataclass
class CoverPoint:
    """
    A position where an enemy can take cover.

    Attributes:
        position: World-space position of the cover point.
        normal: Direction the cover faces (away from the threat).
        width: Width of the cover object (for positioning).
        height: Height of the cover object.
        is_valid: Whether this cover point is currently usable.
    """

    position: Vec3
    normal: Vec3
    width: float = 2.0
    height: float = 2.0
    is_valid: bool = True


@dataclass
class SoundEvent:
    """
    An audio event that propagates through the world and can be detected by enemies.

    Attributes:
        position: World-space origin of the sound.
        sound_type: Category of sound (gunfire, footsteps, etc.).
        radius: Detection radius for this sound.
        timestamp: Time the sound occurred (for aging).
    """

    position: Point3
    sound_type: SoundType
    radius: float
    timestamp: float


@dataclass
class AlertEvent:
    """
    An alert signal shared between squad members.

    Attributes:
        position: World-space position of the alert.
        source_id: Entity ID of the enemy that raised the alert.
        alert_level: Severity of the alert.
        timestamp: When the alert was raised.
    """

    position: Point3
    source_id: int
    alert_level: AlertLevel
    timestamp: float


# ---------------------------------------------------------------------------
# Squad / Tactical Manager
# ---------------------------------------------------------------------------


class SquadManager:
    """
    Manages a group of enemies for coordinated tactics.

    Responsibilities:
        - Track all enemies in the squad.
        - Propagate alert events to nearby squad members.
        - Coordinate flanking maneuvers.
        - Track suppression targets.
        - Call for reinforcements.

    Attributes:
        enemies: List of Enemy instances in this squad.
        leader: The squad leader (first enemy to detect the player), if any.
    """

    def __init__(self, squad_id: int = 0):
        self.squad_id: int = squad_id
        self.enemies: List["Enemy"] = []
        self.leader: Optional["Enemy"] = None
        self._suppression_targets: Dict[int, Point3] = {}  # enemy_id -> player_pos
        self._alert_propagation_radius: float = 40.0

    def add_enemy(self, enemy: "Enemy") -> None:
        """Register an enemy as part of this squad."""
        if enemy not in self.enemies:
            self.enemies.append(enemy)
            enemy.squad = self

    def remove_enemy(self, enemy: "Enemy") -> None:
        """Remove an enemy from the squad (e.g., on death)."""
        if enemy in self.enemies:
            self.enemies.remove(enemy)
        if self.leader is enemy:
            self._promote_new_leader()

    def _promote_new_leader(self) -> None:
        """Promote the first living enemy to squad leader."""
        for e in self.enemies:
            if e.state != EnemyState.DEAD:
                self.leader = e
                return
        self.leader = None

    def broadcast_alert(
        self,
        source: "Enemy",
        position: Point3,
        alert_level: AlertLevel,
    ) -> None:
        """
        Broadcast an alert event to all squad members within range.
        """
        if not source.call_reinforcements:
            return

        event = AlertEvent(
            position=position,
            source_id=id(source),
            alert_level=alert_level,
            timestamp=ClockObject.get_global_clock().get_frame_time(),
        )

        for e in self.enemies:
            if e is source:
                continue
            if e.state == EnemyState.DEAD:
                continue

            dist = e.node.get_pos().distance(position)
            if dist <= self._alert_propagation_radius:
                e.receive_alert(event)

    def get_suppressed_targets(self) -> Dict[int, Point3]:
        """Return the current suppression targets for all squad members."""
        return dict(self._suppression_targets)

    def coordinate_flanking(
        self,
        flanker: "Enemy",
        player_pos: Point3,
    ) -> Optional[Vec3]:
        """
        Coordinate a flanking maneuver. Returns a flanking position if feasible.
        """
        other_enemies = [e for e in self.enemies if e is not flanker and e.state != EnemyState.DEAD]
        if not other_enemies:
            return None

        # The other enemies engage directly, while the flanker circles around
        leader_pos = self.leader.node.get_pos() if self.leader else player_pos

        # Compute a flanking position perpendicular to the line from leader to player
        to_player = player_pos - leader_pos
        to_player.normalize()

        # Perpendicular vector (rotate 90 degrees around Z)
        flank_dir = Vec3(-to_player.y, to_player.x, 0).normalized()

        flank_distance = random.uniform(8.0, 15.0)
        flank_side = random.choice([-1, 1])
        offset = flank_dir * (flank_distance * flank_side)

        flank_pos = player_pos + offset
        return flank_pos

    def get_alive_count(self) -> int:
        """Count living enemies in the squad."""
        return sum(1 for e in self.enemies if e.state != EnemyState.DEAD)


# ---------------------------------------------------------------------------
# Core Enemy Class
# ---------------------------------------------------------------------------


class Enemy(DirectObject):
    """
    Base enemy character with full AI state machine, detection, navigation,
    and combat capabilities.

    This class implements:
        - State machine: PATROL, CHASE, ATTACK, FLEE, DEAD
        - Vision cone and audio detection systems
        - Waypoint-based pathfinding navigation
        - Dynamic cover finding and usage
        - Procedural 3D model (capsule + direction indicator)
        - Health bar rendering
        - Weapon-based combat with aim prediction
        - Squad coordination via SquadManager
        - Audio event propagation to nearby enemies
        - Ragdoll physics on death (simplified)

    The class is designed to be subclassed by enemy_types.py and bosses.py
    to create specialized enemy variants with unique behavior parameters.

    Args:
        base: The Panda3D ShowBase instance.
        enemy_data: An EnemyData instance with this enemy's configuration.
        parent_node: NodePath to parent the enemy's geometry under.
        collision_traverser: CollisionTraverser for line-of-sight raycasts.
        world_node: Optional world root node for the scene.

    Attributes:
        state: Current EnemyState.
        alert_level: Current AlertLevel.
        health: Current health (float).
        max_health: Maximum health.
        position: Current world position.
        squad: The SquadManager this enemy belongs to, if any.
        player_ref: Reference to the player NodePath (set by EnemyManager).
    """

    _id_counter: int = 0

    def __init__(
        self,
        base: Any,
        enemy_data: EnemyData,
        parent_node: Optional[NodePath] = None,
        collision_traverser: Optional[CollisionTraverser] = None,
        world_node: Optional[NodePath] = None,
    ):
        if base is None:
            raise ValueError("base (ShowBase instance) cannot be None")

        DirectObject.__init__(self)

        self.base = base
        self.render = base.render
        self.cTrav = collision_traverser if collision_traverser is not None else base.cTrav
        self.world_node = world_node if world_node is not None else self.render
        self.parent_node = parent_node if parent_node is not None else self.render

        # --- Identity ---
        Enemy._id_counter += 1
        self.id: int = Enemy._id_counter
        self.enemy_data: EnemyData = enemy_data
        self.name: str = enemy_data.name

        # --- State machine ---
        self.state: EnemyState = EnemyState.PATROL
        self.alert_level: AlertLevel = AlertLevel.SUSPICIOUS
        self._state_enter_time: float = 0.0

        # --- Combat stats ---
        self.max_health: float = enemy_data.health
        self.health: float = enemy_data.health
        self.armor: float = enemy_data.armor
        self.current_damage: float = enemy_data.damage
        self.current_accuracy: float = enemy_data.accuracy
        self.attack_range: float = enemy_data.attack_range
        self.fire_rate: float = enemy_data.fire_rate

        # --- Movement ---
        self.move_speed: float = enemy_data.move_speed
        self.run_speed: float = enemy_data.run_speed
        self.turn_speed: float = math.radians(enemy_data.turn_speed)
        self.velocity: Vec3 = Vec3(0, 0, 0)
        self._target_position: Optional[Vec3] = None
        self._path: List[Vec3] = []
        self._path_index: int = 0
        self._nav_cooldown: float = 0.0

        # --- Detection ---
        self.vision_angle: float = math.radians(enemy_data.vision_angle * 0.5)
        self.vision_distance: float = enemy_data.vision_distance
        self.hearing_distance: float = enemy_data.hearing_distance
        self._last_seen_player_pos: Optional[Point3] = None
        self._last_seen_time: float = 0.0
        self._search_timer: float = 0.0
        self._search_duration: float = 5.0

        # --- Cover system ---
        self._current_cover: Optional[CoverPoint] = None
        self._cover_points: List[CoverPoint] = []
        self._cover_cooldown: float = 0.0

        # --- Patrol ---
        self._patrol_points: List[PatrolPoint] = []
        self._current_patrol_index: int = 0
        self._wait_timer: float = 0.0

        # --- Weapon / combat ---
        self.weapon_id: str = enemy_data.weapon_id
        self._weapon: Optional[Any] = None  # Weapon instance
        self._cooldown_timer: float = 0.0
        self._burst_remaining: int = 0
        self._is_ads: bool = False
        self._suppression_level: float = 0.0  # 0.0 to 1.0
        self._melee_range: float = 2.0
        self._melee_damage: float = 25.0
        self._grenade_cooldown: float = 0.0
        self._last_grenade_time: float = 0.0

        # --- Squad ---
        self.squad: Optional[SquadManager] = None
        self.call_reinforcements: bool = enemy_data.call_reinforcements
        self.reinforcement_radius: float = enemy_data.reinforcement_radius

        # --- References ---
        self.player_ref: Optional[NodePath] = None
        self.manager: Optional["EnemyManager"] = None

        # --- Audio events log ---
        self._audio_events: List[SoundEvent] = []

        # --- Visual representation ---
        self.node: NodePath = NodePath(f"enemy_{self.id}")
        self.node.reparent_to(self.parent_node)
        self.node.set_tag("enemy_id", str(self.id))

        # Collision setup
        self._collision_node: Optional[NodePath] = None
        self._setup_collisions()

        # Visual model
        self._visual_root: Optional[NodePath] = None
        self._body_node: Optional[NodePath] = None
        self._direction_indicator: Optional[NodePath] = None
        self._health_bar: Optional[NodePath] = None
        self._build_visual_model()

        # Ragdoll / death
        self._is_ragdoll: bool = False
        self._ragdoll_velocity: Vec3 = Vec3(0, 0, 0)

        # Register tasks
        self._register_tasks()

        logger.debug("Enemy '%s' (ID: %d) created.", self.name, self.id)

    # -----------------------------------------------------------------------
    # State Machine
    # -----------------------------------------------------------------------

    def _enter_state(self, new_state: EnemyState) -> None:
        """
        Transition to a new state, running enter/exit logic.

        Args:
            new_state: The state to transition into.
        """
        old_state = self.state

        if old_state == new_state:
            return

        # Exit logic for old state
        self._exit_state(old_state)

        # Enter logic for new state
        self._enter_state_logic(new_state)

        self.state = new_state
        self._state_enter_time = globalClock.getFrameTime()

        logger.debug("Enemy %d: %s -> %s", self.id, old_state.name, new_state.name)

    def _exit_state(self, old_state: EnemyState) -> None:
        """Run cleanup logic when leaving a state."""
        if old_state == EnemyState.CHASE:
            # Stop searching for player when leaving chase
            pass
        elif old_state == EnemyState.ATTACK:
            self._stop_firing()
        elif old_state == EnemyState.FLEE:
            self._stop_firing()

    def _enter_state_logic(self, new_state: EnemyState) -> None:
        """Run enter logic for a specific state."""
        if new_state == EnemyState.PATROL:
            self._start_patrol()
        elif new_state == EnemyState.CHASE:
            self.alert_level = AlertLevel.ALERT
            self._search_timer = 0.0
        elif new_state == EnemyState.ATTACK:
            self.alert_level = AlertLevel.COMBAT
            self._start_firing()
        elif new_state == EnemyState.FLEE:
            self.alert_level = AlertLevel.COMBAT
        elif new_state == EnemyState.DEAD:
            self._start_death_sequence()

    def _start_patrol(self) -> None:
        """Begin patrolling the configured waypoint route."""
        if not self._patrol_points:
            # No patrol points - just idle in place
            self._target_position = self.node.get_pos()
            return

        self._current_patrol_index = 0
        pp = self._patrol_points[0]
        self._target_position = pp.position
        self._wait_timer = pp.wait_time

    # -----------------------------------------------------------------------
    # Main AI Update
    # -----------------------------------------------------------------------

    def _ai_update(self, task: Task) -> Task:
        """
        Main AI tick, called every frame via the Panda3D task system.

        Args:
            task: The Panda3D Task object.

        Returns:
            Task.cont to continue updating.
        """
        dt = globalClock.getDt()
        clock = globalClock.getFrameTime()

        # Skip updates if dead
        if self.state == EnemyState.DEAD:
            self._update_ragdoll(dt)
            return Task.cont

        # Update state-specific logic
        self._update_state(dt, clock)

        # Update movement
        self._update_movement(dt)

        # Update animations (procedural)
        self._update_animation(dt)

        # Update health bar visibility
        self._update_health_bar()

        return Task.cont

    def _update_state(self, dt: float, clock: float) -> None:
        """
        Dispatch to state-specific update methods.

        Args:
            dt: Delta time in seconds.
            clock: Current frame time.
        """
        if self.state == EnemyState.PATROL:
            self._update_patrol(dt, clock)
        elif self.state == EnemyState.CHASE:
            self._update_chase(dt, clock)
        elif self.state == EnemyState.ATTACK:
            self._update_attack(dt, clock)
        elif self.state == EnemyState.FLEE:
            self._update_flee(dt, clock)

    def _update_patrol(self, dt: float, clock: float) -> None:
        """
        Patrol state: move between waypoints, detect the player,
        respond to audio events.
        """
        # Check if we should transition to combat
        player_pos = self._get_player_position()
        if player_pos is not None:
            # Check vision
            if self._check_vision(player_pos):
                if self.squad:
                    self.squad.broadcast_alert(self, player_pos, AlertLevel.COMBAT)
                self._enter_state(EnemyState.CHASE)
                return

            # Check audio events
            heard_sound = self._check_audio_events()
            if heard_sound is not None:
                if heard_sound.sound_type == SoundType.GUNFIRE:
                    self.alert_level = AlertLevel.ALERT
                    self._enter_state(EnemyState.CHASE)
                    # Investigate the sound location
                    self._last_seen_player_pos = heard_sound.position
                    self._target_position = heard_sound.position
                    return
                elif self.alert_level < AlertLevel.ALERT:
                    self._last_seen_player_pos = heard_sound.position
                    self._target_position = heard_sound.position

        # Move toward current target
        if self._target_position is not None:
            dist = self.node.get_pos().distance(self._target_position)
            if dist < 0.5:
                # Reached waypoint
                self._advance_patrol()
                self._wait_timer = self._patrol_points[self._current_patrol_index].wait_time

        if self._wait_timer > 0:
            self._wait_timer -= dt
            if self._wait_timer > 0:
                return  # Still waiting

        # Continue to next waypoint
        self._move_to_target(dt)

    def _advance_patrol(self) -> None:
        """Move to the next patrol point in the route."""
        if not self._patrol_points:
            return
        self._current_patrol_index = (self._current_patrol_index + 1) % len(self._patrol_points)
        pp = self._patrol_points[self._current_patrol_index]
        self._target_position = pp.position
        self._wait_timer = pp.wait_time

    def _update_chase(self, dt: float, clock: float) -> None:
        """
        Chase state: move toward the player (or last known position),
        attempt to engage if in range.
        """
        player_pos = self._get_player_position()

        # Update last known position
        if self._check_vision(player_pos) if player_pos else False:
            self._last_seen_player_pos = player_pos
            self._last_seen_time = clock
            self._search_timer = 0.0
        else:
            # Player not in sight - track how long we've been without visual
            time_since_seen = clock - self._last_seen_time
            self._search_timer += dt

            if self._search_timer > self._search_duration:
                # Lost track - return to patrol
                if self._patrol_points:
                    self._enter_state(EnemyState.PATROL)
                    return

        # Determine target position (player if visible, else last known)
        target = self._last_seen_player_pos if self._last_seen_player_pos else player_pos
        if target is None:
            return

        self._target_position = target

        # Check if we should enter attack state
        if self._can_attack(target):
            self._enter_state(EnemyState.ATTACK)
            return

        # Check if we should flee
        health_pct = self.health / self.max_health
        if health_pct < self.enemy_data.flee_threshold:
            if self.squad and self.squad.get_alive_count() <= 1:
                self._enter_state(EnemyState.FLEE)
                return

        # Navigate toward target
        self._move_to_target(dt)

        # Flanking coordination
        if self.squad and random.random() < 0.1:
            flank_pos = self.squad.coordinate_flanking(self, target)
            if flank_pos is not None:
                self._target_position = flank_pos

    def _update_attack(self, dt: float, clock: float) -> None:
        """
        Attack state: fire at the player while maintaining cover and awareness.
        """
        player_pos = self._get_player_position()

        if player_pos is None:
            return

        # Check if player is still visible
        can_see = self._check_vision(player_pos)

        if not can_see:
            # Player lost from sight
            self._search_timer += dt
            if self._search_timer > self._search_duration:
                if self._patrol_points:
                    self._enter_state(EnemyState.PATROL)
                else:
                    self._enter_state(EnemyState.CHASE)
                return
        else:
            self._last_seen_player_pos = player_pos
            self._last_seen_time = clock
            self._search_timer = 0.0

        # Update target
        self._target_position = player_pos

        # Check flee threshold
        health_pct = self.health / self.max_health
        if health_pct < self.enemy_data.flee_threshold:
            if self.squad and self.squad.get_alive_count() <= 1:
                self._enter_state(EnemyState.FLEE)
                return

        # Move to cover if available
        if self._cover_cooldown <= 0 and not self._current_cover:
            self._seek_cover(player_pos)

        # Fire at player
        self._aim_and_fire(player_pos)

        # Grenade throwing
        if self._grenade_cooldown <= 0:
            dist_to_player = self.node.get_pos().distance(player_pos)
            if 8.0 < dist_to_player < 20.0 and random.random() < 0.02:
                self._throw_grenade(player_pos)

        # Call for reinforcements when heavily damaged
        if self.call_reinforcements and health_pct < 0.4:
            self._call_for_reinforcements()

    def _update_flee(self, dt: float, clock: float) -> None:
        """
        Flee state: retreat to a safe position, avoid the player,
        and occasionally look back to fire.
        """
        player_pos = self._get_player_position()

        if player_pos is not None:
            # Move away from player
            direction = (self.node.get_pos() - player_pos).normalized()
            flee_distance = random.uniform(15.0, 25.0)
            self._target_position = self.node.get_pos() + direction * flee_distance

            # Occasionally fire while retreating
            if random.random() < 0.05:
                self._aim_and_fire(player_pos)
        else:
            # No player reference - just stand still and wait
            pass

        self._move_to_target(dt)

        # Check if we should stop fleeing
        health_pct = self.health / self.max_health
        if health_pct > self.enemy_data.flee_threshold + 0.2:
            self._enter_state(EnemyState.CHASE)

    # -----------------------------------------------------------------------
    # Detection System
    # -----------------------------------------------------------------------

    def _check_vision(self, target_pos: Point3) -> bool:
        """
        Check if the target position is within the enemy's vision cone.

        Performs:
            1. Distance check against vision_distance.
            2. Angle check against FOV.
            3. Raycast for line-of-sight (occlusion).

        Args:
            target_pos: World position to check.

        Returns:
            True if the target is visible, False otherwise.
        """
        my_pos = self.node.get_pos()
        to_target = target_pos - my_pos

        # Distance check
        distance = to_target.length()
        if distance > self.vision_distance:
            return False

        # Angle check (horizontal FOV)
        my_hpr = self.node.get_hpr()
        forward = Vec3(math.sin(math.radians(my_hpr.x)), math.cos(math.radians(my_hpr.x)), 0).normalized()

        to_target_normalized = to_target.normalized()

        # Calculate angle between forward and target direction
        dot = forward.dot(to_target_normalized)
        angle = math.acos(max(-1.0, min(1.0, dot)))

        if angle > self.vision_angle:
            return False

        # Line-of-sight raycast
        return self._raycast_los(my_pos, target_pos)

    def _raycast_los(self, start: Point3, end: Point3) -> bool:
        """
        Raycast from start to end to check for line-of-sight.

        Uses Panda3D's collision system with a raycast.

        Args:
            start: Ray origin.
            end: Ray target.

        Returns:
            True if the path is clear (no occlusion), False if blocked.
        """
        if self.cTrav is None:
            return True  # No collision traverser - assume clear

        direction = end - start
        distance = direction.length()
        if distance < 0.01:
            return True

        direction.normalize()

        # Create a ray
        ray = CollisionRay()
        ray.set_origin(start + Vec3(0, 0, 1.5))  # Aim from head height
        ray.set_direction(direction)

        # Create collision node
        ray_node = CollisionNode(f"los_ray_{self.id}")
        ray_node.add_solid(ray)
        # Only collide with geometry
        ray_node.set_from_collide_mask(Constants.MASK_GEOMETRY)
        ray_node.set_into_collide_mask(BitMask32.all_off())

        ray_np = self.render.attach_new_node(ray_node)

        # Use a handler queue to get results
        queue = CollisionHandlerQueue()
        self.cTrav.traverse(self.render)
        self.cTrav.traverse_node(ray_np, self.cTrav, queue)

        # Check results
        entries = queue.get_entries()
        ray_np.remove_node()

        if not entries:
            return True  # No obstacles - clear line of sight

        # Check if the closest hit is closer than our target
        closest = entries[0]
        hit_distance = closest.get_surface_point(self.render).distance(start)

        return hit_distance >= distance - 0.5  # Allow small tolerance

    def _check_audio_events(self) -> Optional[SoundEvent]:
        """
        Check for audio events within hearing range.

        Returns the most relevant SoundEvent if one was detected,
        or None if nothing was heard.
        """
        my_pos = self.node.get_pos()
        current_time = globalClock.getFrameTime()

        best_event: Optional[SoundEvent] = None
        best_score: float = 0.0

        # Audio events are propagated to enemies by the EnemyManager
        # or placed in the world by gunfire/explosion events
        for event in self._audio_events:
            # Age out old events
            age = current_time - event.timestamp
            if age > 10.0:
                continue

            dist = my_pos.distance(event.position)
            if dist > self.hearing_distance * self._get_sound_radius_multiplier(event.sound_type):
                continue

            # Score based on sound type and distance
            score = self._get_sound_importance(event.sound_type) / (1.0 + dist * 0.1)
            if score > best_score:
                best_score = score
                best_event = event

        return best_event

    def _get_sound_radius_multiplier(self, sound_type: SoundType) -> float:
        """Return a distance multiplier for different sound types."""
        multipliers = {
            SoundType.FOOTSTEPS: 0.8,
            SoundType.GUNFIRE: 3.0,
            SoundType.EXPLOSION: 5.0,
            SoundType.DEATH: 1.5,
            SoundType.ALARM: 4.0,
            SoundType.AMBIENT: 0.5,
        }
        return multipliers.get(sound_type, 1.0)

    def _get_sound_importance(self, sound_type: SoundType) -> float:
        """Return importance weight for a sound type (higher = more attention-grabbing)."""
        importance = {
            SoundType.FOOTSTEPS: 2.0,
            SoundType.GUNFIRE: 10.0,
            SoundType.EXPLOSION: 15.0,
            SoundType.DEATH: 5.0,
            SoundType.ALARM: 20.0,
            SoundType.AMBIENT: 0.5,
        }
        return importance.get(sound_type, 1.0)

    def receive_sound_event(self, event: SoundEvent) -> None:
        """Receive a propagated sound event from the EnemyManager."""
        self._audio_events.append(event)
        # Keep only recent events
        if len(self._audio_events) > 20:
            self._audio_events = self._audio_events[-10:]

    def receive_alert(self, event: AlertEvent) -> None:
        """Receive an alert broadcast from a squad mate."""
        if self.state == EnemyState.DEAD:
            return

        # Don't override combat state
        if self.state == EnemyState.ATTACK and event.alert_level == AlertLevel.SUSPICIOUS:
            return

        # Update alert level
        if event.alert_level.value > self.alert_level.value:
            self.alert_level = event.alert_level

        # Investigate the alert location
        self._last_seen_player_pos = event.position
        self._target_position = event.position
        self._search_timer = 0.0

        if self.state == EnemyState.PATROL:
            self._enter_state(EnemyState.CHASE)

    # -----------------------------------------------------------------------
    # Movement & Navigation
    # -----------------------------------------------------------------------

    def _update_movement(self, dt: float) -> None:
        """
        Update the enemy's position based on current target and state.

        Handles basic path following and physics (gravity).
        """
        if self._is_ragdoll:
            return

        if self._target_position is not None:
            self._move_to_target(dt)

    def _move_to_target(self, dt: float) -> None:
        """
        Move toward the current target position.

        If a path is set, follows the path.
        Otherwise, moves directly toward the target.
        """
        if self._path and self._path_index < len(self._path):
            # Follow path waypoints
            waypoint = self._path[self._path_index]
            self._move_toward_point(waypoint, dt)

            # Check if we reached the waypoint
            dist = self.node.get_pos().distance(waypoint)
            if dist < 0.5:
                self._path_index += 1
        elif self._target_position is not None:
            self._move_toward_point(self._target_position, dt)

    def _move_toward_point(self, target: Vec3, dt: float) -> None:
        """
        Move toward a single point, rotating to face it.

        Args:
            target: World position to move toward.
            dt: Delta time in seconds.
        """
        my_pos = self.node.get_pos()
        direction = target - my_pos
        distance = direction.length()

        if distance < 0.01:
            self.velocity = Vec3(0, 0, 0)
            return

        # Determine speed based on state
        if self.state == EnemyState.CHASE or self.state == EnemyState.ATTACK:
            speed = self.run_speed
        elif self.state == EnemyState.FLEE:
            speed = self.run_speed * 1.2
        else:
            speed = self.move_speed

        # Apply suppression penalty
        speed *= max(0.3, 1.0 - self._suppression_level * 0.5)

        direction.normalize()

        # Rotate toward target
        target_h = math.degrees(math.atan2(-direction.x, direction.y))
        current_h = self.node.get_h()
        # Smooth rotation
        angle_diff = (target_h - current_h) % 360
        if angle_diff > 180:
            angle_diff -= 360
        max_turn = math.degrees(self.turn_speed) * dt
        turn = max(-max_turn, min(max_turn, angle_diff))
        self.node.set_h(current_h + turn)

        # Move forward
        forward = Vec3(
            math.sin(math.radians(self.node.get_h())),
            math.cos(math.radians(self.node.get_h())),
            0,
        ).normalized()

        move_vec = forward * speed * dt
        if move_vec.length() > distance:
            move_vec = direction * distance  # Don't overshoot

        # Apply movement
        new_pos = my_pos + move_vec

        # Simple ground clamp (raycast down)
        self._clamp_to_ground(new_pos)

    def _clamp_to_ground(self, pos: Vec3) -> None:
        """Clamp the enemy to the ground below it using a raycast."""
        if self.cTrav is None:
            pos.z = 0.0
            self.node.set_pos(pos)
            return

        start = pos + Vec3(0, 0, 2.0)
        end = pos + Vec3(0, 0, -10.0)
        direction = end - start
        direction.normalize()

        ray = CollisionRay()
        ray.set_origin(start)
        ray.set_direction(direction)

        ray_node = CollisionNode(f"ground_ray_{self.id}")
        ray_node.add_solid(ray)
        ray_node.set_from_collide_mask(Constants.MASK_GEOMETRY)
        ray_node.set_into_collide_mask(BitMask32.all_off())

        ray_np = self.render.attach_new_node(ray_node)
        queue = CollisionHandlerQueue()
        self.cTrav.traverse(self.render)
        self.cTrav.traverse_node(ray_np, self.cTrav, queue)

        ray_np.remove_node()

        entries = queue.get_entries()
        if entries:
            closest = entries[0]
            ground_z = closest.get_surface_point(self.render).z
            pos.z = ground_z + self.enemy_data.size[1] * 0.5  # Half height above ground

        self.node.set_pos(pos)

    def set_patrol_route(self, points: List[PatrolPoint]) -> None:
        """Set the patrol route for this enemy."""
        self._patrol_points = list(points)
        if self._patrol_points:
            self._current_patrol_index = 0
            self._target_position = self._patrol_points[0].position

    def set_path(self, path: List[Vec3]) -> None:
        """Set a navigation path (list of waypoints)."""
        self._path = list(path)
        self._path_index = 0

    def stop_movement(self) -> None:
        """Stop all movement immediately."""
        self._target_position = self.node.get_pos()
        self.velocity = Vec3(0, 0, 0)

    # -----------------------------------------------------------------------
    # Combat System
    # -----------------------------------------------------------------------

    def _can_attack(self, target_pos: Point3) -> bool:
        """Check if the enemy is within attack range of the target."""
        dist = self.node.get_pos().distance(target_pos)
        return dist <= self.attack_range

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """
        Aim at the target with prediction and fire.

        Uses lead-prediction for moving targets.
        """
        # Apply suppression effect
        spread_multiplier = 1.0 + self._suppression_level * 2.0
        accuracy_penalty = random.uniform(-spread_multiplier, spread_multiplier) * 0.1

        effective_accuracy = max(0.1, self.current_accuracy + accuracy_penalty)

        # Aim prediction
        predicted_pos = self._predict_target_position(target_pos)

        # Fire weapon
        self._cooldown_timer -= globalClock.getDt()
        if self._cooldown_timer > 0:
            return

        shots_per_second = self.fire_rate
        if shots_per_second <= 0:
            return

        # Check accuracy
        if random.random() > effective_accuracy * (1.0 - predicted_pos.distance(self.node.get_pos()) / (self.attack_range * 1000)):
            # Missed (add randomness to shot direction)
            pass

        # Weapon firing (if we have a weapon, fire it)
        if self._weapon is not None and hasattr(self._weapon, 'fire'):
            self._weapon.fire()
        else:
            # Default damage application
            if self.manager and self.manager.player_ref:
                # Raycast to player
                self.manager.apply_damage_to_player(
                    self.current_damage,
                    self.node.get_pos(),
                    predicted_pos,
                )

        # Set cooldown
        self._cooldown_timer = 1.0 / shots_per_second

        # Apply recoil to aim
        self._apply_recoil()

    def _predict_target_position(self, target_pos: Point3) -> Point3:
        """
        Predict where the target will be based on its velocity.

        Args:
            target_pos: Current position of the target.

        Returns:
            Predicted future position.
        """
        # Use manager's player velocity if available
        if self.manager and self.manager.player_ref:
            player_vel = getattr(self.manager.player_ref, 'velocity', Vec3(0, 0, 0))
            if player_vel.length() > 0.1:
                time_to_impact = target_pos.distance(self.node.get_pos()) / 200.0  # Estimate bullet speed
                return target_pos + player_vel * time_to_impact
        return target_pos

    def _apply_recoil(self) -> None:
        """Apply visual recoil to the direction indicator."""
        if self._direction_indicator:
            kick = math.radians(2.0) * random.uniform(0.5, 1.5)
            current_p = self._direction_indicator.get_p()
            self._direction_indicator.set_p(current_p + kick * random.choice([-1, 1]))

    def _stop_firing(self) -> None:
        """Stop firing the current weapon."""
        if self._weapon and hasattr(self._weapon, 'stop_firing'):
            self._weapon.stop_firing()

    def _throw_grenade(self, target_pos: Point3) -> None:
        """Throw a grenade toward the target position."""
        self._grenade_cooldown = 5.0
        self._last_grenade_time = globalClock.getFrameTime()

        if self.manager and self.manager.player_ref:
            # Spawn an explosion grenade
            self.manager.spawn_explosive(
                self.node.get_pos(),
                target_pos,
                damage=50.0,
                radius=8.0,
            )

    def _call_for_reinforcements(self) -> None:
        """Call nearby enemies to reinforce this position."""
        if not self.manager:
            return
        if not self.call_reinforcements:
            return

        # Broadcast an alert to nearby enemies
        alert_pos = self.node.get_pos()
        for enemy in self.manager.enemies:
            if enemy is self or enemy.state == EnemyState.DEAD:
                continue
            dist = enemy.node.get_pos().distance(alert_pos)
            if dist <= self.reinforcement_radius and enemy.alert_level < AlertLevel.COMBAT:
                enemy.receive_alert(AlertEvent(
                    position=alert_pos,
                    source_id=self.id,
                    alert_level=AlertLevel.COMBAT,
                    timestamp=globalClock.getFrameTime(),
                ))

    # -----------------------------------------------------------------------
    # Cover System
    # -----------------------------------------------------------------------

    def _seek_cover(self, threat_pos: Point3) -> None:
        """
        Find and move to a nearby cover position.

        Args:
            threat_pos: Position of the threat to find cover from.
        """
        if self._cover_cooldown > 0:
            return
        self._cover_cooldown = 3.0  # Don't seek cover again for 3 seconds

        best_cover: Optional[CoverPoint] = None
        best_score: float = -1.0

        my_pos = self.node.get_pos()

        for cp in self._cover_points:
            if not cp.is_valid:
                continue

            dist = my_pos.distance(cp.position)
            if dist > 25.0:
                continue

            # Check if cover blocks line of sight to threat
            if not self._raycast_los(threat_pos, cp.position):
                continue

            # Score: closer to enemy, further from threat, good angle
            to_cover = cp.position - threat_pos
            angle = abs(to_cover.dot(cp.normal))

            score = dist * -1 + angle * 10 + (my_pos.distance(cp.position) * -0.5)

            if score > best_score:
                best_score = score
                best_cover = cp

        if best_cover is not None:
            self._current_cover = best_cover
            self._target_position = best_cover.position
        else:
            self._cover_cooldown = 1.0

    def register_cover_point(self, cover: CoverPoint) -> None:
        """Register a cover point in the enemy's local knowledge."""
        self._cover_points.append(cover)

    # -----------------------------------------------------------------------
    # Damage System
    # -----------------------------------------------------------------------

    def take_damage(self, damage: float, source: Vec3 = None) -> None:
        """
        Apply damage to the enemy, accounting for armor.

        Args:
            damage: Raw incoming damage.
            source: Optional world position of the damage source (for knockback).
        """
        if self.state == EnemyState.DEAD:
            return

        # Apply armor reduction
        effective_damage = damage * (1.0 - self.armor * 0.5)

        self.health -= effective_damage

        # Apply suppression
        self._suppression_level = min(1.0, self._suppression_level + (effective_damage / self.max_health) * 0.3)

        # Hit effect
        self._spawn_hit_effect()

        # Update health bar
        self._show_health_bar()

        if self.health <= 0:
            self._die(source)
        else:
            # React to damage
            self._react_to_damage(source)

        # Propagate alert to squad
        if self.squad and source is not None:
            self.squad.broadcast_alert(self, source, AlertLevel.COMBAT)

    def _react_to_damage(self, source: Vec3) -> None:
        """React to taking damage (enter combat, retaliate)."""
        if source is not None:
            self._last_seen_player_pos = source
            self._target_position = source

        # Suppress and alert
        if self.state == EnemyState.PATROL:
            self._enter_state(EnemyState.CHASE)

    def _die(self, source: Vec3 = None) -> None:
        """Handle death: change state, apply ragdoll, remove threats."""
        self._enter_state(EnemyState.DEAD)

        # Drop weapon
        if self._weapon:
            self._weapon = None

        # Notify manager
        if self.manager:
            self.manager.on_enemy_death(self, source)

        # Notify squad
        if self.squad:
            self.squad.remove_enemy(self)

    def _start_death_sequence(self) -> None:
        """Initialize ragdoll physics on death."""
        self._is_ragdoll = True
        if source is not None:
            pass  # source not available here, use stored value
        direction = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), 0.3).normalized()
        self._ragdoll_velocity = direction * random.uniform(5, 15)

        # Hide health bar
        self._hide_health_bar()

        # Play death sound
        self._play_sound("death")

    def _update_ragdoll(self, dt: float) -> None:
        """Update ragdoll physics (simplified gravity + sliding)."""
        # Apply gravity
        self._ragdoll_velocity.z -= Constants.GRAVITY * dt

        # Terminal velocity
        if self._ragdoll_velocity.z < -Constants.TERMINAL_VELOCITY:
            self._ragdoll_velocity.z = -Constants.TERMINAL_VELOCITY

        # Update position
        pos = self.node.get_pos() + self._ragdoll_velocity * dt
        self._ragdoll_velocity.x *= 0.98
        self._ragdoll_velocity.y *= 0.98
        self.node.set_pos(pos)

    def _get_player_position(self) -> Optional[Point3]:
        """Get the current player position, or None if not available."""
        if self.manager and self.manager.player_ref:
            return self.manager.player_ref.get_pos(self.render)
        return None

    # -----------------------------------------------------------------------
    # Visual Representation
    # -----------------------------------------------------------------------

    def _build_visual_model(self) -> None:
        """
        Build the procedural visual representation for this enemy.

        Since no 3D models are available, the enemy is represented as:
            - A colored capsule (cylinder + hemispheres) for the body.
            - A triangle/pyramid for the direction indicator (facing forward).
            - A health bar that appears when damaged or targeted.
        """
        radius, height = self.enemy_data.size
        color = self.enemy_data.color

        # Create visual root
        self._visual_root = self.node.attach_new_node("visual")

        # --- Body: Capsule representation ---
        # Cylinder for the torso
        from panda3d.core import Cylinder as P3DCylinder

        body_cyl = P3DCylinder(false, 1.0, 0.0, 1.0, 1.0, True)
        body_cyl_geom = body_cyl.get_geom(0)
        body_cyl_geom.set_scale(radius, radius, height)

        body_node = GeomNode("body")
        body_node.add_geom(body_cyl_geom)
        self._body_node = self._visual_root.attach_new_node(body_node)
        self._body_node.set_color(color)
        self._body_node.set_shader_auto()
        self._body_node.set_z(height * 0.5)

        # --- Direction indicator: Triangle ---
        self._direction_indicator = self.node.attach_new_node("direction")

        # Create a simple arrow/triangle
        tri_vdata = GeomVertexData("arrow", GeomVertexFormat.get_v3t2(), Geom.UH_static)
        tri_vertex = GeomVertexWriter(tri_vdata, "vertex")
        tri_texcoord = GeomVertexWriter(tri_vdata, "texcoord")

        # Triangle pointing forward (toward -Y)
        arrow_length = radius * 2.5
        arrow_height = height * 0.6
        tri_vertex.add_data3f(0, arrow_length * 0.3, arrow_height)
        tri_vertex.add_data3f(-radius * 1.2, arrow_length, arrow_height)
        tri_vertex.add_data3f(radius * 1.2, arrow_length, arrow_height)
        tri_texcoord.add_data2f(0.5, 0.5)
        tri_texcoord.add_data2f(0.0, 1.0)
        tri_texcoord.add_data2f(1.0, 1.0)

        # Nose cone
        tri_vertex.add_data3f(0, arrow_length * 1.1, arrow_height)
        tri_vertex.add_data3f(0, arrow_length, arrow_height + radius)
        tri_vertex.add_data3f(0, arrow_length, arrow_height - radius)
        tri_texcoord.add_data2f(0.5, 1.0)
        tri_texcoord.add_data2f(0.0, 0.5)
        tri_texcoord.add_data2f(1.0, 0.5)

        tri_prim = GeomTriangles(Geom.UH_static)
        tri_prim.add_vertices(0, 1, 2)
        tri_prim.add_vertices(3, 4, 5)
        tri_prim.close_primitive()

        arrow_geom = Geom(tri_vdata)
        arrow_geom.add_primitive(tri_prim)

        arrow_node = GeomNode("arrow")
        arrow_node.add_geom(arrow_geom)
        arrow_np = self._direction_indicator.attach_new_node(arrow_node)
        arrow_np.set_color(Vec4(1, 1, 0, 1))  # Yellow arrow
        arrow_np.set_shader_auto()

        # --- Collision capsule ---
        # Already set up in _setup_collisions

    def _setup_collisions(self) -> None:
        """Set up the collision sphere/capsule for this enemy."""
        radius, height = self.enemy_data.size

        # Use a sphere for simplicity (center at enemy position)
        cnode = CollisionNode(f"enemy_{self.id}_collider")
        csphere = CollisionSphere(0, 0, height * 0.5, radius)
        cnode.add_solid(csphere)
        cnode.set_from_collide_mask(Constants.MASK_ENEMY | Constants.MASK_GEOMETRY)
        cnode.set_into_collide_mask(Constants.MASK_ENEMY)

        self._collision_node = self.node.attach_new_node(cnode)
        self._collision_node.set_python_tag("enemy_ref", self)

    def _show_health_bar(self) -> None:
        """Show the health bar above the enemy."""
        if self.health >= self.max_health:
            self._hide_health_bar()
            return

        if self._health_bar is None:
            self._health_bar = self.render.attach_new_node(f"health_bar_{self.id}")
            self._health_bar.set_billboard_axis()
            self._health_bar.set_light_off()
            self._health_bar.set_shader_auto()

            # Background bar
            from panda3d.core import CardMaker
            bg_cm = CardMaker("health_bg")
            bg_cm.set_frame(-0.3, 0.3, -0.03, 0.03)
            bg = self._health_bar.attach_new_node(bg_cm.generate())
            bg.set_color(Vec4(0.2, 0.2, 0.2, 0.7))

            # Foreground bar
            fg_cm = CardMaker("health_fg")
            fg_cm.set_frame(-0.3, 0.3, -0.03, 0.03)
            self._health_fg = self._health_bar.attach_new_node(fg_cm.generate())
            self._health_fg.set_color(Vec4(0.8, 0.2, 0.2, 0.9))

        # Update bar width based on health
        health_pct = self.health / self.max_health
        self._health_fg.set_scale(health_pct, 1, 1)

        # Update position above enemy
        pos = self.node.get_pos(self.render)
        pos.z += self.enemy_data.size[1] + 0.3
        self._health_bar.set_pos(pos)

        # Color based on health
        if health_pct > 0.5:
            self._health_fg.set_color(Vec4(0.2, 0.8, 0.2, 0.9))
        elif health_pct > 0.25:
            self._health_fg.set_color(Vec4(0.8, 0.8, 0.2, 0.9))
        else:
            self._health_fg.set_color(Vec4(0.8, 0.2, 0.2, 0.9))

    def _hide_health_bar(self) -> None:
        """Hide the health bar."""
        if self._health_bar is not None:
            self._health_bar.hide()

    def _spawn_hit_effect(self) -> None:
        """Spawn a visual effect when the enemy is hit."""
        from panda3d.core import CardMaker

        effect = self.render.attach_new_node(f"hit_effect_{self.id}")
        effect.set_pos(self.node.get_pos())

        cm = CardMaker("hit_flash")
        cm.set_frame(-0.2, 0.2, -0.2, 0.2)
        card = effect.attach_new_node(cm.generate())
        card.set_color(Vec4(1, 0.3, 0.3, 0.6))
        card.set_billboard_axis()
        card.set_shader_auto()
        card.set_transparency(TransparencyAttrib.M_alpha)

        from direct.interval.IntervalGlobal import Sequence, LerpFunc, Func
        seq = Sequence(
            LerpFunc(lambda t: card.set_color_scale(Vec4(1, 0.3, 0.3, 0.6 * (1 - t))), duration=0.3, fromData=0, toData=1),
            Func(effect.remove_node),
        )
        seq.start()

    def _play_sound(self, key: str) -> None:
        """Play a sound effect (placeholder - overridden by subclasses or manager)."""
        if self.manager and self.manager.audio_system:
            sound = self.manager.audio_system.get_sound(key)
            if sound:
                sound.play()

    # -----------------------------------------------------------------------
    # Animation System (Procedural)
    # -----------------------------------------------------------------------

    def _update_animation(self, dt: float) -> None:
        """Update procedural animations (direction indicator, body lean, etc.)."""
        if self._is_ragdoll:
            return

        # Animate direction indicator based on velocity
        if self.velocity.length() > 0.1 and self._direction_indicator:
            # Slight bounce/bob based on movement
            bob_amount = math.sin(globalClock.getFrameTime() * 8) * 0.05
            self._direction_indicator.set_z(bob_amount)

    # -----------------------------------------------------------------------
    # Weapon Handling
    # -----------------------------------------------------------------------

    def equip_weapon(self, weapon_data: Any) -> None:
        """
        Equip a weapon using the game's weapon system.

        Args:
            weapon_data: A WeaponData instance from the weapons package.
        """
        try:
            from weapons.weapon import Weapon
            self._weapon = Weapon(
                weapon_data=weapon_data,
                parent_node=self.node,
                camera=self.node,  # Use enemy node as "camera" for aiming
                collision_traverser=self.cTrav,
                render_node=self.render,
            )
        except ImportError:
            logger.warning("Weapons system not available, using default damage.Enemy.equip_weapon")
        except Exception as e:
            logger.warning("Failed to equip weapon: %s", e)

    def get_weapon(self) -> Optional[Any]:
        """Return the currently equipped weapon, if any."""
        return self._weapon

    def set_accuracy(self, accuracy: float) -> None:
        """Override the enemy's accuracy."""
        self.current_accuracy = max(0.0, min(1.0, accuracy))

    def apply_suppression(self, amount: float) -> None:
        """
        Apply suppression effect, making the enemy less accurate and slower.

        Args:
            amount: Suppression intensity (0.0 to 1.0).
        """
        self._suppression_level = min(1.0, self._suppression_level + amount)

    def clear_suppression(self) -> None:
        """Reset suppression level."""
        self._suppression_level = 0.0

    # -----------------------------------------------------------------------
    # Task Registration
    # -----------------------------------------------------------------------

    def _register_tasks(self) -> None:
        """Register the AI update task with Panda3D's task manager."""
        task_name = f"enemy_ai_{self.id}"
        taskMgr.add(self._ai_update, task_name, sort=30)

        # Cooldown task
        cooldown_name = f"enemy_cooldown_{self.id}"
        taskMgr.add(self._cooldown_update, cooldown_name, sort=31)

    def _cooldown_update(self, task: Task) -> Task:
        """Update cooldown timers."""
        dt = globalClock.getDt()
        self._nav_cooldown = max(0.0, self._nav_cooldown - dt)
        self._cover_cooldown = max(0.0, self._cover_cooldown - dt)
        self._grenade_cooldown = max(0.0, self._grenade_cooldown - dt)
        self._suppression_level *= 0.98  # Decay suppression over time
        return Task.cont

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_position(self) -> Vec3:
        """Return the enemy's current world position."""
        return self.node.get_pos(self.render)

    def get_state(self) -> EnemyState:
        """Return the current AI state."""
        return self.state

    def get_health_pct(self) -> float:
        """Return current health as a percentage (0.0 to 1.0)."""
        return self.health / self.max_health if self.max_health > 0 else 0.0

    def is_alive(self) -> bool:
        """Return True if the enemy is alive."""
        return self.state != EnemyState.DEAD

    def get_alert_level(self) -> AlertLevel:
        """Return the current alert level."""
        return self.alert_level

    def get_bounding_radius(self) -> float:
        """Return the radius of the enemy's collision bounds."""
        return self.enemy_data.size[0]

    def destroy(self) -> None:
        """Clean up all resources and remove the enemy from the world."""
        # Remove tasks
        taskMgr.remove_tasks_by_tags(f"enemy_{self.id}")
        taskMgr.remove(f"enemy_ai_{self.id}")
        taskMgr.remove(f"enemy_cooldown_{self.id}")

        # Clean up weapon
        if self._weapon and hasattr(self._weapon, 'cleanup'):
            self._weapon.cleanup()

        # Remove node
        if self.node and not self.node.is_empty():
            self.node.remove_node()

        # Remove from squad
        if self.squad:
            self.squad.remove_enemy(self)

        logger.debug("Enemy %d destroyed.", self.id)


# ---------------------------------------------------------------------------
# Enemy Manager
# ---------------------------------------------------------------------------


class EnemyManager(DirectObject):
    """
    Central manager for all enemy entities in the game world.

    Responsibilities:
        - Spawn and despawn enemies.
        - Propagate sound events to nearby enemies.
        - Track all active enemies and bosses.
        - Interface with the player for damage application.
        - Provide shared collision traverser and audio system.
        - Manage enemy squads for coordinated tactics.

    Args:
        base: The Panda3D ShowBase instance.
        collision_traverser: Shared collision traverser (or None to use base.cTrav).
    """

    def __init__(
        self,
        base: Any,
        collision_traverser: Optional[CollisionTraverser] = None,
    ):
        self.base = base
        self.render = base.render

        # Shared collision system
        self.cTrav = collision_traverser if collision_traverser is not None else base.cTrav

        # Entity tracking
        self.enemies: List[Enemy] = []
        self.bosses: List[Any] = []  # Boss instances (from ai.bosses)
        self.squads: Dict[int, SquadManager] = {}
        self._squad_counter: int = 0

        # Player reference
        self.player_ref: Optional[NodePath] = None

        # Audio system (optional, for enemy sounds)
        self.audio_system: Optional[Any] = None

        # Sound event propagation
        self._sound_events: List[SoundEvent] = []
        self._sound_propagation_task_name = "enemy_sound_propagation"

        # Spawn tracking
        self._enemy_counter: int = 0

        # Register the sound propagation task
        taskMgr.add(self._sound_propagation_update, self._sound_propagation_task_name, sort=10)

        logger.info("EnemyManager initialized.")

    def set_player(self, player_node: NodePath) -> None:
        """Set the player reference for all enemies to target."""
        self.player_ref = player_node
        for enemy in self.enemies:
            enemy.player_ref = player_node
        for boss in self.bosses:
            boss.player_ref = player_node

    def spawn_enemy(
        self,
        enemy_class: type,
        enemy_data: Optional[EnemyData] = None,
        position: Tuple[float, float, float] = (0, 0, 0),
        parent_node: Optional[NodePath] = None,
        squad_id: Optional[int] = None,
        patrol_points: Optional[List[PatrolPoint]] = None,
    ) -> Enemy:
        """
        Spawn an enemy of the given class at the specified position.

        Args:
            enemy_class: A subclass of Enemy to instantiate.
            enemy_data: Optional EnemyData override (uses class default if None).
            position: World-space spawn position.
            parent_node: NodePath to parent the enemy under.
            squad_id: Optional squad ID for grouping enemies.
            patrol_points: Optional patrol route waypoints.

        Returns:
            The spawned Enemy instance.
        """
        if not issubclass(enemy_class, Enemy):
            raise TypeError("enemy_class must be a subclass of Enemy")

        ed = enemy_data if enemy_data is not None else (
            enemy_class.ENEMY_DATA if hasattr(enemy_class, 'ENEMY_DATA') else EnemyData()
        )

        enemy = enemy_class(
            base=self.base,
            enemy_data=ed,
            parent_node=parent_node if parent_node is not None else self.render,
            collision_traverser=self.cTrav,
        )

        enemy.set_position(Vec3(position[0], position[1], position[2]))
        enemy.player_ref = self.player_ref
        enemy.manager = self

        # Assign to squad
        if squad_id is not None:
            squad = self.squads.get(squad_id)
            if squad is None:
                squad = SquadManager(squad_id)
                self.squads[squad_id] = squad
            squad.add_enemy(enemy)
        else:
            # Auto-create a squad for this enemy
            squad = SquadManager(self._squad_counter)
            self._squad_counter += 1
            squad.add_enemy(enemy)

        # Set patrol route if provided
        if patrol_points:
            enemy.set_patrol_route(patrol_points)

        # Register collision handler
        self._register_collision(enemy)

        self.enemies.append(enemy)
        self._enemy_counter += 1

        logger.info("Spawned enemy '%s' (ID: %d) at %s", enemy.name, enemy.id, position)
        return enemy

    def spawn_boss(
        self,
        boss_class: type,
        position: Tuple[float, float, float] = (0, 0, 0),
        parent_node: Optional[NodePath] = None,
    ) -> Any:
        """
        Spawn a boss enemy at the specified position.

        Args:
            boss_class: A subclass of Boss from ai.bosses.
            position: World-space spawn position.
            parent_node: NodePath to parent under (default: render).

        Returns:
            The spawned Boss instance.
        """
        boss = boss_class(
            base=self.base,
            parent_node=parent_node if parent_node is not None else self.render,
            collision_traverser=self.cTrav,
        )

        boss.set_position(Vec3(position[0], position[1], position[2]))
        boss.player_ref = self.player_ref
        boss.manager = self

        self._register_collision(boss)
        self.bosses.append(boss)

        logger.info("Spawned boss '%s' (ID: %d) at %s", boss.name, boss.id, position)
        return boss

    def _register_collision(self, enemy: Enemy) -> None:
        """Register the enemy's collision node with Panda3D's collision system."""
        if enemy._collision_node and self.cTrav is not None:
            # Set up collision handling if needed
            pass

    def _sound_propagation_update(self, task: Task) -> Task:
        """Task that propagates sound events to nearby enemies each frame."""
        # Age out old sound events
        current_time = globalClock.getFrameTime()
        self._sound_events = [e for e in self._sound_events if current_time - e.timestamp < 3.0]

        # Propagate events to enemies
        for event in self._sound_events:
            for enemy in self.enemies:
                if enemy.state == EnemyState.DEAD:
                    continue
                dist = enemy.node.get_pos().distance(event.position)
                max_radius = self._get_sound_radius(event)
                if dist <= max_radius:
                    enemy.receive_sound_event(event)

        return Task.cont

    def _get_sound_radius(self, event: SoundEvent) -> float:
        """Get the effective radius for a sound event based on type."""
        base = event.radius
        multiplier = {
            SoundType.FOOTSTEPS: 1.0,
            SoundType.GUNFIRE: 3.0,
            SoundType.EXPLOSION: 5.0,
            SoundType.DEATH: 1.5,
            SoundType.ALARM: 4.0,
            SoundType.AMBIENT: 0.5,
        }
        return base * multiplier.get(event.sound_type, 1.0)

    def on_sound_event(
        self,
        position: Point3,
        sound_type: SoundType,
        radius: float = 25.0,
    ) -> None:
        """
        Register a sound event in the world (e.g., gunfire, explosion).

        Args:
            position: World-space origin of the sound.
            sound_type: Category of sound.
            radius: Base detection radius.
        """
        event = SoundEvent(
            position=position,
            sound_type=sound_type,
            radius=radius,
            timestamp=globalClock.getFrameTime(),
        )
        self._sound_events.append(event)

        # Keep list bounded
        if len(self._sound_events) > 100:
            self._sound_events = self._sound_events[-50:]

    def on_enemy_death(self, enemy: Enemy, source: Optional[Vec3]) -> None:
        """Handle an enemy death event."""
        if enemy in self.enemies:
            self.enemies.remove(enemy)

        logger.info("Enemy '%s' (ID: %d) killed.", enemy.name, enemy.id)

    def apply_damage_to_player(
        self,
        damage: float,
        source_pos: Vec3,
        target_pos: Vec3,
    ) -> None:
        """
        Apply damage to the player. Should be overridden or connected
        to the game's player damage system.
        """
        if self.player_ref is None:
            return

        # Send an event that the game can listen for
        self.base.messenger.send("player_damaged", [damage, source_pos])

    def spawn_explosive(
        self,
        start_pos: Vec3,
        target_pos: Vec3,
        damage: float = 50.0,
        radius: float = 8.0,
    ) -> None:
        """
        Spawn a grenade/explosive that travels to target and explodes.

        This is a simplified implementation. A real game would use a
        proper projectile entity.
        """
        # Register the explosion as a sound event
        self.on_sound_event(target_pos, SoundType.EXPLOSION, radius=radius)

        # Apply damage to player if within radius
        if self.player_ref:
            player_pos = self.player_ref.get_pos(self.render)
            if player_pos.distance(target_pos) <= radius:
                self.base.messenger.send("player_damaged", [damage, target_pos])

    def get_all_enemies(self) -> List[Enemy]:
        """Return all active (living and dead) enemies."""
        return list(self.enemies)

    def get_living_enemies(self) -> List[Enemy]:
        """Return all living enemies."""
        return [e for e in self.enemies if e.state != EnemyState.DEAD]

    def get_enemies_in_radius(self, center: Vec3, radius: float) -> List[Enemy]:
        """Return all enemies within a radius of the center point."""
        return [e for e in self.enemies if e.node.get_pos().distance(center) <= radius]

    def update(self, dt: float) -> None:
        """Update all enemies (called by the game loop if not using individual tasks)."""
        for enemy in self.enemies:
            if enemy.state != EnemyState.DEAD:
                enemy._update_state(dt, globalClock.getFrameTime())

    def cleanup(self) -> None:
        """Clean up all enemies and the manager."""
        taskMgr.remove(self._sound_propagation_task_name)

        for enemy in self.enemies:
            enemy.destroy()
        self.enemies.clear()

        for boss in self.bosses:
            if hasattr(boss, 'destroy'):
                boss.destroy()
        self.bosses.clear()

        self.squads.clear()
        self.player_ref = None

        logger.info("EnemyManager cleaned up. %d enemies destroyed.", self._enemy_counter)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def create_sound_event(
    position: Point3,
    sound_type: SoundType,
    radius: float = 25.0,
) -> SoundEvent:
    """
    Create a SoundEvent for propagation.

    Args:
        position: Where the sound originated.
        sound_type: Type of sound.
        radius: Base detection radius.

    Returns:
        A SoundEvent instance.
    """
    return SoundEvent(
        position=position,
        sound_type=sound_type,
        radius=radius,
        timestamp=globalClock.getFrameTime(),
    )


def line_of_sight_check(
    cTrav: CollisionTraverser,
    render: NodePath,
    start: Point3,
    end: Point3,
    collision_mask: BitMask32 = None,
) -> bool:
    """
    Static helper: check line of sight between two points using raycast.

    Args:
        cTrav: Panda3D CollisionTraverser instance.
        render: The render scene graph root.
        start: Ray origin.
        end: Ray target.
        collision_mask: Mask to collide against (default: geometry only).

    Returns:
        True if line of sight is clear, False if obstructed.
    """
    if collision_mask is None:
        collision_mask = Constants.MASK_GEOMETRY

    direction = end - start
    distance = direction.length()
    if distance < 0.01:
        return True

    direction.normalize()

    ray = CollisionRay()
    ray.set_origin(start + Vec3(0, 0, 1.5))
    ray.set_direction(direction)

    ray_node = CollisionNode("los_check_temp")
    ray_node.add_solid(ray)
    ray_node.set_from_collide_mask(collision_mask)
    ray_node.set_into_collide_mask(BitMask32.all_off())

    ray_np = render.attach_new_node(ray_node)
    queue = CollisionHandlerQueue()
    cTrav.traverse(render)
    cTrav.traverse_node(ray_np, cTrav, queue)

    ray_np.remove_node()

    entries = queue.get_entries()
    if not entries:
        return True

    closest = entries[0]
    hit_distance = closest.get_surface_point(render).distance(start)
    return hit_distance >= distance - 0.5


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "EnemyState",
    "AlertLevel",
    "SoundType",
    "EnemyData",
    "PatrolPoint",
    "CoverPoint",
    "SoundEvent",
    "AlertEvent",
    "SquadManager",
    "Enemy",
    "EnemyManager",
    "create_sound_event",
    "line_of_sight_check",
]
