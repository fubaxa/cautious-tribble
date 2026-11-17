"""Build the test level (NEEDS.md tests, most unknowns first) and put it in the player's created levels.

    ./run.sh tools.testlevel                 # build, check in the simulator, print a summary
    ./run.sh tools.testlevel --write         # ... and add it to CCLocalLevels.dat (GD must be closed)

No hazards: nothing kills unless a test object itself does (marked "may kill" below), so every run
gets through every section. Coordinates are level units with the ground's top at y = 90 (the level
string stores y - 90).

Sections, in order (x at 1x unless noted):
  1. Cube, normal (then two gravity portals touched on one step): a 45 and a 2:1 slope pair making a square with its flat top 0.5 above the ground
     (Sailent's step-up), then lone hanging slopes whose flat top can be jumped onto (their sloped
     undersides are the "jump into a slope's open side" test: may kill). Gravity portal to a block
     ceiling, a blue pad turned 90 deg there and one turned 270 deg on the floor (both gravities).
  2. UFO, normal, 1x: floor hills (45 and 2:1, 1 and 2 blocks high, a 2:1 into 45 chain), turned
     pads between them, turned orbs (30/45/60 deg) and negatively scaled turned orbs in the air;
     then upside down (gravity portal) under hanging hills on the band's ceiling.
  3. UFO, mini: hills, a blue pad turned 334 deg (Aeternus), turned orbs.
  4. UFO, normal, 3x: hills.
  5. Ball, normal and mini, 1x: floor hills and hanging hills under a block ceiling.
"""
import argparse
import sys

from sim import gdsave

HEADER = ("kS38,1_40_2_125_3_255_11_255_12_255_13_255_4_-1_6_1000_7_1_15_1_18_0_8_1|"
          "1_0_2_102_3_255_11_255_12_255_13_255_4_-1_6_1001_7_1_15_1_18_0_8_1|"
          "1_0_2_102_3_255_11_255_12_255_13_255_4_-1_6_1009_7_1_15_1_18_0_8_1|"
          "1_255_2_255_3_255_11_255_12_255_13_255_4_-1_6_1002_5_1_7_1_15_1_18_0_8_1|"
          "1_255_2_255_3_255_11_255_12_255_13_255_4_-1_6_1004_7_1_15_1_18_0_8_1|,"
          "kA13,0,kA15,0,kA16,0,kA14,,kA6,0,kA7,0,kA25,0,kA17,0,kA18,0,kS39,0,kA2,0,kA3,0,kA8,0,"
          "kA4,0,kA9,0,kA10,0,kA22,0,kA23,0,kA24,0,kA27,0,kA40,0,kA48,0,kA41,0,kA42,0,kA28,0,kA29,0,"
          "kA31,0,kA32,0,kA36,0,kA43,0,kA44,0,kA45,0,kA46,0,kA47,0,kA33,0,kA34,0,kA35,0,kA37,0,"
          "kA38,0,kA39,0,kA19,0,kA26,0,kA20,0,kA21,0,kA11,0")

BLOCK, SLOPE45, SLOPE21 = 1, 289, 291
GRAV_NORMAL, GRAV_FLIP = 10, 11
CUBE, BALL, UFO = 12, 47, 111
NORMAL_SIZE, MINI = 99, 101
SPEED_1X, SPEED_3X = 201, 203
YELLOW_PAD, PINK_PAD, BLUE_PAD = 35, 140, 67
YELLOW_ORB, PINK_ORB, BLUE_ORB = 36, 141, 84
G = 90.0   # the ground's top


class Level:
    def __init__(self):
        self.objs = []
        self.tests = set()   # indices of test objects (left out for the layout check)

    def test(self, *a, **k):
        self.tests.add(len(self.objs))
        self.add(*a, **k)

    def add(self, id_, x, y, rot=0.0, fx=False, fy=False, sx=None, sy=None):
        o = [1, id_, 2, round(x, 3), 3, round(y - G, 3)]
        if rot:
            o += [6, rot]
        if fx:
            o += [4, 1]
        if fy:
            o += [5, 1]
        if sx is not None:
            o += [128, sx]
        if sy is not None:
            o += [129, sy]
        self.objs.append(",".join(str(v) for v in o))

    def block(self, x0, y0, n=1, rows=1):
        """n blocks along x from x0 (left edge), `rows` high from y0 (bottom edge)."""
        for i in range(n):
            for j in range(rows):
                self.add(BLOCK, x0 + 15 + 30 * i, y0 + 15 + 30 * j)

    def portal(self, id_, x, lo=G, hi=None):
        """A column of portals at x covering y lo..hi (one portal is ~75-90 tall)."""
        hi = hi if hi is not None else lo + 90
        y = lo + 40
        while True:
            self.add(id_, x, y)
            if y + 40 >= hi:
                break
            y += 75

    def hill(self, x0, s, height, top, steep=True, hang=False):
        """A hill of `height` blocks on a floor at s (or hanging from a ceiling at s), slopes up,
        `top` blocks flat, slopes down. Returns the x where it ends."""
        w = 30 if steep else 60
        sid = SLOPE45 if steep else SLOPE21
        d = -1 if hang else 1
        x = x0
        for k in range(height):                       # going up (into the ceiling when hanging)
            cx = x + w / 2 + w * k
            self.add(sid, cx, s + d * (15 + 30 * k), fy=hang)
            for j in range(k):
                for b in range(w // 30):
                    self.add(BLOCK, x + w * k + 15 + 30 * b, s + d * (15 + 30 * j))
        x += w * height
        for i in range(top):
            for j in range(height):
                self.add(BLOCK, x + 15 + 30 * i, s + d * (15 + 30 * j))
        x += 30 * top
        for k in range(height):                       # coming down
            lvl = height - 1 - k
            cx = x + w / 2 + w * k
            self.add(sid, cx, s + d * (15 + 30 * lvl), fx=True, fy=hang)
            for j in range(lvl):
                for b in range(w // 30):
                    self.add(BLOCK, x + w * k + 15 + 30 * b, s + d * (15 + 30 * j))
        return x + w * height

    def string(self, tests=True):
        objs = [o for i, o in enumerate(self.objs) if tests or i not in self.tests]
        return HEADER + ";" + ";".join(objs) + ";"


def build() -> tuple[str, list]:
    L = Level()
    marks = []   # (x, what) for the summary

    # 1. Cube --------------------------------------------------------------------------------
    x = 300
    marks.append((x, "cube: 45 square, top 0.5 above the ground"))
    L.test(SLOPE45, x + 15, G + 0.5 - 15)
    L.test(SLOPE45, x + 15, G + 0.5 - 15, fx=True, fy=True)
    x = 420
    marks.append((x, "cube: 2:1 square, top 0.5 above the ground"))
    L.test(SLOPE21, x + 30, G + 0.5 - 15)
    L.test(SLOPE21, x + 30, G + 0.5 - 15, fx=True, fy=True)
    # lone hanging slopes, flat top at 152 (a jump lands on it), underside 2 above the cube's head
    x = 640
    marks.append((x, "cube: hanging 45 slope, jump onto its flat top / into its underside"))
    L.test(SLOPE45, x + 15, 152 - 15, fy=True)
    x = 820
    marks.append((x, "cube: hanging 2:1 slope, the same"))
    L.test(SLOPE21, x + 30, 152 - 15, fy=True)
    # upside down under a block ceiling; blue pads turned sideways
    x = 1000
    L.block(x - 30, 240, n=18)                       # ceiling: bottom at 240
    L.portal(GRAV_FLIP, x + 20, G, 240)
    marks.append((x + 20, "cube: gravity portal (flip) to a ceiling at 240"))
    L.test(BLUE_PAD, x + 200, 225, rot=90)
    marks.append((x + 200, "cube: blue pad turned 90 at the ceiling (upside down)"))
    L.test(BLUE_PAD, x + 330, 105, rot=270)
    marks.append((x + 330, "cube: blue pad turned 270 on the floor (normal gravity)"))
    L.portal(GRAV_NORMAL, x + 400, G, 240)
    L.add(GRAV_FLIP, x + 500, G + 40)                  # both on the same step (test)
    L.add(GRAV_NORMAL, x + 500, G + 40)
    marks.append((x + 500, "cube: flip and normal gravity portals on the same step"))
    L.portal(GRAV_NORMAL, x + 560, G, 390)             # whatever that did, normal again

    # 2. UFO, normal, 1x ---------------------------------------------------------------------
    x = 1600
    L.portal(UFO, x, G, 390)
    marks.append((x, "UFO 1x: floor hills"))
    x += 120
    x = L.hill(x, G, 1, 2, steep=True) + 90
    L.test(YELLOW_PAD, x - 45, G + 2, rot=30)
    x = L.hill(x, G, 2, 2, steep=True) + 90
    L.test(YELLOW_PAD, x - 45, G + 2, rot=330)
    x = L.hill(x, G, 1, 2, steep=False) + 90
    L.test(PINK_PAD, x - 45, G + 2.5, rot=45)
    x = L.hill(x, G, 2, 1, steep=False) + 90
    # chain: 2:1 then 45 up, top, 45 then 2:1 down
    marks.append((x, "UFO 1x: 2:1 into 45 chain"))
    L.add(SLOPE21, x + 30, G + 15)
    L.add(SLOPE45, x + 75, G + 45)
    L.block(x + 60, G, n=1)
    L.block(x + 90, G, n=3, rows=2)
    L.add(SLOPE45, x + 195, G + 45, fx=True)
    L.block(x + 180, G, n=1)
    L.add(SLOPE21, x + 240, G + 15, fx=True)
    x += 330
    # turned orbs in the air (touching them is free; clicks optional)
    marks.append((x, "UFO 1x: turned orbs and negatively scaled turned orbs in the air"))
    for i, (oid, rot) in enumerate([(YELLOW_ORB, 30), (PINK_ORB, 45), (YELLOW_ORB, 60), (BLUE_ORB, 300)]):
        L.test(oid, x + 60 + 90 * i, 200 + 40 * (i % 2), rot=rot)
    x += 420
    for i, rot in enumerate([30, 45, 60]):
        L.test(YELLOW_ORB, x + 60 + 90 * i, 210, rot=rot, sx=-1, sy=-1)
    x += 330
    # upside down on the band's ceiling (390) under hanging hills
    L.portal(GRAV_FLIP, x, G, 390)
    marks.append((x, "UFO 1x upside down: hanging hills on the ceiling"))
    x += 120
    x = L.hill(x, 390, 1, 2, steep=True, hang=True) + 90
    x = L.hill(x, 390, 2, 1, steep=True, hang=True) + 90
    x = L.hill(x, 390, 1, 2, steep=False, hang=True) + 90
    x = L.hill(x, 390, 2, 1, steep=False, hang=True) + 60
    L.portal(GRAV_NORMAL, x, G, 390)

    # 3. UFO, mini --------------------------------------------------------------------------
    x += 90
    L.portal(MINI, x, G, 390)
    marks.append((x, "UFO mini: floor hills, turned pads, blue pad turned 334"))
    x += 90
    x = L.hill(x, G, 1, 2, steep=True) + 90
    L.test(YELLOW_PAD, x - 45, G + 2, rot=30)
    x = L.hill(x, G, 1, 2, steep=False) + 90
    L.test(BLUE_PAD, x - 45, G + 3, rot=334)            # flips it up: back down at the next portal
    x += 90
    for i, (oid, rot) in enumerate([(YELLOW_ORB, 30), (PINK_ORB, 60)]):
        L.test(oid, x + 60 + 90 * i, 300, rot=rot)       # near the ceiling, where it goes after the pad
    x += 270
    L.portal(GRAV_NORMAL, x, G, 390)
    x += 60
    x = L.hill(x, G, 2, 1, steep=True) + 90
    x = L.hill(x, G, 2, 1, steep=False) + 60
    L.portal(NORMAL_SIZE, x, G, 390)

    # 4. UFO, normal, 3x --------------------------------------------------------------------
    x += 90
    L.portal(SPEED_3X, x, G, 390)
    marks.append((x, "UFO 3x: floor hills"))
    x += 150
    x = L.hill(x, G, 1, 3, steep=True) + 150
    x = L.hill(x, G, 2, 2, steep=True) + 150
    x = L.hill(x, G, 1, 3, steep=False) + 150
    x = L.hill(x, G, 2, 2, steep=False) + 120
    L.portal(SPEED_1X, x, G, 390)

    # 5. Ball, normal then mini, under a block ceiling at 240 --------------------------------
    x += 120
    ball0 = x
    L.portal(BALL, x, G, 240)
    marks.append((x, "ball: floor hills and hanging hills (ceiling at 240)"))
    x += 120
    for steep, hang in [(True, False), (True, True), (False, False), (False, True)]:
        x = L.hill(x, 240 if hang else G, 1, 2, steep=steep, hang=hang) + 120
    L.portal(MINI, x, G, 240)
    marks.append((x, "ball mini: the same"))
    x += 90
    for steep, hang in [(True, False), (True, True), (False, False), (False, True)]:
        x = L.hill(x, 240 if hang else G, 1, 2, steep=steep, hang=hang) + 120
    L.portal(NORMAL_SIZE, x, G, 240)
    L.portal(GRAV_NORMAL, x + 60, G, 240)
    L.portal(CUBE, x + 120, G, 240)
    end = x + 300
    L.block(ball0 - 120, 240, n=int((end - ball0 + 120) // 30))   # the ceiling
    L.block(end, G, n=1)   # level end marker on the floor (nothing after it)
    return L.string(), marks, L.string(tests=False)


def check(level_string):
    """Run the simulator with no input and with a few tap patterns: no deaths before the end."""
    from converter.convert import convert
    from sim.level import Level as SimLevel
    from sim.physics import Sim, Unsupported
    import json
    import os
    import tempfile
    lv = convert(level_string, "test level", "string")
    path = os.path.join(tempfile.gettempdir(), "dynamicbutter_testlevel.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lv, f)
    level = SimLevel.load(path)
    end = max(o.x for o in level.objects)
    for name, pattern in [("no input", lambda t: False), ("hold", lambda t: True),
                          ("tap every 40", lambda t: t % 40 < 3), ("tap every 17", lambda t: t % 17 < 2)]:
        sim = Sim(level)
        p = sim.player
        t, why = 0, "reached the end"
        try:
            while p.x < end and t < 40000:
                p = sim.step(pattern(t))
                t += 1
                if p.dead:
                    why = f"died at x={p.x:.0f} y={p.y:.0f}: {p.killer}"
                    break
            if t >= 40000:
                why = f"stuck at x={p.x:.0f}"
        except Unsupported as e:
            why = f"sim stops at x={p.x:.0f} ({p.mode}): {e}"
        print(f"  {name:13s} {why}")
    return lv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="add it to CCLocalLevels.dat (GD closed)")
    ap.add_argument("--name", default="DB test 1")
    a = ap.parse_args()
    s, marks, bare = build()
    print(f"{s.count(';') - 1} objects")
    for x, what in marks:
        print(f"  x {x:6.0f}  {what}")
    print("with the test objects:")
    check(s)
    print("layout only (test objects left out):")
    check(bare)
    if a.write:
        import subprocess
        out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout
        if "GeometryDash.exe" in out:
            sys.exit("Geometry Dash is running: close it first (it rewrites the save on exit)")
        backup = gdsave.add_local_level(a.name, s, creator="fubaxa")
        print(f"added '{a.name}' to the created levels (backup: {backup})")


if __name__ == "__main__":
    main()
