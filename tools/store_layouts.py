"""Store the level each regression trace was played on as a layout file next to the traces
(traces/layouts/), for traces recorded before DynamicButter saved layouts itself, and point
tools/regress_set.txt at it. A level is only stored when converting it gives exactly the converted
level the regression has been using (objects, triggers, anchors): then it's the played layout.

    ./run.sh tools.store_layouts
"""
import json
import os

from converter.convert import convert
from sim import gdsave
from tools.regress import SET, TRACES


def fnv(s: str) -> str:
    h = 1469598103934665603
    for c in s.encode("utf-8"):
        h = ((h ^ c) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def source_string(old):
    if old.get("name") == "DB test 1":
        from tools import testlevel     # edited in the save after its trace: the built version
        return testlevel.build()[0]
    if old.get("source") == "local":
        return gdsave.local_level(old["name"])
    if old.get("source") == "saved":
        return gdsave.saved_level(old["name"])
    raise KeyError(f"source {old.get('source')!r}")


def main():
    lines = open(SET, encoding="utf-8").read().splitlines()
    out, done = [], {}
    os.makedirs(os.path.join(TRACES, "layouts"), exist_ok=True)
    for line in lines:
        if not line.strip() or line.startswith("#"):
            out.append(line)
            continue
        name, trace, level = [p.strip() for p in line.split("|")][:3]
        if level.startswith("layouts/"):
            out.append(line)
            continue
        if level not in done:
            done[level] = None
            try:
                old = json.load(open(level, encoding="utf-8"))
                s = source_string(old)
                new = convert(s, old.get("name", ""), old.get("source", ""))
                if all(new[k] == old.get(k) for k in ("objects", "triggers", "anchors")):
                    lid = old["name"] if old.get("source") == "saved" else "0"
                    fn = f"layouts/{lid}_{fnv(s)}.txt"
                    with open(os.path.join(TRACES, fn), "w", encoding="utf-8", newline="") as f:
                        f.write(gdsave.encode_level_string(s))   # GD's own compressed form
                    done[level] = fn
                    print(f"{level}: stored as {fn}")
                else:
                    print(f"{level}: the save's version differs from the converted level: kept")
            except (KeyError, OSError) as e:
                print(f"{level}: {e}: kept")
        out.append(f"{name} | {trace} | {done[level]}" if done[level] else line)
    with open(SET, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
