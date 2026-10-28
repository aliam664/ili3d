"""
scene.py

Scene / level management.

``SceneManager`` is responsible for:
- Loading and unloading world geometry.
- Setting up ambient and directional lighting.
- Creating the skybox / skysphere.
- Hiding / showing the world between states.
"""

from __future__ import annotations

import logging
from typing import Optional

from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    NodePath,
    TransparencyAttrib,
    Vec3,
    Vec4,
    load_prc_file_data,
)

logger = logging.getLogger(__name__)


class SceneManager:
    """
    High-level scene management.

    Parameters
    ----------
    game : Game
        Reference to the parent Game instance (for access to
        ``loader``, ``render``, etc.).
    """

    #: Registry of world name -> world module path.
    #: Worlds are loaded by importing the corresponding module
    #: and instantiating its ``World`` class.
    WORLD_REGISTRY: dict[str, str] = {
        "cyberpunk_city": "worlds.cyberpunk_city.CyberpunkCity",
        "wasteland": "worlds.wasteland.Wasteland",
        "military_facility": "worlds.military_facility.MilitaryFacility",
        "jungle": "worlds.jungle.Jungle",
        "arctic": "worlds.arctic.Arctic",
        "space_station": "worlds.space_station.SpaceStation",
        "fantasy": "worlds.fantasy.Fantasy",
    }

    def __init__(self, game: "Game") -> None:
        self.game = game
        self._world_root: Optional[NodePath] = None  # container for world geometry
        self._current_world = None  # the World instance, if loaded
        self._skybox: Optional[NodePath] = None
        self._lights: dict[str, NodePath] = {}

    # ------------------------------------------------------------------ #
    #  World loading / unloading                                          #
    # ------------------------------------------------------------------ -->

    def load_world(self, world_name: str) -> Optional["World"]:
        """
        Load a world by name.

        Parameters
        ----------
        world_name : str
            Key into ``WORLD_REGISTRY``.

        Returns
        -------
        Optional[World]
            The loaded world instance, or ``None`` on failure.
        """
        if world_name not in self.WORLD_REGISTRY:
            logger.error("Unknown world: %s", world_name)
            return None

        module_path = self.WORLD_REGISTRY[world_name]
        try:
            module_full, class_name = module_path.rsplit(".", 1)
            mod = __import__(module_full, fromlist=[class_name])
            world_cls = getattr(mod, class_name)
            self._current_world = world_cls(self.game)
            logger.info("World '%s' loaded.", world_name)
            return self._current_world
        except Exception:
            logger.exception("Failed to load world '%s'.", world_name)
            return None

    def hide_world(self) -> None:
        """Hide the current world geometry (called on pause / menu)."""
        if self._world_root is not None:
            self._world_root.hide()

    def show_world(self) -> None:
        """Show the current world geometry."""
        if self._world_root is not None:
            self._world_root.show()

    # ------------------------------------------------------------------ #
    #  Lighting setup                                                     #
    # ------------------------------------------------------------------ -->

    def setup_lighting(self) -> None:
        """
        Create default ambient + directional lighting for the scene.

        Called by the world's own setup, but can be invoked standalone.
        """
        # Ambient light — provides a base fill so shadows aren't
        # completely black.
        ambient = AmbientLight("ambient")
        ambient.setColor(Vec4(0.3, 0.3, 0.35, 1.0))
        al_np = self.game.render.attachNewNode(ambient)
        self._lights["ambient"] = al_np
        self.game.render.setLight(al_np)

        # Directional light — simulates the sun / main light source.
        dlight = DirectionalLight("sun")
        dlight.setColor(Vec4(0.8, 0.75, 0.6, 1.0))
        dlight.setDirection(Vec3(-0.5, -0.7, -0.5).normalized())
        dlight_np = self.game.render.attachNewNode(dlight)
        self._lights["sun"] = dlight_np
        self.game.render.setLight(dlight_np)

        logger.info("Default lighting set up.")

    # ------------------------------------------------------------------ #
    #  Skybox / Skysphere                                                 #
    # ------------------------------------------------------------------ -->

    def create_sky(self) -> None:
        """
        Create a simple skysphere.

        If an actual skybox model exists in the assets, it would be
        loaded here.  For now we create a colored sphere that moves
        with the camera.
        """
        try:
            # Try to load a real skysphere model first.
            sky = self.game.loader.loadModel("assets/models/skysphere")
            if sky is not None:
                sky.reparentTo(self.game.camera)
                sky.setScale(5000)
                sky.setShaderAuto()
                # Sky should not receive lighting.
                sky.setLightOff()
                sky.setFogOff()
                self._skybox = sky
                logger.info("Skysphere model loaded from assets.")
                return
        except Exception:
            logger.debug("No skysphere model found; falling back to procedural sky.")

        # Fallback: create a simple colored sphere via raw geometry.
        self._create_fallback_sky()

    def _create_fallback_sky(self) -> None:
        """
        Create a simple colored hemisphere as a fallback sky.

        This uses raw Panda3D geometry construction.
        """
        from panda3d.core import (
            Geom,
            GeomNode,
            GeomTriangles,
            GeomVertexData,
            GeomVertexFormat,
            GeomVertexWriter,
            NodePath,
        )
        import math

        format = GeomVertexFormat.getV3t2()
        vdata = GeomVertexData("sky", format, Geom.UH_static)
        vdata.setNumRows(362)

        vertex = GeomVertexWriter(vdata, "vertex")
        texcoord = GeomVertexWriter(vdata, "texcoord")

        # Build a UV sphere.
        lat_steps = 32
        lon_steps = 32
        for i in range(lat_steps + 1):
            phi = math.pi * i / lat_steps
            for j in range(lon_steps + 1):
                theta = 2 * math.pi * j / lon_steps
                x = math.sin(phi) * math.cos(theta)
                y = math.cos(phi)
                z = math.sin(phi) * math.sin(theta)
                vertex.addData3(x, y, z)
                # Simple UV mapping.
                texcoord.addData2(j / lon_steps, i / lat_steps)

        prim = GeomTriangles(Geom.UH_static)
        for i in range(lat_steps):
            for j in range(lon_steps):
                a = i * (lon_steps + 1) + j
                b = a + lon_steps + 1
                c = a + 1
                d = b + 1
                if i > 0:
                    prim.addVertices(a, b, c)
                if i < lat_steps - 1:
                    prim.addVertices(c, b, d)

        geom = Geom(vdata)
        geom.addPrimitive(prim)

        node = GeomNode("sky_fallback")
        node.addGeom(geom)

        sky = NodePath(node)
        sky.reparentTo(self.game.camera)
        sky.setScale(5000)
        sky.setShaderAuto()
        sky.setLightOff()
        sky.setFogOff()
        # Color the inside of the sphere.
        sky.setColor(Vec3(0.1, 0.1, 0.3), 1)
        self._skybox = sky
        logger.info("Fallback procedural sky (manual sphere) created.")

    # ------------------------------------------------------------------ #
    #  Per-frame                                                         #
    # ------------------------------------------------------------------ -->

    def update(self, dt: float) -> None:
        """
        Per-frame update.

        Parameters
        ----------
        dt : float
            Delta time in seconds.
        """
        # Skybox follows camera position.
        if self._skybox is not None and self._skybox.isEmpty() is False:
            self._skybox.setPos(self.game.camera.getPos())
