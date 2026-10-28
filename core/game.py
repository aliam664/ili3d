"""
game.py

Main game class that extends ``ShowBase``.

This is the central hub that wires together all subsystems:
rendering, state management, input, audio, player, and world.
"""

from __future__ import annotations

import logging
from typing import Optional

from panda3d.core import (
    WindowProperties,
    load_prc_file_data,
)
from panda3d.core import ClockObject
from direct.showbase.ShowBase import ShowBase


# globalClock is set by ShowBase after initialization.
globalClock = ClockObject.getGlobalClock()
from direct.gui import DirectGuiGlobals as DGG  # noqa: F401  (sets up GUI globals)

from config import GameConfig
from config import Settings
from config.constants import Constants

from core.states import GameState, StateManager
from core.audio import AudioManager
from core.scene import SceneManager

from systems.stats import PlayerStats
from systems.progression import PlayerProgression
from weapons.weapon_manager import WeaponManager
from missions import MissionManager
from modes import ModeManager

logger = logging.getLogger(__name__)


class Game(ShowBase):
    """
    Core game engine class.

    Extends Panda3D's ``ShowBase`` and orchestrates the lifecycle:
    initialization, state transitions, and the main update loop.

    Parameters
    ----------
    config : GameConfig, optional
        Static game configuration.  Defaults to a fresh ``GameConfig``.
    settings : Settings, optional
        User settings.  Defaults to a fresh ``Settings`` instance
        loaded from disk.
    """

    def __init__(
        self,
        config: Optional[GameConfig] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        # ------------------------------------------------------------------
        # Store configuration
        # ------------------------------------------------------------------
        self.game_config: GameConfig = config or GameConfig()
        self.settings: Settings = settings or Settings()
        self.constants = Constants

        # ------------------------------------------------------------------
        # Apply engine-level settings BEFORE ShowBase.__init__
        # ------------------------------------------------------------------
        self._apply_engine_settings()

        # ------------------------------------------------------------------
        # Initialize ShowBase (creates the window, camera, task manager)
        # ------------------------------------------------------------------
        # We defer disabling the built-in mouse-based camera control
        # until after ShowBase init, then turn it off.
        super().__init__()

        # Disable the default mouse fly camera.
        self.disable_mouse()

        # ------------------------------------------------------------------
        # Core subsystems
        # ------------------------------------------------------------------
        self.state_mgr: StateManager = StateManager()
        self.audio_mgr: AudioManager = AudioManager(self.settings)
        self.audio_mgr._loader = self.loader  # Set loader reference after ShowBase init
        self.scene_mgr: SceneManager = SceneManager(self)

        # Game systems that need the full Game instance.
        self.stats: PlayerStats = PlayerStats()
        self.progression: PlayerProgression = PlayerProgression()
        self.weapon_mgr: WeaponManager = WeaponManager(self.render, self.camera, self.cTrav)
        self.mission_mgr: MissionManager = MissionManager(self)
        self.mode_mgr: ModeManager = ModeManager(self)

        # ------------------------------------------------------------------
        # Game-loop bookkeeping
        # ------------------------------------------------------------------
        self._running: bool = False
        self._dt: float = 0.0  # delta time, seconds

        # ------------------------------------------------------------------
        # Wire up state callbacks
        # ------------------------------------------------------------------
        self._register_state_callbacks()

        # ------------------------------------------------------------------
        # Input handling
        # ------------------------------------------------------------------
        self._setup_input()

        # ------------------------------------------------------------------
        # Post-startup: enter LOADING, then MENU
        # ------------------------------------------------------------------
        logger.info("Game initialized. Version %s", self.game_config.version)

    # ------------------------------------------------------------------ #
    #  Engine configuration                                               #
    # ------------------------------------------------------------------ -->

    def _apply_engine_settings(self) -> None:
        """
        Push Panda3D prc settings before the window is created.

        Window size, fullscreen mode, V-sync, and model search paths
        are configured here.  We use ``load_prc_file_data`` so
        settings take effect at the earliest possible point.
        """
        # Set window properties.
        width = self.settings.get("window_width", self.game_config.window_width)
        height = self.settings.get("window_height", self.game_config.window_height)
        fullscreen = self.settings.get("fullscreen", False)
        vsync = self.settings.get("vsync", True)

        load_prc_file_data(
            "",
            f"win-size {width} {height}\n"
            f"fullscreen {str(fullscreen).lower()}\n"
            f"sync-video {str(vsync).lower()}\n"
            "show-frame-rate-meter #t\n"
            f"window-title {self.game_config.game_title} v{self.game_config.version}\n",
        )

        # Register model search paths so Panda3D can find assets
        # via relative paths.
        model_dirs = self.game_config.get_model_dirs()
        for d in model_dirs:
            load_prc_file_data("", f"model-path {d}")

    # ------------------------------------------------------------------ #
    #  State management                                                   #
    # ------------------------------------------------------------------ -->

    def _register_state_callbacks(self) -> None:
        """Register enter / exit callbacks for each game state."""
        self.state_mgr.register_enter(GameState.LOADING, self._enter_loading)
        self.state_mgr.register_exit(GameState.LOADING, self._exit_loading)

        self.state_mgr.register_enter(GameState.MENU, self._enter_menu)
        self.state_mgr.register_exit(GameState.MENU, self._exit_menu)

        self.state_mgr.register_enter(GameState.PLAYING, self._enter_playing)
        self.state_mgr.register_exit(GameState.PLAYING, self._exit_playing)

        self.state_mgr.register_enter(GameState.PAUSED, self._enter_paused)
        self.state_mgr.register_exit(GameState.PAUSED, self._exit_paused)

    def _enter_loading(self) -> None:
        """Enter the LOADING state — show a loading screen."""
        logger.info("Entering LOADING state.")
        self._running = False

    def _exit_loading(self) -> None:
        """Exit the LOADING state."""
        logger.info("Exiting LOADING state.")

    def _enter_menu(self) -> None:
        """Enter the MENU state — show the main menu, hide gameplay."""
        logger.info("Entering MENU state.")
        self._running = False
        self.scene_mgr.hide_world()

    def _exit_menu(self) -> None:
        """Exit the MENU state."""
        logger.info("Exiting MENU state.")

    def _enter_playing(self) -> None:
        """Enter the PLAYING state — start the game clock and accept input."""
        logger.info("Entering PLAYING state.")
        self._running = True
        self.scene_mgr.show_world()
        self.audio_mgr.play_ambient("main_theme")

    def _exit_playing(self) -> None:
        """Exit the PLAYING state."""
        logger.info("Exiting PLAYING state.")
        self._running = False

    def _enter_paused(self) -> None:
        """Enter the PAUSED state — freeze the game clock."""
        logger.info("Entering PAUSED state.")
        self._running = False
        self.set_clock_frame_rate(0)  # freeze time
        # Show pause menu overlay.

    def _exit_paused(self) -> None:
        """Exit the PAUSED state."""
        logger.info("Exiting PAUSED state.")
        self.set_clock_frame_rate()

    # ------------------------------------------------------------------ #
    #  Input handling                                                     #
    # ------------------------------------------------------------------ -->

    def _setup_input(self) -> None:
        """Bind global input keys (escape to quit, etc.)."""
        self.accept("escape", self._on_escape)

    def _on_escape(self) -> None:
        """Toggle between PLAYING and PAUSED."""
        if self.state_mgr.is_state(GameState.PLAYING):
            self.state_mgr.change_state(GameState.PAUSED)
        elif self.state_mgr.is_state(GameState.PAUSED):
            self.state_mgr.change_state(GameState.PLAYING)

    # ------------------------------------------------------------------ #
    #  Update loop                                                        #
    # ------------------------------------------------------------------ -->

    def setup(self) -> None:
        """
        Public setup method called after construction.

        This is where the player controller and initial world are
        created, because they depend on Panda3D objects that are
        only available after ``ShowBase.__init__`` completes.
        """
        # Load the initial world.
        self.scene_mgr.load_world("cyberpunk_city")

        # Set up the player (done here so all ShowBase resources exist).
        self._setup_player()

        # Transition to the main menu, then auto-start for demo.
        self.state_mgr.change_state(GameState.LOADING)
        self.state_mgr.change_state(GameState.MENU)
        # For this demo build, auto-enter PLAYING:
        self.state_mgr.change_state(GameState.PLAYING)

    def _setup_player(self) -> None:
        """
        Create the player controller and attach it to the camera.

        Uses lazy imports to avoid circular references.
        """
        try:
            from player.controller import PlayerController

            self.player: PlayerController = PlayerController(self)
            # The player controller takes ownership of the camera.
            self.camera.reparent_to(self.player.node)
            logger.info("Player controller created.")
        except Exception:
            logger.exception("Failed to create player controller.")
            self.player = None

    def update(self, task) -> int:
        """
        Main per-frame update task.

        Parameters
        ----------
        task : Task
            The Panda3D task object.

        Returns
        -------
        int
            ``task.cont`` to keep the task running.
        """
        dt = globalClock.getDt()
        self._dt = dt

        if self._running:
            if self.player is not None:
                self.player.update(dt)
            self.scene_mgr.update(dt)
            self.audio_mgr.update(dt)
            self.mission_mgr.update(dt)
            self.mode_mgr.update(dt)

        return task.cont

    # ------------------------------------------------------------------ #
    #  Entry point                                                        #
    # ------------------------------------------------------------------ -->

    def run_game(self) -> None:
        """
        Start the game loop.

        Call this instead of the default ``ShowBase.run`` to ensure
        ``setup`` has been called and the update task is registered.
        """
        self.setup()
        self.taskMgr.add(self.update, "game-update")
        self.state_mgr.change_state(GameState.PLAYING)
        super().run()
