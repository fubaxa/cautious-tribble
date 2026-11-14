"""Scan DynamicButter traces (any version) and report what they cover.

    python -m tools.coverage <trace.csv>... [--hitboxes]

Prints, per game mode / speed / size: step counts and the most common per-step yVel changes
(held / not held), the yVel right after pads and used orbs, and every object ID seen in an event
row with its hitbox size. Used to see which constants are measured and which still need a test.
"""
import collections
import sys

from sim.trace import _open

MODES = {0: "cube", 1: "ship", 2: "ufo", 4: "ball", 8: "wave", 16: "robot", 32: "spider", 64: "swing"}
SPEEDS = {0.7: "0.5x", 0.9: "1x", 1.1: "2x", 1.3: "3x", 1.6: "4x"}


def version(path):
    with _open(path) as f:
        first = f.readline()
    return int(first.rsplit("v", 1)[1]) if "trace v" in first else 0


def scan(paths):
    steps = collections.Counter()                      # (mode, speed, size, upside) -> steps
    dvy = collections.defaultdict(collections.Counter)  # (mode, speed, size, hold) -> dvy -> n
    dydv = collections.defaultdict(collections.Counter)  # (mode, speed) -> dy/yVel -> n
    after = collections.defaultdict(collections.Counter)  # (kind, id, mode, speed, size) -> yVel after -> n
    boxes = collections.defaultdict(collections.Counter)  # (kind, id) -> (w, h, rot) -> n
    vy_range = {}
    for path in paths:
        v = version(path)
        prev = None
        pending = []   # (kind, id) events waiting for the S row that shows their effect
        with _open(path) as f:
            for line in f:
                if line.startswith("#"):
                    continue
                r = line.rstrip("\n").split(",")
                k = r[0]
                if k == "A":
                    prev = None
                    pending = []
                elif k == "S" and len(r) >= 23:
                    mode, size = int(r[12]), round(float(r[8]), 1)
                    speed = SPEEDS.get(round(float(r[9]), 1), r[9])
                    up, hold, vy, y = r[11] == "1", r[17] == "1", float(r[6]), float(r[4])
                    name = MODES.get(mode, str(mode))
                    steps[(name, speed, size, up)] += 1
                    lo, hi = vy_range.get((name, size), (0.0, 0.0))
                    vy_range[(name, size)] = (min(lo, vy), max(hi, vy))
                    for kind, oid in pending:
                        after[(kind, oid, name, speed, size)][round(vy if not up else -vy, 3)] += 1
                    pending = []
                    if prev and prev["tick"] + 2 == int(r[1]) and prev["mode"] == mode and prev["up"] == up \
                            and prev["size"] == size and prev["speed"] == speed and r[2] == "1":
                        d = vy - prev["vy"]
                        if up:
                            d = -d
                        if not (r[10] == "1" and prev["ground"]) or mode in (1, 2, 8, 64):
                            dvy[(name, speed, size, hold)][round(d, 3)] += 1
                        if vy and r[10] != "1":
                            dydv[(name, speed)][round((y - prev["y"]) / vy, 3)] += 1
                    prev = dict(tick=int(r[1]), mode=mode, up=up, size=size, speed=speed, vy=vy, y=y,
                                ground=r[10] == "1")
                elif k == "O":
                    off = 4 if v >= 3 else 3
                    kind, oid = r[2], int(r[off])
                    w, h = float(r[off + 5]), float(r[off + 6])
                    rot = float(r[off + 7]) if v >= 3 and len(r) > off + 7 and r[off + 7] else None
                    boxes[(kind, oid)][(round(w, 2), round(h, 2), rot)] += 1
                    if kind == "pad":
                        pending.append((kind, oid))
                elif k == "U":
                    oid = int(r[3])
                    pending.append(("orb", oid))
                elif k == "P":
                    oid = int(r[3])
                    rot = float(r[10]) if r[10] else None
                    boxes[("portal", oid)][(round(float(r[8]), 2), round(float(r[9]), 2), rot)] += 1
                elif k == "D" and r[-1] == "1" and r[2] != "0":
                    boxes[("killer", int(r[2]))][(round(float(r[7]), 2), round(float(r[8]), 2), None)] += 1
    return steps, dvy, dydv, after, boxes, vy_range


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    steps, dvy, dydv, after, boxes, vy_range = scan(args)
    print("== steps per mode / speed / size (normal + flipped gravity)")
    agg = collections.Counter()
    for (m, sp, sz, up), n in steps.items():
        agg[(m, sp, sz)] += n
    for (m, sp, sz), n in sorted(agg.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), -kv[0][2])):
        flipped = steps.get((m, sp, sz, True), 0)
        print(f"  {m:7s} {sp:5} size {sz}: {n:6d} steps ({flipped} flipped)")
    print("== yVel change per step (gravity-relative), top values: mode speed size held")
    for key in sorted(dvy, key=lambda k: (k[0], str(k[1]), -k[2], k[3])):
        c = dvy[key]
        if sum(c.values()) < 30:
            continue
        print(f"  {key[0]:7s} {key[1]:5} size {key[2]} held={int(key[3])}: {c.most_common(5)}")
    print("== dy / yVel per step: mode speed")
    for key in sorted(dydv, key=str):
        print(f"  {key[0]:7s} {key[1]:5}: {dydv[key].most_common(3)}")
    print("== yVel range seen: mode size")
    for key in sorted(vy_range, key=str):
        print(f"  {key[0]:7s} size {key[1]}: {vy_range[key]}")
    print("== yVel on the step after a pad touch / orb use (gravity-relative): kind id mode speed size")
    for key in sorted(after, key=str):
        print(f"  {key[0]:4s} {key[1]:5d} {key[2]:7s} {key[3]:5} size {key[4]}: {after[key].most_common(3)}")
    print("== object hitboxes seen in event rows: kind id -> (w, h, rotation) x count")
    for key in sorted(boxes, key=lambda k: (k[0], k[1])):
        print(f"  {key[0]:8s} {key[1]:5d}: {boxes[key].most_common(3)}")


if __name__ == "__main__":
    main()
