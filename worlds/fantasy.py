"""
fantasy.py

Concrete World implementation -- "Ancient Fantasy Realm".

This level provides:
- Floating islands with waterfalls.
- Magical crystal formations.
- Glowing runes on stone pillars.
- Enchanted forest clearing.
- Dynamic lighting shifts between day and night cycles.
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


class Fantasy(World):
    """
    The Ancient Fantasy Realm level (World 7).
    """

    def __init__(self, game):
        self.level_name: str = "Aethermoor"
        self.level_id: str = "fantasy"
        self.player_spawn: Vec3 = Vec3(0, 0, 30)

        self._islands: list = []
        self._crystals: list = []
        self._runes: list = []

        super().__init__(game)

    def _setup_lighting(self):
        """Fantasy lighting: magical glow with multiple colored lights."""
        ambient = AmbientLight("fantasy_ambient")
        ambient.setColor(Vec4(0.3, 0.3, 0.4, 1.0))
        al_np = self.world_root.attachNewNode(ambient)
        self.world_root.setLight(al_np)

        # Main directional light.
        dlight = DirectionalLight("fantasy_sun")
        dlight.setColor(Vec4(0.7, 0.7, 0.8, 1.0))
        dlight.setDirection(Vec3(-0.4, -0.4, -0.5).normalized())
        dlight.setShadowCaster(True, 1024, 1024)
        dlight_np = self.world_root.attachNewNode(dlight)
        self.world_root.setLight(dlight_np)

        self.world_root.setShaderAuto()

    def _load_geometry(self):
        """Create floating islands, crystals, and magical elements."""
        self._create_floor()
        self._create_islands()
        self._create_waterfalls()
        self._create_crystals()
        self._create_runes()

    def _create_floor(self):
        """Create the base platform / ground."""
        from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter

        grid_size = 14
        cell_size = 8.0
        half = grid_size * cell_size / 2

        vformat = GeomVertexFormat.getV3n3()
        vdata = GeomVertexData("fantasy_floor", vformat, Geom.UH_static)
        vertex = GeomVertexWriter(vdata, "vertex")
        normal = GeomVertexWriter(vdata, "normal")

        for i in range(grid_size + 1):
            for j in range(grid_size + 1):
                x = i * cell_size - half
                y = j * cell_size - half
                # Slight undulation for magical terrain.
                z = 0.15 * math.sin(i * 0.3) + 0.15 * math.cos(j * 0.3)
                vertex.addData3(x, y, z)
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
        node = GeomNode("fantasy_floor")
        node.addGeom(geom)
        floor = self.world_root.attachNewNode(node)
        floor.setHpr(0, -90, 0)
        floor.setZ(0)
        floor.setColor(Vec4(0.25, 0.5, 0.25, 1.0))

        self._add_floor_collision(floor)

    def _create_islands(self):
        """Create floating islands at various heights."""
        islands = [
            # (x, y, z, radius_x, radius_y, height)
            (0, 0, 25, 15, 15, 5),   # Central island
            (40, 20, 35, 10, 10, 4),  # East island
            (-40, -15, 30, 12, 12, 4),  # West island
            (20, -35, 28, 8, 8, 3),   # South island
            (-25, 30, 40, 10, 10, 4), # North island
        ]

        for i, (x, y, z, rx, ry, h) in enumerate(islands):
            island = self._make_box(rx * 2, ry * 2, h, f"island_{i}")
            island.setPos(x, y, z)
            island.setColor(Vec4(0.3, 0.6, 0.3, 0.9))
            island.reparentTo(self.world_root)
            self._islands.append(island)

            self._add_box_collision(island, rx * 2, ry * 2, h)

    def _create_waterfalls(self):
        """Create simple waterfall effects between islands."""
        for i in range(3):
            x = -20 + i * 20
            water = self._make_box(2, 2, 15, f"waterfall_{i}")
            water.setPos(x, 10, 25)
            water.setColor(Vec4(0.4, 0.6, 1.0, 0.5))
            water.setTransparency(True)
            water.reparentTo(self.world_root)
            self._islands.append(water)

    def _create_crystals(self):
        """Create glowing magical crystals."""
        import random
        colors = [
            Vec4(1.0, 0.3, 0.3, 1.0),   # Red
            Vec4(0.3, 1.0, 0.3, 1.0),   # Green
            Vec4(0.3, 0.3, 1.0, 1.0),   # Blue
            Vec4(1.0, 1.0, 0.3, 1.0),   # Yellow
            Vec4(0.8, 0.3, 1.0, 1.0),   # Purple
        ]

        for i in range(15):
            x = random.uniform(-50, 50)
            y = random.uniform(-50, 50)
            z = random.uniform(5, 45)
            h = random.uniform(1, 4)

            crystal = self._make_box(0.5, 0.5, h, f"crystal_{i}")
            crystal.setPos(x, y, z)
            color = random.choice(colors)
            crystal.setColor(color)
            crystal.reparentTo(self.world_root)
            self._crystals.append(crystal)

            # Matching glow light.
            self._add_point_light(
                f"crystal_light_{i}",
                color,
                Vec3(x, y, z + h / 2),
            )

    def _create_runes(self):
        """Create glowing runes on stone pillars."""
        for i in range(8):
            x = -30 + i * 8
            y = -10

            pillar = self._make_box(1, 1, 8, f"rune_pillar_{i}")
            pillar.setPos(x, y, 4)
            pillar.setColor(Vec4(0.3, 0.3, 0.35, 1.0))
            pillar.reparentTo(self.world_root)
            self._runes.append(pillar)

            # Rune glow.
            self._add_point_light(
                f"rune_light_{i}",
                Vec4(0.5, 0.5, 1.0, 1.0),
                Vec3(x, y, 8),
            )

    def _setup_fog(self):
        """Configure fantasy fog (magical, misty)."""
        self._configure_fog(
            color=Vec4(0.3, 0.4, 0.5, 0.4),
            mode="exponential",
            density=0.002,
        )

    def _setup_collision(self):
        """Set up collision geometry for the fantasy realm."""
        super()._setup_collision()

        for island in self._islands:
            self._add_box_collision(island, 1, 1, 1)

        for crystal in self._crystals:
            self._add_box_collision(crystal, 0.5, 0.5, 3)

    def _spawn_entities(self):
        """Spawn enemies on the floating islands."""
        spawn_points = [
            Vec3(5, 5, 28),
            Vec3(38, 18, 38),
            Vec3(-38, -13, 33),
            Vec3(18, -33, 31),
            Vec3(-23, 28, 43),
        ]

        for sp in spawn_points:
            self._entities.append(("spawn_point", None, (sp.x, sp.y, sp.z)))

    def get_spawn_point(self) -> Vec3:
        return self.player_spawn

    def get_music_path(self) -> str:
        return ""
