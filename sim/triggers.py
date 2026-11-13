"""Move, toggle, spawn and touch triggers.

PROVISIONAL - NOT FULLY DEVELOPED, TO BE CHANGED once traces of trigger levels are checked (see
NOTES.md, "Triggers"). Nothing here is measured yet. What it does now:
  - a trigger fires on the step the player's x reaches the trigger's x (after the move); a
    touch-activated one (key 11) when the player's box overlaps the trigger's 30x30 box (times its
    scale, keys 128/129/32); a spawn-activated one (key 62) when a spawn trigger fires it;
  - toggle: turns the target group's objects off (no collision) or on (key 56);
  - move: shifts the target group by (key 28, key 29) game units, spread linearly over the
    duration (key 10, seconds x 240 steps); easing (key 30) is ignored. Triggers in the moved group
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

STEPS_PER_SECOND = 240
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
                o.uncertain = why

    def _shift(self, g, idxs, dx, dy):
        grid = self.sim.grid
        for i in idxs:
            o = self.sim.objects[i]
            o.x += dx
            o.y += dy
            grid.moved(i)
        for t in self.trig_groups.get(g, ()):
            t["x"] += dx
            t["y"] += dy
            self.unsorted = True
        for a in self.anchor_groups.get(g, ()):
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
            on = keys.get("56") == "1"
            for i in target:
                self.sim.objects[i].enabled = on
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
            self.active.append([g, target, dx, dy, steps, 0])

    def _spawn(self, g, p):
        for t in list(self.trig_groups.get(g, ())):
            if self._spawned(t):
                self._fire(t, p)

    def _resort(self):
        if self.unsorted:
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
        for m in self.active:
            g, idxs, dx, dy, steps, done = m
            self._shift(g, idxs, dx / steps, dy / steps)
            m[5] = done + 1
            if m[5] < steps:
                still.append(m)
        self.active = still
        locks = []
        for lk in self.locks:
            g, idxs, mx, my, left = lk
            if mx or my:
                self._shift(g, idxs, moved[0] * mx, moved[1] * my)
            lk[4] = left - 1
            if lk[4] > 0:
                locks.append(lk)
        self.locks = locks

    def catch_up(self, p):
        """After the simulator is put at a later point: fire everything before it, finish moves.
        Touch triggers and spawn delays on the way are not replayed."""
        self._resort()
        while self.next < len(self.by_x) and self.by_x[self.next]["x"] <= p.x:
            self._fire(self.by_x[self.next], p)
            self.next += 1
        for g, idxs, dx, dy, steps, done in self.active:
            left = (steps - done) / steps
            self._shift(g, idxs, dx * left, dy * left)
        self.active = []
        # Locked groups follow the player to the new place.
        if self.last:
            for g, idxs, mx, my, left in self.locks:
                self._shift(g, idxs, (p.x - self.last[0]) * mx, (p.y - self.last[1]) * my)
        self.last = (p.x, p.y)
