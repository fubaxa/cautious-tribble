"""Replay a real-game trace's inputs in the simulator and report every step where it differs.

Parts the simulator can't do yet (other game modes, missing mechanics) are skipped: the simulator
is put back into the game's state on the next cube step standing on the ground and carries on.

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
    """Button 1 (player 1) held state for the step ending at `tick`."""
    state = None
    for t, down, button, p2 in inputs:
        if t > tick:   # an input stamped with tick T is applied in the step that ends at T
            break
        if button == 1:   # both keys drive player 1 outside two-player mode
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
    if abs(real.size - p.size) > 1e-6:
        diffs.append(("size", real.size, p.size))
    if MODES.get(real.mode) != p.mode:
        diffs.append(("mode", MODES.get(real.mode, real.mode), p.mode))
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


def resync(sim, real, holding):
    """Put the simulator in the game's state at `real` (after a part it can't simulate yet)."""
    p = sim.player
    p.x, p.y, p.y_vel = real.x, real.y, real.y_vel
    p.speed, p.size = C.SPEEDS[real.speed], (1.0 if real.size > 0.8 else 0.6)
    p.upside_down, p.on_ground = real.upside_down, real.on_ground
    p.holding, p.buffered = bool(holding), real.jump_buffered
    p.dead = False
    p.steps = 2
    p.last_block = None
    p.dashing = False
    p.hold_blocked = False
    p.mode = MODES[real.mode]


def run(trace_path, level_name, attempt_no=None, save=None, details=3):
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
        stats = collections.Counter()
        segments = []            # (first tick, last matched tick, matched steps, why it ended)
        history = []
        seg_start, matched, skipping, shown = att.steps[0].tick, 0, None, 0

        def end(tick, why):
            segments.append((seg_start, tick, matched, why))

        prev = None
        for real in att.steps:
            hold = held_at(att.inputs, real.tick)
            # At the end of a level the sprite stops while the end animation plays: not physics.
            if prev is not None and real.x == prev.x and real.step_in_frame == 1 and prev.step_in_frame == 1:
                if not skipping:
                    end(real.tick, "level end reached")
                skipping = 10 ** 9
                break
            prev = real
            if skipping:
                # Resume on the first cube step standing on something, a while after the stop.
                if real.mode in MODES and real.on_ground and real.tick >= skipping and real.step_in_frame == 1:
                    resync(sim, real, hold)
                    seg_start, matched, skipping, history = real.tick, 0, None, []
                continue
            if real.mode not in MODES:
                end(real.tick, f"game mode {real.mode} not implemented")
                skipping = real.tick
                continue
            try:
                p = sim.step(hold)
            except Unsupported as e:
                end(real.tick, str(e))
                skipping = real.tick + 2 * RESYNC_STEPS
                continue
            history.append((real, fmt_sim(p)))
            d = compare(real, p, stats)
            if not d and p.dead and att.death_tick != real.tick:
                d = [("death", att.death_tick, real.tick)]
            if d:
                why = "DIFFERENCE: " + ", ".join(f"{n} real={a!r} sim={b!r}" for n, a, b in d)
                end(real.tick, why)
                if shown < details:
                    shown += 1
                    print(f"  difference at tick {real.tick} (attempt {att.number}):")
                    for rs, ss in history[-3:]:
                        print(f"    tick {rs.tick} step-in-frame {rs.step_in_frame}")
                        print(f"       real {fmt_real(rs)}")
                        print(f"       sim  {ss}")
                skipping = real.tick + 2 * RESYNC_STEPS
                continue
            matched += 1
            stats["matched"] += 1
            if p.dead:
                end(real.tick, "died on the same step as the game")
                break
        else:
            if not skipping:
                end(att.steps[-1].tick, "end of the attempt")
        if not segments or (skipping is None and not segments[-1][3].startswith(("level end", "died", "end of"))):
            pass
        cube = sum(1 for st in att.steps if st.mode in MODES)
        print(f"attempt {att.number}: {stats['matched']} of {cube} cube and ball steps matched "
              f"({stats['yvel_near']} yVel and {stats['y_near']} y near misses), {len(att.steps)} steps in total")
        for a0, a1, n, why in segments:
            print(f"   ticks {a0:6d}-{a1:6d}: {n:5d} matched; {why[:150]}")


MODES = {0: "cube", 4: "ball"}   # trace mode bits the simulator can play
RESYNC_STEPS = 60  # after a stop, wait this many steps before resuming


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("trace")
    ap.add_argument("--level", required=True, help="level name in CCLocalLevels.dat")
    ap.add_argument("--attempt", type=int)
    ap.add_argument("--save", help="path to CCLocalLevels.dat (default: GD's save folder)")
    a = ap.parse_args()
    run(a.trace, a.level, a.attempt, a.save)
