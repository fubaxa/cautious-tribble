"""Object IDs the simulator knows.

GAMEPLAY: id -> (kind, width, height, extra, name). Hitboxes (centred on the object, at scale 1 and
rotation 0) are measured from DynamicButter trace rows; None = the ID is known but its hitbox hasn't
been measured yet. Names and the trigger / ignore lists are from memory of GD's object IDs and are
only used for reporting; they need checking against a dump from the game (see NEEDS.md).
"""
from dataclasses import dataclass, field

SOLID, HAZARD, SPEED_PORTAL, GRAVITY_PORTAL = "solid", "hazard", "speed", "gravity"
MODE_PORTAL, SIZE_PORTAL, PAD, ORB = "mode", "size", "pad", "orb"
MIRROR_PORTAL, DUAL_PORTAL, TELEPORT = "mirror", "dual", "teleport"

GAMEPLAY = {
    # solids (30x30 confirmed by landing height: player centre = top + half its size)
    1: (SOLID, 30.0, 30.0, None, "block"),
    467: (SOLID, 30.0, 30.0, None, "block"),
    # hazards
    8: (HAZARD, 6.0, 12.0, None, "spike"),
    39: (HAZARD, 6.0, 5.6, None, "half spike"),
    # gravity portals
    10: (GRAVITY_PORTAL, 25.0, 75.0, "normal", "gravity portal (normal)"),
    11: (GRAVITY_PORTAL, 25.0, 75.0, "flip", "gravity portal (flip)"),
    # mode portals
    12: (MODE_PORTAL, 34.0, 86.0, "cube", "cube portal"),
    13: (MODE_PORTAL, None, None, "ship", "ship portal"),
    47: (MODE_PORTAL, 34.0, 86.0, "ball", "ball portal"),
    111: (MODE_PORTAL, None, None, "ufo", "ufo portal"),
    660: (MODE_PORTAL, 34.0, 86.0, "wave", "wave portal"),
    745: (MODE_PORTAL, 34.0, 86.0, "robot", "robot portal"),
    1331: (MODE_PORTAL, None, None, "spider", "spider portal"),
    1933: (MODE_PORTAL, None, None, "swing", "swing portal"),
    # size portals
    99: (SIZE_PORTAL, 31.0, 90.0, "normal", "normal size portal"),
    101: (SIZE_PORTAL, 31.0, 90.0, "mini", "mini portal"),
    # speed portals (GD treats them as touch triggers)
    200: (SPEED_PORTAL, 35.0, 44.0, "0.5x", "speed portal 0.5x"),
    201: (SPEED_PORTAL, 33.0, 56.0, "1x", "speed portal 1x"),
    202: (SPEED_PORTAL, 51.0, 56.0, "2x", "speed portal 2x"),
    203: (SPEED_PORTAL, 65.0, 56.0, "3x", "speed portal 3x"),
    1334: (SPEED_PORTAL, 69.0, 56.0, "4x", "speed portal 4x"),
    # pads
    35: (PAD, 25.0, 4.0, "yellow", "yellow pad"),
    67: (PAD, 25.0, 6.0, "blue", "blue (gravity) pad"),
    140: (PAD, 25.0, 5.0, "pink", "pink pad"),
    1332: (PAD, 29.0, 7.0, "red", "red pad"),
    3005: (PAD, 28.5, 11.0, "spider", "spider pad"),
    # orbs
    36: (ORB, 36.0, 36.0, "yellow", "yellow orb"),
    84: (ORB, 36.0, 36.0, "blue", "blue (gravity) orb"),
    141: (ORB, 36.0, 36.0, "pink", "pink orb"),
    1022: (ORB, 36.0, 36.0, "green", "green orb"),
    1330: (ORB, 36.0, 36.0, "black", "black orb"),
    1333: (ORB, 36.0, 36.0, "red", "red orb"),
    1594: (ORB, 36.0, 36.0, "toggle", "toggle orb"),
    1704: (ORB, 36.0, 36.0, "dash-green", "green dash orb"),
    1751: (ORB, 36.0, 36.0, "dash-pink", "pink dash orb"),
    3004: (ORB, 36.0, 36.0, "spider", "spider orb"),
    # known by ID, not measured
    45: (MIRROR_PORTAL, None, None, "on", "mirror portal (on)"),
    46: (MIRROR_PORTAL, None, None, "off", "mirror portal (off)"),
    286: (DUAL_PORTAL, None, None, "on", "dual portal (on)"),
    287: (DUAL_PORTAL, None, None, "off", "dual portal (off)"),
    747: (TELEPORT, None, None, None, "teleport portal"),
}

# Hazards that killed the player in a trace, but whose base size isn't known (the trace row gives
# the hitbox as placed, with unknown scale/rotation; saws use a radius). Kept as hazards, unmeasured.
for _id in (218, 446, 458, 678, 1705, 1707, 1719, 1732, 1734, 1735):
    GAMEPLAY[_id] = (HAZARD, None, None, None, "hazard (size not measured)")

# Triggers that change gameplay (from memory): kept in the converted level's "triggers" list.
GAMEPLAY_TRIGGERS = {
    901: "move", 1049: "toggle", 1346: "rotate", 1347: "follow", 1268: "spawn", 1595: "touch",
    1611: "count", 1811: "instant count", 1815: "collision", 1616: "stop", 2067: "scale",
    1814: "follow player y", 1912: "random", 1917: "reverse", 2900: "rotate gameplay",
    1935: "time warp", 2899: "options", 3600: "end", 1817: "pickup", 1812: "on death",
    1585: "animate", 3016: "advanced follow", 2068: "advanced random", 3033: "keyframe animate",
    1816: "collision block", 3640: "collision state", 2066: "gravity", 3022: "teleport",
}

# Never affect the player (from memory): start positions, colour / camera / visual / audio triggers.
IGNORED = {
    31: "start position", 899: "color", 29: "bg color", 30: "ground color", 105: "color", 744: "color",
    900: "color", 915: "color", 1006: "pulse", 1007: "alpha", 1520: "shake", 1612: "hide player",
    1613: "show player", 32: "trail on", 33: "trail off", 1818: "bg effect on", 1819: "bg effect off",
    1913: "camera zoom", 1914: "camera static", 1916: "camera offset", 2015: "camera rotate",
    2062: "camera edge", 2925: "camera mode", 2016: "camera guide", 1934: "song", 3602: "sfx",
    22: "enter effect", 23: "enter effect", 24: "enter effect", 25: "enter effect", 26: "enter effect",
    27: "enter effect", 28: "enter effect", 55: "enter effect", 56: "enter effect", 57: "enter effect",
    58: "enter effect", 59: "enter effect", 1915: "stop jump", 2999: "middleground", 3029: "bg change",
    3030: "ground change", 3031: "mg change",
}


@dataclass
class Obj:
    id: int
    x: float
    y: float
    rotation: float = 0.0
    kind: str | None = None
    w: float | None = 0.0
    h: float | None = 0.0
    extra: str | None = None
    flip_x: bool = False
    flip_y: bool = False
    groups: list = field(default_factory=list)
    multi: bool = False

    @property
    def rect(self):
        return (self.x - self.w / 2, self.y - self.h / 2, self.w, self.h)


def make(id_: int, x: float, y: float, rotation: float = 0.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Obj:
    """Object with its axis-aligned hitbox. Rotations by 90/270 swap width and height; any other
    rotation keeps the unrotated size and the rotation (those objects use oriented boxes)."""
    o = Obj(id_, x, y, rotation % 360)
    g = GAMEPLAY.get(id_)
    if g:
        o.kind, o.w, o.h, o.extra = g[0], g[1], g[2], g[3]
        if o.w is not None:
            o.w, o.h = o.w * abs(scale_x), o.h * abs(scale_y)
            if o.rotation in (90.0, 270.0):
                o.w, o.h = o.h, o.w
                o.rotation = 0.0
            elif o.rotation == 180.0:
                o.rotation = 0.0
                o.flip_y = not o.flip_y
                o.flip_x = not o.flip_x
    return o


def overlap(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
