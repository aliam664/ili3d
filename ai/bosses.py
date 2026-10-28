"""
SHARIFA Game - Boss Enemy Classes

This module implements six multi-phase boss enemies, each tied to a specific
game world and featuring unique mechanics, phase transitions, and visual
representations:

    1. CyberneticOverlord  - Cyberpunk City final boss. Tech shield + drones.
    2. WarBeast            - Post-Apocalyptic boss. Berserk melee + area stomps.
    3. SecurityCore        - Military Facility boss. Turret defense + lockdown.
    4. Guardian            - Arctic Base boss. Ice manipulation + frozen arena.
    5. Xenomorph           - Space Station boss. Acid blood + wall crawling.
    6. NightmareLord       - Fantasy boss. Shadow clones + teleportation.

Each boss inherits from the base Boss class, which extends Enemy with:
    - Multi-phase health system
    - Phase-specific behavior overrides
    - Enrage timers and phase transitions
    - Unique special abilities per phase
    - Visual transformation effects

Author: SHARIFA Game Development Team
"""

from __future__ import annotations

import logging
import math
import random
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple

from panda3d.core import (
    Vec3,
    Vec4,
    Point3,
    BitMask32,
    CollisionNode,
    CollisionSphere,
    CollisionInvSphere,
    CollisionTube,
    NodePath,
    TransparencyAttrib,
    Geom,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    GeomNode,
    CardMaker,
    TextNode,
    ClockObject,
)

# globalClock is set by ShowBase after initialization.
globalClock = ClockObject.getGlobalClock()
from direct.task.Task import Task
from direct.interval.IntervalGlobal import (
    Sequence, Parallel, Wait, Func, LerpFunc, LerpPosInterval,
    LerpScaleInterval, LerpColorScaleInterval,
)

from ai.enemy import (
    Enemy,
    EnemyState,
    AlertLevel,
    SoundType,
    EnemyData,
    PatrolPoint,
    CoverPoint,
    EnemyManager,
    SquadManager,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Boss Phase Enumeration
# ---------------------------------------------------------------------------


class BossPhase(IntEnum):
    """
    Phases of a boss fight.

    PHASE_1   - Opening phase with basic attacks.
    PHASE_2   - Second phase, typically triggered at 66% health.
    PHASE_3   - Final phase at 33% health, significantly more aggressive.
    ENRAGE    - Final desperation phase when health is critical.
    """

    PHASE_1 = 0
    PHASE_2 = 1
    PHASE_3 = 2
    ENRAGE = 3


# ---------------------------------------------------------------------------
# Base Boss Class
# ---------------------------------------------------------------------------


class Boss(Enemy):
    """
    Base boss enemy class with multi-phase health system.

    Extends the Enemy class with:
        - Phase-based state transitions (P1 -> P2 -> P3 -> Enrage)
        - Phase thresholds and enrage timer
        - Visual transformation effects on phase change
        - Boss-specific health bar rendering
        - Immunity to stagger/flee effects
        - Custom phase transition logic

    Bosses are immune to fleeing and suppression effects by default.
    They have a larger health pool and unique visual representation.

    Args:
        base: The Panda3D ShowBase instance.
        boss_data: An EnemyData instance with boss-specific configuration.
        parent_node: NodePath to parent the boss under.
        collision_traverser: CollisionTraverser for raycasts.

    Attributes:
        phase: Current BossPhase.
        phase_thresholds: Dict mapping phases to health percentage thresholds.
        is_enraged: Whether the boss is in the enrage phase.
        enrage_timer: Time remaining in the enrage phase.
    """

    # Default phase thresholds (health percentage at which phase changes)
    PHASE_THRESHOLDS: Dict[BossPhase, float] = {
        BossPhase.PHASE_2: 0.66,
        BossPhase.PHASE_3: 0.33,
        BossPhase.ENRAGE: 0.15,
    }

    def __init__(
        self,
        base: Any,
        boss_data: EnemyData,
        parent_node: Optional[NodePath] = None,
        collision_traverser: Optional[CollisionTraverser] = None,
        world_node: Optional[NodePath] = None,
    ):
        super().__init__(
            base=base,
            enemy_data=boss_data,
            parent_node=parent_node,
            collision_traverser=collision_traverser,
            world_node=world_node,
        )

        self.phase: BossPhase = BossPhase.PHASE_1
        self.phase_thresholds: Dict[BossPhase, float] = dict(self.PHASE_THRESHOLDS)
        self.is_enraged: bool = False
        self.enrage_timer: float = 0.0
        self._enrage_duration: float = 60.0  # 60 seconds in enrage
        self._phase_enter_time: float = 0.0
        self._special_ability_cooldown: float = 0.0
        self._visual_transforms: List[NodePath] = []

    # -----------------------------------------------------------------------
    # Phase System
    # -----------------------------------------------------------------------

    def _check_phase_transition(self) -> None:
        """Check if the boss should transition to a new phase based on health."""
        health_pct = self.health / self.max_health

        # Determine target phase
        target_phase = BossPhase.PHASE_1
        for phase, threshold in sorted(self.phase_thresholds.items(), key=lambda x: x[1], reverse=True):
            if health_pct <= threshold:
                target_phase = phase

        if target_phase != self.phase:
            old_phase = self.phase
            self.phase = target_phase
            self._phase_enter_time = globalClock.getFrameTime()
            self._on_phase_change(old_phase, target_phase)

    def _on_phase_change(self, old_phase: BossPhase, new_phase: BossPhase) -> None:
        """
        Called when the boss transitions between phases.

        Subclasses should override this to implement phase-specific
        behavior changes (stat boosts, new abilities, visual effects).

        Args:
            old_phase: The phase being left.
            new_phase: The phase being entered.
        """
        logger.info("Boss '%s' entering %s", self.name, new_phase.name)

        # Stat changes based on phase
        phase_multipliers = {
            BossPhase.PHASE_1: 1.0,
            BossPhase.PHASE_2: 1.2,
            BossPhase.PHASE_3: 1.5,
            BossPhase.ENRAGE: 2.0,
        }

        multiplier = phase_multipliers.get(new_phase, 1.0)
        self.current_damage = self.enemy_data.damage * multiplier
        self.current_accuracy = min(1.0, self.enemy_data.accuracy * (0.9 + multiplier * 0.1))
        self.fire_rate = max(0.05, self.enemy_data.fire_rate / multiplier)

        # Enrage phase
        if new_phase == BossPhase.ENRAGE:
            self.is_enraged = True
            self.enrage_timer = self._enrage_duration

        # Visual effects
        self._play_phase_transition_effect(old_phase, new_phase)

        # Broadcast alert
        if self.squad:
            self.squad.broadcast_alert(
                self, self.node.get_pos(), AlertLevel.COMBAT
            )

    def _play_phase_transition_effect(self, old_phase: BossPhase, new_phase: BossPhase) -> None:
        """Visual/special effect when transitioning between phases."""
        # Default: screen shake and color flash
        if self._body_node:
            original_color = self._body_node.get_color()
            flash_seq = Sequence(
                Func(self._body_node.set_color, Vec4(1, 1, 1, 1)),
                Wait(0.1),
                Func(self._body_node.set_color, original_color),
                Wait(0.1),
                Func(self._body_node.set_color, Vec4(1, 1, 1, 1)),
                Wait(0.1),
                Func(self._body_node.set_color, original_color),
            )
            flash_seq.start()

        # Screen shake effect
        shake_intensity = (new_phase.value + 1) * 2.0
        if self.manager and self.manager.player_ref:
            self.manager.on_sound_event(
                self.node.get_pos(), SoundType.EXPLOSION, radius=shake_intensity * 5
            )

    # -----------------------------------------------------------------------
    # Update and Combat Overrides
    # -----------------------------------------------------------------------

    def _ai_update(self, task: Task) -> Task:
        """Override to handle boss-specific phase updates."""
        # Update enrage timer
        if self.is_enraged:
            self.enrage_timer -= globalClock.getDt()
            if self.enrage_timer <= 0:
                # Out of enrage - boss dies (in most games)
                self._on_enrage_timeout()

        # Check phase transitions
        self._check_phase_transition()

        # Update special ability cooldown
        if self._special_ability_cooldown > 0:
            self._special_ability_cooldown -= globalClock.getDt()

        return super()._ai_update(task)

    def _on_enrage_timeout(self) -> None:
        """Called when the enrage phase expires (boss should die)."""
        logger.warning("Boss '%s' enrage expired - forcing death.", self.name)
        self._die(self.node.get_pos())

    def _update_attack(self, dt: float, clock: float) -> None:
        """Override to add special abilities in attack state."""
        # Use special ability periodically
        if self._special_ability_cooldown <= 0:
            self._use_special_ability()
            self._special_ability_cooldown = random.uniform(8.0, 20.0)

        super()._update_attack(dt, clock)

    def _use_special_ability(self) -> None:
        """Use a special boss ability. Override in subclasses."""
        # Default: nothing
        pass

    def _enter_state(self, new_state: EnemyState) -> None:
        """Override - bosses never enter FLEE state."""
        if new_state == EnemyState.FLEE:
            # Ignore flee attempts
            return
        super()._enter_state(new_state)

    def take_damage(self, damage: float, source: Vec3 = None) -> None:
        """Override - bosses have higher damage resistance and phase checks."""
        # Reduce damage by an additional amount for bosses
        effective_damage = damage * 0.85

        super().take_damage(effective_damage, source)

    def _die(self, source: Vec3 = None) -> None:
        """Override for boss death with phase completion effects."""
        # Play death explosion
        if self.manager:
            self.manager.on_sound_event(
                self.node.get_pos(), SoundType.EXPLOSION, radius=30.0
            )

        # Visual destruction
        self._play_death_effect()

        super()._die(source)

    def _play_death_effect(self) -> None:
        """Large-scale visual effect when the boss dies."""
        if self._body_node:
            explosion_seq = Parallel(
                LerpScaleInterval(self._body_node, 0.5, 2.0),
                LerpColorScaleInterval(self._body_node, 0.5, Vec4(1, 0, 0, 0)),
            )
            explosion_seq.start()
            # Remove after animation
            task_name = f"boss_death_cleanup_{self.id}"
            def cleanup(task):
                if self.node and not self.node.is_empty():
                    self.node.remove_node()
                return Task.done
            taskMgr.do_method_later(0.6, cleanup, task_name)

    def _setup_collisions(self) -> None:
        """Override for boss - use larger collision volume."""
        radius, height = self.enemy_data.size

        cnode = CollisionNode(f"boss_{self.id}_collider")
        # Use a larger sphere for bosses
        boss_radius = max(radius, 1.0)
        csphere = CollisionSphere(0, 0, height * 0.5, boss_radius)
        cnode.add_solid(csphere)
        cnode.set_from_collide_mask(Constants.MASK_ENEMY | Constants.MASK_GEOMETRY)
        cnode.set_into_collide_mask(Constants.MASK_ENEMY)

        self._collision_node = self.node.attach_new_node(cnode)
        self._collision_node.set_python_tag("boss_ref", self)

    def _build_visual_model(self) -> None:
        """Override to build a large, imposing boss model."""
        radius, height = self.enemy_data.size
        color = self.enemy_data.color

        # Scale up the boss
        big_radius = radius * 3
        big_height = height * 2

        self._visual_root = self.node.attach_new_node("visual")

        # Body: Large capsule made of cylinder + two hemispheres
        from panda3d.core import Cylinder as P3DCylinder

        body_cyl = P3DCylinder(false, 1.0, 0.0, 1.0, 1.0, True)
        body_cyl_geom = body_cyl.get_geom(0)
        body_cyl_geom.set_scale(big_radius, big_radius, big_height)

        body_node = GeomNode("body")
        body_node.add_geom(body_cyl_geom)
        self._body_node = self._visual_root.attach_new_node(body_node)
        self._body_node.set_color(color)
        self._body_node.set_shader_auto()
        self._body_node.set_pos(0, 0, big_height * 0.5)

        # Direction indicator: Large arrow
        self._direction_indicator = self.node.attach_new_node("direction")

        arrow_len = big_radius * 3
        arrow_height = big_height * 0.6

        tri_vdata = GeomVertexData("boss_arrow", GeomVertexFormat.get_v3t2(), Geom.UH_static)
        tri_vertex = GeomVertexWriter(tri_vdata, "vertex")
        tri_texcoord = GeomVertexWriter(tri_vdata, "texcoord")

        # Large arrow triangle
        tri_vertex.add_data3f(0, arrow_len * 0.3, arrow_height + big_height * 0.5)
        tri_vertex.add_data3f(-big_radius * 1.5, arrow_len, arrow_height + big_height * 0.5)
        tri_vertex.add_data3f(big_radius * 1.5, arrow_len, arrow_height + big_height * 0.5)
        tri_texcoord.add_data2f(0.5, 1.0)
        tri_texcoord.add_data2f(0.0, 0.0)
        tri_texcoord.add_data2f(1.0, 0.0)

        tri_prim = GeomTriangle(Geom.UH_static)
        tri_prim.add_vertices(0, 1, 2)
        tri_prim.close_primitive()

        arrow_geom = Geom(tri_vdata)
        arrow_geom.add_primitive(tri_prim)
        arrow_node = GeomNode("arrow")
        arrow_node.add_geom(arrow_geom)
        arrow_np = self._direction_indicator.attach_new_node(arrow_node)
        arrow_np.set_color(Vec4(1, 1, 0, 1))
        arrow_np.set_shader_auto()

        # Boss health bar - much larger and always visible
        self._create_boss_health_bar()

    def _create_boss_health_bar(self) -> None:
        """Create a prominent health bar that's always visible."""
        if self._health_bar is not None:
            self._health_bar.remove_node()

        self._health_bar = self.render.attach_new_node(f"boss_health_{self.id}")
        self._health_bar.set_billboard_axis()
        self._health_bar.set_light_off()
        self._health_bar.set_shader_auto()
        self._health_bar.set_scale(3.0)

        # Background
        bg_cm = CardMaker("boss_health_bg")
        bg_cm.set_frame(-1.0, 1.0, -0.1, 0.1)
        bg = self._health_bar.attach_new_node(bg_cm.generate())
        bg.set_color(Vec4(0.1, 0.1, 0.1, 0.8))
        bg.set_transparency(TransparencyAttrib.M_alpha)

        # Foreground
        fg_cm = CardMaker("boss_health_fg")
        fg_cm.set_frame(-1.0, 1.0, -0.1, 0.1)
        self._health_fg = self._health_bar.attach_new_node(fg_cm.generate())
        self._health_fg.set_color(Vec4(0.8, 0.2, 0.2, 0.9))

        # Phase indicator
        self._phase_indicator: Optional[NodePath] = self._health_bar.attach_new_node("phase_text")
        phase_text = TextNode("phase_text")
        phase_text.set_text(f"BOSS - PHASE 1")
        phase_text.set_text_color(Vec4(1, 1, 1, 1))
        phase_text.set_card_color(Vec4(0, 0, 0, 0.5))
        phase_text.set_card_as_margin(0.2, 0.2, 0.2, 0.2)
        self._phase_indicator.node = phase_text

    def _update_health_bar(self) -> None:
        """Override to keep boss health bar always visible and show phase."""
        # Boss health bar is always visible
        if self._health_bar is None:
            self._create_boss_health_bar()
            return

        health_pct = self.health / self.max_health
        self._health_fg.set_scale(health_pct, 1, 1)
        self._health_fg.set_x(-1.0 + (1.0 - health_pct))

        # Color based on health
        if health_pct > 0.5:
            self._health_fg.set_color(Vec4(0.2, 0.8, 0.2, 0.9))
        elif health_pct > 0.25:
            self._health_fg.set_color(Vec4(0.8, 0.8, 0.2, 0.9))
        else:
            self._health_fg.set_color(Vec4(0.8, 0.2, 0.2, 0.9))

        # Update position
        pos = self.node.get_pos(self.render)
        pos.z += self.enemy_data.size[1] * 2 + 1.0
        self._health_bar.set_pos(pos)

        # Update phase text
        if self._phase_indicator and self._phase_indicator.has_python_tag("phase_text"):
            phase_node = self._phase_indicator.node
            if hasattr(phase_node, 'set_text'):
                phase_node.set_text(f"BOSS - {self.phase.name} ({int(health_pct * 100)}%)")


# ---------------------------------------------------------------------------
# 1. Cybernetic Overlord
# ---------------------------------------------------------------------------


class CyberneticOverlord(Boss):
    """
    Cyberpunk City - Final Boss

    A heavily cybernetic enemy that uses energy shields and deploys combat drones.
    Has a technological aesthetic with glowing circuitry patterns.

    Phase 1: Shielded attacks, basic energy weapons.
    Phase 2: Deploys drone minions, shield drops.
    Phase 3: Goes berserk, shield returns with increased power.
    Enrage: Overload explosion imminent - self-destructs.

    Special Abilities:
        - Energy Shield: Reduces incoming damage by 50% in P1 and P3.
        - Drone Deployment: Spawns CombatDrone minions in P2.
        - EMP Blast: Stuns player and disables weapons temporarily.
        - Self-Destruct: In enrage, explodes after 30 seconds.
    """

    ENEMY_DATA = EnemyData(
        name="Cybernetic Overlord",
        health=1500.0,
        armor=0.3,
        move_speed=5.0,
        run_speed=8.0,
        turn_speed=150.0,
        vision_angle=120.0,
        vision_distance=60.0,
        hearing_distance=50.0,
        accuracy=0.85,
        damage=45.0,
        fire_rate=0.2,
        attack_range=40.0,
        flee_threshold=0.0,  # Never flee
        call_reinforcements=True,
        reinforcement_radius=50.0,
        color=Vec4(0.2, 0.6, 1.0, 1.0),  # Electric blue
        size=(0.8, 2.5),
        weapon_id="plasma_rifle",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shield_active: bool = False
        self._shield_energy: float = 300.0
        self._max_shield: float = 300.0
        self._drones_spawned: int = 0
        self._max_drones: int = 6
        self._drones: List[Enemy] = []
        self._emp_cooldown: float = 0.0
        self._circuit_pattern: Optional[NodePath] = None

    def _on_phase_change(self, old_phase: BossPhase, new_phase: BossPhase) -> None:
        """Override for Overlord phase transitions."""
        super()._on_phase_change(old_phase, new_phase)

        if new_phase == BossPhase.PHASE_1:
            self._shield_active = True
            self._shield_energy = self._max_shield
        elif new_phase == BossPhase.PHASE_2:
            # Shield drops, drones deploy
            self._shield_active = False
            self._deploy_drones()
        elif new_phase == BossPhase.PHASE_3:
            # Shield returns
            self._shield_active = True
            self._shield_energy = self._max_shield * 0.5
        elif new_phase == BossPhase.ENRAGE:
            self._start_self_destruct()

    def _deploy_drones(self) -> None:
        """Deploy combat drone minions."""
        from ai.enemy_types import CombatDrone

        for _ in range(2):
            if self._drones_spawned >= self._max_drones:
                break

            # Spawn near the boss
            offset = Vec3(
                random.uniform(-5, 5),
                random.uniform(-5, 5),
                random.uniform(3, 6),
            )
            spawn_pos = self.node.get_pos() + offset

            if self.manager:
                drone = self.manager.spawn_enemy(
                    CombatDrone,
                    position=(spawn_pos.x, spawn_pos.y, spawn_pos.z),
                )
                self._drones.append(drone)
                self._drones_spawned += 1

    def _start_self_destruct(self) -> None:
        """Start the self-destruct sequence in enrage."""
        logger.info("Cybernetic Overlord entering self-destruct sequence!")
        self.enrage_timer = 30.0  # 30 seconds to escape

    def _on_enrage_timeout(self) -> None:
        """Override: explode on enrage timeout."""
        if self.manager:
            self.manager.on_sound_event(
                self.node.get_pos(), SoundType.EXPLOSION, radius=50.0
            )
        # Massive damage to player
        if self.manager and self.manager.player_ref:
            self.manager.apply_damage_to_player(
                200.0, self.node.get_pos(), self.node.get_pos()
            )
        super()._on_enrage_timeout()

    def take_damage(self, damage: float, source: Vec3 = None) -> None:
        """Override for shield absorption."""
        if self._shield_active and self._shield_energy > 0:
            absorbed = min(damage, self._shield_energy)
            self._shield_energy -= absorbed
            damage -= absorbed

            # Shield hit effect
            self._play_shield_hit_effect()

        super().take_damage(damage, source)

    def _play_shield_hit_effect(self) -> None:
        """Visual effect when the shield absorbs damage."""
        if self._body_node:
            flash = Sequence(
                Func(self._body_node.set_color, Vec4(0.5, 1.0, 1.0, 1.0)),
                Wait(0.1),
                Func(self._body_node.set_color, self.enemy_data.color),
            )
            flash.start()

    def _use_special_ability(self) -> None:
        """Override for Overlord abilities."""
        if self.phase == BossPhase.PHASE_1:
            # Regenerate shield
            self._shield_energy = min(self._max_shield, self._shield_energy + 50.0)
        elif self.phase == BossPhase.PHASE_2:
            # Deploy another drone
            if self._drones_spawned < self._max_drones and self.manager:
                self._deploy_drones()
        elif self.phase == BossPhase.PHASE_3:
            # EMP blast
            if self._emp_cooldown <= 0:
                self._emp_blast()
        elif self.phase == BossPhase.ENRAGE:
            # Self-destruct - no special ability needed
            pass

    def _emp_blast(self) -> None:
        """EMP blast that stuns the player and nearby drones."""
        self._emp_cooldown = 15.0

        if self.manager and self.manager.player_ref:
            self.manager.on_sound_event(
                self.node.get_pos(), SoundType.EXPLOSION, radius=20.0
            )

        # Visual effect
        if self._body_node:
            emp_seq = Sequence(
                Func(self._body_node.set_color, Vec4(0.3, 1.0, 1.0, 1.0)),
                Wait(0.5),
                Func(self._body_node.set_color, self.enemy_data.color),
            )
            emp_seq.start()

    def _build_visual_model(self) -> None:
        """Override for cybernetic aesthetic."""
        super()._build_visual_model()

        # Add glowing circuitry
        if self._visual_root:
            circuit_node = self._visual_root.attach_new_node("circuits")
            for i in range(6):
                line = circuit_node.attach_new_node(f"circuit_line_{i}")
                cm = CardMaker(f"circuit_{i}")
                cm.set_frame(0, 0, -0.2, 0.2)
                card = line.attach_new_node(cm.generate())
                card.set_color(Vec4(0.0, 1.0, 1.0, 0.4))
                card.set_transparency(TransparencyAttrib.M_alpha)
                card.set_pos(0, 0, i * 0.4)
                card.set_scale(2.0, 0.1, 0.05)

    def _update_animation(self, dt: float) -> None:
        """Override for cybernetic pulsing effect."""
        super()._update_animation(dt)

        if self._body_node and self._circuit_pattern is None:
            # Pulsing glow on the body
            pulse = math.sin(globalClock.getFrameTime() * 3) * 0.1 + 0.9
            if self._shield_active:
                self._body_node.set_color_scale(
                    Vec4(1 + pulse * 0.2, 1, 1, 1)
                )


# ---------------------------------------------------------------------------
# 2. War Beast
# ---------------------------------------------------------------------------


class WarBeast(Boss):
    """
    Post-Apocalyptic Boss

    A massive mutated creature focused on melee combat and area control.
    Uses ground slams, charge attacks, and summons smaller creatures.

    Phase 1: Basic melee, slow but powerful.
    Phase 2: Gains new attacks (charge, ground slam).
    Phase 3: Enraged - faster, deals AoE damage continuously.
    Enrage: Berserker rage - doubles attack speed and damage.

    Special Abilities:
        - Ground Slam: Damages all enemies in a large radius.
        - Charge Attack: Charges toward the player for massive damage.
        - Summon Pack: Calls lesser creatures to aid in battle.
        - Berserk: In enrage, attacks deal constant AoE damage.
    """

    ENEMY_DATA = EnemyData(
        name="War Beast",
        health=2000.0,
        armor=0.4,
        move_speed=4.0,
        run_speed=12.0,
        turn_speed=100.0,
        vision_angle=180.0,
        vision_distance=40.0,
        hearing_distance=50.0,
        accuracy=0.9,
        damage=60.0,
        fire_rate=0.5,
        attack_range=5.0,  # Very close range
        flee_threshold=0.0,
        call_reinforcements=True,
        reinforcement_radius=40.0,
        color=Vec4(0.6, 0.2, 0.2, 1.0),  # Dark red
        size=(1.0, 3.0),
        weapon_id="",  # Melee only
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._charge_ready: bool = False
        self._charge_cooldown: float = 0.0
        self._slam_cooldown: float = 0.0
        self._summoned_count: int = 0
        self._max_summons: int = 4

    def _on_phase_change(self, old_phase: BossPhase, new_phase: BossPhase) -> None:
        """Override for Beast phase transitions."""
        super()._on_phase_change(old_phase, new_phase)

        stat_boosts = {
            BossPhase.PHASE_1: {"speed": 1.0, "damage": 1.0, "armor": 0.0},
            BossPhase.PHASE_2: {"speed": 1.3, "damage": 1.2, "armor": 0.1},
            BossPhase.PHASE_3: {"speed": 1.6, "damage": 1.5, "armor": 0.2},
            BossPhase.ENRAGE: {"speed": 2.0, "damage": 2.0, "armor": 0.3},
        }

        boost = stat_boosts.get(new_phase, stat_boosts[BossPhase.PHASE_1])
        self.run_speed = self.enemy_data.run_speed * boost["speed"]
        self.current_damage = self.enemy_data.damage * boost["damage"]
        self.armor = self.enemy_data.armor + boost["armor"]

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override for melee attacks."""
        dist = self.node.get_pos().distance(target_pos)

        if dist > self._melee_range:
            # Move closer
            self._target_position = target_pos
            self._move_to_target(globalClock.getDt())
        else:
            # Melee attack
            self._melee_attack(target_pos)

    def _melee_attack(self, target_pos: Vec3) -> None:
        """Perform a melee attack."""
        self._cooldown_timer -= globalClock.getDt()
        if self._cooldown_timer > 0:
            return

        if self.manager and self.manager.player_ref:
            self.manager.apply_damage_to_player(
                self.current_damage,
                self.node.get_pos(),
                target_pos,
            )

        # Attack effect
        self._play_attack_effect()
        self._cooldown_timer = 1.0 / self.fire_rate

    def _play_attack_effect(self) -> None:
        """Visual effect for melee attack."""
        if self._body_node:
            seq = Sequence(
                Func(self._body_node.set_scale, Vec3(1.1, 1.1, 1.1)),
                Wait(0.2),
                Func(self._body_node.set_scale, Vec3(1.0, 1.0, 1.0)),
            )
            seq.start()

    def _use_special_ability(self) -> None:
        """Override for Beast abilities."""
        if self.phase == BossPhase.PHASE_2:
            # 50% chance for charge or slam
            if random.random() < 0.5 and self._charge_cooldown <= 0:
                self._charge_attack()
            elif self._slam_cooldown <= 0:
                self._ground_slam()
        elif self.phase == BossPhase.PHASE_3:
            # More aggressive - 70% chance for special ability
            if random.random() < 0.7:
                if random.random() < 0.5:
                    self._charge_attack()
                else:
                    self._ground_slam()
            elif self._summoned_count < self._max_summons:
                self._summon_pack()
        elif self.phase == BossPhase.ENRAGE:
            # Enraged - always trying special abilities
            if self._charge_cooldown <= 0:
                self._charge_attack()
            elif self._slam_cooldown <= 0:
                self._ground_slam()

    def _charge_attack(self) -> None:
        """Charge toward the player."""
        self._charge_cooldown = 8.0
        player_pos = self._get_player_position()
        if player_pos is None:
            return

        # Lunge forward
        direction = (player_pos - self.node.get_pos()).normalized()
        lunge_distance = 10.0
        target_pos = self.node.get_pos() + direction * lunge_distance

        # Move to target quickly
        self._target_position = target_pos

        # Damage at end of charge
        task_name = f"beast_charge_{self.id}"
        def process_charge(task):
            dist = self.node.get_pos().distance(player_pos)
            if dist < 5.0 and self.manager and self.manager.player_ref:
                self.manager.apply_damage_to_player(
                    self.current_damage * 1.5,
                    self.node.get_pos(),
                    player_pos,
                )
            return Task.done

        taskMgr.do_method_later(0.5, process_charge, task_name)

    def _ground_slam(self) -> None:
        """Area attack around the boss."""
        self._slam_cooldown = 12.0

        if self.manager and self.manager.player_ref:
            player_pos = self.manager.player_ref.get_pos(self.render)
            dist = self.node.get_pos().distance(player_pos)
            if dist < 10.0:
                self.manager.apply_damage_to_player(
                    self.current_damage * 0.8,
                    self.node.get_pos(),
                    player_pos,
                )

        # Visual effect
        if self._body_node:
            seq = Sequence(
                Func(self._body_node.set_scale, Vec3(1.5, 1.5, 0.5)),
                Wait(0.3),
                Func(self._body_node.set_scale, Vec3(1.0, 1.0, 1.0)),
            )
            seq.start()

    def _summon_pack(self) -> None:
        """Summon lesser creatures."""
        from ai.enemy_types import ExperimentalCreature

        self._summoned_count += 1

        if self.manager:
            offset = Vec3(
                random.uniform(-3, 3),
                random.uniform(-3, 3),
                0,
            )
            spawn_pos = self.node.get_pos() + offset

            creature = self.manager.spawn_enemy(
                ExperimentalCreature,
                position=(spawn_pos.x, spawn_pos.y, spawn_pos.z),
            )

    def _update_animation(self, dt: float) -> None:
        """Override for heavy footstep effects."""
        super()._update_animation(dt)

        # Ground shake effect
        if self.velocity.length() > 0.1 and random.random() < 0.05:
            if self.manager:
                self.manager.on_sound_event(
                    self.node.get_pos(), SoundType.FOOTSTEPS, radius=15.0
                )


# ---------------------------------------------------------------------------
# 3. Security Core
# ---------------------------------------------------------------------------


class SecurityCore(Boss):
    """
    Military Facility Boss

    A stationary (or minimally mobile) defensive AI core that activates
    turrets, deploys shields, and initiates facility lockdown.

    Phase 1: Single core, basic laser attack.
    Phase 2: Deploys turrets and energy barriers.
    Phase 3: Core exposed, multi-target laser barrage.
    Enrage: Self-destruct sequence with facility-wide explosion.

    Special Abilities:
        - Turret Deployment: Spawns automated turrets.
        - Energy Barrier: Blocks player from certain directions.
        - Laser Barrage: Multi-target high-damage attack.
        - Facility Lockdown: Locks doors, spawns more enemies.
        - Hardened Shell: Reduces all damage in early phases.
    """

    ENEMY_DATA = EnemyData(
        name="Security Core",
        health=1200.0,
        armor=0.5,
        move_speed=0.0,  # Stationary
        run_speed=0.0,
        turn_speed=90.0,
        vision_angle=360.0,
        vision_distance=70.0,
        hearing_distance=60.0,
        accuracy=0.95,
        damage=40.0,
        fire_rate=0.3,
        attack_range=50.0,
        flee_threshold=0.0,
        call_reinforcements=True,
        reinforcement_radius=60.0,
        color=Vec4(0.8, 0.8, 0.2, 1.0),  # Yellow/gold
        size=(1.5, 1.5),
        weapon_id="laser_cannon",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._turrets: List[Enemy] = []
        self._max_turrets: int = 4
        self._turret_count: int = 0
        self._barrier_active: bool = False
        self._laser_barrage_cooldown: float = 0.0
        self._lockdown_activated: bool = False

    def _on_phase_change(self, old_phase: BossPhase, new_phase: BossPhase) -> None:
        """Override for Security Core phase transitions."""
        super()._on_phase_change(old_phase, new_phase)

        if new_phase == BossPhase.PHASE_2:
            self._deploy_turrets()
            self._activate_barrier()
        elif new_phase == BossPhase.PHASE_3:
            # Core exposed - remove armor
            self.armor = 0.1
            self._deploy_additional_turrets()
        elif new_phase == BossPhase.ENRAGE:
            self._activate_lockdown()

    def _deploy_turrets(self) -> None:
        """Deploy automated turrets around the core."""
        from ai.enemy_types import CombatDrone

        for i in range(2):
            if self._turret_count >= self._max_turrets:
                break

            angle = math.radians(i * 120)
            offset = Vec3(
                math.cos(angle) * 10.0,
                math.sin(angle) * 10.0,
                0,
            )
            spawn_pos = self.node.get_pos() + offset

            if self.manager:
                # Create a stationary drone-like turret
                turret = self.manager.spawn_enemy(
                    CombatDrone,
                    position=(spawn_pos.x, spawn_pos.y, spawn_pos.z),
                )
                turret.move_speed = 0
                turret.run_speed = 0
                self._turrets.append(turret)
                self._turret_count += 1

    def _deploy_additional_turrets(self) -> None:
        """Deploy more turrets in phase 3."""
        if self._turret_count < self._max_turrets and self.manager:
            for i in range(2):
                if self._turret_count >= self._max_turrets:
                    break
                angle = math.radians(i * 90 + 45)
                offset = Vec3(math.cos(angle) * 15.0, math.sin(angle) * 15.0, 0)
                spawn_pos = self.node.get_pos() + offset

                # Simple turret
                turret_data = EnemyData(
                    name="Turret",
                    health=100.0,
                    armor=0.2,
                    move_speed=0,
                    run_speed=0,
                    turn_speed=200.0,
                    vision_angle=120.0,
                    vision_distance=40.0,
                    hearing_distance=40.0,
                    accuracy=0.8,
                    damage=20.0,
                    fire_rate=0.15,
                    attack_range=35.0,
                    color=Vec4(0.8, 0.8, 0.2, 1.0),
                    size=(0.5, 1.0),
                )
                turret = self.manager.spawn_enemy(
                    Enemy,  # Use base Enemy as turret
                    enemy_data=turret_data,
                    position=(spawn_pos.x, spawn_pos.y, spawn_pos.z),
                )
                turret.move_speed = 0
                self._turrets.append(turret)
                self._turret_count += 1

    def _activate_barrier(self) -> None:
        """Activate an energy barrier."""
        self._barrier_active = True
        logger.info("Security Core: Energy barrier activated.")

    def _activate_lockdown(self) -> None:
        """Initiate facility-wide lockdown."""
        self._lockdown_activated = True
        logger.info("Security Core: FACILITY LOCKDOWN INITIATED!")

        if self.manager:
            self.manager.on_sound_event(
                self.node.get_pos(), SoundType.ALARM, radius=100.0
            )

    def _use_special_ability(self) -> None:
        """Override for Security Core abilities."""
        if self.phase == BossPhase.PHASE_1:
            # Hardened shell - reduce damage
            self.armor = 0.5
        elif self.phase == BossPhase.PHASE_2:
            # Laser barrage
            self._laser_barrage()
        elif self.phase == BossPhase.PHASE_3:
            # Multi-target attack
            if self._laser_barrage_cooldown <= 0:
                self._laser_barrage()
        elif self.phase == BossPhase.ENRAGE:
            # Self-destruct countdown
            self._start_self_destruct()

    def _laser_barrage(self) -> None:
        """Fire lasers at multiple targets."""
        self._laser_barrage_cooldown = 10.0

        if self.manager and self.manager.player_ref:
            player_pos = self.manager.player_ref.get_pos(self.render)

            # Main beam
            self.manager.apply_damage_to_player(
                self.current_damage, self.node.get_pos(), player_pos
            )

            # Visual effect
            if self._body_node:
                seq = Sequence(
                    Func(self._body_node.set_color, Vec4(1.0, 1.0, 0.0, 1.0)),
                    Wait(0.2),
                    Func(self._body_node.set_color, self.enemy_data.color),
                )
                seq.start()

    def _start_self_destruct(self) -> None:
        """Start the self-destruct sequence."""
        self.enrage_timer = 45.0  # 45 seconds to escape

        if self.manager:
            self.manager.on_sound_event(
                self.node.get_pos(), SoundType.ALARM, radius=100.0
            )

    def take_damage(self, damage: float, source: Vec3 = None) -> None:
        """Override for hardened shell."""
        if self.phase == BossPhase.PHASE_1 and not self.is_enraged:
            damage *= 0.5  # 50% damage reduction from hardened shell

        super().take_damage(damage, source)

    def _move_toward_point(self, target: Vec3, dt: float) -> None:
        """Override - Security Core doesn't move (stationary)."""
        # Only rotate to face target
        if self._target_position is not None:
            direction = self._target_position - self.node.get_pos()
            if direction.length() > 0.01:
                direction.normalize()
                target_h = math.degrees(math.atan2(-direction.x, direction.y))
                self.node.set_h(self.node.get_h() + (target_h - self.node.get_h()) * 0.1)

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override for turret-like aiming."""
        # Rotate to face target
        direction = target_pos - self.node.get_pos()
        if direction.length() > 0.01:
            direction.normalize()
            target_h = math.degrees(math.atan2(-direction.x, direction.y))
            self.node.set_h(self.node.get_h() + (target_h - self.node.get_h()) * 0.2)

        # Fire laser
        self._cooldown_timer -= globalClock.getDt()
        if self._cooldown_timer > 0:
            return

        if self.manager and self.manager.player_ref:
            self.manager.apply_damage_to_player(
                self.current_damage, self.node.get_pos(), target_pos
            )

        self._cooldown_timer = 1.04 / self.fire_rate

    def _build_visual_model(self) -> None:
        """Override for core aesthetic - sphere with hexagonal panels."""
        radius, height = self.enemy_data.size
        color = self.enemy_data.color

        self._visual_root = self.node.attach_new_node("visual")

        # Core sphere
        from panda3d.core import Sphere

        sphere_node = self._make_uv_sphere(radius=radius, segments=16)
        self._body_node = self._visual_root.attach_new_node(sphere_node)
        self._body_node.set_color(color)
        self._body_node.set_shader_auto()

        # Hexagonal panels
        for i in range(6):
            angle = i * 60
            panel = self._visual_root.attach_new_node(f"panel_{i}")
            panel.set_h(angle)
            cm = CardMaker(f"panel_{i}")
            cm.set_frame(-radius * 0.3, radius * 0.3, -radius * 0.3, radius * 0.3)
            card = panel.attach_new_node(cm.generate())
            card.set_color(Vec4(0.6, 0.6, 0.1, 1.0))
            card.set_shader_auto()

        # Top antenna
        antenna = self._visual_root.attach_new_node("antenna")
        cm = CardMaker("antenna")
        cm.set_frame(-0.1, 0.1, -radius, radius * 2)
        antenna_card = antenna.attach_new_node(cm.generate())
        antenna_card.set_color(Vec4(0.5, 0.5, 0.5, 1.0))
        antenna.set_z(radius)

        # Direction indicator (laser turret)
        self._direction_indicator = self.node.attach_new_node("direction")
        line_vdata = GeomVertexData("laser_line", GeomVertexFormat.get_v3t2(), Geom.UH_static)
        line_vertex = GeomVertexWriter(line_vdata, "vertex")
        line_vertex.add_data3f(0, 0, height * 0.5)
        line_vertex.add_data3f(0, radius * 2, height * 0.5)

        line_prim = GeomTriangle(Geom.UH_static)
        # Actually use a thin quad for the laser
        from panda3d.core import GeomLine
        # Simpler: just use a card
        laser_cm = CardMaker("laser")
        laser_cm.set_frame(0, 0, 0, radius * 2)
        laser_np = self._direction_indicator.attach_new_node(laser_cm.generate())
        laser_np.set_color(Vec4(1.0, 0.5, 0.0, 0.6))
        laser_np.set_transparency(TransparencyAttrib.M_alpha)
        laser_np.set_pos(0, 0, height * 0.5)

        # Boss health bar
        self._create_boss_health_bar()


# ---------------------------------------------------------------------------
# 4. Guardian
# ---------------------------------------------------------------------------


class Guardian(Boss):
    """
    Arctic Base Boss

    A massive ice construct that manipulates the frozen environment.
    Creates ice spikes, freezes the ground, and uses cold-based attacks.

    Phase 1: Ice shard attacks, creates slippery surfaces.
    Phase 2: Freezes parts of the arena, spawns ice minions.
    Phase 3: Blizzard storm - reduced visibility and constant damage.
    Enrage: Absolute zero - instant freeze if player gets too close.

    Special Abilities:
        - Ice Shard Barrage: Ranged projectile attack.
        - Freeze Ground: Player moves are slowed in affected area.
        - Ice Minions: Spawns frozen enemies.
        - Blizzard: Arena-wide storm with visibility reduction.
        - Absolute Zero: Instant death zone around the boss in enrage.
    """

    ENEMY_DATA = EnemyData(
        name="Arctic Guardian",
        health=1800.0,
        armor=0.35,
        move_speed=3.0,
        run_speed=6.0,
        turn_speed=100.0,
        vision_angle=135.0,
        vision_distance=45.0,
        hearing_distance=35.0,
        accuracy=0.8,
        damage=50.0,
        fire_rate=0.4,
        attack_range=35.0,
        flee_threshold=0.0,
        call_reinforcements=True,
        reinforcement_radius=45.0,
        color=Vec4(0.5, 0.8, 1.0, 1.0),  # Ice blue
        size=(1.2, 2.8),
        weapon_id="frost_cannon",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ice_spike_positions: List[Vec3] = []
        self._blizzard_active: bool = False
        self._frozen_ground_radius: float = 0.0
        self._ice_minion_count: int = 0
        self._max_ice_minions: int = 4

    def _on_phase_change(self, old_phase: BossPhase, new_phase: BossPhase) -> None:
        """Override for Guardian phase transitions."""
        super()._on_phase_change(old_phase, new_phase)

        if new_phase == BossPhase.PHASE_2:
            self._spawn_ice_minions()
            self._frozen_ground_radius = 15.0
        elif new_phase == BossPhase.PHASE_3:
            self._activate_blizzard()
            self._frozen_ground_radius = 20.0
        elif new_phase == BossPhase.ENRAGE:
            self._frozen_ground_radius = 30.0
            self._blizzard_active = True

    def _spawn_ice_minions(self) -> None:
        """Spawn ice minion enemies."""
        from ai.enemy_types import ExperimentalCreature

        for _ in range(2):
            if self._ice_minion_count >= self._max_ice_minions:
                break

            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(8, 15)
            offset = Vec3(
                math.cos(angle) * dist,
                math.sin(angle) * dist,
                0,
            )
            spawn_pos = self.node.get_pos() + offset

            if self.manager:
                minion = self.manager.spawn_enemy(
                    ExperimentalCreature,
                    position=(spawn_pos.x, spawn_pos.y, spawn_pos.z),
                )
                minion.color = Vec4(0.5, 0.8, 1.0, 1.0)  # Ice-colored
                self._ice_minion_count += 1

    def _activate_blizzard(self) -> None:
        """Activate a blizzard storm effect."""
        self._blizzard_active = True
        logger.info("Arctic Guardian: Blizzard activated!")

        if self.manager and self.manager.player_ref:
            self.manager.on_sound_event(
                self.node.get_pos(), SoundType.AMBIENT, radius=60.0
            )

    def _use_special_ability(self) -> None:
        """Override for Guardian abilities."""
        if self.phase == BossPhase.PHASE_1:
            # Ice shard barrage
            self._ice_shard_barrage()
        elif self.phase == BossPhase.PHASE_2:
            # Freeze player area
            self._freeze_ground()
        elif self.phase == BossPhase.PHASE_3:
            # Blizzard + ice shards
            if random.random() < 0.7:
                self._ice_shard_barrage()
            else:
                self._freeze_ground()
        elif self.phase == BossPhase.ENRAGE:
            # Absolute zero zone
            self._absolute_zero()

    def _ice_shard_barrage(self) -> None:
        """Fire multiple ice shards at the player."""
        if self.manager and self.manager.player_ref:
            player_pos = self.manager.player_ref.get_pos(self.render)

            # Multiple projectiles
            for i in range(3):
                offset = Vec3(
                    random.uniform(-2, 2),
                    random.uniform(-2, 2),
                    random.uniform(-1, 1),
                )
                target = player_pos + offset
                self.manager.apply_damage_to_player(
                    self.current_damage * 0.7,
                    self.node.get_pos(),
                    target,
                )

            # Visual effect
            if self._body_node:
                seq = Sequence(
                    Func(self._body_node.set_color, Vec4(1.0, 1.0, 1.0, 1.0)),
                    Wait(0.2),
                    Func(self._body_node.set_color, self.enemy_data.color),
                )
                seq.start()

    def _freeze_ground(self) -> None:
        """Freeze the ground around the boss, slowing the player."""
        if self.manager and self.manager.player_ref:
            player_pos = self.manager.player_ref.get_pos(self.render)
            dist = self.node.get_pos().distance(player_pos)

            if dist < self._frozen_ground_radius:
                # Slow the player (send event)
                if hasattr(self.manager.player_ref, 'apply_slow'):
                    self.manager.player_ref.apply_slow(0.5, 3.0)
                else:
                    # Use messenger
                    self.base.messenger.send("player_slowed", [0.5, 3.0])

    def _absolute_zero(self) -> None:
        """Create an instant-death zone around the boss."""
        if self.manager and self.manager.player_ref:
            player_pos = self.manager.player_ref.get_pos(self.render)
            dist = self.node.get_pos().distance(player_pos)

            if dist < 12.0:
                self.manager.apply_damage_to_player(
                    200.0, self.node.get_pos(), player_pos
                )

        # Visual: blue white flash
        if self._body_node:
            seq = Sequence(
                Func(self._body_node.set_color, Vec4(1.0, 1.0, 1.0, 1.0)),
                Wait(0.1),
                Func(self._body_node.set_color, self.enemy_data.color),
            )
            seq.start()

    def _clamp_to_ground(self, pos: Vec3) -> None:
        """Override - Guardian stays on ground."""
        pos.z = 1.0  # Fixed height
        self.node.set_pos(pos)

    def _build_visual_model(self) -> None:
        """Override for icy aesthetic - crystalline, faceted appearance."""
        radius, height = self.enemy_data.size
        color = self.enemy_data.color

        self._visual_root = self.node.attach_new_node("visual")

        # Main body: faceted cylinder
        from panda3d.core import Cylinder as P3DCylinder

        body_cyl = P3DCylinder(false, 1.0, 0.0, 1.0, 1.0, True)
        body_geom = body_cyl.get_geom(0)
        body_geom.set_scale(radius, radius, height)

        body_node = GeomNode("body")
        body_node.add_geom(body_geom)
        self._body_node = self._visual_root.attach_new_node(body_node)
        self._body_node.set_color(color)
        self._body_node.set_shader_auto()
        self._body_node.set_pos(0, 0, height * 0.5)

        # Ice crystal spikes on top
        for i in range(6):
            angle = i * 60
            spike = self._visual_root.attach_new_node(f"spike_{i}")
            spike.set_h(angle)
            spike.set_pos(0, 0, height)

            # Pyramid spike
            spike_vdata = GeomVertexData("spike", GeomVertexFormat.get_v3t2(), Geom.UH_static)
            spike_vertex = GeomVertexWriter(spike_vdata, "vertex")
            spike_vertex.add_data3f(0, 0, radius * 0.5)
            spike_vertex.add_data3f(-radius * 0.3, 0, 0)
            spike_vertex.add_data3f(radius * 0.3, 0, 0)
            spike_vertex.add_data3f(0, 0, radius * 2)

            from panda3d.core import GeomTrifans
            spike_prim = GeomTrifans(Geom.UH_static)
            for v in range(4):
                spike_prim.add_vertex(v)
            spike_prim.close_primitive()

            spike_geom = Geom(spike_vdata)
            spike_geom.add_primitive(spike_prim)
            spike_node = GeomNode("spike")
            spike_node.add_geom(spike_geom)
            spike_np = spike.attach_new_node(spike_node)
            spike_np.set_color(Vec4(0.6, 0.9, 1.0, 0.7))
            spike_np.set_transparency(TransparencyAttrib.M_alpha)

        # Direction indicator
        self._direction_indicator = self.node.attach_new_node("direction")

        # Boss health bar
        self._create_boss_health_bar()


# ---------------------------------------------------------------------------
# 5. Xenomorph
# ---------------------------------------------------------------------------


class Xenomorph(Boss):
    """
    Space Station Boss

    An alien creature that can crawl on walls and ceilings, emerging
    unexpectedly for ambush attacks. Has acidic blood that damages
    anyone who gets too close.

    Phase 1: Ground-based attacks, acid blood.
    Phase 2: Wall crawling, ceiling ambushes.
    Phase 3: Full alien form - faster, can be anywhere.
    Enrage: Acid spray - area denial attack.

    Special Abilities:
        - Wall Crawl: Moves on walls and ceilings.
        - Ambush: Emerges from unexpected locations.
        - Acid Blood: Damages nearby enemies on hit.
        - Pounce: Leaps from walls/ceiling for a surprise attack.
        - Acid Spray: Area-of-effect acid attack in enrage.
    """

    ENEMY_DATA = EnemyData(
        name="Xenomorph",
        health=1500.0,
        armor=0.2,
        move_speed=6.0,
        run_speed=20.0,
        turn_speed=300.0,
        vision_angle=180.0,
        vision_distance=35.0,
        hearing_distance=45.0,
        accuracy=0.9,
        damage=35.0,
        fire_rate=0.8,
        attack_range=4.0,  # Melee range
        flee_threshold=0.0,
        call_reinforcements=False,
        color=Vec4(0.1, 0.6, 0.1, 1.0),  # Dark green/alien
        size=(0.5, 2.0),
        weapon_id="",  # Melee
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_wall: bool = False
        self._pounce_ready: bool = True
        self._pounce_cooldown: float = 0.0
        self._acid_blood: float = 100.0  # Acid blood level
        self._emergence_positions: List[Vec3] = []

    def _on_phase_change(self, old_phase: BossPhase, new_phase: BossPhase) -> None:
        super()._on_phase_change(old_phase, new_phase)

        if new_phase == BossPhase.PHASE_2:
            # Gain wall crawling
            self._on_wall = True
            self._setup_wall_anchors()
        elif new_phase == BossPhase.PHASE_3:
            # Full alien - can teleport to walls/ceiling
            self._setup_emergence_points()

    def _setup_wall_anchors(self) -> None:
        """Set up wall attachment points for crawling."""
        # In a real game, would find walls in the scene
        # Here we just enable wall movement
        pass

    def _setup_emergence_points(self) -> None:
        """Set up positions for ceiling ambushes."""
        # Create random emergence points around the arena
        for _ in range(8):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(10, 25)
            pos = Vec3(
                math.cos(angle) * dist,
                math.sin(angle) * dist,
                random.uniform(3, 8),  # On walls/ceiling
            )
            self._emergence_positions.append(pos)

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override for alien melee attacks with pouncing."""
        dist = self.node.get_pos().distance(target_pos)

        if dist > self._melee_range + 2.0:
            # Move closer
            self._target_position = target_pos
            self._move_to_target(globalClock.getDt())
        else:
            # Melee attack
            self._melee_attack(target_pos)

    def _melee_attack(self, target_pos: Vec3) -> None:
        """Perform a melee attack with acid blood effect."""
        self._cooldown_timer -= globalClock.getDt()
        if self._cooldown_timer > 0:
            return

        if self.manager and self.manager.player_ref:
            # Main attack
            self.manager.apply_damage_to_player(
                self.current_damage, self.node.get_pos(), target_pos
            )

            # Acid blood on hit
            self._acid_blood = min(100.0, self._acid_blood + 30.0)

        self._cooldown_timer = 0.5

    def take_damage(self, damage: float, source: Vec3 = None) -> None:
        """Override - acid blood damages attacker."""
        # Acid blood effect
        if self._acid_blood > 20 and source is not None:
            # Apply damage to player if they're close
            if self.manager and self.manager.player_ref:
                player_pos = self.manager.player_ref.get_pos(self.render)
                if player_pos.distance(source) < 5.0:
                    self.manager.apply_damage_to_player(
                        10.0,  # Acid damage
                        self.node.get_pos(),
                        source,
                    )

        super().take_damage(damage, source)

    def _use_special_ability(self) -> None:
        """Override for alien abilities."""
        if self.phase == BossPhase.PHASE_2 and self._pounce_cooldown <= 0:
            # Pounce from wall
            if self._on_wall:
                self._pounce_attack()
        elif self.phase == BossPhase.PHASE_3:
            if self._pounce_cooldown <= 0:
                self._pounce_attack()
        elif self.phase == BossPhase.ENRAGE:
            # Acid spray
            self._acid_spray()

    def _pounce_attack(self) -> None:
        """Leap toward the player from a wall or ceiling."""
        self._pounce_cooldown = 6.0
        self._pounce_ready = False

        if self.manager and self.manager.player_ref:
            player_pos = self.manager.player_ref.get_pos(self.render)

            # Move to player quickly
            self._target_position = player_pos
            self._movement_boost = 5.0

            # Reset boost after a delay
            task_name = f"xeno_pounce_{self.id}"
            def reset_boost(task):
                self._movement_boost = 1.0
                return Task.done
            taskMgr.do_method_later(0.5, reset_boost, task_name)

    def _acid_spray(self) -> None:
        """Spray acid in a cone in front of the boss."""
        if self.manager and self.manager.player_ref:
            player_pos = self.manager.player_ref.get_pos(self.render)
            dist = self.node.get_pos().distance(player_pos)

            if dist < 15.0:
                self.manager.apply_damage_to_player(
                    self.current_damage * 0.5,
                    self.node.get_pos(),
                    player_pos,
                )

        # Effect
        if self._body_node:
            seq = Sequence(
                Func(self._body_node.set_color, Vec4(0.3, 1.0, 0.3, 1.0)),
                Wait(0.3),
                Func(self._body_node.set_color, self.enemy_data.color),
            )
            seq.start()

    def _move_toward_point(self, target: Vec3, dt: float) -> None:
        """Override for wall-crawling movement."""
        # In phase 2+, the xenomorph can move on walls
        if self._on_wall and self.phase.value >= BossPhase.PHASE_2.value:
            # Move along wall surfaces (simplified - just allow Z axis movement)
            direction = target - self.node.get_pos()
            direction.normalize()
            speed = self.run_speed * getattr(self, '_movement_boost', 1.0)
            move = direction * speed * dt
            self.node.set_pos(self.node.get_pos() + move)
        else:
            super()._move_toward_point(target, dt)

    def _build_visual_model(self) -> None:
        """Override for alien aesthetic - elongated, segmented body."""
        radius, height = self.enemy_data.size
        color = self.enemy_data.color

        self._visual_root = self.node.attach_new_node("visual")

        # Elongated body (tapered capsule)
        from panda3d.core import Cylinder as P3DCylinder

        body_cyl = P3DCylinder(false, 1.0, 0.0, 1.0, 1.0, True)
        body_geom = body_cyl.get_geom(0)
        body_geom.set_scale(radius, radius, height * 1.5)

        body_node = GeomNode("body")
        body_node.add_geom(body_geom)
        self._body_node = self._visual_root.attach_new_node(body_node)
        self._body_node.set_color(color)
        self._body_node.set_shader_auto()
        self._body_node.set_pos(0, 0, height * 0.4)

        # Carapace ridges
        for i in range(5):
            ridge = self._visual_root.attach_new_node(f"ridge_{i}")
            ridge.set_z(height * 0.3 + i * height * 0.2)
            cm = CardMaker(f"ridge_{i}")
            cm.set_frame(-radius * 0.7, radius * 0.7, -0.1, 0.1)
            ridge_card = ridge.attach_new_node(cm.generate())
            ridge_card.set_color(color * 0.8)
            ridge_card.set_shader_auto()

        # Mandibles (direction indicator)
        self._direction_indicator = self.node.attach_new_node("direction")
        for side in [-1, 1]:
            mandible = self._direction_indicator.attach_new_node(f"mandible_{side}")
            mandible.set_y(side * radius * 0.5)
            mandible.set_z(height * 0.2)
            cm = CardMaker(f"mandible_{side}")
            cm.set_frame(0, radius * 1.5, -0.1, 0.1)
            md = mandible.attach_new_node(cm.generate())
            md.set_color(Vec4(0.2, 0.8, 0.2, 1.0))
            md.set_shader_auto()

        # Boss health bar
        self._create_boss_health_bar()


# ---------------------------------------------------------------------------
# 6. Nightmare Lord
# ---------------------------------------------------------------------------


class NightmareLord(Boss):
    """
    Fantasy Boss

    A demonic entity from nightmares that uses shadow magic, teleportation,
    and summons shadow clones to confuse and overwhelm the player.

    Phase 1: Shadow bolts, minor illusions.
    Phase 2: Shadow clones, teleportation.
    Phase 3: Realm shift - arena distortion, damage amplification.
    Enrage: Full demon form - constant AoE damage and teleportation.

    Special Abilities:
        - Shadow Bolt: Ranged dark magic attack.
        - Shadow Clone: Creates decoy enemies.
        - Teleport: Instantly moves to a new location.
        - Realm Shift: Distorts the arena, making enemies harder to distinguish.
        - Demon Form: Massive stat boost and AoE in enrage.
    """

    ENEMY_DATA = EnemyData(
        name="Nightmare Lord",
        health=1600.0,
        armor=0.25,
        move_speed=5.0,
        run_speed=12.0,
        turn_speed=250.0,
        vision_angle=140.0,
        vision_distance=45.0,
        hearing_distance=40.0,
        accuracy=0.85,
        damage=45.0,
        fire_rate=0.3,
        attack_range=40.0,
        flee_threshold=0.0,
        call_reinforcements=False,
        color=Vec4(0.5, 0.2, 0.8, 1.0),  # Purple/dark magical
        size=(0.9, 2.6),
        weapon_id="shadow_bolt",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shadow_clones: List[Enemy] = []
        self._max_clones: int = 3
        self._clone_count: int = 0
        self._teleport_cooldown: float = 0.0
        self._realm_shift_active: bool = False
        self._demon_form: bool = False

    def _on_phase_change(self, old_phase: BossPhase, new_phase: BossPhase) -> None:
        super()._on_phase_change(old_phase, new_phase)

        if new_phase == BossPhase.PHASE_2:
            self._spawn_shadow_clones()
        elif new_phase == BossPhase.PHASE_3:
            self._activate_realm_shift()
            self._spawn_more_clones()
        elif new_phase == BossPhase.ENRAGE:
            self._activate_demon_form()

    def _spawn_shadow_clones(self) -> None:
        """Spawn shadow clone decoys."""
        for _ in range(2):
            if self._clone_count >= self._max_clones:
                break
            self._create_shadow_clone()

    def _spawn_more_clones(self) -> None:
        """Spawn additional clones in phase 3."""
        while self._clone_count < self._max_clones:
            self._create_shadow_clone()

    def _create_shadow_clone(self) -> None:
        """Create a single shadow clone."""
        if not self.manager:
            return

        # Random position near the boss
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(5, 12)
        offset = Vec3(math.cos(angle) * dist, math.sin(angle) * dist, 0)

        clone_data = EnemyData(
            name="Shadow Clone",
            health=50.0,
            armor=0.0,
            move_speed=8.0,
            run_speed=15.0,
            turn_speed=300.0,
            vision_angle=180.0,
            vision_distance=30.0,
            hearing_distance=30.0,
            accuracy=0.6,
            damage=15.0,
            fire_rate=0.2,
            attack_range=20.0,
            color=Vec4(0.3, 0.1, 0.5, 0.4),  # Semi-transparent
            size=(0.7, 2.2),
        )

        clone = self.manager.spawn_enemy(
            Enemy,
            enemy_data=clone_data,
            position=(offset.x, offset.y, offset.z),
        )

        # Make clone transparent
        if clone._body_node:
            clone._body_node.set_transparency(TransparencyAttrib.M_alpha)
            clone._body_node.set_color(clone_data.color)

        # Clone despawns after a short time
        task_name = f"clone_despawn_{clone.id}"
        def despawn(task):
            clone._die(self.node.get_pos())
            return Task.done
        taskMgr.do_method_later(10.0, despawn, task_name)

        self._shadow_clones.append(clone)
        self._clone_count += 1

    def _activate_realm_shift(self) -> None:
        """Distort the arena - affects visibility."""
        self._realm_shift_active = True
        logger.info("Nightmare Lord: Realm shift activated!")

        if self.manager:
            self.manager.on_sound_event(
                self.node.get_pos(), SoundType.EXPLOSION, radius=50.0
            )

    def _activate_demon_form(self) -> None:
        """Enter full demon form with massive stat boost."""
        self._demon_form = True
        self.current_damage *= 2.0
        self.run_speed *= 1.5
        self.current_accuracy = 1.0

        # Visual transformation
        if self._body_node:
            from direct.interval.IntervalGlobal import LerpColorScaleInterval
            seq = Sequence(
                LerpColorScaleInterval(self._body_node, 0.5, Vec4(1, 0, 0, 1)),
                LerpColorScaleInterval(self._body_node, 0.5, Vec4(1, 0.3, 0.3, 1)),
            )
            seq.start()

    def _use_special_ability(self) -> None:
        """Override for Nightmare Lord abilities."""
        if self._teleport_cooldown <= 0 and random.random() < 0.4:
            self._teleport()

        if self.phase == BossPhase.PHASE_3 and random.random() < 0.3:
            self._spawn_shadow_clones()

    def _teleport(self) -> None:
        """Teleport to a random location near the player."""
        self._teleport_cooldown = 8.0

        if self.manager and self.manager.player_ref:
            player_pos = self.manager.player_ref.get_pos(self.render)

            # Teleport to a position near the player but not too close
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(8, 18)
            offset = Vec3(math.cos(angle) * dist, math.sin(angle) * dist, 0)

            self.node.set_pos(player_pos + offset)

            # Visual effect
            if self._body_node:
                seq = Sequence(
                    Func(self._body_node.set_color_scale, Vec4(0, 0, 0, 1)),
                    Wait(0.1),
                    Func(self._body_node.set_color_scale, Vec4(1, 1, 1, 1)),
                )
                seq.start()

    def _aim_and_fire(self, target_pos: Point3) -> None:
        """Override for shadow bolt attack."""
        self._cooldown_timer -= globalClock.getDt()
        if self._cooldown_timer > 0:
            return

        # Shadow bolt with prediction
        predicted = self._predict_target_position(target_pos)

        if self._weapon is not None and hasattr(self._weapon, 'fire'):
            self._weapon.fire()
        elif self.manager and self.manager.player_ref:
            self.manager.apply_damage_to_player(
                self.current_damage,
                self.node.get_pos(),
                predicted,
            )

        # Visual effect
        if self._body_node:
            seq = Sequence(
                Func(self._body_node.set_color, Vec4(0.3, 0.0, 0.6, 1.0)),
                Wait(0.1),
                Func(self._body_node.set_color, self.enemy_data.color),
            )
            seq.start()

        self._cooldown_timer = 1.0 / self.fire_rate

    def _build_visual_model(self) -> None:
        """Override for demonic aesthetic - horned, floating appearance."""
        radius, height = self.enemy_data.size
        color = self.enemy_data.color

        self._visual_root = self.node.attach_new_node("visual")

        # Main body (tall, with horns)
        from panda3d.core import Cylinder as P3DCylinder

        body_cyl = P3DCylinder(false, 1.0, 0.0, 1.0, 1.0, True)
        body_geom = body_cyl.get_geom(0)
        body_geom.set_scale(radius, radius, height * 1.2)

        body_node = GeomNode("body")
        body_node.add_geom(body_geom)
        self._body_node = self._visual_root.attach_new_node(body_node)
        self._body_node.set_color(color)
        self._body_node.set_shader_auto()
        self._body_node.set_pos(0, 0, height * 0.4)

        # Large horns
        for side in [-1, 1]:
            horn = self._visual_root.attach_new_node(f"horn_{side}")
            horn.set_pos(side * radius * 0.5, 0, height * 1.0)

            horn_vdata = GeomVertexData("horn", GeomVertexFormat.get_v3t2(), Geom.UH_static)
            horn_vertex = GeomVertexWriter(horn_vdata, "vertex")
            horn_vertex.add_data3f(0, 0, 0)
            horn_vertex.add_data3f(side * radius * 0.4, 0, radius * 2)
            horn_vertex.add_data3f(side * radius * 0.6, 0, radius * 1.5)

            horn_prim = GeomTriangle(Geom.UH_static)
            horn_prim.add_vertices(0, 1, 2)
            horn_prim.close_primitive()

            horn_geom = Geom(horn_vdata)
            horn_geom.add_primitive(horn_prim)
            horn_node = GeomNode("horn")
            horn_node.add_geom(horn_geom)
            horn_np = horn.attach_new_node(horn_node)
            horn_np.set_color(Vec4(0.3, 0.1, 0.5, 1.0))
            horn_np.set_shader_auto()

        # Glowing eyes
        for eye_idx in range(2):
            eye = self._visual_root.attach_new_node(f"eye_{eye_idx}")
            eye.set_pos(
                (eye_idx - 0.5) * radius * 0.6,
                radius * 0.8,
                height * 0.8,
            )
            cm = CardMaker(f"eye_{eye_idx}")
            cm.set_frame(-0.2, 0.2, -0.2, 0.2)
            eye_card = eye.attach_new_node(cm.generate())
            eye_card.set_color(Vec4(1.0, 0.0, 0.0, 0.8))  # Red glow
            eye_card.set_billboard_axis()
            eye_card.set_transparency(TransparencyAttrib.M_alpha)

        # Floating effect - no ground clamp
        self._direction_indicator = self.node.attach_new_node("direction")

        # Boss health bar
        self._create_boss_health_bar()


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "BossPhase",
    "Boss",
    "CyberneticOverlord",
    "WarBeast",
    "SecurityCore",
    "Guardian",
    "Xenomorph",
    "NightmareLord",
]
