"""Replay a real-game trace's inputs in the simulator and report the first step that differs.

    python -m tools.tracediff <trace.csv> --level <local level name> [--attempt N]

Compares, per step: x (exact on single-step frames; posX within 1e-3 otherwise), y, yVel, xVel,
upside-down, on-ground and death. Stops at the first difference and prints both states around it.
"""
import argparse
import collections
import struct
import sys

from sim import constants as C
from sim.level import Level
from sim.physics import Sim, Unsupported
from sim.trace import load


def held_at(inputs, tick):
    """Button 1 (player 1) held state for the step ending at `tick`: inputs stamped before it."""
    state = None
    for t, down, button, p2 in inputs:
        if t >= tick:
            break
        if button == 1 and not p2:
            state = down
    return state


def ulps(a: float, b: float) -> int:
    ia = struct.unpack("<q", struct.pack("<d", a))[0]
    ib = struct.unpack("<q", struct.pack("<d", b))[0]
    return abs(ia - ib)


def ulps32(a: float, b: float) -> int:
    ia = struct.unpack("<i", struct.pack("<f", a))[0]
    ib = struct.unpack("<i", struct.pack("<f", b))[0]
    return abs(ia - ib)


# Open issue (see NOTES.md): on ~5% of steps GD's yVel is 1 ulp off round(v, 3) and y is 1 float32
# ulp off f32(y + yVel*0.225); no simple formula reproduces either. Such near misses are counted and
# the simulator carries on from the game's value, so later (real) differences still show.
NEAR_ULPS = 2


def compare(real, p, stats):
    diffs = []
    if real.y_vel != p.y_vel and ulps(real.y_vel, p.y_vel) <= NEAR_ULPS:
        stats["yvel_near"] += 1
        p.y_vel = real.y_vel
    if real.y != p.y and ulps32(real.y, p.y) <= 1:
        stats["y_near"] += 1
        p.y = real.y
    if real.step_in_frame == 1:
        if real.x != p.x:
            diffs.append(("x", real.x, p.x))
    elif abs(real.pos_x - p.x) > 1e-3:
        diffs.append(("posX", real.pos_x, p.x))
    if real.y != p.y:
        diffs.append(("y", real.y, p.y))
    if real.y_vel != p.y_vel:
        diffs.append(("yVel", real.y_vel, p.y_vel))
    if real.x_vel != p.x_vel:
        diffs.append(("xVel", real.x_vel, p.x_vel))
    if real.upside_down != p.upside_down:
        diffs.append(("upsideDown", real.upside_down, p.upside_down))
    if real.on_ground != p.on_ground:
        diffs.append(("onGround", real.on_ground, p.on_ground))
    return diffs


def fmt_real(s):
    return (f"x={s.x!r} y={s.y!r} yVel={s.y_vel!r} xVel={s.x_vel!r} ground={int(s.on_ground)} "
            f"upside={int(s.upside_down)} mode={s.mode} hold={int(s.holding)}")


def fmt_sim(p):
    return (f"x={p.x!r} y={p.y!r} yVel={p.y_vel!r} xVel={p.x_vel!r} ground={int(p.on_ground)} "
            f"upside={int(p.upside_down)} hold={int(p.holding)} dead={int(p.dead)}")


def run(trace_path, level_name, attempt_no=None, save=None):
    tr = load(trace_path)
    if tr.version < 5:
        sys.exit(f"trace v{tr.version}: needs v5 or later (event ticks and posX)")
    level = Level.load_local(level_name, save)
    attempts = [a for a in tr.attempts if attempt_no in (None, a.number)]
    for att in attempts:
        if att.practice:
            print(f"attempt {att.number}: practice, skipped")
            continue
        sim = Sim(level, start_speed=C.SPEEDS[att.steps[0].speed])
        history = []
        result = None
        stats = collections.Counter()
        for real in att.steps:
            if real.mode != 0:
                result = f"stopped at tick {real.tick}: game mode {real.mode} not implemented"
                break
            try:
                p = sim.step(held_at(att.inputs, real.tick))
            except Unsupported as e:
                result = f"stopped at tick {real.tick}: {e}"
                break
            history.append((real, fmt_sim(p)))
            d = compare(real, p, stats)
            if not d and p.dead and att.death_tick != real.tick:
                d = [("death", att.death_tick, real.tick)]
            if d:
                result = f"FIRST DIFFERENCE at tick {real.tick}: " + ", ".join(
                    f"{n} real={a!r} sim={b!r}" for n, a, b in d)
                print(f"attempt {att.number}: {len(history) - 1} steps matched ({stats['yvel_near']} yVel and {stats['y_near']} y near misses)")
                print("  " + result)
                for rs, ss in history[-4:]:
                    print(f"  tick {rs.tick} step-in-frame {rs.step_in_frame}")
                    print(f"     real {fmt_real(rs)}")
                    print(f"     sim  {ss}")
                result = "diff"
                break
            if p.dead:
                result = f"died at tick {real.tick}, same as the game"
                break
        else:
            result = f"all {len(att.steps)} steps matched"
        if result != "diff":
            print(f"attempt {att.number}: {len(history)} steps matched ({stats['yvel_near']} yVel and {stats['y_near']} y near misses); {result}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("trace")
    ap.add_argument("--level", required=True, help="level name in CCLocalLevels.dat")
    ap.add_argument("--attempt", type=int)
    ap.add_argument("--save", help="path to CCLocalLevels.dat (default: GD's save folder)")
    a = ap.parse_args()
    run(a.trace, a.level, a.attempt, a.save)
