"""Replay a real-game trace's inputs in the simulator and report every step where it differs.

Parts the simulator can't do yet (other game modes, missing mechanics) are skipped: the simulator
is put back into the game's state on the next cube or ball step standing on the ground (or any
wave step) and carries on.

Older traces (v1-v4) work too: deaths and inputs are stamped correctly in every version, and the
position on lag frames comes from the hitbox. Their interaction rows (O/U) are a step early, but
the diff doesn't use them.

    python -m tools.tracediff <trace.csv> --level <local level name> [--attempt N]

Compares, per step: x (exact on single-step frames; posX within 1e-3 otherwise), y, yVel, xVel,
upside-down, on-ground and death. Stops at the first difference and prints both states around it.
"""
import argparse
import os
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
    if real.step_in_frame == 1:
        # x and y are the sprite position: exact, but only updated on a frame's first step.
        if real.y != p.y and ulps32(real.y, p.y) <= 1:
            stats["y_near"] += 1
            p.y = real.y
        if real.x != p.x:
            diffs.append(("x", real.x, p.x))
        if real.y != p.y:
            diffs.append(("y", real.y, p.y))
    else:
        # Later steps of a lag frame: compare the hitbox centre instead.
        if abs(real.pos_x - p.x) > 1e-3:
            diffs.append(("posX", real.pos_x, p.x))
        if abs(real.pos_y - p.y) > 1e-3:
            diffs.append(("posY", real.pos_y, p.y))
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
            f"upside={int(p.upside_down)} hold={int(p.holding)} dead={int(p.dead)} {p.killer}")


def resync(sim, real, holding, att=None, catch=True):
    """Put the simulator in the game's state at `real` (after a part it can't simulate yet)."""
    p = sim.player
    # The wave's floor and ceiling come from the last wave portal used.
    wave_p = [e for e in (att.events if att else []) if e[0] == "P" and e[3] == "660" and int(e[1]) <= real.tick]
    if wave_p:
        p.area_bottom = C.wave_area_bottom(float(wave_p[-1][5]))
    elif att and att.steps and att.steps[0].x != 0.0 and att.steps[0].mode == 8:
        # Started from a wave start position: it sets the area like a portal at its y (guess).
        p.area_bottom = C.wave_area_bottom(att.steps[0].y)
    else:
        p.area_bottom = C.GROUND_Y
    p.x, p.y, p.y_vel = real.x, real.y, real.y_vel
    if real.step_in_frame != 1:
        p.x, p.y = real.pos_x, real.pos_y
    p.speed, p.size = C.SPEEDS[real.speed], (1.0 if real.size > 0.8 else 0.6)
    p.upside_down, p.on_ground = real.upside_down, real.on_ground
    p.holding, p.buffered = bool(holding), real.jump_buffered
    p.dead = False
    p.steps = 2
    p.last_block = None
    p.dashing = False
    p.hold_blocked = False
    p.on_slope, p.slope_capped = real.on_slope and real.mode == 0, False
    if catch:
        sim.triggers.catch_up(p)

    p.mode = MODES[real.mode]


def run(trace_path, level_name, attempt_no=None, save=None, details=3):
    tr = load(trace_path)
    if tr.version < 5:
        print(f"(trace v{tr.version}: old format, see the note at the top of tools/tracediff.py)")
    # a converted .json keeps the layout a trace was recorded on, after the level is edited
    level = Level.load(level_name) if level_name.endswith(".json") else Level.load_local(level_name, save)
    attempts = [a for a in tr.attempts if attempt_no in (None, a.number)]
    # A practice checkpoint restores the player's snap reference as it was when it was saved:
    # remember it per tick from the attempts replayed so far.
    snap_at = {}
    for att in attempts:
        if att.practice and not os.environ.get("PRACTICE"):
            print(f"attempt {att.number}: practice, skipped")
            continue
        if not att.steps:
            continue
        sim = Sim(level, start_speed=C.SPEEDS[att.steps[0].speed])
        stats = collections.Counter()
        segments = []            # (first tick, last matched tick, matched steps, why it ended)
        history = []
        seg_start, matched, skipping, shown = att.steps[0].tick, 0, None, 0

        def end(tick, why):
            segments.append((seg_start, tick, matched, why))

        prev = None
        frame_x = None
        first = att.steps[0]
        # The step that dies keeps the tick of the step before it (the progress doesn't advance),
        # then the game repeats it: the death step is the last row that moved.
        death_row = None
        if att.death_tick is not None:
            for k in range(len(att.steps) - 1, 0, -1):
                a_, b_ = att.steps[k], att.steps[k - 1]
                if (a_.pos_x, a_.pos_y) != (b_.pos_x, b_.pos_y):
                    death_row = att.steps[k]
                    break
        from_first = first.mode in MODES
        if from_first:
            # Begin in the game's state at the first step: covers start positions and the level's
            # start settings (mini, gravity, ...), which the simulator doesn't read yet.
            resync(sim, first, held_at(att.inputs, first.tick), att, catch=first.x != 0.0)
            sim.player.steps = 1
            saved = snap_at.get(first.tick)
            if att.practice and saved and abs(saved[0] - first.pos_x) < 1e-3:
                sim.player.last_block, sim.player.last_diff, sim.player.last_block_x = saved[1:]
            elif att.practice and sim.player.on_ground and sim.player.mode in ("cube", "ball"):
                sim._track_standing_block(sim.player)   # respawned standing: the block under it
        for real in att.steps:
            hold = held_at(att.inputs, real.tick)
            if real is first and from_first:
                history.append((real, fmt_sim(sim.player)))
                prev = real
                continue
            # At the end of a level the sprite stops while the end animation plays: not physics.
            # (The sprite x only changes once per frame: compare with the previous frame's.)
            if real.step_in_frame == 1 and frame_x is not None and real.x == frame_x                     and real.pos_x != real.x:
                if not skipping:
                    end(real.tick, "level end reached")
                skipping = 10 ** 9
                break
            prev = real
            if real.step_in_frame == 1:
                frame_x = real.x
            if skipping:
                # Resume on the first cube step standing on something, a while after the stop.
                if real.mode in MODES and (real.on_ground or real.mode == 8) and real.tick >= skipping \
                        and real.step_in_frame == 1:
                    resync(sim, real, hold, att)
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
            if not d and p.dead and real is not death_row:
                d = [("death", att.death_tick, f"{real.tick} ({p.killer})")]
            if not d and not p.dead and real is death_row:
                d = [("death", real.tick, "none")]
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
            snap_at.setdefault(real.tick, (p.x, p.last_block, p.last_diff, p.last_block_x))
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
        print(f"attempt {att.number}: {stats['matched']} of {cube} cube, ball and wave steps matched "
              f"({stats['yvel_near']} yVel and {stats['y_near']} y near misses), {len(att.steps)} steps in total")
        for a0, a1, n, why in segments:
            print(f"   ticks {a0:6d}-{a1:6d}: {n:5d} matched; {why[:150]}")


MODES = {0: "cube", 4: "ball", 8: "wave"}   # trace mode bits the simulator can play
RESYNC_STEPS = 60  # after a stop, wait this many steps before resuming


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("trace")
    ap.add_argument("--level", required=True, help="level name in CCLocalLevels.dat")
    ap.add_argument("--attempt", type=int)
    ap.add_argument("--save", help="path to CCLocalLevels.dat (default: GD's save folder)")
    a = ap.parse_args()
    run(a.trace, a.level, a.attempt, a.save)
