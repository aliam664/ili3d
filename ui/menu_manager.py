"""
menu_manager.py

Menu system for the SHARIFA game.

The ``MenuManager`` handles:
- Main menu (new game, continue, options, quit).
- Pause menu (resume, options, quit to menu).
- Options menu (audio, graphics, controls settings).

Menus are built using Panda3D's DirectGUI and respond to keyboard /
mouse input.  The manager is designed to be instantiated after the
``ShowBase`` window exists.
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Callable, Dict, List, Optional

from panda3d.core import Vec3, Vec4
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import (
    DirectFrame,
    DirectButton,
    DirectLabel,
    DirectSlider,
    DirectOptionMenu,
    DirectCheckButton,
)

logger = logging.getLogger(__name__)


class MenuType(Enum):
    """Identifies which menu screen is currently active."""

    MAIN = "main"
    PAUSE = "pause"
    OPTIONS = "options"
    NONE = "none"


class MenuManager:
    """
    Manages all in-game menu screens.

    Parameters
    ----------
    parent : NodePath
        ``aspect2d`` or another GUI root to attach menus to.
    settings : Settings
        User settings object to read / write menu changes.
    callbacks : Dict[str, callable], optional
        Mapping of callback names to functions:
        - ``"new_game"``: Start a new game.
        - ``"continue"``: Continue from a save.
        - ``"options_apply"``: Settings were applied.
        - ``"resume"``: Resume from pause.
        - ``"quit_to_menu"``: Quit current game to main menu.
        - ``"quit_game"``: Exit the application.
    """

    def __init__(
        self,
        parent,
        settings=None,
        callbacks: Optional[Dict[str, Callable]] = None,
    ) -> None:
        from panda3d.core import aspect2d

        if parent is None:
            parent = aspect2d

        self.parent = parent
        self.settings = settings
        self.callbacks: Dict[str, Callable] = callbacks or {}

        self.current_menu: MenuType = MenuType.NONE
        self._root: Optional[NodePath] = None
        self._build_root()

    # ------------------------------------------------------------------ #
    #  UI Construction                                                    #
    # ------------------------------------------------------------------ -->

    def _build_root(self) -> None:
        """Create the root node for all menus."""
        self._root = self.parent.attachNewNode("menu_root")
        self._root.hide()  # Hidden by default.

    def hide(self) -> None:
        """Hide all menus."""
        if self._root is not None:
            self._root.hide()
        self.current_menu = MenuType.NONE

    def show_menu(self, menu_type: MenuType) -> None:
        """
        Show a specific menu type, hiding any existing menu first.

        Parameters
        ----------
        menu_type : MenuType
            Which menu to display.
        """
        # Clean up any existing menu.
        self._destroy_current_menu()

        if menu_type == MenuType.NONE:
            self.current_menu = MenuType.NONE
            self._root.hide()
            return

        self.current_menu = menu_type
        self._root.show()

        if menu_type == MenuType.MAIN:
            self._build_main_menu()
        elif menu_type == MenuType.PAUSE:
            self._build_pause_menu()
        elif menu_type == MenuType.OPTIONS:
            self._build_options_menu()

    def _destroy_current_menu(self) -> None:
        """Remove all child UI elements from the menu root."""
        if self._root is not None:
            for child in list(self._root.getChildren()):
                child.removeNode()

    # ------------------------------------------------------------------ #
    #  Menu builders                                                      #
    # ------------------------------------------------------------------ -->

    def _build_main_menu(self) -> None:
        """Build the main menu with New Game, Continue, Options, Quit."""
        # Dark semi-transparent background.
        bg = DirectFrame(
            frameColor=(0, 0, 0, 0.85),
            frameSize=(-1, 1, -1, 1),
            parent=self._root,
        )

        title = DirectLabel(
            text="SHARIFA",
            text_scale=0.18,
            text_fg=(0.0, 0.8, 1.0, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.5),
            parent=self._root,
        )

        subtitle = DirectLabel(
            text="v0.1.0-alpha",
            text_scale=0.04,
            text_fg=(0.6, 0.6, 0.8, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.38),
            parent=self._root,
        )

        btn_w = 0.4
        btn_h = 0.08
        btn_y_start = 0.1

        buttons = [
            ("New Game", btn_y_start, self._on_new_game),
            ("Continue", btn_y_start - 0.15, self._on_continue),
            ("Options", btn_y_start - 0.30, self._on_options),
            ("Quit", btn_y_start - 0.45, self._on_quit),
        ]

        for text, y, command in buttons:
            DirectButton(
                text=text,
                text_scale=0.05,
                text_fg=(1, 1, 1, 1),
                text_hover_fg=(0.4, 0.8, 1.0, 1.0),
                frameColor=(0.15, 0.15, 0.25, 0.7),
                frameSize=(-btn_w / 2, btn_w / 2, -btn_h / 2, btn_h / 2),
                pos=(0, 0, y),
                relief="raised",
                command=command,
                parent=self._root,
            )

    def _build_pause_menu(self) -> None:
        """Build the pause menu."""
        bg = DirectFrame(
            frameColor=(0, 0, 0, 0.7),
            frameSize=(-1, 1, -1, 1),
            parent=self._root,
        )

        label = DirectLabel(
            text="PAUSED",
            text_scale=0.15,
            text_fg=(1.0, 0.8, 0.2, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.3),
            parent=self._root,
        )

        btn_w = 0.35
        btn_h = 0.07
        buttons = [
            ("Resume", 0.0, self._on_resume),
            ("Options", -0.15, self._on_options),
            ("Main Menu", -0.30, self._on_quit_to_menu),
        ]

        for text, y, command in buttons:
            DirectButton(
                text=text,
                text_scale=0.05,
                text_fg=(1, 1, 1, 1),
                text_hover_fg=(0.4, 0.8, 1.0, 1.0),
                frameColor=(0.15, 0.15, 0.25, 0.7),
                frameSize=(-btn_w / 2, btn_w / 2, -btn_h / 2, btn_h / 2),
                pos=(0, 0, y),
                relief="raised",
                command=command,
                parent=self._root,
            )

    def _build_options_menu(self) -> None:
        """Build the options menu with volume sliders and graphics quality."""
        bg = DirectFrame(
            frameColor=(0, 0, 0, 0.85),
            frameSize=(-1, 1, -1, 1),
            parent=self._root,
        )

        title = DirectLabel(
            text="OPTIONS",
            text_scale=0.12,
            text_fg=(0.4, 1.0, 0.4, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.7),
            parent=self._root,
        )

        # Volume sliders.
        slider_x = -0.25
        slider_w = 0.5

        # Master volume.
        DirectLabel(
            text="Master Volume",
            text_scale=0.04,
            text_fg=(0.8, 0.8, 1.0, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(slider_x - 0.05, 0, 0.5),
            text_align=0,
            parent=self._root,
        )
        master_val = self._settings_get("master_volume", 0.8)
        self._master_slider = DirectSlider(
            range=(0, 1),
            value=master_val,
            pageSize=0.01,
            orientation="horizontal",
            frameSize=(0, slider_w, -0.02, 0.02),
            pos=(slider_x, 0, 0.42),
            parent=self._root,
        )
        self._master_slider.setScale(0.8)

        # SFX volume.
        DirectLabel(
            text="SFX Volume",
            text_scale=0.04,
            text_fg=(0.8, 0.8, 1.0, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(slider_x - 0.05, 0, 0.25),
            parent=self._root,
        )
        sfx_val = self._settings_get("sfx_volume", 0.8)
        self._sfx_slider = DirectSlider(
            range=(0, 1),
            value=sfx_val,
            pageSize=0.01,
            orientation="horizontal",
            frameSize=(0, slider_w, -0.02, 0.02),
            pos=(slider_x, 0, 0.17),
            parent=self._root,
        )
        self._sfx_slider.setScale(0.8)

        # Music volume.
        DirectLabel(
            text="Music Volume",
            text_scale=0.04,
            text_fg=(0.8, 0.8, 1.0, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(slider_x - 0.05, 0, 0.0),
            parent=self._root,
        )
        music_val = self._settings_get("music_volume", 0.6)
        self._music_slider = DirectSlider(
            range=(0, 1),
            value=music_val,
            pageSize=0.01,
            orientation="horizontal",
            frameSize=(0, slider_w, -0.02, 0.02),
            pos=(slider_x, 0, -0.08),
            parent=self._root,
        )
        self._music_slider.setScale(0.8)

        # Graphics quality dropdown.
        DirectLabel(
            text="Graphics Quality",
            text_scale=0.04,
            text_fg=(0.8, 0.8, 1.0, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(slider_x - 0.05, 0, -0.35),
            parent=self._root,
        )
        current_quality = self._settings_get("graphics_quality", "high")
        self._quality_menu = DirectOptionMenu(
            items=["low", "medium", "high", "ultra"],
            initialitem=["low", "medium", "high", "ultra"].index(current_quality),
            scale=0.04,
            pos=(slider_x + 0.2, 0, -0.35),
            parent=self._root,
        )

        # Fullscreen toggle.
        fullscreen_val = self._settings_get("fullscreen", False)
        self._fullscreen_check = DirectCheckButton(
            text="Fullscreen",
            text_scale=0.04,
            text_fg=(0.8, 0.8, 1.0, 1.0),
            frameColor=(0, 0, 0, 0),
            pos=(slider_x, 0, -0.55),
            parent=self._root,
        )
        self._fullscreen_check["command"] = self._on_fullscreen_toggle

        # Back button.
        DirectButton(
            text="Back",
            text_scale=0.05,
            text_fg=(1, 1, 1, 1),
            text_hover_fg=(0.4, 0.8, 1.0, 1.0),
            frameColor=(0.15, 0.15, 0.25, 0.7),
            frameSize=(-0.15, 0.15, -0.04, 0.04),
            pos=(0, 0, -0.85),
            relief="raised",
            command=self._on_back,
            parent=self._root,
        )

        # Apply button.
        DirectButton(
            text="Apply",
            text_scale=0.05,
            text_fg=(1, 1, 1, 1),
            text_hover_fg=(0.4, 1.0, 0.4, 1.0),
            frameColor=(0.15, 0.25, 0.15, 0.7),
            frameSize=(-0.15, 0.15, -0.04, 0.04),
            pos=(0.3, 0, -0.85),
            relief="raised",
            command=self._on_apply_options,
            parent=self._root,
        )

    # ------------------------------------------------------------------ #
    #  Button callbacks                                                   #
    # ------------------------------------------------------------------ -->

    def _on_new_game(self) -> None:
        """Handle New Game button."""
        self._call_callback("new_game")

    def _on_continue(self) -> None:
        """Handle Continue button."""
        self._call_callback("continue")

    def _on_options(self) -> None:
        """Handle Options button — show the options menu."""
        self.show_menu(MenuType.OPTIONS)

    def _on_back(self) -> None:
        """Handle Back button — return to previous menu."""
        prev = MenuType.MAIN if self.current_menu == MenuType.OPTIONS else MenuType.MAIN
        self.show_menu(prev)

    def _on_resume(self) -> None:
        """Handle Resume button."""
        self._call_callback("resume")
        self.hide()

    def _on_quit_to_menu(self) -> None:
        """Handle Quit to Main Menu button."""
        self._call_callback("quit_to_menu")
        self.hide()

    def _on_quit(self) -> None:
        """Handle Quit button."""
        self._call_callback("quit_game")

    def _on_fullscreen_toggle(self) -> None:
        """Handle fullscreen checkbox toggle."""
        if self._fullscreen_check is not None and self.settings is not None:
            is_checked = self._fullscreen_check["isChecked"]
            self.settings.set("fullscreen", is_checked)

    def _on_apply_options(self) -> None:
        """Handle Apply button — write settings."""
        if self.settings is None:
            return

        # Read slider values.
        for attr_name, setting_key in [
            ("_master_slider", "master_volume"),
            ("_sfx_slider", "sfx_volume"),
            ("_music_slider", "music_volume"),
        ]:
            slider = getattr(self, attr_name, None)
            if slider is not None:
                self.settings.set(setting_key, slider["value"])

        # Read quality.
        if self._quality_menu is not None:
            self.settings.set("graphics_quality", self._quality_menu["itemText"])

        # Save.
        self.settings.save()
        self._call_callback("options_apply")
        logger.info("Settings applied and saved.")

    # ------------------------------------------------------------------ #
    #  Settings helpers                                                   #
    # ------------------------------------------------------------------ -->

    def _settings_get(self, key: str, default=None):
        """Get a setting value, handling the case where settings is None."""
        if self.settings is None:
            return default
        return self.settings.get(key, default)

    def _call_callback(self, name: str) -> None:
        """Invoke a registered callback by name, if it exists."""
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
        """Clean up all menu UI elements."""
        try:
            if self._root is not None:
                self._root.removeNode()
                self._root = None
        except Exception:
            logger.exception("Error destroying MenuManager.")


__all__ = [
    "MenuManager",
    "MenuType",
]
