"""Find a macro that beats a level, in the simulator, and save it for DynamicButter.

    python -m tools.solve --local "Every End 2" [--prefer middle] [--min-gap 12] [-o out.gdr2]
    python -m tools.solve --saved <name|id> ...      a downloaded level
    python -m tools.solve --json levels/x.json ...    an already converted level

How it searches (not every step, not every click):
  * The run goes on WITHOUT input until it dies (or beats the level). Only steps where a press can
    change anything are candidates: the cube/ball on the ground, or an orb in reach; and a new
    press needs at least --min-gap steps since the previous one (12 steps = 20 clicks/s). Holding
    is allowed: it adds no clicks.
  * Each candidate is tried as a short click (press, release on the next step) and followed only
    until it lands and settles, or rejoins a run already seen. Candidates that end in exactly the
    same state are ONE window (DynamicButter's "exact" window: the click can be anywhere in it and
    nothing after it changes), so the search continues once per window, not once per step.
  * Windows are tried from the one closest to the death backwards; when a window's run dies later,
    the search backs up (depth first). States proven hopeless are remembered and never searched
    again. Only when no short click works, holding through landings is tried (no new clicks).
  * --prefer early / middle / late picks the step inside each window. The window sizes are saved
    with the macro (DynamicButter's window data), so Dynamic mode can use them.

The result is replayed from the start once more before it's saved.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from sim import gdr2, state
from sim.level import Level
from sim.objects import ORB
from sim.physics import Unsupported
from sim.run import advance, end_x, new_sim, play

DEAD, END = -1, -2
SETTLE = 8          # steps on the ground after landing before a click's outcome counts as settled
TRIAL_CAP = 1200    # a click followed this long without settling is an outcome of its own
LOOKBACK = 160      # candidates considered per batch, back from the death (steps)
HOLD_VARIANTS = (1, 2)   # hold through this many automatic jumps (no new clicks)
# A press up to this many steps before a landing still jumps on it (measured at x 12465 in Every
# End 2: 1 step before works, 2 doesn't; one more for safety). Those steps are candidates too.
BUFFER_STEPS = 3
# Window order: "size" = largest first (the most forgiving click, usually the level's intended
# route), then the latest; "late" = the latest first.
ORDER = os.environ.get("SOLVE_ORDER", "size")
KEEP_FRAMES = 400   # how many clicks back the search may still undo (memory)


class Frame:
    """A point after a click (or the start): the run from here without input, and what to try."""
    __slots__ = ("snap", "key", "last_press", "click", "cands", "death", "batches_done",
                 "alts", "alt_i", "holds_done", "valid")

    def __init__(self, snap, key, last_press, click):
        self.snap, self.key, self.last_press, self.click = snap, key, last_press, click
        self.cands = None      # [(tick, saved point before that step)] in time order
        self.death = None
        self.batches_done = 0
        self.alts = []         # windows to try: (ticks, variant)
        self.alt_i = 0
        self.holds_done = set()
        # Candidates up to this tick can be restored directly: the undo log still matches the run
        # without input up to there (restores only go backwards; see _goto).
        self.valid = 0


class Solver:
    def __init__(self, level, prefer="middle", min_gap=12, log=print, time_limit=None, margin=0.0):
        self.level = level
        self.prefer = prefer
        self.gap = 2 * min_gap          # ticks between presses
        self.end = end_x(level)
        if self.end is None:
            raise ValueError("the level file has no last_x: convert it again")
        self.sim = new_sim(level)
        self.sim.margin = margin
        state.enable(self.sim)
        self.dead = set()
        self.resolved = {}   # trial id -> its final outcome, for trials that rejoin it
        self.committed = []  # clicks too far back to undo any more
        self.log = log
        self.time_limit = time_limit
        self.orbs = [o for o in self.sim.objects if o.kind == ORB]
        self.stats = dict(steps=0, trials=0, frames=0, backtracks=0)

    # --- helpers ---
    def _step(self, hold):
        self.stats["steps"] += 1
        return advance(self.sim, hold)

    def _can_press(self):
        p = self.sim.player
        if p.mode == "wave":
            return True
        if p.on_ground:
            return True
        for i, o in self.sim._near(p.x - 50, p.x + 50):
            if o.kind == ORB and i not in p.used and abs(o.y - p.y) < 60:
                return True
        return False

    def _node_key(self, last_press):
        return state.key(self.sim) + (min(self.sim.tick - last_press, self.gap),)

    # --- the run from a frame without input ---
    def _coast(self, f):
        state.restore(self.sim, f.snap)
        cands = []
        recent = []   # the last airborne steps: a press there is kept and jumps on landing
        while True:
            nxt = self.sim.tick + 2
            allowed = nxt - f.last_press >= self.gap
            was_ground = self.sim.player.on_ground
            if allowed and self._can_press():
                cands.append((nxt, state.save(self.sim)))
            elif allowed:
                recent.append((nxt, state.save(self.sim)))
                del recent[:-BUFFER_STEPS]
            p = self._step(False)
            if p.dead or (p.on_ground and not was_ground):
                cands += recent
                recent = []
            if p.dead:
                f.death = self.sim.tick
                break
            if p.x >= self.end:
                return True
        cands.sort(key=lambda c: c[0])
        f.cands = cands
        return False

    def _goto(self, f, t):
        """Put the simulator just before candidate step t of frame f's run without input."""
        best = None
        for tt, snap in f.cands:
            if tt > min(t, f.valid):
                break
            best = (tt, snap)
        state.restore(self.sim, best[1] if best else f.snap)
        while self.sim.tick < t - 2:
            self._step(False)
        f.valid = t

    # --- one click tried from a candidate (the simulator is just before its step) ---
    def _done(self, oid, outcome):
        self.resolved[oid] = outcome
        return outcome

    def _final(self, oid):
        """The final outcome of a trial (a trial that rejoined another has that one's outcome)."""
        seen = set()
        while oid in self.resolved and self.resolved[oid] != oid and oid not in seen:
            seen.add(oid)
            oid = self.resolved[oid]
        return oid

    def _click(self, t, variant, seen, oid, stop_at=None):
        """Press at tick t; variant 0 = release on the next step, k = keep holding through k
        automatic jumps (no new clicks). Returns (outcome, stop tick, release tick); the outcome
        is an id (`oid` or a run it rejoined), DEAD, END, or ("L", tick): the run landed safely at
        that tick but dies after it without input (the next click must come right after landing,
        so the search goes on from the landing; `stop_at` stops there)."""
        sim = self.sim
        self.stats["trials"] += 1
        jumps, holding, on_ground_for, release, landed = 0, True, 0, None, None
        p = self._step(True)
        while True:
            if stop_at is not None and sim.tick >= stop_at:
                return ("L", stop_at), sim.tick, release, landed
            if p.dead:
                if landed is not None:
                    # go on from a few steps before the landing, where the next press can be kept
                    at = max(landed - 2 * BUFFER_STEPS, release or t + 2)
                    return self._done(oid, ("L", at)), sim.tick, release, landed
                return self._done(oid, DEAD), sim.tick, release, landed
            if p.x >= self.end:
                return self._done(oid, END), sim.tick, (release or sim.tick + 2), landed
            if holding:
                holding = variant > 0 and jumps < variant
                if not holding:
                    release = sim.tick + 2
            if not holding:
                k = state.key(sim)
                if k + (min(sim.tick - t, self.gap),) in self.dead:
                    return self._done(oid, DEAD), sim.tick, release, landed
                prev = seen.get(k)
                if prev is not None:
                    return self._done(oid, self._final(prev)), sim.tick, release, landed
                if seen is not None:
                    seen[k] = oid
                if p.on_ground:
                    on_ground_for += 1
                    if on_ground_for == 1:
                        landed = sim.tick
                    if on_ground_for >= SETTLE:
                        return self._done(oid, oid), sim.tick, release, landed
                else:
                    on_ground_for = 0
            if sim.tick - t > 2 * TRIAL_CAP:
                return self._done(oid, oid), sim.tick, (release or sim.tick + 2), landed
            was_ground = p.on_ground
            p = self._step(holding)
            if holding and was_ground and not p.on_ground and p.sign * p.y_vel > 0:
                jumps += 1

    def _windows(self, f, batch, variant):
        """Try every candidate of the batch (latest first, so restores only go backwards); group
        the ones with the same outcome into windows. Returns the windows (latest first) as tick
        lists, and a window whose click beats the level, if any."""
        seen = {}
        outcome = {}
        self.resolved = {}   # trial ids are only rejoined within one batch
        for t, _ in reversed(batch):
            self._goto(f, t)
            outcome[t] = self._click(t, variant, seen, ("o", t))[0]
        wins, cur, cur_o = [], [], None
        for t, _ in batch:
            o = outcome[t]
            if cur and o == cur_o and t == cur[-1] + 2:
                cur.append(t)
            else:
                if cur and cur_o != DEAD:
                    wins.append(cur)
                cur, cur_o = [t], o
        if cur and cur_o != DEAD:
            wins.append(cur)
        ends = [w for w in wins if outcome[w[0]] == END]
        # Largest window first (the most forgiving click: usually the level's intended route),
        # then the latest.
        wins = sorted(wins, key=lambda w: (-len(w), -w[-1])) if ORDER == "size" else list(reversed(wins))
        return wins, (ends[0] if ends else None)

    def _pick(self, ticks):
        if self.prefer == "early":
            return ticks[0]
        if self.prefer == "late":
            return ticks[-1]
        return ticks[(len(ticks) - 1) // 2]

    def _next_alt(self, f):
        """The next window to try from this frame, computing more candidates lazily."""
        while f.alt_i >= len(f.alts):
            n = len(f.cands)
            hi = n - f.batches_done * LOOKBACK
            if hi > 0:
                batch = f.cands[max(0, hi - LOOKBACK):hi]
                f.batches_done += 1
                wins, end = self._windows(f, batch, 0)
                if end:
                    return (end, 0, True)
                f.alts += [(w, 0) for w in wins]
                continue
            # no short click works from here: hold through landings (no new clicks)
            for v in HOLD_VARIANTS:
                if v in f.holds_done:
                    continue
                f.holds_done.add(v)
                wins = []
                for hi in range(n, 0, -LOOKBACK):
                    batch = f.cands[max(0, hi - LOOKBACK):hi]
                    w, end = self._windows(f, batch, v)
                    if end:
                        return (end, v, True)
                    wins += w
                f.alts += [(w, v) for w in wins]
                break
            else:
                return None
        alt = f.alts[f.alt_i]
        f.alt_i += 1
        return (alt[0], alt[1], False)

    def _child(self, f, ticks, variant):
        """Play the chosen click of a window from the frame; return the frame after it."""
        t = self._pick(ticks)
        self._goto(f, t)
        p = self.sim.player
        phys = (p.x, p.y, 0.0, p.x_vel, p.y_vel)
        o, _, release, landed = self._click(t, variant, {}, "c")
        if o == DEAD:
            return None
        if o != END and landed is not None:
            # The next frame starts a few steps before this click's landing: the next press may
            # have to come right at it (kept from the air), before the run counts as settled.
            at = max(landed - 2 * BUFFER_STEPS, release or t + 2, t + 2)
            self._goto(f, t)
            _, _, release, _ = self._click(t, variant, {}, "c", stop_at=at)
        click = dict(press=t, release=release, early=(t - ticks[0]) // 2, late=(ticks[-1] - t) // 2,
                     variant=variant, phys=phys, end=o == END)
        return Frame(state.save(self.sim), self._node_key(t), t, click)

    # --- search ---
    def solve(self):
        t0 = time.time()
        root = Frame(state.save(self.sim), self._node_key(-10 ** 9), -10 ** 9, None)
        stack = [root]
        best_x, last_report = 0.0, 0.0
        while stack:
            if self.time_limit and time.time() - t0 > self.time_limit:
                raise TimeoutError(f"no macro within {self.time_limit} s (furthest x {best_x:.0f})")
            f = stack[-1]
            if f.cands is None:
                self.stats["frames"] += 1
                if f.click and f.click["end"]:
                    return self._result(stack, t0)
                if self._coast(f):
                    return self._result(stack, t0)
                f.valid = 10 ** 12
                best_x = max(best_x, self.sim.player.x)
                if time.time() - last_report > 5:
                    last_report = time.time()
                    self.log(f"  x {self.sim.player.x:9.0f} of {self.end:.0f}   clicks {len(stack) - 1:5d}   "
                             f"backtracks {self.stats['backtracks']:5d}   {time.time() - t0:6.0f} s")
            alt = self._next_alt(f)
            if alt is None:
                self.dead.add(f.key)
                stack.pop()
                self.stats["backtracks"] += 1
                if not stack:
                    if self.committed:
                        raise RuntimeError(f"stuck (furthest x {best_x:.0f}); the clicks before it "
                                           f"can't be undone any more (KEEP_FRAMES)")
                    break
                continue
            ticks, variant, _ = alt
            child = self._child(f, ticks, variant)
            if child is None or child.key in self.dead:
                continue
            stack.append(child)
            if len(stack) > KEEP_FRAMES:
                # too far back to undo: commit the oldest click
                old = stack.pop(0)
                if old.click:
                    self.committed.append(old.click)
                state.trim(self.sim, stack[0].snap)
        raise RuntimeError(f"no route found (furthest x {best_x:.0f})")

    def _result(self, stack, t0):
        clicks = self.committed + [f.click for f in stack if f.click]
        self.stats["time"] = round(time.time() - t0, 1)
        return clicks


# GD marks the level complete this long after the last physics step (the end animation): Every End
# 2's recorded macro ends at 211112, its last physics step was 210634.
END_ANIMATION_TICKS = 478


def to_macro(level, name, clicks, end_tick):
    m = gdr2.Macro(level_id=0, level_name=name, end_tick=end_tick + END_ANIMATION_TICKS,
                   author="cautious-tribble-sim solver")
    for c in clicks:
        w = gdr2.Window(early=c["early"], late=c["late"], early_exact=c["early"], late_exact=c["late"])
        m.inputs.append(gdr2.Input(c["press"], True, False, c["phys"], w))
        m.inputs.append(gdr2.Input(c["release"], False, False, c["phys"]))
    annotate(level, m)
    return m


# The simulator doesn't model the player's rotation: macros store NaN, and DynamicButter's
# correction then leaves the player's own rotation alone.
UNKNOWN_ROTATION = float("nan")
PATH_CORNER_EPS = 0.02   # as DynamicButter's PathBuilder (x per tick)


def annotate(level, m):
    """Replay a macro from the start and fill in what DynamicButter stores with it: each input's
    player state right before it (start-position correction moves the player there, so it has to
    be the run's real state), and the run's x path (where a start position lies in the macro)."""
    inputs = sorted(m.inputs, key=lambda i: i.tick)
    sim = new_sim(level)
    state.enable(sim)
    p = sim.player
    pts, last, slope = [(sim.tick - 2, 0.0)], (sim.tick - 2, 0.0), None
    k, held = 0, False
    ex = end_x(level)
    while True:
        nxt = sim.tick + 2
        if k < len(inputs) and inputs[k].tick <= nxt:
            # GD's snapshot when it applies an input at tick T: the state after the step at T played
            # with the button as it was before (the input's own effect isn't in it yet; matches the
            # states DynamicButter records, x, y and yVel exactly).
            snap = state.save(sim)
            q = advance(sim, held)
            before = (q.x, q.y, UNKNOWN_ROTATION, q.x_vel, q.y_vel)
            state.restore(sim, snap)
            p = sim.player
            while k < len(inputs) and inputs[k].tick <= nxt:
                inputs[k].phys = before
                held = inputs[k].down
                k += 1
            state.trim(sim, snap)
        p = advance(sim, held)
        if p.dead or p.x >= ex or sim.tick > 10 ** 7:
            break
        # the x path, corner points only (PathBuilder.add)
        t, x = sim.tick, float(p.x)
        sl = (x - last[1]) / (t - last[0])
        if slope is not None and abs(sl - slope) > PATH_CORNER_EPS and pts[-1][0] != last[0]:
            pts.append(last)
        slope, last = sl, (t, x)
    if pts[-1][0] != last[0]:
        pts.append(last)
    for i in inputs[k:]:
        i.phys = (p.x, p.y, UNKNOWN_ROTATION, p.x_vel, p.y_vel)
    m.path = pts
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--local", help="name of a level you made")
    src.add_argument("--saved", help="name or ID of a downloaded level")
    src.add_argument("--json", help="an already converted level (.json)")
    ap.add_argument("--prefer", choices=("early", "middle", "late"), default="middle",
                    help="where in each click's window to click (default middle)")
    ap.add_argument("--min-gap", type=int, default=12,
                    help="steps between two presses, at least (12 = 20 clicks/s; holding is free)")
    ap.add_argument("--margin", type=float, default=0.01,
                    help="search with every killing box this much bigger (default 0.01, a hundredth "
                         "of a pixel): no route relies on the game's exact edges; 0 = off")
    ap.add_argument("-o", "--out", help="macro file (default: DynamicButter's macros folder)")
    ap.add_argument("--time-limit", type=float, help="give up after this many seconds")
    a = ap.parse_args()

    from converter.convert import convert
    from sim import gdsave
    if a.json:
        level, name = Level.load(a.json), None
        name = level.name or os.path.splitext(os.path.basename(a.json))[0]
    else:
        name = a.local or a.saved
        s = gdsave.local_level(name) if a.local else gdsave.saved_level(name)
        print(f"converting {name} ...")
        level = Level.from_dict(convert(s, name, "local" if a.local else "saved"))
    print(f"solving {name}: prefer {a.prefer} of each window, a press at most every {a.min_gap} steps, "
          f"margin {a.margin}")
    solver = Solver(level, a.prefer, a.min_gap, time_limit=a.time_limit, margin=a.margin)
    try:
        clicks = solver.solve()
    except Unsupported as e:
        sys.exit(f"the simulator can't play this level yet: {e}")
    except (RuntimeError, TimeoutError) as e:
        sys.exit(str(e))
    st = solver.stats
    print(f"found a route: {len(clicks)} clicks, {st['time']} s, {st['steps']:,} steps simulated, "
          f"{st['trials']:,} clicks tried, {st['backtracks']} backtracks")
    # check: replay the whole macro from the start
    inputs = [(c["press"], True) for c in clicks] + [(c["release"], False) for c in clicks]
    sim_m, out_m = play(level, inputs, margin=a.margin)
    if out_m != "end":
        sys.exit(f"the replay with the margin did not beat the level ({out_m} at tick {sim_m.tick}): not saved")
    sim, out = play(level, inputs)
    presses = sorted(c["press"] for c in clicks)
    gaps = [b - a for a, b in zip(presses, presses[1:])]
    if out != "end":
        sys.exit(f"the replay from the start did not beat the level ({out} at tick {sim.tick}): not saved")
    if gaps and min(gaps) < 2 * a.min_gap:
        sys.exit(f"two presses only {min(gaps) // 2} steps apart: not saved")
    sizes = sorted(c["early"] + c["late"] + 1 for c in clicks) or [0]
    print(f"replay from the start: beats the level at tick {sim.tick}; "
          f"window sizes (steps): min {sizes[0]}, median {sizes[len(sizes) // 2]}, max {sizes[-1]}")
    m = to_macro(level, name, clicks, sim.tick)
    out_path = a.out
    if not out_path:
        d = os.path.expandvars(r"%LOCALAPPDATA%\GeometryDash\geode\mods\fubaxa.dynamicbutter\macros")
        out_path = os.path.join(d, f"{name} (solver {a.prefer}).gdr2")
    gdr2.save(out_path, m)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
