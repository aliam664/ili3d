"""
jungle.py

Concrete World implementation -- "Overgrown Jungle Ruins".

This level provides:
- Dense jungle canopy with hanging vines.
- Bioluminescent plants and glowing fungi.
- Humid atmospheric fog.
- Ancient stone ruins overtaken by vegetation.
- Ambient wildlife sounds placeholder.
"""

from __future__ import annotations

import logging
import math
import random

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


class Jungle(World):
    """
    The Overgrown Jungle Ruins level (World 4).
    """

    def __init__(self, game):
        self.level_name: str = "Emerald Canopy"
        self.level_id: str = "jungle"
        self.player_spawn: Vec3 = Vec3(0, 0, 5)

        self._trees: list = []
        self._ruins: list = []
        self._glowing_foliage: list = []
        self._vine_lights: list = []

        super().__init__(game)

    def _setup_lighting(self):
        """Jungle lighting: dim ambient with shafts of sunlight."""
        ambient = AmbientLight("jungle_ambient")
        ambient.setColor(Vec4(0.25, 0.35, 0.25, 1.0))
        al_np = self.world_root.attachNewNode(ambient)
        self.world_root.setLight(al_np)

        dlight = DirectionalLight("jungle_sun")
        dlight.setColor(Vec4(0.7, 0.8, 0.5, 1.0))  # dappled sunlight
        dlight.setDirection(Vec3(-0.3, -0.5, -0.7).normalized())
        dlight.setShadowCaster(True, 1024, 1024)
        dlight_np = self.world_root.attachNewNode(dlight)
        self.world_root.setLight(dlight_np)

        self.world_root.setShaderAuto()

    def _load_geometry(self):
        """Create jungle floor, trees, ruins, and vines."""
        self._create_floor()
        self._create_trees()
        self._create_ruins()
        self._create_glowing_foliage()
        self._create_vines()

    def _create_floor(self):
        """Create uneven jungle terrain with a green mossy appearance."""
        from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter

        grid_size = 20
        cell_size = 6.0
        half = grid_size * cell_size / 2

        vformat = GeomVertexFormat.getV3n3()
        vdata = GeomVertexData("jungle_floor", vformat, Geom.UH_static)
        vertex = GeomVertexWriter(vdata, "vertex")
        normal = GeomVertexWriter(vdata, "normal")

        for i in range(grid_size + 1):
            for j in range(grid_size + 1):
                x = i * cell_size - half
                y = j * cell_size - half
                # Add procedural bumps for uneven terrain.
                z = 0.1 * math.sin(x * 0.1) + 0.1 * math.cos(y * 0.1)
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
        node = GeomNode("jungle_floor")
        node.addGeom(geom)
        floor = self.world_root.attachNewNode(node)
        floor.setHpr(0, -90, 0)
        floor.setZ(0)
        floor.setColor(Vec4(0.15, 0.45, 0.15, 1.0))

        self._add_floor_collision(floor)

    def _create_trees(self):
        """Create scattered tree trunks."""
        tree_positions = [
            (15, 15), (-20, 25), (30, -10), (-10, -30),
            (40, 5), (-35, -15), (5, 40), (-25, 35),
            (35, 30), (-40, 20), (20, -35), (-15, -40),
        ]

        for i, (x, y) in enumerate(tree_positions):
            trunk = self._make_box(2, 2, 12, f"tree_{i}")
            trunk.setPos(x, y, 6.0)
            trunk.setColor(Vec4(0.25, 0.15, 0.05, 1.0))
            trunk.reparentTo(self.world_root)
            self._trees.append(trunk)

            # Tree top (foliage).
            top = self._make_box(6, 6, 8, f"foliage_{i}")
            top.setPos(x, y, 13.0)
            top.setColor(Vec4(0.1, 0.5, 0.1, 1.0))
            top.reparentTo(self.world_root)
            self._trees.append(top)

            # Add collision for tree trunk.
            self._add_box_collision(trunk, 2, 2, 12)

    def _create_ruins(self):
        """Create ancient stone ruins."""
        ruins = [
            # (x, y, w, d, h)
            (0, 0, 10, 10, 8),
            (-25, 10, 8, 6, 6),
            (30, -20, 12, 8, 10),
            (10, 35, 7, 7, 5),
        ]

        for i, (x, y, w, d, h) in enumerate(ruins):
            ruin = self._make_box(w, d, h, f"ruin_{i}")
            ruin.setPos(x, y, h / 2)
            ruin.setColor(Vec4(0.4, 0.4, 0.4, 0.85))
            ruin.setTransparency(True)
            ruin.reparentTo(self.world_root)
            self._ruins.append(ruin)

            self._add_box_collision(ruin, w, d, h)

    def _create_glowing_foliage(self):
        """Create bioluminescent plants."""
        for i in range(12):
            x = random.uniform(-45, 45)
            y = random.uniform(-45, 45)

            plant = self._make_box(1, 1, 2, f"glow_plant_{i}")
            plant.setPos(x, y, 1.0)
            plant.setColor(Vec4(0.2, 0.6, 0.2, 0.6))
            plant.setTransparency(True)
            plant.reparentTo(self.world_root)
            self._glowing_foliage.append(plant)

            # Pulsing glow light.
            light = self._add_point_light(
                f"glow_light_{i}",
                Vec4(0.2, 0.6, 0.2, 1.0),
                Vec3(x, y, 2.0),
            )
            self._vine_lights.append(light)

    def _create_vines(self):
        """Create hanging vines between trees and ruins."""
        for i in range(8):
            x = random.uniform(-40, 40)
            y = random.uniform(-40, 40)
            height = random.uniform(3, 6)

            vine = self._make_box(0.3, 0.3, height, f"vine_{i}")
            vine.setPos(x, y, height / 2)
            vine.setColor(Vec4(0.1, 0.5, 0.1, 0.7))
            vine.setTransparency(True)
            vine.reparentTo(self.world_root)
            self._trees.append(vine)

    def _setup_fog(self):
        """Configure jungle fog (greenish, humid)."""
        self._configure_fog(
            color=Vec4(0.2, 0.35, 0.2, 0.8),
            mode="exponential",
            density=0.003,
        )

    def _setup_collision(self):
        """Set up collision geometry for the jungle."""
        super()._setup_collision()

        for tree in self._trees:
            self._add_box_collision(tree, 2, 2, 12)

        for ruin in self._ruins:
            self._add_box_collision(ruin, 1, 1, 1)

    def _spawn_entities(self):
        """Spawn enemies among the ruins and trees."""
        spawn_points = [
            Vec3(5, 5, 1),
            Vec3(-25, 5, 1),
            Vec3(30, -20, 1),
            Vec3(10, 35, 1),
            Vec3(-15, 15, 1),
            Vec3(25, -10, 1),
        ]

        for sp in spawn_points:
            self._entities.append(("spawn_point", None, (sp.x, sp.y, sp.z)))

    def get_spawn_point(self) -> Vec3:
        return self.player_spawn

    def get_music_path(self) -> str:
        return ""
