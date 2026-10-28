"""
cyberpunk_city.py

Concrete World implementation -- "Cyberpunk City".

This level provides:
- A large urban environment with buildings of varying heights.
- Ambient cyberpunk lighting (purple / blue / neon tones).
- Neon signs with emissive materials and point lights.
- Volumetric-like fog.
- Rain particle effect.
- Reflective / glossy wet ground surface.
- A defined player spawn point.

The geometry is generated procedurally for the demo; in a production
build, this would load a pre-built egg / bam level mesh.
"""

from __future__ import annotations

import logging
import math

from panda3d.core import (
    AmbientLight,
    CollisionBox,
    CollisionNode,
    DirectionalLight,
    Fog,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    Point3,
    PointLight,
    TransparencyAttrib,
    Vec3,
    Vec4,
    CardMaker,
)
from panda3d.physics import ParticleSystem
from direct.particles.ParticleEffect import ParticleEffect
from direct.particles.Particles import Particles
from direct.showbase.ShowBase import ShowBase

from .world_base import World

logger = logging.getLogger(__name__)


class CyberpunkCity(World):
    """
    The first level: a cyberpunk-themed city block.

    Overrides ``_load_geometry``, ``_setup_lighting``, ``_setup_sky``,
    ``_setup_collision``, ``_spawn_entities``, and ``_setup_fog`` to add
    the level-specific cyberpunk content.
    """

    def __init__(self, game: "ShowBase") -> None:
        #: Level metadata.
        self.level_name: str = "Cyberpunk City"
        self.level_id: str = "cyberpunk_city"
        self.player_spawn: Vec3 = Vec3(0, 5, 20)

        # Cyberpunk-specific settings.
        #: Size of the city ground plane (square, in world units).
        self.city_size: float = 100.0
        #: Number of building plots in each dimension.
        self.grid_divisions: int = 10
        #: Whether to show the rain effect.
        self.enable_rain: bool = True
        #: Number of rain particles.
        self.rain_particle_count: int = 2000

        # Tracked resources.
        self._buildings: list[NodePath] = []
        self._neon_signs: list[NodePath] = []
        self._neon_lights: list[NodePath] = []
        self._rain_effect: ParticleEffect | None = None

        super().__init__(game)

    # ------------------------------------------------------------------ #
    #  Lighting override                                                #
    # ------------------------------------------------------------------ -->

    def _setup_lighting(self) -> None:
        """
        Cyberpunk-style lighting: dim ambient + colored directional
        light simulating a neon-lit sky.

        Overrides the base to use colder, bluer tones characteristic
        of a night-time cyberpunk city.
        """
        from panda3d.core import AmbientLight, DirectionalLight

        # Blue-tinged ambient light.
        ambient = AmbientLight("cyber_ambient")
        ambient.setColor(Vec4(0.12, 0.12, 0.25, 1.0))
        al_np = self.world_root.attachNewNode(ambient)
        self.world_root.setLight(al_np)

        # Strong directional light with a cool neon tint.
        dlight = DirectionalLight("cyber_sun")
        dlight.setColor(Vec4(0.55, 0.58, 0.85, 1.0))
        dlight.setDirection(Vec3(-0.3, -0.5, -0.7).normalized())
        # Enable shadows for the directional light.
        dlight.setShadowCaster(True, 1024, 1024)
        dlight_np = self.world_root.attachNewNode(dlight)
        self.world_root.setLight(dlight_np)

        self.world_root.setShaderAuto()
        logger.info("Cyberpunk lighting configured.")

    def _setup_fog(self) -> None:
        """
        Configure volumetric-like fog for the cyberpunk city.

        Uses a denser, blue-tinged exponential fog to simulate
        the misty, rain-soaked atmosphere of a neon city.
        """
        self._fog = Fog("cyberpunk_fog")
        fog_color = Vec4(0.02, 0.05, 0.15, 1.0)
        self._fog.set_color(fog_color)
        self._fog.set_exp_density(0.006)  # Dense fog
        self.world_root.set_fog(self._fog)
        self.game.render.set_fog(self._fog)

        logger.info("Cyberpunk fog configured (density=0.006).")

    # ------------------------------------------------------------------ #
    #  Sky override                                                     #
    # ------------------------------------------------------------------ -->

    def _setup_sky(self) -> None:
        """
        Create a night-sky dome with a gradient color.

        Instead of relying on the SceneManager's sky, we create a
        large sphere with a dark blue-to-purple gradient material
        to match the cyberpunk aesthetic.
        """
        radius = 400.0
        segments = 32

        vformat = GeomVertexFormat.getV3n3()
        vdata = GeomVertexData("sky_sphere", vformat, Geom.UH_static)

        vertex = GeomVertexWriter(vdata, "vertex")
        normal = GeomVertexWriter(vdata, "normal")

        # Build a UV sphere (inverted -- normals face inward).
        # Store color per-vertex using the normal as a carrier for color.
        for i in range(segments + 1):
            phi = (i / segments) * math.pi
            for j in range(segments + 1):
                theta = (j / segments) * 2.0 * math.pi

                # Color gradient: dark blue at top, purple at horizon, dark at bottom.
                t = i / segments
                if t < 0.5:
                    # Top: dark blue
                    color_val = 0.08 + t * 0.07
                    col = Vec4(0.02, 0.02, color_val, 1.0)
                elif t < 0.8:
                    # Mid: purple-pink
                    blend = (t - 0.5) / 0.3
                    r = 0.05 + blend * 0.2
                    g = 0.02 + blend * 0.1
                    b = 0.2 + blend * 0.3
                    col = Vec4(r, g, b, 1.0)
                else:
                    # Bottom: very dark
                    col = Vec4(0.0, 0.0, 0.05, 1.0)

                x = radius * math.sin(phi) * math.cos(theta)
                y = radius * math.cos(phi)
                z = radius * math.sin(phi) * math.sin(theta)

                vertex.addData3f(x, y, z)
                # Use normalized position * color as "normal" for vertex coloring
                # (we'll use setColor instead for a simpler approach).
                nx = x / radius
                ny = y / radius
                nz = z / radius
                # Modulate normal by color to pass color info via vertex color-like approach
                normal.addData3f(nx * col[0] * 2, ny * col[1] * 2, nz * col[2] * 2)

        # Triangulate the sphere.
        prim = GeomTriangles(Geom.UH_static)
        for i in range(segments):
            for j in range(segments):
                a = i * (segments + 1) + j
                b = (i + 1) * (segments + 1) + j
                c = a + 1
                d = b + 1
                if i > 0:
                    prim.addVertices(a, b, c)
                if i < segments - 1:
                    prim.addVertices(c, b, d)

        prim.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(prim)

        node = GeomNode("cyber_sky_geom")
        node.addGeom(geom)

        sky_np = self.world_root.attachNewNode(node)
        sky_np.setHpr(0, 180, 0)  # Flip so normals face inward
        sky_np.setLightOff()      # Don't let sky be lit by world lights
        sky_np.setShaderAuto()
        sky_np.setBin("background", 0)
        sky_np.setDepthTest(False)
        sky_np.setDepthWrite(False)

        # Apply a gradient color to the sky sphere.
        sky_np.setColor(Vec4(0.02, 0.02, 0.1, 0.0))

        # Create a material for the sky.
        sky_mat = self._create_material(
            name="night_sky",
            diffuse=Vec4(0.05, 0.05, 0.2, 1.0),
            ambient=Vec4(0.05, 0.05, 0.2, 1.0),
            specular=Vec4(0.1, 0.1, 0.2, 1.0),
            shininess=1.0,
        )
        sky_np.setMaterial(sky_mat, 1)

        logger.info("Cyberpunk night sky sphere created.")

    # ------------------------------------------------------------------ #
    #  Geometry override                                                #
    # ------------------------------------------------------------------ -->

    def _load_geometry(self) -> None:
        """
        Load / create the level mesh.

        For this demo we build a cyberpunk city with procedurally
        generated buildings, neon signs, and a wet reflective floor.
        """
        # Delegate to base for the floor (ground plane) -- but override
        # the ground material.
        super()._load_geometry()

        # Build the cyberpunk cityscape.
        self._create_city_ground()
        self._create_buildings()
        self._create_neon_signs()

        # Start rain if enabled.
        if self.enable_rain:
            self._start_rain()

    def _create_city_ground(self) -> None:
        """
        Replace the base floor with a wet, reflective cyberpunk ground.

        The ground is a large plane with high specular reflectivity
        to simulate wet pavement under neon lights.
        """
        # Remove the base floor.
        old_floor = self.world_root.find("**/grid_floor")
        if not old_floor.isEmpty():
            old_floor.removeNode()

        size = self.city_size
        half = size / 2.0

        # Create a large ground plane.
        cm = CardMaker("cyber_floor")
        cm.setFrame(-half, half, -half, half)
        floor = self.world_root.attachNewNode(cm.generate())
        floor.setHpr(0, -90, 0)  # Rotate to horizontal
        floor.setZ(-0.05)  # Slightly below origin to avoid z-fighting

        # Wet pavement material: dark with high specular.
        wet_mat = self._create_material(
            name="wet_pavement",
            diffuse=Vec4(0.03, 0.03, 0.06, 1.0),   # Very dark base
            ambient=Vec4(0.05, 0.05, 0.1, 1.0),
            specular=Vec4(0.9, 0.9, 1.0, 1.0),    # Strong highlights
            shininess=64.0,                        # Sharp reflections
        )
        floor.set_material(wet_mat, 1)

        # Add a subtle repeating pattern by tiling the texture coordinates.
        from panda3d.core import TextureStage
        floor.setTexScale(TextureStage.getDefault(), 4.0, 4.0)

        # Collision for the ground.
        from panda3d.core import CollisionNode, CollisionPlane, Plane

        ground_plane = CollisionPlane(Plane(Vec3(0, 0, 1), Point3(0, 0, 0)))
        cnode = CollisionNode("cyber_ground_collision")
        cnode.addSolid(ground_plane)
        cnode.setIntoCollideMask(self._get_collision_mask())
        cnode.setTag("geometry", "floor")

        self.collision_root.attachNewNode(cnode)

        logger.info("Wet reflective ground created (%.1fx%.1f).", size, size)

    def _create_buildings(self) -> None:
        """
        Generate a grid of buildings with varying heights and widths.

        Buildings are placed in a city-block grid pattern. Heights and
        widths are varied using a deterministic pseudo-random approach
        based on grid coordinates.
        """
        grid_size = self.grid_divisions
        spacing = self.city_size / grid_size

        for gx in range(grid_size):
            for gy in range(grid_size):
                if self._should_skip_plot(gx, gy, grid_size):
                    continue

                # Deterministic pseudo-random dimensions based on grid coords.
                # This ensures consistent generation across runs.
                h1 = math.sin(gx * 2.1 + gy * 1.3) * 0.5 + 0.5  # [0, 1]
                h2 = math.cos(gx * 0.7 + gy * 3.1) * 0.5 + 0.5
                w1 = math.sin(gx * 1.7 - gy * 2.3) * 0.5 + 0.5
                w2 = math.cos(gx * 3.3 - gy * 0.8) * 0.5 + 0.5

                width = 3.0 + h1 * 4.0          # 3-7 units
                depth = 3.0 + h2 * 4.0          # 3-7 units
                height = 5.0 + w1 * 10.0 + w2 * 5.0  # 5-20 units

                # Position (center of grid cell, offset from world center).
                bx = gx * spacing - self.city_size / 2 + spacing / 2
                by = gy * spacing - self.city_size / 2 + spacing / 2

                building = self._create_building(width, depth, height, bx, by)
                self._buildings.append(building)

        logger.info("Generated %d buildings.", len(self._buildings))

    def _should_skip_plot(self, gx: int, gy: int, grid_size: int) -> bool:
        """
        Determine whether a grid cell should be empty (street / alley).

        Creates a pattern with main streets and some random gaps.
        Uses deterministic pseudo-randomness based on coordinates.
        """
        # Main streets every 3 cells.
        if gx % 3 == grid_size // 2 or gy % 3 == grid_size // 2:
            if gx % 6 == 0 or gy % 6 == 0:
                return True

        # Deterministic pseudo-random gaps (~15% chance).
        gap_val = math.sin(gx * 12.9898 + gy * 78.233) * 43758.5453
        gap_val = gap_val - math.floor(gap_val)  # Fractional part
        if gap_val < 0.15:
            return True

        # Center plaza -- leave some space open.
        center = grid_size // 2
        if abs(gx - center) <= 1 and abs(gy - center) <= 1:
            if math.sin(gx * 17.0 + gy * 29.0 + gx * gy * 0.1) > 0.5:
                return True

        return False

    def _create_building(
        self,
        width: float,
        depth: float,
        height: float,
        x: float,
        y: float,
    ) -> NodePath:
        """
        Create a single cyberpunk-style building.

        Args:
            width: Building width (X-axis).
            depth: Building depth (Y-axis).
            height: Building height (Z-axis).
            x: World X position (center of building footprint).
            y: World Y position (center of building footprint).

        Returns:
            NodePath of the created building.
        """
        # Use the base class helper to create a box geometry.
        box_np = self._make_box_nodepath(width, depth, height, name=f"building_{x:.0f}_{y:.0f}")
        building = self.world_root.attachNewNode(box_np.node())
        building.setPos(x, y, height / 2.0)  # Base at z=0

        # Create building material with cyberpunk aesthetic.
        mat = self._create_building_material(height)
        building.set_material(mat, 1)

        # Set collision box for the building.
        cnode = CollisionNode(f"building_collision_{x:.0f}_{y:.0f}")
        cnode.addSolid(CollisionBox(
            Point3(x, y, height / 2.0),
            width / 2.0,
            depth / 2.0,
            height / 2.0,
        ))
        cnode.setIntoCollideMask(self._get_collision_mask())
        cnode.setTag("geometry", "building")
        self.collision_root.attachNewNode(cnode)

        # Add reflective glass panels or trim for taller buildings.
        if height > 12:
            self._add_building_trim(building, width, depth, height)

        return building

    def _create_building_material(self, height: float) -> "Material":
        """
        Create a cyberpunk-style material for a building.

        Taller buildings get darker, glassier materials with more
        blue/purple tint. Shorter buildings are brighter.

        Args:
            height: Building height (used to vary material properties).

        Returns:
            A configured Material.
        """
        height_factor = height / 20.0  # Normalize for aesthetic variation

        # Dark base with blue tint, varying by height.
        r = 0.04 + height_factor * 0.03
        g = 0.04 + height_factor * 0.02
        b = 0.08 + height_factor * 0.15

        # Specular increases with height (reflective glass).
        spec = 0.3 + height_factor * 0.5
        shininess = 30.0 + height_factor * 50.0

        mat = self._create_material(
            name=f"building_mat_h{int(height)}",
            diffuse=Vec4(r, g, b + 0.05, 1.0),
            ambient=Vec4(r * 1.3, g * 1.3, b * 1.3, 1.0),
            specular=Vec4(spec, spec, spec * 1.2, 1.0),
            shininess=shininess,
        )
        return mat

    def _add_building_trim(self, building: NodePath, width: float, depth: float, height: float) -> None:
        """
        Add a thin trim box around the top edge of tall buildings.

        Tall buildings sometimes have a lighter-colored cap for
        visual interest and to suggest a rooftop antenna array.
        """
        trim_np = self._make_box_nodepath(
            width + 0.4,
            depth + 0.4,
            0.6,
            name="building_trim",
        )
        trim = building.attachNewNode(trim_np.node())
        trim.setZ(height / 2.0 + 0.3)  # On top of the building

        mat = self._create_material(
            name="building_trim_mat",
            diffuse=Vec4(0.3, 0.3, 0.5, 1.0),
            ambient=Vec4(0.4, 0.4, 0.6, 1.0),
            specular=Vec4(0.7, 0.7, 0.9, 1.0),
            shininess=40.0,
        )
        trim.set_material(mat, 1)

    # ------------------------------------------------------------------ #
    #  Neon signs and lights                                            #
    # ------------------------------------------------------------------ -->

    def _create_neon_signs(self) -> None:
        """
        Generate neon signs on buildings with emissive materials.

        Neon signs are placed on the sides of buildings facing outward.
        Each sign is both a visible emissive panel and a light source.
        """
        target_signs = 30  # Desired number of neon signs
        num_signs = 0

        for building in self._buildings:
            if num_signs >= target_signs:
                break

            pos = building.getPos()
            scale = building.getScale()
            width = scale[0]
            depth = scale[1]
            height = scale[2]

            # Try 2-3 signs per building on random faces.
            for face_idx in range(4):
                if num_signs >= target_signs:
                    break

                # Deterministic pseudo-random decision.
                face_val = math.sin(id(building) * 0.001 + face_idx * 7.13) * 43758.5453
                face_val = face_val - math.floor(face_val)

                if face_val < 0.4:
                    sign = self._create_neon_sign(building, pos, width, depth, height, face_idx)
                    if sign is not None:
                        self._neon_signs.append(sign)
                        num_signs += 1

        logger.info("Generated %d neon signs.", num_signs)

    def _create_neon_sign(
        self,
        parent: NodePath,
        building_pos: Vec3,
        width: float,
        depth: float,
        height: float,
        face_idx: int,
    ) -> NodePath | None:
        """
        Create a single neon sign on a specified building face.

        Args:
            parent: The building NodePath to attach the sign to.
            building_pos: World position of the building center.
            width: Building width.
            depth: Building depth.
            height: Building height.
            face_idx: Face of the building (0=front, 1=back, 2=left, 3=right).

        Returns:
            NodePath of the created neon sign, or None on failure.
        """
        # Sign dimensions.
        sign_width = 1.5 + (math.sin(face_idx * 3.7) * 0.5 + 0.5) * 1.0   # 1.5-2.5
        sign_height = 0.3 + (math.cos(face_idx * 5.3) * 0.5 + 0.5) * 0.7  # 0.3-1.0

        # Place sign at a random height on the building wall.
        y_offset = height * (0.2 + (math.sin(face_idx * 11.1) * 0.5 + 0.5) * 0.4)

        # Determine outward normal direction based on face.
        if face_idx == 0:  # Front (facing -Y)
            sign_pos = Vec3(0, -depth / 2.0, y_offset)
        elif face_idx == 1:  # Back (facing +Y)
            sign_pos = Vec3(0, depth / 2.0, y_offset)
        elif face_idx == 2:  # Left (facing -X)
            sign_pos = Vec3(-width / 2.0, 0, y_offset)
        else:  # Right (facing +X)
            sign_pos = Vec3(width / 2.0, 0, y_offset)

        # Choose a neon color.
        neon_colors = [
            Vec4(1.0, 0.0, 0.4, 1.0),   # Hot pink / magenta
            Vec4(0.0, 0.8, 1.0, 1.0),   # Cyan
            Vec4(1.0, 0.3, 0.0, 1.0),   # Orange-red
            Vec4(0.3, 0.0, 1.0, 1.0),   # Purple
            Vec4(0.0, 1.0, 0.5, 1.0),   # Electric green
            Vec4(1.0, 1.0, 0.0, 1.0),   # Yellow
        ]
        color = neon_colors[face_idx % len(neon_colors)]

        # Create the sign panel (a thin box).
        sign_np = self._make_box_nodepath(sign_width, 0.15, sign_height, name="neon_sign")
        sign = parent.attachNewNode(sign_np.node())
        sign.setPos(sign_pos)
        sign.set_name("neon_sign")

        # Emissive + colored material for the sign.
        sign_mat = self._create_material(
            name=f"neon_{face_idx}_{len(self._neon_signs)}",
            diffuse=color * 0.3,
            ambient=color * 0.3,
            specular=Vec4(1, 1, 1, 1),
            shininess=60.0,
            emissive=color * 0.9,  # Strong emissive glow
        )
        sign.set_material(sign_mat, 1)

        # Enable transparency for soft edges.
        sign.setTransparency(TransparencyAttrib.M_alpha)

        # Attach a point light to make the sign cast colored light.
        light_pos = Vec3(
            building_pos[0] + sign_pos[0],
            building_pos[1] + sign_pos[1],
            building_pos[2] + y_offset,
        )
        light_np = self._add_point_light(
            name=f"neon_light_{len(self._neon_signs)}",
            color=color * 0.6,
            position=light_pos,
            attenuation=Vec3(0.0, 0.0, 0.3),  # Localized falloff
        )
        self._neon_lights.append(light_np)

        return sign

    # ------------------------------------------------------------------ #
    #  Rain particle effect                                             #
    # ------------------------------------------------------------------ -->

    def _start_rain(self) -> None:
        """
        Start the rain particle effect.

        Creates a particle system that simulates rain falling from the sky
        onto the ground. Rain drops are tiny transparent particles with
        a slight downward velocity, tinted blue to match the cyberpunk
        aesthetic.

        Uses Panda3D's standard ParticleSystem API:
        - ``ParticleEffect`` is the top-level container.
        - We create a ``Particles`` pool and add it to the effect.
        - The pool's ``factory``, ``renderer``, and ``emitter`` control
          how particles are born, how they look, and where/when they spawn.
        - ``renderParent`` determines where particles are drawn (the world).
        """
        try:
            self._rain_effect = ParticleEffect("cyberpunk_rain")

            # Create a Particles pool for rain drops.
            rain_particles = Particles("rain_drops")
            self._rain_effect.addParticles(rain_particles)

            # --- Factory: how each drop is born and lives ---
            rain_particles.factory.set_lifespan(0.8)            # Drop lives 0.8s
            rain_particles.factory.set_mass(0.15)               # Light drops
            rain_particles.factory.set_terminal_velocity(40.0)  # Cap fall speed
            # Gravity-like downward force (offset force in Z direction).
            rain_particles.factory.set_final_alpha(0.0)

            # --- Renderer: how each drop appears ---
            # Use a point sprite renderer with a fade-out effect.
            renderer = rain_particles.renderer
            renderer.set_alpha_mode(renderer.PR_ALPHA_OUT)      # Fade out as it ages
            renderer.set_color(Vec4(0.6, 0.8, 1.0, 0.6))       # Light blue tint
            renderer.set_scale(0.12)                             # Tiny drops

            # --- Emitter: where drops spawn and their initial velocity ---
            # Position the emitter high above the city, covering the city area.
            # We use a large rectangle emitter (via setBounds with manual config).
            emitter = rain_particles.emitter

            # Configure emitter to cover the entire city area from above.
            half_size = self.city_size / 2.0 + 10.0

            # Set emission parameters for downward rain.
            # The amplitude sets the initial velocity magnitude.
            emitter.set_emission_type(ParticleSystem.ET_NORMAL)
            emitter.set_amplitude(1.0)
            emitter.set_amplitude_spread(0.2)

            # Spread particles across a wide area above the city.
            emitter.set_theta(0)    # No horizontal rotation
            emitter.set_phi(90)     # Point downward (90 degrees from vertical)
            emitter.set_omega(0)    # No roll

            # Set the emitter's offset position (high above).
            emitter.set_offset_force(Vec3(0, 0, -20.0))  # Downward initial velocity

            # Configure emitter bounds to cover the city area.
            # For a point/plane emitter, we spread across the city.
            emitter.set_explicit_birth_parallel(True)

            # Pool and birth settings.
            rain_particles.set_birth_rate(0.002)          # Frequent births
            rain_particles.set_pool_size(self.rain_particle_count)
            rain_particles.set_splash(False)              # No splash on birth
            rain_particles.set_soft_start(0.0, 1.0)
            rain_particles.set_soft_stop(1.0, 1.0)
            rain_particles.set_uniform_scale(True)
            rain_particles.set_render_mode_perspective(True)

            # Start the rain effect, parented to the world root.
            # The renderParent is the base render so particles appear in the world.
            self._rain_effect.start(
                parent=self.world_root,
                renderParent=self.game.render
            )

            # Position the particle effect to cover the city area.
            # Place high above the city so particles fall through the scene.
            self._rain_effect.set_pos(0, 0, 70.0)

            logger.info("Rain particle system started (%d particles).",
                        self.rain_particle_count)

        except Exception as e:
            logger.warning("Rain particle system failed: %s", e)
            self._create_minimal_rain()

    def _create_minimal_rain(self) -> None:
        """
        Create a minimal rain effect as a fallback.

        This creates semi-transparent particles falling from above,
        simulating rain in the simplest possible way when the full
        particle system fails to initialize.
        """
        try:
            self._rain_effect = ParticleEffect("minimal_rain")

            # Create a Particles pool.
            rain = Particles("rain_minimal")
            self._rain_effect.addParticles(rain)

            # Factory settings (birth and lifecycle).
            rain.factory.set_lifespan(0.6)
            rain.factory.set_mass(0.2)
            rain.factory.set_terminal_velocity(30.0)
            rain.factory.set_final_alpha(0.0)

            # Emitter settings (downward velocity).
            rain.emitter.set_offset_force(Vec3(0, 0, -15.0))
            rain.emitter.set_emission_type(ParticleSystem.ET_NORMAL)

            # Renderer settings (appearance).
            renderer = rain.renderer
            renderer.set_alpha_mode(renderer.PR_ALPHA_OUT)
            renderer.set_color(Vec4(0.55, 0.75, 1.0, 0.4))
            renderer.set_scale(0.15)

            # Pool and birth settings.
            rain.set_birth_rate(0.004)
            rain.set_pool_size(800)
            rain.set_render_mode_perspective(True)

            # Start the minimal rain system high above the city.
            self._rain_effect.start(
                parent=self.world_root,
                renderParent=self.game.render
            )
            self._rain_effect.set_pos(0, 0, 60.0)

            logger.info("Minimal rain particle system started.")

        except Exception as e:
            logger.warning("Could not start any rain effect: %s", e)

    def _stop_rain(self) -> None:
        """Stop and clean up the rain particle effect."""
        if self._rain_effect is not None:
            try:
                self._rain_effect.softStop()
                self._rain_effect.cleanup()
            except Exception as e:
                logger.warning("Error stopping rain effect: %s", e)
            self._rain_effect = None

    # ------------------------------------------------------------------ #
    #  Collision override                                               #
    # ------------------------------------------------------------------ -->

    def _setup_collision(self) -> None:
        """
        Set up collision geometry for the cyberpunk city.

        Creates floor collision and per-building collision boxes.
        Building collisions are handled in ``_create_building``.
        """
        from panda3d.core import CollisionNode, CollisionPlane, Plane

        # Floor collision plane.
        floor_plane = CollisionPlane(
            Plane(Vec3(0, 0, 1), Point3(0, 0, 0))
        )

        cnode = CollisionNode("cyber_floor_collision")
        cnode.addSolid(floor_plane)
        cnode.setIntoCollideMask(self._get_collision_mask())
        cnode.setTag("geometry", "floor")

        self.collision_root.attachNewNode(cnode)

        logger.info("Cyberpunk city collision geometry set up.")

    # ------------------------------------------------------------------ #
    #  Entity spawning                                                  #
    # ------------------------------------------------------------------ -->

    def _spawn_entities(self) -> None:
        """
        Spawn entities into the cyberpunk city.

        For this demo, we spawn nothing -- but the hook is here
        for future expansion (enemies, pickups, etc.).
        """
        super()._spawn_entities()
        logger.info("Cyberpunk city: no entities spawned (demo).")

    # ------------------------------------------------------------------ #
    #  Audio setup                                                      #
    # ------------------------------------------------------------------ -->

    def get_music_path(self) -> str | None:
        """
        Return the path to cyberpunk-themed background music.

        Returns None since we don't have external assets.
        The game framework can load its own music.
        """
        return None

    # ------------------------------------------------------------------ #
    #  Per-frame update                                                 #
    # ------------------------------------------------------------------ -->

    def update(self, dt: float) -> None:
        """
        Cyberpunk city per-frame update.

        Currently handles rain animation and any dynamic neon effects.

        Parameters
        ----------
        dt : float
            Delta time in seconds.
        """
        super().update(dt)

        # Future: animate neon pulse, adjust rain intensity based on
        # player position, etc.

    # ------------------------------------------------------------------ #
    #  Public API                                                       #
    # ------------------------------------------------------------------ -->

    def toggle_rain(self, enabled: bool) -> None:
        """
        Enable or disable the rain particle effect.

        Args:
            enabled: True to start rain, False to stop it.
        """
        if enabled and self._rain_effect is None:
            self._start_rain()
        elif not enabled and self._rain_effect is not None:
            self._stop_rain()

    def set_neon_intensity(self, intensity: float) -> None:
        """
        Adjust the intensity of all neon point lights in the scene.

        Args:
            intensity: A multiplier (1.0 = default, 2.0 = double brightness).
        """
        for light_np in self._neon_lights:
            node = light_np.node()
            if isinstance(node, PointLight):
                base_color = node.get_color()
                node.set_color(base_color * intensity)

    def get_building_count(self) -> int:
        """Return the number of buildings in the city."""
        return len(self._buildings)

    def get_neon_sign_count(self) -> int:
        """Return the number of neon signs in the city."""
        return len(self._neon_signs)

    def destroy(self) -> None:
        """Clean up all cyberpunk-specific resources."""
        self._stop_rain()
        super().destroy()


__all__ = ["CyberpunkCity"]
