"""
space_station.py

Concrete World implementation -- "Derelict Space Station".

This level provides:
- Zero-gravity sections with low-friction physics.
- Hanging wires and floating debris.
- Emergency lighting (red/beam sweep effect).
- Glass windows overlooking space.
- Atmospheric processor humming sound placeholder.
"""

from __future__ import annotations

import logging
import math

from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Fog,
    NodePath,
    PointLight,
    Vec3,
    Vec4,
)

from .world_base import World

logger = logging.getLogger(__name__)


class SpaceStation(World):
    """
    The Derelict Space Station level (World 6).
    """

    def __init__(self, game):
        self.level_name: str = "Kepler Station"
        self.level_id: str = "space_station"
        self.player_spawn: Vec3 = Vec3(0, 0, 40)

        self._platforms: list = []
        self._debris: list = []
        self._emergency_lights: list = []

        super().__init__(game)

    def _setup_lighting(self):
        """Space station lighting: dim ambient with emergency red sweep."""
        ambient = AmbientLight("space_ambient")
        ambient.setColor(Vec4(0.1, 0.1, 0.18, 1.0))
        al_np = self.world_root.attachNewNode(ambient)
        self.world_root.setLight(al_np)

        # Main directional light (simulates distant sun through windows).
        dlight = DirectionalLight("space_sun")
        dlight.setColor(Vec4(0.6, 0.6, 0.7, 1.0))
        dlight.setDirection(Vec3(-0.5, -0.5, -0.3).normalized())
        dlight_np = self.world_root.attachNewNode(dlight)
        self.world_root.setLight(dlight_np)

        self.world_root.setShaderAuto()

    def _load_geometry(self):
        """Create station platforms, debris, and windows."""
        self._create_floor()
        self._create_platforms()
        self._create_debris()
        self._create_windows()

    def _create_floor(self):
        """Create central platform floor for the station interior."""
        from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter

        grid_size = 12
        cell_size = 8.0
        half = grid_size * cell_size / 2

        vformat = GeomVertexFormat.getV3n3()
        vdata = GeomVertexData("space_floor", vformat, Geom.UH_static)
        vertex = GeomVertexWriter(vdata, "vertex")
        normal = GeomVertexWriter(vdata, "normal")

        for i in range(grid_size + 1):
            for j in range(grid_size + 1):
                x = i * cell_size - half
                y = j * cell_size - half
                vertex.addData3(x, y, 0)
                normal.addData3(0, 0, 1)

        prim = GeomTriangles(Geom.UH_static)
        for i in range(grid_size):
            for j in range(grid_size):
                a = i * (grid_size + 1) + j
                b = a + 1
                c = a + (grid_size + 1)
                d = c + 1
                prim.addVertices(a, b, c)
                prim.addVertices(c, b, d)

        geom = Geom(vdata)
        geom.addPrimitive(prim)
        node = GeomNode("space_floor")
        node.addGeom(geom)
        floor = self.world_root.attachNewNode(node)
        floor.setHpr(0, -90, 0)
        floor.setZ(30)
        floor.setColor(Vec4(0.3, 0.3, 0.4, 1.0))

        self._add_floor_collision(floor)

    def _create_platforms(self):
        """Create elevated platforms connected by walkways."""
        platforms = [
            # (x, y, z, width, depth, height, color)
            (0, 0, 40, 20, 20, 5, Vec4(0.5, 0.5, 0.6, 1.0)),    # Central hub
            (30, 10, 45, 10, 8, 3, Vec4(0.45, 0.45, 0.55, 1.0)),  # East platform
            (-30, -10, 45, 10, 8, 3, Vec4(0.45, 0.45, 0.55, 1.0)),  # West platform
            (10, 35, 43, 12, 6, 2, Vec4(0.45, 0.45, 0.55, 1.0)),   # North walkway
            (-10, -35, 43, 12, 6, 2, Vec4(0.45, 0.45, 0.55, 1.0)),  # South walkway
        ]

        for i, (x, y, z, w, d, h, color) in enumerate(platforms):
            platform = self._make_box(w, d, h, f"platform_{i}")
            platform.setPos(x, y, z)
            platform.setColor(color)
            platform.reparentTo(self.world_root)
            self._platforms.append(platform)

            self._add_box_collision(platform, w, d, h)

    def _create_debris(self):
        """Create floating debris in zero-gravity areas."""
        import random
        for i in range(25):
            x = random.uniform(-55, 55)
            y = random.uniform(-55, 55)
            z = random.uniform(33, 60)
            w = random.uniform(1, 4)
            d = random.uniform(1, 4)
            h = random.uniform(1, 4)

            debris = self._make_box(w, d, h, f"debris_{i}")
            debris.setPos(x, y, z)
            debris.setColor(Vec4(0.4, 0.4, 0.5, 0.8))
            debris.setTransparency(True)
            debris.reparentTo(self.world_root)
            self._debris.append(debris)

    def _create_windows(self):
        """Create transparent windows showing space."""
        windows = [
            Vec3(0, 45, 45),
            Vec3(0, -45, 45),
            Vec3(45, 0, 45),
            Vec3(-45, 0, 45),
        ]

        for i, pos in enumerate(windows):
            window = self._make_box(10, 0.5, 6, f"window_{i}")
            window.setPos(pos)
            window.setColor(Vec4(0.5, 0.8, 1.0, 0.3))
            window.setTransparency(True)
            window.reparentTo(self.world_root)

            # Light bleeding through window.
            self._add_point_light(
                f"window_light_{i}",
                Vec4(0.5, 0.8, 1.0, 0.5),
                pos,
            )

    def _setup_fog(self):
        """Configure space fog (thin, atmospheric)."""
        self._configure_fog(
            color=Vec4(0.05, 0.05, 0.15, 0.3),
            mode="exponential",
            density=0.0005,
        )

    def _setup_collision(self):
        """Set up collision geometry for the space station."""
        super()._setup_collision()

        for platform in self._platforms:
            self._add_box_collision(platform, 1, 1, 1)

    def _spawn_entities(self):
        """Spawn enemies on the platforms."""
        spawn_points = [
            Vec3(0, 5, 43),
            Vec3(28, 8, 47),
            Vec3(-28, -8, 47),
            Vec3(8, 33, 45),
            Vec3(-8, -33, 45),
        ]

        for sp in spawn_points:
            self._entities.append(("spawn_point", None, (sp.x, sp.y, sp.z)))

    def get_spawn_point(self) -> Vec3:
        return self.player_spawn

    def get_music_path(self) -> str:
        return ""
