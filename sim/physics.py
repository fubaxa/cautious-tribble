"""Headless GD physics, one physics step (1/240 s) at a time. Cube mode only so far.

Step order (each part measured from traces; see constants.py):
  1. the first step after a spawn doesn't move the player
  2. inputs due this step change the held button
  3. cube: jump if holding on the ground, otherwise gravity
  4. move: x += xVel*0.25, y += yVel*0.225 (float32 positions)
  5. floor
  6. objects touched with the new hitbox: portals (they affect the next step), hazards
Not implemented yet: blocks as platforms, snapping, rotation, orbs/pads, other modes.
"""
from dataclasses import dataclass, field

from . import constants as C
from .f32 import f32
from .objects import GRAVITY_PORTAL, HAZARD, SOLID, SPEED_PORTAL, overlap


class Unsupported(Exception):
    """The level or run needs a mechanic the simulator doesn't have yet."""


@dataclass
class Player:
    x: float = 0.0
    y: float = 105.0
    y_vel: float = 0.0
    speed: str = "1x"
    size: float = 1.0  # 1.0 or 0.6 (mini); compared as f32 against the trace
    on_ground: bool = False
    upside_down: bool = False
    holding: bool = False
    dead: bool = False
    steps: int = 0
    used: set = field(default_factory=set)  # one-time objects already activated (by index)

    @property
    def x_vel(self) -> float:
        return C.X_VEL[self.speed]

    @property
    def player_speed(self) -> float:
        return C.PLAYER_SPEED[self.speed]

    @property
    def half(self) -> float:
        return C.PLAYER_SIZE[self.size] / 2

    @property
    def rect(self):
        h = self.half
        return (self.x - h, self.y - h, 2 * h, 2 * h)


class Sim:
    def __init__(self, level, start_speed: str = "1x"):
        self.level = level
        self.objects = [o for o in level.objects if o.kind]
        self.player = Player(speed=start_speed)
        self.player.y = C.GROUND_Y + self.player.half

    def step(self, holding: bool | None = None) -> Player:
        p = self.player
        if holding is not None:
            p.holding = holding
        p.steps += 1
        if p.steps == 1:
            return p  # first step after a spawn: no movement

        g = C.CUBE_GRAVITY[p.speed]
        if p.holding and p.on_ground:
            jump = C.CUBE_JUMP.get(p.speed)
            if jump is None:
                raise Unsupported(f"cube jump at {p.speed} not measured")
            if p.size != 1.0:
                jump *= C.MINI_JUMP_FACTOR
            p.y_vel = -jump if p.upside_down else jump
            p.on_ground = False
        elif not p.on_ground:
            # GD's yVel stays on multiples of 0.001 (accumulating 0.216 in double drifts off them).
            p.y_vel = round(p.y_vel + g if p.upside_down else p.y_vel - g, 3)
            p.y_vel = max(p.y_vel, C.CUBE_MAX_FALL) if not p.upside_down else p.y_vel

        p.x = f32(p.x + p.x_vel * C.X_STEP)
        p.y = f32(p.y + p.y_vel * C.Y_STEP)

        floor = C.GROUND_Y + p.half
        if not p.upside_down and p.y <= floor:
            p.y = floor
            p.y_vel = 0.0
            p.on_ground = True

        r = p.rect
        for i, o in enumerate(self.objects):
            if o.rotation % 360 and o.kind in (SPEED_PORTAL, GRAVITY_PORTAL):
                if overlap(r, o.rect):
                    raise Unsupported(f"rotated {o.kind} portal {o.id} at x={o.x}: needs oriented boxes")
                continue
            if not overlap(r, o.rect):
                continue
            if o.kind == SPEED_PORTAL:
                p.speed = C.SPEED_PORTALS[o.id]
            elif o.kind == GRAVITY_PORTAL:
                flip = o.extra == "flip"
                if flip != p.upside_down:
                    p.upside_down = flip
                    p.y_vel *= C.GRAVITY_FLIP_YVEL_FACTOR
                    p.on_ground = False
            elif o.kind == HAZARD:
                p.dead = True
            elif o.kind == SOLID:
                raise Unsupported(f"block {o.id} at x={o.x} y={o.y}: block collision not implemented")
        return p
