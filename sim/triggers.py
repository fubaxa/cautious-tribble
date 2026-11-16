"""Move, toggle, spawn and touch triggers.

PROVISIONAL - NOT FULLY DEVELOPED, TO BE CHANGED once traces of trigger levels are checked (see
NOTES.md, "Triggers"). Nothing here is measured yet. What it does now:
  - a trigger fires on the step the player's x reaches the trigger's x (after the move); a
    touch-activated one (key 11) when the player's box overlaps the trigger's 30x30 box (times its
    scale, keys 128/129/32); a spawn-activated one (key 62) when a spawn trigger fires it;
  - toggle: turns the target group's objects off (no collision) or on (key 56);
  - move: shifts the target group by (key 28, key 29) game units over the duration (key 10,
    seconds x 240 steps), following its easing (key 30, rate key 85; see ease()). Triggers in the moved group
    move with it (some levels carry touch triggers into the player's path this way);
  - move to target (key 100): to the player's position (key 138) or group 71's anchor, from group
    395's anchor (else the moved group's), on both axes / x only / y only (key 101). A group's
    anchor is its group-parent object (key 34), else its first object in level order (converter);
  - lock to player x / y (keys 58 / 59): for the duration the group also moves by the player's own
    movement each step, times key 143 / 144 (default 1);
  - spawn: fires the spawn-activated triggers in its target group after its delay (key 63).
Not simulated - the target objects are marked uncertain and the simulator stops if the player
reaches one: follow, stop and rotate (with an angle) triggers, a lock to player combined with a
move to target,
spawn-activated triggers that only something else (collision, on-death, count...) can start,
targets or centres made only of objects the converter dropped (decoration).
"""

import math

STEPS_PER_SECOND = 240
import os as _os
MOVE_START_WAIT = int(_os.environ.get("MOVE_WAIT", "2"))   # an eased move starts 2 steps later
# (a moving orb in Night Rider 2: exponential-out progress 2 steps behind the linear rule; linear
# moves keep Every End 2's timing)


def ease(kind, rate, t):
    """GD's move easing (key 30, rate key 85), the cocos2d curves: progress 0..1 at time 0..1."""
    if kind == 0 or t <= 0.0 or t >= 1.0:
        return min(max(t, 0.0), 1.0)
    r = rate or 2.0
    if kind == 1:                       # ease in out
        t2 = t * 2
        return 0.5 * t2 ** r if t2 < 1 else 1.0 - 0.5 * (2 - t2) ** r
    if kind == 2:                       # ease in
        return t ** r
    if kind == 3:                       # ease out
        return t ** (1.0 / r)
    if kind in (4, 5, 6):               # elastic (rate = period)
        period = rate or 0.3
        s_ = period / 4
        if kind == 5:
            t -= 1
            return -(2 ** (10 * t)) * math.sin((t - s_) * 2 * math.pi / period)
        if kind == 6:
            return 2 ** (-10 * t) * math.sin((t - s_) * 2 * math.pi / period) + 1
        t2 = t * 2 - 1
        if t2 < 0:
            return -0.5 * 2 ** (10 * t2) * math.sin((t2 - s_) * 2 * math.pi / period)
        return 2 ** (-10 * t2) * math.sin((t2 - s_) * 2 * math.pi / period) * 0.5 + 1
    if kind in (7, 8, 9):               # bounce
        def out(u):
            if u < 1 / 2.75:
                return 7.5625 * u * u
            if u < 2 / 2.75:
                u -= 1.5 / 2.75
                return 7.5625 * u * u + 0.75
            if u < 2.5 / 2.75:
                u -= 2.25 / 2.75
                return 7.5625 * u * u + 0.9375
            u -= 2.625 / 2.75
            return 7.5625 * u * u + 0.984375
        if kind == 9:
            return out(t)
        if kind == 8:
            return 1 - out(1 - t)
        return (1 - out(1 - t * 2)) * 0.5 if t < 0.5 else out(t * 2 - 1) * 0.5 + 0.5
    if kind == 10:                      # exponential in out
        t2 = t * 2
        return 0.5 * 2 ** (10 * (t2 - 1)) if t2 < 1 else 0.5 * (2 - 2 ** (-10 * (t2 - 1)))
    if kind == 11:
        return 2 ** (10 * (t - 1)) - 0.001
    if kind == 12:
        return 1 - 2 ** (-10 * t)
    if kind == 13:                      # sine in out
        return -0.5 * (math.cos(math.pi * t) - 1)
    if kind == 14:
        return 1 - math.cos(t * math.pi / 2)
    if kind == 15:
        return math.sin(t * math.pi / 2)
    if kind in (16, 17, 18):            # back
        o = 1.70158
        if kind == 17:
            return t * t * ((o + 1) * t - o)
        if kind == 18:
            t -= 1
            return t * t * ((o + 1) * t + o) + 1
        o *= 1.525
        t2 = t * 2
        if t2 < 1:
            return t2 * t2 * ((o + 1) * t2 - o) / 2
        t2 -= 2
        return t2 * t2 * ((o + 1) * t2 + o) / 2 + 1
    return t
FOLLOWERS = ("FollowCom", "AdvFollow", "FollowPCom", "StopMover", "RotateCom")
HANDLED = ("MoveCom", "Toggle", "Spawn") + FOLLOWERS


def _f(t, key, default=0.0):
    try:
        return float(t["keys"].get(key, default))
    except ValueError:
        return default


def _g(t, key):
    return int(_f(t, key))


class Triggers:
    def __init__(self, sim, triggers, anchors=()):
        self.sim = sim
        # Where move-to-target triggers measure a group from (see converter): moved with its groups.
        self.anchors = {a["g"]: dict(a) for a in anchors}
        self.anchor_groups = {}
        for a in self.anchors.values():
            for g in a["groups"]:
                self.anchor_groups.setdefault(g, []).append(a)
        self.groups = {}
        for i, o in enumerate(sim.objects):
            for g in o.groups:
                self.groups.setdefault(g, []).append(i)
        # Each simulator keeps its own copies: moves carry triggers along.
        self.all = [dict(t, keys=t["keys"]) for t in triggers if t["type"] in HANDLED]
        self.trig_groups = {}
        for t in self.all:
            for g in t.get("groups", ()):
                self.trig_groups.setdefault(g, []).append(t)
        self.by_x = sorted((t for t in self.all if not self._spawned(t) and not self._touch(t)),
                           key=lambda t: t["x"])
        self.next = 0
        self.touch = [t for t in self.all if self._touch(t) and not self._spawned(t)]
        self.fired = set()   # id() of single-use triggers already fired
        self.active = []     # moves in progress: [object indices, triggers, dx, dy, steps, done]
        self.queue = []      # spawns waiting for their delay: [steps left, group]
        self.unsorted = False
        self.locks = []      # [group, object indices, mod x, mod y, steps left]
        self.starting = []   # timed moves fired this step: they start moving on the next one
        self.last = None     # player position at the previous update
        # Spawn-activated triggers that no spawn trigger can start: their targets are uncertain.
        reachable = {_g(t, "51") for t in self.all if t["type"] == "Spawn"}
        for t in self.all:
            if self._spawned(t) and not reachable.intersection(t.get("groups", ())):
                target = self.groups.get(_g(t, "51"))
                if target and t["type"] != "Spawn":
                    self._uncertain(target, f"a {t['type']} trigger started by something not simulated")

    @staticmethod
    def _spawned(t):
        return t["keys"].get("62") == "1"

    @staticmethod
    def _touch(t):
        return t["keys"].get("11") == "1"

    def _uncertain(self, idxs, why):
        for i in idxs:
            o = self.sim.objects[i]
            if not o.uncertain:
                self.sim.log_obj(i)
                o.uncertain = why

    def toggle_group(self, g, on):
        """Turn group g's objects on or off (no collision while off): toggle triggers and orbs."""
        for i in self.groups.get(g, ()):
            self.sim.log_obj(i)
            self.sim.objects[i].enabled = on

    def _shift(self, g, idxs, dx, dy):
        grid = self.sim.grid
        step = self.sim.player.steps
        j = self.sim.journal
        for i in idxs:
            o = self.sim.objects[i]
            if j is not None:
                j.append((0, i, o.x, o.y, o.moved_step, o.enabled, o.uncertain))
            o.x += dx
            o.y += dy
            o.moved_step = step
            grid.moved(i)
        for t in self.trig_groups.get(g, ()):
            if j is not None:
                j.append((1, t, t["x"], t["y"]))
            t["x"] += dx
            t["y"] += dy
            self.unsorted = True
        for a in self.anchor_groups.get(g, ()):
            if j is not None:
                j.append((1, a, a["x"], a["y"]))
            a["x"] += dx
            a["y"] += dy

    def _centre(self, g):
        a = self.anchors.get(g)
        if a:
            return a["x"], a["y"]
        idxs = self.groups.get(g)
        if not idxs:
            return None
        rs = [self.sim.objects[i].rect for i in idxs]
        x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
        x1, y1 = max(r[0] + r[2] for r in rs), max(r[1] + r[3] for r in rs)
        return (x0 + x1) / 2, (y0 + y1) / 2

    def _fire(self, t, p):
        if t["keys"].get("87") != "1":
            if id(t) in self.fired:
                return
            self.fired.add(id(t))
            if self.sim.journal is not None:
                self.sim.journal.append((2, id(t)))
        g = _g(t, "51")
        typ, keys, at = t["type"], t["keys"], t["x"]
        if typ == "Spawn":
            steps = round(_f(t, "63") * STEPS_PER_SECOND)
            self.queue.append([steps, g])
            return
        target = self.groups.get(g)
        if not target and not self.trig_groups.get(g):
            return
        target = target or []
        if typ == "Toggle":
            self.toggle_group(g, keys.get("56") == "1")
            return
        if typ in FOLLOWERS:
            if typ != "RotateCom" or _f(t, "68"):
                self._uncertain(target, f"a {typ} trigger at x={at:.0f}")
            return
        lock_x, lock_y = keys.get("58") == "1", keys.get("59") == "1"
        if (lock_x or lock_y) and keys.get("100") == "1":
            self._uncertain(target, f"a move to target locked to the player at x={at:.0f}")
            return
        if lock_x or lock_y:
            self.locks.append([g, target, _f(t, "143", 1.0) if lock_x else 0.0,
                               _f(t, "144", 1.0) if lock_y else 0.0,
                               round(_f(t, "10") * STEPS_PER_SECOND)])
        if keys.get("100") == "1":
            if keys.get("138") == "1":
                tx, ty = p.x, p.y
            else:
                c = self._centre(_g(t, "71"))
                if c is None:
                    self._uncertain(target, f"a move to a dropped target at x={at:.0f}")
                    return
                tx, ty = c
            c = self._centre(_g(t, "395")) if keys.get("395") else self._centre(g)
            if c is None:
                self._uncertain(target, f"a move from a dropped centre at x={at:.0f}")
                return
            axis = int(_f(t, "101"))
            dx = 0.0 if axis == 2 else tx - c[0]
            dy = 0.0 if axis == 1 else ty - c[1]
        else:
            dx, dy = _f(t, "28"), _f(t, "29")
        if not dx and not dy:
            return
        steps = round(_f(t, "10") * STEPS_PER_SECOND)
        if steps <= 0:
            self._shift(g, target, dx, dy)
        else:
            # A timed move starts on the step after it fires (Every End 2's first slab, 2 steps).
            kind = int(_f(t, "30"))
            self.starting.append([g, target, dx, dy, steps, 0, kind, _f(t, "85", 2.0),
                                  MOVE_START_WAIT if kind else 0, at])

    def _spawn(self, g, p):
        for t in list(self.trig_groups.get(g, ())):
            if self._spawned(t):
                self._fire(t, p)

    def _resort(self):
        if self.unsorted:
            if self.sim.journal is not None:
                self.sim.journal.append((3, self.next, self.by_x[self.next:]))
            rest = sorted(self.by_x[self.next:], key=lambda t: t["x"])
            self.by_x[self.next:] = rest
            self.unsorted = False

    def update(self, p):
        """Fire what the player has reached or touched, run spawn delays, advance moves one step."""
        moved = (p.x - self.last[0], p.y - self.last[1]) if self.last else (0.0, 0.0)
        self.last = (p.x, p.y)
        self._resort()
        while self.next < len(self.by_x) and self.by_x[self.next]["x"] <= p.x:
            self._fire(self.by_x[self.next], p)
            self.next += 1
        if self.touch:
            h = p.half
            for t in self.touch:
                if id(t) in self.fired and t["keys"].get("87") != "1":
                    continue
                s = _f(t, "32", 1.0) or 1.0
                hw = 15 * (_f(t, "128", s) or s)
                hh = 15 * (_f(t, "129", s) or s)
                if abs(t["x"] - p.x) < hw + h and abs(t["y"] - p.y) < hh + h:
                    self._fire(t, p)
        waiting = []
        for q in self.queue:
            if q[0] <= 0:
                self._spawn(q[1], p)
            else:
                q[0] -= 1
                waiting.append(q)
        self.queue = waiting
        still = []
        started, waiting_moves = [], []
        for m in self.starting:
            if m[8] > 0:
                m[8] -= 1
                waiting_moves.append(m)
            else:
                started.append(m)
        self.starting = waiting_moves
        for m in self.active:
            g, idxs, dx, dy, steps, done, kind, rate, _w, _x = m
            f = ease(kind, rate, (done + 1) / steps) - ease(kind, rate, done / steps)
            self._shift(g, idxs, dx * f, dy * f)
            m[5] = done + 1
            if m[5] < steps:
                still.append(m)
        self.active = still + started
        locks = []
        for lk in self.locks:
            g, idxs, mx, my, left = lk
            if mx or my:
                self._shift(g, idxs, moved[0] * mx, moved[1] * my)
            lk[4] = left - 1
            if lk[4] > 0:
                locks.append(lk)
        self.locks = locks

    def catch_up(self, p, since=None):
        """After the simulator is put at a later point: fire everything before it and bring timed
        moves to where they are now. `since(x)` (from the recording) gives the steps since the
        player passed x; without it moves are finished at once. Touch triggers and spawn delays on
        the way are not replayed."""
        self._resort()
        while self.next < len(self.by_x) and self.by_x[self.next]["x"] <= p.x:
            self._fire(self.by_x[self.next], p)
            self.next += 1
        keep = []
        for m in self.active + self.starting:
            g, idxs, dx, dy, steps, done, kind, rate, wait, x = m
            now = steps
            if since is not None:
                el = since(x)
                if el is not None:
                    # fired on the step the player reached x, moving from the next one (+ the
                    # start wait less the fire step: the original one, not what's left of it - a move
                    # already under way has 0 left and was put a step ahead, The Hallucination platforms)
                    w0 = (MOVE_START_WAIT - 1 if kind else 0)
                    now = min(max(el - w0, 0), steps)
            if now > done:
                f = ease(kind, rate, now / steps) - ease(kind, rate, done / steps)
                self._shift(g, idxs, dx * f, dy * f)
            if now < steps:
                m[5], m[8] = now, 0
                keep.append(m)
        self.active, self.starting = keep, []
        # Locked groups follow the player to the new place.
        if self.last:
            for g, idxs, mx, my, left in self.locks:
                self._shift(g, idxs, (p.x - self.last[0]) * mx, (p.y - self.last[1]) * my)
        self.last = (p.x, p.y)
