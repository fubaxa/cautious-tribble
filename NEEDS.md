# What the simulator still needs

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
