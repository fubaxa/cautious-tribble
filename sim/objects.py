"""Every GD object ID: what it is to the player and its hitbox.

The data is `sim/data/objects_2.2091.csv`, DynamicButter's object dump: for each ID the game's own
object type, hitbox (at scale 1, rotation 0), hitbox offset and radius, read after GD's per-object
setup. Checked against trace measurements: 32 of 32 measured hitboxes are identical.
"""
import csv
import os
from dataclasses import dataclass, field

SOLID, HAZARD, SLOPE, BREAKABLE, SPECIAL = "solid", "hazard", "slope", "breakable", "special"
SPEED_PORTAL, GRAVITY_PORTAL, MODE_PORTAL, SIZE_PORTAL = "speed", "gravity", "mode", "size"
MIRROR_PORTAL, DUAL_PORTAL, TELEPORT = "mirror", "dual", "teleport"
PAD, ORB, TRIGGER, PICKUP = "pad", "orb", "trigger", "pickup"

# GD's GameObjectType (Geode bindings enum) -> (kind, extra)
TYPE_KIND = {
    0: (SOLID, None), 2: (HAZARD, None), 47: (HAZARD, "animated"), 25: (SLOPE, None),
    21: (BREAKABLE, None), 39: (SPECIAL, "collision block"), 40: (SPECIAL, None),
    3: (GRAVITY_PORTAL, "flip"), 4: (GRAVITY_PORTAL, "normal"), 42: (GRAVITY_PORTAL, "toggle"),
    5: (MODE_PORTAL, "ship"), 6: (MODE_PORTAL, "cube"), 16: (MODE_PORTAL, "ball"),
    19: (MODE_PORTAL, "ufo"), 26: (MODE_PORTAL, "wave"), 27: (MODE_PORTAL, "robot"),
    33: (MODE_PORTAL, "spider"), 41: (MODE_PORTAL, "swing"),
    17: (SIZE_PORTAL, "normal"), 18: (SIZE_PORTAL, "mini"),
    14: (MIRROR_PORTAL, "on"), 15: (MIRROR_PORTAL, "off"),
    23: (DUAL_PORTAL, "on"), 24: (DUAL_PORTAL, "off"), 28: (TELEPORT, None),
    8: (PAD, "yellow"), 9: (PAD, "pink"), 10: (PAD, "blue"), 34: (PAD, "red"), 44: (PAD, "spider"),
    11: (ORB, "yellow"), 12: (ORB, "pink"), 13: (ORB, "blue"), 29: (ORB, "green"),
    32: (ORB, "black"), 35: (ORB, "red"), 36: (ORB, "toggle"), 37: (ORB, "dash-green"),
    38: (ORB, "dash-pink"), 43: (ORB, "spider"), 46: (ORB, "teleport"),
    22: (PICKUP, "secret coin"), 31: (PICKUP, "user coin"), 30: (PICKUP, "item"),
    # 7 = decoration, 20 = modifier (speed portals and triggers), 45 = area effect triggers
}
SPEED_PORTALS = {200: "0.5x", 201: "1x", 202: "2x", 203: "3x", 1334: "4x"}

# Triggers that can't affect the player: matched on the editor icon name in the dump.
_VISUAL_TRIGGER_WORDS = (
    "TintCol", "Pulse", "Alpha", "Shake", "PHide", "PShow", "BGE", "Zoom", "Static", "CamRot",
    "CamGuide", "Edge", "Gradient", "Shader", "Sh_", "Song", "SFX", "Ghost", "StartPos", "Area",
    "eNone", "eFB", "eFT", "eFL", "eFR", "eSU", "eSD", "eFA", "Particle", "ChangeBG", "ChangeG",
    "ChangeMG", "UISettings", "eOffset",
)


@dataclass(frozen=True)
class Info:
    id: int
    name: str
    kind: str | None      # None = decoration / visual only: never touches the player
    extra: str | None
    w: float
    h: float
    dx: float
    dy: float
    radius: float
    gd_type: int


_table: dict | None = None


def table() -> dict:
    global _table
    if _table is None:
        _table = {}
        path = os.path.join(os.path.dirname(__file__), "data", "objects_2.2091.csv")
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(line for line in f if not line.startswith("#")):
                oid = int(r["id"])
                name = r["frame"].replace("_001.png", "").replace("edit_e", "").replace("Btn", "")
                if r["type"] == "":           # could not be set up outside a level (1329: user coin)
                    _table[oid] = Info(oid, name, PICKUP, "user coin", 0, 0, 0, 0, 0, -1)
                    continue
                t = int(r["type"])
                kind, extra = TYPE_KIND.get(t, (None, None))
                if oid in SPEED_PORTALS:
                    kind, extra = SPEED_PORTAL, SPEED_PORTALS[oid]
                elif r["trigger"] == "1":
                    visual = any(w in r["frame"] for w in _VISUAL_TRIGGER_WORDS)
                    kind, extra = (None, None) if visual else (TRIGGER, name)
                _table[oid] = Info(oid, name, kind, extra, float(r["rectW"]), float(r["rectH"]),
                                   float(r["rectDX"]), float(r["rectDY"]), float(r["radius"]), t)
    return _table


def info(oid: int) -> Info | None:
    return table().get(oid)


@dataclass
class Obj:
    id: int
    x: float
    y: float
    rotation: float = 0.0
    kind: str | None = None
    w: float = 0.0
    h: float = 0.0
    extra: str | None = None
    flip_x: bool = False
    flip_y: bool = False
    groups: list = field(default_factory=list)
    multi: bool = False
    radius: float = 0.0
    ox: float = 0.0   # hitbox centre offset from the object's position
    oy: float = 0.0

    @property
    def rect(self):
        return (self.x + self.ox - self.w / 2, self.y + self.oy - self.h / 2, self.w, self.h)


def make(id_: int, x: float, y: float, rotation: float = 0.0, scale_x: float = 1.0, scale_y: float = 1.0) -> Obj:
    """Object with its axis-aligned hitbox. Rotations by 90/270 swap width and height; any other
    rotation keeps the unrotated size and the rotation (those objects use oriented boxes)."""
    o = Obj(id_, x, y, rotation % 360)
    i = info(id_)
    if i and i.kind:
        o.kind, o.extra = i.kind, i.extra
        sx, sy = abs(scale_x), abs(scale_y)
        o.w, o.h, o.ox, o.oy = i.w * sx, i.h * sy, i.dx * sx, i.dy * sy
        o.radius = i.radius * max(sx, sy)
        # Offsets on rotated/flipped objects are not verified against the game yet (NEEDS.md).
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
