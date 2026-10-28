"""
test_imports.py

Verify all game modules can be imported without errors.
Does not start the Panda3D window -- just tests import-level integration.
"""

import sys
import traceback


def test_imports():
    """Test that all modules import correctly."""
    modules = [
        "config.constants",
        "config.game_config",
        "config.settings",
        "core.states",
        "core.scene",
        "core.audio",
        "player.controller",
        "weapons.weapon",
        "weapons.weapon_definitions",
        "weapons.weapon_manager",
        "ai.enemy",
        "ai.enemy_types",
        "ai.bosses",
        "systems.stats",
        "systems.progression",
        "systems.save_manager",
        "ui.menu_manager",
        "ui.hud",
        "ui.screens",
        "missions.missions",
        "modes.game_modes",
        "worlds.world_base",
        "worlds.cyberpunk_city",
        "worlds.wasteland",
        "worlds.military_facility",
        "worlds.jungle",
        "worlds.arctic",
        "worlds.space_station",
        "worlds.fantasy",
    ]

    errors = []
    for mod_name in modules:
        try:
            __import__(mod_name)
            print(f"  OK: {mod_name}")
        except Exception as e:
            errors.append((mod_name, str(e), traceback.format_exc()))
            print(f"  FAIL: {mod_name} -- {e}")

    # Test Game import (this requires Panda3D base).
    try:
        from core.game import Game
        print("  OK: core.game.Game")
    except Exception as e:
        errors.append(("core.game", str(e), traceback.format_exc()))
        print(f"  FAIL: core.game -- {e}")

    if errors:
        print(f"\n{len(errors)} import(s) failed.")
        return 1
    else:
        print(f"\nAll {len(modules)} modules imported successfully.")
        return 0


if __name__ == "__main__":
    sys.exit(test_imports())
