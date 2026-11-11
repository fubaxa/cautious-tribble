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
slopes, rotated objects, other game modes, most orbs outside the measured speed.
"""
from dataclasses import dataclass, field

from . import constants as C
from .f32 import f32
from .objects import (GRAVITY_PORTAL, HAZARD, MODE_PORTAL, ORB, PAD, SIZE_PORTAL, SLOPE, SOLID,
                      SPEED_PORTAL, overlap)

EPS = 1e-4


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
    dead: bool = False
    killer: str = ""              # what killed the player (for reports)
    steps: int = 0
    used: set = field(default_factory=set)  # one-time objects already activated (by index)
    last_block: int | None = None  # index of the block last landed on (None after the floor)
    last_diff: float = 0.0         # player x - that block's x at the landing

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

    def _supported(self, p) -> bool:
        """Is there a surface exactly under the player (in the direction of gravity)?"""
        if not p.upside_down and p.y <= C.GROUND_Y + p.half:
            return True
        if p.mode == "wave":   # the wave slides only on the floor; blocks kill it
            return False
        left, right = p.x - p.half, p.x + p.half
        foot = p.y - p.sign * p.half
        for _, o in self.solids:
            ox, oy, ow, oh = o.rect
            if left < ox + ow and ox < right:
                surface = oy + oh if not p.upside_down else oy
                if abs(surface - foot) < EPS:
                    return True
        return False

    def _hazard_rect(self, p):
        """The box hazards touch: the body box, but smaller for the wave."""
        if p.mode != "wave":
            return p.body_rect
        size = p.size
        if not self.level.settings.get("physics", {}).get("enable22Changes", False):
            size = 1.0   # pre-2.2 levels: the mini wave touches hazards with the normal box
        return p.box(C.WAVE_HAZARD_BOX[size])

    def _collide_solids(self, p, prev_y, was_airborne):
        """Landing on the floor or on a block's top (its underside when upside down)."""
        floor = C.GROUND_Y + p.half
        if not p.upside_down and p.y <= floor:
            # The wave's yVel becomes 0 only when the move went past the floor; landing exactly on
            # it keeps the yVel for that step (it is 0 from the next one).
            if p.mode != "wave" or p.y < floor:
                p.y_vel = 0.0
            p.y, p.on_ground = floor, True
            p.last_block = None
            return
        if p.mode == "wave":
            ceiling = C.WAVE_CEILING_Y - p.half
            if not p.upside_down and p.y >= ceiling:
                if p.y > ceiling:
                    p.y_vel = 0.0
                p.y = ceiling
                return
            # Any contact of the wave's block box (7.2x7.2 at both sizes) with a block kills it,
            # from any side. D blocks: not tested.
            br = p.box(C.WAVE_BLOCK_BOX[p.size])
            for _, o in self.solids:
                if overlap(br, o.rect):
                    p.dead, p.killer = True, f"block {o.id} at x={o.x} y={o.y}"
                    return
            return
        r = p.body_rect
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
                if p.mode == "wave" and not above:
                    # Wave deaths against blocks report no killing object (10 in Sonic Wave 2).
                    side = p.sign * (prev_foot - surface) < -EPS and p.sign * ((prev_y + p.sign * p.half) - (oy if not p.upside_down else oy + oh)) <= EPS
                    if not side:
                        raise Unsupported(f"wave touching the underside of block {o.id} at x={o.x}: not measured")
                    p.dead, p.killer = True, f"side of block {o.id} at x={o.x} y={o.y}"
                    return
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

        # In wave mode GD's on-ground flag stays set after the floor is first touched, in the air
        # too (it only feeds the trace); whether the wave slides is decided by the floor itself.
        if p.on_ground and p.mode != "wave" and not self._supported(p):
            p.on_ground = False
        was_airborne = not p.on_ground
        move_v = None
        if p.mode == "wave":
            # Held = up (relative to gravity). Standing on the floor without holding: no movement.
            on_floor = not p.upside_down and p.y <= C.GROUND_Y + p.half
            on_ceiling = not p.upside_down and p.y >= C.WAVE_CEILING_Y - p.half
            if (on_floor and not p.holding) or (on_ceiling and p.holding):
                p.y_vel, move_v = 0.0, 0.0
            else:
                d = p.sign if p.holding else -p.sign
                # The trace shows yVel rounded to 3 decimals; the move uses the exact xVel.
                p.y_vel, move_v = d * round(p.x_vel, 3), d * p.x_vel
        elif p.dashing:
            p.y_vel = 0.0
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
        self._collide_solids(p, prev_y, was_airborne)
        if p.dead:
            return p

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
        for i, o in enumerate(self.objects):
            if o.kind == SOLID:
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
            if not overlap(hr, o.rect):
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
                if o.extra != p.mode:
                    if "wave" in (o.extra, p.mode):
                        # Into or out of the wave: yVel is halved (cube -1.512 -> wave entry
                        # -0.756; wave -5.193 -> cube -2.5965), in the air or not.
                        p.y_vel *= C.GRAVITY_FLIP_YVEL_FACTOR
                        p.on_ground = False
                    elif not p.on_ground:
                        raise Unsupported(f"{o.extra} portal at x={o.x} entered in the air: not measured")
                    p.mode = o.extra
            elif o.kind == HAZARD:
                p.dead, p.killer = True, f"hazard {o.id} at x={o.x} y={o.y}"
            elif o.kind == PAD:
                self._pad(p, i, o)
            elif o.kind == ORB:
                self._orb(p, i, o)
            else:
                raise Unsupported(f"{o.extra or ''} {o.kind} {o.id} at x={o.x} y={o.y}: not implemented")

        if pressed and p.buffered and p.on_ground and p.mode != "wave":
            self._jump(p)
        return p

    def _pad(self, p, i, o):
        if i in p.used:
            return
        if o.extra == "spider":
            self._spider_pad(p, o)
            p.used.add(i)
            return
        if p.mode != "cube":
            raise Unsupported(f"{o.extra} pad at x={o.x} in {p.mode} mode: not measured")
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
        for _, b in self.solids:
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
        if p.mode != "cube":
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
