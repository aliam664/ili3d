"""
world_base.py

Base World class -- provides the foundation for all levels.

A ``World`` is responsible for:
- Loading the level geometry (collision + render).
- Setting up lighting specific to this level.
- Creating the skybox / skysphere.
- Spawning initial entities (later: enemies, pickups, etc.).
- Providing a floor plane for testing movement.

Subclasses override ``_load_geometry`` and ``_setup_level``
to define the actual content.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Fog,
    GeomNode,
    Material,
    NodePath,
    PointLight,
    Point3,
    TransparencyAttrib,
    Vec3,
    Vec4,
)
from direct.showbase.ShowBase import ShowBase

from core.scene import SceneManager

logger = logging.getLogger(__name__)


class World:
    """
    Base world / level class.

    Parameters
    ----------
    game : ShowBase
        The parent game instance.
    """

    #: Collision mask used for world geometry.
    COLLISION_MASK_GEOMETRY = 0x0001

    #: Fog settings (worlds may override these).
    DEFAULT_FOG_COLOR: Vec4 = Vec4(0.1, 0.1, 0.2, 1.0)
    DEFAULT_FOG_DENSITY: float = 0.003

    #: Ambient light color.
    DEFAULT_AMBIENT_COLOR: Vec4 = Vec4(0.25, 0.25, 0.3, 1.0)

    #: Directional (sun) color and direction.
    DEFAULT_SUN_COLOR: Vec4 = Vec4(0.9, 0.85, 0.7, 1.0)
    DEFAULT_SUN_DIRECTION: Vec3 = Vec3(-0.6, -0.6, -0.6).normalized()

    def __init__(self, game: "ShowBase") -> None:
        self.game = game
        self.scene_mgr: SceneManager = game.scene_mgr

        # Root node that holds all world geometry.
        # Hiding / showing this node toggles visibility.
        self.world_root: NodePath = self.game.render.attachNewNode("world_root")

        # Collision geometry -- parented under a separate node so
        # we can hide it in production builds.
        self.collision_root: NodePath = self.game.render.attachNewNode("collision_root")

        # Storage for entities.
        self._entities: list = []

        # Tracked resources for cleanup.
        self._point_lights: list[NodePath] = []
        self._fog: Optional[Fog] = None
        self._music_sound = None  # AudioSound for background music

        # State.
        self._is_loaded: bool = False

        # Perform world-specific setup.
        self._init_world()

    # ------------------------------------------------------------------ #
    #  World lifecycle                                                    #
    # ------------------------------------------------------------------ -->

    def _init_world(self) -> None:
        """
        Perform the full world initialization sequence.

        This method is called from ``__init__`` and orchestrates:
        geometry loading, lighting, sky, and entity placement.
        """
        self._setup_lighting()
        self._load_geometry()
        self._setup_sky()
        self._setup_collision()
        self._spawn_entities()
        self._setup_fog()

        self._is_loaded = True
        logger.info("World '%s' initialized.", self.__class__.__name__)

    def _setup_lighting(self) -> None:
        """
        Set up level-specific lighting.

        The base implementation creates a standard
        ambient + directional light rig.  Subclasses can
        override to add volumetric lights, fog, etc.
        """
        # Ambient light.
        ambient = AmbientLight("world_ambient")
        ambient.setColor(self.DEFAULT_AMBIENT_COLOR)
        al_np = self.world_root.attachNewNode(ambient)
        self.world_root.setLight(al_np)

        # Directional light (sun).
        dlight = DirectionalLight("world_sun")
        dlight.setColor(self.DEFAULT_SUN_COLOR)
        dlight.setDirection(self.DEFAULT_SUN_DIRECTION)
        # Cast shadows (Panda3D 1.10+).
        dlight.setShadowCaster(True, 2048, 2048)
        dlight_np = self.world_root.attachNewNode(dlight)
        self.world_root.setLight(dlight_np)

        # Enable automatic shader generation for lighting.
        self.world_root.setShaderAuto()

        logger.info("World lighting set up.")

    def _load_geometry(self) -> None:
        """
        Load the world's visual geometry.

        The base implementation creates a simple floor for testing.
        Subclasses should override this to load real level meshes.
        """
        self._create_floor()

    def _create_floor(self) -> None:
        """
        Create a simple flat floor for player movement testing.

        Uses a large CardMaker-generated quad with a grid-like
        texture or color pattern.
        """
        from panda3d.core import CardMaker

        cm = CardMaker("floor")
        cm.setFrame(-100, 100, -100, 100)
        floor = self.world_root.attachNewNode(cm.generate())
        floor.setHpr(0, -90, 0)  # rotate to be horizontal
        floor.setZ(-1.0)  # set height

        # Give the floor a visible color pattern.
        # Create a simple grid by using vertex colors on a subdivided plane.
        floor.setColor(0.3, 0.3, 0.3, 1.0)

        # Create a more detailed floor with a repeating pattern.
        from panda3d.core import (
            Geom,
            GeomNode as PandaGeomNode,
            GeomTriangles,
            GeomVertexData,
            GeomVertexFormat,
            GeomVertexWriter,
        )

        # Create a grid of quads.
        grid_size = 20
        cell_size = 10.0
        half_grid = grid_size * cell_size / 2

        format = GeomVertexFormat.getV3t2()
        vdata = GeomVertexData("grid_floor", format, Geom.UH_static)
        vdata.setNumRows((grid_size + 1) * (grid_size + 1))

        vertex = GeomVertexWriter(vdata, "vertex")
        texcoord = GeomVertexWriter(vdata, "texcoord")

        # Generate vertices for the grid.
        for i in range(grid_size + 1):
            for j in range(grid_size + 1):
                x = i * cell_size - half_grid
                y = j * cell_size - half_grid
                vertex.addData3(x, y, 0)
                texcoord.addData2(i / grid_size, j / grid_size)

        # Generate triangles.
        prim = GeomTriangles(Geom.UH_static)
        for i in range(grid_size):
            for j in range(grid_size):
                a = i * (grid_size + 1) + j
                b = a + 1
                c = a + (grid_size + 1)
                d = c + 1

                # Two triangles per cell.
                prim.addVertices(a, b, c)
                prim.addVertices(c, b, d)

        geom = Geom(vdata)
        geom.addPrimitive(prim)

        node = PandaGeomNode("floor_geom")
        node.addGeom(geom)

        # Replace the simple floor with the detailed grid.
        floor.removeNode()
        floor = self.world_root.attachNewNode(node)
        floor.setHpr(0, -90, 0)
        floor.setZ(-1.0)
        floor.setColor(0.35, 0.3, 0.35, 1.0)

        logger.info("Floor created (grid: %dx%d cells).", grid_size, grid_size)

    def _setup_sky(self) -> None:
        """Create the skybox or skysphere for this world."""
        self.scene_mgr.create_sky()

    def _setup_collision(self) -> None:
        """
        Set up collision geometry for the world.

        The base implementation creates invisible collision planes
        for the floor.  Subclasses should call this and add walls.
        """
        from panda3d.core import CollisionNode, CollisionPlane, Plane, Point3

        # Floor collision plane.
        floor_plane = CollisionPlane(Plane(Vec3(0, 0, 1), Point3(0, 0, -1)))

        cnode = CollisionNode("world_floor_collision")
        cnode.addSolid(floor_plane)
        cnode.setIntoCollideMask(self._get_collision_mask())
        cnode.setTag("geometry", "floor")

        self.collision_root.attachNewNode(cnode)

        logger.info("World collision geometry set up.")

    def _get_collision_mask(self):
        """Return the collision mask for world geometry."""
        from panda3d.core import BitMask32
        # Import locally to avoid circular dependency.
        from config.constants import Constants
        return Constants.MASK_GEOMETRY

    def _spawn_entities(self) -> None:
        """
        Spawn entities into the world.

        Base implementation is empty.  Subclasses override to
        spawn enemies, pickups, items, etc.
        """
        logger.info("No entities to spawn in base world.")

    def _setup_fog(self) -> None:
        """
        Set up fog for the world.

        Uses exponential fog by default.  Subclasses can override
        ``_configure_fog`` to change the mode and parameters.
        """
        self._fog = Fog("world_fog")
        self._fog.set_color(self.DEFAULT_FOG_COLOR)
        self._fog.set_exp_density(self.DEFAULT_FOG_DENSITY)
        self.world_root.set_fog(self._fog)

        # Also apply to the base render for global effect.
        self.game.render.set_fog(self._fog)
        logger.debug("Fog configured.")

    def _configure_fog(
        self,
        color: Vec4,
        mode: str = "exponential",
        density: float = 0.005,
        start: float = 10.0,
        end: float = 100.0,
    ) -> None:
        """
        Reconfigure fog parameters at runtime.

        Args:
            color: RGBA fog color.
            mode: ``"exponential"`` or ``"linear"``.
            density: Fog density for exponential mode.
            start: Near distance for linear mode.
            end: Far distance for linear mode.
        """
        if self._fog is None:
            self._fog = Fog("world_fog")
            self.world_root.set_fog(self._fog)
            self.game.render.set_fog(self._fog)

        self._fog.set_color(color)
        if mode == "exponential":
            self._fog.set_exp_density(density)
        elif mode == "linear":
            self._fog.set_linear_range(start, end)

        logger.debug("Fog reconfigured: mode=%s, color=%s", mode, color)

    def _add_point_light(
        self,
        name: str,
        color: Vec4,
        position: Vec3,
        attenuation: Optional[Vec3] = None,
    ) -> NodePath:
        """
        Create and attach a point light to the world.

        Args:
            name: Name for the light (used in node path naming).
            color: RGBA color of the light (intensity in RGB channels).
            position: World-space position for the light.
            attenuation: (constant, linear, quadratic) falloff.
                         If None, a standard quadratic attenuation is used.

        Returns:
            The NodePath of the created point light.
        """
        plight = PointLight(f"plight_{name}")
        plight.set_color(color)
        if attenuation is not None:
            plight.set_attenuation(attenuation)
        else:
            plight.set_attenuation(Vec3(0.0, 0.0, 1.0))

        plight_np = self.world_root.attachNewNode(plight)
        plight_np.set_pos(position)
        self.world_root.setLight(plight_np)
        self._point_lights.append(plight_np)
        return plight_np

    def _setup_audio(self) -> None:
        """
        Set up background music for this world.

        Subclasses can override ``get_music_path`` to provide a music file.
        Falls back to the game's AudioManager if available.
        """
        music_path = self.get_music_path()
        if music_path and os.path.exists(music_path):
            try:
                self._music_sound = self.game.loader.loadSfx(music_path)
                if self._music_sound is not None:
                    self._music_sound.set_loop(True)
                    self._music_sound.set_volume(self.game.settings.get("music_volume", 0.6))
                    self._music_sound.play()
                    logger.debug("Background music loaded: %s", music_path)
            except Exception:
                logger.exception("Failed to load background music.")

    def _stop_music(self) -> None:
        """Stop the currently playing background music, if any."""
        if self._music_sound is not None:
            self._music_sound.stop()
            self._music_sound = None

    def _create_material(
        self,
        name: str,
        diffuse: Vec4,
        ambient: Vec4,
        specular: Vec4,
        shininess: float,
        emissive: Optional[Vec4] = None,
    ) -> Material:
        """
        Create a configured Material.

        Args:
            name: Name for the material (for debugging).
            diffuse: Diffuse color.
            ambient: Ambient color.
            specular: Specular highlight color.
            shininess: Shininess exponent (higher = sharper highlights).
            emissive: Optional emissive color (glows without lighting).

        Returns:
            A configured Material.
        """
        mat = Material()
        mat.set_name(name)
        mat.set_diffuse(diffuse)
        mat.set_ambient(ambient)
        mat.set_specular(specular)
        mat.set_shininess(shininess)
        if emissive is not None:
            mat.set_emission(emissive)
        return mat

    def _make_box_nodepath(
        self,
        width: float,
        depth: float,
        height: float,
        name: str = "box",
    ) -> NodePath:
        """
        Create a box (rectangular prism) as a NodePath.

        Args:
            width: X-axis extent.
            depth: Y-axis extent.
            height: Z-axis extent.
            name: Name for the NodePath.

        Returns:
            A NodePath containing the box geometry.
        """
        from panda3d.core import Geom, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter

        vformat = GeomVertexFormat.getV3n3()
        vdata = GeomVertexData(name + "_vdata", vformat, Geom.UH_static)

        vertex = GeomVertexWriter(vdata, "vertex")
        normal = GeomVertexWriter(vdata, "normal")
        prim = GeomTriangles(Geom.UH_static)

        hw = width / 2.0
        hd = depth / 2.0
        hh = height / 2.0

        corners = [
            (-hw, -hd, -hh),
            (hw, -hd, -hh),
            (hw, hd, -hh),
            (-hw, hd, -hh),
            (-hw, -hd, hh),
            (hw, -hd, hh),
            (hw, hd, hh),
            (-hw, hd, hh),
        ]

        faces = [
            ([0, 1, 2, 3], Vec3(0, 0, -1)),  # -Z (bottom)
            ([4, 7, 6, 5], Vec3(0, 0, 1)),   # +Z (top)
            ([0, 3, 7, 4], Vec3(-1, 0, 0)),   # -X (left)
            ([1, 5, 6, 2], Vec3(1, 0, 0)),    # +X (right)
            ([0, 4, 5, 1], Vec3(0, -1, 0)),   # -Y (front)
            ([2, 6, 7, 3], Vec3(0, 1, 0)),    # +Y (back)
        ]

        for face_corners, n_vec in faces:
            base = vertex.getWriteRow()
            for idx in face_corners:
                cx, cy, cz = corners[idx]
                vertex.addData3f(cx, cy, cz)
                normal.addData3f(n_vec)

            # Two triangles per face (CCW winding).
            prim.addVertices(base + 0, base + 1, base + 2)
            prim.addVertices(base + 0, base + 2, base + 3)

        prim.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(prim)

        gnode = GeomNode(name + "_geom")
        gnode.addGeom(geom)
        np = NodePath(gnode)
        np.set_name(name)
        return np

    def _make_box(self, width: float, depth: float, height: float, name: str = "box") -> NodePath:
        """Alias for ``_make_box_nodepath``."""
        return self._make_box_nodepath(width, depth, height, name)

    def _add_floor_collision(self, floor_node: NodePath) -> None:
        """
        Add collision geometry for the floor.

        Creates an invisible collision plane matching the floor NodePath
        and attaches it to ``collision_root``.
        """
        from panda3d.core import CollisionNode, CollisionPlane, Plane, Point3, BitMask32

        floor_plane = CollisionPlane(Plane(Vec3(0, 0, 1), Point3(0, 0, floor_node.getZ())))
        cnode = CollisionNode("floor_collision")
        cnode.addSolid(floor_plane)
        cnode.setIntoCollideMask(self._get_collision_mask())
        cnode.setTag("geometry", "floor")
        self.collision_root.attachNewNode(cnode)

    def _add_box_collision(self, box_np: NodePath, width: float, depth: float, height: float) -> None:
        """
        Add collision geometry for a box (rectangular prism).

        Parameters
        ----------
        box_np : NodePath
            The visible box NodePath (used for position/size reference).
        width : float
            X-axis extent of the box.
        depth : float
            Y-axis extent of the box.
        height : float
            Z-axis extent of the box.
        """
        from panda3d.core import CollisionNode, CollisionBox, BitMask32

        pos = box_np.getPos()
        # Build collision box centered on the box's position.
        box = CollisionBox(
            (pos.x - width/2, pos.y - depth/2, pos.z),
            (pos.x + width/2, pos.y + depth/2, pos.z + height),
        )
        cnode = CollisionNode("box_collision")
        cnode.addSolid(box)
        cnode.setIntoCollideMask(self._get_collision_mask())
        cnode.setTag("geometry", "wall")
        self.collision_root.attachNewNode(cnode)

    # ------------------------------------------------------------------ #
    #  Per-frame                                                        #
    # ------------------------------------------------------------------ -->

    def update(self, dt: float) -> None:
        """
        World per-frame update.

        Parameters
        ----------
        dt : float
            Delta time in seconds.
        """
        pass

    # ------------------------------------------------------------------ #
    #  Accessors                                                        #
    # ------------------------------------------------------------------ -->

    def get_spawn_point(self) -> Vec3:
        """
        Return the player spawn position for this world.

        Subclasses should override to define specific spawn points.
        """
        return Vec3(0, 0, 10)  # above the floor

    def get_music_path(self) -> Optional[str]:
        """
        Return the path to this world's background music file.

        Returns None by default -- subclasses should override to provide
        a music file path. The file must exist on disk.
        """
        return None

    def destroy(self) -> None:
        """Clean up the world -- remove geometry, lights, fog, particles, music."""
        self._stop_music()

        # Remove point lights
        for light_np in self._point_lights:
            self.world_root.setLightOff(light_np)
            light_np.removeNode()
        self._point_lights.clear()

        # Remove fog
        if self._fog is not None:
            self.world_root.clearFog()
            self.game.render.clearFog()
            self._fog = None

        # Remove geometry
        self.world_root.removeNode()
        self.collision_root.removeNode()
        logger.info("World destroyed.")


__all__ = ["World"]
