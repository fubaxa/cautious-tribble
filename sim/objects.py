"""Object IDs the simulator knows, with their hitboxes (width, height, centred on the object).

Sizes come from DynamicButter trace rows (O/P/D give each object's hitbox rect). Objects not listed
are treated as decoration, which is wrong for unknown solids and hazards: the trace diff shows where.
"""
from dataclasses import dataclass

SOLID, HAZARD, SPEED_PORTAL, GRAVITY_PORTAL = "solid", "hazard", "speed", "gravity"

# id -> (kind, width, height[, extra])
HITBOXES = {
    1: (SOLID, 30.0, 30.0),
    8: (HAZARD, 6.0, 12.0),          # spike (D rows: 6x12, centred)
    10: (GRAVITY_PORTAL, 25.0, 75.0, "normal"),
    11: (GRAVITY_PORTAL, 25.0, 75.0, "flip"),
    200: (SPEED_PORTAL, 35.0, 44.0),  # 0.5x (speed probe log)
    201: (SPEED_PORTAL, 33.0, 56.0),
    202: (SPEED_PORTAL, 51.0, 56.0),
    203: (SPEED_PORTAL, 65.0, 56.0),
    1334: (SPEED_PORTAL, 69.0, 56.0),
}


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

    @property
    def rect(self):
        return (self.x - self.w / 2, self.y - self.h / 2, self.w, self.h)


def make(id_: int, x: float, y: float, rotation: float = 0.0) -> Obj:
    o = Obj(id_, x, y, rotation)
    hb = HITBOXES.get(id_)
    if hb:
        o.kind, o.w, o.h = hb[0], hb[1], hb[2]
        o.extra = hb[3] if len(hb) > 3 else None
    return o


def overlap(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
