"""Headless GD physics, one physics step (1/240 s) at a time. Cube mode only so far.

Order inside a step (each part measured from traces; see NOTES.md and constants.py):
  1. the first step after a spawn doesn't move the player
  2. standing is re-checked; a held button on the ground jumps (this step already moves with the
     jump velocity); otherwise gravity applies while airborne
  3. move: x += xVel*0.25, y += yVel*0.225 (float32 positions)
  4. floor and block tops: landing, with the x snap between consecutive blocks
  5. the step's input arrives (after the move)
  6. objects touched with the new hitbox: portals, pads, orbs (they change the next step), hazards
  7. a new press on the ground jumps: yVel is set now, y first changes on the next step
Anything not measured yet raises Unsupported instead of guessing: block sides and ceilings,
slopes, rotated objects, other game modes, most orbs outside the measured speed.
"""
from dataclasses import dataclass, field

from . import constants as C
from .f32 import f32
from .objects import (GRAVITY_PORTAL, HAZARD, MODE_PORTAL, ORB, PAD, SIZE_PORTAL, SOLID, SPEED_PORTAL,
                      overlap)

EPS = 1e-4


class Unsupported(Exception):
    """The level or run needs a mechanic the simulator doesn't have yet."""


@dataclass
class Player:
    x: float = 0.0
    y: float = 105.0
    y_vel: float = 0.0
    speed: str = "1x"
    size: float = 1.0  # 1.0 or 0.6 (mini)
    on_ground: bool = False
    upside_down: bool = False
    holding: bool = False
    buffered: bool = False        # a press that hasn't been used by a jump or an orb yet
    dashing: bool = False         # in a dash orb's dash: flies straight while the button is held
    dead: bool = False
    steps: int = 0
    used: set = field(default_factory=set)  # one-time objects already activated (by index)
    last_block: int | None = None  # index of the block last landed on (None after the floor)
    last_diff: float = 0.0         # player x - that block's x at the landing

    @property
    def x_vel(self) -> float:
        return C.X_VEL[self.speed]

    @property
    def half(self) -> float:
        return C.PLAYER_SIZE[self.size] / 2

    @property
    def rect(self):
        h = self.half
        return (self.x - h, self.y - h, 2 * h, 2 * h)

    @property
    def sign(self) -> float:
        """+1 with normal gravity, -1 upside down: yVel * sign is 'up' relative to gravity."""
        return -1.0 if self.upside_down else 1.0


class Sim:
    def __init__(self, level, start_speed: str = "1x"):
        self.level = level
        self.objects = [o for o in level.objects if o.kind]
        self.solids = [(i, o) for i, o in enumerate(self.objects) if o.kind == SOLID and not o.rotation % 360]
        self.player = Player(speed=start_speed)
        self.player.y = C.GROUND_Y + self.player.half

    # --- helpers ---

    def _jump_value(self, p) -> float:
        jump = C.CUBE_JUMP.get(p.speed)
        if jump is None:
            raise Unsupported(f"cube jump at {p.speed} not measured")
        return jump * C.MINI_JUMP_FACTOR if p.size != 1.0 else jump

    def _jump(self, p):
        p.y_vel = p.sign * self._jump_value(p)
        p.on_ground = False
        p.buffered = False

    def _supported(self, p) -> bool:
        """Is there a surface exactly under the player (in the direction of gravity)?"""
        if not p.upside_down and p.y <= C.GROUND_Y + p.half:
            return True
        left, right = p.x - p.half, p.x + p.half
        foot = p.y - p.sign * p.half
        for _, o in self.solids:
            ox, oy, ow, oh = o.rect
            if left < ox + ow and ox < right:
                surface = oy + oh if not p.upside_down else oy
                if abs(surface - foot) < EPS:
                    return True
        return False

    def _collide_solids(self, p, prev_y, was_airborne):
        """Landing on the floor or on a block's top (its underside when upside down)."""
        floor = C.GROUND_Y + p.half
        if not p.upside_down and p.y <= floor:
            p.y, p.y_vel, p.on_ground = floor, 0.0, True
            p.last_block = None
            return
        r = p.rect
        prev_foot = prev_y - p.sign * p.half
        best = None
        for i, o in self.solids:
            if not overlap(r, o.rect):
                continue
            ox, oy, ow, oh = o.rect
            surface = oy + oh if not p.upside_down else oy
            coming_down = p.sign * p.y_vel <= 0
            above = p.sign * (prev_foot - surface) >= -EPS
            if not (coming_down and above):
                raise Unsupported(f"contact with the side or underside of block {o.id} at "
                                  f"x={o.x} y={o.y}: rule not measured")
            if best is None or p.sign * (surface - best[2]) > 0:
                best = (i, o, surface)
        if best is None:
            return
        i, o, surface = best
        p.y = f32(surface + p.sign * p.half)
        p.y_vel, p.on_ground = 0.0, True
        if was_airborne and p.last_block is not None and p.last_block != i:
            # Snap: GD predicts x from where the player stood on the previous block and moves the
            # player toward that spot, by at most 1 unit (0.5x, 1x, 4x) or 2 (2x, 3x).
            predicted = p.last_diff + o.x
            shift = C.SNAP_SHIFT[p.speed]
            d = predicted - p.x
            p.x = f32(predicted if abs(d) <= shift else p.x + (shift if d > 0 else -shift))
        if was_airborne or p.last_block != i:
            p.last_block, p.last_diff = i, p.x - o.x

    # --- one physics step ---

    def step(self, holding: bool | None = None) -> Player:
        p = self.player
        p.steps += 1
        if p.steps == 1:
            if holding is not None:
                p.holding = holding
            return p

        if p.on_ground and not self._supported(p):
            p.on_ground = False
        was_airborne = not p.on_ground
        if p.dashing:
            p.y_vel = 0.0
        elif p.on_ground and p.holding:
            self._jump(p)
        elif not p.on_ground:
            g = C.CUBE_GRAVITY[p.speed]
            # GD's yVel stays on multiples of 0.001 (accumulating 0.216 in double drifts off them).
            p.y_vel = round(p.y_vel - p.sign * g, 3)
            if p.sign * p.y_vel < -C.CUBE_MAX_FALL:
                p.y_vel = -p.sign * C.CUBE_MAX_FALL

        prev_y = p.y
        p.x = f32(p.x + p.x_vel * C.X_STEP)
        p.y = f32(p.y + p.y_vel * C.Y_STEP)
        self._collide_solids(p, prev_y, was_airborne)

        pressed = False
        if holding is not None:
            pressed = holding and not p.holding
            if pressed:
                p.buffered = True
            elif not holding:
                p.buffered = False
                p.dashing = False   # the dash ends on release; gravity returns on the next step
            p.holding = holding

        r = p.rect
        for i, o in enumerate(self.objects):
            if o.kind == SOLID:
                continue
            if o.rotation % 360:
                if overlap(r, o.rect):
                    raise Unsupported(f"rotated {o.kind} {o.id} at x={o.x}: needs oriented boxes")
                continue
            if not overlap(r, o.rect):
                continue
            if o.kind == SPEED_PORTAL:
                p.speed = o.extra
            elif o.kind == GRAVITY_PORTAL:
                if o.extra == "toggle":
                    raise Unsupported(f"gravity toggle portal at x={o.x}: not measured")
                flip = o.extra == "flip"
                if flip != p.upside_down:
                    p.upside_down = flip
                    p.y_vel *= C.GRAVITY_FLIP_YVEL_FACTOR
                    p.on_ground = False
            elif o.kind == SIZE_PORTAL:
                p.size = 0.6 if o.extra == "mini" else 1.0   # y is kept; the floor corrects it next step
            elif o.kind == MODE_PORTAL:
                if o.extra != "cube":
                    raise Unsupported(f"{o.extra} portal at x={o.x}: game mode not implemented")
            elif o.kind == HAZARD:
                p.dead = True
            elif o.kind == PAD:
                self._pad(p, i, o)
            elif o.kind == ORB:
                self._orb(p, i, o)
            else:
                raise Unsupported(f"{o.extra or ''} {o.kind} {o.id} at x={o.x} y={o.y}: not implemented")

        if pressed and p.buffered and p.on_ground:
            self._jump(p)
        return p

    def _pad(self, p, i, o):
        if i in p.used:
            return
        if o.extra == "blue":
            v = C.BLUE_PAD_FALL.get(p.size)
            if v is None:
                raise Unsupported(f"blue pad at x={o.x} (size {p.size}): value not measured")
            p.upside_down = not p.upside_down
            p.y_vel = -p.sign * v
        else:
            v = C.PAD_YVEL.get((o.extra, p.size))
            if v is None:
                raise Unsupported(f"{o.extra} pad at x={o.x} (size {p.size}): value not measured")
            p.y_vel = p.sign * v
        p.used.add(i)
        p.on_ground = False

    def _orb(self, p, i, o):
        if not p.buffered or (i in p.used and not o.multi):
            return
        if o.extra == "dash-green":
            # Flies straight (yVel 0 from the next step on) for as long as the button stays held.
            p.used.add(i)
            p.dashing, p.on_ground = True, False
            return
        if o.extra == "blue":
            v = C.BLUE_ORB_FALL.get((p.speed, p.size))
            if v is None:
                raise Unsupported(f"blue orb at x={o.x} ({p.speed}, size {p.size}): not measured")
            p.used.add(i)
            p.buffered = False
            p.upside_down = not p.upside_down
            p.y_vel = -p.sign * v
            p.on_ground = False
            return
        v = C.ORB_YVEL.get((o.extra, p.speed, p.size))
        if v is None:
            raise Unsupported(f"{o.extra} orb at x={o.x} ({p.speed}, size {p.size}): not measured")
        p.used.add(i)
        p.buffered = False
        if o.extra == "green":
            p.upside_down = not p.upside_down
        p.y_vel = p.sign * v
        p.on_ground = False
