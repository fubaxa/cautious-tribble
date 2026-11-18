# What the simulator still needs

## Resume here (2026-11-18)

**Latest (2026-11-18)**: Rotate trigger (+17,525, incl. reconverted levels and a respawn catch-up
estimate), force blocks (+989), Passable (in, unvalidated), Stop trigger (+0), Gravity trigger
(+728). Regression-checked, baseline saved. Uncommitted. Traces now come with their level
(traces/layouts/, `# layout` header; regress_set.txt points there; see NOTES "Layouts saved with
traces"). Open from this round:
- NR2b -134 (respawn right after moves fired at x 29847-30117: what a checkpoint keeps of a running
  move is unclear; `SINCE_PRIOR` was worse);
- force in ship/UFO/wave (ship 0.59x, one case) and sideways force arrows;
- turned solids (not multiples of 90) still have no collision;
- Gravity trigger for ship/UFO/wave; Pause/Resume options of the Stop trigger;
- DB test 1 in the save was edited after its trace (rebuilt from tools/testlevel.py).


**Latest (2026-11-17, late)**: Every End 2 re-recorded (trace 1794976406, speedhack) and in the
regression set as EveryEnd2: 105,287 steps, **0 differences** start to end. Fixes for it (all other
traces +0, baseline saved): landing on an exact x edge touch, H zeroes yVel only on head hits,
tracediff level end mid-frame. Committed and pushed (6aed4ff).

**Latest (2026-11-17 evening)**: Flamewall added (171,638 -> 194,035 matched after the fixes below).
Uncommitted, regression-checked, baseline saved after each step:
- Follow Player Y portals (`Sim.follow_y`): +20,377 Flamewall, +3,178 elsewhere;
- the robot on cube slope code: +1094;
- cube jumps on rising slopes (`Sim._slope_jump`): +3916;
- the UFO press on a slope plus slope time restored on resync: +904.
Next in Flamewall: y/yVel stops (277), deaths (223: saws 1705-1736, spikes 216/218), the spider
on slopes (27, not implemented), cube jumps on falling slopes, the Options (25) and Gravity (5)
triggers (2.2, not simulated).

**Latest (2026-11-17 night)**: everything up to d83e50e is pushed. Uncommitted, regression-checked,
baseline saved: H (+5,027), J (+1,149) and S (+4,203) letter objects; toggles switching triggers +
the Options trigger's disable-controls (+4,319). Open from this round:
- the ball band (the user: the ball doesn't die on the ceiling, like the UFO/ship);
- the Follow Player Y lag (1/6 of the gap per step, per the guide);
- the Gravity trigger (Flamewall x 37275, x1.03);
- the same-step order of a touch Toggle and the triggers it enables;
- Flamewall's ball yVel +0.083 a step after the wave -> ball portals.

**State of the code (older)**: everything up to commit bf97f6f is pushed. Uncommitted but
regression-checked: snaps only after a jump (`p.launch`, +879), the 0.5x snap layouts, SNAPLOG's
distance and launch kind, shared objects with copy-on-write (`Sim.own`), tools/regress.py
with regress_set.txt and regress_baseline.txt, and run.sh using PyPy when present.

**Regression baseline**: `tools/regress_baseline.txt` is the source of truth (the list below is
from 2026-11-17, before Cosmic Salad: CosmicA 525447, CosmicB 48014, CosmicC 25008). Cosmic Salad isn't in the set yet: 48,014 / 25,008 / 525,447 for its
three traces.
Aeternus 61658, AkiraA 31616, AkiraB 44633, Artifice 41553, Aurorae 13588, BOTS 28683,
ChopStep 34094, DBtest 24735, DoubleDash 18544, Halluc 58006, HallucRec 53908, Llorona 8079,
LostLove 16327, NR2a 10515, NR2b 33687, Orochi 84917, Sailent 85731, SubSonic 101468,
Tartarus 74699, josh 28386, part11 36338, part14 54918, ship1 22195, ship2 13957, ship3 16095,
slope1 19233, slope2 16108, slope3 5231, sw2 28543, t1113 5096, t1113d 6198.

**To do, in order** (details in NOTES.md, the sections named in brackets):
1. ~~Snap change regression~~: done, kept. ~~Cosmic Salad in the set~~: done (CosmicA/B/C).
   ~~Speed~~: `./run.sh tools.regress` takes 76 s under PyPy (run.sh picks it automatically;
   baseline in tools/regress_baseline.txt).
2. Snap, still open (2026-11-17: fresh vs held press, time in the air, takeoff offset and the
   reference-block choice are ruled out; see NOTES "Snap factor hunt"):
   - the factor that makes jump landings at 1x (90, 30) and (120, 30) snap only sometimes;
   - whether (90, 30) belongs in the 1x list;
   - 2x (150, 30) never snapped in 9 jumps (drop it from the list?);
   - the 4x snaps after pads. [Cosmic Salad]
3. Turned player box: Aeternus (mini UFO +8.7 deg) wants the current turn direction, DB test 1
   (mini UFO -3.2 deg) wants the opposite. Needs a test with bigger tilts, both directions,
   normal and mini. [Aeternus, DB test 1]
4. Cube into a hanging slope's underside: measured (7.47 past the line in DB test 1) but switched
   off (`SLOPE_UNDERSIDE=1`), because Artifice's upside-down 2x cube lived at 8.34. Try the cube's
   rotation. [DB test 1]
5. UFO on slopes:
   - ~~jumps~~: a press = the slope launch with its ramp (wired in, NOTES "UFO press on a slope").
     Open: 1x after 1-4 steps gives 8.0 (normal) / 6.648 (mini);
   - the 4x upside-down slopes in Cosmic Salad: the 0.0004 drift is the move-trigger easing's
     rounding (the slopes move), not slope physics (see item 8). The 8.5 catch onto a slope is
     still open;
   - leaving-slope yVel (41 stops).
   [Ball and UFO on slopes, DB test 1, Cosmic Salad]
6. Turned mode/size portals:
   - Cosmic Salad: 53 deg used by the game but not the sim; 315 deg used by the sim but not the
     game;
   - the group-1 ball portal that fired 834 units away.
   [Cosmic Salad]
7. Blue pad turned 90/270 in normal gravity, and turned 270 at all (only "90, upside down: no
   effect" is known). Teleport portals turned 45/90. Wave into each mode portal. [DB test 1,
   Tartarus tests]
8. Objects moved by move/rotate triggers that something not simulated starts: Cosmic Salad (130
   stops), AKIRA, Night Rider 2, Hallucination (slopes 327/1718 moved).
9. **From the GD editor guide** (docs/gd_editor_guide.md): model H (1859, no head-hit death:
   Artifice 114, part 11 61, NR2 56 ...), J (1813, no held-click jump: Aeternus 119 ...) and S
   (1829, dash ends: Double Dash 48 ...). The traces already have them. Then the ball's portal
   band, the Passable / Dont Boost flags (find their level-string keys), and the
   Gravity / TimeWarp / Teleport / Player Control triggers where levels use them.
10. Smaller: the saw outliers in Cosmic Salad; Sailent's remaining stops (see its section below);
   dual p2.x; 1339 slopes; a 0.5x pad snap case.

**Next test level (DB test 2) should cover**: snaps (1x jumps onto (90, 30) and (120, 30) from
different spots on the block, falls onto the same layouts); turned pads and orbs with the player
tilted 10-40 deg both ways (normal and mini, cube and UFO); a cube jumping into hanging slope
undersides at different rotations; a blue pad turned 270 in normal gravity.


From `tools/coverage.py` over all 11 traces (about 159,000 physics steps, GD 2.2091) and the
converter's reports on 6 levels. "Have" = measured from traces. "How" = cheapest way to get the rest:
**dump** = read it from the game with the mod, no playing; **check** = review by hand; **test** = a short recorded run;
**code** = the data exists, the simulator just doesn't use it yet.

## Objects

Done: `sim/data/objects_2.2091.csv` is the game's own table for all 4,093 object IDs (type, hitbox,
hitbox offset, radius), dumped by DynamicButter. It matches every hitbox measured from traces
(32 of 32 IDs), and converted levels match every object touched in a trace (168 of 168; the only
misses are objects a move trigger had moved). No level has unknown IDs any more.

| What | Have | Missing | How |
|---|---|---|---|
| Type + hitbox per ID | All 4,093 IDs: 336 solids, 99 hazards, 74 slopes, all portals, pads and orbs | - | - |
| Saws and other round hazards | Radius for 41 IDs | Whether GD tests the circle, the box, or both | test |
| Slopes | Box size for 74 IDs | Which way each one faces (from flips and rotation) and the slope physics | test |
| Hitbox offsets | 13 IDs have an off-centre box | How the offset turns with rotation and flips | test |
| Special blocks (D, J, S, H, F blocks, force blocks, collision blocks) | IDs and boxes (8 IDs) | Their effects | test |
| Triggers | 55 gameplay trigger types named from the game; visual ones dropped by icon name | Confirm none of the dropped ones matter | check |
| Player hitboxes | Main box 30 (mini 18); rotated box 10 (mini 6) in wave | Inner "solid" box (death against blocks), rotated box in other modes | dump |

## Movement per game mode (yVel per step unless noted)

| Mode | Have | Missing | How |
|---|---|---|---|
| All | x per step at all 5 speeds; y += yVel x 0.225 | Exact rounding: about 5% of steps are 1 ulp off (NOTES.md) | open |
| Cube | Gravity 0.212 / 0.216 / 0.215 / 0.216 / 0.216 (0.5x..4x); jump 10.62 / 11.18 / 11.42 / 11.23 (0.5x..3x); mini jump 8.496 / 8.944 (0.5x, 1x) | Jump at 4x; mini jump at 2x, 3x, 4x; fall cap (-20 seen, mini -15 seen, not confirmed); rotation per step (needed for rotated portals) | test |
| Ship | Fall -0.069 or -0.103, rise +0.086 or +0.108; mini -0.081 / -0.122, +0.101 / +0.127; same at 0.5x, 1x, 3x, 4x | Rule choosing between the two values; top speed up and down; 2x | test |
| Ball | Gravity 0.129 at 1x, 2x, 4x, both sizes | yVel right after a click; 0.5x, 3x | test |
| UFO | Fall 0.086 or 0.129 (1x, 4x) | Rule between the two; jump value; mini; 0.5x, 2x, 3x | test |
| Robot | Gravity 0.194; held jump keeps yVel 5.59 (mini 4.472), 1x only | How long the hold lasts; other speeds | test |
| Spider | Gravity 0.129 (1x, 3x) | The teleport on click; mini; other speeds | test |
| Wave | yVel = +/- xVel; y += yVel x 0.25 (mini x 0.5); all speeds | Nothing for free flight | - |
| Swing | Nothing | Everything | test |

## Collisions

| What | Have | Missing | How |
|---|---|---|---|
| Floor | Top at y = 90 | Ceiling / floor band in ship, ball, UFO, wave, spider, swing | test |
| Blocks | Landing height (centre = top + half size); side hit kills (object 0) | Exact landing and ceiling rule, how far a corner can clip, head hits | test |
| Snap | +1 at 1x, -2 at 2x on a staircase | Block distance that triggers it, 0.5x / 3x / 4x, mini | test |
| Slopes | Nothing | Everything | test |
| Plain portals, pads, orbs | Fire on main-hitbox overlap, on the step's own position | Spider pad 3005 fires without overlap | test |
| Rotated portals | Fire on first rotated-box overlap (12 of 12) | Same check for other rotated objects (hazards) | code + test |
| Level end | Completion tick for 2 levels | Rule for where the level ends | test |

## Pads, orbs, portals (yVel set on use, normal gravity)

| What | Have | Missing | How |
|---|---|---|---|
| Yellow pad | Cube 16 (1x..4x); spider 9.6 | Other modes, mini | test |
| Pink pad | Cube 10.4; ball and spider 6.72 | Other modes, mini | test |
| Red pad | Cube 20, mini 16 | Other modes | test |
| Blue pad, spider pad | Hitboxes | Their effect | code + test |
| Yellow orb | Cube 11.18 at 1x | Other speeds (probably the jump value), mini, other modes | test |
| Pink orb | Cube 8.05 at 1x | Same | test |
| Red orb | Cube 15.76 at 2x | Same | test |
| Green orb | Cube 11.42 at 2x, flips gravity | Same | test |
| Blue orb | Flips gravity, yVel -4.568 at 2x in one case | The rule for the new yVel | test |
| Black orb | Cube -15 | Other modes | test |
| Dash orbs | Used 3 times | Speed, direction, how the hold ends | test |
| Spider orb, toggle orb | Used / touched | Their effect | test |
| Orb rules | Held click activates an orb | Buffer length, multi-activate, one use per click | test |
| Gravity portal | Flips and halves yVel (physics options on) | With options off; in other modes | test |
| Mode and size portals | Hitboxes | What happens to yVel and y on entry | code + test |
| Dual, mirror, teleport | IDs | Everything | test |

## Level features

| What | Have | Missing | How |
|---|---|---|---|
| 13 physics options | Read from each level; own levels have them off unless switched on | What each one changes | test (same run with a flag on and off) |
| Move / toggle / rotate / spawn triggers | Kept by the converter with their raw keys | Timing and easing rules. AKIRA: 476 triggers acting on 2,165 gameplay objects | test |
| Dual mode, two-player | Start flag | Player 2 | later |
| Platformer mode | Start flag | Out of scope for now | - |

## Tartarus tests (2026-11-15)

What Tartarus still stops on that only a recorded run can settle (the rest is fixed or in NOTES.md):

| Test | Stops in Tartarus |
|---|---|
| ~~Wave on slopes~~: done (it dies, 7.4 box; 2026-11-16). Still wanted: the wave on slopes and blocks inside D blocks, and mini wave deaths at slopes to settle the 4.44 box | 0 |
| Ball and UFO on slopes: see "Ball and UFO slope tests" below | 12 (265 over all traces) |
| Wave into each mode portal, going up and down, normal and mini | 2 |
| Two gravity portals (flip + normal) touched on one step, cube and ship | 2 |
| Blue pad turned 90 deg, cube, both gravities | 3 |
| Cube jumping up into a slope's open side | 2 |
| Teleport portal turned ~45 deg and 90 deg, cube and ball | 7 |

## Ball and UFO slope tests (2026-11-16)

265 distinct ball/UFO slope stops over the regression traces (DoubleDash 78, Orochi 29, Artifice 20,
part 14 20, SubSonic 17, Aurorae 17, ...; ball 120, UFO 145). The traces already settle most of it:

- **Where they sit on a slope**: exactly where the cube does (half the size from the line at right
  angles), both modes, both sizes, both gravities, 45 deg, 2:1 and 1:2: ~4,600 on-slope steps fit to
  0.01. The rest are at slope ends (the cube's cap past the corner).
- **Leaving with no input**: the ship's launch (L[k] x xVel x steps/24 in [0.4, 1], not the cube's
  x 4/3) fits 70 of ~100 cases exactly; the other 30 are short or chained stays, the UFO's 6.4 cap,
  or drop-offs (to sort out when wiring it in).
- **Landing onto a slope**: ~170 cases in the traces.

What a test level still has to show (thin or missing in the traces):

| Test | Seen so far |
|---|---|
| ~~Ball switch on a slope~~: settled from ~70 switches already in the traces (2026-11-16); still useful: a press on the slope's last step, and 4x | ~70 |
| UFO jump on a slope (the UFO now uses the ship's slope code): taps going up and down 45 deg and 2:1 floor slopes, upside down on ceiling slopes; normal and mini; 1x and 3x | 4 |
| Holding through the slope's end: UFO held (no new press) and ball with a press buffered in the air before landing on the slope | 10 + 12, mixed |
| Short stays: touch a rising slope for 1, 3, 6, 12, 20 steps and leave (landing near its top at different heights), ball and UFO, to pin the launch ramp | few clean ones |
| Down a slope from its top and off its bottom (a falling floor, a rising ceiling upside down), ball and UFO: does it stick, drop or launch | a handful |
| Slope to slope and slope to block: two slopes of different steepness in a row, slope into a flat block and back | mixed in, not separable |

One level with both modes, each row at 1x and 3x, normal and mini, both gravities, covers it; play
each part a few times with the inputs varied.

## Sailent Clubstar (2026-11-16)

- Flat top of a hanging slope: a standing cube is lifted onto it (x 25650, +0.5). A general
  "land on the flat side" rule breaks the slope test levels. Needs a test: a cube walking and
  falling onto the flat top of a hanging slope (45 degrees and 2:1), alone and paired into a square.
- Remaining Sailent stops (by trace tick):
  - ticks 18114-20558: y off by 0.27 with yVel 3.2 vs 3.81;
  - ticks 23938-24370: gravity flips with y 0.03 off;
  - ticks 37034-37834: y off by 0.5 at y 1119.5 and 1161;
  - dual p2.x (23 cases).

## Aeternus (2026-11-16)

- Turned pads and orbs against a mini player: the box GD turns for the mini UFO seems bigger than
  18x18 (Aeternus x 14066: a blue pad at 334 deg). Needs a test: a mini cube and a mini UFO
  touching pads and orbs turned 30-60 deg from each side, plus the same at normal size.
- Negative scale: the point hitbox of objects turned by angles other than 90 deg isn't measured.
