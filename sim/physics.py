"""Headless GD physics, one physics step (1/240 s) at a time. Cube, ball and wave so far.

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
from .objects import (BREAKABLE, GRAVITY_PORTAL, HAZARD, MODE_PORTAL, ORB, PAD, SIZE_PORTAL, SLOPE, SOLID,
                      SPEED_PORTAL, TELEPORT, overlap)
from .triggers import Triggers

EPS = 1e-4


def _key(o, p=None):
    """Standing on several blocks at once, the snap's reference is the first in level-string order."""
    return o.order


def _lkey(o, p=None):
    """Landing on several blocks at once, the block landed on is the LAST in level-string order
    (every other pairing of first / last / back / front / centre fits Every End 2 worse)."""
    return -o.order


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
    mode: str = "cube"  # "cube", "ball" or "wave"
    on_ground: bool = False
    upside_down: bool = False
    holding: bool = False
    buffered: bool = False        # a press that hasn't been used by a jump or an orb yet
    hold_blocked: bool = False    # after a spider orb: the held button is ignored until released
    dashing: bool = False         # in a dash orb's dash: flies straight while the button is held
    area_bottom: float = C.GROUND_Y  # the wave's floor (set by the wave portal); ceiling 300 above
    dead: bool = False
    killer: str = ""              # what killed the player (for reports)
    steps: int = 0
    on_slope: bool = False         # standing on a slope (cube)
    slope_capped: bool = False     # already one step at the slope's top height
    used: set = field(default_factory=set)  # one-time objects already activated (by index)
    last_block: int | None = None  # index of the block last landed on (None after the floor)
    last_diff: float = 0.0         # player x - that block's x at the landing
    last_block_x: float = 0.0      # that block's x at the landing (a trigger may move it later)
    snap_dbg: dict | None = None   # the last landing's snap decision (for tools)

    @property
    def x_vel(self) -> float:
        return C.X_VEL[self.speed]

    @property
    def half(self) -> float:
        """Half the body box: what stands on the floor and on blocks."""
        if self.mode == "wave":
            return C.WAVE_BODY[self.size] / 2
        return C.PLAYER_SIZE[self.size] / 2

    @property
    def hit_half(self) -> float:
        """Half the hitbox that touches hazards, portals, pads and orbs."""
        if self.mode == "wave":
            return C.WAVE_HITBOX[self.size] / 2
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
        self.grid = Grid(self.objects)
        self.triggers = Triggers(self, level.triggers, level.anchors)
        self.player = Player(speed=start_speed)
        self.player.y = C.GROUND_Y + self.player.half

    # --- helpers ---

    def _near(self, x0, x1):
        for i in self.grid.near(x0, x1):
            o = self.objects[i]
            if o.enabled:
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

    def _jump_value(self, p) -> float:
        jump = C.CUBE_JUMP.get(p.speed)
        if jump is None:
            raise Unsupported(f"cube jump at {p.speed} not measured")
        return jump * C.MINI_JUMP_FACTOR if p.size != 1.0 else jump

    def _jump(self, p):
        """Cube: jump. Ball: switch gravity and leave the surface at 0.3 x the jump value."""
        if p.mode == "ball":
            p.upside_down = not p.upside_down
            p.y_vel = -p.sign * self._jump_value(p) * C.BALL_SWITCH_FACTOR
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
        if not p.upside_down and p.y <= C.GROUND_Y + p.half:
            return True
        if p.mode == "wave":   # the wave slides only on the floor; blocks kill it
            return False
        left, right = x - p.half, x + p.half
        foot = p.y - p.sign * p.half
        for _, o in self._solids(left, right):
            ox, oy, ow, oh = o.rect
            if left < ox + ow and ox < right:
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
        per speed). Measured at 1x and 2x (957 landings, see NOTES); other speeds keep snapping
        on every block-to-block landing until measured."""
        last, new = self.objects[p.last_block], self.objects[i]
        if last.kind == BREAKABLE:
            return False   # never from a breakable block (Every End 2: 9 landings); onto one it does
        pats = C.SNAP_PATTERNS.get(p.speed)
        if pats is None:
            return True
        return (round(new.x - last.x), round((new.y - last.y) * p.sign)) in pats

    def _hazard_rect(self, p):
        """The box hazards touch: the body box, but smaller for the wave."""
        if p.mode != "wave":
            return p.body_rect
        return p.box(C.WAVE_HAZARD_BOX[p.size])

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
            on_line = y0 + k * (p.x - x0) + (-1 if up else 1) * h * math.sqrt(1 + k * k)
            cap = (min(y0, y1) - h) if up else (max(y0, y1) + h)
            capped = (on_line <= cap) if up else (on_line >= cap)
            s = cap if capped else on_line
            if best is None or p.sign * (s - best[0]) > 0:
                best = (s, capped, i)
        return best

    def _collide_slopes(self, p):
        """Cube on slopes. Returns True when a slope decided the cube's height this step."""
        sl = self._slope_support(p)
        if sl is None:
            p.on_slope = p.slope_capped = False
            return False
        s, capped, i = sl
        floor = C.GROUND_Y + p.half
        if not p.upside_down and s <= floor:
            p.on_slope = p.slope_capped = False
            return False          # the floor holds the cube higher
        below = p.sign * (p.y - s) < -EPS       # the cube is inside the slope
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
                # launch speed grows with the time spent on the slope and isn't worked out yet.
                raise Unsupported(f"leaving the top of slope {self.objects[i].id} at "
                                  f"x={self.objects[i].x}: launch speed not measured")
            p.y = f32(s)
            p.y_vel, p.on_ground = 0.0, True
            p.on_slope, p.slope_capped = True, capped
            p.last_block = None
            return True
        if below:
            raise Unsupported(f"hitting slope {self.objects[i].id} at x={self.objects[i].x} "
                              f"from its open side while rising: not measured")
        return False

    def _collide_solids(self, p, prev_y, was_airborne):
        """Landing on the floor or on a block's top (its underside when upside down)."""
        if p.mode == "cube" and self._collide_slopes(p):
            return
        floor = (p.area_bottom if p.mode == "wave" else C.GROUND_Y) + p.half
        if (not p.upside_down or p.mode == "wave") and p.y <= floor:   # the wave: either gravity
            # The wave's yVel becomes 0 only when the move went past the floor; landing exactly on
            # it keeps the yVel for that step (it is 0 from the next one).
            if p.mode != "wave" or p.y < floor:
                p.y_vel = 0.0
            p.y, p.on_ground = floor, True
            p.last_block = None
            return
        if p.mode == "wave":
            ceiling = p.area_bottom + C.WAVE_AREA_HEIGHT - p.half
            if p.y >= ceiling:
                if p.y > ceiling:
                    p.y_vel = 0.0
                p.y = ceiling
                return
            # Any contact of the wave's block box (7.2x7.2 at both sizes) with a block kills it,
            # from any side. D blocks: not tested.
            br = p.box(C.WAVE_BLOCK_BOX[p.size])
            for _, o in self._solids(br[0], br[0] + br[2]):
                if overlap(br, o.rect):
                    p.dead, p.killer = True, f"block {o.id} at x={o.x} y={o.y}"
                    return
            return
        r = p.body_rect
        best = None
        ceiling = None
        for i, o in self._solids(r[0], r[0] + r[2]):
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
                if p.sign * (face - p.y) > 0 and o.moved_step == p.steps:
                    # A block moving into the cube from its head side pushes it out (Every End 2:
                    # a slab moving down carried the cube at its speed, yVel kept). A static
                    # block's underside doesn't: a rising cube passes into it.
                    push = face - p.sign * p.half
                    if ceiling is None or p.sign * (push - ceiling) < 0:
                        ceiling = push
                    continue
                # Side: the outer box may overlap a block freely; the player dies when the small
                # inner box touches one.
                iw, ih = C.INNER_BOX[p.size]
                if touches_rounded((p.x - iw / 2, p.y - ih / 2, iw, ih), o.rect, C.CUBE_CORNER * (p.size if p.size != 1.0 else 1.0)):
                    if o.kind == BREAKABLE:
                        o.enabled = False   # breaks instead of killing (provisional)
                        continue
                    p.dead, p.killer = True, f"block {o.id} at x={o.x:.0f} y={o.y:.0f} (inner box)"
                    return
                continue
            if best is None or p.sign * (surface - best[2]) > 0                     or (abs(surface - best[2]) < EPS and _lkey(o, p) < _lkey(best[1], p)):
                best = (i, o, surface)   # the highest; between equals the back-most
        if ceiling is not None and best is None:
            p.y = f32(ceiling)
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
        if was_airborne and p.last_block is not None and p.last_block != i                 and self.objects[p.last_block].x == p.last_block_x and self._snaps(p, i):
            # (no snap when the previous block has moved since: seen in Every End 2, provisional)
            # Snap: GD predicts x from where the player stood on the previous block and moves the
            # player toward that spot by at most 1 unit (0.5x, 1x, 4x) or 2 (2x, 3x).
            predicted = p.last_diff + o.x
            shift = C.SNAP_SHIFT[p.speed]
            d = predicted - p.x
            p.x = f32(predicted if abs(d) <= shift else p.x + (shift if d > 0 else -shift))
        if was_airborne or p.last_block != i:
            p.last_block, p.last_diff, p.last_block_x = i, p.x - o.x, o.x

    # --- one physics step ---

    def step(self, holding: bool | None = None) -> Player:
        p = self.player
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
        if p.on_ground and p.mode != "wave" and not p.on_slope and not jumping                 and not self._supported(p, f32(p.x + p.x_vel * C.X_STEP)):
            p.on_ground = False
        was_airborne = not p.on_ground
        move_v = None
        if p.mode == "wave":
            # Held = up (relative to gravity). Standing on the floor without holding: no movement.
            on_floor = p.y <= p.area_bottom + p.half
            on_ceiling = p.y >= p.area_bottom + C.WAVE_AREA_HEIGHT - p.half
            d = p.sign if p.holding else -p.sign   # +1 = up on screen
            if (on_floor and d < 0) or (on_ceiling and d > 0):
                p.y_vel, move_v = 0.0, 0.0
            else:
                # The trace shows yVel rounded to 3 decimals; the move uses the exact xVel.
                p.y_vel, move_v = d * round(p.x_vel, 3), d * p.x_vel
        elif p.dashing:
            p.y_vel = 0.0
        elif p.on_ground and p.on_slope and p.holding and not p.hold_blocked:
            raise Unsupported("jump on a slope: speed not measured (it grows with time on the slope)")
        elif p.on_ground and ((p.holding and not p.hold_blocked) if p.mode == "cube" else p.buffered):
            # Cube: a held button jumps again on every landing. Ball: only a press that hasn't
            # been used yet switches (made in the air, it switches on the step after landing).
            self._jump(p)
        elif not p.on_ground:
            g = C.CUBE_GRAVITY[p.speed] if p.mode == "cube" else C.BALL_GRAVITY
            # GD's yVel stays on multiples of 0.001 (accumulating 0.216 in double drifts off them).
            p.y_vel = round(p.y_vel - p.sign * g, 3)
            if p.mode == "cube" and p.sign * p.y_vel < -C.CUBE_MAX_FALL:
                p.y_vel = -p.sign * C.CUBE_MAX_FALL

        prev_y = p.y
        p.x = f32(p.x + p.x_vel * C.X_STEP)
        if move_v is None:
            p.y = f32(p.y + p.y_vel * C.Y_STEP)
        else:
            p.y = f32(p.y + move_v * C.X_STEP * (1.0 if p.size == 1.0 else C.WAVE_MINI_SLOPE))
        self.triggers.update(p)
        self._check_uncertain(p)
        self._collide_solids(p, prev_y, was_airborne)
        if p.dead:
            return p
        if p.on_ground and p.last_block is not None and p.mode in ("cube", "ball"):
            # also on the landing step (after the snap): a cube that lands and jumps again at once
            # takes off with the standing reference, not the block it landed on
            self._track_standing_block(p)

        pressed = False
        if holding is not None:
            pressed = holding and not p.holding
            if pressed:
                p.buffered = True
            elif not holding:
                p.buffered = False
                p.dashing = False   # the dash ends on release; gravity returns on the next step
                p.hold_blocked = False
            p.holding = holding

        r = p.rect
        for i, o in self._near(p.x - 30, p.x + 30):
            if o.kind in (SOLID, BREAKABLE) or (o.kind == SLOPE and p.mode == "cube" and not o.rotation % 360):
                continue
            if o.extra == "collision block" or (o.kind == "special" and o.extra is None):
                # Collision blocks only matter to collision triggers; GD's other "special"
                # objects (type 40, they carry the trigger flag) have no player collision
                # (assumed, not measured).
                continue
            if o.rotation % 360:
                # Not decided yet; but when even the player box at any rotation can't reach the
                # object's rotated box, there's certainly no contact.
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
                if (cx - nx) ** 2 + (cy - ny) ** 2 < o.radius ** 2:
                    p.dead, p.killer = True, f"saw {o.id} at x={o.x} y={o.y}"
                continue
            if o.kind == HAZARD:
                # Hazards: cocos2d's intersectsRect counts touching edges (a mini wave died with a
                # gap of 0.000). The normal cube survived overlaps of 0.11 (Every End 2, 12 times):
                # its box is a little smaller than 30 - modelled as a tolerance (provisional).
                ox, oy, ow, oh = o.rect
                if hr[0] > ox + ow or ox > hr[0] + hr[2] or hr[1] > oy + oh or oy > hr[1] + hr[3]:
                    continue
                if p.mode == "cube" and p.size == 1.0 and not touches_rounded(hr, o.rect, C.CUBE_CORNER):
                    continue   # a corner touch short of the rounded corner (see C.CUBE_CORNER)
            elif not overlap(hr, o.rect):
                continue
            if o.kind == SPEED_PORTAL:
                p.speed = o.extra
            elif o.kind == GRAVITY_PORTAL:
                if o.extra == "toggle":
                    raise Unsupported(f"gravity toggle portal at x={o.x}: not measured")
                if p.mode == "ball":
                    raise Unsupported(f"gravity portal at x={o.x} in ball mode: not measured")
                if (o.extra == "flip") != p.upside_down:
                    self._flip(p)
            elif o.kind == SIZE_PORTAL:
                p.size = 0.6 if o.extra == "mini" else 1.0   # y is kept; the floor corrects it next step
            elif o.kind == MODE_PORTAL:
                if o.extra not in ("cube", "ball", "wave"):
                    raise Unsupported(f"{o.extra} portal at x={o.x}: game mode not implemented")
                if o.extra == "wave":
                    p.area_bottom = C.wave_area_bottom(o.y)
                if o.extra != p.mode:
                    if "wave" in (o.extra, p.mode):
                        # Into or out of the wave: yVel is halved (cube -1.512 -> wave entry
                        # -0.756; wave -5.193 -> cube -2.5965), in the air or not.
                        p.y_vel *= C.GRAVITY_FLIP_YVEL_FACTOR
                        p.on_ground = False
                    elif not p.on_ground:
                        raise Unsupported(f"{o.extra} portal at x={o.x} entered in the air: not measured")
                    p.mode = o.extra
            elif o.kind == TELEPORT:
                # The player is put at the exit portal's height: blue portal y + key 54 (measured
                # once, Every End 2: 135 + 420 -> 555 on the touching step). Speed kept.
                if i not in p.used:
                    p.used.add(i)
                    p.y = f32(o.y + o.tp_offset)
                    if p.on_ground and p.steps > 2:
                        # Teleported off the ground: airborne at once, with one step of gravity
                        # on yVel but none on y (test level). On the run's first moving step the
                        # game keeps it on the ground instead (Every End 2's start).
                        p.on_ground = False
                        g = C.CUBE_GRAVITY[p.speed] if p.mode == "cube" else C.BALL_GRAVITY
                        p.y_vel = round(p.y_vel - p.sign * g, 3)
            elif o.kind == HAZARD:
                p.dead, p.killer = True, f"hazard {o.id} at x={o.x} y={o.y}"
            elif o.kind == PAD:
                self._pad(p, i, o)
            elif o.kind == ORB:
                self._orb(p, i, o)
            else:
                raise Unsupported(f"{o.extra or ''} {o.kind} {o.id} at x={o.x} y={o.y}: not implemented")

        if pressed and p.buffered and p.on_ground and p.mode != "wave":
            if p.on_slope:
                raise Unsupported("jump on a slope: speed not measured (it grows with time on the slope)")
            self._jump(p)
        return p

    def _pad(self, p, i, o):
        if i in p.used:
            return
        if o.extra == "spider":
            self._spider_pad(p, o)
            p.used.add(i)
            return
        if p.mode not in ("cube", "ball"):
            raise Unsupported(f"{o.extra} pad at x={o.x} in {p.mode} mode: not measured")
        ball = p.mode == "ball"
        if o.extra == "blue":
            # Sets gravity the way the pad points (up unless flipped); no effect if it already is.
            if o.quarter:
                raise Unsupported(f"blue pad at x={o.x} rotated sideways: not measured")
            if p.upside_down == (not o.flip_y):
                p.used.add(i)
                return
            v = (C.BALL_BLUE_PAD_FALL if ball else C.BLUE_PAD_FALL).get(p.size)
            if v is None:
                raise Unsupported(f"blue pad at x={o.x} (size {p.size}): value not measured")
            p.upside_down = not p.upside_down
            p.y_vel = -p.sign * v
        else:
            v = (C.BALL_PAD_YVEL if ball else C.PAD_YVEL).get((o.extra, p.size))
            if v is None:
                raise Unsupported(f"{o.extra} pad at x={o.x} ({p.mode}, size {p.size}): value not measured")
            p.y_vel = p.sign * v
        p.used.add(i)
        p.on_ground = False

    def _spider_pad(self, p, o, stand=True):
        """Throws the player onto the nearest surface in the direction the object points (up when
        unrotated, down when rotated 180 or flipped vertically) and sets gravity that way.
        Measured in ball mode: onto a block's underside the player stands at once (yVel 0); onto
        the floor it arrives with yVel -1 and stands on the next step."""
        if o.quarter:
            raise Unsupported(f"spider {o.kind} at x={o.x} rotated sideways: not measured")
        up = not o.flip_y                # direction of travel = the new gravity
        left, right = p.x - p.half, p.x + p.half
        best = None
        for _, b in self._solids(left, right):
            bx, by, bw, bh = b.rect
            if not (left < bx + bw and bx < right):
                continue
            surface = by if up else by + bh
            if (surface - p.y) * (1 if up else -1) > 0 and (best is None or abs(surface - p.y) < abs(best - p.y)):
                best = surface
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
        else:
            raise Unsupported(f"spider pad at x={o.x} with nothing above: not measured")
        p.last_block = None

    def _orb(self, p, i, o):
        if not p.buffered or p.dashing or (i in p.used and not o.multi):
            return   # no unused press, or mid-dash (a dash flew through an orb without using it)
        ball = p.mode == "ball"
        if p.mode != "cube" and not (ball and o.extra in ("yellow", "pink", "red", "green", "black", "blue")):
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
            p.dashing, p.on_ground = True, False
            return
        if o.extra == "blue":
            v = (C.BALL_BLUE_ORB_FALL if ball else C.BLUE_ORB_FALL).get((p.speed, p.size))
            if v is None:
                raise Unsupported(f"blue orb at x={o.x} ({p.speed}, size {p.size}): not measured")
            p.used.add(i)
            p.buffered = False
            p.upside_down = not p.upside_down
            p.y_vel = -p.sign * v
            p.on_ground = False
            return
        if o.extra == "black":
            v = C.BLACK_ORB_YVEL
        else:
            v = (C.BALL_ORB_YVEL if ball else C.ORB_YVEL).get((o.extra, p.speed, p.size))
        if v is None:
            raise Unsupported(f"{o.extra} orb at x={o.x} ({p.mode} {p.speed}, size {p.size}): not measured")
        p.used.add(i)
        p.buffered = False
        if o.extra == "green":
            p.upside_down = not p.upside_down
        p.y_vel = p.sign * v
        p.on_ground = False
