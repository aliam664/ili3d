"""
constants.py

Fixed game-wide constants that do not change at runtime.
These include collision mask bits, tag names, physics parameters,
and other foundational identifiers used throughout the engine.

All values are immutable and defined as class-level attributes.
"""

from panda3d.core import BitMask32


class Constants:
    """
    Global game constants.

    This class holds values that are truly constant across the entire
    lifetime of the application.  Modify this file to tune fundamental
    game parameters; runtime tweaks should live in ``Settings``.
    """

    # ------------------------------------------------------------------ #
    #  Collision bit-masks                                               #
    #  Each object type gets its own bit.  An object's INTO mask          #
    #  determines what it can be hit *by*, and its FROM mask determines   #
    #  what it can hit *with*.                                            #
    # ------------------------------------------------------------------ #

    #: Collides with world geometry (walls, floor, ceilings).
    MASK_GEOMETRY = BitMask32.bit(0)

    #: Collides with the player capsule.
    MASK_PLAYER = BitMask32.bit(1)

    #: Collides with enemy characters.
    MASK_ENEMY = BitMask32.bit(2)

    #: Collides with projectiles / bullets.
    MASK_PROJECTILE = BitMask32.bit(3)

    #: A combination of all masks — useful for "everything" checks.
    MASK_ALL = BitMask32.all_on()

    # ------------------------------------------------------------------ #
    #  Collision node / ray flags                                        #
    # ------------------------------------------------------------------ #

    #: Tag key used to mark nodes that belong to walkable world geometry.
    TAG_GEOMETRY = "geometry"

    #: Tag key used to mark enemy characters.
    TAG_ENEMY = "enemy"

    # ------------------------------------------------------------------ #
    #  Physics parameters                                                #
    # ------------------------------------------------------------------ #

    #: Gravity acceleration in Panda3D units / sec^2 (positive = down).
    GRAVITY = 32.0

    #: Default step height for climbing (not yet fully implemented).
    STEP_HEIGHT = 1.4

    #: Maximum vertical velocity before terminal velocity kicks in.
    TERMINAL_VELOCITY = 60.0

    # ------------------------------------------------------------------ #
    #  Player physics dimensions                                         #
    # ------------------------------------------------------------------ #

    #: Radius of the player's capsule collider (half-width).
    PLAYER_RADIUS = 0.4

    #: Full height of the player (standing).
    PLAYER_HEIGHT_STANDING = 1.8

    #: Height of the player when crouching.
    PLAYER_HEIGHT_CROUCHING = 1.0

    #: Time (seconds) to interpolate between standing and crouching.
    CROUCH_TRANSITION_TIME = 0.3

    # ------------------------------------------------------------------ #
    #  Movement speeds (units / second)                                  #
    # ------------------------------------------------------------------ #

    WALK_SPEED = 8.0          # Walking (base move speed).
    SPRINT_SPEED = 16.0       # Sprinting (fast move speed).
    CROUCH_SPEED = 4.0        # Moving while crouched.

    #: Jump impulse velocity (upward units / second).
    JUMP_VELOCITY = 18.0

    #: Mouse sensitivity multiplier — multiplied by the user setting.
    MOUSE_SENSITIVITY_SCALE = 0.15

    # ------------------------------------------------------------------ #
    #  Camera / FOV                                                      #
    # ------------------------------------------------------------------ #

    #: Default field of view in degrees.
    DEFAULT_FOV = 80.0

    #: Minimum FOV (when running, e.g. FOV kick).
    MIN_FOV = 70.0

    #: Maximum FOV.
    MAX_FOV = 100.0

    # ------------------------------------------------------------------ #
    #  Default user settings (used on first launch)                      #
    # ------------------------------------------------------------------ #

    #: Default master volume (0.0 – 1.0).
    DEFAULT_MASTER_VOLUME = 0.8

    #: Default SFX volume.
    DEFAULT_SFX_VOLUME = 0.8

    #: Default music volume.
    DEFAULT_MUSIC_VOLUME = 0.6

    #: Default mouse sensitivity (0.0 – 1.0).
    DEFAULT_MOUSE_SENSITIVITY = 0.7

    #: Default field of view.
    DEFAULT_FOV_SETTING = 80.0
