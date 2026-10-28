"""
arctic.py

Concrete World implementation -- "Frozen Arctic Research Station".

This level provides:
- Snow-covered terrain with icy surfaces.
- A research station with glowing windows.
- Ice formations and frozen lakes.
- Aurora borealis sky effect.
- Slippery surface mechanics placeholder.
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


class Arctic(World):
    """
    The Frozen Arctic Research Station level (World 5).
    """

    def __init__(self, game):
        self.level_name: str = "Frostbite Outpost"
        self.level_id: str = "arctic"
        self.player_spawn: Vec3 = Vec3(5, -5, 20)

        self._ice_formations: list = []
        self._station_buildings: list = []
        self._aurora_light: NodePath = None

        super().__init__(game)

    def _setup_lighting(self):
        """Arctic lighting: cold blue ambient with aurora effect."""
        ambient = AmbientLight("arctic_ambient")
        ambient.setColor(Vec4(0.3, 0.35, 0.5, 1.0))
        al_np = self.world_root.attachNewNode(ambient)
        self.world_root.setLight(al_np)

        dlight = DirectionalLight("arctic_sun")
        dlight.setColor(Vec4(0.8, 0.85, 1.0, 1.0))  # cool, bright
        dlight.setDirection(Vec3(-0.5, -0.5, -0.5).normalized())
        dlight.setShadowCaster(True, 1024, 1024)
        dlight_np = self.world_root.attachNewNode(dlight)
        self.world_root.setLight(dlight_np)

        # Aurora lights (green/purple point lights).
        aurora_green = self._add_point_light("aurora_green", Vec4(0.2, 0.8, 0.2, 1.0), Vec3(0, 0, 40))
        aurora_purple = self._add_point_light("aurora_purple", Vec4(0.5, 0.2, 0.7, 1.0), Vec3(0, 0, 50))
        self._aurora_light = aurora_green

        self.world_root.setShaderAuto()

    def _load_geometry(self):
        """Create snow terrain, ice formations, and research station."""
        self._create_floor()
        self._create_ice_formations()
        self._create_station()

    def _create_floor(self):
        """Create snow-covered terrain."""
        from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter

        grid_size = 22
        cell_size = 5.0
        half = grid_size * cell_size / 2

        vformat = GeomVertexFormat.getV3n3()
        vdata = GeomVertexData("arctic_floor", vformat, Geom.UH_static)
        vertex = GeomVertexWriter(vdata, "vertex")
        normal = GeomVertexWriter(vdata, "normal")

        for i in range(grid_size + 1):
            for j in range(grid_size + 1):
                x = i * cell_size - half
                y = j * cell_size - half
                # Add snow drifts.
                z = 0.2 * math.sin(x * 0.05) * math.cos(y * 0.05)
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
        node = GeomNode("arctic_floor")
        node.addGeom(geom)
        floor = self.world_root.attachNewNode(node)
        floor.setHpr(0, -90, 0)
        floor.setZ(0)
        floor.setColor(Vec4(0.7, 0.8, 0.95, 1.0))  # icy blue-white

        self._add_floor_collision(floor)

    def _create_ice_formations(self):
        """Create tall ice crystal formations."""
        for i in range(15):
            x = -50 + i * 7
            y = (i % 3) * 15 - 7
            height = 5 + (i % 4) * 3

            ice = self._make_box(1, 1, height, f"ice_{i}")
            ice.setPos(x, y, height / 2)
            ice.setColor(Vec4(0.6, 0.8, 1.0, 0.5))
            ice.setTransparency(True)
            ice.reparentTo(self.world_root)
            self._ice_formations.append(ice)

    def _create_station(self):
        """Create the Arctic research station buildings."""
        buildings = [
            # (x, y, w, d, h, color)
            (-5, 0, 15, 15, 20, Vec4(0.8, 0.8, 0.85, 1.0)),  # Main hub
            (-15, -15, 8, 8, 10, Vec4(0.7, 0.7, 0.75, 1.0)),  # Lab wing
            (10, 10, 8, 10, 12, Vec4(0.75, 0.75, 0.8, 1.0)),  # Living quarters
        ]

        for i, (x, y, w, d, h, color) in enumerate(buildings):
            building = self._make_box(w, d, h, f"station_{i}")
            building.setPos(x, y, h / 2)
            building.setColor(color)
            building.reparentTo(self.world_root)
            self._station_buildings.append(building)

            self._add_box_collision(building, w, d, h)

            # Warm yellow glow from windows.
            if i == 0:
                for wx in range(-5, 6, 3):
                    for wy in range(-5, 6, 4):
                        self._add_point_light(
                            f"window_light_{i}_{wx}_{wy}",
                            Vec4(1.0, 0.9, 0.7, 1.0),
                            Vec3(x + wx, y + wy, h - 1),
                        )

    def _setup_fog(self):
        """Configure arctic fog (cold, misty)."""
        self._configure_fog(
            color=Vec4(0.6, 0.7, 0.9, 0.6),
            mode="exponential",
            density=0.0015,
        )

    def _setup_collision(self):
        """Set up collision geometry for the arctic."""
        super()._setup_collision()

        for building in self._station_buildings:
            self._add_box_collision(building, 1, 1, 1)

        for ice in self._ice_formations:
            self._add_box_collision(ice, 1, 1, 1)

    def _spawn_entities(self):
        """Spawn enemies around the research station."""
        spawn_points = [
            Vec3(-15, -13, 1),
            Vec3(10, 8, 1),
            Vec3(0, 7, 1),
            Vec3(-10, -5, 1),
            Vec3(12, 12, 1),
        ]

        for sp in spawn_points:
            self._entities.append(("spawn_point", None, (sp.x, sp.y, sp.z)))

    def get_spawn_point(self) -> Vec3:
        return self.player_spawn

    def get_music_path(self) -> str:
        return ""
