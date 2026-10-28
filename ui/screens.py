"""
screens.py

Mission-complete and game-over result screens.

The ``ScreenManager`` displays results screens with:
- Mission outcome (Victory / Defeat).
- Performance metrics (time, accuracy, kills, damage taken).
- Score and XP gained.
- Medal / rank award based on performance.
- Continue / Retry / Main Menu buttons.

Screens are built with Panda3D's DirectGUI.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from panda3d.core import NodePath, TextNode
from direct.gui.DirectGui import (
    DirectFrame,
    DirectButton,
    DirectLabel,
    OnscreenText,
)

logger = logging.getLogger(__name__)


class ScreenType(Enum):
    """Types of result screens."""

    MISSION_COMPLETE = "mission_complete"
    GAME_OVER = "game_over"
    NONE = "none"


class ScreenManager:
    """
    Manages mission-complete and game-over result screens.

    Parameters
    ----------
    parent : NodePath
        ``aspect2d`` or another GUI root.
    callbacks : Dict[str, callable], optional
        - ``"continue"``: Continue to next mission / main menu.
        - ``"retry"``: Restart the current mission.
        - ``"main_menu"``: Return to main menu.

    Attributes
    ----------
    current_screen : ScreenType
        The screen currently displayed.
    """

    def __init__(
        self,
        parent,
        callbacks: Optional[Dict[str, Any]] = None,
    ) -> None:
        from panda3d.core import aspect2d

        if parent is None:
            parent = aspect2d

        self.parent = parent
        self.callbacks = callbacks or {}
        self.current_screen: ScreenType = ScreenType.NONE
        self._root: Optional[NodePath] = None
        self._build_root()

    # ------------------------------------------------------------------ #
    #  UI Construction                                                    #
    # ------------------------------------------------------------------ -->

    def _build_root(self) -> None:
        """Create the root node for all result screens."""
        self._root = self.parent.attachNewNode("screen_root")

    def hide(self) -> None:
        """Hide all screens."""
        if self._root is not None:
            self._root.hide()
        self.current_screen = ScreenType.NONE

    def show_mission_complete(
        self,
        mission_name: str = "Mission",
        victory: bool = True,
        time_taken: float = 0.0,
        kills: int = 0,
        headshots: int = 0,
        accuracy: float = 0.0,
        damage_taken: int = 0,
        score: int = 0,
        xp_gained: int = 0,
        level_unlocked: bool = False,
        weapon_unlocked: Optional[str] = None,
    ) -> None:
        """
        Display the mission-complete results screen.

        Parameters mirror the stats to be displayed.  All have sensible
        defaults so the screen can be shown even with partial data.
        """
        self._destroy_current()
        self.current_screen = ScreenType.MISSION_COMPLETE

        if self._root is None:
            return

        self._root.show()

        bg = DirectFrame(
            frameColor=(0, 0, 0, 0.9),
            frameSize=(-1, 1, -1, 1),
            parent=self._root,
        )

        # Title.
        status_text = "MISSION COMPLETE" if victory else "MISSION FAILED"
        status_color = (0.2, 1.0, 0.4, 1.0) if victory else (1.0, 0.3, 0.3, 1.0)

        DirectLabel(
            text=status_text,
            text_scale=0.12,
            text_fg=status_color,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.8),
            parent=self._root,
        )

        DirectLabel(
            text=mission_name,
            text_scale=0.06,
            text_fg=(0.7, 0.7, 0.9, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.68),
            parent=self._root,
        )

        # Stats rows.
        stats: List[Dict[str, Any]] = [
            {"label": "Time", "value": self._format_time(time_taken)},
            {"label": "Kills", "value": str(kills)},
            {"label": "Headshots", "value": str(headshots)},
            {"label": "Accuracy", "value": f"{accuracy:.1f}%"},
            {"label": "Damage Taken", "value": str(damage_taken)},
            {"label": "Score", "value": str(score)},
            {"label": "XP Gained", "value": str(xp_gained)},
        ]

        if level_unlocked:
            stats.append({"label": "LEVEL UP", "value": "", "special": True})

        if weapon_unlocked:
            stats.append({"label": "New Weapon", "value": weapon_unlocked, "special": True})

        # Draw stats in two columns.
        for i, s in enumerate(stats):
            y = 0.45 - i * 0.07
            label_text = s["label"] + ":"
            if s.get("special"):
                label_text = s["label"]

            DirectLabel(
                text=label_text,
                text_scale=0.035,
                text_fg=(0.6, 0.6, 0.8, 1.0),
                frameColor=(0, 0, 0, 0),
                pos=(-0.3, 0, y),
                text_align=TextNode.ALeft,
                parent=self._root,
            )

            DirectLabel(
                text=s["value"],
                text_scale=0.035,
                text_fg=(status_color[0], status_color[1] - 0.1, status_color[2], 1.0),
                frameColor=(0, 0, 0, 0),
                pos=(0.1, 0, y),
                text_align=TextNode.ALeft,
                parent=self._root,
            )

        # Buttons.
        btn_w = 0.25
        btn_h = 0.07

        DirectButton(
            text="Continue",
            text_scale=0.05,
            text_fg=(1, 1, 1, 1),
            text_hover_fg=(0.4, 1.0, 0.4, 1.0),
            frameColor=(0.15, 0.25, 0.15, 0.7),
            frameSize=(-btn_w / 2, btn_w / 2, -btn_h / 2, btn_h / 2),
            pos=(-0.35, 0, -0.75),
            relief="raised",
            command=self._on_continue,
            parent=self._root,
        )

        DirectButton(
            text="Retry",
            text_scale=0.05,
            text_fg=(1, 1, 1, 1),
            text_hover_fg=(1.0, 0.8, 0.4, 1.0),
            frameColor=(0.25, 0.25, 0.15, 0.7),
            frameSize=(-btn_w / 2, btn_w / 2, -btn_h / 2, btn_h / 2),
            pos=(0, 0, -0.75),
            relief="raised",
            command=self._on_retry,
            parent=self._root,
        )

        DirectButton(
            text="Main Menu",
            text_scale=0.05,
            text_fg=(1, 1, 1, 1),
            text_hover_fg=(1.0, 0.4, 0.4, 1.0),
            frameColor=(0.25, 0.15, 0.15, 0.7),
            frameSize=(-btn_w / 2, btn_w / 2, -btn_h / 2, btn_h / 2),
            pos=(0.35, 0, -0.75),
            relief="raised",
            command=self._on_main_menu,
            parent=self._root,
        )

    def show_game_over(
        self,
        mission_name: str = "Mission",
        time_survived: float = 0.0,
        kills: int = 0,
        accuracy: float = 0.0,
        score: int = 0,
    ) -> None:
        """
        Display the game-over screen.

        Parameters
        ----------
        mission_name : str
            Name of the mission that was failed.
        time_survived : float
            How long the player survived (seconds).
        kills : int
            Number of enemies killed.
        accuracy : float
            Shot accuracy percentage.
        score : int
            Final score.
        """
        self._destroy_current()
        self.current_screen = ScreenType.GAME_OVER

        if self._root is None:
            return

        self._root.show()

        bg = DirectFrame(
            frameColor=(0, 0, 0, 0.95),
            frameSize=(-1, 1, -1, 1),
            parent=self._root,
        )

        # Title.
        DirectLabel(
            text="GAME OVER",
            text_scale=0.14,
            text_fg=(1.0, 0.2, 0.2, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.8),
            parent=self._root,
        )

        DirectLabel(
            text=mission_name,
            text_scale=0.05,
            text_fg=(0.6, 0.6, 0.8, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.65),
            parent=self._root,
        )

        # Stats.
        stats: List[Dict[str, str]] = [
            {"label": "Time Survived", "value": self._format_time(time_survived)},
            {"label": "Kills", "value": str(kills)},
            {"label": "Accuracy", "value": f"{accuracy:.1f}%"},
            {"label": "Score", "value": str(score)},
        ]

        for i, s in enumerate(stats):
            y = 0.4 - i * 0.08
            DirectLabel(
                text=f"{s['label']}:",
                text_scale=0.04,
                text_fg=(0.5, 0.5, 0.7, 1.0),
                frameColor=(0, 0, 0, 0),
                pos=(-0.2, 0, y),
                text_align=TextNode.ALeft,
                parent=self._root,
            )
            DirectLabel(
                text=s["value"],
                text_scale=0.04,
                text_fg=(1.0, 0.8, 0.8, 1.0),
                frameColor=(0, 0, 0, 0),
                pos=(0.1, 0, y),
                text_align=TextNode.ALeft,
                parent=self._root,
            )

        # Buttons.
        btn_w = 0.3
        btn_h = 0.07

        DirectButton(
            text="Retry",
            text_scale=0.05,
            text_fg=(1, 1, 1, 1),
            text_hover_fg=(1.0, 0.8, 0.4, 1.0),
            frameColor=(0.25, 0.25, 0.15, 0.7),
            frameSize=(-btn_w / 2, btn_w / 2, -btn_h / 2, btn_h / 2),
            pos=(0, 0, -0.65),
            relief="raised",
            command=self._on_retry,
            parent=self._root,
        )

        DirectButton(
            text="Main Menu",
            text_scale=0.05,
            text_fg=(1, 1, 1, 1),
            text_hover_fg=(1.0, 0.4, 0.4, 1.0),
            frameColor=(0.25, 0.15, 0.15, 0.7),
            frameSize=(-btn_w / 2, btn_w / 2, -btn_h / 2, btn_h / 2),
            pos=(0.35, 0, -0.65),
            relief="raised",
            command=self._on_main_menu,
            parent=self._root,
        )

    # ------------------------------------------------------------------ #
    #  Button callbacks                                                   #
    # ------------------------------------------------------------------ -->

    def _on_continue(self) -> None:
        self._call_callback("continue")
        self.hide()

    def _on_retry(self) -> None:
        self._call_callback("retry")
        self.hide()

    def _on_main_menu(self) -> None:
        self._call_callback("main_menu")
        self.hide()

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ -->

    def _destroy_current(self) -> None:
        """Remove all child UI elements."""
        if self._root is not None:
            for child in list(self._root.getChildren()):
                child.removeNode()

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as MM:SS.ss."""
        if seconds <= 0:
            return "0:00"
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}:{secs:05.2f}"

    def _call_callback(self, name: str) -> None:
        """Invoke a registered callback by name."""
        cb = self.callbacks.get(name)
        if cb is not None:
            try:
                cb()
            except Exception:
                logger.exception("Error in callback '%s'.", name)
        else:
            logger.warning("No callback registered for '%s'.", name)

    # ------------------------------------------------------------------ #
    #  Cleanup                                                            #
    # ------------------------------------------------------------------ -->

    def destroy(self) -> None:
        """Clean up all UI elements."""
        try:
            if self._root is not None:
                self._root.removeNode()
                self._root = None
        except Exception:
            logger.exception("Error destroying ScreenManager.")


__all__ = [
    "ScreenManager",
    "ScreenType",
]
