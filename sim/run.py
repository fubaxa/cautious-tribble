"""A run from the level start, as GD plays it: ticks, inputs at ticks, the level end.

GD counts time in ticks (half-steps, m_currentProgress); a physics step advances it by 2. The
attempt starts at tick 2 with a frozen step (the player doesn't move); an input stamped with tick
T is applied in the step that ends at T (the same convention as the traces and the macros).
"""
from __future__ import annotations

from . import constants as C
from .physics import Sim

# GD ends the level (and starts the end animation) about 40 past the furthest object: Every End 2's
# last object is at 136725, the last physics step was at 136766.16 (the one before at 136764.86).
END_PAST_LAST_OBJECT = 40.0


def end_x(level) -> float | None:
    last = getattr(level, "last_x", None)
    return None if last is None else last + END_PAST_LAST_OBJECT


def new_sim(level) -> Sim:
    """The simulator at tick 2, the frozen first step of a fresh attempt."""
    s = level.settings
    sim = Sim(level, s.get("speed") or "1x")
    p = sim.player
    p.mode = s.get("mode") or "cube"
    if p.mode not in ("cube", "ball", "wave"):
        raise ValueError(f"the level starts in {p.mode} mode, which the simulator can't play yet")
    p.size = 0.6 if s.get("mini") else 1.0
    p.upside_down = bool(s.get("flipped"))
    p.y = C.GROUND_Y + p.half
    p.steps = 1
    sim.tick = 2
    return sim


def advance(sim, holding: bool):
    """One physics step; returns the player."""
    sim.tick += 2
    return sim.step(holding)


def play(level, presses, max_tick=None):
    """Play inputs [(tick, down)] from the start. Returns (sim, outcome) with outcome 'end',
    'dead' or 'timeout'."""
    sim = new_sim(level)
    ex = end_x(level)
    inputs = sorted(presses)
    k, held = 0, False
    limit = max_tick or 10 ** 9
    while sim.tick < limit:
        nxt = sim.tick + 2
        while k < len(inputs) and inputs[k][0] <= nxt:
            held = inputs[k][1]
            k += 1
        p = advance(sim, held)
        if p.dead:
            return sim, "dead"
        if ex is not None and p.x >= ex:
            return sim, "end"
    return sim, "timeout"
