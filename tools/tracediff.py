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


def held_at(inputs, tick, key=None):
    """Button 1 held state for the step ending at `tick`. key None: either key (outside 2-player
    mode both keys drive the player(s)); False / True: only the P1 / P2 key (2-player levels)."""
    state = None
    for t, down, button, p2 in inputs:
        if t > tick:   # an input stamped with tick T is applied in the step that ends at T
            break
        if button == 1 and (key is None or p2 == key):
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
    # The ship's on-ground flag doesn't affect its motion and GD sets it inconsistently on the
    # side away from gravity (set or not by size and level; see NOTES): not compared for the ship.
    # In dual GD keeps the flag set while falling off a ledge (45 of 45): not compared either.
    # Upside down, GD keeps the flag set while a cube falls off a ledge (142 of 144; with normal
    # gravity never): only the flag, the fall matches, so it isn't compared then either.
    if real.on_ground != p.on_ground and not (real.mode in (1, 2) and p.mode in ("ship", "ufo")) \
            and not real.dual and not (real.upside_down and real.on_ground and not p.on_ground):
        diffs.append(("onGround", real.on_ground, p.on_ground))
    return diffs


def fmt_real(s):
    return (f"x={s.x!r} y={s.y!r} yVel={s.y_vel!r} xVel={s.x_vel!r} ground={int(s.on_ground)} "
            f"upside={int(s.upside_down)} mode={s.mode} hold={int(s.holding)}")


def fmt_sim(p):
    return (f"x={p.x!r} y={p.y!r} yVel={p.y_vel!r} xVel={p.x_vel!r} ground={int(p.on_ground)} "
            f"upside={int(p.upside_down)} hold={int(p.holding)} dead={int(p.dead)} {p.killer}")


def resync(sim, real, holding, att=None, catch=True, respawn=False):
    """Put the simulator in the game's state at `real` (after a part it can't simulate yet)."""
    p = sim.player
    # The wave's floor and ceiling come from the last wave portal used.
    # (and the ship's from the last ship portal: the same rule)
    wave_p = [e for e in (att.events if att else []) if e[0] == "P" and e[3] in ("660", "13", "111", "1331", "286") and int(e[1]) <= real.tick]
    if not wave_p and att is not None and att.steps and att.steps[0].tick > 4:
        # started at a checkpoint: the latest band portal any attempt touched by this tick
        wave_p = [e for t, e in getattr(att, "band_events", []) if t <= real.tick][-1:]
    p.area_height = C.WAVE_AREA_HEIGHT
    if wave_p:
        p.area_bottom = C.wave_area_bottom(float(wave_p[-1][5]))
        ex = float(wave_p[-1][4])
        near = [o for o in sim.objects if o.kind == "mode" and abs(o.x - ex) < 1]
        if near and near[0].free:   # Free Mode portal: ground floor, no ceiling
            p.area_bottom, p.area_height = C.GROUND_Y, float("inf")
    elif att and att.steps and att.steps[0].x != 0.0 and att.steps[0].mode == 8:
        # Started from a wave start position: it sets the area like a portal at its y (guess).
        p.area_bottom = C.wave_area_bottom(att.steps[0].y)
    elif MODES.get(real.mode) in ("ship", "wave", "ufo", "spider"):
        # No portal event in this attempt (it started after the portal, e.g. from a checkpoint):
        # the last portal of this mode the player has passed in the level.
        kind = MODES[real.mode]
        passed = [o for o in sim.objects if o.kind == "mode" and o.extra == kind and o.x <= real.x]
        last = max(passed, key=lambda o: o.x) if passed else None
        p.area_bottom = C.wave_area_bottom(last.y) if last and not last.free else C.GROUND_Y
        if last and last.free:
            p.area_height = float("inf")
    else:
        p.area_bottom = C.GROUND_Y
    kind = MODES.get(real.mode)
    if real.dual and kind not in ("ship", "wave", "ufo", "spider") and p.area_height != float("inf") \
            and not (p.area_bottom <= real.y <= p.area_bottom + p.area_height):
        # dual: the band of the last band-setting portal (flying modes, dual) that holds the player
        fits = [o for o in sim.objects if (o.kind == "dual" and o.extra == "on" or o.kind == "mode" and
                o.extra in ("ship", "wave", "ufo", "spider")) and o.x <= real.x + 30 and not o.free
                and C.wave_area_bottom(o.y) <= real.y <= C.wave_area_bottom(o.y) + C.WAVE_AREA_HEIGHT]
        if fits:
            p.area_bottom = C.wave_area_bottom(max(fits, key=lambda o: o.x).y)
        else:
            p.area_height = float("inf")
    if kind in ("ship", "wave", "ufo", "spider") and p.area_height != float("inf") \
            and not (p.area_bottom <= real.y <= p.area_bottom + p.area_height):
        # The player is outside that band (moved there without a logged portal, e.g. a teleport
        # into a portal at once, Orochi buff 3): the last portal of this mode passed in the level
        # whose band holds the player.
        fits = [o for o in sim.objects if o.kind == "mode" and o.extra == kind and o.x <= real.x + 30
                and not o.free and C.wave_area_bottom(o.y) <= real.y <= C.wave_area_bottom(o.y) + C.WAVE_AREA_HEIGHT]
        if fits:
            p.area_bottom = C.wave_area_bottom(max(fits, key=lambda o: o.x).y)
    p.x, p.y, p.y_vel = real.x, real.y, real.y_vel
    if real.step_in_frame != 1:
        p.x, p.y = real.pos_x, real.pos_y
    p.speed, p.size = C.SPEEDS[real.speed], (1.0 if real.size > 0.8 else 0.6)
    p.upside_down, p.on_ground = real.upside_down, real.on_ground
    p.holding, p.buffered = bool(holding), real.jump_buffered
    if MODES.get(real.mode) == "ufo":
        p.buffered = False   # GD keeps that flag while held; a UFO press acts on its own step only
    p.dead = False
    p.force = 0.0
    p.steps = 2
    p.last_block = None
    p.dashing = False
    p.hold_blocked = False
    p.ship_clip = False
    # GD's on-slope flag stays set in the air (Tartarus 14156: set while falling 50 above the slope)
    p.on_slope, p.slope_capped = real.on_slope and real.mode == 0 and real.on_ground, False
    if catch:
        since = None
        if att is not None:
            past = [s for s in att.steps if s.tick <= real.tick]
            first_x = getattr(att, "first_x", None)
            def since(x, past=past, now=real.tick, first_x=first_x):
                hit = next((s for s in past if s.x >= x), None)
                if first_x and past and x < past[0].x:
                    # passed before this attempt began (a checkpoint): when the player first reached
                    # x in any attempt of the trace (the same tick in every one)
                    import bisect
                    k = bisect.bisect_left(first_x[0], x)
                    if k < len(first_x[1]) and first_x[1][k] <= now:
                        # a practice respawn puts the player one step past the checkpoint, the moved
                        # groups stay where they were saved (The Hallucination: a platform one step
                        # behind the sim's right after the respawn)
                        lag = 1 if respawn else 0
                        return max((now - first_x[1][k]) // 2 - lag, 0)
                if past and x < past[0].x and os.environ.get("SINCE_PRIOR"):
                    # experiment (worse: +5,930 against the estimate's +17,525): the timing of the
                    # last earlier attempt that went from x to here
                    x0 = past[0].x
                    for pa in reversed(getattr(att, "prior", ())):
                        a_ = next((s for s in pa.steps if s.x >= x), None)
                        b_ = next((s for s in pa.steps if s.x >= x0), None) if a_ is not None else None
                        if b_ is not None and a_.tick <= b_.tick:
                            return max((b_.tick - a_.tick) // 2 - (1 if respawn else 0), 0)
                if past and x < past[0].x and past[0].x_vel > 0 and os.environ.get("SINCE_OLD") is None:
                    # passed before this attempt and no recording says when: estimated from the
                    # distance at this speed (x moves xVel/4 a step), not this attempt's first step
                    # (NR2's 20 s spin from x 800 restarted at x 30195)
                    return max(int((past[0].x - x) / (past[0].x_vel * 0.25)) - (1 if respawn else 0), 0)
                el = None if hit is None else (now - hit.tick) // 2
                return el
        sim.triggers.catch_up(p, since)

    p.mode = MODES[real.mode]
    # The trace doesn't record an Options trigger's "controls disabled": back to normal on a resync
    # (a stale disable kept after a mismatch cost Flamewall ~1900 steps)
    sim.p1_disabled = sim.p2_disabled = False
    if p.mode in ("ufo", "ship", "ball") and real.on_slope and real.on_ground and att is not None \
            and os.environ.get("NO_SLOPE_RESYNC") is None:
        # riding a slope: its time on the slope sets the launch ramp (and a UFO press on a slope);
        # count the game's own on-slope rows up to here (a resync used to restart it at 0). Only
        # rows on the ground: GD's flag stays set in the air (Cosmic Salad: -404 without this)
        k = next((i for i, s_ in enumerate(att.steps) if s_ is real), None)
        if k is not None:
            n = 0
            while k - n >= 0 and att.steps[k - n].on_slope and att.steps[k - n].on_ground:
                n += 1
            p.on_slope, p.slope_steps = True, n
    p.rotation = real.rotation
    p.rot_yv, p.rot_up = real.y_vel, real.upside_down
    # the cube's spin direction / the ball's roll rate from the game's last two rows
    prev_row = None
    if att is not None:
        k = next((i for i, s_ in enumerate(att.steps) if s_ is real), None)
        if k:
            prev_row = att.steps[k - 1]
    g = -1.0 if real.upside_down else 1.0
    p.spin = g
    if prev_row is not None and prev_row.mode == real.mode and prev_row.size == real.size:
        d = real.rotation - prev_row.rotation
        if p.mode == "cube" and not real.on_ground and abs(d) > 1:
            p.spin = 1.0 if d > 0 else -1.0
        elif p.mode == "ball" and real.x_vel:
            p.spin = d / (C.BALL_ROLL * real.x_vel * (1.25 if real.size < 0.8 else 1.0))
    sim.player2, sim.p2_spawn = None, None
    p.dual = real.dual
    if real.p2 is not None and real.p2.mode in MODES:
        # player 2 from its own row, otherwise as player 1 (band, used orbs, speed)
        import dataclasses
        r2 = real.p2
        q = dataclasses.replace(p, used=set(p.used))
        q.player2 = True
        q.x, q.y, q.y_vel = r2.x, r2.y, r2.y_vel
        if r2.step_in_frame != 1:
            q.x, q.y = r2.pos_x, r2.pos_y
        q.size = 1.0 if r2.size > 0.8 else 0.6
        q.upside_down, q.on_ground, q.mode = r2.upside_down, r2.on_ground, MODES[r2.mode]
        q.last_block, q.on_slope, q.robot_boost = None, False, 0
        q.holding = r2.holding
        q.rotation = r2.rotation
        q.rot_yv, q.rot_up, q.spin = r2.y_vel, r2.upside_down, -1.0 if r2.upside_down else 1.0
        sim.p2_hold_ok = r2.holding or not holding
        q.speed = C.SPEEDS[r2.speed]   # each player takes its own speed portals
        q.buffered = r2.jump_buffered and q.mode != "ufo"
        sim.player2 = q


def run(trace_path, level_name, attempt_no=None, save=None, details=3):
    tr = load(trace_path)
    if tr.version < 5:
        print(f"(trace v{tr.version}: old format, see the note at the top of tools/tracediff.py)")
    # a converted .json keeps the layout a trace was recorded on, after the level is edited
    if level_name in (None, "", "layout"):
        # the layout DynamicButter saved with the trace (the level as it was played)
        if not tr.layout:
            raise SystemExit("this trace has no saved layout (recorded before DynamicButter saved them): give --level")
        level = Level.load_layout(tr.layout)
    elif level_name.startswith("layouts/"):
        # a layout file in the trace's folder (one DynamicButter saved, or one stored for an older trace)
        lp = os.path.join(os.path.dirname(os.path.abspath(trace_path)), level_name)
        level = Level.load(lp) if lp.endswith(".json") else Level.load_layout(lp)
    else:
        level = Level.load(level_name) if level_name.endswith(".json") else Level.load_local(level_name, save)
    attempts = [a for a in tr.attempts if attempt_no in (None, a.number)]
    # Band-setting portals touched in any attempt of the trace (tick, event): an attempt that starts
    # at a checkpoint past the portal has no event of its own (The Hallucination: the band's wave
    # portal is moved by a trigger, so its level position doesn't tell which one was used).
    band_events = sorted((int(e[1]), e) for a in tr.attempts for e in a.events
                         if e[0] == "P" and e[3] in ("660", "13", "111", "1331", "286"))
    # x -> tick at which the run first got there, from the attempt that went furthest from the start
    full = max((a for a in tr.attempts if a.steps and a.steps[0].tick <= 4), key=lambda a: a.steps[-1].tick, default=None)
    first_x = None
    if full is not None:
        xs, ts, hi = [], [], float("-inf")
        for st in full.steps:
            if st.x > hi:
                hi = st.x
                xs.append(st.x)
                ts.append(st.tick)
        first_x = (xs, ts)
    for k, a in enumerate(tr.attempts):
        a.prior = tr.attempts[:k]   # earlier attempts: when a checkpoint's run passed a trigger
    for a in attempts:
        a.band_events = band_events
        a.first_x = first_x
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
            resync(sim, first, held_at(att.inputs, first.tick), att, catch=first.x != 0.0,
                   respawn=att.practice and first.tick > 4)
            sim.player.steps = 1
            saved = snap_at.get(first.tick)
            if att.practice and saved and abs(saved[0] - first.pos_x) < 1e-3 and abs(saved[1] - first.pos_y) < 1e-3:
                sim.player.last_block, sim.player.last_diff, sim.player.last_block_x = saved[2:]
                if os.environ.get("DEBUG_SNAP"):
                    o_ = sim.objects[saved[2]] if saved[2] is not None else None
                    print(f"  [respawn {first.tick}: restored ref {(o_.id, o_.x, o_.y, o_.order) if o_ else None} diff {saved[3]}]")
            elif os.environ.get("DEBUG_SNAP") and att.practice:
                print(f"  [respawn {first.tick}: nothing saved (saved={saved}, x={first.pos_x})]")
            elif att.practice and sim.player.on_ground and sim.player.mode in ("cube", "ball"):
                sim._track_standing_block(sim.player)   # respawned standing: the block under it
        two = bool(level.settings.get("two_player"))
        for real in att.steps:
            # 2-player levels in dual mode: the P1 key drives player 1, the P2 key player 2; outside
            # dual both keys drive player 1 (Duelo Maestro: a P2-key press made player 1 jump)
            split = two and sim.player.dual
            hold = held_at(att.inputs, real.tick, False if split else None)
            hold2 = held_at(att.inputs, real.tick, True) if split else None
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
            # Above 1x speed the end can come mid-frame: the tick goes on, the physics state stays
            # the same to the last digit (moving at full speed; a death keeps its tick instead).
            if prev is not None and real.tick > prev.tick and real.x_vel > 0 \
                    and (real.pos_x, real.pos_y, real.y_vel) == (prev.pos_x, prev.pos_y, prev.y_vel):
                if not skipping:
                    end(prev.tick, "level end reached")
                skipping = 10 ** 9
                break
            prev = real
            if real.step_in_frame == 1:
                frame_x = real.x
            if skipping:
                # Resume on the first cube step standing on something, a while after the stop.
                if real.mode in MODES and (real.on_ground or real.mode in (1, 2, 8)) and real.tick >= skipping \
                        and real.step_in_frame == 1:
                    resync(sim, real, hold, att)
                    seg_start, matched, skipping, history = real.tick, 0, None, []
                continue
            if real.mode not in MODES:
                end(real.tick, f"game mode {real.mode} not implemented")
                skipping = real.tick
                continue
            try:
                p = sim.step(hold, hold2)
            except Unsupported as e:
                end(real.tick, str(e))
                skipping = real.tick + 2 * RESYNC_STEPS
                continue
            if os.environ.get("SNAP_LOG") and p.snap_cand is not None:
                c_ = p.snap_cand; p.snap_cand = None
                got = "snap" if real.x == c_["x1"] else "keep" if real.x == c_["x0"] else "other"
                if c_["x1"] == c_["x0"]:
                    got = "same"
                print(f"SNAPLOG {real.tick} {c_['speed']} {c_['layout'][0]} {c_['layout'][1]} {got} {c_['ids'][0]} {c_['ids'][1]} {c_['brk']} {c_['x1']-c_['x0']:.3f} {c_.get('d', 0):.3f} {c_.get('launch')} fresh={int(bool(c_['ji'][0])) if c_.get('ji') else '-'} air={c_['steps'] - c_['ji'][1] if c_.get('ji') else '-'} ld={c_.get('ld', 0):.3f} lb={c_.get('lb')} nb={c_.get('nb')} x0={c_['x0']:.3f}")
                if os.environ.get("SNAP_ORACLE") and got in ("snap", "keep"):
                    p.x = real.x; p.last_diff = p.x - c_["ox"]
            history.append((real, fmt_sim(p)))
            d = compare(real, p, stats)
            if not d and real.p2 is not None:
                q = sim.player2
                if q is None:
                    d = [("player2", "present", "none")]
                else:
                    d = [("p2." + n, a, b) for n, a, b in compare(real.p2, q, stats)]
            elif not d and real.p2 is None and sim.player2 is not None and not real.dual:
                d = [("player2", "none", "present")]
            if not d and p.dead and real is not death_row:
                d = [("death", att.death_tick, f"{real.tick} ({p.killer})")]
            if not d and not p.dead and real is death_row:
                d = [("death", real.tick, "none")]
            if d:
                why = "DIFFERENCE: " + ", ".join(f"{n} real={a!r} sim={b!r}" for n, a, b in d)
                if os.environ.get("DEBUG_SNAP"):
                    print(f"  [snap decision at {real.tick}: {p.snap_dbg}]")
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
            snap_at[real.tick] = (p.x, p.y, p.last_block, p.last_diff, p.last_block_x)   # the latest pass
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


MODES = {0: "cube", 1: "ship", 2: "ufo", 4: "ball", 8: "wave", 16: "robot", 32: "spider"}   # trace mode bits the simulator can play
RESYNC_STEPS = 60  # after a stop, wait this many steps before resuming


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("trace")
    ap.add_argument("--level", help="a converted level (.json) or a level name in CCLocalLevels.dat; "
                    "default: the layout DynamicButter saved with the trace")
    ap.add_argument("--attempt", type=int)
    ap.add_argument("--save", help="path to CCLocalLevels.dat (default: GD's save folder)")
    a = ap.parse_args()
    run(a.trace, a.level, a.attempt, a.save)
