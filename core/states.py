"""
states.py

Game state management.

The game transitions between distinct states (MENU, PLAYING, PAUSED,
etc.) and each state can have its own set of active systems, UI layers,
and input behaviors.  ``StateManager`` is a simple finite-state
machine with enter / exit hooks.
"""

from __future__ import annotations

import enum
import logging
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class GameState(enum.Enum):
    """
    Enumeration of every possible game state.

    Each value is a string for easy serialization / display.
    """

    UNINITIALIZED = "uninitialized"
    LOADING = "loading"
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    CUTSCENE = "cutscene"
    GAME_OVER = "game_over"
    OPTIONS = "options"
    MISSION_COMPLETE = "mission_complete"

    def __str__(self) -> str:
        return self.value


class StateManager:
    """
    Finite-state machine for game states.

    ``StateManager`` is a *singleton per Game instance*.  It tracks
    the current state and notifies registered callbacks whenever the
    state changes.  Typical usage in ``Game``::

        self.state_mgr = StateManager()
        self.state_mgr.register_enter(GameState.PLAYING, self._enter_playing)
        self.state_mgr.register_exit(GameState.PLAYING, self._exit_playing)

    Attributes
    ----------
    current_state : GameState
        The active game state.
    previous_state : Optional[GameState]
        The state the game was in before the current one (``None``
        at startup).
    """

    _instance: Optional["StateManager"] = None

    # ------------------------------------------------------------------ #
    #  Construction                                                        #
    # ------------------------------------------------------------------ #

    def __new__(cls) -> "StateManager":
        """Enforce singleton — only one StateManager per process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized: bool = True

        self._current_state: GameState = GameState.UNINITIALIZED
        self._previous_state: Optional[GameState] = None

        #: Maps GameState -> list of enter callbacks.
        self._enter_callbacks: Dict[GameState, list[Callable]] = {}
        #: Maps GameState -> list of exit callbacks.
        self._exit_callbacks: Dict[GameState, list[Callable]] = {}

        #: When True, a request to change to the same state is a no-op.
        self._allow_reenter_same: bool = False

    # ------------------------------------------------------------------ #
    #  State access                                                       #
    # ------------------------------------------------------------------ #

    @property
    def current_state(self) -> GameState:
        """Return the current game state."""
        return self._current_state

    @property
    def previous_state(self) -> Optional[GameState]:
        """Return the previous game state, or ``None`` if this is the first switch."""
        return self._previous_state

    def is_state(self, *states: GameState) -> bool:
        """
        Check whether the current state matches any of *states*.

        Parameters
        ----------
        *states : GameState
            One or more states to test against.

        Returns
        -------
        bool
            True if the current state is in *states*.
        """
        return self._current_state in states

    # ------------------------------------------------------------------ #
    #  Callback registration                                              #
    # ------------------------------------------------------------------ #

    def register_enter(self, state: GameState, callback: Callable[[], None]) -> None:
        """
        Register a callback invoked when entering *state*.

        Parameters
        ----------
        state : GameState
            The state to listen for.
        callback : callable
            A zero-argument function called on state entry.
        """
        self._enter_callbacks.setdefault(state, []).append(callback)

    def register_exit(self, state: GameState, callback: Callable[[], None]) -> None:
        """
        Register a callback invoked when exiting *state*.

        Parameters
        ----------
        state : GameState
            The state to listen for.
        callback : callable
            A zero-argument function called on state exit.
        """
        self._exit_callbacks.setdefault(state, []).append(callback)

    def unregister_enter(self, state: GameState, callback: Callable[[], None]) -> None:
        """Remove a previously-registered enter callback."""
        if state in self._enter_callbacks and callback in self._enter_callbacks[state]:
            self._enter_callbacks[state].remove(callback)

    def unregister_exit(self, state: GameState, callback: Callable[[], None]) -> None:
        """Remove a previously-registered exit callback."""
        if state in self._exit_callbacks and callback in self._exit_callbacks[state]:
            self._exit_callbacks[state].remove(callback)

    # ------------------------------------------------------------------ #
    #  State transitions                                                  #
    # ------------------------------------------------------------------ #

    def change_state(self, new_state: GameState) -> None:
        """
        Transition from the current state to *new_state*.

        This fires all exit callbacks for the *current* state,
        then all enter callbacks for *new_state*.  If
        ``new_state`` equals the current state and
        ``allow_reenter_same`` is ``False`` (default), the
        transition is skipped silently.

        Parameters
        ----------
        new_state : GameState
            The state to transition to.
        """
        if new_state == self._current_state and not self._allow_reenter_same:
            logger.debug("State change ignored — already in %s.", new_state)
            return

        logger.info("State change: %s -> %s", self._current_state, new_state)

        # Fire exit callbacks for the outgoing state.
        self._fire_callbacks(self._exit_callbacks.get(self._current_state, []))

        self._previous_state = self._current_state
        self._current_state = new_state

        # Fire enter callbacks for the incoming state.
        self._fire_callbacks(self._enter_callbacks.get(new_state, []))

    def push_state(self, new_state: GameState) -> None:
        """
        Alias for :meth:`change_state`.

        The name ``push_state`` is retained for compatibility and
        to mirror common game-engine terminology (a stack-like
        mental model).
        """
        self.change_state(new_state)

    def pop_state(self) -> Optional[GameState]:
        """
        Return to the previous state if one exists.

        Returns
        -------
        Optional[GameState]
            The new current state, or ``None`` if there was no
            previous state to return to.
        """
        if self._previous_state is not None:
            target = self._previous_state
            self._previous_state = None  # simple — no full state stack
            self.change_state(target)
            return self._current_state
        logger.warning("pop_state() called but no previous state to return to.")
        return None

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ -->

    @staticmethod
    def _fire_callbacks(callbacks: list[Callable]) -> None:
        """Execute a list of callbacks, catching and logging exceptions."""
        for cb in callbacks:
            try:
                cb()
            except Exception:
                logger.exception("State callback raised an exception.")
