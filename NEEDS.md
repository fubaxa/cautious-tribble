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
