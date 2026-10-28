"""
hud.py

In-game heads-up display (HUD) for the SHARIFA game.

The ``HUD`` class renders:
- Health / shield bars.
- Current weapon ammo (magazine / reserve).
- Fire-mode indicator.
- Mini-map placeholder.
- Hit-marker feedback.
- Weapon-switch and weapon-pickup notifications.

It is designed to be lightweight and updated via simple ``update`` and
``show_*`` methods called from the game loop.
"""

from __future__ import annotations

import logging
from typing import Optional

from panda3d.core import (
    NodePath,
    TransparencyAttrib,
    TextNode,
)
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import (
    DirectFrame,
    DirectWaitBar,
    DirectLabel,
    OnscreenText,
)

logger = logging.getLogger(__name__)


class HUD:
    """
    Heads-up display for the game.

    Parameters
    ----------
    parent : NodePath
        The render2d or aspect2d node to attach UI elements to.
    settings : Settings, optional
        User settings (used for graphics quality decisions).
    """

    def __init__(
        self,
        parent: Optional[NodePath] = None,
        settings=None,
    ) -> None:
        from panda3d.core import aspect2d, render2d

        if parent is None:
            parent = aspect2d

        self.parent = parent
        self.settings = settings

        # Root node for all HUD elements (so we can show/hide easily).
        self.root: NodePath = parent.attachNewNode("hud_root")

        # Health / shield state (0..100).
        self._health: float = 100.0
        self._shield: float = 100.0
        self._max_health: float = 100.0
        self._max_shield: float = 100.0

        # Ammo state.
        self._current_ammo: int = 0
        self._reserve_ammo: int = 0
        self._fire_mode_text: str = "SEMI"

        # Hit marker.
        self._hit_marker_active: bool = False
        self._hit_marker_critical: bool = False
        self._hit_marker_timer: float = 0.0

        # Weapon notifications.
        self._notification_timer: float = 0.0
        self._notification_text: str = ""

        # UI references.
        self._health_bar: Optional[DirectWaitBar] = None
        self._shield_bar: Optional[DirectWaitBar] = None
        self._ammo_label: Optional[OnscreenText] = None
        self._fire_mode_label: Optional[OnscreenText] = None
        self._hit_marker: Optional[OnscreenText] = None
        self._notification: Optional[OnscreenText] = None
        self._minimap_frame: Optional[DirectFrame] = None

        self._build_ui()

    # ------------------------------------------------------------------ #
    #  UI Construction                                                    #
    # ------------------------------------------------------------------ -->

    def _build_ui(self) -> None:
        """Create all UI elements and lay them out."""
        try:
            # --- Health bar (red, bottom-left) ---
            self._health_bar = DirectWaitBar(
                range=self._max_health,
                value=self._health,
                barColor=(0.8, 0.2, 0.2, 0.8),
                frameColor=(0, 0, 0, 0),
                scale=(0.3, 1, 0.03),
                pos=(-1.0, 0, -0.92),
                parent=self.root,
            )

            # --- Shield bar (blue, bottom-left, above health) ---
            self._shield_bar = DirectWaitBar(
                range=self._max_shield,
                value=self._shield,
                barColor=(0.2, 0.5, 1.0, 0.8),
                frameColor=(0, 0, 0, 0),
                scale=(0.3, 1, 0.03),
                pos=(-1.0, 0, -0.86),
                parent=self.root,
            )

            # --- Ammo label (bottom-right) ---
            self._ammo_label = OnscreenText(
                text="",
                parent=self.root,
                pos=(0.9, -0.9),
                scale=0.07,
                fg=(1, 1, 1, 1),
                align=TextNode.ARight,
                mayChange=True,
            )

            # --- Fire-mode label (above ammo) ---
            self._fire_mode_label = OnscreenText(
                text="",
                parent=self.root,
                pos=(0.9, -0.80),
                scale=0.04,
                fg=(0.8, 0.8, 1.0, 1),
                align=TextNode.ARight,
                mayChange=True,
            )

            # --- Hit marker (center screen) ---
            self._hit_marker = OnscreenText(
                text="",
                parent=self.root,
                pos=(0, 0),
                scale=0.2,
                fg=(1, 0.2, 0.2, 0.8),
                align=TextNode.ACenter,
                mayChange=True,
            )
            self._hit_marker.hide()

            # --- Notification text (center-top) ---
            self._notification = OnscreenText(
                text="",
                parent=self.root,
                pos=(0, 0.8),
                scale=0.06,
                fg=(0.3, 1.0, 0.3, 1),
                align=TextNode.ACenter,
                mayChange=True,
            )
            self._notification.hide()

            # --- Mini-map frame (top-right) ---
            self._minimap_frame = DirectFrame(
                frameColor=(0, 0, 0, 0.3),
                frameSize=(-0.15, 0.15, -0.15, 0.15),
                pos=(1.0, 0, 0.85),
                parent=self.root,
            )
            minimap_label = OnscreenText(
                text="MAP",
                parent=self.root,
                pos=(0.85, 0.78),
                scale=0.035,
                fg=(0.5, 0.5, 1.0, 1),
                align=TextNode.ACenter,
            )

            logger.debug("HUD elements built successfully.")
        except Exception:
            logger.exception("Failed to build HUD UI elements.")

    # ------------------------------------------------------------------ #
    #  State setters                                                      #
    # ------------------------------------------------------------------ -->

    def set_health(self, health: float, max_health: float = 100.0) -> None:
        """Update the health bar."""
        self._health = max(0.0, health)
        self._max_health = max(1.0, max_health)
        if self._health_bar is not None:
            self._health_bar["range"] = self._max_health
            self._health_bar["value"] = self._health

    def set_shield(self, shield: float, max_shield: float = 100.0) -> None:
        """Update the shield bar."""
        self._shield = max(0.0, shield)
        self._max_shield = max(1.0, max_shield)
        if self._shield_bar is not None:
            self._shield_bar["range"] = self._max_shield
            self._shield_bar["value"] = self._shield

    def set_ammo(self, current: int, reserve: int) -> None:
        """Update the ammo display."""
        self._current_ammo = max(0, current)
        self._reserve_ammo = max(0, reserve)
        if self._ammo_label is not None:
            self._ammo_label.setText(f"{self._current_ammo} | {self._reserve_ammo}")

    def set_fire_mode(self, mode: str) -> None:
        """Update the fire-mode indicator."""
        self._fire_mode_text = mode.upper()
        if self._fire_mode_label is not None:
            self._fire_mode_label.setText(self._fire_mode_text)

    def show_hit_marker(self, critical: bool = False) -> None:
        """Display a hit marker at the center of the screen."""
        if self._hit_marker is None:
            return

        self._hit_marker_active = True
        self._hit_marker_critical = critical
        self._hit_marker_timer = 0.3 if critical else 0.2

        self._hit_marker["text"] = "!" if critical else "X"
        self._hit_marker["fg"] = (1.0, 0.2, 0.2, 1.0) if critical else (1.0, 1.0, 1.0, 0.8)
        self._hit_marker.show()

    def show_weapon_pickup(self, weapon_name: str) -> None:
        """Display a weapon pickup notification."""
        if self._notification is None:
            return
        self._notification["text"] = f"Weapon Acquired: {weapon_name}"
        self._notification["fg"] = (0.3, 1.0, 0.3, 1.0)
        self._notification.show()
        self._notification_timer = 3.0

    def show_notification(self, message: str, critical: bool = False) -> None:
        """Display a general notification message."""
        if self._notification is None:
            return
        self._notification["text"] = message
        self._notification["fg"] = (1.0, 0.4, 0.4, 1.0) if critical else (0.3, 1.0, 0.3, 1.0)
        self._notification.show()
        self._notification_timer = 3.0

    # ------------------------------------------------------------------ #
    #  Update                                                             #
    # ------------------------------------------------------------------ -->

    def update(self, dt: float) -> None:
        """
        Per-frame update — decrements timers and hides transient elements.

        Parameters
        ----------
        dt : float
            Delta time in seconds.
        """
        # Hit marker decay.
        if self._hit_marker_active:
            self._hit_marker_timer -= dt
            if self._hit_marker_timer <= 0:
                self._hit_marker_active = False
                if self._hit_marker is not None:
                    self._hit_marker.hide()

        # Notification decay.
        if self._notification_timer > 0:
            self._notification_timer -= dt
            if self._notification_timer <= 0 and self._notification is not None:
                self._notification.hide()

    # ------------------------------------------------------------------ #
    #  Visibility                                                         #
    # ------------------------------------------------------------------ -->

    def show(self) -> None:
        """Show the entire HUD."""
        self.root.show()

    def hide(self) -> None:
        """Hide the entire HUD."""
        self.root.hide()

    def destroy(self) -> None:
        """Clean up all UI elements."""
        try:
            if self._health_bar is not None:
                self._health_bar.destroy()
            if self._shield_bar is not None:
                self._shield_bar.destroy()
            if self._minimap_frame is not None:
                self._minimap_frame.destroy()
            for text in (
                self._ammo_label,
                self._fire_mode_label,
                self._hit_marker,
                self._notification,
            ):
                if text is not None:
                    text.destroy()
            self.root.removeNode()
        except Exception:
            logger.exception("Error destroying HUD elements.")


__all__ = ["HUD"]
