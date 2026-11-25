"""Run the regression set (tools/regress_set.txt) in parallel and compare with the baseline.

    ./run.sh tools.regress                    # all traces, half the CPU cores + 4 (16 of 24), low priority
    ./run.sh tools.regress Sailent Tartarus   # only these
    ./run.sh tools.regress --save             # also store the result as the new baseline

Each trace runs in its own process at below-normal priority (the PC stays usable), biggest first.
Full tracediff output per trace goes to .regress/<name>.txt. The summary prints matched steps and
differences per trace and the change from tools/regress_baseline.txt.
"""
import argparse
import contextlib
import io
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SET = os.path.join(HERE, "regress_set.txt")
BASELINE = os.path.join(HERE, "regress_baseline.txt")
OUT = os.path.join(ROOT, ".regress")
TRACES = os.path.join(os.environ.get("LOCALAPPDATA", ""), "GeometryDash", "geode", "mods",
                      "fubaxa.dynamicbutter", "traces")


def read_set():
    out = []
    for line in open(SET, encoding="utf-8"):
        if line.strip() and not line.startswith("#"):
            parts = [p.strip() for p in line.split("|")]
            # an optional 4th column: the macro the run played (exact times of clicks between steps)
            out.append(tuple(parts[:3]) + ((parts[3] if len(parts) > 3 else None),))
    return out


def trace_path(name):
    p = os.path.join(TRACES, name)
    if not os.path.exists(p) and os.path.exists(p + ".xz"):
        p += ".xz"
    return p


def _low_priority():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    else:
        os.nice(10)


def run_one(name, trace, level, macro=None):
    _low_priority()
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    os.environ.setdefault("PRACTICE", "1")
    from tools import tracediff
    buf = io.StringIO()
    t = time.time()
    try:
        with contextlib.redirect_stdout(buf):
            tracediff.run(trace_path(trace), level,
                          macro=os.path.join(TRACES, macro) if macro else None)
        err = ""
    except Exception as e:      # keep going: report it in the summary
        import traceback
        err = traceback.format_exc()
    text = buf.getvalue() + err
    with open(os.path.join(OUT, name + ".txt"), "w", encoding="utf-8") as f:
        f.write(text)
    matched = sum(int(m.group(1)) for m in re.finditer(r"^\s+ticks\s+\d+-\s*\d+:\s+(\d+) matched", text, re.M))
    diffs = text.count("DIFFERENCE")
    return name, matched, diffs, bool(err), time.time() - t


def read_baseline():
    b = {}
    if os.path.exists(BASELINE):
        for line in open(BASELINE, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                n, m, d = line.split()
                b[n] = (int(m), int(d))
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--jobs", type=int, default=min(os.cpu_count() or 2, max(1, (os.cpu_count() or 2) // 2 + 4)))
    ap.add_argument("--save", action="store_true", help="store this run as the new baseline")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    todo = [r for r in read_set() if not a.names or r[0] in a.names]
    todo.sort(key=lambda r: -os.path.getsize(trace_path(r[1])) if os.path.exists(trace_path(r[1])) else 0)
    base = read_baseline()
    t0 = time.time()
    results = {}
    from tools.regress import run_one as worker   # by module name: picklable for the workers
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(worker, *r) for r in todo]
        for f in as_completed(futs):
            name, m, d, err, dt = f.result()
            results[name] = (m, d, err)
            print(f"  done {name:12s} {m:8d} matched {d:5d} diffs  {dt:6.0f}s{'  ERROR' if err else ''}", flush=True)
    print(f"\n{len(results)} traces in {time.time() - t0:.0f}s ({a.jobs} processes)\n")
    total = 0
    for name, *_ in todo:
        m, d, err = results[name]
        bm, bd = base.get(name, (None, None))
        change = "" if bm is None else f"{m - bm:+d}"
        if bm is not None:
            total += m - bm
        flag = "  LOWER" if bm is not None and m < bm else ""
        print(f"{name:12s} {m:8d} {d:5d}  {change:>8s}{flag}{'  ERROR' if err else ''}")
    print(f"\ntotal change vs baseline: {total:+d}")
    if a.save:
        merged = dict(base)
        merged.update({n: (m, d) for n, (m, d, _) in results.items()})
        with open(BASELINE, "w", encoding="utf-8") as f:
            f.write("# name matched diffs (tools/regress.py --save)\n")
            for n in sorted(merged):
                f.write(f"{n} {merged[n][0]} {merged[n][1]}\n")
        print(f"baseline saved: {BASELINE}")


if __name__ == "__main__":
    main()
