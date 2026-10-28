#!/usr/bin/env python3
"""
run_game.py

Entry point for the SHARIFA 3D FPS game.

Usage:
    python run_game.py

This module creates and runs the main ``Game`` instance, wiring up
state management, audio, scene, and the player controller.
"""

from __future__ import annotations

import logging
import sys
import traceback

from core.game import Game
from core.states import GameState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_game")


def main() -> int:
    """
    Create the game instance and start the main loop.

    Returns
    -------
    int
        Exit code (0 on normal exit, 1 on error).
    """
    logger.info("Starting SHARIFA v0.1.0-alpha")

    try:
        game = Game()
        game.run_game()
        return 0
    except Exception:
        logger.error("Fatal error during game execution:")
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
