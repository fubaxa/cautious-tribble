"""Headless GD physics, one physics step (1/240 s) at a time. Cube, ship, ball, UFO, wave, robot
and spider.

Order inside a step (each part measured from traces; see NOTES.md and constants.py):
  1. the first step after a spawn doesn't move the player
  2. standing is re-checked; a held button on the ground jumps (this step already moves with the
     jump velocity); otherwise gravity applies while airborne
  3. move: x += xVel*0.25, y += yVel*0.225 (float32 positions)
  4. floor and block tops: landing, with the x snap between consecutive blocks
  5. the step's input arrives (after the move)
  6. objects touched with the new hitbox: portals, pads, orbs (they change the next step), hazards
  7. a new press on the ground jumps: yVel is set now, y first changes on the next step
Wave: no gravity; y moves by +-xVel x 0.25 (mini x 0.5) toward the held direction, so the slope
is exactly 1 (mini 2). The direction set by an input is used from the next step on.
Anything not measured yet raises Unsupported instead of guessing: block sides and ceilings,
slope launches, rotated objects, other game modes. Exception: triggers and teleport portals
(sim/triggers.py) are a provisional first version, not measured, and will change.
"""
import dataclasses
from dataclasses import dataclass, field

from . import constants as C
from .f32 import f32
from .grid import Grid
from .objects import (BREAKABLE, DUAL_PORTAL, GRAVITY_PORTAL, HAZARD, MIRROR_PORTAL, MODE_PORTAL, ORB, PAD, SIZE_PORTAL, SLOPE, SOLID,
                      SPEED_PORTAL, TELEPORT, overlap)
from .triggers import Triggers

import math
import os

EPS = 1e-4


def _sec(o):
    """GD keeps objects in 100-unit sections along x and checks collisions section by section, in
    level-string order within a section."""
    return math.floor(o.x / 100)


def _key(o, p=None):
    """Standing on several blocks at once, the snap's reference is the first one GD checks."""
    return (_sec(o), o.order)


def _lkey(o, p=None):
    """Landing on several blocks at once, the block landed on is the LAST one GD checks: a later
    section, else later in level-string order. Every End 2 (tick 38952) and the brick test
    landed on a brick + a block in two sections and took the block in the later section."""
    return (-_sec(o), -o.order)


def touches_rounded(box, rect, radius):
    """Does `box` (with corners rounded by `radius`) touch `rect`? Touching edges count."""
    dx = min(box[0] + box[2], rect[0] + rect[2]) - max(box[0], rect[0])
    dy = min(box[1] + box[3], rect[1] + rect[3]) - max(box[1], rect[1])
    if dx < 0 or dy < 0:
        return False
    if dx < radius and dy < radius:
        return (radius - dx) ** 2 + (radius - dy) ** 2 < radius * radius
    return True


def _any_rotation(r):
    """A box covering the square r at any rotation about its centre."""
    x, y, w, h = r
    e = (w * 2 ** 0.5 - w) / 2
    return (x - e, y - e, w + 2 * e, h + 2 * e)


def overlap_oriented(r, o):
    """Does the axis-aligned box r overlap object o's box rotated about its centre (clockwise by
    o.rotation)? Separating-axis test; touching counts as overlapping, as with overlap()."""
    import math
    x, y, w, h = o.rect
    cx, cy = x + w / 2, y + h / 2
    a = math.radians(o.rotation)
    c, s_ = math.cos(a), math.sin(a)
    ux, uy = c, -s_          # the box's own x axis, turned clockwise
    vx, vy = s_, c           # its y axis
    corners = [(cx + ux * dx + vx * dy, cy + uy * dx + vy * dy)
               for dx in (-w / 2, w / 2) for dy in (-h / 2, h / 2)]
    rc = [(r[0], r[1]), (r[0] + r[2], r[1]), (r[0], r[1] + r[3]), (r[0] + r[2], r[1] + r[3])]
    for ax, ay in ((1.0, 0.0), (0.0, 1.0), (ux, uy), (vx, vy)):
        p1 = [px * ax + py * ay for px, py in corners]
        p2 = [px * ax + py * ay for px, py in rc]
        if max(p1) < min(p2) or max(p2) < min(p1):
            return False
    return True


def _obb(cx, cy, w, h, deg):
    a = math.radians(deg)
    c, s_ = math.cos(a), math.sin(a)
    ux, uy, vx, vy = c, -s_, s_, c
    return ([(cx + ux * dx + vx * dy, cy + uy * dx + vy * dy) for dx in (-w / 2, w / 2) for dy in (-h / 2, h / 2)],
            ((ux, uy), (vx, vy)))


def obb_overlap(a, b):
    """Separating-axis test of two turned boxes (from _obb); touching counts as overlapping."""
    (ca, axa), (cb, axb) = a, b
    for ax, ay in axa + axb:
        p1 = [x * ax + y * ay for x, y in ca]
        p2 = [x * ax + y * ay for x, y in cb]
        if max(p1) < min(p2) or max(p2) < min(p1):
            return False
    return True


def obb_of(o):
    """The object's turned box. Its hitbox offset turns with it (The Hallucination: a teleport portal
    turned 305 deg, offset 10.8 to the side, was touched a step early with the offset left unturned)."""
    x, y, w, h = o.rect
    if (o.ox or o.oy):
        a = math.radians(o.rotation)
        c, s_ = math.cos(a), math.sin(a)
        return _obb(o.x + c * o.ox + s_ * o.oy, o.y - s_ * o.ox + c * o.oy, w, h, o.rotation)
    return _obb(x + w / 2, y + h / 2, w, h, o.rotation)


def box_hits_slope(box, o):
    """Does the box reach into slope o's solid triangle (not just its bounding box)?"""
    if not overlap(box, o.rect):
        return False
    ln = o.slope_line()
    if not ln:
        return True
    (x0, y0), (x1, y1), below = ln
    lo, hi = max(box[0], x0), min(box[0] + box[2], x1)
    if lo > hi:
        return True      # past the line's ends but in the box: the slope's flat side
    k = (y1 - y0) / (x1 - x0)
    lines = (y0 + k * (lo - x0), y0 + k * (hi - x0))
    return min(box[1] for _ in lines) <= max(lines) if below else box[1] + box[3] >= min(lines)


def slope_triangle(o):
    """Slope o's solid triangle: the two ends of its surface and the right-angle corner."""
    (x0, y0), (x1, y1), below = o.slope_line()
    if below:
        c = (x1, y0) if y1 > y0 else (x0, y1)
    else:
        c = (x0, y1) if y1 > y0 else (x1, y0)
    return [(x0, y0), (x1, y1), c]


def obb_hits_slope(obb, o):
    """Separating-axis test of a turned box (from _obb) against slope o's solid triangle; touching
    counts."""
    if not o.slope_line():
        return True
    tri = slope_triangle(o)
    corners, axes = obb
    axes = list(axes)
    for (ax, ay), (bx, by) in zip(tri, tri[1:] + tri[:1]):
        axes.append((-(by - ay), bx - ax))
    for ax, ay in axes:
        p1 = [x * ax + y * ay for x, y in corners]
        p2 = [x * ax + y * ay for x, y in tri]
        if max(p1) < min(p2) or max(p2) < min(p1):
            return False
    return True


def r3(v):
    """Round to 0.001 with halves up, as GD's yVel (0.4865 -> 0.487, -3.4225 -> -3.422)."""
    return math.floor(v * 1000 + 0.5 + 1e-7) / 1000


def _rotated_bounds(o):
    """Axis-aligned bounds of an object's box rotated about its centre."""
    import math
    x, y, w, h = o.rect
    a = math.radians(o.rotation)
    c, s = abs(math.cos(a)), abs(math.sin(a))
    bw, bh = w * c + h * s, w * s + h * c
    return (x + w / 2 - bw / 2, y + h / 2 - bh / 2, bw, bh)


class Unsupported(Exception):
    """The level or run needs a mechanic the simulator doesn't have yet."""


@dataclass
class Player:
    x: float = 0.0
    y: float = 105.0
    y_vel: float = 0.0
    speed: str = "1x"
    size: float = 1.0  # 1.0 or 0.6 (mini)
    mode: str = "cube"  # "cube", "ship", "ball", "ufo", "wave", "robot" or "spider"
    on_ground: bool = False
    upside_down: bool = False
    holding: bool = False
    buffered: bool = False        # a press that hasn't been used by a jump or an orb yet
    hold_blocked: bool = False    # after a spider orb: the held button is ignored until released
    doomed: str | None = None     # thrown onto a hazard by a spider orb/pad: dies on the next step
    doom_in: int = 1              # ... or after this many steps (thrown out of the level: 2)
    dashing: bool = False         # in a dash orb's dash: flies straight while the button is held
    dash_slope: float = 0.0       # the dash's y move per unit of x (a turned dash orb)
    dash_rot: float = 0.0         # the player's angle during the dash: the orb's
    rot_under: float = 0.0        # the angle the dash hides (it comes back when the dash ends)
    rot_dx: float = 0.0           # this step's move, for the angle
    rot_dy: float = 0.0
    area_bottom: float = C.GROUND_Y  # the wave's floor (set by the wave portal); ceiling 300 above
    area_height: float = C.WAVE_AREA_HEIGHT   # infinite after a Free Mode portal (no ceiling)
    dead: bool = False
    killer: str = ""              # what killed the player (for reports)
    steps: int = 0
    on_slope: bool = False         # standing on a slope (cube)
    slope_capped: bool = False     # already one step at the slope's top height
    slope_steps: int = 0           # ship: steps on the current slope (sets the launch speed)
    slope_dir: int = 0             # ship: +1 on a floor slope (solid below), -1 on a ceiling one
    slope_k: float = 0.0           # ship: the slope's gradient (screen, per x to the right)
    slope_launch: float | None = None   # ship: launch speed if it leaves (set on the slope)
    slope_xvel: float = 0.0        # ship: the x speed on its last step on the slope
    robot_boost: int = 0           # robot: steps its jump may still be held flat
    dual: bool = False             # in dual mode (a second player exists)
    player2: bool = False          # this is player 2
    rotation: float = 0.0          # degrees, clockwise (GD's); see _update_rotation
    spin: float = 1.0              # cube: spin direction (+1 / -1); ball: roll rate factor
    rot_yv: float = 0.0            # yVel and gravity at the last rotation update (spin changes)
    rot_up: bool = False
    snap_from: float | None = None # x before this step's landing snap
    used: set = field(default_factory=set)  # one-time objects already activated (by index)
    last_block: int | None = None  # index of the block last landed on (None after the floor)
    last_diff: float = 0.0         # player x - that block's x at the landing
    last_block_x: float = 0.0      # that block's x at the landing (a trigger may move it later)
    snap_dbg: dict | None = None   # the last landing's snap decision (for tools)
    snap_cand: dict | None = None  # SNAP_LOG: this step's landing that could snap (for tools)
    ship_clip: bool = False        # ship: the next step puts yVel at the cap (after a yellow orb / pad)
    y_moved: float = 0.0           # y after this step's move, before collisions

    @property
    def x_vel(self) -> float:
        return C.X_VEL[self.speed]

    @property
    def half(self) -> float:
        """Half the body box: what stands on the floor and on blocks."""
        if self.mode == "wave":
            return C.WAVE_BODY[self.size] / 2
        if self.mode == "spider":
            return C.PLAYER_SIZE[self.size] * C.SPIDER_SIZE_FACTOR / 2
        return C.PLAYER_SIZE[self.size] / 2

    @property
    def hit_half(self) -> float:
        """Half the hitbox that touches hazards, portals, pads and orbs."""
        if self.mode == "wave":
            return C.WAVE_HITBOX[self.size] / 2
        if self.mode == "spider":
            return C.PLAYER_SIZE[self.size] * C.SPIDER_SIZE_FACTOR / 2
        return C.PLAYER_SIZE[self.size] / 2

    @property
    def rect(self):
        h = self.hit_half
        return (self.x - h, self.y - h, 2 * h, 2 * h)

    def box(self, side: float):
        h = side / 2
        return (self.x - h, self.y - h, side, side)

    @property
    def body_rect(self):
        h = self.half
        return (self.x - h, self.y - h, 2 * h, 2 * h)

    @property
    def sign(self) -> float:
        """+1 with normal gravity, -1 upside down: yVel * sign is 'up' relative to gravity."""
        return -1.0 if self.upside_down else 1.0


class Sim:
    def __init__(self, level, start_speed: str = "1x"):
        self.level = level
        # Each simulator gets its own copy of the objects: triggers move and toggle them.
        self.objects = [dataclasses.replace(o) for o in level.objects if o.kind]
        # Legacy levels (fixNegativeScale off): an object scaled by a negative factor has a 0x0
        # hitbox at one corner (the trace's own orb rects, Lost Love) and a saw's radius is negative,
        # so it never kills (Aeternus: 3 saws passed 9.7-17 from the centre).
        self.neg_off = not self.level.settings.get("physics", {}).get("fixNegativeScale")             and os.environ.get("NEG_SCALE_ON") is None
        if self.neg_off:
            for o in self.objects:
                if o.neg and not o.radius:
                    o.x, o.y, o.w, o.h, o.ox, o.oy = o.neg[0], o.neg[1], 0.0, 0.0, 0.0, 0.0
        self.grid = Grid(self.objects)
        self.journal = None   # undo log for searches (sim/state.py), see log_obj
        # Searches only: every box that kills is this much bigger, so a route that survives by
        # less than this counts as a death (the game's exact edges are never relied on).
        self.margin = 0.0
        self.triggers = Triggers(self, level.triggers, level.anchors)
        self.player = Player(speed=start_speed)
        self.player2 = None    # player 2 while dual mode is on
        self.p2_hold_ok = True
        self.p2_spawn = None
        self.player.y = C.GROUND_Y + self.player.half

    def log_obj(self, i):
        """Record object i's changeable fields before a change. The undo log (when a search sets
        it) lets a saved point be restored without copying the level."""
        if self.journal is not None:
            o = self.objects[i]
            self.journal.append((0, i, o.x, o.y, o.moved_step, o.enabled, o.uncertain))

    # --- helpers ---

    def _near(self, x0, x1):
        for i in self.grid.near(x0, x1):
            o = self.objects[i]
            if o.enabled and not (o.neg and o.radius and self.neg_off):
                yield i, o

    def _solids(self, x0, x1):
        for i, o in self._near(x0, x1):
            if (o.kind == SOLID or o.kind == BREAKABLE) and not o.rotation % 360:
                yield i, o

    def _slopes(self, x0, x1):
        for i, o in self._near(x0, x1):
            if o.kind == SLOPE and not o.rotation % 360:
                line = o.slope_line()
                if line:
                    yield i, o, line

    def _check_uncertain(self, p):
        """Stop when the player reaches an object whose position or state isn't modelled."""
        h = max(p.half, p.hit_half) + 5
        box = (p.x - h, p.y - h, 2 * h, 2 * h)
        for _, o in self._near(box[0], box[0] + box[2]):
            if o.extra == "collision block":
                continue   # only collision triggers see these
            if o.uncertain and overlap(box, _rotated_bounds(o) if o.rotation % 360 else o.rect):
                raise Unsupported(f"{o.kind} {o.id} at x={o.x:.0f} y={o.y:.0f} is moved by "
                                  f"{o.uncertain}: not simulated")

    def _ship_accel(self, p, holding):
        """One step of ship thrust / gravity (see C.SHIP_*). Like the cube, the step uses the button
        as it was before this step's input."""
        if self.level.settings.get("physics", {}).get("fixGravityBug"):
            # fixed: the comparison is mirrored upside down (VOLTSTORM's mini ship, 73 steps;
            # its level settings aren't readable, so the flag itself isn't confirmed)
            falling = p.sign * p.y_vel < C.ship_falling_yvel(p.speed)
        else:
            t = C.ship_falling_yvel(p.speed)
            falling = p.y_vel > t if p.upside_down else p.y_vel < t
        k = C.SHIP_HOLD[0 if falling else 1] if holding else -C.SHIP_RELEASE[0 if falling else 1]
        m = C.SHIP_MINI if p.size != 1.0 else 1.0
        # caps on GD's 0.001 grid like yVel itself (mini 8 / 0.85 = 9.41176 -> 9.412)
        up, down = round(C.SHIP_CAP_UP * m, 3), round(C.SHIP_CAP_DOWN * m, 3)
        rel = p.sign * p.y_vel
        if p.ship_clip:
            # the step after a yellow orb / pad: put at the cap (16 -> 8), no thrust that step
            p.ship_clip = False
            if rel > up:
                p.y_vel = p.sign * up
                return
        if rel > up:      # faster than the caps (after an orb or pad): slows back, no thrust
            k = -C.SHIP_ABOVE_CAP[0 if holding else 1]
        elif rel < -down:
            k = C.SHIP_BELOW_CAP[0 if holding else 1]
        v = round(p.y_vel + p.sign * k * C.SHIP_G * m, 3)
        rel_new = p.sign * v
        # Within the caps, thrust / gravity can't push past them.
        if -down <= rel <= up:
            if holding and rel_new > up:
                v = p.sign * up
            elif not holding and rel_new < -down:
                v = -p.sign * down
        p.y_vel = round(v, 3)

    def _ufo_accel(self, p):
        """UFO: a press (from the previous step) sets the flap speed, then gravity as the ship's
        released gravity (0.6 / 0.4 of the base), capped at the fall cap."""
        if p.buffered and not p.hold_blocked:
            p.y_vel = p.sign * C.UFO_JUMP[p.size]
            p.buffered = False
            p.on_ground = False
        if self.level.settings.get("physics", {}).get("fixGravityBug"):
            falling = p.sign * p.y_vel < C.ship_falling_yvel(p.speed)
        else:
            t = C.ship_falling_yvel(p.speed)
            falling = p.y_vel > t if p.upside_down else p.y_vel < t
        m = C.SHIP_MINI if p.size != 1.0 else 1.0
        if p.ship_clip:
            p.ship_clip = False
            clip = round(C.UFO_YELLOW_CLIP * m, 3)      # mini 9.412, as the ship's cap
            if p.sign * p.y_vel > clip:
                p.y_vel = p.sign * clip
                return
        k = C.UFO_GRAVITY[0 if falling else 1]
        v = r3(p.y_vel - p.sign * k * C.SHIP_G * m)
        cap = C.UFO_FALL_CAP[p.size]
        if p.sign * v < -cap <= p.sign * p.y_vel:
            v = -p.sign * cap       # only reaching it: past it (a black orb's -11.2) it keeps falling
        p.y_vel = v

    @staticmethod
    def _banded(p):
        """Held between the band's floor and ceiling (300 high, from the last ship/UFO/spider/wave
        or dual portal). Not the cube or ball in dual: holding them in the band too lost 5,000
        matched steps (Night Rider 2, part 11), though a dual ball in Tartarus stands right under
        the dual portal's band ceiling (540, 510)."""
        return p.mode in ("ship", "ufo", "spider")

    def _in_dblock(self, p):
        """Is the player's box touching a D block (id 1755)? The wave then doesn't die on solids."""
        r = p.rect
        for _, o in self._near(r[0] - 30, r[0] + r[2] + 30):
            if o.id == 1755 and overlap(r, o.rect):
                return True
        return False

    def _on_floor_line(self, p):
        """Standing on the floor (the ground or the band's floor), not on a block."""
        floor = (p.area_bottom if self._banded(p) or p.mode == "wave" else C.GROUND_Y) + p.half
        return abs(p.y - floor) < EPS   # (checked after a flip too)

    def _jump_value(self, p) -> float:
        jump = C.CUBE_JUMP.get(p.speed)
        if jump is None:
            raise Unsupported(f"cube jump at {p.speed} not measured")
        return jump * C.MINI_JUMP_FACTOR if p.size != 1.0 else jump

    def _jump(self, p):
        """Cube: jump. Ball: switch gravity and leave the surface at 0.3 x the jump value."""
        if p.mode == "ball":
            jump = self._jump_value(p)
            if p.on_slope and p.slope_k and (p.slope_k > 0) == (p.slope_dir > 0):
                # On a slope carrying it up, the jump value gains a quarter of the ship's full slope
                # launch, rounded to 0.001, before the switch factor (~70 switches: 1x-3x, normal
                # and mini, 1:2 / 45 / 2:1 exact, e.g. (8.984 + 2.086) x 0.3 = 3.321; not by the
                # time on the slope); on a falling slope it's the flat value.
                L = C.SHIP_SLOPE_LAUNCH.get(abs(round(p.slope_k, 6)))
                if L is None:
                    raise Unsupported(f"ball switch on a slope of gradient {p.slope_k:g}: not measured")
                jump = round(jump + C.BALL_SLOPE_SWITCH * L * p.x_vel, 3)
            v = jump * C.BALL_SWITCH_FACTOR
            p.on_slope = p.slope_capped = False
            p.slope_steps = 0
            p.upside_down = not p.upside_down
            p.y_vel = -p.sign * v
        else:
            p.y_vel = p.sign * self._jump_value(p)
        p.on_ground = False
        p.buffered = False

    @staticmethod
    def _flip(p):
        """Gravity change by a portal or dash orb: yVel is halved."""
        p.upside_down = not p.upside_down
        p.y_vel *= C.GRAVITY_FLIP_YVEL_FACTOR
        p.on_ground = False

    def _supported(self, p, x=None) -> bool:
        """Is there a surface exactly under the player (in the direction of gravity)? GD checks it
        with this step's x already moved: the cube drops on the first step its back edge has passed
        the block's end (17 cases: cube, ball, mini, 0.5x-2x)."""
        x = p.x if x is None else x
        if p.mode == "ship":
            if not p.upside_down and p.y <= p.area_bottom + p.half:
                return True
            if p.upside_down and p.y >= p.area_bottom + p.area_height - p.half:
                return True
        elif not p.upside_down and p.y <= C.GROUND_Y + p.half:
            return True
        if p.mode == "wave":   # the wave slides only on the floor; blocks kill it
            return False
        left, right = x - p.half, x + p.half
        foot = p.y - p.sign * p.half
        for _, o in self._solids(left, right):
            ox, oy, ow, oh = o.rect
            # touching counts: the back edge exactly at the block's end still stands (Every End 2
            # x 40215.0 on a block ending at 40200.0, solver macro)
            if left <= ox + ow and ox <= right:
                surface = oy + oh if not p.upside_down else oy
                if abs(surface - foot) < EPS:
                    return True
        return False

    def _track_standing_block(self, p):
        """While standing, the snap's reference is the block under the cube (the first in level
        order) and where the cube is on it, refreshed every step: so the jump's take-off spot.
        (Every End 2: 95,282 -> 97,483 matched steps over the landing-time reference.)"""
        foot = p.y - p.sign * p.half
        left, right = p.x - p.half, p.x + p.half
        under = None
        for i, o in self._solids(left, right):
            ox, oy, ow, oh = o.rect
            if left < ox + ow and ox < right and abs((oy + oh if not p.upside_down else oy) - foot) < EPS:
                if under is None or _key(o, p) < _key(under[1], p):
                    under = (i, o)
        if under:
            i, o = under
            p.last_block, p.last_diff, p.last_block_x = i, p.x - o.x, o.x

    def _snaps(self, p, i) -> bool:
        """GD only snaps between certain block layouts (distance from the previous block to this one,
        per speed). Measured at 1x and 2x (957 landings, see NOTES); at 0.5x, 3x and 4x it never
        snapped (846 landings over 27 traces)."""
        last, new = self.objects[p.last_block], self.objects[i]
        if last.kind == BREAKABLE:
            return False   # never from a breakable block (Every End 2: 9 landings); onto one it does
        pats = C.SNAP_PATTERNS.get(p.speed, ())
        return (round(new.x - last.x), round((new.y - last.y) * p.sign)) in pats

    def _hazard_rect(self, p):
        """The box hazards touch: the body box, but smaller for the wave (plus the search margin)."""
        m = self.margin
        if p.mode != "wave":
            r = p.body_rect
            return (r[0] - m, r[1] - m, r[2] + 2 * m, r[3] + 2 * m) if m else r
        return p.box(C.WAVE_HAZARD_BOX[p.size] + 2 * m)

    def _slope_support(self, p):
        """Where a slope holds the cube: its centre sits half its size from the slope line, at right
        angles to it (y = line(x) +- half x sqrt(1 + k^2)), but no further than half its size past
        the slope's top (the cap). Measured exact on 45 deg, 2:1 and 1:2 slopes, both gravities.
        Returns (y, capped, index) for the slope holding the cube highest, or None."""
        import math
        h, up = p.half, p.upside_down
        best = None
        for i, o, ((x0, y0), (x1, y1), below) in self._slopes(p.x - h, p.x + h):
            if below == up:     # its solid part must be on the gravity side
                continue
            if not (p.x - h < x1 and x0 < p.x + h):
                continue
            if not (min(y0, y1) - h - 40 < p.y < max(y0, y1) + h + 40):
                continue
            k = (y1 - y0) / (x1 - x0)
            top_left = (y0 > y1) != up          # the slope's top end (its cap) is its left end
            if top_left and p.x < x0 and os.environ.get("NO_SLOPE_AHEAD") is None:
                # a slope falling away ahead (a peak): it doesn't hold the player before its centre
                # gets there (Hallucination, a mini ball over a 2:1 peak)
                continue
            on_line = y0 + k * (p.x - x0) + (-1 if up else 1) * h * math.sqrt(1 + k * k)
            cap = (min(y0, y1) - h) if up else (max(y0, y1) + h)
            capped = (on_line <= cap) if up else (on_line >= cap)
            s = cap if capped else on_line
            if best is None or p.sign * (s - best[0]) > 0:
                best = (s, capped, i)
        return best

    def _collide_slopes(self, p):
        """Cube, ball and UFO on slopes (the ball and the UFO sit where the cube does: ~4,600 steps
        in the traces). Returns True when a slope decided the player's height this step."""
        if p.mode != "cube" and p.on_slope and p.sign * p.y_vel > 0:
            # kicked off it (a UFO jump, an orb, a pad)
            p.on_slope = p.slope_capped = False
            p.slope_steps = 0
            return False
        if p.mode == "ball" and os.environ.get("NO_BALL_PUSH") is None:
            # A slope on the side away from gravity (a ceiling slope over a ball falling down) that
            # comes at the ball faster than it moves pushes it along its line; yVel goes on
            # building up (DoubleDash: switched under a falling ceiling it rode the line, -3.45,
            # -3.58, ...), like the ship's other-side slopes.
            for y, _, i, side, k, lo, hi in self._ship_supports(p):
                if side != p.sign and side * (p.y - y) < -EPS and not p.on_ground:
                    p.y = f32(y)
        sl = self._slope_support(p)
        if sl is None:
            if p.on_slope and p.mode != "cube":
                self._leave_slope(p)
            p.on_slope = p.slope_capped = False
            return False
        s, capped, i = sl
        floor = C.GROUND_Y + p.half
        if not p.upside_down and s <= floor:
            p.on_slope = p.slope_capped = False
            return False          # the floor holds the cube higher
        below = p.sign * (p.y - s) < -EPS       # the cube is inside the slope
        if below and not p.on_slope and not overlap(p.body_rect, self.objects[i].rect):
            # under the line but not touching the slope at all: it's beside or past it (Tartarus
            # 14158: a cube falling 40 under a slope's bottom was put on top of it)
            return False
        if capped and not p.on_slope:
            # A falling cube passes through the top height while its centre is still over the
            # slope, and lands on it once the centre is past the top corner (seen once).
            (x0, y0), (x1, y1), _ = self.objects[i].slope_line()
            top_x = x1 if (y1 > y0) != p.upside_down else x0
            if (p.x < top_x) if top_x == x1 else (p.x > top_x):
                p.slope_capped = False
                return False
        if p.on_slope or (below and (p.on_ground or p.sign * p.y_vel <= 0)):
            if capped and p.on_slope and p.slope_capped:
                # The second step at the top height leaves the slope (all 4 cases measured); the
                # cube's launch speed grows with the time spent on the slope and isn't worked out
                # yet. The ball and the UFO take the ship's launch (70 of ~100 cases exact).
                if p.mode == "cube":
                    raise Unsupported(f"leaving the top of slope {self.objects[i].id} at "
                                      f"x={self.objects[i].x}: launch speed not measured")
                if p.mode == "ball":
                    # that step still moves with one step of gravity (Hallucination: 291 -> 291.029
                    # upside down), then the launch
                    p.y = f32(p.y - p.sign * round(C.BALL_GRAVITY, 3) * C.Y_STEP)
                self._leave_slope(p)
                return False
            if not p.on_slope:
                p.slope_steps = 0
            p.y = f32(s)
            p.y_vel, p.on_ground = 0.0, True
            p.on_slope, p.slope_capped = True, capped
            (x0, y0), (x1, y1), _ = self.objects[i].slope_line()
            k = (y1 - y0) / (x1 - x0)
            p.slope_steps += 1
            p.slope_dir, p.slope_k = p.sign, k
            c = C.SHIP_SLOPE_LAUNCH.get(abs(round(k, 6)))
            f = min(max(p.slope_steps / C.SLOPE_RAMP_STEPS, C.SLOPE_LAUNCH_MIN), 1.0)
            p.slope_launch = None if c is None else round(c * p.x_vel * f, 3)
            p.last_block = None
            return True
        if below:
            raise Unsupported(f"hitting slope {self.objects[i].id} at x={self.objects[i].x} "
                              f"from its open side while rising: not measured")
        return False

    def _leave_slope(self, p):
        """Ball / UFO off a slope: where the slope carries it off (a rising floor's top, a falling
        ceiling's bottom upside down) it launches as the ship does; otherwise it just falls."""
        k, side = p.slope_k, p.slope_dir
        if k and (k > 0) == (side > 0):
            if p.slope_launch is None:
                raise Unsupported(f"{p.mode} leaving a slope of gradient {k:g}: launch not measured")
            p.y_vel = side * max(side * p.y_vel, p.slope_launch)
        p.on_slope = p.slope_capped = False
        p.slope_steps = 0
        p.on_ground = False

    def _ship_supports(self, p):
        """Every slope whose sloped face the ship is at: (y, launch_cap, index, side, k).
        side +1 = solid below the line (the ship rests above it), -1 = solid above. y as for the
        cube - half its size from the line at right angles - capped at half the ship past the far
        corner. launch_cap: held at the end the slope carries
        the ship off (a rising floor's top, a falling ceiling's bottom). A ship past the flat leg,
        or beside the tall end below its top, isn't at the sloped face (see _ship_slope_blocks)."""
        h = p.half
        out = []
        for i, o, ((x0, y0), (x1, y1), below) in self._slopes(p.x - h, p.x + h):
            if not (p.x - h < x1 and x0 < p.x + h):
                continue
            lo, hi = min(y0, y1), max(y0, y1)
            side = 1 if below else -1
            if (side > 0 and p.y <= lo) or (side < 0 and p.y >= hi):
                continue                     # on the flat leg's side: a block face
            k = (y1 - y0) / (x1 - x0)
            on_line = y0 + k * (p.x - x0) + side * h * math.sqrt(1 + k * k)
            top = (hi + h) if side > 0 else (lo - h)      # the far corner's height
            tall_x = x1 if (y1 > y0) == (side > 0) else x0   # the end at the far corner
            past_tall = p.x > x1 if tall_x == x1 else p.x < x0
            launch_end = (k > 0) == (side > 0)               # the tall end carries the ship off
            if past_tall and not launch_end:
                continue     # past a tall end that doesn't launch: the slope acts as a block there
            if past_tall and side * (p.y - top) < -EPS:
                continue                     # beside the tall end, below its corner
            capped = side * (on_line - top) >= 0
            if capped and not launch_end:
                continue     # over a falling floor's top (rising ceiling's bottom): no hold, it drops off
            y = top if capped else on_line
            launch_cap = capped and launch_end
            out.append((y, launch_cap, i, side, k, lo, hi))
        return out

    def _ship_slope_blocks(self, p, x0, x1):
        """Slopes the ship meets from a flat leg's side, or past a tall end that doesn't launch
        (a falling floor's top, a rising ceiling's bottom): they act as blocks (their box)."""
        for i, o, ((sx0, sy0), (sx1, sy1), below) in self._slopes(x0, x1):
            lo, hi = min(sy0, sy1), max(sy0, sy1)
            k = (sy1 - sy0) / (sx1 - sx0)
            if (below and p.y <= lo) or (not below and p.y >= hi):
                yield i, o
            elif (k > 0) != below and (p.x > sx1 if (sy1 > sy0) == below else p.x < sx0):
                yield i, o

    def _ship_slopes(self, p, prev_y):
        """The ship on slopes (measured, see NOTES). Returns True when a slope set its height."""
        best = None
        for s, launch_cap, i, side, k, lo, hi in self._ship_supports(p):
            gap = side * (p.y - s)        # > 0: outside (clear of it), < 0: inside
            thrust_in = (p.sign if (p.holding and not p.hold_blocked) else -p.sign) != side
            if p.on_slope and side == p.slope_dir:
                # Riding it: with the thrust into it the ship sticks, also to a slope moving away
                # faster than it would follow (down a falling floor, up a rising ceiling), unless
                # it's moving away itself; otherwise it leaves once it's outside (outrunning the
                # slope, past its corner).
                touch = gap <= EPS or (thrust_in and not launch_cap and side * p.y_vel <= 0)
            elif launch_cap:
                touch = gap <= EPS        # a corner it was just carried off doesn't catch it again
            else:
                # A new contact: GD catches the ship up to 1 unit outside a surface that isn't
                # coming at it (a rising floor under a falling ship 0.63 above wasn't caught);
                # inside, however deep (5.9 at a thin end was caught).
                # Only while the ship closes in on it faster than the surface moves away (a ship
                # falling 0.09 a step just above a floor dropping 1.3 a step isn't caught).
                coming = side * k * (1 if not launch_cap else 0) > 0
                closing = -side * p.y_vel * C.Y_STEP - abs(k) * p.x_vel * C.X_STEP
                touch = gap <= (C.SHIP_SLOPE_SNAP if not coming and closing > 0 else 0.0)
            if not touch:
                continue
            if best is None or side * (s - best[0]) > 0:
                best = (s, launch_cap, i, side, k, lo, hi)
        # A ship riding its gravity-side slope comes off on the step its x speed changes (a speed
        # portal: 5 of 5, launched at the old speed); on the other side it rides on (7 of 7).
        speed_off = p.on_slope and p.slope_dir == p.sign and p.x_vel != p.slope_xvel
        if best is None or (best[1] and p.on_slope and p.slope_capped) or speed_off:
            if p.on_slope:
                self._ship_leave_slope(p)
            return False
        s, launch_cap, i, side, k, lo, hi = best
        if p.on_slope and (k > 0) != (side > 0):
            for edge in (lo, hi):
                # On a slope that falls away (a falling floor, a rising ceiling), the step the
                # support crosses the slope box's top or bottom puts the ship exactly on it, then
                # it goes on (15 cases, normal and mini; never on rising floors or falling
                # ceilings; once not, at a crossing of 0.002).
                if (prev_y - edge) * (s - edge) < 0:
                    s = edge
        if not p.on_slope:
            p.slope_steps = 0
        thrust = p.sign if (p.holding and not p.hold_blocked) else -p.sign   # screen direction
        rel = side * p.y_vel                      # speed away from the slope
        floor = p.area_bottom + p.half
        if side < 0 and p.y <= floor and p.sign > 0:
            # pressed into the ground by a slope above: the floor zeroes yVel first (a mini ship
            # pushed down through the ground kept yVel -2.0 exactly)
            rel = max(rel, 0.0)
        gravity_side = side == p.sign
        if thrust == side:
            p.y_vel = side * max(rel, C.SHIP_SLOPE_AWAY_YVEL)
            p.on_ground = False
        elif rel <= 0 or (gravity_side and rel * C.Y_STEP < abs(k) * p.x_vel * C.X_STEP):
            # Thrust into it: yVel 0, except for a ship already moving away - on the other side
            # it keeps its speed; on the gravity side only if it outpaces the slope (1.85 a step
            # against 1.30 kept; 0.45 against 1.95 and 0.81 against 0.98 became 0).
            p.y_vel = 0.0
            p.on_ground = gravity_side
        p.y = f32(s)
        p.on_slope, p.slope_capped = True, launch_cap
        p.slope_steps += 1
        p.slope_dir, p.slope_k = side, k
        # The launch is worked out on the step on the slope, with that step's speed: a ship
        # leaving on the first step after a speed portal launches at the old speed (8.342 at 1x).
        c = C.SHIP_SLOPE_LAUNCH.get(abs(round(k, 6)))
        f = min(max(p.slope_steps / C.SLOPE_RAMP_STEPS, C.SLOPE_LAUNCH_MIN), 1.0)
        p.slope_launch = None if c is None else round(c * p.x_vel * f, 3)
        p.slope_xvel = p.x_vel
        p.last_block = None
        return True

    def _ship_leave_slope(self, p):
        """Off a slope: where the slope keeps moving the ship's way, it launches the ship."""
        k, side = p.slope_k, p.slope_dir
        if (k > 0) == (side > 0) and k:
            if p.slope_launch is None:
                raise Unsupported(f"ship leaving a slope of gradient {k:g}: launch not measured")
            p.y_vel = side * max(side * p.y_vel, p.slope_launch)
        p.on_slope = p.slope_capped = False
        p.slope_steps = 0
        p.on_ground = False

    def _collide_solids(self, p, prev_y, was_airborne):
        """Landing on the floor or on a block's top (its underside when upside down)."""
        if p.mode in ("cube", "ball") and self._collide_slopes(p):
            return
        # The UFO on slopes is the ship: the held button counts as thrust (riding a rising floor
        # held, yVel reads 2.0; under a slope it is pushed), the same launch (DoubleDash, josh)
        if p.mode in ("ship", "ufo") and self._ship_slopes(p, prev_y):
            return
        ship = p.mode in ("ship", "ufo")    # flies: stops under blocks, no snap
        if p.mode == "ship" and p.y < C.GROUND_Y and not p.upside_down:
            # a slope pushed it into the ground and let go: dies (mini, centre 9 under the ground)
            p.dead, p.killer = True, "pushed into the ground by a slope"
            return
        if self._banded(p):
            # The band (ship, UFO, spider): it stops at its floor and
            # ceiling (standing on the one gravity points to), then blocks as below.
            lo = p.area_bottom + p.half
            hi = p.area_bottom + p.area_height - p.half
            if p.y <= lo or p.y >= hi:
                standing = (p.y <= lo) != p.upside_down
                p.y = f32(lo if p.y <= lo else hi)
                p.y_vel = 0.0
                if standing:   # the side gravity points to sets the (sticky) flag at once
                    p.on_ground = True
                    p.last_block = None
                    return

        floor = (p.area_bottom if self._banded(p) or p.mode == "wave" else C.GROUND_Y) + p.half
        if not ship and (not p.upside_down or p.mode == "wave") and p.y <= floor:   # the wave: either gravity
            # The wave's yVel becomes 0 only when the move went past the floor; landing exactly on
            # it keeps the yVel for that step (it is 0 from the next one).
            if p.mode != "wave" or p.y < floor:
                p.y_vel = 0.0
            p.y = floor
            if not p.upside_down:   # an upside-down wave on the floor isn't on the ground (BOTS)
                p.on_ground = True
            p.last_block = None
            return
        if p.mode == "wave":
            ceiling = p.area_bottom + p.area_height - p.half
            if p.y >= ceiling:
                if p.y > ceiling:
                    p.y_vel = 0.0
                p.y = ceiling
                return
            # Touching a D block, the wave doesn't die on solids: met from straight above or below,
            # it slides along a block face with its 10x10 box (mini 6x6), yVel 0, like on the band's
            # edges (AKIRA: a mini wave in D blocks rising into block undersides at y 690 stood at
            # 687 for 16 steps, ground flag set). Without one any block contact kills (below).
            if self._in_dblock(p):
                half = C.WAVE_HAZARD_BOX[p.size] / 2
                hb = p.box(C.WAVE_HAZARD_BOX[p.size])
                face = None
                for _, o in self._solids(hb[0], hb[0] + hb[2]):
                    if not overlap(hb, o.rect):
                        continue
                    ox, oy, ow, oh = o.rect
                    if p.y > prev_y and prev_y + half <= oy + EPS:
                        f = oy - half
                    elif p.y < prev_y and prev_y - half >= oy + oh - EPS:
                        f = oy + oh + half
                    else:
                        continue
                    if face is None or abs(f - prev_y) < abs(face - prev_y):
                        face = f
                if face is not None:
                    p.y = f32(face)
                    p.y_vel = 0.0
                    p.on_ground = True
            # Any contact of the wave's block box (7.2x7.2 at both sizes) with a block kills it,
            # from any side. D blocks: not tested.
            if self._in_dblock(p):
                return   # (D block: side contacts not measured)
            br = p.box(C.WAVE_BLOCK_BOX[p.size] + 2 * self.margin)
            for _, o in self._solids(br[0], br[0] + br[2]):
                if overlap(br, o.rect):
                    p.dead, p.killer = True, f"block {o.id} at x={o.x} y={o.y}"
                    return
            return
        r = p.body_rect
        best = None
        ceiling = None
        side_kill = None
        blocks = self._solids(r[0], r[0] + r[2])
        if ship:
            import itertools
            blocks = itertools.chain(blocks, self._ship_slope_blocks(p, r[0], r[0] + r[2]))
        for i, o in blocks:
            if not overlap(r, o.rect):
                continue
            ox, oy, ow, oh = o.rect
            surface = oy + oh if not p.upside_down else oy
            coming_down = p.sign * p.y_vel <= 0
            # A falling cube is caught by any block its outer box overlaps whose top is below the
            # cube's centre, even from several units below that top (Every End 2: from 7.6 below).
            above = p.sign * (p.y - surface) > C.LAND_MIN_ABOVE
            if not (coming_down and above):
                face = oy if not p.upside_down else oy + oh     # the side facing the cube's head
                # The ship stops under a block's underside (head side) instead of passing in:
                # rising with its centre more than LAND_MIN_ABOVE below that side.
                head_hit = (ship or p.mode in ("robot", "spider")) and p.sign * p.y_vel >= 0 and p.sign * (face - p.y) > C.LAND_MIN_ABOVE
                if p.sign * (face - p.y) > 0 and (o.moved_step == p.steps or head_hit):
                    # A block moving into the cube from its head side pushes it out (Every End 2:
                    # a slab moving down carried the cube at its speed, yVel kept). A static
                    # block's underside doesn't: a rising cube passes into it.
                    push = face - p.sign * p.half
                    if ceiling is None or p.sign * (push - ceiling) < 0:
                        ceiling = push
                    continue
                # Side: the outer box may overlap a block freely; the player dies when the small
                # inner box touches one.
                # (a slope's side kills a mini ship with the normal-size box: 2 of 2 deaths)
                iw, ih = C.INNER_BOX[1.0 if o.kind == SLOPE else p.size]
                iw, ih = iw + 2 * self.margin, ih + 2 * self.margin
                if touches_rounded((p.x - iw / 2, p.y - ih / 2, iw, ih), o.rect, 0.0):
                    if o.kind == BREAKABLE:
                        self.log_obj(i)
                        o.enabled = False   # breaks instead of killing (provisional)
                        continue
                    killer = f"block {o.id} at x={o.x:.0f} y={o.y:.0f} (inner box)"
                    if ship:
                        # the ship's death step still shows the block contacts resolved (it
                        # stood under a slope's flat bottom while dying at its side)
                        side_kill = side_kill or killer
                        continue
                    p.dead, p.killer = True, killer
                    return
                continue
            if best is None or p.sign * (surface - best[2]) > 0                     or (abs(surface - best[2]) < EPS and _lkey(o, p) < _lkey(best[1], p)):
                best = (i, o, surface)   # the highest; between equals the back-most
        if ceiling is not None and best is None:
            p.y = f32(ceiling)
            if ship or p.mode in ("robot", "spider"):
                p.y_vel = 0.0
        if side_kill and best is None:
            p.dead, p.killer = True, side_kill
            return
        if best is None:
            return
        i, o, surface = best
        p.y = f32(surface + p.sign * p.half)
        p.y_vel, p.on_ground = 0.0, True
        if was_airborne and p.last_block is not None:
            lb_ = self.objects[p.last_block]
            p.snap_dbg = dict(ref=(lb_.id, lb_.x, lb_.y, lb_.order), new=(o.id, o.x, o.y, o.order), same=p.last_block == i,
                              moved=lb_.x != p.last_block_x, eligible=p.last_block != i and self._snaps(p, i),
                              need=p.last_diff + o.x - p.x, layout=(round(o.x - lb_.x, 2), round((o.y - lb_.y) * p.sign, 2)))
        if os.environ.get("SNAP_LOG") and was_airborne and p.last_block is not None and p.last_block != i and not ship                 and p.mode != "spider" and self.objects[p.last_block].x == p.last_block_x:
            lb_ = self.objects[p.last_block]
            pr_ = p.last_diff + o.x; sh_ = C.SNAP_SHIFT[p.speed]; d_ = pr_ - p.x
            p.snap_cand = dict(speed=p.speed, layout=(round(o.x - lb_.x, 2), round((o.y - lb_.y) * p.sign, 2)),
                               ids=(lb_.id, o.id), brk=lb_.kind == BREAKABLE, x0=p.x,
                               x1=f32(pr_ if abs(d_) <= sh_ else p.x + (sh_ if d_ > 0 else -sh_)), ox=o.x)
        if was_airborne and p.last_block is not None and p.last_block != i and not ship and p.mode != "spider"                 and self.objects[p.last_block].x == p.last_block_x and self._snaps(p, i):
            # (no snap when the previous block has moved since: seen in Every End 2, provisional)
            # Snap: GD predicts x from where the player stood on the previous block and moves the
            # player toward that spot by at most 1 unit (0.5x, 1x, 4x) or 2 (2x, 3x).
            predicted = p.last_diff + o.x
            shift = C.SNAP_SHIFT[p.speed]
            d = predicted - p.x
            p.snap_from = p.x    # undone if a pad launches it on this step (see _pad)
            p.x = f32(predicted if abs(d) <= shift else p.x + (shift if d > 0 else -shift))
        if was_airborne or p.last_block != i:
            p.last_block, p.last_diff, p.last_block_x = i, p.x - o.x, o.x
        if side_kill:
            p.dead, p.killer = True, side_kill

    # --- one physics step ---

    def step(self, holding: bool | None = None, holding2: bool | None = None) -> Player:
        """One physics step: player 1, then player 2 while dual mode is on (its own portals and
        orbs; its death ends the run). The same input drives both, or in a 2-player level
        `holding2` (the P2 key) drives player 2."""
        two = bool(self.level.settings.get("two_player"))
        p = self._step(self.player, holding, True)
        q = self.player2
        if q is not None:
            if not p.dual or p.dead:
                self.player2 = None
            else:
                q.speed = p.speed      # speed is shared: a speed portal sets it for both players
                # Player 2 appears with the button up: a hold carried over from before the dual
                # portal doesn't reach it until a new press (889 steps in Night Rider 2).
                h2 = holding2 if two else holding
                if h2 is not None:
                    if not h2:
                        self.p2_hold_ok = True
                    h2 = h2 and self.p2_hold_ok
                self.player = q
                try:
                    self._step(q, h2, False)
                finally:
                    self.player = p
                p.speed = q.speed
                if q.dead and not p.dead:
                    p.dead, p.killer = True, f"player 2: {q.killer}"
        if p.dual and self.player2 is None and self.p2_spawn is not None:
            self.player2, self.p2_spawn = self.p2_spawn, None
            self.player2.speed = p.speed   # with the speed portals touched later in that step
        return p

    def _update_rotation(self, p, dx, dy):
        """The player's angle after this step's move and landing (GD logs it after the step; the
        turned box uses it in the same step's collisions)."""
        m = p.mode
        g = -1.0 if p.upside_down else 1.0
        p.rot_dx, p.rot_dy = dx, dy
        if p.dashing:
            # During a dash the player shows the orb's angle (AKIRA: -70 / -24 / 0 in UFO and cube
            # mode); the cube's own angle goes on underneath and comes back when the dash ends.
            if m in ("cube", "ball"):
                shown, p.rotation = p.rotation, p.rot_under
                self._update_rotation_mode(p, dx, dy, g)
                p.rot_under, p.rotation = p.rotation, p.dash_rot
            else:
                p.rotation = p.dash_rot
            p.rot_yv, p.rot_up = p.y_vel, p.upside_down
            return
        self._update_rotation_mode(p, dx, dy, g)
        p.rot_yv, p.rot_up = p.y_vel, p.upside_down

    def _end_dash(self, p):
        """The dash ends (release, a pad): the angle it hid comes back in the same step; flying modes
        turn on from the dash angle with this step's (still dashing) move (AKIRA, UFO: -70 -> -68.285)."""
        if not p.dashing:
            return
        p.dashing = False
        if p.mode in ("cube", "ball"):
            p.rotation = p.rot_under
        else:
            self._update_rotation_mode(p, p.rot_dx, p.rot_dy, -1.0 if p.upside_down else 1.0)

    def _update_rotation_mode(self, p, dx, dy, g):
        m = p.mode
        if m == "cube":
            if p.on_ground:
                t = round(p.rotation / 90) * 90
                p.rotation = t - (t - p.rotation) * (1 - C.CUBE_SETTLE * C.SPEED_VALUE[p.speed])
                p.spin = g
            else:
                # the spin turns with a kick to yVel (jump, orb, pad: the sign of the new yVel), not
                # with a gravity portal (yVel just halved); 98.9 % of airborne cube steps
                if p.upside_down != p.rot_up:
                    kick = abs(p.y_vel - p.rot_yv / 2) > 0.5 and abs(p.y_vel - p.rot_yv) > 0.5
                else:
                    kick = abs(p.y_vel - p.rot_yv) > 0.5
                if kick:
                    p.spin = 1.0 if p.y_vel > 0 else -1.0
                p.rotation += (1.0 if p.spin >= 0 else -1.0) * C.CUBE_SPIN[p.size]
        elif m == "ball":
            base = C.BALL_ROLL * p.x_vel * (1.25 if p.size != 1.0 else 1.0)
            if p.on_ground:
                p.spin = g
            elif p.upside_down != p.rot_up:
                p.spin = -C.BALL_AIR_SWITCH * g
            p.rotation += p.spin * base
        elif m in ("ship", "wave") and dx > 0:
            target = -math.degrees(math.atan2(dy, dx))
            d = (target - p.rotation + 180.0) % 360.0 - 180.0
            k = C.SHIP_TURN if m == "ship" else C.WAVE_TURN[p.size]
            p.rotation += d * k
        elif m == "ufo" and dx > 0:
            # the UFO tilts the other way from the ship, by 0.4 of its direction, at most 0.1 rad
            # toward the ground (AKIRA: 20,000 steps)
            target = C.UFO_TILT * math.degrees(math.atan2(dy, dx))
            if target * g < -C.UFO_FALL_TILT:
                target = -C.UFO_FALL_TILT * g
            d = (target - p.rotation + 180.0) % 360.0 - 180.0
            p.rotation += d * C.UFO_TURN
        # the robot and the spider don't turn

    def _turned_box(self, box, deg):
        """Corners and axes of `box` (x, y, w, h) turned clockwise by `deg` about its centre."""
        x, y, w, h = box
        return _obb(x + w / 2, y + h / 2, w, h, deg)

    def _spawn_player2(self, p):
        """Dual portal (Night Rider 2, ChopStep 2, Aurorae 2: 20 entries): player 2 appears as player
        1's mirror at that step - same x, mode, size and speed, opposite gravity and yVel, at player
        1's height after the move but before landing (on the ground: 0.0486 lower, yVel +0.216)."""
        q = dataclasses.replace(p, used=set(p.used))
        q.y = p.y_moved
        q.y_vel = -p.y_vel
        q.upside_down = not p.upside_down
        q.on_ground = False
        q.on_slope = q.slope_capped = False
        q.last_block = None
        q.robot_boost = 0
        q.dead, q.killer = False, None
        q.player2 = True
        q.holding = q.buffered = False
        self.p2_hold_ok = not p.holding
        self.p2_spawn = q

    def _step(self, p, holding, primary) -> Player:
        p.steps += 1
        if p.steps == 1:
            if holding is not None:
                p.holding = holding
            return p

        # In wave mode GD's on-ground flag stays set after the floor is first touched, in the air
        # too (it only feeds the trace); whether the wave slides is decided by the floor itself.
        # A held jump on the ground goes before the support check: a cube that landed with its
        # back edge barely on a block still jumps on the next step (Every End 2, 4 times).
        jumping = p.on_ground and p.mode == "cube" and p.holding and not p.hold_blocked             and not p.dashing and not p.on_slope
        # The ship's on-ground flag is sticky like the wave's: set by any touch (floor, ceiling, a
        # block's top or underside), kept while flying, cleared only by a pad or an orb.
        if p.on_ground and p.mode not in ("wave", "ship") and not p.on_slope and not jumping                 and not self._supported(p, f32(p.x + p.x_vel * C.X_STEP)):
            p.on_ground = False
        was_airborne = not p.on_ground
        move_v = None
        if p.mode == "wave":
            # Held = up (relative to gravity). Standing on the floor without holding: no movement.
            on_floor = p.y <= p.area_bottom + p.half
            on_ceiling = p.y >= p.area_bottom + p.area_height - p.half
            d = p.sign if p.holding else -p.sign   # +1 = up on screen
            if (on_floor and d < 0) or (on_ceiling and d > 0):
                p.y_vel, move_v = 0.0, 0.0
            else:
                # The trace shows yVel rounded to 3 decimals; the move uses the exact xVel.
                p.y_vel, move_v = d * round(p.x_vel, 3), d * p.x_vel
        elif p.dashing:
            # a dash flies straight in every mode (the user: dash orbs work the same), along the
            # orb's angle (AKIRA: a 290 deg orb, y +6.5939 per 2.4 of x; yVel reads 0)
            p.y_vel = 0.0
        elif p.mode == "ship":
            self._ship_accel(p, p.holding and not p.hold_blocked)
        elif p.mode == "ufo":
            self._ufo_accel(p)
        elif p.mode == "robot":
            if p.on_ground and p.holding and not p.hold_blocked:
                p.y_vel = p.sign * self._jump_value(p) * C.ROBOT_JUMP_FACTOR
                p.robot_boost, p.on_ground, p.buffered = C.ROBOT_BOOST_STEPS, False, False
            elif not p.on_ground:
                if p.holding and p.robot_boost > 0:
                    p.robot_boost -= 1          # the jump held flat
                else:
                    p.robot_boost = 0
                    p.y_vel = r3(p.y_vel - p.sign * C.ROBOT_GRAVITY[p.speed])
                    if p.sign * p.y_vel < -C.CUBE_MAX_FALL:
                        p.y_vel = -p.sign * C.CUBE_MAX_FALL
        elif p.mode == "spider":
            if p.on_ground and p.buffered:
                p.buffered = False
                self._spider_pad(p, None, stand=False, up=not p.upside_down)
            else:
                # gravity also while standing (the floor puts it back; pads keep the move)
                p.y_vel = r3(p.y_vel - p.sign * C.BALL_GRAVITY)
                if p.sign * p.y_vel < -C.SPIDER_MAX_FALL:
                    p.y_vel = -p.sign * C.SPIDER_MAX_FALL
        elif p.on_ground and p.on_slope and p.mode == "cube" and p.holding and not p.hold_blocked:
            raise Unsupported("jump on a slope: speed not measured (it grows with time on the slope)")
        elif p.on_ground and ((p.holding and not p.hold_blocked) if p.mode == "cube" else p.buffered):
            # Cube: a held button jumps again on every landing. Ball: only a press that hasn't
            # been used yet switches (made in the air, it switches on the step after landing).
            self._jump(p)
        elif not p.on_ground:
            g = C.CUBE_GRAVITY[p.speed] if p.mode == "cube" else C.BALL_GRAVITY
            # GD's yVel stays on multiples of 0.001 (accumulating 0.216 in double drifts off them).
            p.y_vel = round(p.y_vel - p.sign * g, 3)
            # the ball falls no faster than 15 either (Tartarus, SubSonic, part 14: -14.923 -> -15.0)
            if p.sign * p.y_vel < -C.CUBE_MAX_FALL:
                p.y_vel = -p.sign * C.CUBE_MAX_FALL

        prev_y, prev_x = p.y, p.x
        p.x = f32(p.x + p.x_vel * C.X_STEP)
        if p.dashing and p.dash_slope:
            p.y = f32(p.y + p.x_vel * C.X_STEP * p.dash_slope)
        elif move_v is None:
            p.y = f32(p.y + p.y_vel * C.Y_STEP)
        else:
            p.y = f32(p.y + move_v * C.X_STEP * (1.0 if p.size == 1.0 else C.WAVE_MINI_SLOPE))
        if primary:
            self.triggers.update(p)
        self._check_uncertain(p)
        p.y_moved = p.y
        p.snap_from = None
        self._collide_solids(p, prev_y, was_airborne)
        if p.dead:
            return p
        if p.on_ground and p.last_block is not None and p.mode in ("cube", "ball"):
            # also on the landing step (after the snap): a cube that lands and jumps again at once
            # takes off with the standing reference, not the block it landed on
            self._track_standing_block(p)
        self._update_rotation(p, p.x - prev_x, p.y - prev_y)

        pressed = False
        if holding is not None:
            pressed = holding and not p.holding
            if pressed:
                p.buffered = True
            elif not holding:
                p.buffered = False
                self._end_dash(p)   # the dash ends on release; gravity returns on the next step
                p.hold_blocked = False
            p.holding = holding

        if p.doomed and p.doom_in <= 1:
            # thrown onto a hazard: it kills on the step after the throw, whatever its box
            p.dead, p.killer, p.doomed, p.doom_in = True, p.doomed, None, 1
            return p
        if p.doomed:
            p.doom_in -= 1
        r = p.rect
        orbs = []
        for i, o in self._near(p.x - 30, p.x + 30):
            if o.kind in (SOLID, BREAKABLE) or (o.kind == SLOPE and p.mode in ("cube", "ship", "ball", "ufo") and not o.rotation % 360):
                continue
            if o.extra == "collision block" or (o.kind == "special" and o.extra is None):
                # Collision blocks only matter to collision triggers; GD's other "special"
                # objects (type 40, they carry the trigger flag) have no player collision
                # (assumed, not measured).
                continue
            if o.kind == HAZARD and p.doomed:
                continue   # thrown onto a hazard this step: the game kills on the next step
            rotated_hit = False
            if o.rotation % 360:
                if o.kind != SLOPE and not (o.kind == HAZARD and o.radius):
                    # Objects turned by any angle but a multiple of 90 (their box turned with them):
                    # GD turns the player's box by the player's rotation as well (C.SPEED_VALUE's
                    # notes). Hazards touch the hazard box, the rest the full box; size and mode
                    # portals the box from before the change (the step's own box).
                    box = self._hazard_rect(p) if o.kind == HAZARD else r
                    if not obb_overlap(self._turned_box(box, p.rotation), obb_of(o)):
                        continue
                    rotated_hit = True
                elif o.kind == HAZARD:
                    pass    # saws: a circle, their angle doesn't matter
                else:
                    # Not decided yet; but when even the player box at any rotation can't reach
                    # the object's rotated box, there's certainly no contact.
                    if overlap(_any_rotation(r), _rotated_bounds(o)):
                        raise Unsupported(f"rotated {o.kind} {o.id} at x={o.x}: needs oriented boxes")
                    continue
            # Hazards touch the hazard box (wave 12x12, mini 7.2x7.2); slopes the body box.
            hr = self._hazard_rect(p) if o.kind == HAZARD else p.body_rect if o.kind == SLOPE else r
            if o.kind == HAZARD and o.radius:
                # Round hazards (saws) collide by circle: hit when the circle reaches the player's
                # box (measured: death on the first step the distance is under the radius).
                cx, cy = o.x + o.ox, o.y + o.oy
                nx = min(max(cx, hr[0]), hr[0] + hr[2])
                ny = min(max(cy, hr[1]), hr[1] + hr[3])
                if (cx - nx) ** 2 + (cy - ny) ** 2 < (o.radius + self.margin) ** 2:
                    p.dead, p.killer = True, f"saw {o.id} at x={o.x} y={o.y}"
                continue
            if o.kind == HAZARD and not rotated_hit:
                # Hazards: cocos2d's intersectsRect counts touching edges (a mini wave died with a
                # gap of 0.000). An upside-down spike's flat side is inset (C.FLIPPED_SPIKE_SHIFT).
                ox, oy, ow, oh = o.rect
                if o.id == 8 and o.flip_y and not o.quarter and not o.neg:
                    oh -= C.FLIPPED_SPIKE_SHIFT   # its flat side (the top) is inset; the tip isn't
                if hr[0] > ox + ow or ox > hr[0] + hr[2] or hr[1] > oy + oh or oy > hr[1] + hr[3]:
                    continue
            elif not rotated_hit and not overlap(hr, o.rect):
                continue
            if o.kind == SLOPE and not rotated_hit:
                # Other modes on slopes aren't simulated: stop only when the mode's own hitbox
                # (the wave's small box) reaches into the slope's triangle, not its whole box.
                # The wave: its hazard box (it died 5.7 above a 45 deg slope's line, out of reach
                # of its 4-unit block box). Quarter-turned slopes converted before the turn was
                # recorded have no reliable line: their whole box counts.
                sb = p.box(C.WAVE_SLOPE_BOX[p.size]) if p.mode == "wave" else hr
                if not (o.quarter and not o.turn) and not box_hits_slope(sb, o):
                    continue
                if p.mode == "wave" and not self._in_dblock(p):
                    # the wave dies on any solid it touches, slopes too, unless it's touching a
                    # D block (the user; Tartarus: 22 wave stops at slopes)
                    p.dead, p.killer = True, f"slope {o.id} at x={o.x} y={o.y}"
                    continue
            if o.kind == SPEED_PORTAL:
                p.speed = o.extra
            elif o.kind == GRAVITY_PORTAL:
                if o.extra == "toggle":
                    raise Unsupported(f"gravity toggle portal at x={o.x}: not measured")
                # the ball like the cube: yVel halved after the step's move (30 uses, part 14).
                # A portal acts on its first touch only, even when that touch changed nothing
                # (AKIRA: a UFO already upside-down touched a yellow portal, flipped back by a blue
                # one, then touched the yellow one again: no flip).
                if i not in p.used:
                    p.used.add(i)
                    if (o.extra == "flip") != p.upside_down:
                        self._flip(p)
            elif o.kind == SIZE_PORTAL:
                size = 0.6 if o.extra == "mini" else 1.0   # y is kept; the floor corrects it next step
                if size > p.size and p.on_ground and p.mode in ("cube", "ball", "robot", "spider")                         and not self._on_floor_line(p):
                    # ...but grown on a block, the player stands on it at once (AKIRA: an upside-down
                    # mini cube under a block, 771 -> 765 on the portal's step)
                    half = p.half
                    p.size = size
                    p.y = f32(p.y + p.sign * (p.half - half))
                p.size = size
            elif o.kind == MODE_PORTAL:
                if o.extra not in ("cube", "ball", "wave", "ship", "ufo", "robot", "spider"):
                    raise Unsupported(f"{o.extra} portal at x={o.x}: game mode not implemented")
                if o.extra in ("wave", "ship", "ufo", "spider"):
                    # Free Mode (ship test 15:32: the ship flew to y 721 past a portal at y 285):
                    # the ground is the floor and there's no ceiling.
                    p.area_bottom = C.GROUND_Y if o.free else C.wave_area_bottom(o.y)
                    p.area_height = float("inf") if o.free else C.WAVE_AREA_HEIGHT
                if o.extra != p.mode:
                    # After the step's move with the old mode. Between two flying modes (ship,
                    # UFO, wave) yVel is quartered, not rounded (-7.15 -> -1.7875); between a
                    # flying and a falling mode (cube, ball, robot, spider) halved, in the air or
                    # not (cube -7.744 -> ship -3.98); between falling modes kept (cube -> robot,
                    # robot -> spider, spider -> ball: 80 switches in Shitty mix 11/14, Artifice).
                    fly_old, fly_new = p.mode in C.FLY_MODES, o.extra in C.FLY_MODES
                    if fly_old and fly_new:
                        p.y_vel *= C.WAVE_TO_SHIP_YVEL_FACTOR
                        p.on_ground = False
                    elif fly_old or fly_new:
                        p.y_vel *= C.GRAVITY_FLIP_YVEL_FACTOR
                        # standing, the switch stays on the ground into the UFO (34 cases) and from a
                        # flying mode into a falling one (ship -> cube on a block, Orochi buff 3)
                        if o.extra != "ufo" and not (fly_old and p.on_ground and p.y_vel == 0):
                            p.on_ground = False
                    elif not p.on_ground and {p.mode, o.extra} == {"cube", "ball"}                             and abs(p.y_vel) >= C.CUBE_MAX_FALL:
                        raise Unsupported(f"{o.extra} portal at x={o.x} at the fall cap: not measured")
                    old_half = p.half
                    p.mode = o.extra
                    p.robot_boost = 0
                    if p.on_ground and p.half != old_half:
                        # standing: the box changes size about its bottom (spider 27 -> UFO 30:
                        # 433.5 -> 435)
                        p.y = f32(p.y + p.sign * (p.half - old_half))
            elif o.kind == TELEPORT:
                # The player is put at the exit portal's height: blue portal y + key 54 (measured
                # once, Every End 2: 135 + 420 -> 555 on the touching step). Speed kept.
                if i not in p.used:
                    p.used.add(i)
                    p.y = f32(o.y + o.tp_offset)
                    if p.on_ground and p.steps > 2 and p.mode != "ship" and not self._supported(p):
                        # Teleported off the ground: airborne at once, with one step of gravity
                        # on yVel but none on y (test level). On the run's first moving step the
                        # game keeps it on the ground instead (Every End 2's start), and when the
                        # exit puts it exactly on a block (BOTS phase 4, x 5670).
                        p.on_ground = False
                        g = C.CUBE_GRAVITY[p.speed] if p.mode == "cube" else C.BALL_GRAVITY
                        p.y_vel = round(p.y_vel - p.sign * g, 3)
            elif o.kind == HAZARD:
                p.dead, p.killer = True, f"hazard {o.id} at x={o.x} y={o.y}"
            elif o.kind == PAD:
                self._pad(p, i, o)
            elif o.kind == ORB:
                orbs.append((i, o))   # used after the step's portals (see below)
            elif o.kind == DUAL_PORTAL:
                # Dual: a second player appears; the first one moves on as before (yVel kept on
                # entry, Marathon 2 / BOTS / Night Rider 2). The second isn't simulated yet.
                was = p.dual
                p.dual = o.extra == "on"
                if p.dual and not o.free:
                    # it sets the band like a ship or wave portal
                    p.area_bottom = C.wave_area_bottom(o.y)
                    p.area_height = C.WAVE_AREA_HEIGHT
                if p.dual and not was and not getattr(p, "player2", False):
                    self._spawn_player2(p)
            elif o.kind == MIRROR_PORTAL:
                pass   # mirror flips the view only
            else:
                raise Unsupported(f"{o.extra or ''} {o.kind} {o.id} at x={o.x} y={o.y}: not implemented")

        # Orbs act after the portals touched on the same step (Tartarus: a blue orb inside a
        # gravity portal flips the player; the portal, already matching, doesn't flip it back).
        for i, o in orbs:
            self._orb(p, i, o)
        if p.mode == "ship":
            # A ship's press only works on its own step: held into an orb later, it doesn't use
            # it (BOTS phase 4: pressed 6 steps before a black orb and held, the orb wasn't used).
            p.buffered = False
        if pressed and p.buffered and p.on_ground and p.mode not in ("wave", "ship", "ufo"):
            if p.on_slope and p.mode != "ball":
                raise Unsupported("jump on a slope: speed not measured (it grows with time on the slope)")
            if p.mode == "spider":
                # the spider is thrown on the press step itself (79 of 79 ground presses)
                p.buffered = False
                self._spider_pad(p, None, stand=False, up=not p.upside_down)
            elif p.mode == "robot":
                p.y_vel = p.sign * self._jump_value(p) * C.ROBOT_JUMP_FACTOR
                p.robot_boost, p.on_ground, p.buffered = C.ROBOT_BOOST_STEPS, False, False
            else:
                self._jump(p)
        return p

    def _pad(self, p, i, o):
        if i in p.used:
            return
        # a pad ends a dash (AKIRA: 3 pink pads under -70 deg UFO dashes, yVel 6.4 at once)
        self._end_dash(p)
        if p.snap_from is not None and os.environ.get("NO_PAD_UNSNAP") is None:
            # landed and launched by a pad on the same step: GD doesn't snap x (Tartarus, a blue pad
            # at 3x: x kept, the sim had moved it 2 units)
            p.x, p.snap_from = p.snap_from, None
        if o.extra == "spider":
            self._spider_pad(p, o, stand=p.mode != "spider")   # the spider arrives moving, as from its orb
            p.used.add(i)
            return
        if p.mode not in ("cube", "ball", "ship", "ufo", "robot", "spider"):
            raise Unsupported(f"{o.extra} pad at x={o.x} in {p.mode} mode: not measured")
        ball = p.mode in ("ball", "spider")
        ship = p.mode == "ship"
        if o.extra == "blue":
            # Sets gravity the way the pad points (up unless flipped); no effect if it already is.
            if o.quarter:
                raise Unsupported(f"blue pad at x={o.x} rotated sideways: not measured")
            if p.upside_down == (not o.flip_y):
                p.used.add(i)
                return
            v = C.pad_yvel(p.mode, "blue", p.size)
            if v is None:
                raise Unsupported(f"blue pad at x={o.x} (size {p.size}): value not measured")
            standing = p.on_ground and p.mode in ("cube", "ball", "robot") and not self._on_floor_line(p)
            if standing:
                # Standing on a block, GD pulls the player down by one step of gravity before the
                # block puts it back; the flip keeps that move (405 -> 404.9514, Tartarus 1x and 3x).
                g = C.CUBE_GRAVITY[p.speed] if p.mode == "cube" else C.BALL_GRAVITY
                p.y = f32(p.y - p.sign * round(g, 3) * C.Y_STEP)
            p.upside_down = not p.upside_down
            p.y_vel = -p.sign * v
            if ship:
                # The ship standing on a block when the pad flips it keeps this step's small move
                # (it isn't put back on the block: 255 -> 254.984, ship test level).
                p.y = p.y_moved
            elif p.mode == "spider" and not self._on_floor_line(p):
                # The same for the spider off the floor: GD moves it with gravity while it stands on
                # a block, and the flip keeps that step's move (1306.5 -> 1306.529, Artifice).
                p.y = p.y_moved
        else:
            v = C.pad_yvel(p.mode, o.extra, p.size)
            if p.mode in ("ship", "ufo") and o.extra == "yellow":
                p.ship_clip = True
            if p.mode == "spider" and not self._on_floor_line(p):
                p.y = p.y_moved     # keeps the step's move (just thrown: 1606.5 -> 1606.725); not
                                    # on the floor itself (103.5 stayed, test level)
            elif p.on_ground and p.mode in ("cube", "ball", "robot") and not self._on_floor_line(p):
                # the same one step of gravity as the blue pad (The Hallucination, a yellow pad at
                # 0.5x: 255 -> 254.9523)
                g = C.CUBE_GRAVITY[p.speed] if p.mode == "cube" else C.BALL_GRAVITY
                p.y = f32(p.y - p.sign * round(g, 3) * C.Y_STEP)
            if v is None:
                raise Unsupported(f"{o.extra} pad at x={o.x} ({p.mode}, size {p.size}): value not measured")
            p.y_vel = p.sign * v
        p.used.add(i)
        p.on_ground = False

    def _spider_pad(self, p, o, stand=True, up=None):
        """Throws the player onto the nearest surface in the direction the object points (up when
        unrotated, down when rotated 180 or flipped vertically) and sets gravity that way.
        Measured in ball mode: onto a block's underside the player stands at once (yVel 0); onto
        the floor it arrives with yVel -1 and stands on the next step."""
        if o is not None and o.quarter:
            raise Unsupported(f"spider {o.kind} at x={o.x} rotated sideways: not measured")
        if up is None:
            up = not o.flip_y            # direction of travel = the new gravity
        ox = o.x if o is not None else p.x
        left, right = p.x - p.half, p.x + p.half
        best = None
        for _, b in self._solids(left, right):
            bx, by, bw, bh = b.rect
            if not (left < bx + bw and bx < right):
                continue
            surface = by if up else by + bh
            if (surface - p.y) * (1 if up else -1) > 0 and (best is None or abs(surface - p.y) < abs(best - p.y)):
                best = surface
        if p.mode in ("ship", "ufo", "spider"):
            # the band's edges count as surfaces
            edge = p.area_bottom + p.area_height if up else p.area_bottom
            if edge != float("inf") and (best is None or abs(edge - p.y) < abs(best - p.y)):
                best = edge
        # A hazard in the way stops the throw too: the player is put at the hazard's centre and
        # dies on the next step (ship tests 13:47-15:32: 34 throws, y = a hazard's y every time).
        # Hazards count when their box comes within C.SPIDER_HAZARD_REACH of the player's x (after
        # the step's move): 3.998 stopped it, 4.036 passed (two diagonal spike columns, 0.5 apart).
        # The ship's own box overlapping a spike isn't enough. The nearest one in reach wins.
        land = None if best is None else (best - p.half if up else best + p.half)
        hit = None
        reach = C.SPIDER_HAZARD_REACH
        for _, h in self._near(p.x - reach - 30, p.x + reach + 30):
            if h.kind != HAZARD:
                continue
            hx, hy, hw, hh = h.rect
            if not (hx < p.x + reach and p.x - reach < hx + hw):
                continue
            near = hy - p.half if up else hy + hh + p.half   # where the player's edge reaches it
            ahead = (near - p.y) * (1 if up else -1) > 0
            before_land = land is None or (land - near) * (1 if up else -1) > 0
            if ahead and before_land and (hit is None or abs(h.y - p.y) < abs(hit.y - p.y)):
                hit = h
        if hit is not None:
            p.upside_down = up
            p.y, p.y_vel, p.on_ground = f32(hit.y), (1.0 if up else -1.0), False
            p.doomed = f"{hit.kind} {hit.id} at x={hit.x} y={hit.y} (spider throw)"
            p.last_block = None
            return
        p.upside_down = up
        if best is not None and stand:
            p.y = f32(best - p.half if up else best + p.half)
            p.y_vel, p.on_ground = 0.0, True
        elif best is not None:
            # Spider orb: arrives with yVel 1 toward the surface and stands on the next step.
            p.y = f32(best - p.half if up else best + p.half)
            p.y_vel, p.on_ground = (1.0 if up else -1.0), False
        elif not up:
            p.y, p.y_vel, p.on_ground = C.GROUND_Y + p.half, -1.0, False
        elif not stand:
            # Spider orb with nothing above (ship test 15:32, Free Mode): thrown to the level's top,
            # y 3180, and killed by the out-of-bounds area two steps later.
            p.y, p.y_vel, p.on_ground = C.SPIDER_TOP_Y, 1.0, False
            p.doomed, p.doom_in = f"out of the level (spider throw at x={ox})", 2
        else:
            raise Unsupported(f"spider throw at x={ox} with nothing above: not measured")
        p.last_block = None

    def _orb(self, p, i, o):
        if not p.buffered or p.dashing or (i in p.used and not o.multi):
            return   # no unused press, or mid-dash (a dash flew through an orb without using it)
        ball = p.mode == "ball"
        ship = p.mode == "ship"
        if o.extra == "toggle":
            # Toggle orb: turns its target group on or off, like a toggle trigger, and uses the
            # press; the player moves on as it was (The Hallucination: 8 uses in wave mode, yVel
            # unchanged).
            if o.target is None:
                raise Unsupported(f"toggle orb at x={o.x}: no target group (level converted before "
                                  f"toggle orbs: convert it again)")
            p.used.add(i)
            p.buffered = False
            self.triggers.toggle_group(o.target, o.activate)
            return
        if p.mode == "wave" and o.extra in ("blue", "green"):
            # The wave uses only the gravity orbs (The Hallucination: blue 27 uses, green 5; yellow
            # touched 40 times, never used). Gravity flips and yVel is the cube's orb value (blue
            # 4.492 at 4x, 4.568 at 2x, mini 3.5935; green -11.23 at 4x); this step's move keeps the
            # old direction, and the next step's yVel comes from the hold as always.
            v = C.orb_yvel("cube", o.extra, p.speed, p.size)
            if v is None:
                raise Unsupported(f"{o.extra} orb at x={o.x} in wave mode ({p.speed}, size {p.size}): not measured")
            p.used.add(i)
            p.buffered = False
            p.upside_down = not p.upside_down
            p.y_vel = -p.sign * v if o.extra == "blue" else p.sign * v
            return
        if p.mode == "wave" and o.extra in ("yellow", "pink", "red", "black"):
            return   # no effect on the wave
        if p.mode not in ("cube", "ball", "ship", "ufo", "robot", "spider") and o.extra not in ("dash-green", "dash-pink"):
            raise Unsupported(f"{o.extra} orb at x={o.x} in {p.mode} mode: not measured")
        if o.extra == "spider":
            # Same throw as the spider pad. The button held from this press doesn't jump on
            # landing (seen: 19 steps standing with the button held, until it was released).
            p.used.add(i)
            p.buffered = False
            p.hold_blocked = True
            self._spider_pad(p, o, stand=False)
            return
        if o.extra in ("dash-green", "dash-pink"):
            # Flies straight (yVel 0 from the next step on) for as long as the button stays held.
            # The pink one also flips gravity (yVel halved on the use step, like a gravity portal).
            p.used.add(i)
            if o.extra == "dash-pink":
                self._flip(p)
            a = (o.rotation + 180.0) % 360.0 - 180.0
            if o.flip_x or abs(a) >= 90 or (a and p.upside_down):
                raise Unsupported(f"{o.extra} orb at x={o.x} turned {o.rotation} (flipped {o.flip_x}, "
                                  f"upside-down {p.upside_down}): dash direction not measured")
            p.dash_slope = math.tan(math.radians(-a))
            if not p.dashing:
                p.rot_under = p.rotation
            p.dash_rot = p.rotation = a
            p.buffered = False   # the dash uses the press (AKIRA: no UFO jump when a pad ends it)
            p.dashing, p.on_ground = True, False
            return
        if o.extra == "blue":
            v = C.orb_yvel(p.mode, "blue", p.speed, p.size)
            if v is None:
                raise Unsupported(f"blue orb at x={o.x} ({p.speed}, size {p.size}): not measured")
            p.used.add(i)
            p.buffered = False
            p.upside_down = not p.upside_down
            p.y_vel = -p.sign * v
            p.on_ground = False
            return
        if o.extra == "black":
            v = C.BLACK_ORB.get(p.mode, C.BLACK_ORB_YVEL)
        else:
            v = C.orb_yvel(p.mode, o.extra, p.speed, p.size)
        if v is None:
            raise Unsupported(f"{o.extra} orb at x={o.x} ({p.mode} {p.speed}, size {p.size}): not measured")
        p.used.add(i)
        p.buffered = False
        if o.extra == "green":
            p.upside_down = not p.upside_down
        p.y_vel = p.sign * v
        p.on_ground = False
        if p.mode in ("ship", "ufo") and o.extra == "yellow":
            p.ship_clip = True
