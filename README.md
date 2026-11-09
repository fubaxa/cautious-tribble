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
```

Plain Python 3.10+, no dependencies yet.

## Trace diff

```
./run_diff.sh <trace.csv> --level <level name> [--attempt N]
```

The level is read from your own `CCLocalLevels.dat`, so it must be the same version of the level
the trace was recorded on.

## Level converter

```
./run.sh converter.convert --local <name>       # a level you made
./run.sh converter.convert --saved <id|name>    # a level you downloaded
./run.sh converter.convert --string <file>      # a raw level string
```

Writes `levels/<name>.json`: start settings, the 13 physics options, and the objects that can touch
the player (solids, slopes, hazards, portals, pads, orbs) with hitboxes, plus gameplay triggers.
What each object ID is comes from `sim/data/objects_2.2091.csv`, the game's own object table as
dumped by DynamicButter's "Object dump" setting (re-dump after a game update).

## Coverage

```
./run.sh tools.coverage <trace.csv>...
```
