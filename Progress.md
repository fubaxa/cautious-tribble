# Progress

State of the project as of 2026-11-19: what has been built, what has been measured, how it's
tested, and what is still unresolved. Two repositories take part:

- **DynamicButter** (`GeodeMod/DynamicButter`, branch `claude/geometry-dash-ai-training-plan-b0uzfd`):
  a Geode mod for Geometry Dash 2.2091. It records and plays macros, and it is the measuring
  instrument: it writes per-step physics traces of real play.
- **cautious-tribble-sim** (this repository, branch `main`): a headless Python simulator of GD
  2.2091's physics, a level converter, a trace-comparison tool, a regression runner and a solver
  that finds macros.

The detailed evidence for every rule below is in [NOTES.md](NOTES.md), the GD editor guide
findings in [docs/gd_editor_guide.md](docs/gd_editor_guide.md), and the running list of open items
in [NEEDS.md](NEEDS.md).

---

## 1. Where things stand, in numbers

### 1.1 The regression set

36 recorded traces from 25 levels, replayed in the simulator step by step against the game
(`./run.sh tools.regress`, 76 s on 12 processes under PyPy):

| | |
|---|---|
| Traces | 36 |
| Attempts | 4,817 |
| Physics steps recorded | 2,858,105 |
| Steps where the simulator matched the game exactly | **2,017,542 (70.6 %)** |
| Stops caused by a value that differs | 5,910 |
| Stops caused by something the simulator doesn't do yet ("unsupported") | 610 |
| Deaths reproduced on exactly the game's step | 2,817 |

A "matched" step means x, y, yVel, xVel, gravity direction, on-ground, game mode, size and death
all agree with the game (players 1 and 2). After a stop, the comparison tool puts the simulator
back into the game's state on a later stable step and carries on, so one trace can contain many
matched stretches.

### 1.2 Runs that match the game completely

| Trace | Content | Result |
|---|---|---|
| **Every End 2** (bot run, 2026-11-17) | A full real level: cube, ball, moving platforms, teleports, breakable blocks, 673 triggers | **105,287 steps from the start to the level end, 0 differences** |
| t1113d (snap test level) | cube staircases | 6,198 steps, 0 differences |
| t1113 (snap test level) | cube landings | 5,096 steps, 0 differences |
| ship1 (ship test level) | ship flight, orbs, pads | 22,195 steps, 0 differences |
| ship2 (ship test level) | ship spider throws into hazards | 13,957 steps, 0 differences |
| ship3 (ship test level) | ship spider throws | 16,095 steps, 1 difference |

Earlier runs that also matched completely (no longer in the set): the first `test` level (7,093
steps, all 2.2 options on), the wave test level (19,680 steps), Sonic Wave 2's wave parts (4,701
steps), and all five older Every End 2 recordings (a bot run and 4 practice sessions, 494
attempts).

### 1.3 Per trace (current baseline, `tools/regress_baseline.txt`)

| Name | Level | Attempts | Matched | Recorded steps | Differences |
|---|---|---|---|---|---|
| EveryEnd2 | Every End 2 (bot) | 1 | 105,287 | 105,535 | 0 |
| Sailent | Sailent Clubstar (89054024) | 738 | 85,731 | 112,560 | 97 |
| Aeternus | Aeternus (102647436, bot) | 561 | 62,865 | 92,681 | 247 |
| CosmicA | Cosmic Salad (78676189) | 550 | 529,354 | 680,500 | 1,008 |
| CosmicB | Cosmic Salad | 196 | 51,492 | 82,529 | 125 |
| CosmicC | Cosmic Salad | 108 | 28,232 | 49,821 | 95 |
| Flamewall | Flamewall (126242564) | 819 | 202,625 | 325,770 | 1,021 |
| Tartarus | Tartarus (59075347) | 215 | 74,699 | 93,790 | 96 |
| SubSonic | SubSonic (33387622) | 534 | 105,897 | 198,251 | 563 |
| DoubleDash | Double Dash (59315849) | 59 | 19,233 | 52,220 | 307 |
| Artifice | Shitty Artifice (58965186) | 21 | 42,830 | 58,363 | 129 |
| part11 | Shitty mix part 11 (63446913) | 20 | 36,541 | 46,639 | 73 |
| part14 | Shitty mix part 14 (81534446) | 23 | 56,320 | 79,046 | 146 |
| Halluc | The Hallucination (81139702), playback | 130 | 58,164 | 87,678 | 266 |
| HallucRec | The Hallucination, recording | 256 | 54,259 | 90,373 | 335 |
| AkiraA | AKIRA (88421468), practice | 137 | 33,485 | 54,426 | 116 |
| AkiraB | AKIRA, recording and playbacks | 63 | 45,347 | 69,679 | 154 |
| Aurorae | Aurorae 2 (local) | 20 | 14,090 | 27,799 | 104 |
| ChopStep | ChopStep 2 (local) | 56 | 34,506 | 49,849 | 108 |
| Llorona | La Llorona 2 (local) | 12 | 11,554 | 19,799 | 63 |
| NR2a | Night Rider 2 (local) | 11 | 11,992 | 22,880 | 77 |
| NR2b | Night Rider 2 | 67 | 34,504 | 75,144 | 321 |
| Orochi | Shitty Orochi buff 3 (local) | 65 | 85,606 | 106,606 | 152 |
| BOTS | BOTS phase 4 startpo (local) | 2 | 29,189 | 35,603 | 51 |
| LostLove | Lost Love startpos 2 (local) | 16 | 16,653 | 22,441 | 34 |
| DBtest | DB test 1 (own test level) | 10 | 24,735 | 30,338 | 56 |
| sw2 | Sonic Wave 2 | 30 | 28,543 | 38,612 | 81 |
| josh | josh layout | 24 | 29,696 | 37,520 | 48 |
| t1113 / t1113d | snap test levels | 3 / 7 | 5,096 / 6,198 | 5,579 / 6,205 | 0 / 0 |
| ship1 / ship2 / ship3 | ship test levels | 11 / 12 / 25 | 22,195 / 13,957 / 16,095 | 22,652 / 15,037 / 18,571 | 0 / 0 / 1 |
| slope1 | ship slope test | 8 | 19,233 | 20,154 | 10 |
| slope2 / slope3 | mini slope test | 6 / 1 | 16,108 / 5,231 | 17,918 / 5,537 | 21 / 5 |

The closest real levels to 1:1 after Every End 2 are Tartarus (79.6 %, 96 differences, no
unsupported stops) and Sailent Clubstar (97 differences).

### 1.4 Gains, in the order they were made (matched steps over the whole set)

| Change | Gain |
|---|---|
| Rotation of the player and turned-box collisions (Tartarus pass) | +47,574 |
| Negative-scale fixes, upside-down spike inset, no snap at 0.5x/3x/4x (Sailent pass) | +30,071 |
| AKIRA pass (UFO rotation, turned dashes, one-touch gravity portals...) | ~+27,000 |
| The Hallucination pass | +25,300 |
| Follow Player Y portals | +23,555 |
| Rotate trigger (with reconverted levels and the respawn catch-up estimate) | +17,525 |
| Ball and UFO on slopes | +12,195 |
| H letter object | +5,027 |
| Options trigger + toggles switching triggers | +4,319 |
| S letter object | +4,203 |
| Cube jump on a rising slope | +3,916 |
| J letter object | +1,149 |
| Robot on slopes | +1,094 |
| Force blocks | +989 |
| UFO press on a slope + slope time on resync | +904 |
| Snap only after a jump | +879 |
| Gravity trigger | +728 |

---

## 2. DynamicButter (the mod)

### 2.1 Built and working

| Feature | State | Notes |
|---|---|---|
| Tick counter and input log (M1) | done | GD counts ticks (`m_currentProgress`), +2 per physics step, 240 steps/s. Click-between-steps is forced off every frame. |
| Recording (M2) | done | Inputs stamped by tick, with a "Phys" snapshot (x, y, yVel, rotation) per input. Practice-mode cut-back on respawn. |
| Playback with physics correction (M3) | done | Stereo Madness replayed to 100 % with 0 drift. Correction applies the stored state at each input; a NaN rotation means "leave the rotation alone". |
| Precise checkpoints (M4) | done | GD's own checkpoints turned out to be exact (31/31 and 33/33 tests). |
| Practice-mode recording (M5) | done | Holds active at a checkpoint get a release at T+2 on respawn. |
| GDR2 files and the pause popup (M6) | done | Own reader/writer, byte-identical to the reference library. Frame = tick / 2. DynamicButter's own extension: end tick, x path (v3), seek points (v2), rotation track. Load / Auto / Folder / Seek / Settings buttons. |
| Safe mode (M7) | done | Playback or speedhack ≠ 1x makes the attempt unsafe: GD's test mode is held on, nothing is saved. |
| Speedhack | done | **0.01x to 4x** (raised from 0.1–2x on 2026-11-17), slider plus a typeable box in the pause popup, hotkey Alt+S. Scales the frame time and the music pitch. Physics is identical at any speed (M8a). |
| Seek / start positions (M8) | built, in testing | Fast-forward (virtual 240-FPS frames for up to 14 ms per rendered frame), playback from level start positions using the stored x path, macro-defined seek points. |
| Dynamic click assist (M9) | built, in testing | The player plays; each press/release is matched by time to the nearest macro press/release and moved onto its window if up to `dynamic-leniency` steps early. Window scan to find each click's window. Off at speedhack ≠ 1x. |
| 2-player mode | done | Each key is recorded and played on its own player; the P2 key drives player 1 until dual starts. |
| Rotation track | done | The player's rotation is put back at inputs, also after practice respawns. |
| Physics trace | done (v6) | See 2.2. |
| Layouts saved with traces | done (2026-11-18), not yet seen in a real recording | See 2.2. |
| Object dump | done | Writes the game's own table of all 4,093 object IDs (type, hitbox, offset, radius) to `sim/data/objects_2.2091.csv`. |

### 2.2 The physics trace (the measurement)

Setting `physics-trace` (off by default). One CSV per session in `<save dir>/traces/`, named
`<level id>_<name>_<unix time>.csv`. Off during seeks and window scans.

Header: format version (v6), level id/name/GD version, start settings (mode, speed, mini, dual,
mirror, flipped, platformer, two-player, rotated/reversed gameplay), the 13 legacy physics flags
with their level-string keys, GD's full settings string, the player's own copies of the flags, and
since 2026-11-18 **`# layout layouts/<id>_<hash>.txt`**: the level's data as it was played
(`GJGameLevel::m_levelString`, GD's compressed form), written once per level version.

Rows:
- `A` attempt start (number, tick, practice flag);
- `S` one row per physics step: tick, step-in-frame, sprite x/y, xVel, yVel, rotation, size, speed,
  on-ground, upside-down, mode bits, dashing, jump-buffered, ring-jump, on-slope, holding, dual,
  hitbox rect, hitbox centre (posX/posY, correct on every step; the sprite x/y are stale on the 2nd+
  step of a frame);
- `S2` the same for player 2 while dual is on;
- `I` every input (tick, down, button, P2 key, from macro, position right before it);
- `O` touches of orbs/pads/triggers (with the object's and the player's oriented boxes);
- `P` portals used; `U` orbs actually used; `D` deaths (object, its rect, which player); `C`
  level complete.

Stored layouts: 22 files plus 8 converted levels in `traces/layouts/`, 26 MB.

---

## 3. The simulator

### 3.1 Files

| File | What it is |
|---|---|
| `sim/physics.py` | The simulator: `Sim.step()` plays one 240/s physics step for one or two players. |
| `sim/constants.py` | Every measured constant, with where it came from. |
| `sim/objects.py` | Object model, the game's object table, hitboxes, turning (`turn_by`). |
| `sim/triggers.py` | Move, toggle, spawn, rotate, stop, gravity, options and follow-player-Y triggers. |
| `sim/grid.py` | Spatial index over x (60-unit cells). |
| `sim/level.py` | Loads a converted level, a local level, or a layout file saved with a trace (with a cache). |
| `sim/state.py` | Cheap save/restore through an undo journal (for the solver). |
| `sim/trace.py` | Trace reader (plain or `.xz`), including the `# layout` header. |
| `sim/gdsave.py` | Reads CCLocalLevels.dat / CCGameManager.dat; encodes level strings; adds a level to the save. |
| `sim/gdr2.py` | Reads and writes GDR2 macros like DynamicButter. |
| `sim/run.py` | A run from the level start as GD plays it (ticks, inputs, level end). |
| `converter/convert.py` | Full level string → JSON with only what the simulator needs. |
| `sim/data/objects_2.2091.csv` | The game's object table (dumped by the mod). |

Plain Python 3.10+, no dependencies. `run.sh` uses PyPy 8.0.1 when it's unzipped at
`%LOCALAPPDATA%/pypy-download` (same results, about 3x faster).

### 3.2 Game modes

| Mode | State |
|---|---|
| Cube | Simulated: all speeds, both sizes, both gravities, blocks, slopes (rising-slope jumps), snaps, rotation. |
| Ball | Simulated: switching, slopes (sitting, launch, switch value on slopes), pads/orbs, rotation. |
| Ship | Simulated: thrust model, caps, band, slopes (sitting, riding, launch), orbs/pads, spider throws. |
| UFO | Simulated: press, gravity, caps, band, ship slope code, press on a slope, rotation. |
| Wave | Simulated: movement, boxes, band, slope and block deaths, D blocks, orbs. |
| Robot | Simulated: jump, held boost (67 steps), gravity, head stops, cube slope code. |
| Spider | Simulated: gravity, press throw, pads/orbs; **no slopes**. |
| Swing | Not simulated (no recorded data). |
| Dual (single player) | Simulated: player 2 spawned as a mirror, independent afterwards. |
| 2-player mode | Simulated: P2 key drives player 2 only while dual is on. |
| Mirror | View only (no physics effect). |
| Platformer | Not simulated. |

---

## 4. Measured values and rules

All values are per physics step (240/s) and come from DynamicButter traces of GD 2.2091. "Exact"
means bit-exact against the trace unless a tolerance is given.

### 4.1 Time and integration

- One physics step = tick + 2. An attempt starts at tick 2 with a frozen step (the player doesn't
  move).
- **x** (float32): `x = f32(x + xVel × 0.25)`, exact on every checked step. xVel per speed:
  0.5x 4.1860013287128206, 1x 5.1930015618800667, 2x 6.457002339951754, 3x 7.8000023138976102,
  4x 9.6000033430511955.
- **y** (float32): `y = f32(y + yVel × 0.225)` in every mode, using the step's new yVel.
- yVel stays on multiples of 0.001 (`round(yVel ± g, 3)`). About 5 % of airborne steps are 1 ulp
  off that (unexplained; counted as near misses).
- Order inside a step: speed change (gravity, thrust, jump), move, triggers, landing/collisions,
  the step's input, then objects (portals first, then orbs). Orb/pad/trigger touches use the
  position after the move.
- A death keeps the tick of the step before it and repeats it; the true death step is the last row
  that moved.
- Speed value (used by rotation): 0.5x 0.7, 1x 0.9, 2x 1.1, 3x 1.3, 4x 1.6.
- The level ends about 40 units past the furthest object (Every End 2: last object 136725, last
  physics step 136766.16). The level-complete tick is 478 ticks after the last physics step.

### 4.2 Cube

- Gravity: 0.5x 0.2116, 1x 0.958199 × 0.225 (= 0.21559), 2x 0.21537, 3x and 4x 0.21625. Not
  multiples of 0.001 (fitted ranges from off-grid speeds).
- Jump: 0.5x 10.62, 1x 11.18, 2x 11.42, 3x 11.23, 4x 11.23. Mini × 0.8.
- Fall cap −15 (the ball too).
- A press on the ground sets yVel on the press step; y moves from the next step. A held button
  jumps again on the step after landing, already moving with the jump. A press up to 1 step before
  a landing still jumps on it.
- Floor top y = 90; normal player centre on the floor 105.
- Hitboxes: outer 30×30 (mini 18×18), used for landing, hazards, orbs and portals; **inner box
  9 × 7.848** (mini × 0.6), square corners, kills when it touches a block.
- Landing: caught by any block the outer box overlaps whose top is below the centre, if the centre
  is **more than 3 above** the top after the move (caught at 3.12 in 1,394 landings, not at 2.748).
  An exact touch in x counts (front or back edge exactly at a block's edge).
- Walking off a block: drops on the first step the back edge has passed the block's end (exactly
  at the end still stands), moving with gravity that step.
- Hazards: the full 30×30 box, touching edges count, square corners. **Upside-down spike (ID 8)**:
  its flat side is inset by 0.2; the tip isn't.
- A block moving into the cube from above pushes it, yVel kept; a still block's underside doesn't.
- Blocks typed solid with a perspective-outline sprite (507, 509, 515, 516, 624, 626, 628...) have
  no collision.
- Breakable blocks (143) can be landed on and break instead of killing (provisional).
- Rotation in the air ±1.7307692 per step (mini 2.25); on the ground the angle to the nearest 90
  shrinks by 1 − 0.13125 × speed value per step. Direction follows gravity on the ground and the
  sign of yVel at orb/pad/jump kicks.
- **Jump on a slope carrying it up**: `round(jump + L[k] × xVel × clamp(n/24, 0.4, 1) / 3, 3)` (n =
  steps on the slope), ~100 jumps fit.

### 4.3 Ball

- Gravity 0.958199 × 0.225 × 0.6 = 0.12936 (rounded to 0.001 per step: 0.129 or 0.130). Fall cap 15.
- A press on a surface switches gravity with yVel = 0.3 × the cube jump toward the new gravity
  (1x 3.354, mini 2.6832); a press in the air switches on the step after landing. On a slope
  carrying it up: `round(jump + 0.25 × L[k] × xVel, 3) × 0.3`.
- Rotation: 0.48143 × xVel per step (×1.25 mini) in the gravity direction; after a switch in the
  air −0.7084 × that.
- Slopes: sits where the cube does; carried off a top it takes the ship's launch; pushed by a slope
  on the side away from gravity it rides the line.
- Cube ↔ ball portal in the air keeps yVel.

### 4.4 Ship

- yVel += 0.958199 × 0.225 × k per step, rounded to 0.001: holding k = +0.5 while "falling", +0.4
  otherwise; released −0.32 / −0.48. Mini ÷ 0.85.
- "Falling" = raw yVel < 2 × gravity at the speed (0.5x 1.8822, 1x 1.9164, 2x 1.9133, 3x/4x
  1.9222). Upside down not mirrored (the gravity bug), mirrored with fixGravityBug on.
- Caps +8 / −6.4 (mini 9.412 / 7.529). Faster than a cap it slows back by fixed steps; the step
  after a yellow orb or pad it's put at the cap.
- Band 300 high from the ship portal (floor = portal y − 150 rounded down to 30, at least 90). Free
  Mode portals: no band.
- Orbs: yellow = cube value, red the same (mini 12.578), green 0.7 × yellow, pink 4.137, blue
  4.472 at 1x, black −14. A press works only on its own step.
- Pads: yellow 16, red 10.08, pink 5.6 (mini pink 4.48, red 12.16).
- Spider throws stop at hazards: put at the hazard's centre, dies the next step; a hazard counts
  within 4 of the player's x. Nothing above: thrown to y 3180.
- Slopes: sits half its size from the line on either side; catch rule; thrust into the slope gives
  yVel 0; riding; launch `L[k] × xVel × clamp(steps/24, 0.4, 1)`, L = 0.5776 (1:2), 1.06952 (45°),
  1.51739 (2:1); edge snapping on slopes falling away.
- Rotation: 0.0375 of the way to the travel angle per step.

### 4.5 UFO

- A press sets yVel 7.0 (mini 6.8) on the next step, then that step's gravity (shows 6.871).
- Gravity = ship base × 0.6 while not falling, × 0.4 while falling; mini ÷ 0.85. Fall cap −6.4
  (mini −7.529) only when reached.
- Clip to 8 the step after a yellow orb/pad. Ship band, stops under blocks, no snap.
- Slopes: the ship's slope code (held = thrust). **A press while riding a slope carrying it up =
  the slope launch** (`L[k] × xVel × ramp`), ~420 presses.
- Rotation: 0.0175 of the way to 0.4 × the travel angle, capped at 5.7296° on the gravity side.

### 4.6 Wave

- No gravity; y moves ±xVel × 0.25 (mini × 0.5): exactly 45° (mini 63.43°). An input turns it from
  the next step.
- Boxes: hazards and portals 10×10 (mini 6×6), touching counts; blocks 4×4 (mini 2.4); slopes 7.4
  (mini 4.44) against the slope triangle; floor/ceiling slide with 20×20 (mini 12×12).
- Dies on any solid it touches, slopes included, **unless it touches a D block (1755)**; inside D
  blocks it slides on block faces with its 10×10 box.
- Orbs: only gravity orbs act (blue, green), with the cube's orb value.
- Band 300 high from the wave portal. Into or out of the wave yVel is halved; wave ↔ ship × 0.25.
- Rotation: 1/16 of the way to the travel angle per step (mini 0.1).

### 4.7 Robot

- Jump = cube jump × 0.5 (5.59 at 1x, mini 4.472); held, yVel stays flat for at most 67 steps.
- Gravity 0.19 (0.5x), 0.194 (1x, 2x), 0.195 (3x, 4x). Fall cap 15. Stops under blocks.
- Slopes: the cube's slope code.

### 4.8 Spider

- Gravity 0.129 at every speed and size, also while standing. Fall cap 15. Box 0.9 × the cube's
  (27, mini 16.2).
- A press on the ground throws it on the press step to the nearest surface the other way,
  arriving with yVel 1.

### 4.9 Mode, size, gravity, speed, teleport portals

- Mode portals: the step moves with the old mode; flying ↔ flying × 0.25, flying ↔ falling × 0.5,
  falling ↔ falling kept. Standing switches stay on the ground.
- Gravity portals: the step moves with the old gravity, then flip and yVel × 0.5. They act on the
  first touch only. Flip + normal at one x: both fire, flip first, ends normal with yVel × 0.25.
- Speed portals: plain overlap of the 30×30 box; the touching step moves at the old speed.
  Hitboxes 0.5x 35×44, 1x 33×56, 2x 51×56, 3x 65×56, 4x 69×56.
- Size portals: change on the touching step, y kept; growing on a block puts the player on it at
  once.
- Teleport portals: put at the exit's height (portal y + key 54), speed kept; from the ground it
  leaves at once with one step of gravity on yVel.
- Turned portals, orbs and pads: the player's box turned by its rotation against the object's
  turned box (separating axes), all 424 turned-hazard deaths and every turned-portal touch in
  Tartarus fit. Hitbox offsets turn with the object.

### 4.10 Orbs and pads

yVel = round(cube jump at the speed × factor × 0.8 if mini, 3), then × float32 0.7 for the ball and
the spider. Factors:

| Mode | Yellow | Green | Pink | Red | Blue | Black |
|---|---|---|---|---|---|---|
| Cube | 1 | 1 | 0.72 | 1.38 | 0.4 (fall) | −15 |
| Robot | 0.9 | 1 | – | 1.28 | 0.4 | −15 |
| UFO | 1 | 1 | 0.42 | 1.02 | 0.4 | −11.2 |
| Ship | 1 | 0.7 | 0.37 | 1.0 (mini 1.4) | 0.4 | −14 |
| Ball | 1 | 1 | 0.77 | 1.34 | 0.4 | −15 |
| Spider | 1 | 1 | 0.72 | 1.34 | 0.4 | −16.5 |

Pads (any speed): cube/robot/UFO yellow 16, pink 10.4 (UFO 6.4), red 20, blue 6.4; ball and spider
0.6 × that; ship 16 / 5.6 / 10.08. Mini × 0.8.

- An orb needs a press not yet used; a press is used by a jump or an orb and dropped on release.
  On the ground touching an orb, the orb wins. Orbs act after the step's portals.
- Blue pads set gravity the way they point; one pointing the way gravity already goes does
  nothing. A blue pad turned 90° does nothing to an upside-down cube.
- Every pad keeps the one step of gravity GD applies to a player standing on a block.
- Dash orbs: from the next step yVel 0, y constant while held (turned dashes fly along the orb's
  angle: y += xVel × 0.25 × tan(−angle)); gravity returns the step after release; pink also flips.
  The dash uses the press; a pad ends a dash; other orbs aren't used during a dash.
- Spider orb/pad: thrown to the nearest surface on the other side; the held button doesn't jump
  until released.
- Toggle orbs toggle their group like a toggle trigger; with no target they only use the press.

### 4.11 Landing snap

- Only after a jump (0 of 613 landings after falls, orbs or pads snapped at 1x).
- Only between certain block layouts (x distance, y distance up): 0.5x (60, 60), (90, 30),
  (120, −30); 1x (90, 60), (120, 30), (150, −30); 2x (150, 30). Never at 3x or 4x in the
  recordings.
- x moves toward (reference offset + new block x) by at most 1 (0.5x, 1x, 4x) or 2 (2x, 3x).
- Reference: the block stood on and the offset on it, refreshed every standing step. GD checks
  blocks per 100-unit section in level order: standing on several takes the first, landing on
  several the last. No snap from a breakable reference or when the reference block has moved; no
  snap on a step that also touches a pad.

### 4.12 Slopes (shared rules)

- Surface from the unrotated shape (rising right, solid below), flipped, then rotated clockwise.
- The player's centre sits half its size from the line at right angles: y = line(x) + half ×
  sqrt(1 + k²) (45°: +21.213, 2:1: +33.541), capped half its size past the top.
- A slope falling away ahead doesn't hold the player until its centre passes the falling slope's
  top end.
- Hanging slopes' flat tops hold the cube like a block top (step-up onto one on the first
  overlapping step).
- Launch constant L[k] (per unit of xVel): 1:2 0.5776, 45° 1.06952, 2:1 1.51739.

### 4.13 Negative scale (fixNegativeScale off)

- An object's hitbox is a 0×0 point at (x − w·sx/2, y − h·sy/2) with the signed scales;
  quarter-turned objects use the turned size, offset not turned.
- Saws with a negative radius never kill.
- Turned 30/45/60°: the normal turned hitbox.

### 4.14 Saws

- Circle (radius = table radius × scale) against the player's unturned box; death on the first step
  the circle reaches the box. Best fit over 177,856 steps near saws.

### 4.15 Letter objects and special blocks

- **D (1755)**: the wave may touch blocks (see 4.6).
- **H (1859)**: a rising cube touching one stops under a block's underside with yVel 0 instead of
  dying; a block moving into its head still carries it with yVel kept.
- **J (1813)**: no re-jump from a held click while touching it; a fresh press still jumps.
- **S (1829)**: a dash ends on the step the box touches it.
- **Force blocks (2069 square, 3645 circle)**: while overlapping after a move, the next step's yVel
  gets force (key 149) × 0.225 along the arrow, before that step's move; one per block. Measured
  for the cube (Flamewall 0.544 → 0.122 per block, Aeternus 0.75 → 0.169, 0.2 → 0.045). The ship
  got 0.59 of it in one case.
- Collision blocks and GD's type-40 special objects: no player collision.
- **No Touch** (key 121): dropped by the converter (no collision). **Passable** (key 134, assumed):
  only lands a player coming down onto its top; not validated (every passable object in the
  traced levels is also No Touch).

### 4.16 Triggers

- A trigger fires on the step the player's x reaches it, after the move; touch-activated ones on
  overlap with their scaled 30×30 box; spawn-activated ones from a spawn trigger after its delay.
- **Move**: offsets in game units (keys 28/29) over the duration (key 10 × 240 steps), cocos2d
  easing curves (key 30, rate 85). A timed move starts the step after it fires; eased moves 2 steps
  later. Move to target (player or group 71's anchor, from group 395's anchor; a group's anchor is
  its first object in level order). Lock to player x/y × keys 143/144. Triggers in a moved group
  move too.
- **Toggle**: removes or restores collision, and switches triggers in the group (a toggled-off
  trigger doesn't fire).
- **Spawn**: fires the group's spawn-activated triggers after its delay.
- **Rotate**: degrees = key 68 + 360 × key 69, clockwise, about the centre group's object (key 71);
  centre 0 or the target group itself = each object turns in place; key 70 locks object rotation;
  duration and easing like moves. Hitboxes turn (quarter turns swap w/h, half turns flip, other
  angles become turned boxes). Nested rotations carry triggers and anchors.
- **Stop**: ends the moves, rotations, locks and spawn delays started by the triggers in its target
  group.
- **Gravity**: key 148 multiplies cube/ball/robot/spider gravity before rounding (Flamewall ×1.03 at
  3x: 0.21625 → 0.223); key 138 = player 1 only.
- **Options**: keys 165 / 199 disable P1 / P2 controls (1 disable, −1 enable); the input is frozen
  as it was.
- **Follow Player Y**: portals in the group are kept at the player's y (the lag isn't modelled).
- Respawning at a checkpoint: moves and rotations fired before it are brought to where they are,
  timed from the recording that passed them, else estimated from the distance at the current speed.

### 4.17 Dual and 2-player

- Player 2 appears on the step player 1 touches the dual portal, as its mirror (same x, mode, size;
  opposite gravity and yVel), then plays independently; speed is shared; it starts with the button
  up. Its death ends the run. The dual portal sets the band.
- 2-player levels: the P2 key drives player 2 only while dual is on. Gravity portals in 2-player
  mode flip only the toucher.

### 4.18 Practice mode and start positions

- A checkpoint restores the snap reference it was saved with.
- The state stored with a macro input at tick T is the state after the step at T played with the
  button as it was before (reproduces all 1,224 states of the recorded Every End 2 macro).

### 4.19 Things measured to be impossible or unusual

- Sailent Clubstar's jump at 47 % (x 25641) can't be made at 240 steps/s: the working window is
  ~0.6 units wide and falls between two steps (all ~150 attempts reproduce the same deaths).

---

## 5. Tools for each testing task

| Task | Tool | How |
|---|---|---|
| Record the ground truth | DynamicButter `physics-trace` setting | Play (or bot) a level in GD; the trace and the level's layout land in `<save dir>/traces/`. |
| Record slowly / precisely | DynamicButter speedhack | 0.01x–4x; physics is identical at any speed. |
| Get the game's object table | DynamicButter object dump | Writes `objects_2.2091.csv` (re-dump after a game update). |
| Check GD's checkpoints | DynamicButter `checkpoint-test` | Automatic respawn-vs-original comparison during practice playback. |
| Convert a level | `converter/convert.py` | `./run.sh converter.convert --local <name>` / `--saved <id>` / `--string <file>`. Keeps gameplay objects, hitboxes, anchors and gameplay triggers; prunes triggers that never reach gameplay. |
| Compare one trace with the simulator | `tools/tracediff.py` | `PRACTICE=1 ./run.sh tools.tracediff <trace>` (uses the saved layout) or `--level <json or local name>`; `--attempt N`. Prints every stretch, why it ended, and both states around each difference. |
| Check everything at once | `tools/regress.py` | `./run.sh tools.regress [names] [--save]`: all traces in `tools/regress_set.txt`, half the cores, low priority, against `tools/regress_baseline.txt`; full output in `.regress/<name>.txt`. |
| Try a rule on and off | environment switches | e.g. `ROTATE_OFF=1 ./run.sh tools.regress` (list below). |
| Study landing snaps | `SNAP_LOG=1`, `SNAP_ORACLE=1`, `DEBUG_SNAP=1` with tracediff | One `SNAPLOG` line per candidate landing (speed, layout, distance, launch kind, fresh/air/ld/lb/nb/x0); the oracle follows the game's choice. |
| See what traces cover | `tools/coverage.py` | `./run.sh tools.coverage <trace>...`: steps per mode/speed/size, yVel changes, pad/orb values, object hitboxes. |
| Build a test level | `tools/testlevel.py` | `./run.sh tools.testlevel [--write]`: builds "DB test 1", checks it in the simulator, adds it to the save (GD closed; a backup is made). |
| Store a level for an older trace | `tools/store_layouts.py` | Stores the save's version only when it converts to exactly the level in use. |
| Find a macro for a level | `tools/solve.py` | `./run.sh tools.solve --local/--saved/--json ... [--prefer early|middle|late] [--min-gap 12] [--margin] [--time-limit]`; saves a `.gdr2` with each click's window. |
| Read/write macros | `sim/gdr2.py` | Same format as DynamicButter. |
| Bisect a regression | `git bisect run` with tracediff | Used for the Every End 2 start (found the H rule). |

### 5.1 Environment switches

Rules that can be turned off (or experimental ones turned on) for comparisons:

| Switch | Effect |
|---|---|
| `PRACTICE=1` | compare practice attempts too (the regression sets it) |
| `ROTATE_OFF`, `STOP_OFF`, `GRAVITY_TRIG_OFF`, `OPTIONS_OFF`, `TRIGGER_TOGGLE_OFF`, `FOLLOW_Y_OFF` | trigger features off |
| `FORCE_OFF`, `PASSABLE_OFF`, `H_BLOCK_OFF`, `J_BLOCK_OFF`, `S_BLOCK_OFF` | object features off |
| `ROBOT_SLOPES_OFF`, `UFO_SLOPE_JUMP_OFF`, `NO_SLOPE_AHEAD`, `NO_FLAT_TOPS`, `NO_BALL_PUSH`, `NO_SLOPE_RESYNC` | slope rules off |
| `EDGE_TOUCH_OFF`, `NO_PAD_UNSNAP` | landing details off |
| `SNAP_ANY_LAUNCH` | old snap rule (any launch) |
| `NEG_SCALE_ON` | ignore the legacy negative-scale behaviour |
| `H_KEEP_YVEL`, `OPTIONS_INVERT`, `SLOPE_UNDERSIDE`, `F32_MOVES`, `SINCE_OLD`, `SINCE_PRIOR` | rejected or unvalidated alternatives, kept for re-testing |
| `MOVE_WAIT` | start delay of eased moves (default 2) |
| `PY=python` | run under CPython instead of PyPy |

### 5.2 The solver

- Searches click windows, not single steps: the run continues without input until it dies; only
  steps where a press can matter are tried (on the ground, an orb in reach, the last 3 steps before
  a landing); clicks giving the same state are one window; the largest window is tried first;
  hopeless states are remembered. Holding is tried when single clicks can't make it.
- `--margin` makes every killing box larger, so a route never relies on the game's exact edges.
- **Every End 2 solved**: 826 clicks at least 13 steps apart, windows 1–92 steps (median 8), 495 s,
  4.9 M steps simulated. The "middle" macro beats the level in the game from the start. From start
  positions the first solver macros died (the stored player states were a step early); they were
  rewritten with the corrected states, which reproduce all 1,224 states of the recorded macro.
- Click model made for the cube; cube, ball and wave levels.

---

## 6. What is left (unresolved as of now)

### 6.1 Where the simulator still stops

Differences (5,910), by the fields that differed:

| Fields | Count | Typical cause |
|---|---|---|
| y | 1,451 | landing heights, slope positions, moving platforms' rounding |
| y, yVel | 1,100 | a jump/pad/orb value, a missed or extra landing or head hit |
| death | 633 | hazard boxes against moving or turned objects, saws |
| yVel | 471 | a speed set differently |
| upsideDown, yVel | 407 | gravity changes (turned pads/portals against a turned player) |
| onGround, y, yVel | 369 | landed in one and not the other |
| player 2 (p2.y, p2.yVel, p2.y, player2) | 530 | dual player 2 |
| size | 156 | size portals (turned ones) |
| mode / mode, yVel | 138 | mode portals (turned ones) |
| xVel | 65 | speed portals |
| x | 44 | snaps |

Unsupported stops (610):

| Reason | Count |
|---|---|
| Slopes in modes without slope code (spider; wave in D blocks) | 112 |
| Leaving the top of a slope: launch speed not measured (ball/UFO cases) | 89 |
| Solids, hazards and slopes moved or toggled by triggers that something not simulated starts (collision, on-death, count...) | 151 |
| Hitting a slope's open side while rising | 68 |
| Turned dash orbs upside down | 61 |
| Jump on a falling slope | 34 |
| Force blocks in ship/UFO/spider/wave | 38 |
| Blue pad in wave mode | 24 |
| Pink orb in robot mode | 18 |
| Slope jump growing with time on the slope | 8 |
| Others (sideways blue pads 3, gravity toggle portal 2, ball portal at the fall cap 2) | 7 |

### 6.2 Open physics questions

- **Snap**: at 1x after a jump, (90, 30) snapped 14 times and stayed 16; (120, 30) 20 / 9. Ruled
  out: fresh vs held press, time in the air, takeoff offset, the reference-block choice. 2x
  (150, 30) never snapped in 9 jump landings. 4x snaps seen after pads (12) and falls (2).
- **1-ulp noise** in yVel and y on ~5 % of airborne steps.
- **Turned player box**: Aeternus (mini UFO +8.7°) fits the current turn direction, DB test 1
  (−3.2°) the opposite.
- **Cube into a hanging slope's underside**: dies at more than 7.47 past the line in DB test 1, but
  Artifice's upside-down 2x cube lived at 8.34 (not wired in).
- **UFO**: 1x press after 1–4 steps on a slope gives 8.0 (mini 6.648); an 8.5-unit catch onto a
  slope; leaving-slope yVel.
- **Ball**: 3.84 switches in Orochi where the rule gives 3.707; the ball's own band outside dual.
- **Turned portals in Cosmic Salad**: a 53° pair used by the game but not the sim, a 315° one the
  other way; a group-1 ball portal that fired 834 units away.
- **Move-trigger rounding**: platforms moved by eased moves drift ~0.0004 per step against the game
  (float32 per-step accumulation ruled out).
- **Respawn catch-up**: what a practice checkpoint keeps of a move under way (NR2b −134 right after
  moves fired at x 29847–30117; the earlier attempt's own timing was worse).
- **Follow Player Y lag**: not modelled (portals sit exactly at the player's y; the guide says 1/6
  of the gap per step).
- **Saw outliers** in Cosmic Salad (likely moved saws), a rotated ship dying one step later than
  the sim at saws 1705/1734.
- **Dual**: legacy-dual gravity portals (sometimes both players flip); a player-2 UFO's falling
  rule after an upside-down ship; ~530 player-2 differences.
- **Robot**: rising into a block's underside sometimes passes into it (Duelo Maestro).
- **Flamewall**: the ball's yVel rising +0.083 a step right after wave → ball → blue portals.
- **Touch toggle order**: the sim fires a touch-enabled Options trigger one step after the game.
- **Blue pads turned 90/270** in normal gravity; teleport portals turned 45/90; wave into each mode
  portal.

### 6.3 Not implemented

- Swing mode, platformer, mirror physics (view only).
- Spider on slopes; wave on slopes inside D blocks.
- Turned solids (angles other than multiples of 90°) have no collision.
- Force blocks outside cube/ball, and sideways force arrows.
- Gravity trigger for ship/UFO/wave; Stop trigger pause/resume options.
- Follow, advanced follow, keyframe, area, collision, count, item, time, random, sequence,
  on-death, teleport, reverse, rotate-gameplay, time-warp, player-control and end triggers (their
  objects are marked uncertain and the simulator stops when the player reaches one).
- The F block (2866), ExtraSticky, Dont Boost, GripSlope, Extended Collision (not present on
  gameplay objects in the traced levels).
- Rotation of the cube after a turned dash hides it (the sim keeps spinning underneath).

### 6.4 Not yet verified

- DynamicButter's layout saving: built and installed, no real recording made with it yet.
- Passable objects: implemented, no traced level has one that isn't also No Touch.
- The solver's macros on levels other than Every End 2.
- DynamicButter's Dynamic click assist (M9) and seek (M8): built, still in testing.

### 6.5 Data notes

- DB test 1 in the save was edited after its trace; its stored layout is rebuilt from
  `tools/testlevel.py`.
- The old test levels, Sonic Wave 2 and josh layout: their save versions differ from what was
  played, so their converted files (copied to `traces/layouts/converted_*.json`) are the only copy.
- VOLTSTORM's layout isn't in the save, so its recordings only give free-flight values.
- The trace once showed the holding flag drop in mid-air with no release row (Every End 2
  start-position attempt, tick 45378).
