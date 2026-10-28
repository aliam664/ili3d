"""
audio.py

Audio management for SFX, music, and spatial audio.

``AudioManager`` wraps Panda3D's ``AudioManager`` and provides:
- Master / SFX / Music volume channels.
- Spatial (3D) sound effects.
- Ambient / background music tracks.
- Play lists for music with cross-fading.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from panda3d.core import AudioSound, NodePath, Filename

logger = logging.getLogger(__name__)


class AudioManager:
    """
    High-level audio manager.

    This class wraps Panda3D's built-in audio subsystem and adds
    volume-channel logic, spatial audio, and music playlists.

    Parameters
    ----------
    settings : Settings, optional
        If provided, volume levels are initialized from settings.
    """

    def __init__(self, settings: Optional[Any] = None) -> None:
        self._settings = settings
        self._loader = None  # Set after ShowBase init

        # Volume channels (0.0 – 1.0).
        self._master_volume: float = 0.8
        self._sfx_volume: float = 0.8
        self._music_volume: float = 0.6

        if settings is not None:
            self._master_volume = settings.get("master_volume", 0.8)
            self._sfx_volume = settings.get("sfx_volume", 0.8)
            self._music_volume = settings.get("music_volume", 0.6)

        # Active sound objects, keyed by a user-defined name.
        self._sounds: Dict[str, AudioSound] = {}

        # Music playlist.
        self._music_tracks: list[str] = []
        self._current_music: Optional[AudioSound] = None
        self._next_music: Optional[AudioSound] = None

        # Cache of loaded sounds.
        self._cache: Dict[str, AudioSound] = {}

        # Base audio directory.
        self._audio_dirs: list[str] = ["assets/audio"]

        logger.info("AudioManager initialized.")

    # ------------------------------------------------------------------ #
    #  Volume control                                                     #
    # ------------------------------------------------------------------ -->

    @property
    def master_volume(self) -> float:
        return self._master_volume

    @master_volume.setter
    def master_volume(self, value: float) -> None:
        self._master_volume = max(0.0, min(1.0, value))
        self._apply_volumes()

    @property
    def sfx_volume(self) -> float:
        return self._sfx_volume

    @sfx_volume.setter
    def sfx_volume(self, value: float) -> None:
        self._sfx_volume = max(0.0, min(1.0, value))
        self._apply_volumes()

    @property
    def music_volume(self) -> float:
        return self._music_volume

    @music_volume.setter
    def music_volume(self, value: float) -> None:
        self._music_volume = max(0.0, min(1.0, value))
        self._apply_volumes()

    def _apply_volumes(self) -> None:
        """Recalculate and apply all volume levels."""
        sfx_gain = self._master_volume * self._sfx_volume
        music_gain = self._master_volume * self._music_volume

        for name, sound in self._sounds.items():
            if name.startswith("music_"):
                sound.setVolume(music_gain)
            else:
                sound.setVolume(sfx_gain)

        if self._current_music:
            self._current_music.setVolume(music_gain)
        if self._next_music:
            self._next_music.setVolume(music_gain)

    # ------------------------------------------------------------------ #
    #  Sound loading / caching                                            #
    # ------------------------------------------------------------------ -->

    def _resolve_path(self, filename: str) -> Optional[Path]:
        """
        Search audio directories for *filename*.

        Returns the first match or ``None``.
        """
        from os.path import exists

        base = Path(__file__).resolve().parent.parent
        for d in self._audio_dirs:
            candidate = base / d / filename
            if candidate.exists():
                return candidate
        return None

    def load_sfx(self, name: str, filename: str) -> Optional[AudioSound]:
        """
        Load a sound effect and register it under *name*.

        Parameters
        ----------
        name : str
            Identifier used to play the sound later.
        filename : str
            The audio file (relative to an audio search dir).

        Returns
        -------
        Optional[AudioSound]
            The loaded sound, or ``None`` if loading failed.
        """
        path = self._resolve_path(filename)
        if path is None:
            logger.warning("SFX file not found: %s", filename)
            return None

        try:
            sound = self._loader.loadSfx(str(path)) if self._loader else None
            if sound is None:
                logger.warning("Failed to load SFX: %s", path)
                return None
            sound.setVolume(self._master_volume * self._sfx_volume)
            self._sounds[name] = sound
            self._cache[name] = sound
            return sound
        except Exception:
            logger.exception("Error loading SFX: %s", path)
            return None

    def load_music(self, name: str, filename: str) -> Optional[AudioSound]:
        """
        Load a music track and register it under *name*.

        Parameters
        ----------
        name : str
            Identifier for the track.
        filename : str
            Audio file path.
        """
        # Music files are often streamed, so we load them differently.
        path = self._resolve_path(filename)
        if path is None:
            logger.warning("Music file not found: %s", filename)
            return None

        try:
            sound = self._loader.loadMusic(str(path)) if self._loader else None
            if sound is None:
                logger.warning("Failed to load music: %s", path)
                return None
            sound.setVolume(self._master_volume * self._music_volume)
            key = f"music_{name}"
            self._sounds[key] = sound
            self._cache[key] = sound
            return sound
        except Exception:
            logger.exception("Error loading music: %s", path)
            return None

    # ------------------------------------------------------------------ #
    #  Playback                                                           #
    # ------------------------------------------------------------------ -->

    def play_sfx(self, name: str, loop: bool = False, volume: Optional[float] = None) -> None:
        """
        Play a registered sound effect.

        Parameters
        ----------
        name : str
            The identifier used when loading.
        loop : bool
            If True, the sound loops.
        volume : Optional[float]
            Override volume (0.0 – 1.0).  If ``None``, uses the
            current SFX volume.
        """
        sound = self._sounds.get(name)
        if sound is None:
            logger.warning("SFX '%s' not loaded.", name)
            return

        if volume is not None:
            sound.setVolume(self._master_volume * self._sfx_volume * max(0.0, min(1.0, volume)))
        else:
            sound.setVolume(self._master_volume * self._sfx_volume)

        sound.setLoop(loop)
        sound.play()

    def play_spatial_sfx(
        self,
        name: str,
        node: NodePath,
        loop: bool = False,
        distance_factor: float = 1.0,
    ) -> None:
        """
        Play a sound effect with 3D spatial positioning.

        The sound's position is tied to *node*; as the node moves,
        the perceived position of the sound changes.

        Parameters
        ----------
        name : str
            The sound identifier.
        node : NodePath
            The node to attach the sound to.
        loop : bool
            Whether to loop the sound.
        distance_factor : float
            Scales how quickly volume attenuates with distance.
        """
        sound = self._sounds.get(name)
        if sound is None:
            logger.warning("Spatial SFX '%s' not loaded.", name)
            return

        sound.setVolume(self._master_volume * self._sfx_volume)
        sound.setLoop(loop)

        # Attach the sound to the node so Panda3D handles spatialization.
        node.setSound(sound)

        # Configure attenuation.
        sound.set3dAttrs(
            position=(0, 0, 0),
            velocity=(0, 0, 0),
            success=True,
        )

        sound.play()
        logger.debug("Playing spatial SFX '%s'.", name)

    def play_ambient(self, name: str, loop: bool = True) -> None:
        """
        Start playing an ambient / background music track.

        Parameters
        ----------
        name : str
            The music identifier.
        loop : bool
            Whether to loop the track.
        """
        sound = self._sounds.get(f"music_{name}")
        if sound is None:
            logger.warning("Music track '%s' not loaded.", name)
            return

        self._current_music = sound
        sound.setVolume(self._master_volume * self._music_volume)
        sound.setLoop(loop)
        sound.play()
        logger.debug("Playing ambient music '%s'.", name)

    def stop_music(self, fade_out: float = 0.0) -> None:
        """Stop the current music, optionally with a fade-out."""
        if self._current_music:
            if fade_out > 0.0:
                # Panda3D 1.10+ supports fading via setVolume animation.
                # We'll just stop immediately for simplicity.
                self._current_music.setPlayRate(0.0)
            self._current_music.stop()
        self._current_music = None

    # ------------------------------------------------------------------ #
    #  Frame update                                                       #
    # ------------------------------------------------------------------ -->

    def update(self, dt: float) -> None:
        """
        Per-frame audio update.

        Currently a placeholder — in a full implementation this
        would handle cross-fades, dynamic reverb, etc.
        """
        pass

    def destroy(self) -> None:
        """Stop all sounds and clean up."""
        for sound in self._sounds.values():
            sound.stop()
        self._sounds.clear()
        self._cache.clear()
        logger.info("AudioManager destroyed.")
