"""
Base Weapon class and supporting data structures for the Panda3D FPS weapon system.

This module defines:
- WeaponData: A comprehensive data structure holding all weapon configuration.
- WeaponState, FireMode, AmmoType: Enumerations for weapon states and modes.
- HitResult, SurfaceType: Data structures for hit detection results.
- RecoilKick, MuzzleFlashParams, ShellCasingParams: Parameters for visual/recoil effects.
- Weapon: The main Weapon class implementing all FPS mechanics.

The Weapon class supports:
- Raycast-based hit detection with surface type awareness
- Multiple fire modes (semi, auto, burst)
- Ammo management with magazine and reserve tracking
- ADS (aim down sights) with FOV change and accuracy modifiers
- Recoil system with smooth return and visual feedback
- Reload state machine (interruptible, with dry-fire logic)
- Muzzle flash particle systems using Panda3D's ParticleEffect
- Shell casing ejection with physics
- Weapon sway and movement effects
- Sound effect playback via Panda3D's AudioSystem

Requires:
    - Panda3D (panda3d)
    - Python 3.8+

Author: SHARIFA Game Development Team
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Callable, Any, Tuple

from panda3d.core import (
    NodePath,
    PandaNode,
    CollisionNode,
    CollisionRay,
    CollisionTraverser,
    BitMask32,
    Vec3,
    Vec4,
    Vec2,
    Point3,
    TransformState,
    ClockObject,
    Filename,
    CardMaker,
    GeomNode,
    Geom,
    GeomVertexData,
    GeomVertexFormat,
    GeomEnums,
    GeomTristrips,
    GeomVertexWriter,
    GeomTrifans,
)
from direct.task.Task import Task
from direct.showbase.DirectObject import DirectObject
from direct.particles.ParticleEffect import ParticleEffect
from direct.actor.Actor import Actor
from direct.interval.IntervalManager import ivalMgr
from direct.interval.MetaInterval import Sequence, Parallel
from direct.interval.FunctionInterval import Func, Wait
from direct.interval.IntervalGlobal import LerpFunc, LerpPosInterval
from direct.showbase.MessengerGlobal import messenger
from panda3d import core as p3d


class WeaponState(IntEnum):
    """Enumeration of possible weapon states in the state machine.

    The weapon transitions between these states during gameplay.
    State transitions are managed internally by the Weapon class.
    """

    IDLE = 0          # Weapon is idle, not firing or reloading
    FIRING = 1        # Weapon is actively firing
    RELOADING = 2     # Weapon is in the reload sequence
    SWITCHING = 3     # Weapon is being switched to/from (draw/stow)
    ADS = 4           # Weapon is in aim-down-sights mode
    EMPTY = 5         # Weapon has no ammo in magazine and is not reloading


class FireMode(Enum):
    """Enumeration of fire modes supported by weapons.

    SEMI: Single shot per trigger pull (semi-automatic)
    AUTO: Continuous fire while trigger is held (fully automatic)
    BURST: Fires a fixed number of rounds per trigger pull (burst fire)
    """

    SEMI = "semi"
    AUTO = "auto"
    BURST = "burst"


class AmmoType(Enum):
    """Enumeration of ammunition types.

    Each ammo type can have different effects on different surface types
    and may be resisted or enhanced by armor.
    """

    NORMAL = "normal"
    ARMOR_PIERCING = "armor_piercing"
    INCENDIARY = "incendiary"
    EXPLOSIVE = "explosive"
    ENERGY = "energy"
    PLASMA = "plasma"
    SHOTGUN = "shotgun"


class SurfaceType(Enum):
    """Enumeration of surface types for hit detection and effects.

    Different surface types trigger different impact effects
    (sounds, particle effects, etc.).
    """

    FLESH = "flesh"
    METAL = "metal"
    WOOD = "wood"
    CONCRETE = "concrete"
    GLASS = "glass"
    WATER = "water"
    AIR = "air"


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class RecoilKick:
    """Parameters for weapon recoil behavior.

    Attributes:
        aim_pistol:     Vertical recoil multiplier when not aiming (pistol-like feel).
        aim_rifle:      Vertical recoil multiplier when not aiming (rifle-like feel).
        ads_multiplier: Multiplier applied to all recoil when in ADS mode.
        horizontal_min: Minimum horizontal (side-to-side) recoil angle in degrees.
        horizontal_max: Maximum horizontal recoil angle in degrees.
        vertical_min:   Minimum vertical recoil angle in degrees.
        vertical_max:   Maximum vertical recoil angle in degrees.
        return_speed:   How quickly the view returns to center after recoil (degrees/sec).
        smoothness:     How smoothly the recoil is applied (0.0 = instant, 1.0 = gradual).
    """

    aim_pistol: float = 0.8
    aim_rifle: float = 1.5
    ads_multiplier: float = 0.35
    horizontal_min: float = 0.2
    horizontal_max: float = 1.5
    vertical_min: float = 0.5
    vertical_max: float = 2.5
    return_speed: float = 8.0
    smoothness: float = 0.6


@dataclass
class MuzzleFlashParams:
    """Parameters for muzzle flash visual effects.

    Attributes:
        color:      RGBA color of the muzzle flash.
        scale:      Base scale of the flash sprite.
        duration:   How long the flash lasts in seconds.
        brightness: Peak brightness multiplier.
    """

    color: Vec4 = Vec4(1.0, 0.8, 0.3, 1.0)
    scale: float = 0.3
    duration: float = 0.05
    brightness: float = 1.0


@dataclass
class ShellCasingParams:
    """Parameters for shell casing ejection effects.

    Attributes:
        enabled:       Whether shell casings are ejected.
        model_path:    Path to the shell casing model (if available).
        color:         Default color of the casing (used for procedural geometry).
        scale:         Scale of the casing model.
        eject_velocity: Initial velocity vector for the casing.
        lifetime:      How long the casing exists before being removed.
        gravity:       Gravity multiplier applied to the casing.
    """

    enabled: bool = True
    model_path: str = ""
    color: Vec4 = Vec4(0.8, 0.7, 0.2, 1.0)  # Brass-like
    scale: float = 0.15
    eject_velocity: Vec3 = field(default_factory=lambda: Vec3(2, 5, -3))
    lifetime: float = 5.0
    gravity: float = 1.0


@dataclass
class HitResult:
    """Result of a raycast hit detection.

    Attributes:
        hit:          Whether the ray hit anything.
        hit_position: World-space position of the impact point.
        hit_normal:   Surface normal at the impact point.
        surface_type: Type of surface that was hit.
        entity:       The Entity (or None) that was hit, if any.
        distance:     Distance from the ray origin to the impact point.
    """

    hit: bool = False
    hit_position: Point3 = field(default_factory=lambda: Point3(0, 0, 0))
    hit_normal: Vec3 = field(default_factory=lambda: Vec3(0, 0, 1))
    surface_type: SurfaceType = SurfaceType.AIR
    entity: Optional[Any] = None
    distance: float = 0.0
    is_headshot: bool = False
    damage_multiplier: float = 1.0


@dataclass
class WeaponData:
    """Comprehensive data structure for weapon configuration.

    This dataclass holds all the static configuration for a weapon.
    It is used by the Weapon class to determine behavior.

    Attributes:
        weapon_id:          Unique identifier for this weapon definition.
        name:               Display name of the weapon.
        category:           Weapon category (e.g., 'assault_rifle', 'pistol').
        damage:             Base damage per shot (per projectile).
        fire_rate:          Shots per minute (rounds per minute).
        accuracy:           Base accuracy as a percentage (0.0 to 1.0).
        accuracy_ads:       Accuracy when aiming down sights (0.0 to 1.0).
        accuracy_move:      Accuracy penalty multiplier when moving (0.0 to 1.0).
        range:              Maximum effective range in world units.
        magazine_size:      Number of rounds in a full magazine.
        reserve_ammo:       Starting reserve ammo count.
        reload_time:        Time to complete a full reload in seconds.
        reload_time_empty:  Time to reload when magazine is empty (often longer).
        recoil:             RecoilKick parameters for this weapon.
        muzzle_flash:       MuzzleFlashParams for this weapon.
        shell_casing:       ShellCasingParams for this weapon.
        fire_modes:         List of FireMode values this weapon supports.
        default_fire_mode:  The fire mode used when the weapon is first drawn.
        ammo_type:          AmmoType used by this weapon.
        aim_fov:            FOV when aiming down sights (0 = no change).
        aim_offset:         View model offset when in ADS (Vec3).
        aim_zoom_duration:  Time to transition to/from ADS in seconds.
        shot_sound:         Path to the firing sound effect file.
        reload_sound:       Path to the reload sound effect file.
        dry_fire_sound:     Path to the dry-fire (empty) sound effect file.
        hit_sounds:         Dict mapping SurfaceType to hit sound file paths.
        melee_damage:       Damage dealt by melee attack (if applicable).
        melee_range:        Range of melee attack in world units.
        burst_count:        Number of shots in a burst (for BURST fire mode).
        model_color:        RGBA color for the procedural weapon model.
        model_shape:        Shape name for procedural model ('box', 'cylinder', 'barrel').
        model_dimensions:   (width, height, depth) for procedural model in world units.
        description:        Flavor text description of the weapon.
    """

    # Identification
    weapon_id: str = ""
    name: str = ""
    category: str = ""

    # Core Combat Stats
    damage: float = 10.0
    fire_rate: float = 600.0  # Shots per minute, converted internally
    accuracy: float = 0.85
    accuracy_ads: float = 0.98
    accuracy_move: float = 0.6
    range: float = 800.0

    # Ammo Management
    magazine_size: int = 30
    reserve_ammo: int = 120
    reload_time: float = 2.0
    reload_time_empty: float = 2.5
    ammo_type: AmmoType = AmmoType.NORMAL

    # Fire Modes
    fire_modes: List[FireMode] = field(default_factory=lambda: [FireMode.SEMI, FireMode.AUTO])
    default_fire_mode: FireMode = FireMode.SEMI
    burst_count: int = 3

    # Recoil System
    recoil: RecoilKick = field(default_factory=RecoilKick)

    # Visual Effects
    muzzle_flash: MuzzleFlashParams = field(default_factory=MuzzleFlashParams)
    shell_casing: ShellCasingParams = field(default_factory=ShellCasingParams)

    # Aiming
    aim_fov: float = 0.0          # 0 means no change from default FOV
    aim_offset: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.5, -0.3))
    aim_zoom_duration: float = 0.15

    # Audio
    shot_sound: str = ""
    reload_sound: str = ""
    dry_fire_sound: str = ""
    hit_sounds: Dict[SurfaceType, str] = field(default_factory=dict)

    # Melee
    melee_damage: float = 25.0
    melee_range: float = 2.0

    # Visual Representation
    model_color: Vec4 = field(default_factory=lambda: Vec4(0.8, 0.8, 0.8, 1.0))
    model_shape: str = "box"
    model_dimensions: Tuple[float, float, float] = (0.3, 0.2, 1.2)

    # Metadata
    description: str = ""


# ---------------------------------------------------------------------------
# Main Weapon Class
# ---------------------------------------------------------------------------


class Weapon(DirectObject):
    """Complete FPS weapon implementation with all mechanics.

    The Weapon class encapsulates all gameplay mechanics for a single weapon:
    firing, reloading, switching, aiming, recoil, hit detection, and effects.

    It integrates with Panda3D's task system and event handling, and uses
    procedural geometry for visual representation when 3D models are unavailable.

    Args:
        weapon_data: A WeaponData instance with configuration for this weapon.
        parent_node: The NodePath to attach the weapon's view model to.
        camera:      The camera NodePath (for raycasting and ADS FOV).
        collision_traverser: A CollisionTraverser for raycast hit detection.
        render_node: The main render NodePath (for particle effects, etc.).

    Attributes:
        current_ammo:     Ammo remaining in the current magazine.
        reserve_ammo:     Ammo in reserve (not in magazine).
        state:            Current WeaponState.
        fire_mode:        Current FireMode.
        is_ads:           Whether currently aiming down sights.
        is_trigger_pressed: Whether the fire trigger is currently held.
    """

    def __init__(
        self,
        weapon_data: WeaponData,
        parent_node: NodePath,
        camera: NodePath,
        collision_traverser: CollisionTraverser,
        render_node: NodePath = None,
    ):
        if weapon_data is None:
            raise ValueError("weapon_data cannot be None")
        if parent_node is None:
            raise ValueError("parent_node cannot be None")
        if camera is None:
            raise ValueError("camera cannot be None")

        DirectObject.__init__(self)

        self.weapon_data = weapon_data
        self.parent_node = parent_node
        self.camera = camera
        self.cTrav = collision_traverser
        self.render = render_node if render_node is not None else base.render

        # Ammo state
        self.current_ammo = weapon_data.magazine_size
        self.reserve_ammo = weapon_data.reserve_ammo

        # State machine
        self.state: WeaponState = WeaponState.IDLE
        self.fire_mode: FireMode = weapon_data.default_fire_mode
        self.is_ads: bool = False
        self.is_trigger_pressed: bool = False

        # Timing
        self._last_shot_time: float = 0.0
        self._reload_start_time: float = 0.0
        self._switch_progress: float = 0.0
        self._ads_progress: float = 0.0  # 0.0 = hip, 1.0 = fully ADS
        self._burst_count_remaining: int = 0
        self._burst_cooldown: bool = False

        # Recoil state
        self._recoil_active: bool = False
        self._recoil_target: Vec2 = Vec2(0, 0)
        self._recoil_current: Vec2 = Vec2(0, 0)
        self._camera_pitch_offset: float = 0.0
        self._camera_yaw_offset: float = 0.0

        # Burst / auto timing
        self._time_since_last_shot: float = 0.0
        self._burst_shot_count: int = 0
        self._consecutive_shots: int = 0
        self._dry_fire_timer: float = 0.0

        # Event names (unique per weapon instance)
        self._event_prefix = f"weapon_{id(self)}_"

        # Procedural model and effects nodes
        self.view_model: Optional[NodePath] = None
        self._flash_node: Optional[NodePath] = None
        self._shell_eject_node: Optional[NodePath] = None
        self._muzzle_attach: Optional[NodePath] = None
        self._active_shells: List[NodePath] = []
        self._active_effects: List[ParticleEffect] = []

        # Audio
        self._sounds: Dict[str, Any] = {}

        # Build the procedural model
        self._build_view_model()

        # Register tasks
        self._register_tasks()

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def shots_per_second(self) -> float:
        """Convert fire_rate (rounds per minute) to shots per second."""
        return self.weapon_data.fire_rate / 60.0

    @property
    def time_between_shots(self) -> float:
        """Time in seconds between each shot."""
        if self.shots_per_second <= 0:
            return float('inf')
        return 1.0 / self.shots_per_second

    @property
    def is_magazine_empty(self) -> bool:
        """Whether the current magazine is empty."""
        return self.current_ammo <= 0

    @property
    def has_reserve_ammo(self) -> bool:
        """Whether there is any reserve ammo available."""
        return self.reserve_ammo > 0

    @property
    def is_reloading(self) -> bool:
        """Whether the weapon is currently reloading."""
        return self.state == WeaponState.RELOADING

    @property
    def is_switching(self) -> bool:
        """Whether the weapon is currently being switched."""
        return self.state == WeaponState.SWITCHING

    @property
    def current_spread(self) -> float:
        """Current accuracy spread (higher = less accurate).

        Spread increases when firing rapidly and when not in ADS mode.
        """
        # Base spread from accuracy
        base_spread = 1.0 - self._effective_accuracy()

        # Movement penalty
        move_penalty = 1.0
        if self._is_moving():
            move_penalty = 1.0 / self.weapon_data.accuracy_move

        # Firing penalty (accumulates during automatic fire)
        firing_penalty = 1.0
        if self.state == WeaponState.FIRING and self.fire_mode == FireMode.AUTO:
            firing_penalty = 1.0 + (self._consecutive_shots * 0.02)

        return max(0.0, base_spread * move_penalty * firing_penalty)

    @property
    def effective_fov(self) -> float:
        """Return the effective FOV based on ADS progress."""
        if self.weapon_data.aim_fov == 0.0:
            return 0.0
        return self.weapon_data.aim_fov * self._ads_progress

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def enter_weapon(self, switch_duration: float = 0.5) -> None:
        """Bring the weapon into view (play draw animation).

        Args:
            switch_duration: Time for the draw animation in seconds.
        """
        if self.state == WeaponState.SWITCHING:
            return

        self.state = WeaponState.SWITCHING
        self._switch_progress = 0.0
        if self.view_model:
            self.view_model.show()

    def exit_weapon(self, switch_duration: float = 0.5) -> None:
        """Hide the weapon (play stow animation).

        Args:
            switch_duration: Time for the stow animation in seconds.
        """
        if self.state == WeaponState.SWITCHING:
            return

        self.state = WeaponState.SWITCHING
        self._switch_progress = 0.0

    def start_firing(self) -> None:
        """Begin firing the weapon (called when trigger is pressed)."""
        if self.state in (WeaponState.RELOADING, WeaponState.SWITCHING):
            return

        self.is_trigger_pressed = True

        if not self._can_fire():
            self._play_dry_fire()
            self._start_dry_fire_timer()
            return

        if self.fire_mode == FireMode.SEMI:
            self._fire_single_shot()
        elif self.fire_mode == FireMode.AUTO:
            self._fire_single_shot()
            self.state = WeaponState.FIRING
        elif self.fire_mode == FireMode.BURST:
            self._start_burst()

    def stop_firing(self) -> None:
        """Stop firing the weapon (called when trigger is released)."""
        self.is_trigger_pressed = False

        if self._burst_cooldown:
            return

        if self.state == WeaponState.FIRING:
            if self.is_ads:
                self.state = WeaponState.ADS
            elif self.current_ammo > 0:
                self.state = WeaponState.IDLE
            else:
                self.state = WeaponState.EMPTY

    def reload(self) -> None:
        """Initiate reload sequence.

        The reload can be interrupted by switching weapons. If the magazine
        is empty, the longer empty-reload time is used.
        """
        if self.state == WeaponState.RELOADING:
            return

        if self.state == WeaponState.SWITCHING:
            return

        if self.current_ammo >= self.weapon_data.magazine_size:
            if self.reserve_ammo <= 0:
                return

        self.state = WeaponState.RELOADING
        self._reload_start_time = globalClock.getFrameTime()

        if self.is_magazine_empty:
            reload_time = self.weapon_data.reload_time_empty
        else:
            reload_time = self.weapon_data.reload_time

        self._reload_duration = reload_time
        task_name = f"{self._event_prefix}reload_complete"
        task = Task(self._complete_reload)
        taskMgr.doMethodLater(reload_time, task, task_name)

    def toggle_ads(self) -> None:
        """Toggle aim-down-sights mode."""
        if self.state in (WeaponState.RELOADING, WeaponState.SWITCHING):
            return

        self.is_ads = not self.is_ads
        target_progress = 1.0 if self.is_ads else 0.0
        duration = self.weapon_data.aim_zoom_duration
        self._animate_ads(target_progress, duration)

        if self.is_ads:
            self.state = WeaponState.ADS
        else:
            if self.state == WeaponState.ADS:
                self.state = WeaponState.IDLE

    def aim_down_sights(self) -> None:
        """Enter aim-down-sights mode."""
        if self.is_ads:
            return
        self.is_ads = True
        self._animate_ads(1.0, self.weapon_data.aim_zoom_duration)
        self.state = WeaponState.ADS

    def hip_fire(self) -> None:
        """Exit aim-down-sights mode."""
        if not self.is_ads:
            return
        self.is_ads = False
        self._animate_ads(0.0, self.weapon_data.aim_zoom_duration)
        if self.state == WeaponState.ADS:
            self.state = WeaponState.IDLE

    def switch_fire_mode(self) -> None:
        """Cycle to the next available fire mode."""
        modes = self.weapon_data.fire_modes
        if len(modes) <= 1:
            return

        try:
            current_index = modes.index(self.fire_mode)
        except ValueError:
            current_index = 0
        next_index = (current_index + 1) % len(modes)
        self.fire_mode = modes[next_index]

        if self._burst_cooldown:
            self._burst_cooldown = False
            self._burst_count_remaining = 0

    def get_ammo_status(self) -> Tuple[int, int]:
        """Return current ammo status.

        Returns:
            A tuple of (current_magazine_ammo, reserve_ammo).
        """
        return self.current_ammo, self.reserve_ammo

    def add_ammo(self, ammo_count: int) -> int:
        """Add ammo to reserve.

        Args:
            ammo_count: Number of rounds to add.

        Returns:
            Number of rounds actually added (may be less if at max capacity).
        """
        max_reserve = self.weapon_data.reserve_ammo + self.weapon_data.magazine_size
        space_available = max_reserve - self.reserve_ammo
        added = min(ammo_count, space_available)
        self.reserve_ammo += added
        return added

    def get_ads_fov(self) -> float:
        """Return the FOV to use when in ADS.

        Returns:
            The ADS FOV value. If aim_fov is 0, returns 0 (no change).
        """
        if self.weapon_data.aim_fov == 0.0:
            return 0.0
        return self.weapon_data.aim_fov

    def get_view_offset(self) -> Vec3:
        """Return the view model offset based on ADS state.

        Returns:
            Vec3 offset to apply to the view model position.
        """
        if self.weapon_data.aim_fov == 0.0:
            return Vec3(0, 0, 0)

        target_offset = self.weapon_data.aim_offset
        lerp_factor = self._ads_progress
        return Vec3(
            target_offset.x * lerp_factor,
            target_offset.y * lerp_factor,
            target_offset.z * lerp_factor,
        )

    def get_recoil_offset(self) -> Vec3:
        """Return the accumulated camera recoil offset.

        Returns:
            Vec3 representing the camera offset from recoil.
        """
        return Vec3(
            math.radians(self._camera_yaw_offset) * 10,
            math.radians(self._camera_pitch_offset) * 10,
            0,
        )

    def get_recoil_angles(self) -> Tuple[float, float]:
        """Return the accumulated camera recoil angles.

        Returns:
            Tuple of (yaw_offset_degrees, pitch_offset_degrees).
        """
        return self._camera_yaw_offset, self._camera_pitch_offset

    def cleanup(self) -> None:
        """Clean up resources and unregister events/tasks."""
        self.ignoreAll()

        # Remove tasks
        taskMgr.removeTasksWithTag(self._event_prefix)

        # Clean up particle effects
        for effect in self._active_effects:
            try:
                effect.disable()
                effect.cleanup()
            except Exception:
                pass
        self._active_effects.clear()

        # Clean up shell casings
        for shell in self._active_shells:
            if not shell.isEmpty():
                shell.removeNode()
        self._active_shells.clear()

        # Clean up sounds
        for sound in self._sounds.values():
            if sound and hasattr(sound, 'stop'):
                sound.stop()
        self._sounds.clear()

        # Clean up view model
        if self.view_model:
            self.view_model.removeNode()
            self.view_model = None

    # -----------------------------------------------------------------------
    # Private: Firing Logic
    # -----------------------------------------------------------------------

    def _can_fire(self) -> bool:
        """Check if the weapon can fire right now."""
        if self.current_ammo <= 0:
            return False
        if self.state in (WeaponState.RELOADING, WeaponState.SWITCHING):
            return False
        if self.state == WeaponState.EMPTY:
            return False
        return True

    def _fire_single_shot(self) -> None:
        """Execute a single shot (raycast, consume ammo, apply recoil, play effects)."""
        if not self._can_fire():
            return

        self.current_ammo -= 1
        self.state = WeaponState.FIRING

        self._consecutive_shots += 1

        # Perform hit detection
        hit_result = self._perform_raycast()

        # Notify of hit (for mastery tracking)
        if hit_result.hit:
            messenger.send("weapon_hit", [self.weapon_data.weapon_id, hit_result])

        # Spawn hit effects
        self._spawn_hit_effects(hit_result)

        # Apply recoil
        self._apply_recoil()

        # Spawn muzzle flash
        self._spawn_muzzle_flash()

        # Eject shell casing
        self._eject_shell_casing()

        # Play firing sound
        self._play_sound('shot')

        # Update last shot time
        self._last_shot_time = globalClock.getFrameTime()
        self._time_since_last_shot = 0.0

        # Reset dry fire timer
        self._dry_fire_timer = 0.0

        # Handle empty magazine
        if self.current_ammo <= 0:
            if self.reserve_ammo > 0:
                self.state = WeaponState.EMPTY
            else:
                self.state = WeaponState.EMPTY

            self._play_sound('dry_fire')
        else:
            if self.fire_mode == FireMode.SEMI:
                if self.is_ads:
                    self.state = WeaponState.ADS
                else:
                    self.state = WeaponState.IDLE

    def _start_burst(self) -> None:
        """Start a burst fire sequence."""
        if not self._can_fire():
            self._play_dry_fire()
            return

        self._burst_count_remaining = self.weapon_data.burst_count
        self._burst_cooldown = True
        self._burst_shot_count = 0
        self._fire_burst_shot()

    def _fire_burst_shot(self) -> None:
        """Fire a single shot in the burst sequence."""
        if self._burst_count_remaining <= 0 or not self._can_fire():
            self._burst_cooldown = False
            self._burst_shot_count = 0
            if self.is_ads:
                self.state = WeaponState.ADS
            elif self.current_ammo > 0:
                self.state = WeaponState.IDLE
            else:
                self.state = WeaponState.EMPTY
            return

        self._fire_single_shot()
        self._burst_count_remaining -= 1
        self._burst_shot_count += 1

        if self._burst_count_remaining > 0:
            delay = self.time_between_shots * 0.5
            task_name = f"{self._event_prefix}burst_{id(self)}"
            taskMgr.doMethodLater(delay, self._task_burst_continue, task_name)

    def _task_burst_continue(self, task: Task) -> Task:
        """Task callback to continue the burst sequence."""
        self._fire_burst_shot()
        return Task.done

    def _complete_reload(self, task: Task) -> Task:
        """Complete the reload sequence."""
        needed = self.weapon_data.magazine_size - self.current_ammo
        if self.reserve_ammo >= needed:
            self.current_ammo = self.weapon_data.magazine_size
            self.reserve_ammo -= needed
        else:
            self.current_ammo += self.reserve_ammo
            self.reserve_ammo = 0

        if self.current_ammo <= 0:
            self.state = WeaponState.EMPTY
        elif self.is_ads:
            self.state = WeaponState.ADS
        else:
            self.state = WeaponState.IDLE

        self._consecutive_shots = 0
        self._stop_sound('reload')

        return Task.done

    def _start_dry_fire_timer(self) -> None:
        """Start a timer to prevent constant dry-fire sounds."""
        self._dry_fire_timer = 0.5

    def _play_dry_fire(self) -> None:
        """Play the dry-fire sound if available and not on cooldown."""
        if self._dry_fire_timer > 0:
            return
        self._play_sound('dry_fire')
        self._start_dry_fire_timer()

    # -----------------------------------------------------------------------
    # Private: Raycast / Hit Detection
    # -----------------------------------------------------------------------

    def _perform_raycast(self) -> HitResult:
        """Perform a raycast from the camera to find what was hit.

        Returns:
            A HitResult with hit information.
        """
        result = HitResult()

        try:
            cam_pos = self.camera.getPos(self.render)
            cam_hpr = self.camera.getHpr(self.render)

            # Apply camera recoil offsets
            cam_hpr.x += self._camera_yaw_offset
            cam_hpr.y += self._camera_pitch_offset

            # Create ray from camera
            ray = CollisionRay()
            ray.setOrigin(cam_pos)
            ray.setDirection(self._hpr_to_vector(cam_hpr))

            # Apply spread
            spread = self.current_spread
            spread_x = random.gauss(0, spread)
            spread_y = random.gauss(0, spread)
            spread_dir = ray.getDirection() + Vec3(spread_x, spread_y, 0)
            ray.setDirection(spread_dir)

            # Set up collision
            ray_node = CollisionNode(f"{self._event_prefix}ray")
            ray_node.addSolid(ray)
            ray_node.setFromCollideMask(BitMask32.allOn())
            ray_node.setIntoCollideMask(BitMask32.allOff())

            ray_np = self.camera.attachNewNode(ray_node)
            self.cTrav.traverse(self.render)

            entries = list(self.cTrav.getCollisions())
            if entries:
                entries.sort(key=lambda e: e.getSurfacePoint(self.render).distance(cam_pos))
                closest = entries[0]

                result.hit = True
                result.hit_position = closest.getSurfacePoint(self.render)
                result.hit_normal = closest.getSurfaceNormal(self.render)
                result.distance = result.hit_position.distance(cam_pos)
                result.surface_type = self._detect_surface_type(closest)
                result.entity = closest.getIntoNode() if closest.getIntoNode() else None

            ray_np.removeNode()
        except Exception as e:
            pass

        return result

    def _hpr_to_vector(self, hpr: Vec3) -> Vec3:
        """Convert an HPR orientation to a direction vector."""
        temp_node = NodePath("temp_dir")
        temp_node.setHpr(hpr)
        direction = temp_node.getRelativeVector(self.render, Vec3.forward())
        temp_node.removeNode()
        return direction

    def _detect_surface_type(self, collision_entry) -> SurfaceType:
        """Detect the surface type from a collision entry."""
        into_node = collision_entry.getIntoNode()
        into_name = into_node.getName() if into_node else ""

        if into_node and into_node.hasTag("surface_type"):
            try:
                return SurfaceType(into_node.getTag("surface_type"))
            except ValueError:
                pass

        name_lower = into_node.getName().lower() if into_node else ""
        if "flesh" in name_lower or "character" in name_lower or "enemy" in name_lower:
            return SurfaceType.FLESH
        elif "metal" in name_lower or "steel" in name_lower:
            return SurfaceType.METAL
        elif "wood" in name_lower:
            return SurfaceType.WOOD
        elif "glass" in name_lower:
            return SurfaceType.GLASS
        elif "water" in name_lower:
            return SurfaceType.WATER
        elif "concrete" in name_lower or "wall" in name_lower or "floor" in name_lower:
            return SurfaceType.CONCRETE

        return SurfaceType.CONCRETE

    # -----------------------------------------------------------------------
    # Private: Recoil System
    # -----------------------------------------------------------------------

    def _apply_recoil(self) -> None:
        """Apply recoil to the camera/view."""
        recoil_data = self.weapon_data.recoil

        if self.is_ads:
            multiplier = recoil_data.ads_multiplier
        else:
            multiplier = 1.0

        horiz = random.uniform(recoil_data.horizontal_min, recoil_data.horizontal_max)
        vert = random.uniform(recoil_data.vertical_min, recoil_data.vertical_max)

        if random.random() > 0.5:
            horiz = -horiz

        horiz *= multiplier
        vert *= multiplier

        self._recoil_target = Vec2(horiz, vert)
        self._recoil_current = Vec2(0, 0)
        self._recoil_active = True

        self._camera_yaw_offset += horiz
        self._camera_pitch_offset += vert

        self._camera_yaw_offset = max(-15.0, min(15.0, self._camera_yaw_offset))
        self._camera_pitch_offset = max(-15.0, min(15.0, self._camera_pitch_offset))

    def _update_recoil_return(self, dt: float) -> None:
        """Smoothly return the camera to center after recoil."""
        return_speed = self.weapon_data.recoil.return_speed

        self._camera_yaw_offset *= max(0.0, 1.0 - return_speed * dt)
        self._camera_pitch_offset *= max(0.0, 1.0 - return_speed * dt)

        if abs(self._camera_yaw_offset) < 0.001:
            self._camera_yaw_offset = 0.0
        if abs(self._camera_pitch_offset) < 0.001:
            self._camera_pitch_offset = 0.0

        self._recoil_active = not (
            abs(self._camera_yaw_offset) < 0.01 and abs(self._camera_pitch_offset) < 0.01
        )

    # -----------------------------------------------------------------------
    # Private: Visual Effects
    # -----------------------------------------------------------------------

    def _spawn_muzzle_flash(self) -> None:
        """Spawn a muzzle flash effect at the weapon's muzzle."""
        flash_params = self.weapon_data.muzzle_flash

        if self._muzzle_attach is None:
            return

        flash_np = self._muzzle_attach.attachNewNode("muzzle_flash")

        try:
            effect = ParticleEffect()
            eff = self._create_flash_particle_config(flash_params)
            effect.start(parent=flash_np, renderParent=self.render)
            self._active_effects.append(effect)
            self._schedule_effect_cleanup(effect, flash_params.duration + 0.1)
        except Exception:
            cm = CardMaker("flash_card")
            cm.setFrame(-flash_params.scale, flash_params.scale, -flash_params.scale, flash_params.scale)
            card = flash_np.attachNewNode(cm.generate())
            card.setColor(flash_params.color)
            card.setBillboardAxis()
            card.setShaderAuto()

            seq = Sequence(
                LerpFunc(lambda t: card.setColorScale(flash_params.color * t), duration=flash_params.duration, fromData=0, toData=1),
                Wait(0.01),
                LerpFunc(lambda t: card.setColorScale(flash_params.color * (1.0 - t)), duration=flash_params.duration, fromData=0, toData=1),
                Func(card.removeNode),
            )
            seq.start()

    def _create_flash_particle_config(self, params: MuzzleFlashParams):
        """Create a particle effect configuration for muzzle flash."""
        from direct.particles.Particles import Particles

        eff = ParticleEffect()
        particles = Particles()
        particles.setFactory("PointParticleFactory")
        particles.setRenderer("SpriteParticleRenderer")
        particles.setEmitter("PointEmitter")

        particles.setEmissionType(0)
        particles.setLifespanBase(params.duration)
        particles.setLifespanSpread(0.01)
        particles.setInitialXScale(params.scale * 0.5)
        particles.setInitialYScale(params.scale * 0.5)
        particles.setInitialZScale(params.scale * 0.5)
        particles.setFinalXScale(params.scale * 2.0)
        particles.setFinalYScale(params.scale * 2.0)
        particles.setFinalZScale(params.scale * 2.0)

        particles.setPoolSize(5)
        particles.setBirthRate(0.02)

        emitter = particles.getEmitter()
        emitter.setRadius(0.05)

        eff.addParticles(particles)
        return eff

    def _schedule_effect_cleanup(self, effect: ParticleEffect, delay: float) -> None:
        """Schedule cleanup of a particle effect after a delay."""
        def cleanup(task):
            try:
                effect.disable()
                effect.cleanup()
            except Exception:
                pass
            if effect in self._active_effects:
                self._active_effects.remove(effect)
            return Task.done

        task_name = f"{self._event_prefix}effect_cleanup_{id(effect)}"
        taskMgr.doMethodLater(delay + 0.1, cleanup, task_name)

    def _eject_shell_casing(self) -> None:
        """Eject a shell casing from the weapon."""
        if not self.weapon_data.shell_casing.enabled:
            return

        if self._shell_eject_node is None:
            return

        shell_params = self.weapon_data.shell_casing

        try:
            # Create a simple box for the shell casing (fallback for no Cylinder support)
            geom_node = GeomNode("shell_geom")
            geom_node.addGeom(self._make_box_geom(
                shell_params.scale * 0.6, shell_params.scale * 0.6, shell_params.scale * 1.2
            ))
            shell_np = self._shell_eject_node.attachNewNode(geom_node)
            shell_np.setColor(shell_params.color)
            shell_np.setShaderAuto()

            self._active_shells.append(shell_np)

            def remove_shell(task):
                if shell_np.isEmpty():
                    return Task.done
                shell_np.removeNode()
                if shell_np in self._active_shells:
                    self._active_shells.remove(shell_np)
                return Task.done

            task_name = f"{self._event_prefix}shell_remove_{id(shell_np)}"
            taskMgr.doMethodLater(shell_params.lifetime, remove_shell, task_name)
        except Exception:
            pass

    def _spawn_hit_effects(self, hit: HitResult) -> None:
        """Spawn visual effects at the hit location.

        Args:
            hit: The HitResult describing where the shot hit.
        """
        if not hit.hit:
            return

        effect_color = self._get_hit_effect_color(hit.surface_type)

        try:
            impact_parent = self.render.attachNewNode("impact_effect")
            impact_parent.setPos(hit.hit_position)

            cm = CardMaker("impact_card")
            cm.setFrame(-0.1, 0.1, -0.1, 0.1)
            card = impact_parent.attachNewNode(cm.generate())
            card.setColor(effect_color)
            card.setBillboardAxis()
            card.setShaderAuto()

            seq = Sequence(
                LerpFunc(lambda t: card.setColorScale(effect_color * (1.0 - t)), duration=0.2, fromData=0, toData=1),
                Func(impact_parent.removeNode),
            )
            seq.start()

            # Play hit sound if available
            hit_sound_key = f"hit_{hit.surface_type.value}"
            if hit_sound_key in self._sounds:
                self._sounds[hit_sound_key].setVolume(0.8)
                if hasattr(self._sounds[hit_sound_key], 'play'):
                    self._sounds[hit_sound_key].play()
        except Exception:
            pass

    def _get_hit_effect_color(self, surface_type: SurfaceType) -> Vec4:
        """Return the color for hit effects based on surface type."""
        colors = {
            SurfaceType.FLESH: Vec4(0.8, 0.2, 0.2, 0.8),
            SurfaceType.METAL: Vec4(0.9, 0.9, 0.3, 0.8),
            SurfaceType.WOOD: Vec4(0.6, 0.4, 0.2, 0.8),
            SurfaceType.CONCRETE: Vec4(0.7, 0.7, 0.7, 0.8),
            SurfaceType.GLASS: Vec4(0.8, 0.9, 1.0, 0.7),
            SurfaceType.WATER: Vec4(0.2, 0.4, 0.9, 0.6),
        }
        return colors.get(surface_type, Vec4(0.7, 0.7, 0.7, 0.8))

    # -----------------------------------------------------------------------
    # Private: ADS Animation
    # -----------------------------------------------------------------------

    def _animate_ads(self, target_progress: float, duration: float) -> None:
        """Animate the transition to/from ADS.

        Args:
            target_progress: Target ADS progress (0.0 = hip, 1.0 = fully ADS).
            duration: Duration of the animation in seconds.
        """
        current = self._ads_progress

        def update_ads(t):
            t = max(0.0, min(1.0, t))
            # Smoothstep interpolation
            self._ads_progress = current + (target_progress - current) * (t * t * (3 - 2 * t))

        if duration <= 0:
            self._ads_progress = target_progress
        else:
            lerp = LerpFunc(update_ads, duration=duration, name=f"{self._event_prefix}ads_lerp")
            lerp.start()

    # -----------------------------------------------------------------------
    # Private: Sound System
    # -----------------------------------------------------------------------

    def _load_sounds(self) -> None:
        """Load all sound effects for this weapon."""
        try:
            _loader = getattr(base, 'loader', None)
            if _loader is not None:
                sound_map = {
                    'shot': self.weapon_data.shot_sound,
                    'reload': self.weapon_data.reload_sound,
                    'dry_fire': self.weapon_data.dry_fire_sound,
                }

                for key, path in sound_map.items():
                    if path:
                        try:
                            sound = _loader.loadSfx(path)
                            if sound:
                                self._sounds[key] = sound
                        except Exception:
                            pass

                for surface_type, sound_path in self.weapon_data.hit_sounds.items():
                    key = f"hit_{surface_type.value}"
                    if sound_path:
                        try:
                            sound = _loader.loadSfx(sound_path)
                            if sound:
                                self._sounds[key] = sound
                        except Exception:
                            pass
        except Exception:
            pass

    def _play_sound(self, key: str) -> None:
        """Play a sound by key.

        Args:
            key: The sound key (e.g., 'shot', 'reload', 'dry_fire').
        """
        sound = self._sounds.get(key)
        if sound and hasattr(sound, 'play'):
            sound.setVolume(1.0)
            sound.play()

    def _stop_sound(self, key: str) -> None:
        """Stop a sound by key.

        Args:
            key: The sound key to stop.
        """
        sound = self._sounds.get(key)
        if sound and hasattr(sound, 'stop'):
            sound.stop()

    # -----------------------------------------------------------------------
    # Private: View Model
    # -----------------------------------------------------------------------

    def _build_view_model(self) -> None:
        """Build the procedural weapon view model."""
        if self.view_model is None:
            self.view_model = self.parent_node.attachNewNode(f"weapon_{self.weapon_data.weapon_id}")
        self.view_model.setShaderAuto()

        # Clear existing geometry
        for child in list(self.view_model.getChildren()):
            child.removeNode()

        # Use the weapon's shape to build procedural geometry
        shape = self.weapon_data.model_shape.lower()
        color = self.weapon_data.model_color
        dims = self.weapon_data.model_dimensions  # (width, height, depth)
        w, h, d = dims

        if shape == "box":
            self._build_box_model(self.view_model, w, h, d, color)
        elif shape == "cylinder":
            self._build_cylinder_model(self.view_model, w, d, color)
        elif shape == "barrel":
            self._build_barrel_model(self.view_model, w, h, d, color)
        elif shape == "sphere":
            self._build_sphere_model(self.view_model, w, color)
        else:
            self._build_box_model(self.view_model, w, h, d, color)

        # Set up muzzle attach point
        self._muzzle_attach = self.view_model.attachNewNode("muzzle")
        self._muzzle_attach.setPos(0, d / 2 - 0.05, 0)

        # Set up shell ejection point
        self._shell_eject_node = self.view_model.attachNewNode("eject")
        self._shell_eject_node.setPos(w / 2 + 0.05, d / 2 - 0.2, 0)

        # Position the view model
        self.view_model.setPos(0.3, 0.2, -0.3)

    def _make_box_geom(self, w: float, d: float, h: float) -> Geom:
        """Create a box Geom for simple geometry."""
        fmt = GeomVertexFormat.getV3n3()
        vdata = GeomVertexData("box_geom", fmt, GeomEnums.UH_static)
        vw = GeomVertexWriter(vdata, "vertex")
        nw = GeomVertexWriter(vdata, "normal")

        hw, hd, hh = w / 2, d / 2, h / 2
        verts = [
            (-hw, -hd, -hh), (hw, -hd, -hh), (hw, hd, -hh), (-hw, hd, -hh),
            (-hw, -hd, hh), (hw, -hd, hh), (hw, hd, hh), (-hw, hd, hh),
        ]
        for v in verts:
            vw.addData3f(*v)
            nw.addData3f(0, 0, 1)

        prim = GeomTriangles(GeomEnums.UH_static)
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 4, 7, 3)]
        for a, b, c, d in faces:
            prim.addVertices(a, b, c)
            prim.addVertices(c, d, a)
        prim.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(prim)
        return geom

    def _build_box_model(self, parent: NodePath, w: float, h: float, d: float, color: Vec4) -> None:
        """Build a simple box (rectangular prism) weapon model."""
        fmt = GeomVertexFormat.getV3t1()
        vdata = GeomVertexData("box", fmt, GeomEnums.UH_static)

        vw = GeomVertexWriter(vdata, "vertex")
        tw = GeomVertexWriter(vdata, "texcoord")

        verts = [
            (-w/2, -d/2, -h/2), (w/2, -d/2, -h/2),
            (w/2, d/2, -h/2), (-w/2, d/2, -h/2),
            (-w/2, -d/2, h/2), (w/2, -d/2, h/2),
            (w/2, d/2, h/2), (-w/2, d/2, h/2),
        ]

        for v in verts:
            vw.addData3f(*v)
            tw.addData2f(0, 0)

        faces = [
            (4, 5, 6, 7),   # Front
            (3, 2, 1, 0),   # Back
            (5, 4, 0, 1),   # Right
            (6, 7, 3, 2),   # Left
            (7, 4, 5, 6),   # Top
            (2, 3, 0, 1),   # Bottom
        ]

        geom = Geom(vdata)
        for face_verts in faces:
            prim = GeomTristrips(GeomEnums.UH_static)
            for i in range(4):
                prim.addVertex(face_verts[i])
            for i in range(4):
                prim.addVertex(face_verts[(i + 2) % 4])
            prim.closePrimitive()
            geom.addPrimitive(prim)

        geom_node = GeomNode("box_node")
        geom_node.addGeom(geom)
        box_np = parent.attachNewNode(geom_node)
        box_np.setColor(color)
        box_np.setShaderAuto()

    def _build_cylinder_model(self, parent: NodePath, radius: float, height: float, color: Vec4) -> None:
        """Build a simple cylinder weapon model."""
        try:
            from panda3d.core import Cylinder as CylGeom
            cyl = CylGeom(16, radius, radius, height * 0.9, True)
            geom = cyl.getGeom(0)

            geom_node = GeomNode("cylinder_node")
            geom_node.addGeom(geom)
            cyl_np = parent.attachNewNode(geom_node)
            cyl_np.setColor(color)
            cyl_np.setShaderAuto()
        except Exception:
            # Fallback: use box model
            self._build_box_model(parent, radius * 2, height, radius * 2, color)

    def _build_barrel_model(self, parent: NodePath, w: float, h: float, d: float, color: Vec4) -> None:
        """Build a barrel-style (two cylinders) weapon model."""
        # Body (main receiver)
        body_mat = parent.attachNewNode("body")
        try:
            from panda3d.core import Cylinder as CylGeom
            body_cyl = CylGeom(16, w / 2, w / 2, d * 0.9, True)
            body_geom_node = GeomNode("body_geom")
            body_geom_node.addGeom(body_cyl.getGeom(0))
            body_mat.attachNewNode(body_geom_node)
        except Exception:
            self._build_box_model(body_mat, w, d, d, color)
        body_mat.setColor(color)

        # Barrel (longer, thinner)
        barrel_mat = parent.attachNewNode("barrel")
        try:
            from panda3d.core import Cylinder as CylGeom
            barrel_cyl = CylGeom(12, w / 4, w / 4, h * 0.9, True)
            barrel_geom_node = GeomNode("barrel_geom")
            barrel_geom_node.addGeom(barrel_cyl.getGeom(0))
            barrel_mat.attachNewNode(barrel_geom_node)
        except Exception:
            self._build_box_model(barrel_mat, w / 2, h, w / 2, color)
        barrel_mat.setColor(color * 0.9)

    def _build_sphere_model(self, parent: NodePath, size: float, color: Vec4) -> None:
        """Build a simple sphere weapon model."""
        try:
            from panda3d.core import Sphere
            sphere = Sphere(8, size / 2, True)
            geom = sphere.getGeom(0)

            geom_node = GeomNode("sphere_node")
            geom_node.addGeom(geom)
            sphere_np = parent.attachNewNode(geom_node)
            sphere_np.setColor(color)
            sphere_np.setShaderAuto()
        except Exception:
            # Fallback: use box model
            self._build_box_model(parent, size, size, size, color)

    # -----------------------------------------------------------------------
    # Private: Movement Detection
    # -----------------------------------------------------------------------

    def _is_moving(self) -> bool:
        """Check if the player is currently moving.

        This should be overridden or connected to player state.
        """
        return False

    # -----------------------------------------------------------------------
    # Private: Task Registration
    # -----------------------------------------------------------------------

    def _register_tasks(self) -> None:
        """Register recurring tasks."""
        def update_task(task: Task) -> Task:
            dt = globalClock.getDt()
            self._update(dt)
            return Task.cont

        task_name = f"{self._event_prefix}update"
        self._update_task_name = task_name
        taskMgr.add(update_task, task_name, sort=40)

    # -----------------------------------------------------------------------
    # Private: Update
    # -----------------------------------------------------------------------

    def _update(self, dt: float) -> None:
        """Main update method called every frame.

        Args:
            dt: Delta time in seconds since last frame.
        """
        # Update dry fire timer
        if self._dry_fire_timer > 0:
            self._dry_fire_timer -= dt

        # Update recoil return
        self._update_recoil_return(dt)

        # Update time since last shot
        self._time_since_last_shot += dt

        # Handle auto-fire continuation
        if self.fire_mode == FireMode.AUTO and self.is_trigger_pressed:
            if self.state == WeaponState.FIRING:
                if self._time_since_last_shot >= self.time_between_shots:
                    if self._can_fire():
                        self._fire_single_shot()
                    else:
                        if self.is_ads:
                            self.state = WeaponState.ADS
                        else:
                            self.state = WeaponState.IDLE if self.current_ammo > 0 else WeaponState.EMPTY

        # Update view model position based on ADS
        self._update_view_model_position()

        # Update view model rotation based on recoil
        self._update_view_model_recoil()

    def _update_view_model_position(self) -> None:
        """Update the view model position based on ADS state."""
        if self.view_model:
            offset = self.get_view_offset()
            self.view_model.setPos(0.3 + offset.x * 2, 0.2 + offset.y * 2, -0.3 + offset.z * 2)

    def _update_view_model_recoil(self) -> None:
        """Update the view model rotation based on recoil."""
        if self.view_model:
            if abs(self._camera_yaw_offset) > 0.001 or abs(self._camera_pitch_offset) > 0.001:
                kick_amount = 0.3
                self.view_model.setHpr(
                    self._camera_yaw_offset * -kick_amount,
                    self._camera_pitch_offset * -kick_amount,
                    0
                )
            else:
                self.view_model.setHpr(0, 0, 0)

    # -----------------------------------------------------------------------
    # Private: Effective Accuracy
    # -----------------------------------------------------------------------

    def _effective_accuracy(self) -> float:
        """Calculate the effective accuracy considering ADS state.

        Returns:
            A float from 0.0 to 1.0 representing accuracy.
        """
        if self.is_ads:
            return self.weapon_data.accuracy_ads
        return self.weapon_data.accuracy
