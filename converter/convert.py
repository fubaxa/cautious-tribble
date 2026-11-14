"""Convert a full Geometry Dash level into the minimum the simulator needs.

    python -m converter.convert --local <name>      a level you made (CCLocalLevels.dat)
    python -m converter.convert --saved <name|id>   a level you downloaded (CCGameManager.dat)
    python -m converter.convert --string <file>     a raw level string in a file
        [-o out.json] [--report-only]

Output (JSON): start settings, the level's physics options, and only the objects that can affect
the player: solids, slopes, hazards, portals, pads, orbs, each with its hitbox, plus the gameplay
triggers. Decoration, coins and visual triggers are dropped. What each object ID is comes from the
game's own object table (sim/objects.py); an ID missing from it is counted under "unknown".
"""
import argparse
import collections
import json
import sys

from sim import gdsave, objects

FORMAT = 1
EDITOR_Y_OFFSET = 90.0  # level-string y=0 is the floor's top, which is y=90 in game

START_SPEED = {"0": "1x", "1": "0.5x", "2": "2x", "3": "3x", "4": "4x"}
START_MODE = {"0": "cube", "1": "ship", "2": "ball", "3": "ufo", "4": "wave", "5": "robot",
              "6": "spider", "7": "swing"}
# Level-string keys of the per-level physics options (names from the Geode bindings).
PHYSICS_KEYS = {
    "kA27": "allowMultiRotation", "kA31": "enablePlayerSqueeze", "kA32": "fixGravityBug",
    "kA33": "fixNegativeScale", "kA34": "fixRobotJump", "kA37": "dynamicLevelHeight",
    "kA38": "sortGroups", "kA39": "fixRadiusCollision", "kA40": "enable22Changes",
    "kA41": "allowStaticRotate", "kA42": "reverseSync", "kA45": "decreaseBoostSlide",
    "kA48": "enableImpulseFix",
}


def _num(d, key, default=0.0):
    try:
        return float(d.get(key, default))
    except ValueError:
        return default


def convert(level_string: str, name: str = "", source: str = "") -> dict:
    parts = level_string.split(";")
    head = parts[0].split(",")
    start = dict(zip(head[0::2], head[1::2]))

    settings = {
        "mode": START_MODE.get(start.get("kA2", "0"), start.get("kA2")),
        "speed": START_SPEED.get(start.get("kA4", "0"), start.get("kA4")),
        "mini": start.get("kA3") == "1",
        "dual": start.get("kA8") == "1",
        "flipped": start.get("kA11") == "1",
        "mirror": start.get("kA28") == "1",
        "platformer": start.get("kA22") == "1",
        "two_player": start.get("kA10") == "1",
        # A key missing from the level (levels older than 2.2) means the option is off.
        "physics": {v: start.get(k) == "1" for k, v in PHYSICS_KEYS.items()},
        "other_keys": {k: start[k] for k in sorted(start) if k.startswith("kA")
                       and k not in PHYSICS_KEYS and k not in ("kA2", "kA3", "kA4", "kA8", "kA10",
                                                               "kA11", "kA22", "kA28")
                       and start[k] not in ("", "0")},
    }

    out_objs, triggers = [], []
    unknown = collections.Counter()
    ignored = collections.Counter()
    kinds = collections.Counter()
    no_touch = 0
    moved_groups = set()
    first_in_group, parent_of = {}, {}   # anchors for move-to-target triggers
    last_x = 0.0   # the furthest object of any kind: GD ends the level about 40 past it
    for order, p in enumerate(parts[1:]):
        if not p:
            continue
        a = p.split(",")
        d = dict(zip(a[0::2], a[1::2]))
        oid = int(_num(d, "1"))
        x, y = _num(d, "2"), _num(d, "3") + EDITOR_Y_OFFSET
        last_x = max(last_x, x)
        groups = [int(g) for g in d.get("57", "").split(".") if g]
        for g in groups:
            first_in_group.setdefault(g, (x, y, groups))
            if d.get("34") == "1":
                parent_of.setdefault(g, (x, y, groups))
        i = objects.info(oid)
        if i is None:
            unknown[oid] += 1
            continue
        if i.kind is None:
            ignored["decoration" if i.gd_type == 7 else "visual trigger"] += 1
            continue
        if i.kind == objects.PICKUP:
            ignored["coin / item"] += 1
            continue
        if i.kind == objects.TRIGGER:
            t = {"id": oid, "type": i.extra, "x": x, "y": y,
                 "keys": {k: v for k, v in d.items() if k not in ("1", "2", "3", "155", "57")}}
            if groups:
                t["groups"] = groups
            triggers.append(t)
            for key in ("51", "71"):
                if d.get(key, "0") not in ("", "0"):
                    moved_groups.add(int(_num(d, key)))
            continue
        if d.get("121") == "1":  # "No Touch": no collision at all
            no_touch += 1
            continue
        scale = _num(d, "32", 1.0) or 1.0
        sx = (_num(d, "128", 1.0) or 1.0) * (scale if "128" not in d else 1.0)
        sy = (_num(d, "129", 1.0) or 1.0) * (scale if "129" not in d else 1.0)
        o = objects.make(oid, x, y, _num(d, "6"), sx, sy)
        o.flip_x ^= d.get("4") == "1"
        o.flip_y ^= d.get("5") == "1"
        rec = {"id": oid, "kind": o.kind, "x": x, "y": y, "w": o.w, "h": o.h, "n": order}
        if o.extra:
            rec["type"] = o.extra
        if o.rotation:
            rec["rot"] = o.rotation
        if o.quarter:
            rec["quarter"] = True
            rec["turn"] = o.turn
        if o.kind == objects.SLOPE:
            rec["bw"], rec["bh"] = o.base_w, o.base_h
        if o.flip_x:
            rec["flip_x"] = True
        if o.flip_y:
            rec["flip_y"] = True
        if groups:
            rec["groups"] = groups
        if d.get("99") == "1":
            rec["multi"] = True
        if o.radius:
            rec["radius"] = o.radius
        if o.kind == objects.TELEPORT:
            rec["tp"] = _num(d, "54")
        if o.ox or o.oy:
            rec["ox"], rec["oy"] = o.ox, o.oy
        kinds[o.kind] += 1
        out_objs.append(rec)

    out_objs.sort(key=lambda r: (r["x"], r["y"]))
    # The object a move-to-target trigger measures a group's position by: its group parent
    # (key 34), else its first object in level order - possibly decoration (provisional).
    anchors = []
    used = {int(_num(t["keys"], k)) for t in triggers if t["type"] == "MoveCom" for k in ("395", "71")}
    for g in sorted(used - {0}):
        a = first_in_group.get(g)
        if a:
            anchors.append({"g": g, "x": a[0], "y": a[1], "groups": a[2]})
    triggers.sort(key=lambda r: (r["x"], r["y"]))
    affected = sum(1 for r in out_objs if moved_groups.intersection(r.get("groups", ())))
    return {
        "format": FORMAT,
        "name": name,
        "source": source,
        "settings": settings,
        "last_x": last_x,
        "objects": out_objs,
        "triggers": triggers,
        "anchors": anchors,
        "report": {
            "objects_in_level": sum(1 for p in parts[1:] if p),
            "kept": dict(kinds),
            "gameplay_triggers": dict(collections.Counter(t["type"] for t in triggers)),
            "objects_in_triggered_groups": affected,
            "no_touch_dropped": no_touch,
            "ignored": dict(ignored),
            "unknown": {str(k): v for k, v in unknown.most_common()},
        },
    }


def summary(level: dict) -> str:
    r, s = level["report"], level["settings"]
    on = [k for k, v in s["physics"].items() if v]
    lines = [
        f"{level['name'] or '(unnamed)'}: {r['objects_in_level']} objects in the level",
        f"  start: {s['mode']} {s['speed']}{' mini' if s['mini'] else ''}{' dual' if s['dual'] else ''}"
        f"{' flipped' if s['flipped'] else ''}{' platformer' if s['platformer'] else ''}; "
        f"physics options on: {len(on)}/13",
        f"  kept {len(level['objects'])}: " + ", ".join(f"{n} {k}" for k, n in sorted(r["kept"].items())),
    ]
    if r["gameplay_triggers"]:
        lines.append(f"  gameplay triggers {len(level['triggers'])}: " + ", ".join(
            f"{n} {k}" for k, n in sorted(r["gameplay_triggers"].items()))
            + f" (they act on {r['objects_in_triggered_groups']} kept objects)")
    unk = r["unknown"]
    if unk:
        top = ", ".join(f"{k} x{n}" for k, n in list(unk.items())[:12])
        lines.append(f"  unknown IDs: {sum(unk.values())} objects of {len(unk)} types (top: {top})")
    dropped = [f"{n} {k}" for k, n in sorted(r["ignored"].items())]
    if r["no_touch_dropped"]:
        dropped.append(f"{r['no_touch_dropped']} no-touch")
    lines.append("  dropped: " + (", ".join(dropped) or "nothing"))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--local", help="name of a level you made")
    src.add_argument("--saved", help="name or ID of a downloaded level")
    src.add_argument("--string", help="file with a raw level string")
    ap.add_argument("-o", "--out", help="output JSON path (default: levels/<name>.json)")
    ap.add_argument("--report-only", action="store_true", help="print the summary, write nothing")
    a = ap.parse_args()
    try:
        if a.local:
            name, s, source = a.local, gdsave.local_level(a.local), "local"
        elif a.saved:
            name, s, source = a.saved, gdsave.saved_level(a.saved), "saved"
        else:
            name, source = a.string, "string"
            s = gdsave.decode_level_string(open(a.string, encoding="utf-8").read())
    except KeyError as e:
        sys.exit(str(e.args[0]))
    level = convert(s, name, source)
    print(summary(level))
    if not a.report_only:
        import os
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in str(name)).strip() or "level"
        out = a.out or os.path.join("levels", safe + ".json")
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(level, f, separators=(",", ":"))
        print(f"  wrote {out} ({os.path.getsize(out)} bytes; level string was {len(s)} chars)")


if __name__ == "__main__":
    main()
