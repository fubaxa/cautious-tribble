# Simulator calibration notes

What the simulator implements, the trace evidence for it, and what's still open. All traces are
DynamicButter physics traces (v5 unless noted) from GD 2.2091 at 240 physics steps/s.

## Status

`tools/tracediff.py` on `0_test_1794191254.csv` (level `test`, all 2.2 physics options on):
**all 7,093 steps from the start to the level end match, in one piece, with no differences and
nothing skipped.** (The run's other 241 steps are the end animation.) 158 of those steps were
near misses (open issue 1).

Covered by that run: cube and ball; floor, jumps (pressed and held), fall cap, gravity portals, all
speed portals, mini and normal size portals, ball and cube portals, red / blue / spider pads,
yellow / pink / red / green / black / blue / spider orbs, both dash orbs, landing on blocks and on
block undersides, the snap on a 2x staircase, the level end.

`Sonic Wave 2` (v1 trace, 16 attempts from start positions, physics options off): **no
differences in any attempt**. 4,701 wave steps match; every wave stretch ends at a slope (49), a
rotated cube portal (3) or a death on exactly the game's step (5). Its cube parts stop at block
undersides (34), which aren't measured.

`0_test_1794365066.csv` (level `test` rebuilt as a wave test, saved as `levels/test_wave.json`,
15 attempts): **every attempt matches** from the start to its death (12, all on the game's step) or
to the spider portal; 19,680 steps, no near misses.

This is three recorded runs. Every rule below needs more runs before it's trusted.

## Measured rules

- **Step 1 after a spawn doesn't move the player.**
- **x** (float32): `x = f32(x + xVel * 0.25)` — exact on all 15,373 checked steps.
  xVel (double) per speed: 0.5x 4.1860013287128206, 1x 5.1930015618800667,
  2x 6.457002339951754, 3x 7.8000023138976102, 4x 9.6000033430511955.
- **y** (float32): `y = f32(y + yVel * 0.225)` at every speed, using the step's new yVel.
- **Cube gravity** per step: 0.5x 0.212, 1x 0.216, 2x 0.215, 3x/4x 0.216 (normal and mini equal).
  yVel stays on multiples of 0.001: `round(yVel ± g, 3)`.
- **Cube jump** yVel: 0.5x 10.62, 1x 11.18, 2x 11.42, 3x 11.23 (4x not measured); mini = 0.8x.
- **Floor** top at y = 90 (player centre 105 at normal size).
- **Gravity portals** (2.2 options on): the step moves with the old gravity, then the portal flips
  gravity and halves yVel (10.152 -> 5.076). yVel is stored with its real-world sign.
- **Speed portals**: plain axis-aligned overlap of the player's 30x30 hitbox with the portal's;
  the step that touches still moves at the old speed, xVel changes for the next step.
  Hitboxes (w x h, centred): 0.5x 35x44, 1x 33x56, 2x 51x56, 3x 65x56, 4x 69x56.
- **Rotated portals** (not implemented): fire on the first step where the player's oriented
  hitbox overlaps the portal's oriented hitbox (12/12 cases). Player OBB in wave: 10x10, mini 6x6.
- **Event timing**: orb/pad/trigger touches happen after the move, on the hitbox of that step.
- **Order inside a step**: move, land, then the step's input, then objects (see sim/physics.py).
  An input row carries the already-moved position.
- **Jump**: a new press on the ground sets yVel on that step and y first moves on the next one.
  A button already held when the player lands jumps on the following step, and that step already
  moves with the jump velocity.
- **Fall cap**: cube yVel stops at -15.
- **Mini portal**: size changes on the touching step, y is kept; the player then falls to the floor.
  Normal portal while standing mini: y is kept for that step, the floor lifts the player on the next.
- **Pads**: set yVel on the touching step, after the move: yellow 16, pink 10.4, red 20 (mini 16).
  Blue pad: flips gravity, yVel = 5.12 (mini) in the new falling direction.
- **Orbs** need a press that hasn't been used yet (a press is used by a jump or an orb, and dropped
  on release). With a press on the ground while touching an orb, the orb wins. Values at the
  measured speed: yellow 11.18 (1x), pink 8.05 (1x), red 15.76 (2x), green 11.42 and flip (2x),
  black -15 (2x), blue: flip and fall at 4.568 (2x).
- **Green dash orb**: from the next step yVel is 0 and y stays constant while the button is held;
  gravity returns the step after the release.
- **Blocks**: landing when the player's bottom was at or above the top on the previous step:
  y = top + half size, yVel 0. Block 467 behaves like block 1.
- **Snap, confirmed on 3 landings at 2x**: predicted x = (x - block x at the previous landing) +
  new block x; x moves toward it by at most 2. The first block after the floor doesn't snap.
- **Level end**: the sprite x stops while the hitbox keeps moving for the end animation.
- **Ball**: gravity 0.958199 x 0.225 x 0.6 = 0.12936 per step, then yVel is rounded to 3 decimals
  (so the change is usually 0.129, sometimes 0.130). A press on a surface switches gravity and
  sets yVel to 0.3 x the cube jump value toward the new gravity (1x: 3.354, mini 2.6832), with the
  same timing as the cube's jump. Holding doesn't switch again; a press made in the air switches
  on the step after landing. Checked at 1x, 1x mini and 2x.
- **Spider pad** (ball): throws the player to the nearest surface on the other side and flips
  gravity. Onto a block it stands at once (yVel 0); onto the floor it arrives with yVel -1.
- **Spider orb** (cube): the same throw, arriving with yVel 1 toward the surface. The button held
  from that press doesn't jump on landing until it is released.
- **Pink dash orb**: the green dash plus a gravity flip (yVel halved on the use step).
- **During a dash** other orbs aren't used, even while touching them.
- **Wave**: no gravity. y moves by +-xVel x 0.25 per step (mini x 0.5), using the exact xVel, so the
  slope is exactly 1 (45 deg) and mini exactly 2 (63.43 deg); bit-exact on all 17,022 moving wave
  steps in the traces. The logged yVel is xVel rounded to 3 decimals. An input changes the
  direction from the next step on (640 of 640 turns). The effective angle drifts slightly with x
  because x is float32 (44.995-45.011 deg measured).
- **Wave boxes** (all centred on the player; fitted to the TRUE death steps, see "Deaths" below;
  12 deaths in the wave test, all on the exact step):
  - Hazards: 10x10 (mini 6x6), the trace's player rect (fits 9.2-10.7 / 6.0-6.35); touching edges
    count (a mini wave died with a gap of 0.000).
  - Blocks: an inner box of about 4x4 (mini 2.4x2.4) kills on any contact (fits 3.2-4.8 /
    1.9-3.8). D blocks not tested.
  - Floor and ceiling: slides with a 20x20 box (mini 12x12): y 100 / 96 on the floor, 380 under
    the ceiling at 390 (300 above the floor; one wave portal at y 135, higher portals not tested).
    The step that reaches the floor or ceiling keeps its yVel when it lands exactly on it, and
    gets yVel 0 when the move went past it.
  - Portals, pads, orbs: 10x10 (mini 6x6), the trace's player rect.
  - The rotating box for rotated objects: not in the simulator (it stops when it can't rule
    contact out).
  - Thin outline objects 507/624 (30x2) in Sonic Wave 2 were overlapped for 9 steps without a
    death: their hitbox in our table may be wrong.
- **Wave ground flag**: GD's on-ground flag stays set in the air after the wave first touches the
  floor; it doesn't change how the wave moves. A press on the floor doesn't jump.
- **Into or out of the wave** through a mode portal, yVel is halved, in the air or not.
- **Saws** (hazards with a radius) collide by circle: death on the first step the circle reaches the
  player's box (measured once, at 0.03 units' margin).
- **Spider pads and orbs** throw the player the way they point: up unrotated, down when rotated 180
  or flipped (user's description, consistent with the 4 uses in the test run). Sideways ones stop the
  simulator until tested.
- **Start positions**: the diff starts from the game's first step when an attempt doesn't start at x=0.

- **Orbs and pads, all speeds** (7 levels, 2.2 and older ones give the same values): cube orb =
  the cube jump at that speed x 1 (yellow, green), 0.72 (pink), 1.38 (red), 0.4 as a fall (blue),
  rounded to 3 decimals, mini x 0.8; black is -15 everywhere. Pads don't depend on speed: yellow 16,
  pink 10.4, red 20, blue 6.4 (mini x 0.8). The 4x cube jump is 11.23 (from the yellow orb).
  Ball: pads 0.6 x and orbs 0.7 x the cube's value (float32 factors), measured at 2x and 4x only.
- **Blue pads** set gravity the way they point (up unless flipped); touching one that points the
  way gravity already goes does nothing (seen 2x in josh layout).
- **Cube gravity isn't a multiple of 0.001**: from off-grid speeds (a mini blue orb's 3.3985) only
  values in these ranges give GD's next yVel: 0.5x 0.2115-0.2120, 1x 0.2155-0.2160, 2x
  0.2150-0.2155, 3x 0.2155-0.2165, 4x 0.2160-0.2165. 1x and 3x use 0.958199 x 0.225.
- **Wave floor and ceiling** come from the wave portal: floor = portal y - 150 rounded down to 30,
  at least 90; ceiling 300 above. A wave start position is assumed to work like a portal there.
- **Slopes (cube, in the simulator)**: a slope's surface comes from its unrotated shape (rising to
  the right, solid below) flipped first, then rotated clockwise. On a slope the cube's centre sits
  half its size from the slope line, at right angles to it: y = line(x) + half x sqrt(1 + k^2)
  (45 deg: +21.213, 2:1: +33.541), capped at half its size past the slope's top. Exact on every
  step on 45 deg, 2:1 and 1:2 slopes, both sizes, both gravities. yVel reads 0 on a slope. The
  cube climbs as soon as that height beats the floor; it leaves on the second step at the top
  height (4 of 4). A falling cube passes through the top height while its centre is over the
  slope and lands on it past the top corner (seen once).
  Not worked out: the launch speed when leaving the top (45 deg at 1x: 2.962, 5.863 or 7.405; 2:1:
  10.069 or 10.507) and a jump on a slope (13.807 or 12.231 instead of 11.18). Both grow with the
  time on the slope (GD keeps a slope start time); the simulator stops there. Also not done:
  going down a slope from its top, slopes in other modes, rotated slopes.
- **Walking off a block**: GD checks support with this step's x already moved; the cube (and ball)
  drops on the first step its back edge has passed the block's end, moving with gravity that step.
- **Ship, older levels (fixGravityBug off)**: per step the ship's yVel changes by +0.108 (holding)
  / -0.069 (released) while its speed away from gravity is below about 1.9, and +0.086 / -0.103
  above it (normal size, all speeds). Upside down the switch is at -1.9 instead of +1.9: GD
  compares the on-screen yVel without flipping it, so the upside-down ship behaves differently
  (6,000+ steps). No ship data with the fix on yet. Ship isn't in the simulator.

## Triggers (PROVISIONAL - not fully developed, to be changed)

`sim/triggers.py` has a first version of move, toggle, spawn and touch triggers. It is checked
against one run only (a botted full run of Every End 2: 97,483 of 105,557 steps match) and will
change as more trigger levels are compared. Current rules:
- a trigger fires on the step the player's x reaches its x, after the move, before collisions
  (from the first step that moves); a timed move starts moving on the step after it fires
  (Every End 2's first slab: 19 steps of movement by tick 42);
  touch-activated ones when the player's box overlaps the trigger's 30x30 box (scaled);
  spawn-activated ones from a spawn trigger, after its delay;
- move offsets (keys 28/29) are game units, spread linearly over the duration (easing ignored);
  triggers in a moved group move too;
- move to target (key 100) goes to the player or to group 71's anchor, measured from group 395's
  anchor. **A group's anchor is its first object in level order**, decoration included (the
  converter keeps it). Checked: Every End 2's floor (group 2) is re-centred on the player every
  300 units and stays under it only with this rule; the group-parent object or the bounding-box
  centre throw it away;
- lock to player x/y (keys 58/59) moves the group by the player's own movement times keys
  143/144 (default 1) for the duration (Every End 2's floor follows the player this way);
- toggle off removes collision from the group's objects;
- collision blocks and GD's "special" objects (type 40) have no player collision.
Follow, stop and rotate triggers, and triggers only something unsimulated (collision, on-death,
count...) can start, aren't simulated: their objects are marked uncertain and the simulator stops
if the player reaches one.

Also from Every End 2:
- **Teleport portal**: the player is put at the exit portal's height (blue portal y + key 54:
  135 + 420 = 555) on the touching step, speed kept; GD reports it on the ground that step.
- **Blocks for the cube (and ball)**: a falling cube is caught by any block its outer box overlaps
  whose top is below the cube's centre (even from 7.6 below the top). Other contacts: the outer
  box may overlap a block's side or underside freely; the **inner box, 9 wide x 7.8 tall** (mini x
  0.6), touching a block kills (side deaths: half-width 4.47-5.01; half-height 3.77-3.92 from a
  death and a survival). A block moving into the cube from above pushes it down (a slab carried
  the cube at its speed); a static block's underside doesn't. **Breakable blocks** are blocks you
  can land on that break instead of killing (provisional). **A held jump** goes before the support
  check: a cube that landed with its back edge barely on a block still jumps next step.
- **Hazards for the cube**: mini cube: its full 18x18 box (9 deaths, old physics). Normal cube:
  survives overlaps up to 0.11 (Every End 2); modelled as a 0.2 tolerance, no bound from deaths.
- **Deaths**: the step that dies keeps the tick of the step before it (the progress doesn't
  advance) and is then repeated; the diff tool uses that last moving row. Before this, every death
  was compared one step early, so earlier box fits were off (now redone).
- **Perspective outlines** (IDs with a persp_outline sprite: 507, 509, 515, 516, 624, 626, 628...)
  are typed solid but have no player collision: a box down to 4x4 at the cube's centre overlapped
  them 68 times without a death (and the wave flew through them for 9 steps in Sonic Wave 2).
- **Snap** (Every End 2 ~950 landings + a snap test level, all matching except one landing):
  - reference: the block the cube stands on and where the cube is on it, refreshed every step it
    stands (so the take-off spot) - also on the landing step itself, after the snap (a cube that
    lands and jumps again at once takes off with it). Standing on several blocks: the FIRST in
    level-string order. Landing on several blocks: the block landed on is the LAST in level order.
  - on landing on another block, x moves toward (reference offset + new block x) by at most 1
    (0.5x, 1x, 4x) or 2 (2x, 3x), both directions;
  - only between certain layouts (x distance, y distance up): 1x (90, 60), (120, 30), (150, -30);
    2x (150, 30). Other layouts at 1x never snapped; other speeds snap everywhere until measured;
  - no snap from a breakable reference (onto one it does), none when the reference block has moved.
  - Open: one landing in Every End 2 (tick 38952: from a normal block onto a breakable + a normal
    block, predicted +1, the game didn't move) looks the same as two that did snap +1.
- **Every End 2 now: 105,196 of 105,557 steps (99.66%)**: one difference (the landing above); from
  tick 39188 everything matches to the level end (85,722 steps). The second recording and the
  original Every End (a short run with a death) match the same way.
- **Teleport**: a mid-air teleport stays in the air; one from the ground leaves it at once, with one
  step of gravity on yVel but none on y (breakable test level). On the run's first moving step the
  game kept it on the ground instead (Every End 2's start).
- **Level end** in the diff tool: the sprite stops for the end animation; detected against the
  previous frame's sprite x (it only changes once per drawn frame).

Sonic Wave 2's cube parts (old physics) now run further and show gravity differences: two blue
pads overlapping (one pointing up, one down) are both ignored by the game, while the simulator
applies the up one. Not worked out.

## Open issues

1. **1-ulp noise in yVel and y.** On ~5% of airborne steps GD's yVel is 1 ulp off `round(v, 3)`,
   and y is 1 float32 ulp off `f32(y + yVel*0.225)`. Tried: plain add, round/floor/trunc with
   /1000 or *0.001, fmod/remainder, float32 gravity, per-segment `start + 0.216*n`, double y
   accumulation — none above ~95.7%. Probably one upstream cause inside GD. The trace diff counts
   these as near misses and continues from the game's value.
2. **Not measured, so the simulator stops there**: pads and orbs in ball mode, gravity portals
   in ball mode, entering a mode portal in the air, the ball's fall cap, spider pad with nothing
   above.
3. **The cube's gravity is probably not a multiple of 0.001 either** (ball: 0.12936). 0.216 fits
   every cube step so far because cube velocities sit on the 0.001 grid; the real values for
   0.5x and 2x (measured 0.212 and 0.215) are unknown.
4. **Assumptions in the block code, not yet tested**: the snap applies only on a landing; the
   reference offset is taken at the landing (not while standing); landing on the floor clears it;
   contact with a block's side or underside stops the simulator instead of deciding.
5. `x`/`y` in traces are the sprite position: stale on the 2nd+ step of a multi-step frame. The
   diff uses `posX` (hitbox centre, ~1e-7 less precise) on those steps.
