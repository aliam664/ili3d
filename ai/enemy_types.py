"""
SHARIFA Game - Enemy Type Definitions

This module defines eight distinct enemy types, each with unique behaviors,
stats, and visual representations:

    1. StandardInfantry - Basic soldier with assault rifle. Balanced stats.
    2. FastAssault       - Mobile enemy with SMG. High speed, low health.
    3. HeavySoldier      - Armored enemy with high health and damage resistance.
    4. Sniper            - Long-range enemy. High accuracy at distance.
    5. StealthEnemy      - Can cloak and ambush. Vanishes when stationary.
    6. CombatDrone       - Flying enemy with hovering movement and energy weapons.
    7. EliteCommander    - High-tier enemy with advanced tactics and multiple abilities.
    8. ExperimentalCreature - Melee enemy that closes distance rapidly.

Each enemy type inherits from the base Enemy class and overrides:
    - ENEMY_DATA: Static configuration (stats, colors, sizes, etc.)
    - Behavior methods: _update_state, _aim_and_fire, _react_to_damage, etc.
    - Visual model customization (colors, shapes, special effects)

Author: SHARIFA Game Development Team
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, List, Optional, Tuple

from panda3d.core import (
    Vec3,
    Vec4,
    Point3,
    BitMask32,
    CollisionNode,
    CollisionSphere,
    CollisionTube,
    NodePath,
    TransparencyAttrib,
    Geom,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    GeomNode,
    ClockObject,
)

# globalClock is set by ShowBase after initialization.
globalClock = ClockObject.getGlobalClock()
from direct.task.Task import Task
from direct.interval.IntervalGlobal import Sequence, Wait, Func, LerpFunc

from ai.enemy import (
    Enemy,
    EnemyState,
    AlertLevel,
    SoundType,
    EnemyData,
    PatrolPoint,
    CoverPoint,
    AlertEvent,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Standard Infantry
# ---------------------------------------------------------------------------


class StandardInfantry(Enemy):
    """
    Basic infantry soldier with an assault rifle.

    The backbone of enemy forces. Balanced health, accuracy, and movement.
    Uses standard cover-seeking behavior and burst firing patterns.

    Behaviors:
        - Burst firing (3-round bursts) at medium range.
        - Standard cover usage.
        - Calls for reinforcements when damaged.
    """

    ENEMY_DATA = EnemyData(
        name="Standard Infantry",
        health=100.0,
        armor=0.1,  # 10% damage reduction
        move_speed=6.0,
        run_speed=10.0,
        turn_speed=180.0,
        vision_angle=90.0,
        vision_distance=30.0,
        hearing_distance=25.0,
        accuracy=0.75,
        damage=18.0,
        fire_rate=0.15,  # ~400 RPM equivalent (0.15s between bursts)
        attack_range=35.0,
        flee_threshold=0.2,
        call_reinforcements=True,
        reinforcement_radius=30.0,
        color=Vec4(0.8, 0.2, 0.2, 1.0),  # Red
        size=(0.45, 1.8),
        weapon_id="assault_rifle",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._burst_count: int = 3
        self._burst_remaining: int = 0

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override to implement burst firing pattern."""
        self._cooldown_timer -= globalClock.getDt()
        if self._cooldown_timer > 0:
            return

        if self._burst_remaining <= 0:
            # Start a new burst
            self._burst_remaining = self._burst_count

        # Fire a single shot
        self._fire_single_shot(target_pos)
        self._burst_remaining -= 1
        self._cooldown_timer = 0.1  # Short delay between burst shots

        # After burst, set longer cooldown
        if self._burst_remaining <= 0:
            self._cooldown_timer = 1.5  # Longer cooldown between bursts

    def _fire_single_shot(self, target_pos: Point3) -> None:
        """Fire a single shot at the target."""
        predicted = self._predict_target_position(target_pos)

        if self._weapon is not None and hasattr(self._weapon, 'fire'):
            self._weapon.fire()
        elif self.manager and self.manager.player_ref:
            self.manager.apply_damage_to_player(
                self.current_damage,
                self.node.get_pos(),
                predicted,
            )


# ---------------------------------------------------------------------------
# 2. Fast Assault
# ---------------------------------------------------------------------------


class FastAssault(Enemy):
    """
    Highly mobile enemy equipped with an SMG.

    FastAssault enemies prioritize mobility over survivability.
    They strafe and retreat while firing, making them hard to hit.

    Behaviors:
        - Strafing while firing.
        - Retreats when health is low (more prone to fleeing).
        - Higher movement speed but lower health.
    """

    ENEMY_DATA = EnemyData(
        name="Fast Assault",
        health=60.0,
        armor=0.0,
        move_speed=12.0,
        run_speed=20.0,
        turn_speed=250.0,
        vision_angle=100.0,
        vision_distance=25.0,
        hearing_distance=30.0,
        accuracy=0.65,
        damage=12.0,
        fire_rate=0.08,  # High fire rate
        attack_range=20.0,
        flee_threshold=0.35,
        call_reinforcements=True,
        reinforcement_radius=25.0,
        color=Vec4(0.9, 0.7, 0.2, 1.0),  # Yellow
        size=(0.4, 1.7),
        weapon_id="smg",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._strafe_direction: int = 1
        self._strafe_timer: float = 0.0

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override to implement strafing while firing."""
        self._cooldown_timer -= globalClock.getDt()
        if self._cooldown_timer > 0:
            return

        # Strafe movement
        self._strafe_timer += globalClock.getDt()
        if self._strafe_timer > 2.0:
            self._strafe_direction *= -1
            self._strafe_timer = 0.0

        # Apply strafe offset
        strafe_amount = self._strafe_direction * 0.5
        self.velocity.x += strafe_amount

        # Fire
        if self._weapon is not None and hasattr(self._weapon, 'fire'):
            self._weapon.fire()
        elif self.manager and self.manager.player_ref:
            self.manager.apply_damage_to_player(
                self.current_damage,
                self.node.get_pos(),
                target_pos,
            )

        self._cooldown_timer = 1.0 / self.fire_rate

    def _move_toward_point(self, target: Vec3, dt: float) -> None:
        """Override to add strafing behavior."""
        super()._move_toward_point(target, dt)

        # Add random strafe when in combat
        if self.state == EnemyState.ATTACK:
            self._strafe_timer += dt
            if self._strafe_timer > random.uniform(1.0, 3.0):
                self._strafe_direction *= -1
                self._strafe_timer = 0.0

            offset = self._strafe_direction * self.move_speed * 0.3 * dt
            current_pos = self.node.get_pos()
            current_pos.x += offset
            # Use node relative movement
            self.node.set_x(self.node.get_x() + self._strafe_direction * self.move_speed * 0.3 * dt)


# ---------------------------------------------------------------------------
# 3. Heavy Soldier
# ---------------------------------------------------------------------------


class HeavySoldier(Enemy):
    """
    Heavily armored enemy with a large health pool and high damage resistance.

    HeavySoldiers are slow but extremely durable. They use a heavy machine
    gun or rocket launcher and rarely flee.

    Behaviors:
        - High armor reduces all incoming damage.
        - Suppressive fire that keeps players pinned down.
        - Rarely flees due to high health.
        - Takes longer to aim but hits harder.
    """

    ENEMY_DATA = EnemyData(
        name="Heavy Soldier",
        health=300.0,
        armor=0.4,  # 40% damage reduction
        move_speed=3.0,
        run_speed=5.0,
        turn_speed=120.0,
        vision_angle=120.0,
        vision_distance=40.0,
        hearing_distance=35.0,
        accuracy=0.85,
        damage=35.0,
        fire_rate=0.2,  # Slower fire
        attack_range=50.0,
        flee_threshold=0.1,  # Very reluctant to flee
        call_reinforcements=True,
        reinforcement_radius=40.0,
        color=Vec4(0.2, 0.2, 0.8, 1.0),  # Blue
        size=(0.6, 1.9),
        weapon_id="heavy_rifle",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._suppression_mode: bool = False

    def take_damage(self, damage: float, source: Vec3 = None) -> None:
        """Override to reduce damage further and enable suppression mode."""
        # Heavy armor: significant damage reduction
        effective_damage = damage * (1.0 - self.armor)
        # Additional flat reduction
        effective_damage = max(1.0, effective_damage - 5.0)

        self.health -= effective_damage
        self._suppression_level = min(1.0, self._suppression_level + (effective_damage / 100.0))

        if self.health <= 0:
            self._die(source)
        else:
            self._react_to_damage(source)

        # Suppression mode when heavily damaged
        if self.health / self.max_health < 0.4 and not self._suppression_mode:
            self._suppression_mode = True
            self._enter_suppression_state()

    def _enter_suppression_state(self) -> None:
        """Enter suppressive fire mode - fires continuously while stationary."""
        self._suppression_mode = True
        self.stop_movement()

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override for suppressive firing pattern."""
        self._cooldown_timer -= globalClock.getDt()
        if self._cooldown_timer > 0:
            return

        # Heavy soldiers fire slower but with more damage
        if self._weapon is not None and hasattr(self._weapon, 'fire'):
            self._weapon.fire()
        elif self.manager and self.manager.player_ref:
            self.manager.apply_damage_to_player(
                self.current_damage,
                self.node.get_pos(),
                target_pos,
            )

        # Suppression effect on hit
        if self.manager and self.manager.player_ref:
            self.manager.player_ref  # Apply suppression to player if system supports it

        self._cooldown_timer = 1.0 / self.fire_rate

    def _react_to_damage(self, source: Vec3) -> None:
        """Heavies don't retreat easily - they push toward the player."""
        if source is not None:
            self._last_seen_player_pos = source
            self._target_position = source

        # Stand ground, don't flee
        self._suppression_level = min(1.0, self._suppression_level + 0.1)


# ---------------------------------------------------------------------------
# 4. Sniper
# ---------------------------------------------------------------------------


class Sniper(Enemy):
    """
    Long-range enemy with high accuracy and deadly headshot capability.

    Snipers stay at maximum range, use cover, and fire single precise shots.
    They are vulnerable at close range but devastating from distance.

    Behaviors:
        - Prefers maximum engagement distance.
        - Uses cover extensively.
        - Charges shots for higher damage.
        - Retreats when player gets too close.
    """

    ENEMY_DATA = EnemyData(
        name="Sniper",
        health=80.0,
        armor=0.15,
        move_speed=4.0,
        run_speed=7.0,
        turn_speed=150.0,
        vision_angle=60.0,  # Narrow FOV
        vision_distance=80.0,  # Long range
        hearing_distance=30.0,
        accuracy=0.95,
        damage=75.0,
        fire_rate=0.5,  # Slow fire rate (charging)
        attack_range=70.0,
        flee_threshold=0.3,
        call_reinforcements=False,  # Snipers fight alone
        color=Vec4(0.3, 0.3, 0.8, 1.0),  # Light blue
        size=(0.4, 1.8),
        weapon_id="sniper_rifle",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._charge_timer: float = 0.0
        self._min_charge_time: float = 1.0  # Time to fully charge
        self._charged_shot: bool = False

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override for charged sniper shots."""
        self._cooldown_timer -= globalClock.getDt()
        if self._cooldown_timer > 0:
            # Charging
            self._charge_timer += globalClock.getDt()
            if self._charge_timer >= self._min_charge_time:
                self._charged_shot = True
            return

        # Ensure minimum charge time
        if self._charge_timer < self._min_charge_time:
            self._charge_timer += globalClock.getDt()
            return

        # Fire charged shot
        damage_multiplier = 1.0
        if self._charged_shot:
            damage_multiplier = 2.0  # Headshot-like bonus
            self._charged_shot = False

        # High accuracy at long range
        effective_accuracy = self.current_accuracy
        distance = self.node.get_pos().distance(target_pos)
        if distance > 40:
            effective_accuracy *= 1.2  # Better at long range
        else:
            effective_accuracy *= 0.5  # Worse at close range

        # Fire
        if self._weapon is not None and hasattr(self._weapon, 'fire'):
            self._weapon.fire()
        elif self.manager and self.manager.player_ref:
            self.manager.apply_damage_to_player(
                self.current_damage * damage_multiplier,
                self.node.get_pos(),
                target_pos,
            )

        self._charge_timer = 0.0
        self._cooldown_timer = 1.0  # Slow between shots

    def _move_toward_point(self, target: Vec3, dt: float) -> None:
        """Override to maintain distance from player."""
        player_pos = self._get_player_position()
        if player_pos is not None:
            dist = self.node.get_pos().distance(player_pos)

            # If too close, retreat
            if dist < self.attack_range * 0.5:
                # Move away
                away_dir = (self.node.get_pos() - player_pos).normalized()
                self._target_position = self.node.get_pos() + away_dir * 15.0
            # If too far, advance slightly
            elif dist > self.attack_range:
                self._target_position = player_pos
            # Otherwise hold position (use cover)
            else:
                self._target_position = self.node.get_pos()

        super()._move_toward_point(target, dt)


# ---------------------------------------------------------------------------
# 5. Stealth Enemy
# ---------------------------------------------------------------------------


class StealthEnemy(Enemy):
    """
    Enemy capable of cloaking and executing ambushes.

    StealthEnemies vanish when stationary for a period, then reappear
    to attack the player from unexpected angles.

    Behaviors:
        - Cloaks (becomes invisible) when not moving.
        - Reappears with a surprise attack when near the player.
        - Higher accuracy on first shot after uncloaking.
        - Cannot be detected by vision while cloaked (only by proximity).
    """

    ENEMY_DATA = EnemyData(
        name="Stealth Enemy",
        health=70.0,
        armor=0.05,
        move_speed=8.0,
        run_speed=15.0,
        turn_speed=300.0,
        vision_angle=80.0,
        vision_distance=20.0,
        hearing_distance=15.0,
        accuracy=0.9,
        damage=40.0,
        fire_rate=0.1,
        attack_range=15.0,
        flee_threshold=0.2,
        call_reinforcements=False,
        color=Vec4(0.3, 0.8, 0.3, 0.3),  # Semi-transparent green
        size=(0.35, 1.7),
        weapon_id="silenced_pistol",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_cloaked: bool = False
        self._cloak_timer: float = 0.0
        self._cloak_delay: float = 2.0  # Time to wait before cloaking
        self._ambush_bonus: float = 1.0

    def _build_visual_model(self) -> None:
        """Override to create a stealth-specific visual model."""
        super()._build_visual_model()
        # Start cloaked when patrolling
        self._set_cloaked(True)

    def _set_cloaked(self, cloaked: bool) -> None:
        """Toggle the cloaking visual effect."""
        self._is_cloaked = cloaked

        if self._body_node is not None:
            if cloaked:
                self._body_node.set_color(Vec4(0.3, 0.8, 0.3, 0.1))  # Nearly transparent
                self._body_node.set_transparency(TransparencyAttrib.M_alpha)
                if self._direction_indicator:
                    self._direction_indicator.hide()
            else:
                # Flickering effect on reveal
                self._body_node.set_color(self.enemy_data.color)
                self._body_node.set_transparency(TransparencyAttrib.M_none)
                if self._direction_indicator:
                    self._direction_indicator.show()

    def _update_state(self, dt: float, clock: float) -> None:
        """Override to handle cloaking logic."""
        # Check if we should cloak or uncloak
        if self.state == EnemyState.PATROL:
            speed = self.velocity.length() if hasattr(self, '_velocity_len') else 0
            actual_speed = self.node.get_pos().distance(getattr(self, '_last_pos', self.node.get_pos()))
            if actual_speed < 0.01:
                self._cloak_timer += dt
                if self._cloak_timer > self._cloak_delay and not self._is_cloaked:
                    self._set_cloaked(True)
            else:
                self._cloak_timer = 0.0
                if self._is_cloaked:
                    self._set_cloaked(False)
            self._last_pos = self.node.get_pos()
        else:
            # Uncloak when entering combat
            if self._is_cloaked:
                self._set_cloaked(False)
                self._ambush_bonus = 2.0  # Bonus damage on reveal

        super()._update_state(dt, clock)

    def _check_vision(self, target_pos: Point3) -> bool:
        """Override - cloaked enemies can't detect via vision."""
        if self._is_cloaked:
            return False
        return super()._check_vision(target_pos)

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override for ambush attack with bonus damage."""
        # Apply ambush bonus
        original_damage = self.current_damage
        self.current_damage = original_damage * self._ambush_bonus
        self._ambush_bonus = 1.0  # Reset bonus

        super()._aim_and_fire(target_pos)

        # Restore original damage
        self.current_damage = original_damage

    def _react_to_damage(self, source: Vec3) -> None:
        """Uncloak when taking damage."""
        if self._is_cloaked:
            self._set_cloaked(False)
        super()._react_to_damage(source)


# ---------------------------------------------------------------------------
# 6. Combat Drone
# ---------------------------------------------------------------------------


class CombatDrone(Enemy):
    """
    Flying enemy that hovers and uses energy weapons.

    CombatDrones fly above the battlefield, strafing and firing
    energy projectiles. They can't use cover but are hard to hit
    due to their mobility.

    Behaviors:
        - Hovering flight with smooth movement.
        - Strafing runs across the battlefield.
        - Energy weapons with beam attacks.
        - Cannot use cover - always exposed.
    """

    ENEMY_DATA = EnemyData(
        name="Combat Drone",
        health=120.0,
        armor=0.1,
        move_speed=10.0,
        run_speed=18.0,
        turn_speed=200.0,
        vision_angle=120.0,
        vision_distance=50.0,
        hearing_distance=40.0,
        accuracy=0.8,
        damage=25.0,
        fire_rate=0.1,
        attack_range=40.0,
        flee_threshold=0.2,
        call_reinforcements=False,
        color=Vec4(0.8, 0.8, 0.2, 1.0),  # Gold/yellow
        size=(0.5, 0.5),  # Compact hovering unit
        weapon_id="energy_rifle",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hover_height: float = 5.0
        self._hover_offset: float = 0.0
        self._strafe_target: Vec3 = Vec3(0, 0, 0)

    def _setup_collisions(self) -> None:
        """Override for flying collision - use a sphere instead of ground-based."""
        cnode = CollisionNode(f"enemy_{self.id}_collider")
        csphere = CollisionSphere(0, 0, 0, self.enemy_data.size[0])
        cnode.add_solid(csphere)
        cnode.set_from_collide_mask(Constants.MASK_ENEMY)
        cnode.set_into_collide_mask(Constants.MASK_ENEMY)

        self._collision_node = self.node.attach_new_node(cnode)
        self._collision_node.set_python_tag("enemy_ref", self)

    def _build_visual_model(self) -> None:
        """Override to create a drone-specific visual model."""
        radius, height = self.enemy_data.size
        color = self.enemy_data.color

        self._visual_root = self.node.attach_new_node("visual")

        # Body: sphere
        from panda3d.core import Sphere, GeomNode as GN

        sphere_geom_node = self._make_uv_sphere(radius=radius, segments=12)
        body = self._visual_root.attach_new_node(sphere_geom_node)
        body.set_color(color)
        body.set_shader_auto()

        # Propellers/rotors (quads on top)
        from panda3d.core import CardMaker
        rotor_node = self._visual_root.attach_new_node("rotors")
        for i in range(4):
            rotor = rotor_node.attach_new_node(f"rotor_{i}")
            rotor.set_pos(radius * math.cos(i * math.pi / 2), radius * math.sin(i * math.pi / 2), radius)
            cm = CardMaker(f"rotor_card_{i}")
            cm.set_frame(-radius * 0.5, radius * 0.5, -0.1, 0.1)
            rotor_card = rotor.attach_new_node(cm.generate())
            rotor_card.set_color(Vec4(0.5, 0.5, 0.5, 0.7))
            rotor_card.set_transparency(TransparencyAttrib.M_alpha)

        # Direction indicator: cone pointing forward
        self._direction_indicator = self.node.attach_new_node("direction")
        tri_vdata = GeomVertexData("arrow", GeomVertexFormat.get_v3t2(), Geom.UH_static)
        tri_vertex = GeomVertexWriter(tri_vdata, "vertex")
        tri_texcoord = GeomVertexWriter(tri_vdata, "texcoord")

        arrow_len = radius * 3
        tri_vertex.add_data3f(0, arrow_len, 0)
        tri_vertex.add_data3f(-radius, 0, 0)
        tri_vertex.add_data3f(radius, 0, 0)
        tri_texcoord.add_data2f(1, 0)
        tri_texcoord.add_data2f(0, 1)
        tri_texcoord.add_data2f(1, 1)

        tri_vertex.add_data3f(0, arrow_len, 0)
        tri_vertex.add_data3f(radius, 0, 0)
        tri_vertex.add_data3f(0, -radius, 0)
        tri_texcoord.add_data2f(1, 0)
        tri_texcoord.add_data2f(1, 1)
        tri_texcoord.add_data2f(0.5, 0.5)

        tri_vertex.add_data3f(0, arrow_len, 0)
        tri_vertex.add_data3f(0, -radius, 0)
        tri_vertex.add_data3f(-radius, 0, 0)
        tri_texcoord.add_data2f(1, 0)
        tri_texcoord.add_data2f(0.5, 0.5)
        tri_texcoord.add_data2f(0, 1)

        tri_prim = GeomTriangle(Geom.UH_static)
        tri_prim.add_vertices(0, 1, 2)
        tri_prim.add_vertices(3, 4, 5)
        tri_prim.add_vertices(6, 7, 8)
        tri_prim.close_primitive()

        arrow_geom = Geom(tri_vdata)
        arrow_geom.add_primitive(tri_prim)
        arrow_node = GeomNode("arrow")
        arrow_node.add_geom(arrow_geom)
        arrow_np = self._direction_indicator.attach_new_node(arrow_node)
        arrow_np.set_color(Vec4(1, 1, 0, 1))  # Yellow
        arrow_np.set_shader_auto()

    def _move_toward_point(self, target: Vec3, dt: float) -> None:
        """Override for flying movement with hover."""
        # Apply hovering motion
        self._hover_offset += dt * 2.0
        bob = math.sin(self._hover_offset) * 0.3

        # Maintain hover height above ground
        ground_z = self._get_ground_height()
        target_z = ground_z + self._hover_height + bob
        self.node.set_z(self.node.get_z() + (target_z - self.node.get_z()) * 0.1)

        # Strafing movement
        super()._move_toward_point(target, dt)

        # Rotate around Z for drone-like orientation
        if self.velocity.length() > 0.1:
            self.node.set_h(self.node.get_h() + 180 * dt)

    def _get_ground_height(self) -> float:
        """Get the ground height below the drone."""
        # Simple raycast down
        pos = self.node.get_pos()
        return pos.z  # Simplified - assume flat ground at z=0

    def _clamp_to_ground(self, pos: Vec3) -> None:
        """Override - drones don't clamp to ground."""
        # Maintain position, don't snap to ground
        pass

    def _seek_cover(self, threat_pos: Point3) -> None:
        """Drones don't use cover."""
        pass

    def _update_animation(self, dt: float) -> None:
        """Override for rotor animation."""
        if self._is_ragdoll:
            return

        # Spin rotors
        if self._visual_root:
            rotor_node = self._visual_root.find("rotors")
            if not rotor_node.is_empty():
                rotor_node.set_h(rotor_node.get_h() + 360 * dt * 3)

        # Hover bounce
        if self._direction_indicator:
            bob = math.sin(self._hover_offset) * 0.05
            self._direction_indicator.set_z(bob)

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override for energy beam attack."""
        self._cooldown_timer -= globalClock.getDt()
        if self._cooldown_timer > 0:
            return

        # Beam attack
        if self._weapon is not None and hasattr(self._weapon, 'fire'):
            self._weapon.fire()
        elif self.manager and self.manager.player_ref:
            # Energy beam - instant hit
            self.manager.apply_damage_to_player(
                self.current_damage,
                self.node.get_pos(),
                target_pos,
            )

        self._cooldown_timer = 1.0 / self.fire_rate


# ---------------------------------------------------------------------------
# 7. Elite Commander
# ---------------------------------------------------------------------------


class EliteCommander(Enemy):
    """
    High-tier enemy commander with advanced tactical abilities.

    EliteCommanders coordinate squad movements, call for reinforcements,
    and employ diverse combat tactics including grenade throwing,
    suppressive fire, and tactical retreats.

    Behaviors:
        - Coordinates nearby squad members.
        - Throwsgrenades at clustered positions.
        - Enters a powered exosuit phase with increased stats.
        - Uses advanced cover tactics.
    """

    ENEMY_DATA = EnemyData(
        name="Elite Commander",
        health=250.0,
        armor=0.3,
        move_speed=7.0,
        run_speed=12.0,
        turn_speed=200.0,
        vision_angle=110.0,
        vision_distance=50.0,
        hearing_distance=45.0,
        accuracy=0.9,
        damage=40.0,
        fire_rate=0.12,
        attack_range=45.0,
        flee_threshold=0.15,
        call_reinforcements=True,
        reinforcement_radius=50.0,
        color=Vec4(0.8, 0.2, 0.8, 1.0),  # Purple
        size=(0.5, 2.0),
        weapon_id="assault_rifle",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ability_cooldown: float = 0.0
        self._exosuit_active: bool = False
        self._command_radius: float = 30.0

    def _update_attack(self, dt: float, clock: float) -> None:
        """Override for advanced tactics."""
        player_pos = self._get_player_position()
        if player_pos is None:
            return

        # Coordinate with nearby squad members
        self._coordinate_squad(player_pos)

        # Use abilities periodically
        self._ability_cooldown -= dt
        if self._ability_cooldown <= 0:
            self._use_ability(player_pos)
            self._ability_cooldown = random.uniform(5.0, 15.0)

        # Grenade throwing
        if self._grenade_cooldown <= 0:
            dist_to_player = self.node.get_pos().distance(player_pos)
            if 10.0 < dist_to_player < 25.0 and random.random() < 0.15:
                self._throw_grenade(player_pos)
                self._grenade_cooldown = 8.0

        # Standard attack behavior
        super()._update_attack(dt, clock)

    def _coordinate_squad(self, player_pos: Vec3) -> None:
        """Broadcast tactical commands to nearby squad members."""
        if not self.squad:
            return

        for enemy in self.squad.enemies:
            if enemy is self or enemy.state == EnemyState.DEAD:
                continue

            # Nearby enemies get suppression bonus
            dist = enemy.node.get_pos().distance(self.node.get_pos())
            if dist <= self._command_radius:
                enemy.apply_suppression(0.2)

    def _use_ability(self, player_pos: Vec3) -> None:
        """Use a tactical ability."""
        ability = random.choice(["grenade", "suppression", "flank", "retreat"])

        if ability == "grenade":
            dist = self.node.get_pos().distance(player_pos)
            if 8.0 < dist < 25.0:
                self._throw_grenade(player_pos)
                self._grenade_cooldown = 10.0
        elif ability == "suppression":
            # Suppress player position
            if self.manager and self.manager.player_ref:
                self.manager.on_sound_event(
                    player_pos, SoundType.GUNFIRE, radius=15.0
                )
        elif ability == "flank":
            if self.squad:
                flank_pos = self.squad.coordinate_flanking(self, player_pos)
                if flank_pos:
                    self._target_position = flank_pos
        elif ability == "retreat":
            # Tactical repositioning
            if not self._current_cover:
                self._seek_cover(player_pos)

    def _enter_suppression_state(self) -> None:
        """Override: elite commanders don't enter suppression - they push through."""
        # Exosuit activation when at low health
        if self.health / self.max_health < 0.3 and not self._exosuit_active:
            self._activate_exosuit()

    def _activate_exosuit(self) -> None:
        """Activate powered exosuit for a stat boost."""
        self._exosuit_active = True

        # Stat boosts
        original_health = self.max_health
        self.max_health *= 1.5
        self.health = min(self.max_health, self.health + original_health * 0.5)
        self.armor = min(0.6, self.armor + 0.2)
        self.move_speed *= 1.2
        self.current_damage *= 1.3
        self.current_accuracy = min(1.0, self.current_accuracy + 0.1)

        # Visual change
        if self._body_node:
            self._body_node.set_color(Vec4(1.0, 0.4, 0.0, 1.0))  # Orange glow

        # Alert nearby enemies
        if self.squad:
            self.squad.broadcast_alert(
                self, self.node.get_pos(), AlertLevel.COMBAT
            )

        logger.info("Elite Commander %d activated exosuit!", self.id)

    def _build_visual_model(self) -> None:
        """Override for commander visual - larger with armor plating."""
        super()._build_visual_model()

        # Add shoulder armor detail
        if self._visual_root:
            from panda3d.core import CardMaker
            for side in [-1, 1]:
                shoulder = self._visual_root.attach_new_node("shoulder")
                cm = CardMaker("shoulder_plate")
                cm.set_frame(-0.4, 0.4, -0.3, 0.3)
                plate = shoulder.attach_new_node(cm.generate())
                plate.set_color(Vec4(0.7, 0.7, 0.7, 1.0))
                plate.set_shader_auto()
                shoulder.set_x(side * (self.enemy_data.size[0] + 0.1))
                shoulder.set_z(self.enemy_data.size[1] * 0.7)


# ---------------------------------------------------------------------------
# 8. Experimental Creature
# ---------------------------------------------------------------------------


class ExperimentalCreature(Enemy):
    """
    Melee enemy with high mobility and rapid closing ability.

    These creatures are fast, aggressive, and deal high damage at close range.
    They cannot be effectively countered at range and must be dealt with
    quickly.

    Behaviors:
        - Rapid movement toward the player.
        - High damage melee attacks.
        - Cannot be hit by most ranged weapons while sprinting.
        - Berserk mode when health is low.
    """

    ENEMY_DATA = EnemyData(
        name="Experimental Creature",
        health=150.0,
        armor=0.2,
        move_speed=10.0,
        run_speed=25.0,
        turn_speed=360.0,
        vision_angle=150.0,
        vision_distance=20.0,
        hearing_distance=35.0,
        accuracy=1.0,  # Always hits in melee
        damage=30.0,
        fire_rate=1.0,  # Melee - instant attack
        attack_range=3.0,
        flee_threshold=0.1,
        call_reinforcements=False,
        color=Vec4(0.8, 0.2, 0.8, 1.0),  # Purple/violet
        size=(0.4, 1.5),
        weapon_id="",  # No ranged weapon
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._berserk: bool = False
        self._berserk_timer: float = 0.0

    def _update_state(self, dt: float, clock: float) -> None:
        """Override for berserk behavior."""
        # Check berserk activation
        health_pct = self.health / self.max_health
        if health_pct < 0.4 and not self._berserk:
            self._berserk = True
            self._berserk_timer = 10.0
            self.move_speed *= 1.5
            self.run_speed *= 1.5
            self.current_damage *= 1.5

            # Visual effect
            if self._body_node:
                self._body_node.set_color(Vec4(1.0, 0.1, 0.1, 1.0))

        # Update berserk timer
        if self._berserk:
            self._berserk_timer -= dt
            if self._berserk_timer <= 0:
                self._berserk = False
                self._berserk_timer = 0.0
                # Reset stats
                self.move_speed = self.enemy_data.move_speed
                self.run_speed = self.enemy_data.run_speed
                self.current_damage = self.enemy_data.damage
                if self._body_node:
                    self._body_node.set_color(self.enemy_data.color)

        super()._update_state(dt, clock)

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override for melee attack."""
        # Melee attack - check range
        dist = self.node.get_pos().distance(target_pos)
        if dist <= self._melee_range:
            # Melee hit
            if self.manager and self.manager.player_ref:
                self.manager.apply_damage_to_player(
                    self._melee_damage,
                    self.node.get_pos(),
                    target_pos,
                )
        else:
            # Move closer
            self._target_position = target_pos

    def _move_toward_point(self, target: Vec3, dt: float) -> None:
        """Override for aggressive closing behavior."""
        # Always move at run speed
        original_move = self.move_speed
        original_run = self.run_speed
        self.move_speed = self.run_speed
        super()._move_toward_point(target, dt)
        self.move_speed = original_move
        self.run_speed = original_run

    def _update_animation(self, dt: float) -> None:
        """Override for creature-like movement."""
        if self._is_ragdoll:
            return

        # Undulating movement for creature-like feel
        if self.velocity.length() > 0.1:
            scale = 1.0 + math.sin(globalClock.getFrameTime() * 10) * 0.05
            if self._visual_root:
                self._visual_root.set_scale(scale)

    def _build_visual_model(self) -> None:
        """Override for creature-like appearance - elongated, organic shape."""
        radius, height = self.enemy_data.size
        color = self.enemy_data.color

        self._visual_root = self.node.attach_new_node("visual")

        # Oval body instead of capsule
        from panda3d.core import GeomNode as GN

        sphere_node = self._make_uv_sphere(radius=radius, segments=12)
        body = self._visual_root.attach_new_node(sphere_node)
        body.set_color(color)
        body.set_shader_auto()
        body.set_scale(1.0, 1.0, 1.5)  # Elongated vertically
        body.set_z(height * 0.3)

        # Multiple eye clusters (glow effect)
        for eye_idx in range(2):
            eye = self._visual_root.attach_new_node(f"eye_{eye_idx}")
            eye.set_pos(
                (eye_idx - 0.5) * radius * 0.8,
                radius * 0.8,
                height * 0.4,
            )
            from panda3d.core import CardMaker
            cm = CardMaker(f"eye_{eye_idx}")
            cm.set_frame(-0.1, 0.1, -0.1, 0.1)
            eye_card = eye.attach_new_node(cm.generate())
            eye_card.set_color(Vec4(1.0, 0.0, 0.0, 0.8))  # Red glow
            eye_card.set_billboard_axis()
            eye_card.set_transparency(TransparencyAttrib.M_alpha)

        # Direction indicator: elongated spike
        self._direction_indicator = self.node.attach_new_node("direction")

        tri_vdata = GeomVertexData("spike", GeomVertexFormat.get_v3t2(), Geom.UH_static)
        tri_vertex = GeomVertexWriter(tri_vdata, "vertex")
        tri_texcoord = GeomVertexWriter(tri_vdata, "texcoord")

        spike_len = radius * 3
        tri_vertex.add_data3f(0, spike_len, height * 0.3)
        tri_vertex.add_data3f(-radius * 0.5, 0, height * 0.3)
        tri_vertex.add_data3f(radius * 0.5, 0, height * 0.3)
        tri_texcoord.add_data2f(1, 0)
        tri_texcoord.add_data2f(0, 1)
        tri_texcoord.add_data2f(1, 1)

        tri_vertex.add_data3f(0, spike_len, height * 0.3)
        tri_vertex.add_data3f(radius * 0.5, 0, height * 0.3)
        tri_vertex.add_data3f(0, 0, height * 0.15)
        tri_texcoord.add_data2f(1, 0)
        tri_texcoord.add_data2f(1, 1)
        tri_texcoord.add_data2f(0.5, 0.5)

        tri_vertex.add_data3f(0, spike_len, height * 0.3)
        tri_vertex.add_data3f(0, 0, height * 0.15)
        tri_vertex.add_data3f(-radius * 0.5, 0, height * 0.3)
        tri_texcoord.add_data2f(1, 0)
        tri_texcoord.add_data2f(0.5, 0.5)
        tri_texcoord.add_data2f(0, 1)

        tri_prim = GeomTriangle(Geom.UH_static)
        tri_prim.add_vertices(0, 1, 2)
        tri_prim.add_vertices(3, 4, 5)
        tri_prim.add_vertices(6, 7, 8)
        tri_prim.close_primitive()

        spike_geom = Geom(tri_vdata)
        spike_geom.add_primitive(tri_prim)
        spike_node = GN("spike")
        spike_node.add_geom(spike_geom)
        spike_np = self._direction_indicator.attach_new_node(spike_node)
        spike_np.set_color(Vec4(0.8, 0.2, 0.8, 1.0))
        spike_np.set_shader_auto()

    def _enter_state(self, new_state: EnemyState) -> None:
        """Override to enable/disable melee mode."""
        super()._enter_state(new_state)

        if new_state == EnemyState.ATTACK:
            # Melee enemies don't use ranged weapons
            self._weapon = None

    def take_damage(self, damage: float, source: Vec3 = None) -> None:
        """Override for sprinting-immune behavior."""
        # When berserk or at low health, take reduced damage from ranged attacks
        if self._berserk:
            # 30% damage resistance while berserk
            damage *= 0.7

        super().take_damage(damage, source)


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def create_enemy_by_type(
    enemy_type_name: str,
    *args,
    **kwargs,
) -> Enemy:
    """
    Factory function to create an enemy by its type name.

    Args:
        enemy_type_name: String name of the enemy type (e.g., "StandardInfantry").
        *args, **kwargs: Arguments passed to the enemy constructor.

    Returns:
        An instance of the requested enemy type.

    Raises:
        ValueError: If the enemy type name is not recognized.
    """
    type_map = {
        "StandardInfantry": StandardInfantry,
        "FastAssault": FastAssault,
        "HeavySoldier": HeavySoldier,
        "Sniper": Sniper,
        "StealthEnemy": StealthEnemy,
        "CombatDrone": CombatDrone,
        "EliteCommander": EliteCommander,
        "ExperimentalCreature": ExperimentalCreature,
    }

    enemy_class = type_map.get(enemy_type_name)
    if enemy_class is None:
        raise ValueError(f"Unknown enemy type: '{enemy_type_name}'. Valid types: {list(type_map.keys())}")

    return enemy_class(*args, **kwargs)


def get_all_enemy_types() -> Dict[str, type]:
    """Return a dictionary mapping enemy type names to their classes."""
    return {
        "StandardInfantry": StandardInfantry,
        "FastAssault": FastAssault,
        "HeavySoldier": HeavySoldier,
        "Sniper": Sniper,
        "StealthEnemy": StealthEnemy,
        "CombatDrone": CombatDrone,
        "EliteCommander": EliteCommander,
        "ExperimentalCreature": ExperimentalCreature,
    }


__all__ = [
    "StandardInfantry",
    "FastAssault",
    "HeavySoldier",
    "Sniper",
    "StealthEnemy",
    "CombatDrone",
    "EliteCommander",
    "ExperimentalCreature",
    "create_enemy_by_type",
    "get_all_enemy_types",
]
