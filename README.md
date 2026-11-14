# cautious-tribble

A headless Geometry Dash 2.2091 physics simulator for training an AI, built to match the real game
step for step. See [PLAN.md](PLAN.md) for the project plan and [NOTES.md](NOTES.md) for what's
measured so far, and [NEEDS.md](NEEDS.md) for what's still missing.

Ground truth comes from DynamicButter's physics trace (a Geode mod, used only as a measurement tool).

## Layout

```
sim/        physics (sim/physics.py), constants, object table, save reader, trace reader
converter/  convert.py: full GD level -> only what the simulator needs (JSON)
tools/      tracediff.py: replay a trace's inputs and report the first step that differs
            coverage.py: what the recorded traces cover (source of NEEDS.md)
            solve.py: find a macro that beats a level (saved as .gdr2 for DynamicButter)
```

Plain Python 3.10+, no dependencies yet.

## Trace diff

```
./run_diff.sh <trace.csv> --level <level name> [--attempt N]
```

The level is read from your own `CCLocalLevels.dat`, so it must be the same version of the level
the trace was recorded on.

## Solver: a macro for a level

```
./run.sh tools.solve --local <name> [--prefer early|middle|late] [--min-gap 12] [-o file.gdr2]
./run.sh tools.solve --saved <id|name> ...      # a downloaded level
./run.sh tools.solve --json levels/<name>.json  # an already converted level
```

Converts the level, searches for a route in the simulator, replays the result from the start to
check it, and saves a `.gdr2` into DynamicButter's macros folder (`<name> (solver <prefer>).gdr2`),
with each click's Dynamic window. It searches by click windows, not by steps: the run goes on
without input until it dies; only steps where a press can matter are tried (on the ground, an orb
in reach, the last steps before a landing); clicks ending in exactly the same state are one window;
the largest window is tried first and hopeless states are remembered. `--prefer` picks the step
inside each window; `--min-gap` is the fewest steps between two presses (12 = 20 clicks/s; holding
is free and is tried when single clicks can't make it). Every End 2: 826 clicks in about 8 minutes.
Cube, ball and wave levels only (the simulator's modes); the click model is made for the cube.

## Level converter

```
./run.sh converter.convert --local <name>       # a level you made
./run.sh converter.convert --saved <id|name>    # a level you downloaded
./run.sh converter.convert --string <file>      # a raw level string
```

Writes `levels/<name>.json`: start settings, the 13 physics options, and the objects that can touch
the player (solids, slopes, hazards, portals, pads, orbs) with hitboxes, plus gameplay triggers. Triggers
that act on a group (move, rotate, follow, toggle, stop, spawn, collision, count, ...) are dropped
when they can never reach gameplay: nothing in their target groups is a kept object or a kept
trigger, and no kept trigger reads a position from them (Every End 2: 6,615 -> 673 triggers, same
results, a third faster).
What each object ID is comes from `sim/data/objects_2.2091.csv`, the game's own object table as
dumped by DynamicButter's "Object dump" setting (re-dump after a game update).

## Coverage

```
./run.sh tools.coverage <trace.csv>...
```
