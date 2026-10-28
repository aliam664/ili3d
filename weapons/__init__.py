"""
Weapon System Package for Panda3D FPS Game.

This package provides a complete weapon system including:
- Base Weapon class with full FPS mechanics (recoil, ADS, fire modes, etc.)
- WeaponManager for inventory, switching, attachments, and mastery tracking
- 15+ weapon definitions across all categories (ARs, pistols, shotguns, snipers, SMGs, heavy, energy, explosives)

Usage:
    from weapons import WeaponManager, WeaponData
    from weapons.weapon_definitions import ALL_WEAPONS

    # Create weapon manager
    manager = WeaponManager(base_node=render, camera=camera)

    # Give player a weapon
    manager.add_weapon("ar_77_viper")

    # Switch to it
    manager.switch_to_weapon("ar_77_viper")

Author: SHARIFA Game Development Team
"""

from weapons.weapon import (
    Weapon,
    WeaponData,
    WeaponState,
    FireMode,
    AmmoType,
    HitResult,
    SurfaceType,
    RecoilKick,
    MuzzleFlashParams,
    ShellCasingParams,
)
from weapons.weapon_manager import (
    WeaponManager,
    WeaponMastery,
    Attachment,
    AttachmentType,
    InventorySlot,
    PickupInfo,
)
from weapons.weapon_definitions import (
    ALL_WEAPON_IDS,
    ALL_WEAPONS,
    WEAPON_CATEGORIES,
    get_weapon_definition,
    get_weapons_by_category,
)

__all__ = [
    # weapon.py exports
    "Weapon",
    "WeaponData",
    "WeaponState",
    "FireMode",
    "AmmoType",
    "HitResult",
    "SurfaceType",
    "RecoilKick",
    "MuzzleFlashParams",
    "ShellCasingParams",
    # weapon_manager.py exports
    "WeaponManager",
    "WeaponMastery",
    "Attachment",
    "AttachmentType",
    "InventorySlot",
    "PickupInfo",
    # weapon_definitions.py exports
    "ALL_WEAPON_IDS",
    "ALL_WEAPONS",
    "WEAPON_CATEGORIES",
    "get_weapon_definition",
    "get_weapons_by_category",
]

__version__ = "1.0.0"
__author__ = "SHARIFA Game Development Team"
