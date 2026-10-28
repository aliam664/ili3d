"""
Complete weapon definitions for the Panda3D FPS weapon system.

This module defines all weapon configurations across all categories:

Assault Rifles:
    - AR-77 "Viper"      - Balanced assault rifle
    - AR-99 "Reaper"     - High damage assault rifle
    - AR-SMG "Wasp"      - SMG variant assault rifle

Pistols:
    - PX4 "Striker"      - Standard semi-automatic pistol
    - Magnum "Python"    - High damage revolver
    - Auto Pistol "Raven"- Fully automatic pistol

Shotguns:
    - M87 "Pump"         - Pump-action shotgun
    - AA12 "Auto"        - Automatic combat shotgun

Sniper Rifles:
    - SRS "Longshot"     - Bolt-action sniper rifle
    - DMR-12 "Sentinel"  - Semi-automatic marksman rifle

SMGs:
    - MP7 "Storm"        - Compact submachine gun
    - P90 "Typhoon"      - High-capacity bullpup SMG

Heavy Weapons:
    - M5 "Thumper"       - Grenade launcher
    - Minigun "Annihilator" - Rotary heavy weapon

Energy Weapons:
    - Laser Rifle "Solaris"  - Energy assault rifle
    - Plasma Rifle "Nova"    - Energy weapon with splash damage

Explosives:
    - Frag Grenade           - Throwable explosive
    - C4                     - Placeable explosive charge
    - Proximity Mine         - Automatically detonated mine

Each weapon is defined as a WeaponData instance with unique stats, fire modes,
recoil patterns, visual effects, sound profiles, and procedural model parameters.

Author: SHARIFA Game Development Team
"""

from __future__ import annotations

from typing import Dict, List
from panda3d.core import Vec4, Vec3

from weapons.weapon import (
    WeaponData,
    WeaponState,
    FireMode,
    AmmoType,
    SurfaceType,
    RecoilKick,
    MuzzleFlashParams,
    ShellCasingParams,
)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _hit_sound(surface: SurfaceType, path: str) -> Dict[SurfaceType, str]:
    """Create a hit_sounds dict entry for a single surface type."""
    return {surface: path}


def _all_hit_sounds(
    flesh: str = "", metal: str = "", wood: str = "",
    concrete: str = "", glass: str = "", water: str = ""
) -> Dict[SurfaceType, str]:
    """Create a complete hit_sounds dictionary."""
    result = {}
    if flesh:
        result[SurfaceType.FLESH] = flesh
    if metal:
        result[SurfaceType.METAL] = metal
    if wood:
        result[SurfaceType.WOOD] = wood
    if concrete:
        result[SurfaceType.CONCRETE] = concrete
    if glass:
        result[SurfaceType.GLASS] = glass
    if water:
        result[SurfaceType.WATER] = water
    return result


# ---------------------------------------------------------------------------
# Weapon Definitions
# ---------------------------------------------------------------------------

# ===========================================================================
# ASSAULT RIFLES
# ===========================================================================

# AR-77 "Viper" - Balanced assault rifle
# Description: A versatile, well-rounded assault rifle. Good for medium-range
# engagements with controllable recoil and reliable performance.
AR_77_VIPER = WeaponData(
    weapon_id="ar_77_viper",
    name="AR-77 'Viper'",
    category="assault_rifle",
    damage=32.0,
    fire_rate=750.0,          # rounds per minute
    accuracy=0.85,
    accuracy_ads=0.97,
    accuracy_move=0.65,
    range=900.0,
    magazine_size=30,
    reserve_ammo=120,
    reload_time=2.2,
    reload_time_empty=2.7,
    ammo_type=AmmoType.NORMAL,
    fire_modes=[FireMode.SEMI, FireMode.AUTO],
    default_fire_mode=FireMode.AUTO,
    burst_count=3,
    recoil=RecoilKick(
        aim_pistol=0.6,
        aim_rifle=1.2,
        ads_multiplier=0.35,
        horizontal_min=0.3,
        horizontal_max=1.2,
        vertical_min=0.8,
        vertical_max=1.8,
        return_speed=7.5,
        smoothness=0.65,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.75, 0.35, 1.0),
        scale=0.25,
        duration=0.045,
        brightness=1.0,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.85, 0.78, 0.25, 1.0),  # Brass
        scale=0.12,
        eject_velocity=Vec3(3, 4, -4),
        lifetime=6.0,
        gravity=1.2,
    ),
    aim_fov=25.0,
    aim_offset=Vec3(0.0, 0.6, -0.25),
    aim_zoom_duration=0.15,
    shot_sound="sounds/weapons/ar_77/fire.ogg",
    reload_sound="sounds/weapons/ar_77/reload.ogg",
    dry_fire_sound="sounds/weapons/ar_77/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/ar_77/hit_flesh.ogg",
        metal="sounds/weapons/ar_77/hit_metal.ogg",
        wood="sounds/weapons/ar_77/hit_wood.ogg",
        concrete="sounds/weapons/ar_77/hit_concrete.ogg",
    ),
    melee_damage=30.0,
    melee_range=2.0,
    model_color=Vec4(0.3, 0.3, 0.35, 1.0),
    model_shape="barrel",
    model_dimensions=(0.28, 0.2, 1.0),
    description="A versatile, well-rounded assault rifle. Good for medium-range engagements.",
)


# AR-99 "Reaper" - High damage assault rifle
# Description: Heavy-hitting assault rifle with significant recoil.
# Devastating at close to medium range but requires skill to master.
AR_99_REAPER = WeaponData(
    weapon_id="ar_99_reaper",
    name="AR-99 'Reaper'",
    category="assault_rifle",
    damage=45.0,
    fire_rate=580.0,
    accuracy=0.80,
    accuracy_ads=0.95,
    accuracy_move=0.55,
    range=1000.0,
    magazine_size=25,
    reserve_ammo=100,
    reload_time=2.8,
    reload_time_empty=3.2,
    ammo_type=AmmoType.NORMAL,
    fire_modes=[FireMode.SEMI, FireMode.AUTO],
    default_fire_mode=FireMode.AUTO,
    burst_count=3,
    recoil=RecoilKick(
        aim_pistol=0.5,
        aim_rifle=2.2,
        ads_multiplier=0.50,
        horizontal_min=0.8,
        horizontal_max=2.0,
        vertical_min=1.8,
        vertical_max=3.5,
        return_speed=6.0,
        smoothness=0.55,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.5, 0.15, 1.0),
        scale=0.35,
        duration=0.06,
        brightness=1.2,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.9, 0.82, 0.28, 1.0),
        scale=0.15,
        eject_velocity=Vec3(4, 5, -2),
        lifetime=7.0,
        gravity=1.5,
    ),
    aim_fov=30.0,
    aim_offset=Vec3(0.0, 0.8, -0.3),
    aim_zoom_duration=0.18,
    shot_sound="sounds/weapons/ar_99/fire.ogg",
    reload_sound="sounds/weapons/ar_99/reload.ogg",
    dry_fire_sound="sounds/weapons/ar_99/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/ar_99/hit_flesh.ogg",
        metal="sounds/weapons/ar_99/hit_metal.ogg",
        wood="sounds/weapons/ar_99/hit_wood.ogg",
        concrete="sounds/weapons/ar_99/hit_concrete.ogg",
    ),
    melee_damage=40.0,
    melee_range=2.0,
    model_color=Vec4(0.2, 0.2, 0.25, 1.0),
    model_shape="barrel",
    model_dimensions=(0.32, 0.22, 1.1),
    description="Heavy-hitting assault rifle with significant recoil. Devastating but hard to control.",
)


# AR-SMG "Wasp" - SMG variant assault rifle
# Description: A hybrid weapon combining assault rifle range with SMG fire rate.
# Lightweight with excellent mobility.
AR_SMG_WASP = WeaponData(
    weapon_id="ar_smg_wasp",
    name="AR-SMG 'Wasp'",
    category="assault_rifle",
    damage=22.0,
    fire_rate=1100.0,
    accuracy=0.70,
    accuracy_ads=0.90,
    accuracy_move=0.70,
    range=600.0,
    magazine_size=40,
    reserve_ammo=160,
    reload_time=1.8,
    reload_time_empty=2.2,
    ammo_type=AmmoType.NORMAL,
    fire_modes=[FireMode.SEMI, FireMode.BURST, FireMode.AUTO],
    default_fire_mode=FireMode.AUTO,
    burst_count=5,
    recoil=RecoilKick(
        aim_pistol=0.4,
        aim_rifle=1.8,
        ads_multiplier=0.45,
        horizontal_min=0.5,
        horizontal_max=1.8,
        vertical_min=0.6,
        vertical_max=2.2,
        return_speed=9.0,
        smoothness=0.75,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.8, 0.3, 1.0),
        scale=0.22,
        duration=0.035,
        brightness=0.9,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.9, 0.82, 0.3, 1.0),
        scale=0.1,
        eject_velocity=Vec3(3, 8, -3),
        lifetime=5.0,
        gravity=1.0,
    ),
    aim_fov=20.0,
    aim_offset=Vec3(0.0, 0.4, -0.2),
    aim_zoom_duration=0.12,
    shot_sound="sounds/weapons/ar_smg_wasp/fire.ogg",
    reload_sound="sounds/weapons/ar_smg_wasp/reload.ogg",
    dry_fire_sound="sounds/weapons/ar_smg_wasp/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/ar_smg_wasp/hit_flesh.ogg",
        metal="sounds/weapons/ar_smg_wasp/hit_metal.ogg",
    ),
    melee_damage=25.0,
    melee_range=2.0,
    model_color=Vec4(0.4, 0.4, 0.42, 1.0),
    model_shape="barrel",
    model_dimensions=(0.25, 0.18, 0.85),
    description="SMG variant with hybrid capabilities. High fire rate, lower damage.",
)


# ===========================================================================
# PISTOLS
# ===========================================================================

# PX4 "Striker" - Standard pistol
PX4_STARER = WeaponData(
    weapon_id="px4_striker",
    name="PX4 'Striker'",
    category="pistol",
    damage=35.0,
    fire_rate=450.0,
    accuracy=0.80,
    accuracy_ads=0.92,
    accuracy_move=0.70,
    range=400.0,
    magazine_size=15,
    reserve_ammo=45,
    reload_time=1.5,
    reload_time_empty=1.8,
    ammo_type=AmmoType.NORMAL,
    fire_modes=[FireMode.SEMI],
    default_fire_mode=FireMode.SEMI,
    recoil=RecoilKick(
        aim_pistol=1.5,
        aim_rifle=0.5,
        ads_multiplier=0.50,
        horizontal_min=0.2,
        horizontal_max=0.8,
        vertical_min=1.0,
        vertical_max=2.0,
        return_speed=12.0,
        smoothness=0.7,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(0.9, 0.6, 0.25, 1.0),
        scale=0.18,
        duration=0.04,
        brightness=0.8,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.88, 0.8, 0.28, 1.0),
        scale=0.1,
        eject_velocity=Vec3(2, 3, -2),
        lifetime=4.0,
        gravity=1.0,
    ),
    aim_fov=15.0,
    aim_offset=Vec3(0.0, 0.3, -0.15),
    aim_zoom_duration=0.1,
    shot_sound="sounds/weapons/px4_striker/fire.ogg",
    reload_sound="sounds/weapons/px4_striker/reload.ogg",
    dry_fire_sound="sounds/weapons/px4_striker/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/px4_striker/hit_flesh.ogg",
        metal="sounds/weapons/px4_striker/hit_metal.ogg",
    ),
    melee_damage=25.0,
    melee_range=1.5,
    model_color=Vec4(0.25, 0.25, 0.28, 1.0),
    model_shape="box",
    model_dimensions=(0.15, 0.12, 0.28),
    description="Reliable standard-issue pistol with balanced performance.",
)


# Magnum "Python" - High damage pistol
MAGNUM_PYTHON = WeaponData(
    weapon_id="magnum_python",
    name="Magnum 'Python'",
    category="pistol",
    damage=75.0,
    fire_rate=200.0,
    accuracy=0.90,
    accuracy_ads=0.98,
    accuracy_move=0.60,
    range=600.0,
    magazine_size=6,
    reserve_ammo=24,
    reload_time=2.5,
    reload_time_empty=3.0,
    ammo_type=AmmoType.NORMAL,
    fire_modes=[FireMode.SEMI],
    default_fire_mode=FireMode.SEMI,
    recoil=RecoilKick(
        aim_pistol=2.5,
        aim_rifle=0.3,
        ads_multiplier=0.60,
        horizontal_min=0.1,
        horizontal_max=0.5,
        vertical_min=2.5,
        vertical_max=4.0,
        return_speed=10.0,
        smoothness=0.8,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.6, 0.2, 1.0),
        scale=0.35,
        duration=0.07,
        brightness=1.3,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.85, 0.78, 0.25, 1.0),
        scale=0.18,
        eject_velocity=Vec3(2, 3, -2),
        lifetime=6.0,
        gravity=1.3,
    ),
    aim_fov=20.0,
    aim_offset=Vec3(0.0, 0.5, -0.2),
    aim_zoom_duration=0.12,
    shot_sound="sounds/weapons/magnum_python/fire.ogg",
    reload_sound="sounds/weapons/magnum_python/reload.ogg",
    dry_fire_sound="sounds/weapons/magnum_python/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/magnum_python/hit_flesh.ogg",
        metal="sounds/weapons/magnum_python/hit_metal.ogg",
        concrete="sounds/weapons/magnum_python/hit_concrete.ogg",
    ),
    melee_damage=40.0,
    melee_range=1.8,
    model_color=Vec4(0.4, 0.35, 0.3, 1.0),
    model_shape="box",
    model_dimensions=(0.18, 0.15, 0.32),
    description="High-damage revolver. Devastating at close range but slow to fire.",
)


# Auto Pistol "Raven" - Automatic pistol
AUTO_PISTOL_RAVEN = WeaponData(
    weapon_id="auto_pistol_raven",
    name="Auto Pistol 'Raven'",
    category="pistol",
    damage=28.0,
    fire_rate=900.0,
    accuracy=0.72,
    accuracy_ads=0.88,
    accuracy_move=0.65,
    range=350.0,
    magazine_size=20,
    reserve_ammo=60,
    reload_time=1.6,
    reload_time_empty=2.0,
    ammo_type=AmmoType.NORMAL,
    fire_modes=[FireMode.SEMI, FireMode.AUTO],
    default_fire_mode=FireMode.AUTO,
    recoil=RecoilKick(
        aim_pistol=1.2,
        aim_rifle=1.8,
        ads_multiplier=0.55,
        horizontal_min=0.4,
        horizontal_max=1.2,
        vertical_min=0.8,
        vertical_max=1.8,
        return_speed=11.0,
        smoothness=0.7,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(0.9, 0.55, 0.2, 1.0),
        scale=0.2,
        duration=0.045,
        brightness=0.9,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.88, 0.8, 0.28, 1.0),
        scale=0.11,
        eject_velocity=Vec3(3, 5, -3),
        lifetime=4.5,
        gravity=1.1,
    ),
    aim_fov=12.0,
    aim_offset=Vec3(0.0, 0.35, -0.15),
    aim_zoom_duration=0.1,
    shot_sound="sounds/weapons/auto_pistol_raven/fire.ogg",
    reload_sound="sounds/weapons/auto_pistol_raven/reload.ogg",
    dry_fire_sound="sounds/weapons/auto_pistol_raven/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/auto_pistol_raven/hit_flesh.ogg",
        metal="sounds/weapons/auto_pistol_raven/hit_metal.ogg",
    ),
    melee_damage=30.0,
    melee_range=1.5,
    model_color=Vec4(0.2, 0.2, 0.22, 1.0),
    model_shape="barrel",
    model_dimensions=(0.15, 0.12, 0.26),
    description="Compact automatic pistol. High fire rate for close-quarters combat.",
)


# ===========================================================================
# SHOTGUNS
# ===========================================================================

# M87 "Pump" - Pump action shotgun
M87_PUMP = WeaponData(
    weapon_id="m87_pump",
    name="M87 'Pump'",
    category="shotgun",
    damage=18.0,          # Per pellet
    fire_rate=90.0,       # Pump shotguns are slow
    accuracy=0.60,        # Spread is handled via low accuracy
    accuracy_ads=0.85,
    accuracy_move=0.40,
    range=300.0,
    magazine_size=6,      # 6 shells (1 in chamber + 5 in tube)
    reserve_ammo=30,
    reload_time=0.5,      # Per shell, reloads one at a time
    reload_time_empty=2.8,  # Full reload when empty
    ammo_type=AmmoType.SHOTGUN,
    fire_modes=[FireMode.SEMI],
    default_fire_mode=FireMode.SEMI,
    recoil=RecoilKick(
        aim_pistol=0.3,
        aim_rifle=3.0,
        ads_multiplier=0.60,
        horizontal_min=0.5,
        horizontal_max=1.8,
        vertical_min=3.5,
        vertical_max=5.5,
        return_speed=5.5,
        smoothness=0.45,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.8, 0.25, 1.0),
        scale=0.5,
        duration=0.08,
        brightness=1.5,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.9, 0.82, 0.25, 1.0),
        scale=0.2,
        eject_velocity=Vec3(3, 4, -3),
        lifetime=7.0,
        gravity=1.2,
    ),
    aim_fov=10.0,
    aim_offset=Vec3(0.0, 0.5, -0.2),
    aim_zoom_duration=0.15,
    shot_sound="sounds/weapons/m87_pump/fire.ogg",
    reload_sound="sounds/weapons/m87_pump/reload.ogg",
    dry_fire_sound="sounds/weapons/m87_pump/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/m87_pump/hit_flesh.ogg",
        metal="sounds/weapons/m87_pump/hit_metal.ogg",
        wood="sounds/weapons/m87_pump/hit_wood.ogg",
    ),
    melee_damage=50.0,
    melee_range=2.0,
    model_color=Vec4(0.3, 0.3, 0.3, 1.0),
    model_shape="barrel",
    model_dimensions=(0.3, 0.25, 0.75),
    description="Classic pump-action shotgun. Devastating at close range with wide spread.",
)


# AA12 "Auto" - Automatic combat shotgun
AA12_AUTO = WeaponData(
    weapon_id="aa12_auto",
    name="AA12 'Auto'",
    category="shotgun",
    damage=15.0,
    fire_rate=400.0,
    accuracy=0.55,
    accuracy_ads=0.80,
    accuracy_move=0.45,
    range=280.0,
    magazine_size=20,
    reserve_ammo=40,
    reload_time=3.0,
    reload_time_empty=3.5,
    ammo_type=AmmoType.SHOTGUN,
    fire_modes=[FireMode.SEMI, FireMode.AUTO],
    default_fire_mode=FireMode.AUTO,
    recoil=RecoilKick(
        aim_pistol=0.3,
        aim_rifle=2.8,
        ads_multiplier=0.70,
        horizontal_min=0.8,
        horizontal_max=2.5,
        vertical_min=2.5,
        vertical_max=4.5,
        return_speed=6.5,
        smoothness=0.4,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.7, 0.2, 1.0),
        scale=0.45,
        duration=0.07,
        brightness=1.4,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.88, 0.8, 0.25, 1.0),
        scale=0.18,
        eject_velocity=Vec3(4, 5, -3),
        lifetime=6.0,
        gravity=1.3,
    ),
    aim_fov=15.0,
    aim_offset=Vec3(0.0, 0.6, -0.25),
    aim_zoom_duration=0.15,
    shot_sound="sounds/weapons/aa12_auto/fire.ogg",
    reload_sound="sounds/weapons/aa12_auto/reload.ogg",
    dry_fire_sound="sounds/weapons/aa12_auto/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/aa12_auto/hit_flesh.ogg",
        metal="sounds/weapons/aa12_auto/hit_metal.ogg",
    ),
    melee_damage=45.0,
    melee_range=2.0,
    model_color=Vec4(0.35, 0.35, 0.38, 1.0),
    model_shape="barrel",
    model_dimensions=(0.32, 0.24, 0.85),
    description="Fully automatic combat shotgun. High fire rate for area saturation.",
)


# ===========================================================================
# SNIPER RIFLES
# ===========================================================================

# SRS "Longshot" - Bolt action sniper
SRS_LONGSHOT = WeaponData(
    weapon_id="srs_longshot",
    name="SRS 'Longshot'",
    category="sniper_rifle",
    damage=85.0,
    fire_rate=40.0,       # Very slow, one shot per second
    accuracy=0.99,
    accuracy_ads=0.999,
    accuracy_move=0.30,
    range=2000.0,
    magazine_size=5,
    reserve_ammo=15,
    reload_time=2.5,
    reload_time_empty=3.0,
    ammo_type=AmmoType.ARMOR_PIERCING,
    fire_modes=[FireMode.SEMI],
    default_fire_mode=FireMode.SEMI,
    recoil=RecoilKick(
        aim_pistol=0.1,
        aim_rifle=3.5,
        ads_multiplier=0.20,
        horizontal_min=0.2,
        horizontal_max=0.8,
        vertical_min=2.5,
        vertical_max=4.5,
        return_speed=4.0,
        smoothness=0.3,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(0.8, 0.9, 1.0, 1.0),
        scale=0.4,
        duration=0.1,
        brightness=1.5,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.85, 0.8, 0.25, 1.0),
        scale=0.2,
        eject_velocity=Vec3(1, 3, -2),
        lifetime=8.0,
        gravity=1.0,
    ),
    aim_fov=65.0,
    aim_offset=Vec3(0.0, 1.0, -0.4),
    aim_zoom_duration=0.3,
    shot_sound="sounds/weapons/srs_longshot/fire.ogg",
    reload_sound="sounds/weapons/srs_longshot/reload.ogg",
    dry_fire_sound="sounds/weapons/srs_longshot/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/srs_longshot/hit_flesh.ogg",
        metal="sounds/weapons/srs_longshot/hit_metal.ogg",
        concrete="sounds/weapons/srs_longshot/hit_concrete.ogg",
    ),
    melee_damage=35.0,
    melee_range=2.5,
    model_color=Vec4(0.25, 0.25, 0.3, 1.0),
    model_shape="barrel",
    model_dimensions=(0.35, 0.2, 1.3),
    description="Precision bolt-action sniper rifle. One shot, one kill at long range.",
)


# DMR-12 "Sentinel" - Semi-auto marksman rifle
DMR_12_SENTINEL = WeaponData(
    weapon_id="dmr_12_sentinel",
    name="DMR-12 'Sentinel'",
    category="sniper_rifle",
    damage=60.0,
    fire_rate=240.0,
    accuracy=0.92,
    accuracy_ads=0.995,
    accuracy_move=0.45,
    range=1200.0,
    magazine_size=10,
    reserve_ammo=30,
    reload_time=2.0,
    reload_time_empty=2.4,
    ammo_type=AmmoType.ARMOR_PIERCING,
    fire_modes=[FireMode.SEMI],
    default_fire_mode=FireMode.SEMI,
    recoil=RecoilKick(
        aim_pistol=0.2,
        aim_rifle=2.0,
        ads_multiplier=0.35,
        horizontal_min=0.3,
        horizontal_max=1.0,
        vertical_min=1.8,
        vertical_max=3.0,
        return_speed=5.5,
        smoothness=0.45,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(0.85, 0.85, 0.95, 1.0),
        scale=0.35,
        duration=0.08,
        brightness=1.2,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.88, 0.82, 0.28, 1.0),
        scale=0.15,
        eject_velocity=Vec3(2, 4, -2),
        lifetime=7.0,
        gravity=1.1,
    ),
    aim_fov=45.0,
    aim_offset=Vec3(0.0, 0.7, -0.3),
    aim_zoom_duration=0.2,
    shot_sound="sounds/weapons/dmr_12_sentinel/fire.ogg",
    reload_sound="sounds/weapons/dmr_12_sentinel/reload.ogg",
    dry_fire_sound="sounds/weapons/dmr_12_sentinel/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/dmr_12_sentinel/hit_flesh.ogg",
        metal="sounds/weapons/dmr_12_sentinel/hit_metal.ogg",
        concrete="sounds/weapons/dmr_12_sentinel/hit_concrete.ogg",
    ),
    melee_damage=35.0,
    melee_range=2.2,
    model_color=Vec4(0.3, 0.3, 0.32, 1.0),
    model_shape="barrel",
    model_dimensions=(0.28, 0.2, 1.1),
    description="Semi-automatic designated marksman rifle. High damage with faster follow-up shots than bolt-actions.",
)


# ===========================================================================
# SMGs
# ===========================================================================

# MP7 "Storm" - Compact SMG
MP7_STORM = WeaponData(
    weapon_id="mp7_storm",
    name="MP7 'Storm'",
    category="smg",
    damage=22.0,
    fire_rate=950.0,
    accuracy=0.72,
    accuracy_ads=0.88,
    accuracy_move=0.60,
    range=500.0,
    magazine_size=30,
    reserve_ammo=120,
    reload_time=1.6,
    reload_time_empty=2.0,
    ammo_type=AmmoType.NORMAL,
    fire_modes=[FireMode.SEMI, FireMode.AUTO],
    default_fire_mode=FireMode.AUTO,
    recoil=RecoilKick(
        aim_pistol=0.4,
        aim_rifle=1.5,
        ads_multiplier=0.45,
        horizontal_min=0.6,
        horizontal_max=1.8,
        vertical_min=0.5,
        vertical_max=1.5,
        return_speed=10.0,
        smoothness=0.75,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(0.9, 0.7, 0.3, 1.0),
        scale=0.2,
        duration=0.04,
        brightness=0.9,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.85, 0.78, 0.25, 1.0),
        scale=0.1,
        eject_velocity=Vec3(3, 6, -3),
        lifetime=5.0,
        gravity=1.1,
    ),
    aim_fov=15.0,
    aim_offset=Vec3(0.0, 0.35, -0.15),
    aim_zoom_duration=0.12,
    shot_sound="sounds/weapons/mp7_storm/fire.ogg",
    reload_sound="sounds/weapons/mp7_storm/reload.ogg",
    dry_fire_sound="sounds/weapons/mp7_storm/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/mp7_storm/hit_flesh.ogg",
        metal="sounds/weapons/mp7_storm/hit_metal.ogg",
    ),
    melee_damage=25.0,
    melee_range=1.8,
    model_color=Vec4(0.35, 0.35, 0.38, 1.0),
    model_shape="barrel",
    model_dimensions=(0.22, 0.16, 0.7),
    description="Compact submachine gun. Excellent for close-quarters with controllable recoil.",
)


# P90 "Typhoon" - High capacity SMG
P90_TYPHOON = WeaponData(
    weapon_id="p90_typhoon",
    name="P90 'Typhoon'",
    category="smg",
    damage=18.0,
    fire_rate=1000.0,
    accuracy=0.68,
    accuracy_ads=0.85,
    accuracy_move=0.55,
    range=400.0,
    magazine_size=50,
    reserve_ammo=150,
    reload_time=2.2,
    reload_time_empty=2.8,
    ammo_type=AmmoType.NORMAL,
    fire_modes=[FireMode.SEMI, FireMode.AUTO],
    default_fire_mode=FireMode.AUTO,
    recoil=RecoilKick(
        aim_pistol=0.4,
        aim_rifle=1.8,
        ads_multiplier=0.50,
        horizontal_min=0.8,
        horizontal_max=2.2,
        vertical_min=0.6,
        vertical_max=1.8,
        return_speed=9.5,
        smoothness=0.7,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.75, 0.25, 1.0),
        scale=0.22,
        duration=0.038,
        brightness=0.85,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.9, 0.82, 0.3, 1.0),
        scale=0.09,
        eject_velocity=Vec3(4, 7, -4),
        lifetime=4.5,
        gravity=1.3,
    ),
    aim_fov=18.0,
    aim_offset=Vec3(0.0, 0.4, -0.18),
    aim_zoom_duration=0.12,
    shot_sound="sounds/weapons/p90_typhoon/fire.ogg",
    reload_sound="sounds/weapons/p90_typhoon/reload.ogg",
    dry_fire_sound="sounds/weapons/p90_typhoon/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        flesh="sounds/weapons/p90_typhoon/hit_flesh.ogg",
        metal="sounds/weapons/p90_typhoon/hit_metal.ogg",
    ),
    melee_damage=20.0,
    melee_range=1.7,
    model_color=Vec4(0.28, 0.28, 0.3, 1.0),
    model_shape="box",
    model_dimensions=(0.3, 0.15, 0.65),
    description="High-capacity bullpup SMG. 50-round magazine for sustained fire.",
)


# ===========================================================================
# HEAVY WEAPONS
# ===========================================================================

# M5 "Thumper" - Grenade launcher
M5_THUMPER = WeaponData(
    weapon_id="m5_thumper",
    name="M5 'Thumper'",
    category="heavy",
    damage=100.0,        # Direct hit damage
    fire_rate=60.0,      # Slow firing
    accuracy=0.90,
    accuracy_ads=0.98,
    accuracy_move=0.50,
    range=600.0,
    magazine_size=6,
    reserve_ammo=12,
    reload_time=3.0,
    reload_time_empty=3.5,
    ammo_type=AmmoType.EXPLOSIVE,
    fire_modes=[FireMode.SEMI],
    default_fire_mode=FireMode.SEMI,
    recoil=RecoilKick(
        aim_pistol=0.2,
        aim_rifle=2.0,
        ads_multiplier=0.70,
        horizontal_min=0.3,
        horizontal_max=1.0,
        vertical_min=2.0,
        vertical_max=3.5,
        return_speed=4.5,
        smoothness=0.5,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.6, 0.15, 1.0),
        scale=0.6,
        duration=0.1,
        brightness=1.8,
    ),
    shell_casing=ShellCasingParams(
        enabled=False,  # Grenades don't eject shell casings
    ),
    aim_fov=25.0,
    aim_offset=Vec3(0.0, 0.8, -0.35),
    aim_zoom_duration=0.2,
    shot_sound="sounds/weapons/m5_thumper/fire.ogg",
    reload_sound="sounds/weapons/m5_thumper/reload.ogg",
    dry_fire_sound="sounds/weapons/m5_thumper/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        metal="sounds/weapons/m5_thumper/hit_metal.ogg",
        concrete="sounds/weapons/m5_thumper/hit_concrete.ogg",
    ),
    melee_damage=40.0,
    melee_range=2.5,
    model_color=Vec4(0.3, 0.3, 0.3, 1.0),
    model_shape="cylinder",
    model_dimensions=(0.35, 0.3, 0.9),
    description="Shoulder-fired grenade launcher. Explosive projectiles with splash damage.",
)


# Minigun "Annihilator" - Rotary heavy weapon
MINIGUN_ANNIHILATOR = WeaponData(
    weapon_id="minigun_annihilator",
    name="Minigun 'Annihilator'",
    category="heavy",
    damage=25.0,
    fire_rate=3000.0,    # Extremely high fire rate
    accuracy=0.65,
    accuracy_ads=0.80,
    accuracy_move=0.40,
    range=800.0,
    magazine_size=200,
    reserve_ammo=400,
    reload_time=5.0,
    reload_time_empty=6.0,
    ammo_type=AmmoType.NORMAL,
    fire_modes=[FireMode.AUTO],
    default_fire_mode=FireMode.AUTO,
    recoil=RecoilKick(
        aim_pistol=0.3,
        aim_rifle=3.5,
        ads_multiplier=0.80,
        horizontal_min=1.2,
        horizontal_max=3.5,
        vertical_min=1.5,
        vertical_max=5.0,
        return_speed=3.5,
        smoothness=0.3,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.6, 0.2, 1.0),
        scale=0.4,
        duration=0.03,
        brightness=1.5,
    ),
    shell_casing=ShellCasingParams(
        enabled=True,
        color=Vec4(0.8, 0.75, 0.25, 1.0),
        scale=0.12,
        eject_velocity=Vec3(5, 6, -4),
        lifetime=8.0,
        gravity=1.5,
    ),
    aim_fov=10.0,
    aim_offset=Vec3(0.0, 0.5, -0.25),
    aim_zoom_duration=0.25,
    shot_sound="sounds/weapons/minigun_annihilator/fire_loop.ogg",
    reload_sound="sounds/weapons/minigun_annihilator/reload.ogg",
    dry_fire_sound="sounds/weapons/minigun_annihilator/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        metal="sounds/weapons/minigun_annihilator/hit_metal.ogg",
        concrete="sounds/weapons/minigun_annihilator/hit_concrete.ogg",
    ),
    melee_damage=50.0,
    melee_range=3.0,
    model_color=Vec4(0.4, 0.4, 0.42, 1.0),
    model_shape="cylinder",
    model_dimensions=(0.4, 0.25, 1.0),
    description="Rotary cannon with extreme fire rate. Devastating but requires spin-up.",
)


# ===========================================================================
# ENERGY WEAPONS
# ===========================================================================

# Laser Rifle "Solaris" - Energy assault rifle
LASER_RIFLE_SOLARIS = WeaponData(
    weapon_id="laser_rifle_solaris",
    name="Laser Rifle 'Solaris'",
    category="energy",
    damage=35.0,
    fire_rate=600.0,
    accuracy=0.90,
    accuracy_ads=0.98,
    accuracy_move=0.70,
    range=1000.0,
    magazine_size=30,
    reserve_ammo=120,
    reload_time=2.5,
    reload_time_empty=3.0,
    ammo_type=AmmoType.ENERGY,
    fire_modes=[FireMode.SEMI, FireMode.AUTO],
    default_fire_mode=FireMode.AUTO,
    recoil=RecoilKick(
        aim_pistol=0.3,
        aim_rifle=0.8,
        ads_multiplier=0.25,
        horizontal_min=0.1,
        horizontal_max=0.5,
        vertical_min=0.3,
        vertical_max=1.0,
        return_speed=12.0,
        smoothness=0.85,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(0.3, 0.9, 1.0, 1.0),  # Blue energy
        scale=0.3,
        duration=0.05,
        brightness=1.2,
    ),
    shell_casing=ShellCasingParams(
        enabled=False,  # Energy weapons don't eject shells
    ),
    aim_fov=20.0,
    aim_offset=Vec3(0.0, 0.5, -0.2),
    aim_zoom_duration=0.12,
    shot_sound="sounds/weapons/laser_rifle_solaris/fire.ogg",
    reload_sound="sounds/weapons/laser_rifle_solaris/reload.ogg",
    dry_fire_sound="sounds/weapons/laser_rifle_solaris/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        metal="sounds/weapons/laser_rifle_solaris/hit_metal.ogg",
        concrete="sounds/weapons/laser_rifle_solaris/hit_concrete.ogg",
    ),
    melee_damage=25.0,
    melee_range=2.0,
    model_color=Vec4(0.2, 0.4, 0.8, 1.0),  # Blue tint
    model_shape="barrel",
    model_dimensions=(0.25, 0.18, 1.0),
    description="Advanced laser rifle. Precise energy weapons with minimal recoil.",
)


# Plasma Rifle "Nova" - Energy weapon with splash
PLASMA_RIFLE_NOVA = WeaponData(
    weapon_id="plasma_rifle_nova",
    name="Plasma Rifle 'Nova'",
    category="energy",
    damage=40.0,
    fire_rate=500.0,
    accuracy=0.85,
    accuracy_ads=0.95,
    accuracy_move=0.65,
    range=700.0,
    magazine_size=25,
    reserve_ammo=100,
    reload_time=2.8,
    reload_time_empty=3.2,
    ammo_type=AmmoType.PLASMA,
    fire_modes=[FireMode.SEMI, FireMode.AUTO],
    default_fire_mode=FireMode.AUTO,
    recoil=RecoilKick(
        aim_pistol=0.3,
        aim_rifle=1.5,
        ads_multiplier=0.50,
        horizontal_min=0.4,
        horizontal_max=1.2,
        vertical_min=0.8,
        vertical_max=2.0,
        return_speed=8.0,
        smoothness=0.6,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(0.8, 0.2, 1.0, 1.0),  # Purple plasma
        scale=0.35,
        duration=0.06,
        brightness=1.3,
    ),
    shell_casing=ShellCasingParams(
        enabled=False,  # Energy weapons don't eject shells
    ),
    aim_fov=18.0,
    aim_offset=Vec3(0.0, 0.45, -0.18),
    aim_zoom_duration=0.15,
    shot_sound="sounds/weapons/plasma_rifle_nova/fire.ogg",
    reload_sound="sounds/weapons/plasma_rifle_nova/reload.ogg",
    dry_fire_sound="sounds/weapons/plasma_rifle_nova/dry_fire.ogg",
    hit_sounds=_all_hit_sounds(
        metal="sounds/weapons/plasma_rifle_nova/hit_metal.ogg",
        concrete="sounds/weapons/plasma_rifle_nova/hit_concrete.ogg",
    ),
    melee_damage=30.0,
    melee_range=2.0,
    model_color=Vec4(0.5, 0.15, 0.8, 1.0),  # Purple tint
    model_shape="barrel",
    model_dimensions=(0.28, 0.2, 1.05),
    description="Plasma rifle with area-of-effect damage. Great against groups but slower projectiles.",
)


# ===========================================================================
# EXPLOSIVES
# ===========================================================================

# Frag Grenade - Throwable
FRAG_GRENADE = WeaponData(
    weapon_id="frag_grenade",
    name="Frag Grenade",
    category="explosive",
    damage=100.0,        # Splash damage
    fire_rate=30.0,      # One throw per ~2 seconds
    accuracy=1.0,
    accuracy_ads=1.0,
    accuracy_move=0.8,
    range=400.0,
    magazine_size=1,
    reserve_ammo=4,
    reload_time=1.0,
    reload_time_empty=1.0,
    ammo_type=AmmoType.EXPLOSIVE,
    fire_modes=[FireMode.SEMI],
    default_fire_mode=FireMode.SEMI,
    recoil=RecoilKick(
        aim_pistol=0.2,
        aim_rifle=0.3,
        ads_multiplier=1.0,
        horizontal_min=0.1,
        horizontal_max=0.3,
        vertical_min=0.2,
        vertical_max=0.5,
        return_speed=15.0,
        smoothness=0.9,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.8, 0.3, 1.0),
        scale=0.0,  # No muzzle flash for grenades
        duration=0.0,
    ),
    shell_casing=ShellCasingParams(
        enabled=False,  # No shell casing for grenades
    ),
    aim_fov=0.0,
    aim_offset=Vec3(0.0, 0.2, -0.1),
    aim_zoom_duration=0.1,
    shot_sound="sounds/weapons/frag_grenade/throw.ogg",
    reload_sound="sounds/weapons/frag_grenade/pin_pull.ogg",
    dry_fire_sound="sounds/weapons/frag_grenade/dry_fire.ogg",
    hit_sounds={},
    melee_damage=30.0,
    melee_range=1.5,
    model_color=Vec4(0.4, 0.4, 0.4, 1.0),
    model_shape="sphere",
    model_dimensions=(0.15, 0.15, 0.15),
    description="Fragmentation grenade. Throws explosive damage in a wide radius.",
)


# C4 - Placeable
C4 = WeaponData(
    weapon_id="c4",
    name="C4",
    category="explosive",
    damage=150.0,        # Direct placement damage
    fire_rate=20.0,
    accuracy=1.0,
    accuracy_ads=1.0,
    accuracy_move=0.8,
    range=100.0,
    magazine_size=2,
    reserve_ammo=4,
    reload_time=1.5,
    reload_time_empty=1.5,
    ammo_type=AmmoType.EXPLOSIVE,
    fire_modes=[FireMode.SEMI],
    default_fire_mode=FireMode.SEMI,
    recoil=RecoilKick(
        aim_pistol=0.1,
        aim_rifle=0.2,
        ads_multiplier=1.0,
        horizontal_min=0.1,
        horizontal_max=0.2,
        vertical_min=0.1,
        vertical_max=0.3,
        return_speed=15.0,
        smoothness=0.95,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(1.0, 0.5, 0.15, 1.0),
        scale=0.0,
        duration=0.0,
    ),
    shell_casing=ShellCasingParams(
        enabled=False,
    ),
    aim_fov=0.0,
    aim_offset=Vec3(0.0, 0.2, -0.1),
    aim_zoom_duration=0.1,
    shot_sound="sounds/weapons/c4/place.ogg",
    reload_sound="sounds/weapons/c4/charge_prepare.ogg",
    dry_fire_sound="sounds/weapons/c4/dry_fire.ogg",
    hit_sounds={},
    melee_damage=35.0,
    melee_range=1.8,
    model_color=Vec4(0.2, 0.2, 0.2, 1.0),
    model_shape="box",
    model_dimensions=(0.2, 0.1, 0.3),
    description="Remote-detonated C4 charge. Place and detonate from a distance.",
)


# Proximity Mine - Automatically detonated
PROXIMITY_MINE = WeaponData(
    weapon_id="proximity_mine",
    name="Proximity Mine",
    category="explosive",
    damage=80.0,
    fire_rate=25.0,
    accuracy=1.0,
    accuracy_ads=1.0,
    accuracy_move=0.8,
    range=100.0,
    magazine_size=1,
    reserve_ammo=3,
    reload_time=1.0,
    reload_time_empty=1.0,
    ammo_type=AmmoType.EXPLOSIVE,
    fire_modes=[FireMode.SEMI],
    default_fire_mode=FireMode.SEMI,
    recoil=RecoilKick(
        aim_pistol=0.1,
        aim_rifle=0.2,
        ads_multiplier=1.0,
        horizontal_min=0.1,
        horizontal_max=0.2,
        vertical_min=0.1,
        vertical_max=0.3,
        return_speed=15.0,
        smoothness=0.95,
    ),
    muzzle_flash=MuzzleFlashParams(
        color=Vec4(0.3, 0.8, 1.0, 1.0),
        scale=0.0,
        duration=0.0,
    ),
    shell_casing=ShellCasingParams(
        enabled=False,
    ),
    aim_fov=0.0,
    aim_offset=Vec3(0.0, 0.2, -0.1),
    aim_zoom_duration=0.1,
    shot_sound="sounds/weapons/proximity_mine/place.ogg",
    reload_sound="sounds/weapons/proximity_mine/prepare.ogg",
    dry_fire_sound="sounds/weapons/proximity_mine/dry_fire.ogg",
    hit_sounds={},
    melee_damage=25.0,
    melee_range=1.5,
    model_color=Vec4(0.3, 0.3, 0.35, 1.0),
    model_shape="cylinder",
    model_dimensions=(0.15, 0.15, 0.25),
    description="Proximity-detonated mine. Explodes when enemies are nearby.",
)


# ===========================================================================
# Registry
# ===========================================================================

ALL_WEAPONS: Dict[str, WeaponData] = {
    # Assault Rifles (3)
    "ar_77_viper": AR_77_VIPER,
    "ar_99_reaper": AR_99_REAPER,
    "ar_smg_wasp": AR_SMG_WASP,
    # Pistols (3)
    "px4_striker": PX4_STARER,
    "magnum_python": MAGNUM_PYTHON,
    "auto_pistol_raven": AUTO_PISTOL_RAVEN,
    # Shotguns (2)
    "m87_pump": M87_PUMP,
    "aa12_auto": AA12_AUTO,
    # Sniper Rifles (2)
    "srs_longshot": SRS_LONGSHOT,
    "dmr_12_sentinel": DMR_12_SENTINEL,
    # SMGs (2)
    "mp7_storm": MP7_STORM,
    "p90_typhoon": P90_TYPHOON,
    # Heavy Weapons (2)
    "m5_thumper": M5_THUMPER,
    "minigun_annihilator": MINIGUN_ANNIHILATOR,
    # Energy Weapons (2)
    "laser_rifle_solaris": LASER_RIFLE_SOLARIS,
    "plasma_rifle_nova": PLASMA_RIFLE_NOVA,
    # Explosives (3)
    "frag_grenade": FRAG_GRENADE,
    "c4": C4,
    "proximity_mine": PROXIMITY_MINE,
}

ALL_WEAPON_IDS: List[str] = list(ALL_WEAPONS.keys())

WEAPON_CATEGORIES: Dict[str, List[str]] = {
    "assault_rifle": ["ar_77_viper", "ar_99_reaper", "ar_smg_wasp"],
    "pistol": ["px4_striker", "magnum_python", "auto_pistol_raven"],
    "shotgun": ["m87_pump", "aa12_auto"],
    "sniper_rifle": ["srs_longshot", "dmr_12_sentinel"],
    "smg": ["mp7_storm", "p90_typhoon"],
    "heavy": ["m5_thumper", "minigun_annihilator"],
    "energy": ["laser_rifle_solaris", "plasma_rifle_nova"],
    "explosive": ["frag_grenade", "c4", "proximity_mine"],
}


def get_weapon_definition(weapon_id: str) -> WeaponData:
    """Look up a weapon definition by its ID.

    Args:
        weapon_id: The unique weapon identifier string.

    Returns:
        The WeaponData for the requested weapon.

    Raises:
        KeyError: If the weapon_id is not found in the registry.
    """
    if weapon_id not in ALL_WEAPONS:
        raise KeyError(
            f"Weapon '{weapon_id}' not found. "
            f"Available weapons: {list(ALL_WEAPONS.keys())}"
        )
    return ALL_WEAPONS[weapon_id]


def get_weapons_by_category(category: str) -> List[str]:
    """Get a list of weapon IDs for a given category.

    Args:
        category: The weapon category name (e.g., 'assault_rifle', 'pistol').

    Returns:
        A list of weapon ID strings belonging to that category.

    Raises:
        KeyError: If the category is not found.
    """
    if category not in WEAPON_CATEGORIES:
        raise KeyError(
            f"Category '{category}' not found. "
            f"Available categories: {list(WEAPON_CATEGORIES.keys())}"
        )
    return WEAPON_CATEGORIES[category].copy()


def get_all_weapon_definitions() -> Dict[str, WeaponData]:
    """Return a copy of all weapon definitions.

    Returns:
        A dictionary mapping weapon IDs to WeaponData instances.
    """
    return dict(ALL_WEAPONS)
