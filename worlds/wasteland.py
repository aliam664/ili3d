"""
wasteland.py

Concrete World implementation -- "Post-Apocalyptic Wasteland".

This level provides:
- Ruined terrain with debris and destroyed vehicles.
- Dust storm particle system.
- Dramatic sunset lighting (orange/red directional light).
- Fire and smoke effects.
- Scavenging resources (interactive objects).
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
from direct.particles.ParticleEffect import ParticleEffect
from direct.particles.Particles import Particles

from .world_base import World

logger = logging.getLogger(__name__)


class Wasteland(World):
    """
    The Post-Apocalyptic Wasteland level (World 2).

    Overrides ``_load_geometry``, ``_setup_lighting``, ``_setup_sky``,
    ``_setup_collision``, ``_spawn_entities``, and ``_setup_fog``.
    """

    def __init__(self, game):
        self.level_name: str = "Wasteland Outpost"
        self.level_id: str = "wasteland"
        self.player_spawn: Vec3 = Vec3(0, 0, 15)

        self.wasteland_size: float = 120.0
        self._buildings: list = []
        self._debris: list = []
        self._dust_systems: list = []
        self._fires: list = []

        super().__init__(game)

    def _setup_lighting(self):
        """Sunset lighting: warm orange/red directional light."""
        # Override default lighting.
        ambient = AmbientLight("wasteland_ambient")
        ambient.setColor(Vec4(0.3, 0.25, 0.25, 1.0))
        al_np = self.world_root.attachNewNode(ambient)
        self.world_root.setLight(al_np)

        dlight = DirectionalLight("wasteland_sun")
        dlight.setColor(Vec4(0.9, 0.6, 0.3, 1.0))  # warm sunset
        dlight.setDirection(Vec3(-0.4, -0.6, -0.4).normalized())
        dlight.setShadowCaster(True, 1024, 1024)
        dlight_np = self.world_root.attachNewNode(dlight)
        self.world_root.setLight(dlight_np)

        self.world_root.setShaderAuto()

    def _load_geometry(self):
        """Create ruined terrain, buildings, and debris."""
        # Ground.
        self._create_floor()

        # Ruined buildings.
        self._create_ruins()

        # Debris and vehicles.
        self._create_debris()

        # Scavenging resources.
        self._create_scavenges()

    def _create_floor(self):
        """Create ground with a dusty/brown appearance."""
        from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, CardMaker

        grid_size = 24
        cell_size = 5.0
        half = grid_size * cell_size / 2

        vformat = GeomVertexFormat.getV3t2()
        vdata = GeomVertexData("wasteland_floor", vformat, Geom.UH_static)
        vertex = GeomVertexWriter(vdata, "vertex")
        texcoord = GeomVertexWriter(vdata, "texcoord")

        for i in range(grid_size + 1):
            for j in range(grid_size + 1):
                x = i * cell_size - half
                y = j * cell_size - half
                vertex.addData3(x, y, 0)
                # Vary the texture coordinates slightly for a patchy look.
                texcoord.addData2((i + random.uniform(-0.02, 0.02)) / grid_size,
                                  (j + random.uniform(-0.02, 0.02)) / grid_size)

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
        node = GeomNode("wasteland_floor")
        node.addGeom(geom)
        floor = self.world_root.attachNewNode(node)
        floor.setHpr(0, -90, 0)
        floor.setZ(-1.0)

        # Brown/dusty color.
        floor.setColor(Vec4(0.5, 0.35, 0.2, 1.0))

        # Add collision.
        self._add_floor_collision(floor)

    def _create_ruins(self):
        """Create ruined buildings of varying sizes."""
        # Define building positions and sizes.
        buildings = [
            # (x, y, width, depth, height, color)
            (20, 20, 15, 15, 25, Vec4(0.4, 0.35, 0.3, 1.0)),   # Tall ruined tower
            (40, -15, 20, 12, 8, Vec4(0.35, 0.3, 0.25, 1.0)),  # Low building
            (-25, 30, 10, 10, 12, Vec4(0.3, 0.25, 0.2, 1.0)),  # Small ruin
            (-40, -20, 18, 10, 6, Vec4(0.4, 0.35, 0.3, 1.0)),  # Long structure
            (0, -35, 12, 12, 15, Vec4(0.35, 0.3, 0.25, 1.0)),  # Central ruin
        ]

        for i, (x, y, w, d, h, color) in enumerate(buildings):
            box = self._make_box(w, d, h, f"ruin_{i}")
            box.setPos(x, y, h / 2 - 1.0)
            box.setColor(color)

            # Make some buildings look damaged (missing parts).
            if i % 2 == 0:
                # Add a gap by removing part of the top.
                damage = self._make_box(w * 0.3, d * 0.3, h * 0.4, f"gap_{i}")
                damage.setPos(w/2 - w*0.15, d/2 - d*0.15, h * 0.5)
                # We need to invert: instead of adding a gap box, we subtract.
                # In Panda3D, we can use a boolean or just not add the top part.
                # Simpler: just make a hollow building by not capping the top.

            box.reparentTo(self.world_root)
            self._buildings.append(box)
            self._add_box_collision(box, w, d, h)

    def _create_debris(self):
        """Create scattered debris and destroyed vehicles."""
        for i in range(20):
            x = random.uniform(-50, 50)
            y = random.uniform(-50, 50)
            w = random.uniform(2, 6)
            d = random.uniform(2, 6)
            h = random.uniform(2, 8)

            debris = self._make_box(w, d, h, f"debris_{i}")
            debris.setPos(x, y, h / 2 - 1.0)
            debris.setColor(Vec4(0.35, 0.2, 0.15, 1.0))
            debris.reparentTo(self.world_root)
            self._debris.append(debris)
            self._add_box_collision(debris, w, d, h)

    def _create_scavenges(self):
        """Create scavenging resource markers (glowing boxes)."""
        for i in range(8):
            x = random.uniform(-55, 55)
            y = random.uniform(-55, 55)

            # Resource crate.
            crate = self._make_box(2, 2, 2, f"scavenge_{i}")
            crate.setPos(x, y, 0)
            crate.setColor(Vec4(0.5, 0.8, 0.3, 0.7))
            crate.setTransparency(True)

            # Pulsing glow.
            light = self._add_point_light(f"scavenge_light_{i}",
                                          Vec4(0.5, 0.8, 0.3, 1.0),
                                          Vec3(x, y, 0))

            crate.reparentTo(self.world_root)
            self._entities.append(("scavenge", crate, (x, y, 0)))

    def _create_dust_storm(self):
        """Create a dust storm particle system."""
        try:
            self._dust_systems.append(self._create_dust_particles(Vec3(0, 0, 5)))
        except Exception as e:
            logger.warning("Could not create dust particles: %s", e)

    def _create_dust_particles(self, pos: Vec3) -> ParticleEffect:
        """Create a dust particle effect at the given position."""
        from panda3d.physics import ParticleSystem

        ps = ParticleEffect("dust_effect")
        ps.start(parent=self.world_root, renderParent=self.world_root)

        particles = Particles("dust")
        particles.factory.set_lifespan(3.0)
        particles.factory.set_mass(0.2)
        particles.factory.set_terminal_velocity(5.0)

        renderer = particles.renderer
        renderer.set_alpha_mode(ParticleSystem.PRALPHOut)
        renderer.set_color(Vec4(0.6, 0.4, 0.2, 0.5))
        renderer.set_scale(0.5)

        emitter = particles.emitter
        emitter.set_emission_type(ParticleSystem.ET_NORMAL)
        emitter.set_amplitude(3.0)
        emitter.set_amplitude_spread(1.0)
        emitter.set_offset_force(Vec3(0, 0, 2.0))

        particles.set_birth_rate(0.02)
        particles.set_pool_size(50)

        ps.addParticles(particles)
        ps.setPos(pos)
        ps.reparentTo(self.world_root)
        return ps

    def _setup_fog(self):
        """Configure dust-colored fog."""
        self._configure_fog(
            color=Vec4(0.5, 0.35, 0.2, 1.0),
            mode="exponential",
            density=0.002,
        )

    def _setup_collision(self):
        """Set up collision geometry for the wasteland."""
        super()._setup_collision()

        # Add wall collisions for buildings.
        for building in self._buildings:
            self._add_box_collision(building, 1, 1, 1)  # simplified

    def _spawn_entities(self):
        """Spawn enemies and resources in the wasteland."""
        from config.constants import Constants

        # Spawn points scattered across the wasteland.
        spawn_points = [
            Vec3(30, 30, 0),
            Vec3(-30, -25, 0),
            Vec3(0, -45, 0),
            Vec3(45, -10, 0),
            Vec3(-45, 25, 0),
            Vec3(15, -35, 0),
            Vec3(-20, 40, 0),
        ]

        for sp in spawn_points:
            self._entities.append(("spawn_point", None, (sp.x, sp.y, sp.z)))

    def get_spawn_point(self) -> Vec3:
        return self.player_spawn

    def get_music_path(self) -> str:
        return ""  # No music file; will use procedural audio


