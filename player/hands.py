"""
hands.py

HandsController — renders the first-person hands/arms attached to
the camera.  In a full game this would animate the player's viewmodel
(arms, weapon model, etc.).  This module provides the basic structure.
"""

from __future__ import annotations

import logging
from typing import Optional

from panda3d.core import NodePath
from direct.showbase.ShowBase import ShowBase

logger = logging.getLogger(__name__)


class HandsController:
    """
    Manages the first-person hands / viewmodel.

    The hands node is parented to the camera so it moves with head
    rotation but not with the player's body position.  This creates
    the illusion that the hands are "attached" to the screen.

    Parameters
    ----------
    game : ShowBase
        The running game instance.
    """

    def __init__(self, game: ShowBase) -> None:
        self.game = game

        # Container for all viewmodel geometry.
        self.node: NodePath = NodePath("hands_root")
        self.node.reparentTo(self.game.camera)

        # The actual hands/arms model — placeholder for now.
        self._model: Optional[NodePath] = None
        self._load_model()

        # Animation state.
        self._current_anim: str = "idle"
        self._is_animating: bool = False

        logger.info("HandsController initialized.")

    def _load_model(self) -> None:
        """
        Attempt to load the hands viewmodel.

        Falls back to a simple placeholder if the model is not found.
        """
        try:
            # Try loading a real model.
            self._model = self.game.loader.loadModel("assets/models/hands")
            if self._model is not None:
                self._model.reparentTo(self.node)
                self._model.setScale(0.1)  # adjust to fit view
                self._model.setPos(0, 0.3, -0.2)  # in front of camera
                logger.info("Hands model loaded.")
                return
        except Exception:
            logger.debug("No hands model found at assets/models/hands; using placeholder.")

        # No model found — create a simple placeholder cube.
        from panda3d.core import CardMaker

        cm = CardMaker("hands_placeholder")
        cm.setFrame(-0.1, 0.1, -0.1, 0.1)
        placeholder = self.node.attachNewNode(cm.generate())
        placeholder.setPos(0, 0.5, -0.3)
        placeholder.setColor(0.8, 0.6, 0.4, 1)
        self._model = placeholder
        logger.info("Placeholder hands (colored quad) created.")

    def play_animation(self, anim_name: str, loop: bool = True) -> None:
        """
        Play an animation on the hands model.

        Parameters
        ----------
        anim_name : str
            Identifier of the animation ("idle", "walk", "run",
            "jump", "land", etc.).
        loop : bool
            Whether to loop the animation.
        """
        self._current_anim = anim_name

        if self._model is not None:
            try:
                if loop:
                    self._model.loop(anim_name)
                else:
                    self._model.play(anim_name)
            except Exception:
                logger.debug("Animation '%s' not found on hands model.", anim_name)

    def set_position(self, x: float, y: float, z: float) -> None:
        """Move the hands node to a position relative to the camera."""
        self.node.setPos(x, y, z)

    def set_hpr(self, h: float, p: float, r: float) -> None:
        """Rotate the hands node."""
        self.node.setHpr(h, p, r)

    def destroy(self) -> None:
        """Clean up the hands controller."""
        if self._model is not None:
            self._model.removeNode()
        self.node.removeNode()
        logger.info("HandsController destroyed.")
