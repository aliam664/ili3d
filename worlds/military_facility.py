"""
military_facility.py

Concrete World implementation -- "Secret Military Facility".

This level provides:
- Underground corridors and sterile laboratories.
- Emergency red lighting with flickering fluorescent lights.
- Security checkpoints and containment zones.
- Sparks and alarm particle effects.
- Security hacking terminals (interactive objects).
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


class MilitaryFacility(World):
    """
    The Secret Military Facility level (World 3).

    Features sterile corridors, emergency lighting, and high-security zones.
    """

    def __init__(self, game):
        self.level_name: str = "Blackgate Facility"
        self.level_id: str = "military_facility"
        self.player_spawn: Vec3 = Vec3(2, -2, 2)

        self._rooms: list = []
        self._corridors: list = []
        self._flicker_lights: list = []
        self._terminals: list = []

        super().__init__(game)

    def _setup_lighting(self):
        """Emergency red lighting with ambient fill."""
        ambient = AmbientLight("facility_ambient")
        ambient.setColor(Vec4(0.15, 0.05, 0.05, 1.0))
        al_np = self.world_root.attachNewNode(ambient)
        self.world_root.setLight(al_np)

        # Flickering red emergency light.
        dlight = DirectionalLight("facility_emergency")
        dlight.setColor(Vec4(0.6, 0.1, 0.1, 1.0))
        dlight.setDirection(Vec3(-0.3, -0.5, -0.5).normalized())
        dlight_np = self.world_root.attachNewNode(dlight)
        self.world_root.setLight(dlight_np)

        self.world_root.setShaderAuto()

    def _load_geometry(self):
        """Create underground facility layout."""
        self._create_floor()
        self._create_walls()
        self._create_rooms()
        self._create_security_barriers()
        self._create_terminals()

    def _create_floor(self):
        """Create the facility floor with metal grid pattern."""
        from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter

        grid_size = 16
        cell_size = 5.0
        half = grid_size * cell_size / 2

        vformat = GeomVertexFormat.getV3n3()
        vdata = GeomVertexData("facility_floor", vformat, Geom.UH_static)
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
        node = GeomNode("facility_floor")
        node.addGeom(geom)
        floor = self.world_root.attachNewNode(node)
        floor.setHpr(0, -90, 0)
        floor.setZ(0)
        floor.setColor(Vec4(0.4, 0.4, 0.45, 1.0))

        self._add_floor_collision(floor)

    def _create_walls(self):
        """Create corridor walls."""
        wall_positions = [
            # (x, y, width, depth, height)
            (0, -45, 90, 2, 6),   # Front wall
            (0, 45, 90, 2, 6),    # Back wall
            (-45, 0, 2, 90, 6),   # Left wall
            (45, 0, 2, 90, 6),    # Right wall
        ]

        for i, (x, y, w, d, h) in enumerate(wall_positions):
            wall = self._make_box(w, d, h, f"wall_{i}")
            wall.setPos(x, y, h / 2)
            wall.setColor(Vec4(0.3, 0.3, 0.35, 1.0))
            wall.reparentTo(self.world_root)
            self._corridors.append(wall)
            self._add_box_collision(wall, w, d, h)

    def _create_rooms(self):
        """Create interior rooms: lab, armory, control center."""
        rooms = [
            # (x, y, width, depth, height, color, name)
            (-35, -30, 20, 20, 6, Vec4(0.35, 0.35, 0.4, 1.0), "lab"),
            (20, 30, 20, 15, 6, Vec4(0.35, 0.35, 0.4, 1.0), "armory"),
            (-20, 25, 25, 12, 6, Vec4(0.35, 0.35, 0.4, 1.0), "control"),
        ]

        for x, y, w, d, h, color, name in rooms:
            room = self._make_box(w, d, h, f"room_{name}")
            room.setPos(x, y, h / 2)
            room.setColor(color)
            room.reparentTo(self.world_root)
            self._rooms.append(room)
            self._add_box_collision(room, w, d, h)

            # Interior lighting.
            self._add_point_light(
                f"room_light_{name}",
                Vec4(0.3, 0.1, 0.1, 1.0),
                Vec3(x, y, h),
            )

    def _create_security_barriers(self):
        """Create security checkpoint barriers."""
        barriers = [
            Vec3(0, 5, 2),
            Vec3(15, 10, 2),
            Vec3(-15, -10, 2),
        ]

        for i, pos in enumerate(barriers):
            barrier = self._make_box(8, 0.5, 2, f"barrier_{i}")
            barrier.setPos(pos)
            barrier.setColor(Vec4(0.8, 0.1, 0.1, 0.6))
            barrier.setTransparency(True)
            barrier.reparentTo(self.world_root)

    def _create_terminals(self):
        """Create hacking terminals."""
        terminals = [
            Vec3(-30, -25, 1),
            Vec3(25, 35, 1),
            Vec3(-15, 20, 1),
        ]

        for i, pos in enumerate(terminals):
            terminal = self._make_box(0.5, 1.5, 1.0, f"terminal_{i}")
            terminal.setPos(pos)
            terminal.setColor(Vec4(0.1, 0.3, 0.8, 1.0))
            terminal.setLightOff()
            terminal.reparentTo(self.world_root)
            self._terminals.append(terminal)

            # Blinking light on terminal.
            light = self._add_point_light(
                f"terminal_light_{i}",
                Vec4(0.1, 0.3, 0.8, 1.0),
                Vec3(pos.x, pos.y, pos.z + 1),
            )
            self._flicker_lights.append(light)

    def _setup_fog(self):
        """Configure facility fog (light, sterile white)."""
        self._configure_fog(
            color=Vec4(0.6, 0.6, 0.7, 1.0),
            mode="exponential",
            density=0.001,
        )

    def _setup_collision(self):
        """Set up collision geometry for the facility."""
        super()._setup_collision()

        # Add corridor walls collision.
        for corridor in self._corridors:
            self._add_box_collision(corridor, 1, 1, 1)

    def _spawn_entities(self):
        """Spawn enemies inside the facility."""
        spawn_points = [
            Vec3(-30, -28, 1),
            Vec3(25, 28, 1),
            Vec3(0, 12, 1),
            Vec3(-15, 22, 1),
            Vec3(20, 15, 1),
        ]

        for sp in spawn_points:
            self._entities.append(("spawn_point", None, (sp.x, sp.y, sp.z)))

    def get_spawn_point(self) -> Vec3:
        return self.player_spawn

    def get_music_path(self) -> str:
        return ""
