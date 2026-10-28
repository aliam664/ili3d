"""
controller.py

PlayerController — first-person movement and camera control.

Features
--------
- Mouse-look with configurable sensitivity.
- WASD movement (walk / sprint / crouch).
- Jump with gravity and collision detection.
- Collision capsule against world geometry.
- First-person camera with proper FOV.

The controller is designed to be driven by the main ``Game.update``
loop: call ``controller.update(dt)`` every frame.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from panda3d.core import (
    BitMask32,
    CollisionHandlerGravity,
    CollisionNode,
    CollisionRay,
    CollisionSphere,
    GeomNode,
    NodePath,
    PandaNode,
    Vec3,
    Vec4,
)
try:
    from panda3d.physics import PhysicsManager
except ImportError:
    PhysicsManager = None  # type: ignore
try:
    from panda3d.bullet import BulletCharacterController  # noqa: F401
except ImportError:
    BulletCharacterController = None  # type: ignore
from direct.showbase.ShowBase import ShowBase
from direct.showbase.Loader import Loader

from config.constants import Constants

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency.
# The Game class is imported here only for type hints; at runtime
# it is passed in via the constructor.
# from core.game import Game  # noqa: F401


class PlayerController:
    """
    First-person player controller.

    Parameters
    ----------
    game : ShowBase
        The running ``Game`` instance.  Must have ``render``,
        ``camera``, ``bulletWorld`` (optional), and ``loader``
        attributes.
    """

    def __init__(self, game: ShowBase) -> None:
        self.game = game

        # ------------------------------------------------------------------
        # Movement state
        # ------------------------------------------------------------------
        self._move_speed: float = Constants.WALK_SPEED
        self._velocity: Vec3 = Vec3(0, 0, 0)
        self._is_on_ground: bool = False
        self._jump_requested: bool = False

        # Movement input flags (set by input callbacks)
        self._move_forward: bool = False
        self._move_backward: bool = False
        self._strafe_left: bool = False
        self._strafe_right: bool = False

        # States
        self._is_sprinting: bool = False
        self._is_crouching: bool = False
        self._crouch_target_time: float = 0.0
        self._crouch_current: float = 0.0  # 0 = standing, 1 = crouched

        # Mouse look state
        self._mouse_enabled: bool = True
        self._vertical_angle: float = 0.0  # camera pitch
        self._horizontal_angle: float = 0.0

        # ------------------------------------------------------------------
        # Create the player node (a scene-graph node the camera hangs from)
        # ------------------------------------------------------------------
        self.node: NodePath = NodePath("player_node")
        self.node.reparentTo(self.game.render)
        self.node.setPos(0, 0, 20)  # start above the ground

        # ------------------------------------------------------------------
        # Camera setup
        # ------------------------------------------------------------------
        self._camera_offset_y: float = 1.4  # eye height when standing
        self._camera_offset_crouch: float = 0.5
        self._cam_node: NodePath = self.game.camera  # alias for clarity
        self._cam_node.reparentTo(self.node)
        self._cam_node.setPos(0, self._camera_offset_y, 0)

        # Apply FOV from settings.
        fov = self.game.settings.get("fov", Constants.DEFAULT_FOV)
        self.game.camLens.setFov(fov)

        # ------------------------------------------------------------------
        # Collision setup
        # ------------------------------------------------------------------
        self._setup_collision()

        # ------------------------------------------------------------------
        # Input binding
        # ------------------------------------------------------------------
        self._setup_input()

        logger.info("PlayerController initialized at %s", self.node.getPos())

    # ------------------------------------------------------------------ #
    #  Collision setup                                                    #
    # ------------------------------------------------------------------ -->

    def _setup_collision(self) -> None:
        """
        Create a collision capsule for the player.

        Uses a collision sphere + ray for floor detection,
        which is a lightweight approximation of a capsule.
        """
        # ------------------------------------------------------------------
        # Floor-detection ray (casts downward to detect ground)
        # ------------------------------------------------------------------
        self._floor_ray = CollisionRay(0, 0, 1.2, 0, 0, -1)
        floor_node = CollisionNode("player_floor_ray")
        floor_node.addSolid(self._floor_ray)
        floor_node.setIntoCollideMask(BitMask32.allOff())
        floor_node.setFromCollideMask(Constants.MASK_GEOMETRY)
        self._floor_np = self.node.attachNewNode(floor_node)

        # ------------------------------------------------------------------
        # Physics-style gravity handler
        # ------------------------------------------------------------------
        self._gravity_handler = CollisionHandlerGravity()
        self._gravity_handler.setGravity(Constants.GRAVITY)

        # Register with the game's collision traverser.
        # We create our own traverser if the game doesn't have one.
        if hasattr(self.game, "cTrav") and self.game.cTrav is not None:
            self._cTrav = self.game.cTrav
        else:
            self._cTrav = None  # we'll handle gravity manually

        # ------------------------------------------------------------------
        # Simple ground check using a downward ray we query manually
        # ------------------------------------------------------------------
        # We'll use ray-casting rather than Panda3D's physics for
        # maximum compatibility and control.

    def _get_player_mass(self) -> float:
        """Return a placeholder mass value for the gravity handler."""
        return 80.0  # kg (affects jump arc feel)

    def _cast_floor_ray(self) -> float:
        """
        Cast a ray straight down from the player and return the
        distance to the ground, or ``-1`` if no ground is found.

        Returns
        -------
        float
            Distance to the ground below the player.
        """
        from panda3d.core import CollisionEntry, CollisionTraverser, NodePath

        origin = self.node.getPos(self.game.render)
        # Ray starts a bit below the player's feet.
        ray_start = Vec3(origin.x, origin.y, origin.z)

        # We'll use a simple approach: check the collision node
        # against the scene graph.
        # For simplicity, if we have a Bullet world, use its ray test.
        if hasattr(self.game, "bulletWorld") and self.game.bulletWorld is not None:
            result = self.game.bulletWorld.rayTestClosest(
                ray_start, ray_start - Vec3(0, 0, 3.0),
                mask=Constants.MASK_GEOMETRY,
            )
            if result.hasHit():
                hit_dist = (ray_start.z - result.getHitPos().z)
                return hit_dist
            return -1.0

        # Fallback: traverse the scene graph manually.
        from panda3d.core import (
            BitMask32,
            CollisionNode,
            CollisionRay,
            CollisionTraverser,
            CollisionHandlerQueue,
        )

        # Create a temporary ray for this query.
        query_node = CollisionNode("floor_query")
        query_ray = CollisionRay(0, 0, 0, 0, 0, -1)
        query_node.addSolid(query_ray)
        query_node.setIntoCollideMask(BitMask32.allOff())
        query_node.setFromCollideMask(Constants.MASK_GEOMETRY)
        query_np = self.game.render.attachNewNode(query_node)
        query_np.setPos(ray_start)

        handler = CollisionHandlerQueue()
        temp_trav = CollisionTraverser()
        temp_trav.setRespectPrevTransform(True)
        temp_trav.add_collider(query_np, handler)
        temp_trav.traverse(self.game.render)

        # Cleanup.
        query_np.removeNode()

        handler.sort_entries()
        if handler.get_num_entries() > 0:
            entry = handler.get_entry(0)
            hit_point = entry.get_surface_point(self.game.render)
            return ray_start.z - hit_point.z

        return -1.0

    # ------------------------------------------------------------------ #
    #  Input handling                                                     #
    # ------------------------------------------------------------------ -->

    def _setup_input(self) -> None:
        """Bind keyboard and mouse input for player actions."""
        # Movement keys.
        self.game.accept("w", self._start_walk_forward)
        self.game.accept("w-up", self._stop_walk_forward)
        self.game.accept("s", self._start_walk_backward)
        self.game.accept("s-up", self._stop_walk_backward)
        self.game.accept("a", self._start_strafe_left)
        self.game.accept("a-up", self._stop_strafe_left)
        self.game.accept("d", self._start_strafe_right)
        self.game.accept("d-up", self._stop_strafe_right)

        # Sprint.
        self.game.accept("shift", self._start_sprint)
        self.game.accept("shift-up", self._stop_sprint)

        # Crouch.
        self.game.accept("control", self._start_crouch)
        self.game.accept("control-up", self._stop_crouch)

        # Jump.
        self.game.accept("space", self._request_jump)

        # Mouse look.
        self.game.accept("mouse1", self._on_mouse_press)  # lock mouse
        self.game.accept("mouse1-up", self._on_mouse_release)

    # -- Movement key callbacks -----------------------------------------

    def _start_walk_forward(self) -> None:
        self._move_forward = True

    def _stop_walk_forward(self) -> None:
        self._move_forward = False

    def _start_walk_backward(self) -> None:
        self._move_backward = True

    def _stop_walk_backward(self) -> None:
        self._move_backward = False

    def _start_strafe_left(self) -> None:
        self._strafe_left = True

    def _stop_strafe_left(self) -> None:
        self._strafe_left = False

    def _start_strafe_right(self) -> None:
        self._strafe_right = True

    def _stop_strafe_right(self) -> None:
        self._strafe_right = False

    def _start_sprint(self) -> None:
        if not self._is_crouching:
            self._is_sprinting = True
            self._update_move_speed()

    def _stop_sprint(self) -> None:
        self._is_sprinting = False
        self._update_move_speed()

    def _start_crouch(self) -> None:
        self._is_crouching = True

    def _stop_crouch(self) -> None:
        # Only stand up if there's no ceiling above us.
        # For now, allow standing up.
        self._is_crouching = False

    def _request_jump(self) -> None:
        """Request a jump — will only succeed if on the ground."""
        if self._is_on_ground:
            self._jump_requested = True

    # -- Mouse -----------------------------------------------------------

    def _on_mouse_press(self) -> None:
        """Lock the mouse cursor to the window."""
        self._mouse_enabled = True
        if self.game.mouseWatcherNode.hasMouse():
            self.game.disable_mouse()
            # Hide cursor.
            props = WindowProperties()
            props.setCursorHidden(True)
            self.game.win.requestProperties(props)

    def _on_mouse_release(self) -> None:
        """Unlock the mouse cursor (e.g. on alt-tab)."""
        props = WindowProperties()
        props.setCursorHidden(False)
        self.game.win.requestProperties(props)

    def _update_move_speed(self) -> None:
        """Recalculate current move speed based on state."""
        if self._is_sprinting:
            self._move_speed = Constants.SPRINT_SPEED
        elif self._is_crouching:
            self._move_speed = Constants.CROUCH_SPEED
        else:
            self._move_speed = Constants.WALK_SPEED

    # ------------------------------------------------------------------ #
    #  Per-frame update                                                   #
    # ------------------------------------------------------------------ -->

    def update(self, dt: float) -> None:
        """
        Update player position, camera, and collision each frame.

        Parameters
        ----------
        dt : float
            Delta time in seconds since the last frame.
        """
        # --------------------------------------------------------------
        # 1. Mouse look
        # --------------------------------------------------------------
        self._update_mouse_look()

        # --------------------------------------------------------------
        # 2. Crouch transition
        # --------------------------------------------------------------
        self._update_crouch(dt)

        # --------------------------------------------------------------
        # 3. Movement input
        # --------------------------------------------------------------
        move_vec = self._get_movement_input()

        # Rotate movement vector by camera heading.
        if move_vec.length_squared() > 0.01:
            rot_mat = self._get_rotation_matrix()
            move_vec = rot_mat.xform_vec(move_vec)
            move_vec.normalize()

        # Apply speed.
        move_vec *= self._move_speed
        self._velocity.x = move_vec.x
        self._velocity.y = move_vec.y

        # --------------------------------------------------------------
        # 4. Gravity & jumping
        # --------------------------------------------------------------
        if self._jump_requested and self._is_on_ground:
            self._velocity.z = Constants.JUMP_VELOCITY
            self._is_on_ground = False
            self._jump_requested = False

        # Apply gravity.
        if not self._is_on_ground:
            self._velocity.z -= Constants.GRAVITY * dt
            self._velocity.z = max(self._velocity.z, -Constants.TERMINAL_VELOCITY)

        # --------------------------------------------------------------
        # 5. Move the player
        # --------------------------------------------------------------
        self.node.setPos(
            self.node.getPos() + self._velocity * dt
        )

        # --------------------------------------------------------------
        # 6. Ground check
        # --------------------------------------------------------------
        self._check_ground()

        # --------------------------------------------------------------
        # 7. Update camera position (crouch offset)
        # --------------------------------------------------------------
        cam_z = (
            self._camera_offset_y * (1 - self._crouch_current)
            + self._camera_offset_crouch * self._crouch_current
        )
        self._cam_node.setZ(cam_z)

    # ------------------------------------------------------------------ #
    #  Movement helpers                                                  #
    # ------------------------------------------------------------------ -->

    def _get_movement_input(self) -> Vec3:
        """
        Read WASD state and produce a movement vector in the
        player's local space (forward = +Y, right = +X).

        Returns
        -------
        Vec3
            Local-space movement direction (not yet normalized
            beyond component checks).
        """
        move = Vec3(0, 0, 0)

        if getattr(self, "_move_forward", False):
            move.y += 1.0
        if getattr(self, "_move_backward", False):
            move.y -= 1.0
        if getattr(self, "_strafe_left", False):
            move.x -= 1.0
        if getattr(self, "_strafe_right", False):
            move.x += 1.0

        return move

    def _get_rotation_matrix(self):
        """
        Build a rotation matrix that transforms local movement to
        world movement based on the player's horizontal heading.
        """
        from panda3d.core import Mat4, Vec3

        # Rotate around the Z axis by the node's heading.
        return Mat4.rotateMat(self.node.getH(), Vec3(0, 0, 1))

    # ------------------------------------------------------------------ #
    #  Mouse look                                                        #
    # ------------------------------------------------------------------ -->

    def _update_mouse_look(self) -> None:
        """
        Read the mouse delta and rotate the player node (horizontal)
        and camera (vertical, clamped to a limited pitch range).
        """
        if not self._mouse_enabled:
            return

        mw = self.game.mouseWatcherNode
        if not mw.hasMouse():
            return

        # Mouse position in window coordinates: range [-1, 1].
        # We want the delta since the last frame, so we use the
        # raw mouse position and reset it to center each frame.
        mouse_pos = mw.getMouse()
        dx = mouse_pos.x
        dy = mouse_pos.y

        # Reset mouse to center so we can keep getting deltas.
        self.game.win.movePointer(0,
            int(self.game.win.getProperties().getXSize() / 2),
            int(self.game.win.getProperties().getYSize() / 2),
        )

        # Apply sensitivity.
        sensitivity = self.game.settings.get("mouse_sensitivity", 0.5)
        scale = sensitivity * Constants.MOUSE_SENSITIVITY_SCALE

        dx *= scale * 100
        dy *= scale * 100

        # Horizontal rotation — applied to the player node.
        self._horizontal_angle += dx
        self.node.setH(self.node.getH() - dx)

        # Vertical rotation — applied to the camera, clamped.
        self._vertical_angle += dy
        self._vertical_angle = max(-80.0, min(80.0, self._vertical_angle))
        self._cam_node.setP(self._vertical_angle)

    # ------------------------------------------------------------------ #
    #  Crouch logic                                                      #
    # ------------------------------------------------------------------ -->

    def _update_crouch(self, dt: float) -> None:
        """
        Smoothly interpolate camera height when crouching / standing.
        """
        target = 1.0 if self._is_crouching else 0.0
        speed = dt / max(Constants.CROUCH_TRANSITION_TIME, 0.001)

        self._crouch_current += (target - self._crouch_current) * speed

        # Ensure we don't overshoot.
        if abs(self._crouch_current - target) < 0.01:
            self._crouch_current = target

    # ------------------------------------------------------------------ #
    #  Ground detection                                                  #
    # ------------------------------------------------------------------ -->

    def _check_ground(self) -> None:
        """
        Check if the player is standing on solid ground.

        Casts a short ray downward; if it hits within a reasonable
        distance, the player is considered grounded and their Z
        position is adjusted for floor height.
        """
        player_pos = self.node.getPos(self.game.render)

        # Cast down from the feet.
        floor_dist = self._cast_floor_ray()

        # Threshold: if ground is within this distance below the
        # player, we consider them grounded.
        ground_threshold = 0.5  # units

        if floor_dist >= 0 and floor_dist < (Constants.PLAYER_HEIGHT_STANDING + ground_threshold):
            # Snap to ground.
            target_z = player_pos.z - floor_dist + 0.1  # small offset above ground
            if abs(self._velocity.z) <= 0.01:
                # Only snap horizontally to avoid jitter when falling.
                self.node.setZ(target_z)
            self._is_on_ground = True
            if self._velocity.z <= 0:
                self._velocity.z = 0
        else:
            self._is_on_ground = False

    # ------------------------------------------------------------------ #
    #  Public API                                                        #
    # ------------------------------------------------------------------ -->

    def get_position(self) -> Vec3:
        """Return the player's current world position."""
        return self.node.getPos(self.game.render)

    def get_forward(self) -> Vec3:
        """Return the forward direction vector (world-space)."""
        # The node's local Y+ is forward.
        forward = self.node.getPos(self.game.render) + Vec3(0, 1, 0)
        # Use the node's orientation to extract the forward vector.
        quat = self.node.getQuat(self.game.render)
        return quat.getForward()

    def set_position(self, x: float, y: float, z: float) -> None:
        """Teleport the player to a world-space position."""
        self.node.setPos(x, y, z)

    def enable_mouse_look(self, enabled: bool = True) -> None:
        """Enable or disable mouse look."""
        self._mouse_enabled = enabled

    def destroy(self) -> None:
        """Clean up the player controller."""
        # Remove the node.
        self.node.removeNode()
