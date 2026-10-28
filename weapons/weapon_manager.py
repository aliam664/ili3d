"""
WeaponManager class for inventory, switching, attachments, and mastery tracking.

The WeaponManager manages:
- Player's weapon inventory (slots, active weapon)
- Weapon switching with draw/stow animations
- Ammo tracking across all weapons
- Weapon pickup and drop mechanics
- Modular weapon attachments (scopes, grips, barrels, etc.)
- Weapon mastery and XP progression

This class integrates with Panda3D's task system and event handling,
working in conjunction with the Weapon class to provide a complete
FPS weapon experience.

Author: SHARIFA Game Development Team
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
from typing import Dict, List, Optional, Tuple, Callable, Any

from panda3d.core import (
    NodePath,
    Vec3,
    Vec4,
    Point3,
    PandaNode,
    BitMask32,
    CollisionTraverser,
    CollisionRay,
    CollisionNode,
    ClockObject,
)

# globalClock is set by ShowBase after initialization.
globalClock = ClockObject.getGlobalClock()

from direct.task.Task import Task
from direct.showbase.DirectObject import DirectObject
from direct.showbase.MessengerGlobal import messenger

from weapons.weapon import (
    Weapon,
    WeaponData,
    WeaponState,
    FireMode,
    AmmoType,
    HitResult,
    SurfaceType,
)


# ---------------------------------------------------------------------------
# Attachment System
# ---------------------------------------------------------------------------

class AttachmentType(Enum):
    """Types of weapon attachments."""

    OPTIC = "optic"        # Scopes, red dots
    BARREL = "barrel"      # Suppressors, flash hiders
    UNDERBARREL = "underbarrel"  # Grips, foregrips, bipods
    MAGAZINE = "magazine"   # Extended mags
    STOCK = "stock"        # Stocks, cheek pads
    LAMINATOR = "laminator"  # Laser, tactical lights


@dataclass
class Attachment:
    """Definition of a weapon attachment.

    Attachments modify weapon stats when equipped.

    Attributes:
        attachment_id:     Unique identifier.
        name:              Display name.
        attachment_type:   Type of attachment (AttachmentType).
        compatible_weapons: List of weapon_ids this attachment works with.
        stat_modifiers:    Dict mapping stat names to modifier multipliers/values.
        description:       Flavor text.
    """

    attachment_id: str = ""
    name: str = ""
    attachment_type: AttachmentType = AttachmentType.OPTIC
    compatible_weapons: List[str] = field(default_factory=list)
    stat_modifiers: Dict[str, float] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "attachment_id": self.attachment_id,
            "name": self.name,
            "attachment_type": self.attachment_type.value,
            "compatible_weapons": self.compatible_weapons,
            "stat_modifiers": self.stat_modifiers,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Attachment":
        """Create an Attachment from a dictionary."""
        return cls(
            attachment_id=data.get("attachment_id", ""),
            name=data.get("name", ""),
            attachment_type=AttachmentType(data.get("attachment_type", "optic")),
            compatible_weapons=data.get("compatible_weapons", []),
            stat_modifiers=data.get("stat_modifiers", {}),
            description=data.get("description", ""),
        )


# Predefined common attachments
ATTACHMENTS: Dict[str, Attachment] = {
    "reflex_scope": Attachment(
        attachment_id="reflex_scope",
        name="Reflex Scope",
        attachment_type=AttachmentType.OPTIC,
        compatible_weapons=[],
        stat_modifiers={
            "accuracy_ads": 1.15,
            "aim_zoom_duration": 0.5,
        },
        description="Close-range reflex sight. Faster ADS, improved accuracy.",
    ),
    "sniper_scope": Attachment(
        attachment_id="sniper_scope",
        name="Sniper Scope 8x",
        attachment_type=AttachmentType.OPTIC,
        compatible_weapons=[],
        stat_modifiers={
            "accuracy_ads": 1.30,
            "aim_fov": 45.0,
            "aim_zoom_duration": 2.0,
        },
        description="High-magnification scope for long-range precision.",
    ),
    "suppressor": Attachment(
        attachment_id="suppressor",
        name="Suppressor",
        attachment_type=AttachmentType.BARREL,
        compatible_weapons=[],
        stat_modifiers={
            "fire_rate": 0.95,
            "recoil_aim_pistol": 0.85,
            "damage": 0.90,
        },
        description="Reduces muzzle flash, sound, and recoil. Slight damage penalty.",
    ),
    "foregrip": Attachment(
        attachment_id="foregrip",
        name="Foregrip",
        attachment_type=AttachmentType.UNDERBARREL,
        compatible_weapons=[],
        stat_modifiers={
            "recoil_aim_rifle": 0.75,
            "accuracy_move": 1.10,
        },
        description="Reduces vertical recoil and improves moving accuracy.",
    ),
    "extended_mag": Attachment(
        attachment_id="extended_mag",
        name="Extended Mag",
        attachment_type=AttachmentType.MAGAZINE,
        compatible_weapons=[],
        stat_modifiers={
            "magazine_size": 1.5,
            "reload_time": 1.2,
        },
        description="Increased magazine capacity. Reload slightly slower.",
    ),
}


# ---------------------------------------------------------------------------
# Weapon Mastery System
# ---------------------------------------------------------------------------

@dataclass
class WeaponMastery:
    """Tracks mastery progress for a single weapon.

    Attributes:
        weapon_id:     The weapon this mastery is for.
        xp:            Total experience points earned.
        level:         Current mastery level (0-100).
        kills:         Total kills with this weapon.
        headshots:     Total headshot kills.
        shots_fired:   Total shots fired.
        shots_hit:     Total shots that hit a target.
        time_used:     Total time (seconds) this weapon was active.
    """

    weapon_id: str = ""
    xp: int = 0
    level: int = 0
    kills: int = 0
    headshots: int = 0
    shots_fired: int = 0
    shots_hit: int = 0
    time_used: float = 0.0

    # XP required for each level
    XP_PER_LEVEL: List[int] = field(default_factory=lambda: [
        100, 250, 450, 700, 1000, 1350, 1750, 2200, 2700, 3250,
        3850, 4500, 5200, 5950, 6750, 7600, 8500, 9450, 10450, 11500,
        12600, 13750, 14950, 16200, 17500, 18850, 20250, 21700, 23200, 24750,
    ])

    @property
    def is_max_level(self) -> bool:
        """Whether this weapon has reached maximum mastery level."""
        return self.level >= len(self.XP_PER_LEVEL)

    @property
    def xp_for_next_level(self) -> int:
        """XP required for the next level, or 0 if max."""
        if self.is_max_level:
            return 0
        return self.XP_PER_LEVEL[self.level]

    @property
    def xp_progress(self) -> float:
        """Progress to next level as a float (0.0 to 1.0)."""
        if self.is_max_level:
            return 1.0
        xp_needed = self.xp_for_next_level
        if xp_needed == 0:
            return 0.0
        xp_at_current = 0
        if self.level > 0:
            xp_at_current = sum(self.XP_PER_LEVEL[:self.level])
        xp_into_level = self.xp - xp_at_current
        return min(1.0, max(0.0, xp_into_level / self.XP_PER_LEVEL[self.level]))

    @property
    def accuracy_rate(self) -> float:
        """Overall accuracy percentage."""
        if self.shots_fired == 0:
            return 0.0
        return (self.shots_hit / self.shots_fired) * 100.0

    @property
    def kdr(self) -> float:
        """Kill/Death ratio."""
        deaths = getattr(self, 'deaths', 0)
        if deaths == 0:
            return float(self.kills)
        return self.kills / deaths

    def add_xp(self, amount: int) -> bool:
        """Add XP to this weapon's mastery.

        Returns:
            True if the weapon leveled up.
        """
        if self.is_max_level:
            return False

        self.xp += amount
        if self.xp >= self._xp_to_next_level():
            self.level_up()
            return True
        return False

    def _xp_to_next_level(self) -> int:
        """Calculate XP needed for the next level."""
        if self.level >= len(self.XP_PER_LEVEL):
            return 0
        return self.XP_PER_LEVEL[self.level]

    def level_up(self) -> None:
        """Increase the mastery level by 1."""
        if self.is_max_level:
            return
        self.level += 1

    def add_kill(self, is_headshot: bool = False) -> None:
        """Record a kill with this weapon."""
        self.kills += 1
        self.shots_hit += 1
        if is_headshot:
            self.headshots += 1
        self.add_xp(10 if is_headshot else 5)

    def record_shot(self, hit: bool) -> None:
        """Record a shot fired with this weapon."""
        self.shots_fired += 1
        if hit:
            self.shots_hit += 1

    def add_usage_time(self, dt: float) -> None:
        """Add time to the total usage timer."""
        self.time_used += dt

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "weapon_id": self.weapon_id,
            "xp": self.xp,
            "level": self.level,
            "kills": self.kills,
            "headshots": self.headshots,
            "shots_fired": self.shots_fired,
            "shots_hit": self.shots_hit,
            "time_used": self.time_used,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WeaponMastery":
        """Deserialize from dictionary."""
        obj = cls(
            weapon_id=data.get("weapon_id", ""),
            xp=data.get("xp", 0),
            level=data.get("level", 0),
            kills=data.get("kills", 0),
            headshots=data.get("headshots", 0),
            shots_fired=data.get("shots_fired", 0),
            shots_hit=data.get("shots_hit", 0),
            time_used=data.get("time_used", 0.0),
        )
        return obj


# ---------------------------------------------------------------------------
# Inventory Slots
# ---------------------------------------------------------------------------

class InventorySlot(IntEnum):
    """Inventory slot indices for weapons."""

    PRIMARY = 0    # Assault rifles, shotguns, snipers, SMGs, heavy, energy
    SECONDARY = 1  # Pistols
    MELEE = 2      # Melee weapons (future)
    GRENADE = 3    # Grenades and explosives
    SPECIAL = 4    # Special items (future)


# ---------------------------------------------------------------------------
# Pickup Info
# ---------------------------------------------------------------------------

@dataclass
class PickupInfo:
    """Information about a weapon pickup.

    Attributes:
        weapon_id:   The weapon definition to pick up.
        position:    World position of the pickup.
        rotation:    World rotation (HPR) of the pickup.
        ammo:        Optional: specific ammo count to pick up (overrides default).
        is_dropped:  Whether this is a dropped weapon (vs. a spawn).
    """

    weapon_id: str = ""
    position: Point3 = field(default_factory=lambda: Point3(0, 0, 0))
    rotation: Vec3 = field(default_factory=lambda: Vec3(0, 0, 0))
    ammo: Optional[int] = None
    is_dropped: bool = False


# ---------------------------------------------------------------------------
# WeaponManager
# ---------------------------------------------------------------------------

class WeaponManager(DirectObject):
    """Central manager for all weapon-related gameplay systems.

    The WeaponManager handles:
    - Maintaining the player's weapon inventory
    - Weapon switching and state management
    - Ammo tracking across all weapons
    - Weapon pickups and drops
    - Attachment equipping/unequipping
    - Weapon mastery and XP tracking
    - FOV management for ADS
    - Sound and effect management

    Args:
        base_node:         The NodePath to attach weapons to (typically a camera/node in the render tree).
        camera:            The camera NodePath for raycasting and FOV control.
        collision_traverser: CollisionTraverser for hit detection.
        max_primary:       Maximum number of primary weapons (default 5).
        max_secondary:     Maximum number of secondary weapons (default 3).

    Attributes:
        inventory:         List of Weapon instances in the player's inventory.
        current_weapon:    The currently active Weapon instance.
        active_index:      Index of the current weapon in the inventory list.
        weapon_mastery:    Dict mapping weapon_id to WeaponMastery.
        attachments:       Dict mapping weapon_id to equipped attachments.
    """

    # Primary weapon categories
    PRIMARY_CATEGORIES = {"assault_rifle", "shotgun", "sniper_rifle", "smg", "heavy", "energy"}
    SECONDARY_CATEGORIES = {"pistol"}
    EXPLOSIVE_CATEGORIES = {"explosive"}

    def __init__(
        self,
        base_node: NodePath,
        camera: NodePath,
        collision_traverser: CollisionTraverser,
        max_primary: int = 5,
        max_secondary: int = 3,
    ):
        DirectObject.__init__(self)

        if base_node is None:
            raise ValueError("base_node cannot be None")
        if camera is None:
            raise ValueError("camera cannot be None")
        if collision_traverser is None:
            raise ValueError("collision_traverser cannot be None")

        self.base_node = base_node
        self.camera = camera
        self.cTrav = collision_traverser
        self.render = base_node.getTop() if not base_node.isEmpty() else base.render

        self.max_primary = max_primary
        self.max_secondary = max_secondary

        # Inventory
        self.inventory: List[Weapon] = []
        self.active_index: int = -1
        self._previous_weapon_index: int = -1

        # State tracking
        self._switch_in_progress: bool = False
        self._switch_timer: float = 0.0
        self._switch_duration: float = 0.5
        self._pending_switch_index: int = -1

        # Weapon instances (lookup by weapon_id)
        self._weapon_instances: Dict[str, Weapon] = {}

        # Global ammo pool
        self._global_ammo_pool: Dict[AmmoType, int] = {}

        # Mastery system
        self.weapon_mastery: Dict[str, WeaponMastery] = {}

        # Attachments (weapon_id -> list of attachment_ids)
        self.attachments: Dict[str, List[str]] = {}

        # FOV management
        self._base_fov: float = 75.0
        self._ads_fov: float = 0.0
        self._fov_lerp_speed: float = 10.0

        # Hit markers
        self._hit_marker_active: bool = False
        self._hit_marker_timer: float = 0.0

        # Input state
        self._input_enabled: bool = True

        # Event prefix
        self._event_prefix = "weapon_manager_"

        # Register tasks
        self._register_tasks()

        # Register events
        self._register_events()

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def current_weapon(self) -> Optional[Weapon]:
        """Return the currently equipped weapon, or None if no weapon is equipped."""
        if 0 <= self.active_index < len(self.inventory):
            return self.inventory[self.active_index]
        return None

    @property
    def has_weapon_equipped(self) -> bool:
        """Whether any weapon is currently equipped."""
        return self.current_weapon is not None

    @property
    def inventory_count(self) -> int:
        """Number of weapons in inventory."""
        return len(self.inventory)

    @property
    def is_switching(self) -> bool:
        """Whether a weapon switch is currently in progress."""
        return self._switch_in_progress

    @property
    def is_ads(self) -> bool:
        """Whether the current weapon is in ADS mode."""
        weapon = self.current_weapon
        if weapon is not None:
            return weapon.is_ads
        return False

    # -----------------------------------------------------------------------
    # Weapon Management
    # -----------------------------------------------------------------------

    def add_weapon(self, weapon_id: str, ammo_override: Optional[int] = None) -> bool:
        """Add a weapon to the player's inventory.

        If the weapon already exists in the inventory, only adds ammo.
        Otherwise, creates a new Weapon instance and adds it.

        Args:
            weapon_id:     The weapon definition identifier.
            ammo_override: Optional override for starting ammo.

        Returns:
            True if the weapon was added successfully, False otherwise.
        """
        if not weapon_id:
            raise ValueError("weapon_id cannot be empty")

        from weapons.weapon_definitions import get_weapon_definition
        try:
            weapon_data = get_weapon_definition(weapon_id)
        except KeyError:
            return False

        # Check if weapon already exists
        for w in self.inventory:
            if w.weapon_data.weapon_id == weapon_id:
                if ammo_override is not None:
                    added = w.add_ammo(ammo_override)
                else:
                    added = w.add_ammo(weapon_data.reserve_ammo)
                if added > 0:
                    self._notify_ammo_pickup(weapon_id, added)
                return True

        # Create new weapon instance
        weapon = self._create_weapon_instance(weapon_data)
        if weapon is None:
            return False

        # Check inventory capacity
        if weapon_data.category in self.PRIMARY_CATEGORIES:
            current_primary = len(self._get_weapons_in_slot(InventorySlot.PRIMARY))
            if current_primary >= self.max_primary:
                self._notify_weapon_pickup_failed(weapon_id)
                return False
        elif weapon_data.category in self.SECONDARY_CATEGORIES:
            current_secondary = len(self._get_weapons_in_slot(InventorySlot.SECONDARY))
            if current_secondary >= self.max_secondary:
                self._notify_weapon_pickup_failed(weapon_id)
                return False

        # Add to inventory
        self.inventory.append(weapon)
        self._weapon_instances[weapon_id] = weapon

        # Initialize mastery if not exists
        if weapon_id not in self.weapon_mastery:
            self.weapon_mastery[weapon_id] = WeaponMastery(weapon_id=weapon_id)

        # Initialize attachments list
        if weapon_id not in self.attachments:
            self.attachments[weapon_id] = []

        # Apply starting ammo override
        if ammo_override is not None:
            weapon.current_ammo = min(ammo_override, weapon_data.magazine_size)
            weapon.reserve_ammo = ammo_override - weapon.current_ammo

        # Auto-switch if no weapon is equipped
        if self.current_weapon is None:
            self.active_index = len(self.inventory) - 1
            self._equip_weapon(self.active_index, instant=True)

        # Notify pickup
        self._notify_weapon_pickup(weapon_id)

        return True

    def remove_weapon(self, weapon_id: str) -> bool:
        """Remove a weapon from inventory (drop or discard).

        Args:
            weapon_id: The weapon identifier to remove.

        Returns:
            True if the weapon was removed, False if not found.
        """
        for i, w in enumerate(self.inventory):
            if w.weapon_data.weapon_id == weapon_id:
                removed_weapon = self.inventory.pop(i)
                if weapon_id in self._weapon_instances:
                    del self._weapon_instances[weapon_id]

                # Adjust active index
                if self.active_index == i:
                    if len(self.inventory) > 0:
                        self.active_index = min(i, len(self.inventory) - 1)
                        self.switch_to_weapon_index(self.active_index, instant=True)
                    else:
                        self.active_index = -1
                elif self.active_index > i:
                    self.active_index -= 1

                # Clean up the weapon
                removed_weapon.cleanup()

                return True

        return False

    def switch_to_weapon(self, weapon_id: str) -> bool:
        """Switch to a specific weapon by ID.

        Args:
            weapon_id: The weapon identifier to switch to.

        Returns:
            True if the switch was initiated.
        """
        for i, w in enumerate(self.inventory):
            if w.weapon_data.weapon_id == weapon_id:
                return self.switch_to_weapon_index(i)
        return False

    def switch_to_weapon_index(self, index: int, instant: bool = False) -> bool:
        """Switch to a weapon by inventory index.

        Args:
            index:  Index in the inventory list.
            instant: If True, skips animation and switches immediately.

        Returns:
            True if the switch was initiated.
        """
        if self._switch_in_progress:
            return False

        if index < 0 or index >= len(self.inventory):
            return False

        if index == self.active_index and not instant:
            return False

        if instant:
            return self._switch_to_index_instant(index)
        else:
            return self._switch_to_index_animated(index)

    def switch_to_next(self) -> bool:
        """Switch to the next weapon in inventory."""
        if len(self.inventory) <= 1:
            return False

        next_index = (self.active_index + 1) % len(self.inventory)
        return self.switch_to_weapon_index(next_index)

    def switch_to_previous(self) -> bool:
        """Switch to the previously held weapon."""
        if len(self.inventory) <= 1:
            return False

        if self._previous_weapon_index >= 0:
            target = self._previous_weapon_index
        else:
            target = (self.active_index - 1) % len(self.inventory)

        return self.switch_to_weapon_index(target)

    def switch_to_slot(self, slot: InventorySlot) -> bool:
        """Switch to the first weapon in a specific inventory slot type.

        Args:
            slot: The InventorySlot to switch to.

        Returns:
            True if switched successfully.
        """
        category_map = {
            InventorySlot.PRIMARY: self.PRIMARY_CATEGORIES,
            InventorySlot.SECONDARY: self.SECONDARY_CATEGORIES,
            InventorySlot.GRENADE: self.EXPLOSIVE_CATEGORIES,
        }

        categories = category_map.get(slot, set())
        for i, w in enumerate(self.inventory):
            if w.weapon_data.category in categories:
                if i == self.active_index:
                    return False
                return self.switch_to_weapon_index(i)

        return False

    # -----------------------------------------------------------------------
    # Firing Input
    # -----------------------------------------------------------------------

    def start_firing(self) -> None:
        """Begin firing the current weapon."""
        if not self._input_enabled or self._switch_in_progress:
            return

        weapon = self.current_weapon
        if weapon is None:
            return

        weapon.start_firing()

    def stop_firing(self) -> None:
        """Stop firing the current weapon."""
        if not self._input_enabled:
            return

        weapon = self.current_weapon
        if weapon is not None:
            weapon.stop_firing()

    def reload(self) -> None:
        """Initiate reload on the current weapon."""
        if not self._input_enabled or self._switch_in_progress:
            return

        weapon = self.current_weapon
        if weapon is not None:
            weapon.reload()

    def toggle_ads(self) -> None:
        """Toggle aim-down-sights on the current weapon."""
        if not self._input_enabled or self._switch_in_progress:
            return

        weapon = self.current_weapon
        if weapon is not None:
            weapon.toggle_ads()

    def aim_down_sights(self) -> None:
        """Enter ADS mode."""
        if not self._input_enabled or self._switch_in_progress:
            return

        weapon = self.current_weapon
        if weapon is not None:
            weapon.aim_down_sights()

    def hip_fire(self) -> None:
        """Exit ADS mode."""
        if not self._input_enabled:
            return

        weapon = self.current_weapon
        if weapon is not None:
            weapon.hip_fire()

    def switch_fire_mode(self) -> None:
        """Cycle fire mode on the current weapon."""
        if not self._input_enabled:
            return

        weapon = self.current_weapon
        if weapon is not None:
            weapon.switch_fire_mode()
            self._notify_fire_mode_change(weapon)

    def melee_attack(self) -> None:
        """Perform a melee attack with the current weapon."""
        if not self._input_enabled:
            return

        weapon = self.current_weapon
        if weapon is None:
            return

        hit_result = self._perform_melee_raycast(weapon)

        if hit_result.hit:
            self._on_melee_hit(hit_result, weapon)

    # -----------------------------------------------------------------------
    # Attachments
    # -----------------------------------------------------------------------

    def equip_attachment(self, weapon_id: str, attachment_id: str) -> bool:
        """Equip an attachment to a weapon.

        Args:
            weapon_id:     The weapon to attach to.
            attachment_id: The attachment to equip.

        Returns:
            True if the attachment was equipped.
        """
        if attachment_id not in ATTACHMENTS:
            return False

        attachment = ATTACHMENTS[attachment_id]

        # Check compatibility
        if attachment.compatible_weapons:
            if weapon_id not in attachment.compatible_weapons:
                return False

        # Initialize attachment list for this weapon
        if weapon_id not in self.attachments:
            self.attachments[weapon_id] = []

        # Check if already equipped
        if attachment_id in self.attachments[weapon_id]:
            return True

        # Check slot conflicts (only one attachment per type)
        for existing_id in self.attachments[weapon_id]:
            existing = ATTACHMENTS.get(existing_id)
            if existing and existing.attachment_type == attachment.attachment_type:
                self.unequip_attachment(weapon_id, existing_id)
                break

        # Equip new attachment
        self.attachments[weapon_id].append(attachment_id)

        # Apply stat modifiers
        self._apply_attachment_modifiers(weapon_id)

        return True

    def unequip_attachment(self, weapon_id: str, attachment_id: str) -> bool:
        """Remove an attachment from a weapon.

        Args:
            weapon_id:     The weapon to unattach from.
            attachment_id: The attachment to remove.

        Returns:
            True if the attachment was removed.
        """
        if weapon_id not in self.attachments:
            return False

        if attachment_id not in self.attachments[weapon_id]:
            return False

        self.attachments[weapon_id].remove(attachment_id)
        self._apply_attachment_modifiers(weapon_id)

        return True

    def get_equipped_attachments(self, weapon_id: str) -> List[str]:
        """Get list of equipped attachment IDs for a weapon.

        Args:
            weapon_id: The weapon to check.

        Returns:
            List of attachment IDs currently equipped.
        """
        return self.attachments.get(weapon_id, []).copy()

    def get_attachment(self, attachment_id: str) -> Optional[Attachment]:
        """Get an Attachment definition by ID.

        Args:
            attachment_id: The attachment identifier.

        Returns:
            The Attachment object, or None if not found.
        """
        return ATTACHMENTS.get(attachment_id)

    def get_all_attachments(self) -> Dict[str, Attachment]:
        """Return all available attachment definitions."""
        return dict(ATTACHMENTS)

    # -----------------------------------------------------------------------
    # Ammo Management
    # -----------------------------------------------------------------------

    def add_ammo(self, ammo_type: AmmoType, amount: int) -> int:
        """Add ammo of a specific type to the global pool.

        Args:
            ammo_type: The type of ammo to add.
            amount:    Number of rounds to add.

        Returns:
            Number of rounds actually added.
        """
        current = self._global_ammo_pool.get(ammo_type, 0)
        max_cap = self._get_ammo_cap(ammo_type)
        added = min(amount, max_cap - current)
        self._global_ammo_pool[ammo_type] = current + added
        return added

    def remove_ammo(self, ammo_type: AmmoType, amount: int) -> bool:
        """Remove ammo from the global pool.

        Args:
            ammo_type: The type of ammo to remove.
            amount:    Number of rounds to remove.

        Returns:
            True if there was enough ammo, False otherwise.
        """
        current = self._global_ammo_pool.get(ammo_type, 0)
        if current < amount:
            return False
        self._global_ammo_pool[ammo_type] = current - amount
        return True

    def get_ammo_count(self, ammo_type: AmmoType) -> int:
        """Get current ammo count for a specific type in the global pool.

        Args:
            ammo_type: The ammo type to check.

        Returns:
            Number of rounds in the global pool.
        """
        return self._global_ammo_pool.get(ammo_type, 0)

    def get_total_ammo(self) -> Dict[AmmoType, int]:
        """Get a dictionary of all ammo types and their counts."""
        return dict(self._global_ammo_pool)

    def refill_all_ammo(self) -> None:
        """Refill all ammo in the global pool to maximum capacity."""
        for ammo_type in AmmoType:
            self._global_ammo_pool[ammo_type] = self._get_ammo_cap(ammo_type)

    def refill_current_weapon_ammo(self) -> None:
        """Refill ammo for the currently equipped weapon."""
        weapon = self.current_weapon
        if weapon is None:
            return

        ammo_type = weapon.weapon_data.ammo_type
        needed = (weapon.weapon_data.magazine_size - weapon.current_ammo) + \
                 (weapon.weapon_data.reserve_ammo - weapon.reserve_ammo)
        self.add_ammo(ammo_type, needed)
        weapon.reserve_ammo = min(
            weapon.weapon_data.reserve_ammo + needed,
            self._get_ammo_cap(ammo_type)
        )

    # -----------------------------------------------------------------------
    # Weapon Pickup/Drop
    # -----------------------------------------------------------------------

    def can_pickup_weapon(self, weapon_id: str) -> bool:
        """Check if the player can pickup a weapon.

        Args:
            weapon_id: The weapon to check.

        Returns:
            True if the weapon can be picked up.
        """
        from weapons.weapon_definitions import get_weapon_definition
        try:
            weapon_data = get_weapon_definition(weapon_id)
        except KeyError:
            return False

        # Check if already have
        for w in self.inventory:
            if w.weapon_data.weapon_id == weapon_id:
                return True  # Can always pickup to replenish ammo

        # Check inventory space
        if weapon_data.category in self.PRIMARY_CATEGORIES:
            current_primary = len(self._get_weapons_in_slot(InventorySlot.PRIMARY))
            if current_primary >= self.max_primary:
                return False
        elif weapon_data.category in self.SECONDARY_CATEGORIES:
            current_secondary = len(self._get_weapons_in_slot(InventorySlot.SECONDARY))
            if current_secondary >= self.max_secondary:
                return False

        return True

    def pickup_weapon(self, weapon_id: str, position: Optional[Point3] = None,
                      ammo_override: Optional[int] = None) -> bool:
        """Pick up a weapon from the world.

        Args:
            weapon_id:     The weapon to pick up.
            position:      World position of the pickup (optional, for effects).
            ammo_override: Starting ammo (optional).

        Returns:
            True if picked up successfully.
        """
        success = self.add_weapon(weapon_id, ammo_override)
        if success and position is not None:
            self._spawn_pickup_effect(position, weapon_id)
        return success

    def drop_current_weapon(self) -> Optional[PickupInfo]:
        """Drop the currently equipped weapon.

        Returns:
            PickupInfo for the dropped weapon, or None if nothing to drop.
        """
        weapon = self.current_weapon
        if weapon is None or len(self.inventory) <= 1:
            return None

        weapon_id = weapon.weapon_data.weapon_id
        position = self.camera.getPos(self.render) + \
                   self.camera.getRelativeVector(self.render, Vec3.forward()) * 2.0

        pickup_info = PickupInfo(
            weapon_id=weapon_id,
            position=position,
            rotation=Vec3(0, 0, 0),
            ammo=weapon.current_ammo + weapon.reserve_ammo,
            is_dropped=True,
        )

        self.remove_weapon(weapon_id)
        return pickup_info

    # -----------------------------------------------------------------------
    # Mastery System
    # -----------------------------------------------------------------------

    def get_mastery(self, weapon_id: str) -> WeaponMastery:
        """Get the mastery data for a weapon.

        Args:
            weapon_id: The weapon to check.

        Returns:
            WeaponMastery object. Creates one if it doesn't exist.
        """
        if weapon_id not in self.weapon_mastery:
            self.weapon_mastery[weapon_id] = WeaponMastery(weapon_id=weapon_id)
        return self.weapon_mastery[weapon_id]

    def get_mastery_level(self, weapon_id: str) -> int:
        """Get the mastery level for a weapon.

        Args:
            weapon_id: The weapon to check.

        Returns:
            Mastery level (0-30).
        """
        return self.get_mastery(weapon_id).level

    def add_mastery_xp(self, weapon_id: str, amount: int) -> bool:
        """Add XP to a weapon's mastery.

        Args:
            weapon_id: The weapon to add XP to.
            amount:    Amount of XP to add.

        Returns:
            True if the weapon leveled up.
        """
        mastery = self.get_mastery(weapon_id)
        return mastery.add_xp(amount)

    def record_kill(self, weapon_id: str, is_headshot: bool = False) -> None:
        """Record a kill with a specific weapon.

        Args:
            weapon_id:  The weapon that scored the kill.
            is_headshot: Whether the kill was a headshot.
        """
        mastery = self.get_mastery(weapon_id)
        mastery.add_kill(is_headshot)

    def record_hit(self, weapon_id: str, is_headshot: bool = False) -> None:
        """Record a hit with a specific weapon.

        Args:
            weapon_id: The weapon that scored the hit.
            is_headshot: Whether the hit was a headshot.
        """
        mastery = self.get_mastery(weapon_id)
        mastery.record_shot(hit=True)
        if is_headshot:
            mastery.add_xp(2)

    def get_mastery_progress(self, weapon_id: str) -> Tuple[int, float]:
        """Get mastery progress information.

        Args:
            weapon_id: The weapon to check.

        Returns:
            Tuple of (current_level, progress_to_next_level as 0.0-1.0).
        """
        mastery = self.get_mastery(weapon_id)
        return (mastery.level, mastery.xp_progress)

    def get_all_mastery_data(self) -> Dict[str, WeaponMastery]:
        """Get all weapon mastery data.

        Returns:
            Dict mapping weapon_id to WeaponMastery.
        """
        return dict(self.weapon_mastery)

    # -----------------------------------------------------------------------
    # Input Management
    # -----------------------------------------------------------------------

    def enable_input(self) -> None:
        """Enable weapon input processing."""
        self._input_enabled = True

    def disable_input(self) -> None:
        """Disable weapon input processing."""
        self._input_enabled = False

    @property
    def is_input_enabled(self) -> bool:
        """Whether weapon input is currently enabled."""
        return self._input_enabled

    # -----------------------------------------------------------------------
    # State Queries
    # -----------------------------------------------------------------------

    def get_current_weapon_id(self) -> Optional[str]:
        """Get the ID of the currently equipped weapon.

        Returns:
            Weapon ID string, or None if no weapon is equipped.
        """
        weapon = self.current_weapon
        if weapon is not None:
            return weapon.weapon_data.weapon_id
        return None

    def get_current_ammo(self) -> Tuple[int, int]:
        """Get ammo status of the current weapon.

        Returns:
            Tuple of (current_magazine, reserve) ammo.
        """
        weapon = self.current_weapon
        if weapon is None:
            return (0, 0)
        return weapon.get_ammo_status()

    def get_current_weapon_state(self) -> WeaponState:
        """Return the state of the current weapon.

        Returns:
            WeaponState enum value.
        """
        weapon = self.current_weapon
        if weapon is None:
            return WeaponState.IDLE
        return weapon.state

    def get_current_fire_mode(self) -> FireMode:
        """Return the current fire mode of the equipped weapon.

        Returns:
            FireMode enum value.
        """
        weapon = self.current_weapon
        if weapon is None:
            return FireMode.SEMI
        return weapon.fire_mode

    def get_hit_marker_status(self) -> bool:
        """Check if a hit marker is currently active.

        Returns:
            True if a hit marker should be displayed.
        """
        return self._hit_marker_active

    def get_base_fov(self) -> float:
        """Return the base (hip-fire) FOV."""
        return self._base_fov

    def get_ads_fov(self) -> float:
        """Return the ADS FOV of the current weapon.

        Returns:
            The ADS FOV delta. Returns 0 if no weapon or no ADS FOV defined.
        """
        weapon = self.current_weapon
        if weapon is None:
            return 0.0
        return weapon.get_ads_fov()

    def get_recoil_offsets(self) -> Tuple[float, float]:
        """Get the current recoil camera offsets.

        Returns:
            Tuple of (yaw_offset, pitch_offset) in degrees.
        """
        weapon = self.current_weapon
        if weapon is None:
            return (0.0, 0.0)
        return weapon.get_recoil_angles()

    # -----------------------------------------------------------------------
    # FOV Management
    # -----------------------------------------------------------------------

    def set_base_fov(self, fov: float) -> None:
        """Set the base (hip-fire) FOV.

        Args:
            fov: The field of view in degrees for hip-firing.
        """
        self._base_fov = fov

    def get_effective_fov(self) -> float:
        """Get the effective FOV based on current ADS state.

        Returns:
            The FOV to set on the camera.
        """
        weapon = self.current_weapon
        if weapon is None:
            return self._base_fov

        if weapon.is_ads and weapon.weapon_data.aim_fov != 0.0:
            # Interpolate between base and ADS FOV
            progress = weapon._ads_progress
            ads_fov = self._base_fov - weapon.weapon_data.aim_fov
            return self._base_fov + (ads_fov - self._base_fov) * progress

        return self._base_fov

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def cleanup(self) -> None:
        """Clean up all weapons and remove all tasks/events."""
        self.disable_input()

        self.ignoreAll()

        # Remove tasks
        taskMgr.removeTasksWithTag(self._event_prefix)

        # Clean up all weapons
        for weapon in self.inventory:
            weapon.cleanup()
        self.inventory.clear()

        self._weapon_instances.clear()
        self.weapon_mastery.clear()
        self.attachments.clear()
        self._global_ammo_pool.clear()

    # -----------------------------------------------------------------------
    # Private: Weapon Creation
    # -----------------------------------------------------------------------

    def _create_weapon_instance(self, weapon_data: WeaponData) -> Optional[Weapon]:
        """Create a Weapon instance from WeaponData.

        Args:
            weapon_data: The weapon definition data.

        Returns:
            A new Weapon instance, or None if creation failed.
        """
        try:
            weapon_parent = self.base_node.attachNewNode(f"wm_{weapon_data.weapon_id}")
            weapon_parent.hide()

            weapon = Weapon(
                weapon_data=weapon_data,
                parent_node=weapon_parent,
                camera=self.camera,
                collision_traverser=self.cTrav,
                render_node=self.render,
            )

            return weapon

        except Exception as e:
            print(f"Error creating weapon '{weapon_data.weapon_id}': {e}")
            return None

    # -----------------------------------------------------------------------
    # Private: Weapon Switching
    # -----------------------------------------------------------------------

    def _switch_to_index_instant(self, index: int) -> bool:
        """Switch to a weapon index without animation."""
        if 0 <= self.active_index < len(self.inventory):
            current = self.inventory[self.active_index]
            current.exit_weapon(0.0)
            if current.view_model:
                current.view_model.hide()

        old_index = self.active_index
        self._previous_weapon_index = self.active_index
        self.active_index = index

        weapon = self.inventory[self.active_index]
        weapon.enter_weapon(0.0)
        if weapon.view_model:
            weapon.view_model.show()

        self._notify_weapon_switched(weapon.weapon_data.weapon_id, old_index, index)

        return True

    def _switch_to_index_animated(self, index: int) -> bool:
        """Switch to a weapon index with animation."""
        if self._switch_in_progress:
            return False

        self._switch_in_progress = True
        self._pending_switch_index = index
        self._switch_timer = 0.0
        self._switch_duration = 0.45

        # Stow current weapon
        if 0 <= self.active_index < len(self.inventory):
            current = self.inventory[self.active_index]
            current.exit_weapon(self._switch_duration * 0.5)

        self._schedule_switch_tasks()

        return True

    def _schedule_switch_tasks(self) -> None:
        """Schedule the weapon switch animation tasks."""
        task_name_hide = f"{self._event_prefix}switch_hide"
        task_name_equip = f"{self._event_prefix}switch_equip"
        task_name_end = f"{self._event_prefix}switch_end"

        taskMgr.doMethodLater(
            self._switch_duration * 0.5,
            self._task_switch_hide,
            task_name_hide,
        )
        taskMgr.doMethodLater(
            self._switch_duration * 0.5,
            self._task_switch_equip,
            task_name_equip,
        )
        taskMgr.doMethodLater(
            self._switch_duration,
            self._task_switch_end,
            task_name_end,
        )

    def _task_switch_hide(self, task: Task) -> Task:
        """Hide the current weapon during switch animation."""
        if 0 <= self.active_index < len(self.inventory):
            current = self.inventory[self.active_index]
            if current.view_model and not current.view_model.isEmpty():
                current.view_model.hide()
        return Task.done

    def _task_switch_equip(self, task: Task) -> Task:
        """Equip and show the new weapon."""
        old_index = self.active_index
        self._previous_weapon_index = self.active_index
        self.active_index = self._pending_switch_index

        if 0 <= self.active_index < len(self.inventory):
            weapon = self.inventory[self.active_index]
            weapon.enter_weapon(0.0)
            if weapon.view_model and not weapon.view_model.isEmpty():
                weapon.view_model.show()

            self._notify_weapon_switched(
                weapon.weapon_data.weapon_id,
                old_index,
                self.active_index,
            )

        return Task.done

    def _task_switch_end(self, task: Task) -> Task:
        """End the weapon switch process."""
        self._switch_in_progress = False
        self._pending_switch_index = -1
        return Task.done

    def _equip_weapon(self, index: int, instant: bool = True) -> None:
        """Immediately equip a weapon at the given index."""
        if index < 0 or index >= len(self.inventory):
            return

        self._previous_weapon_index = self.active_index
        self.active_index = index

        weapon = self.inventory[self.active_index]
        weapon.enter_weapon(0.0 if instant else 0.3)
        if weapon.view_model and not weapon.view_model.isEmpty():
            weapon.view_model.show()

        self._notify_weapon_switched(
            weapon.weapon_data.weapon_id,
            self._previous_weapon_index,
            self.active_index,
        )

    # -----------------------------------------------------------------------
    # Private: Attachment Modifiers
    # -----------------------------------------------------------------------

    def _apply_attachment_modifiers(self, weapon_id: str) -> None:
        """Apply attachment stat modifiers to a weapon instance."""
        weapon = self._weapon_instances.get(weapon_id)
        if weapon is None:
            return

        equipped_ids = self.attachments.get(weapon_id, [])

        # Reset to base values first
        # Note: In a production system, we'd store base values and reapply them
        # For this implementation, we apply multiplicative modifiers

        for att_id in equipped_ids:
            attachment = ATTACHMENTS.get(att_id)
            if attachment is None:
                continue

            data = weapon.weapon_data
            for stat, modifier in attachment.stat_modifiers.items():
                if stat == "damage":
                    data.damage *= modifier
                elif stat == "fire_rate":
                    data.fire_rate *= modifier
                elif stat == "accuracy":
                    data.accuracy *= modifier
                elif stat == "accuracy_ads":
                    data.accuracy_ads *= modifier
                elif stat == "accuracy_move":
                    data.accuracy_move *= modifier
                elif stat == "range":
                    data.range *= modifier
                elif stat == "magazine_size":
                    data.magazine_size = max(1, int(data.magazine_size * modifier))
                elif stat == "reload_time":
                    data.reload_time *= modifier
                elif stat == "reload_time_empty":
                    data.reload_time_empty *= modifier
                elif stat == "recoil_aim_pistol":
                    data.recoil.aim_pistol *= modifier
                elif stat == "recoil_aim_rifle":
                    data.recoil.aim_rifle *= modifier
                elif stat == "aim_fov":
                    data.aim_fov = min(90.0, data.aim_fov + modifier)
                elif stat == "aim_zoom_duration":
                    data.aim_zoom_duration = max(0.01, data.aim_zoom_duration * modifier)

    # -----------------------------------------------------------------------
    # Private: Melee
    # -----------------------------------------------------------------------

    def _perform_melee_raycast(self, weapon: Weapon) -> HitResult:
        """Perform a melee attack raycast.

        Args:
            weapon: The weapon performing the melee attack.

        Returns:
            HitResult of the melee attack.
        """
        result = HitResult()

        try:
            cam_pos = self.camera.getPos(self.render)
            cam_hpr = self.camera.getHpr(self.render)

            ray = CollisionRay()
            ray.setOrigin(cam_pos)
            ray.setDirection(self._hpr_to_vector(cam_hpr))
            ray.setClipAction(CollisionRay.CLAMP)  # Clamp to melee range

            ray_node = CollisionNode(f"{self._event_prefix}melee_ray")
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
                result.surface_type = weapon._detect_surface_type(closest)
                result.entity = closest.getIntoNode() if closest.getIntoNode() else None
                result.damage_multiplier = 1.0

            ray_np.removeNode()
        except Exception:
            pass

        return result

    def _on_melee_hit(self, hit: HitResult, weapon: Weapon) -> None:
        """Handle a melee hit.

        Args:
            hit:   The hit result.
            weapon: The weapon that performed the melee.
        """
        mastery = self.get_mastery(weapon.weapon_data.weapon_id)
        mastery.record_shot(hit=True)

        weapon._spawn_hit_effects(hit)

    # -----------------------------------------------------------------------
    # Private: Task Registration
    # -----------------------------------------------------------------------

    def _register_tasks(self) -> None:
        """Register recurring tasks."""
        def update_task(task: Task) -> Task:
            dt = globalClock.getDt()
            self._update(dt)
            return Task.cont

        task_name = f"{self._event_prefix}main_update"
        self._update_task_name = task_name
        taskMgr.add(update_task, task_name, sort=35)

    def _register_events(self) -> None:
        """Register event listeners."""
        self.accept("weapon_hit", self._on_weapon_hit)
        self.accept("weapon_kill", self._on_weapon_kill)

    # -----------------------------------------------------------------------
    # Private: Update
    # -----------------------------------------------------------------------

    def _update(self, dt: float) -> None:
        """Main update method called every frame.

        Args:
            dt: Delta time in seconds.
        """
        weapon = self.current_weapon

        # Update hit markers
        if self._hit_marker_timer > 0:
            self._hit_marker_timer -= dt
            if self._hit_marker_timer <= 0:
                self._hit_marker_active = False

        # Track usage time for mastery
        if weapon is not None:
            weapon_id = weapon.weapon_data.weapon_id
            if weapon_id in self.weapon_mastery:
                self.weapon_mastery[weapon_id].add_usage_time(dt)

    # -----------------------------------------------------------------------
    # Private: Event Handlers
    # -----------------------------------------------------------------------

    def _on_weapon_hit(self, weapon_id: str, hit_result: Any) -> None:
        """Handle weapon hit events from the Weapon class.

        Args:
            weapon_id:   The weapon that caused the hit.
            hit_result:  HitResult data.
        """
        if weapon_id not in self.weapon_mastery:
            return

        mastery = self.weapon_mastery[weapon_id]
        mastery.record_shot(hit=True)

        if getattr(hit_result, 'is_headshot', False):
            self._show_hit_marker(critical=True)
        else:
            self._show_hit_marker()

    def _on_weapon_kill(self, weapon_id: str, kill_info: Any) -> None:
        """Handle weapon kill events.

        Args:
            weapon_id:   The weapon that scored the kill.
            kill_info:   Kill information (is_headshot, etc.).
        """
        is_headshot = getattr(kill_info, 'is_headshot', False) if kill_info else False

        self.record_kill(weapon_id, is_headshot)

        xp_gained = 50 if is_headshot else 25
        leveled_up = self.add_mastery_xp(weapon_id, xp_gained)

        if leveled_up:
            self._notify_level_up(weapon_id)

    def _show_hit_marker(self, critical: bool = False) -> None:
        """Display a hit marker on screen.

        Args:
            critical: If True, shows a critical/headshot hit marker.
        """
        self._hit_marker_active = True
        self._hit_marker_timer = 0.3 if critical else 0.2

    def _notify_level_up(self, weapon_id: str) -> None:
        """Notify that a weapon has leveled up.

        Args:
            weapon_id: The weapon that leveled up.
        """
        pass

    # -----------------------------------------------------------------------
    # Private: Notification System
    # -----------------------------------------------------------------------

    def _notify_weapon_switched(self, weapon_id: str, old_index: int, new_index: int) -> None:
        """Notify listeners of a weapon switch."""
        messenger.send(f"{self._event_prefix}weapon_switched", [weapon_id, old_index, new_index])

    def _notify_weapon_pickup(self, weapon_id: str) -> None:
        """Notify listeners of a weapon pickup."""
        messenger.send(f"{self._event_prefix}weapon_pickup", [weapon_id])

    def _notify_weapon_pickup_failed(self, weapon_id: str) -> None:
        """Notify listeners of a failed weapon pickup."""
        messenger.send(f"{self._event_prefix}weapon_pickup_failed", [weapon_id])

    def _notify_ammo_pickup(self, weapon_id: str, amount: int) -> None:
        """Notify listeners of an ammo pickup."""
        messenger.send(f"{self._event_prefix}ammo_pickup", [weapon_id, amount])

    def _notify_fire_mode_change(self, weapon: Weapon) -> None:
        """Notify listeners of a fire mode change."""
        mode_name = weapon.fire_mode.value
        messenger.send(f"{self._event_prefix}fire_mode_change", [weapon.weapon_data.weapon_id, mode_name])

    # -----------------------------------------------------------------------
    # Private: Utility
    # -----------------------------------------------------------------------

    def _get_weapons_in_slot(self, slot: InventorySlot) -> List[Weapon]:
        """Get all weapons in a specific inventory slot type."""
        category_map = {
            InventorySlot.PRIMARY: self.PRIMARY_CATEGORIES,
            InventorySlot.SECONDARY: self.SECONDARY_CATEGORIES,
            InventorySlot.GRENADE: self.EXPLOSIVE_CATEGORIES,
        }

        categories = category_map.get(slot, set())
        return [w for w in self.inventory if w.weapon_data.category in categories]

    def _get_ammo_cap(self, ammo_type: AmmoType) -> int:
        """Get the maximum ammo capacity for a given ammo type."""
        caps = {
            AmmoType.NORMAL: 500,
            AmmoType.ARMOR_PIERCING: 200,
            AmmoType.INCENDIARY: 200,
            AmmoType.EXPLOSIVE: 10,
            AmmoType.ENERGY: 400,
            AmmoType.PLASMA: 300,
            AmmoType.SHOTGUN: 64,
        }
        return caps.get(ammo_type, 100)

    def _hpr_to_vector(self, hpr: Vec3) -> Vec3:
        """Convert an HPR orientation to a direction vector."""
        temp_node = NodePath("temp_dir")
        temp_node.setHpr(hpr)
        direction = temp_node.getRelativeVector(self.render, Vec3.forward())
        temp_node.removeNode()
        return direction

    def _spawn_pickup_effect(self, position: Point3, weapon_id: str) -> None:
        """Spawn a visual effect for picking up a weapon."""
        try:
            from direct.particles.ParticleEffect import ParticleEffect
            from direct.particles.Particles import Particles

            effect = ParticleEffect()
            particles = Particles()
            particles.setFactory("PointParticleFactory")
            particles.setRenderer("SpriteParticleRenderer")
            particles.setEmitter("RingEmitter")

            particles.setEmissionType(0)
            particles.setLifespanBase(0.5)
            particles.setLifespanSpread(0.2)
            particles.setInitialXScale(0.1)
            particles.setInitialYScale(0.1)
            particles.setFinalXScale(0.0)
            particles.setFinalYScale(0.0)

            particles.setPoolSize(10)
            particles.setBirthRate(0.05)

            emitter = particles.getEmitter()
            emitter.setRadius(0.5)

            effect.addParticles(particles)
            effect.start(pos=position, renderParent=self.render)

            def cleanup(task):
                try:
                    effect.disable()
                    effect.cleanup()
                except Exception:
                    pass
                return Task.done

            task_name = f"{self._event_prefix}pickup_effect_{id(effect)}"
            taskMgr.doMethodLater(1.0, cleanup, task_name)
        except Exception:
            pass
