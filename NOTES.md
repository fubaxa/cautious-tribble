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
  going down a slope from its top, slopes in modes other than the ship, rotated slopes. The
  cube's launch values fit the ship's slope launch (below) x 4/3 exactly: 45 deg at 1x full =
  7.405 (4/3 x 5.554), 2.962 = 0.4 of it, 5.863 = 19/24; 2:1 full 10.507 (4/3 x 7.880), 10.069 =
  23/24. Not wired into the cube yet.
- **Walking off a block**: GD checks support with this step's x already moved; the cube (and ball)
  drops on the first step its back edge has passed the block's end, moving with gravity that step.
  Exactly at the end still stands (back edge 40200.0 on a block ending at 40200.0, a solver macro).
- **Ship (simulated, 2026-11-14)**, from 23,000 free-flight steps (ship test level, BOTS phase 4,
  VOLTSTORM, josh layout, saddsa, Unnamed 0, something 2):
  - per step yVel += 0.958199 x 0.225 x k (gravity-relative), rounded to 3 decimals; holding: k =
    +0.5 while "falling", +0.4 otherwise; released: -0.32 / -0.48. Mini: / 0.85. The step uses
    the button as it was before this step's input (like the cube; the other way was off by one
    thrust step at every change).
  - "falling" = raw yVel < 2 x gravity at the speed (0.5x 1.8822, 1x 1.9164, 2x 1.9133, 3x and 4x
    1.9222; normal and mini). Upside down: raw yVel > that (not mirrored: the gravity bug). With
    fixGravityBug on it's mirrored (VOLTSTORM's mini ship; its settings aren't readable).
  - caps +8 / -6.4 (mini / 0.85, on the 0.001 grid: 9.412 / 7.529), gravity-relative: within them
    holding can't push past +8 and releasing can't push past -6.4. Faster than a cap (after an orb
    or pad) the ship slows back with no thrust: above +8 by 0.32 (holding) / 0.48 (released),
    below -6.4 by 0.5 / 0.4 (x gravity x 0.225; hundreds of steps, both orientations). On the step
    after a yellow orb or pad it's put at the cap instead (16 -> 8); a red orb's 12.578 isn't.
  - band 300 high from the ship portal, the wave's rule (josh layout: floor 150, ceiling 450; ship
    level 630). Standing on the floor (or the ceiling upside down) and on block tops; a block's
    underside stops it. No landing snap.
  - on-ground is sticky (like the wave): set by a touch on the gravity side, kept in the air. On
    the other side GD sets it inconsistently (normal size upside down at the floor: set on the 2nd
    step; mini upside down: 255 steps not; ship level ceiling: 76 steps not). It doesn't change the
    ship's motion, so the diff tool doesn't compare it in ship mode.
  - portals: yVel halved after the step's move with the old mode (cube, ball <-> ship); wave <->
    ship a quarter, not rounded (-7.15 -> -1.7875).
  - orbs in ship (ship test level 2026-11-14, 1x, enableImpulseFix on, plus BOTS): yellow = the
    cube's value (11.18 at 1x), red the same at normal size (13 uses; mini 12.578), green 0.7 x
    yellow (flips), pink 4.137, blue flips and sets the cube's fall (4.472 at 1x), black -14,
    spider: the spider throw, with the ship's band edges as surfaces. A press only works on its
    own step (held into an orb later, nothing happens). After a spider orb the held button is
    ignored until released (like the cube).
  - pads in ship: yellow 16 (the cube's), red 10.08 (0.5x and 1x), pink 5.6 (1x, 12 uses); a blue
    pad flipping a standing ship keeps that step's small sink (it isn't put back on the block). A
    teleport keeps the ship's yVel and on-ground flag.
  - spider throws stop at hazards (ship tests 13:47, 15:00, 15:32: 39 throws, 33 into spikes,
    the last session two diagonal spike columns 0.5 apart in x): the player is put at the
    hazard's CENTRE (y = its y, yVel 1 toward the new gravity) and dies on the next step (the
    throw step itself doesn't kill, even inside the spike; the logged killer can be a spike it
    overlaps there). A hazard counts when its (unrotated) box comes within 4 of the player's x
    after the step's move: 3.998 stopped it, 4.036 passed, on both sides. The ship's own box
    overlapping a spike isn't enough. The nearest hazard in reach wins. Measured in ship mode,
    upward throws from a spider orb; blocks in the throw's column still use the whole box.
    Nothing above at all (the user forgot the blocks behind the spikes): thrown to y 3180, the
    level's top, and killed two steps later by the out-of-bounds area (no object).
  - Free Mode ship/wave portal (key 111 = 1; the converter keeps it as "free"): no band - the
    ground is the floor and there's no ceiling (the ship flew to y 721 past a portal at y 285).
  - slopes (ship slope test 2026-11-14 16:30, 8 attempts, 45 deg / 2:1 / 1:2, floor and ceiling
    slopes, quarter-turned too, 3x and 1x, both gravities; 94% of 20,154 steps match):
    - on a slope the ship sits where the cube does (half its size from the line at right angles),
      on either side: above a slope with solid below, under one with solid above. Capped at half
      its size past the far corner only where the slope carries it off (a rising floor's top, a
      falling ceiling's bottom); over a falling floor's top or a rising ceiling's bottom it just
      drops off. Past such a corner, and from a flat leg's side, the slope acts as a block (its
      box): stands under its flat bottom, dies at its side.
    - a new contact catches the ship once inside the surface, however deep, or up to 1 unit
      outside if the ship closes in faster than the surface moves away (0.98 caught, 1.13 not; a
      floor rising under a falling ship doesn't catch it from outside).
    - thrust into the slope (released over a floor, held under a ceiling; upside down the other
      way): yVel 0 - unless it's moving away already: on the far side from gravity it keeps that
      speed, on the gravity side only when it outpaces the slope. Thrust away while the slope
      pushes: yVel at least 2.0 away. Then yVel keeps its normal ship acceleration.
    - riding: with the thrust into it the ship sticks (also to a slope moving away faster than it
      would follow) unless it moves away itself; otherwise it leaves once outside. On the step its
      x speed changes (speed portal) a ship riding its gravity-side slope comes off (5 of 5).
    - leaving where the slope carries it off (past that corner, or outrunning it mid-slope)
      launches it: yVel = L x xVel x f away from the slope, L per xVel 0.5776 (1:2), 1.06952
      (45 deg), 1.51739 (2:1), f = steps on the slope / 24 held in [0.4, 1] (0.1 s to full). The
      launch is worked out on the last step on the slope (a speed portal touched then doesn't
      change it). Leaving elsewhere: no launch.
    - on a slope falling away from the ship (a falling floor, a rising ceiling), the step the
      support crosses the slope box's top or bottom edge puts the ship exactly on that edge, then
      it goes on (15 cases, both sizes, 0.03-1.1 off; never on rising floors or falling ceilings;
      once not, at a crossing of 0.002).
    - mini ship (test 20:47-20:48, 7 attempts): the same rules with its own size; the launch is
      the same per xVel (0.5x: 4.477 / 6.352 / 2.417, 1x: 5.554 / 7.880 / 2.999). A slope's side
      kills it with the normal-size inner box (2 deaths: 4.0-4.6 into the side). A slope pressing
      it down into the ground: the floor zeroes yVel first (it kept exactly -2.0), and once the
      slope lets go with the centre under the ground line it dies (no object named).
    - open: a rising ceiling's bottom corner stops a rising ship one step late; landing on a corner
      a step late (seen once, also in the cube notes); a mini ship falling onto the flat top of a
      ground-pointing slope 1.5 above it was caught (the block rule wants 3).
  - dash orbs work in ship mode exactly as in the cube (the user: the same in every mode; both
    orbs matched in the mini test).
  - Open: dual (two portals set the band). The 13:43 ship-test session was
    recorded on an earlier layout; the 15:00 one is checked against levels/1114b_shiptest.json, 15:32 against 1114c, 16:30
    (slopes) against 1114d_shipslope.

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
  box may overlap a block's side or underside freely; the **inner box, 9 wide x 7.848 tall**
  (mini x 0.6), square corners, touching a block kills (side deaths: half-width 4.47-5.01;
  half-height 3.924: a cube rising with its centre 3.923981 below a block died twice, at
  3.924011 it survived - the same jump, only float32 rounding at different heights differs). A block moving into the cube from above pushes it down (a slab carried
  the cube at its speed); a static block's underside doesn't. **Breakable blocks** are blocks you
  can land on that break instead of killing (provisional). **A held jump** goes before the support
  check: a cube that landed with its back edge barely on a block still jumps next step.
- **Hazards for the cube**: mini cube: its full 18x18 box (9 deaths, old physics). Normal cube:
  full 30x30, touching counts, plain corners (corner deaths at overlaps 0.023 x 0.484,
  0.523 x 0.034, 0.176 x 0.298, 0.516 x 0.110). **An upside-down spike (ID 8) has its box ~0.2
  lower**: all 12 corner survivals (overlap up to 0.445 x 0.110) were the flat side of flipped
  spikes, while a normal spike killed at 0.516 x 0.110; 0.12-0.25 fit every run. (This replaces an
  earlier rounded-corner model, which missed 3 deaths.) **No hitbox has rounded corners** (GD's
  hitbox viewer draws them square); two earlier rounded-corner fits were artefacts.
- **Landing needs the centre more than 3 above the block's top** after the step's move (caught at
  3.12 above in 1,394 landings; not caught at 2.748: Every End 2 x 23355, where the same x
  landed from 3.97 above 6 times).
- **Invisible bricks**: Every End 2's 64 breakable bricks (ID 143) are all in group 1, which an
  alpha trigger at x -29 fades to 0 at the start: invisible but solid.
- **Practice mode** (Every End 2): a checkpoint restores the snap reference it was saved with; the
  diff tool restores it from the LATEST pass through that tick with the same x and y (an earlier
  pass on another path gave the wrong one), and a cube respawning on the ground takes the block
  under it. Newest practice run (183 attempts): no differences, 164 deaths on the exact step.
- **Every End 2 status: every recording matches with no differences** (bot run, 4 practice runs,
  494 attempts). The tick-38952 landing was the section order below (12 of 12 landings there).
- **Trace gap**: in a botted run the game's holding flag once dropped in mid-air with no release
  row logged (Every End 2 start-position attempt 3, tick 45378): an input DynamicButter doesn't log.
- **Deaths**: the step that dies keeps the tick of the step before it (the progress doesn't
  advance) and is then repeated; the diff tool uses that last moving row. Before this, every death
  was compared one step early, so earlier box fits were off (now redone).
- **Perspective outlines** (IDs with a persp_outline sprite: 507, 509, 515, 516, 624, 626, 628...)
  are typed solid but have no player collision: a box down to 4x4 at the cube's centre overlapped
  them 68 times without a death (and the wave flew through them for 9 steps in Sonic Wave 2).
- **Snap** (Every End 2 ~950 landings + a snap test level, all matching except one landing):
  - reference: the block the cube stands on and where the cube is on it, refreshed every step it
    stands (so the take-off spot) - also on the landing step itself, after the snap (a cube that
    lands and jumps again at once takes off with it). GD checks blocks section by section (100
    units along x), in level-string order within a section. Standing on several blocks: the
    FIRST checked. Landing on several: the block landed on is the LAST checked. Shown by a brick
    + block pair split across two sections (Every End 2 x 25275/25305, brick test x 885/915):
    the game took the block in the later section; pairs inside one section take the newer one.
  - on landing on another block, x moves toward (reference offset + new block x) by at most 1
    (0.5x, 1x, 4x) or 2 (2x, 3x), both directions;
  - only between certain layouts (x distance, y distance up): 1x (90, 60), (120, 30), (150, -30);
    2x (150, 30). Other layouts at 1x never snapped; other speeds snap everywhere until measured;
  - no snap from a breakable reference (onto one it does), none when the reference block has moved.
- **Every End 2 now: the bot run has no differences from start to the level end** (105,315 steps
  compared, the rest skipped by the tool); the practice runs match too.
- **Teleport**: a mid-air teleport stays in the air; one from the ground leaves it at once, with one
  step of gravity on yVel but none on y (breakable test level). On the run's first moving step the
  game kept it on the ground instead (Every End 2's start).
- **Level end** in the diff tool: the sprite stops for the end animation; detected against the
  previous frame's sprite x (it only changes once per drawn frame).

Sonic Wave 2's cube parts (old physics) now run further and show gravity differences: two blue
pads overlapping (one pointing up, one down) are both ignored by the game, while the simulator
applies the up one. Not worked out.

## Solver (tools/solve.py)

- **Level end**: GD's physics stops about 40 past the level's furthest object of any kind (Every
  End 2: last object 136725, last physics step at 136766.16, the one before at 136764.86). The
  converter writes `last_x`; one level measured.
- **A press up to 1 step before a landing jumps on it** (Every End 2 x 12465: 1 step before works, 2
  don't). The solver tries the last 3 airborne steps before each landing.
- **Every End 2 solved**: 826 clicks, at least 13 steps apart, windows 1-92 steps (median 8); 495 s,
  4.9 M steps simulated. Its replay ends 31 steps earlier than the human macro (different snaps).
  The first two macros died in the game: they went through two edge cases no human run had
  touched (a back edge exactly at a block's end; the inner box touching a block's side exactly),
  both fixed. Solver routes go through more such edge cases than human play: any rule that's
  slightly off is where a solver macro will desync first.
- **A macro's end tick** is the level-complete tick, 478 ticks after the last physics step.
- **Start positions** need each input's stored player state to be the run's real state:
  DynamicButter's start-position correction moves the player to it at every input of such an
  attempt. The first solver macros stored the press's state on its release too (up to 239 units
  off) and died right after the spawn. The solver now replays the macro and stores the real state
  (rotation as NaN = unknown: DynamicButter then leaves the player's rotation alone) and the exact
  x path. **The state stored with an input at tick T** is the state after the step at T played with
  the button as it was before (the input's own effect not in it yet): this reproduces all 1,224
  states of the recorded Every End 2 macro exactly (x, y, yVel). One step earlier was 1.298 off
  in x at every input, and correcting to it put a start-position attempt a step out of time (a path the game learns samples the sprite, which only moves once
  per rendered frame, so it lags up to a step).

## Other game modes: measured, not simulated yet (2026-11-14)

From recordings of BOTS phase 4 startpo, Lost Love startpos 2 and VOLTSTORM (traces dated
1794637649-1794638339) plus the two ship recordings. Per step; y += yVel x 0.225 in every mode.
Values are gravity-relative (upside down mirrored). Mini = x 1.175 in every mode below.

- **Ship**: now simulated, see "Ship (simulated)" above.
- **UFO**: speed-independent gravity, two regimes like the ship: -0.086 / -0.129 (mini -0.101 /
  -0.152). A press's boost shows a step after the press (not fitted yet). yVel seen -11.46..11.23.
  11,000 steps.
- **Robot**: gravity per speed like the cube but ~0.9x: -0.190 (0.5x), -0.194 (1x), -0.195 (4x).
  A press from the ground sets yVel 5.31 (0.5x), 5.59 (1x), 5.615 (4x); holding keeps it constant
  for a limited time (seen up to 63 steps at 0.5x, ~9-13 at 1x before release; maximum not
  fitted). 8,000 steps.
- **Spider**: gravity -0.129 (as the ball). A press teleports to the surface on the other side:
  yVel becomes -1.0 (gravity-relative) after it. The landing spot needs the layout. 10,500 steps
  (mostly 4x, in VOLTSTORM).
- **Not covered**: swing, dual (only player 1 is recorded), mirror, platformer.
- **Layouts**: BOTS phase 4 startpo and Lost Love startpos 2 are local levels (convertible).
  VOLTSTORM's level data isn't in the save (GD only keeps it for a few downloaded levels), so its
  recordings can only give free-flight physics until the layout is dumped.
- **Lost Love startpos 2, cube part** (start position x 21938, 69,000 cube steps, 0.5x-3x, often
  upside down): only 40% matches. The causes are triggers, not cube physics: orbs in groups
  112/119/121/486 are shuffled by spawn-started move triggers (the simulator put a green orb on
  top of the yellow one the game used), and speed portals are moved by a follow-player trigger.

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

## Orbs and pads in every mode (Shitty mix part 14, practice, 23 attempts, 2026-11-14)

Over 1,000 orb and pad uses across cube, ship, ball, UFO, robot and spider at every speed and
both sizes. Pads don't depend on speed. Orbs follow one formula (sim/constants.py orb_yvel):
yVel = round(cube jump at that speed x factor(mode, orb) x 0.8 if mini, 3), then x float32 0.7
for the ball and the spider (that reproduces GD's trailing digits). Blue: round(jump x size x 0.8)
halved by the flip (mini 3.3985 = 6.797 / 2). The factors are per mode, not the gravity ratio:
- cube: yellow 1, green 1, pink 0.72, red 1.38, blue 0.4
- robot: yellow 0.9, green 1, red 1.28, blue 0.4
- UFO: yellow 1, green 1, pink 0.42, red 1.02, blue 0.4
- ship: yellow 1, green 0.7, pink 0.37, red 1.0 (mini red 1.4), blue 0.4
- ball: yellow 1, green 1, pink 0.77, red 1.34, blue 0.4 (then x 0.7)
- spider: yellow 1, green 1, pink 0.72, red 1.34, blue 0.4 (then x 0.7)
- black: -15 cube/robot/ball, -16.5 spider, -11.2 UFO, -14 ship
- pads: cube, robot and UFO yellow 16 / pink 10.4 (UFO 6.4) / red 20 / blue 6.4; ball and spider
  0.6 of that (9.6 / 6.72 / 12 / 3.84); ship 16 / 5.6 / 10.08. Mini x 0.8.
The measured tables stay as overrides (a few mini values round in the other order).

Also from part 14:
- the ball at a gravity portal: like the cube, the step moves with the old gravity, then yVel is
  halved (30 uses).
- rotated portals, orbs and pads use their box turned with them (an oriented-box test). The
  unrotated box was worse in Sonic Wave 2 (85 gravity mismatches against 70).
- cube jump while on a 1:2 slope (held): one gravity step under the normal jump (10.408 at 0.5x,
  10.964 at 1x, 11.014 at 3x); not wired in (too few cases, the slope direction not separated).
- landing snaps at speeds other than 1x and 2x: "always snap" is wrong at least for the layouts
  (90, -90) and (90, -30); 14 x differences of 1 or 2 units. Not worked out.
- still stopping the simulator: UFO, robot, spider and swing modes (28 stretches), cube slope
  launches and jumps, dual mode, rotated hazards.

Shitty Artifice (21 attempts) and Shitty mix part 11 (20 attempts), practice, 2026-11-14:
- ship pads, mini: pink 4.48 (0.8 x 5.6), red 12.16 (not 0.8 x 10.08, like the mini ship's red
  orb). Ball and spider minis: 0.8 x (pink 5.376, blue 3.072, red 9.6).
- a cube <-> ball portal in the air keeps yVel (66 switches in the three levels); the step moves
  with the old mode's gravity. Once, at the cube's fall cap (15), yVel was halved: not allowed.
- the wave and the ball near slopes: most stops (64 wave, 14 ball) were the player's box only
  overlapping a slope's box. The simulator now stops only when the mode's box (the wave's 10x10
  hazard box) reaches the slope's triangle (a wave died 5.7 above a 45 deg line, which its 4-unit
  block box doesn't reach). Old level files with quarter-turned slopes but no recorded turn keep
  the whole-box stop. What the wave and the ball do on slopes isn't measured.
- speed portals: a rotated one (316 deg) took effect one step later than its turned box gives;
  with two speed portals touched at once the game took the one earlier in the level order (2x
  over 3x, both in trigger groups). Not changed yet.
- the three levels: Artifice 25,985 / 46,383 steps, part 11 20,042 / 35,174, part 14 26,260 /
  47,642 (from 24,238, 18,058 and 22,328).

## UFO, robot and spider (2026-11-14; Shitty mix 11 / 14, Artifice, BOTS, VOLTSTORM, josh, cool
## challenge, the old test levels: about 60,000 UFO, 40,000 robot and 30,000 spider steps)

- UFO: a press sets yVel on the next step to 7.0 (mini 6.8), then that step's gravity (the trace
  shows 6.871), whatever yVel was, in the air or standing; holding does nothing more. Gravity is
  the ship's base (0.958199 x 0.225) x 0.6 while not falling, x 0.4 while falling (the ship's
  per-speed falling threshold), mini / 0.85; nothing else depends on speed. Fall cap -6.4 (mini
  -7.529), but only when reached: past it (a black orb's -11.2) it keeps falling. The step after
  a yellow orb or pad clips yVel to 8 (mini 9.412), as the ship. It has the ship's band, stops
  under blocks like the ship, doesn't snap. Its on-ground flag is sticky like the ship's (set for a
  step after leaving a ledge, kept through a portal): not compared. A UFO press acts on its own
  step only (resync clears GD's buffered flag, which stays set while held).
- Robot: the cube's jump x 0.5 (mini x 0.8: 5.59 at 1x, 4.472 mini), then yVel stays flat while
  held, for at most 67 steps after the jump step (0.5x, 1x, 3x, 4x alike), then gravity: 0.19
  (0.5x), 0.194 (1x, 2x), 0.195 (3x, 4x) - 0.9 x the cube's, rounded half up (0.6805 - 0.194 ->
  0.487, -3.4225 -> -3.422). Fall cap 15. Jumps like the cube (on the press step, and again on
  landing while held). Rising into a block's underside it stops there (yVel 0).
- Spider: gravity 0.129 (the ball's) at every speed and size, also while standing (the floor or
  block puts it back), fall cap 15. Box 0.9 x the cube's (27, mini 16.2: standing at 103.5). A
  press on the ground throws it on the press step itself (79 of 79) to the nearest surface the
  other way - the spider orb's throw: arriving with yVel 1, standing on the next step. A press in
  the air waits for the landing. Spider pads throw it the same way (arriving with yVel 1). It
  doesn't snap on landing. A pad on a standing spider keeps that step's move, except on the floor
  line itself (block: 1306.5 -> 1306.529; just thrown: 1606.5 -> 1606.725; floor: 103.5 stays).
  Rising into a block's underside it stops there.
- Mode portals: the step moves with the old mode, then between two flying modes (ship, UFO, wave)
  yVel x 0.25, between a flying and a falling mode (cube, ball, robot, spider) x 0.5, between two
  falling modes kept. Standing, the box changes size about its bottom (spider -> UFO 433.5 ->
  435). The UFO and spider get the band from their portal, like the ship and the wave.
- pads per mode: cube, robot and UFO the cube's values (UFO pink 6.4, mini 5.12), ball and spider
  the ball's, the ship its own; mini x 0.8 where not measured. Black orb per mode (see the orbs).
- open: a mini spider stopped at 360 under a band that would end at 390 (mini band 270 high?);
  UFO, robot and spider on slopes; resyncs that start mid-press; the robot stopping under blocks
  helped part 14 and cost part 11 a little (there may be a case where it passes or dies).
- the three practice levels now: Artifice 33,613 / 58,363 matched steps, part 11 29,471 / 46,639,
  part 14 47,188 / 79,046 (the totals grew as these modes' steps now count).

Shitty Orochi buff 3, Marathon 2, Night Rider 2 (2026-11-14 evening, 177 attempts, 215,964 steps):
- a standing switch from a flying mode into a falling one (ship -> cube on a block) stays on the
  ground (48 cases), like the UFO entry.
- resync: a ship/UFO/wave/spider can be somewhere no logged portal explains (teleported straight
  into a portal); the band then comes from the last portal of that mode whose band holds it.
- matched: Orochi buff 3 65,887 / 106,606, Marathon 2 59,444 / 86,478, Night Rider 2 6,747 / 22,880
  (its 671 move triggers keep blocks moving: landings 0.4 off where the simulator's block hasn't
  moved the same way).
- open: the cube's on-ground flag stays set over several falling steps in about 130 cases
  (looks like standing on something moving or sloping down, not a ledge); landing snaps at 3x/4x
  (74 x differences); mini ship / UFO / wave differences after resyncs; mirror portals; dual.
- ZIG (79601086, 76,789 wave steps) isn't in the save yet: kept until GD writes it.

## Move triggers and dual (2026-11-15)

- move easing (key 30, rate key 85): the cocos2d curves (ease in/out, elastic, bounce, exponential,
  sine, back; sim/triggers.py ease()). Checked on a blue orb moved by an exponential-out move in
  Night Rider 2, whose position GD logs every step: progress follows the curve exactly, 2 steps
  behind the linear rule's timing; so an eased move starts 2 steps later (linear moves keep Every
  End 2's timing, which a 2-step delay breaks).
- resync now brings timed moves to where they are at that moment (from when the recording's
  player passed each trigger) instead of finishing them at once (Night Rider 2 resyncs a lot).
- dual portals: the first player moves on unchanged (yVel kept on entry); the second player isn't
  simulated (the trace doesn't log it). In dual GD keeps the first player's on-ground flag set while
  it falls off a ledge (45 of 45): not compared. Mirror portals: view only. Of 25 deaths during
  dual in five levels, the simulator misses 4 - likely the second player's; simulating it needs
  the trace to log player 2 (DynamicButter).
- matched now: Orochi buff 3 67,126, Marathon 2 61,828, Night Rider 2 7,361, Shitty mix 11 30,653,
  BOTS 24,540, mix 14 47,619, Artifice 33,854.

## Player 2 in dual (v6 traces: Night Rider 2, ChopStep 2, Aurorae 2; 32,554 player-2 steps)

- spawn: on the step player 1 touches the dual portal, player 2 appears as its mirror - same x,
  mode, size, opposite gravity and yVel, at player 1's height after the move but before landing
  (standing: 0.0486 lower with yVel +0.216). Portals touched later in that step (a cube portal at
  the same x) aren't passed on: player 2 takes them itself on the next step.
- then it's an independent player: its own portals, orbs, pads and gravity; its death ends the run.
- speed is shared: a speed portal changes both players (player 2 carried player 1's new 0.5x while
  keeping its old mode).
- input: the same button, but player 2 appears with it up - a hold from before the portal doesn't
  reach it until a new press (889 steps with player 1 holding and player 2 not).
- the diff tool compares player 2's rows too (differences prefixed p2.), resyncs it from its row.
- open: a player-2 UFO that came from an upside-down ship used the upside-down "falling" rule with
  normal gravity (switched at -1.92); inverting the rule for every player-2 UFO made other cases
  worse - probably a state kept from earlier. About 90 player-2 differences remain in the three
  levels.
- ZIG (wave, 76,792 steps) is in the save now: 59,159 matched.
- dual vs 2-player mode (the level setting kA10): in dual the one input drives both players; in a
  2-player level the P1 key drives player 1 and the P2 key player 2 (tools/tracediff.py reads the
  keys apart, Sim.step(holding, holding2)). No 2-player recording yet: untested.
- gravity portals in dual (Night Rider 2, ChopStep 2, Aurorae 2: 2.2 physics, single-player): they
  flip the player that touches them; the cases where both flipped had both players touching one on
  the same step. The user's note: in single-player dual with legacy physics a gravity portal flips
  both players, and in 2-player mode only one - not seen in a recording yet, not simulated.

## 2-player mode and legacy dual (Duelo Maestro 2P, Double Dash, SubSonic, Tartarus; 2026-11-15)

- 2-player levels: the P2 key drives player 2 only while dual mode is on; before that both keys
  drive player 1 (a P2-key press made player 1 jump). Duelo Maestro went from 50,172 to 99,209
  matched steps with that. DynamicButter's recorder and playback now pick the player the same way
  (outside dual the P2 key's saved state is player 1's - before, it took the hidden player 2's,
  which showed as a drift of 62,529 in the bot run).
- gravity portals in 2-player mode flip only the player that touches them (Duelo Maestro: never
  both). In single-player legacy dual (Double Dash, SubSonic) sometimes both flip and sometimes only
  the toucher, and the result isn't always mirrored; the trace only logs a portal when a player's
  last activated portal changes, so a second touch is hidden - not worked out, not simulated.
- the on-ground flag: an upside-down cube walking off a ledge keeps it set (142 of 144; with normal
  gravity never, 644 of 644) - flag only, not compared then.
- matched: Duelo Maestro 99,209 / 218,161, SubSonic 70,132 / 198,251, Tartarus 62,217 / 93,790,
  Double Dash 14,033 / 52,220 (108 slope stops). Sonic Wave 2 116 differences (from 150).
- open: a robot rising into a block's underside sometimes passes into it (Duelo Maestro) where the
  simulator stops it; same physics settings as the levels where it stops.


## Rotation, turned objects and the Tartarus pass (2026-11-15)

Worked through every stop in Tartarus (93,790 steps, cube / ship / UFO / ball / wave at all
speeds, two dual parts). Matched steps there 62,217 -> 70,877; over all 30 regression traces +47,574 (none lower).

- **Turned objects** (any angle but a multiple of 90): GD turns the player's box by the player's
  own rotation and tests it against the object's turned box (separating axes). Tartarus: all 424
  deaths at turned hazards and every turned-portal touch (gravity, mode, size, dual) fit, with no
  false touches; the player's box left unturned, or the object turned the other way, don't fit.
  Hazards use the hazard box (the wave's small one), the rest the full box; size and mode portals
  the box from before the change. The game's death boxes (D rows) are the turned boxes' bounds,
  matching our sizes. Saws stay circles against the unturned box: neither version fits their
  deaths cleanly (a rotated ship dies 1 step later than the sim at saws 1734 / 1705: open).
- **Player rotation** (`_update_rotation`, from the S rows of every trace):
  cube in the air +-1.7307692 per step (mini 2.25), on the ground (also the landing step) the angle
  to the nearest 90 shrinks by 1 - 0.13125 x speed (0.5x .9081 ... 4x .79); the spin direction
  follows gravity on the ground and takes the sign of yVel when an orb, pad or jump kicks it, not
  at a gravity portal (98.9 % of airborne steps; the rest look tied to blue orbs / mirror, open).
  Ball: 0.48143 x xVel per step (x1.25 mini) in the gravity direction, kept when rolling off an
  edge; after a switch in the air -0.7084 x that. Ship and wave: each step the angle moves 0.0375
  (wave 1/16, mini wave 0.1) of the way to -atan2(dy, dx) of the step's move, at every speed.
  UFO tilts a few degrees on a lagging curve (kept from the resync); robot and spider don't turn.
- **Ball fall cap** 15, like the cube (-14.923 -> -15.0; 15.129 seen only after kicks).
- **Orbs act after the step's portals**: a blue orb inside a gravity portal flips the player and
  the portal, already matching, doesn't flip it back.
- **Blue pad from standing on a block**: GD pulls the player down one step of gravity first and
  the flip keeps it (405 -> 404.9514); not on the floor line.
- **Cube gravity per speed refitted** on all traces: 3x and 4x 0.21601-0.21649 (3x was 0.215595:
  wrong after off-grid yVels, -0.6865 -> -0.470), 2x 0.21526-0.21549, 0.5x 0.21151-0.21174.
- **Landing snap and a pad on the same step**: no snap (x kept).
- **A cube under a slope's line but not touching the slope** isn't inside it (it was lifted 57
  units onto a slope above it).
- **Dual portal sets the band** like a ship or wave portal (SubSonic +8,400). Holding the cube and
  ball in that band too lost 5,000 steps elsewhere, though a dual ball in Tartarus stands right
  under the band's ceiling: open. The diff tool's resync now picks, in dual, the band of the last
  band-setting portal that holds the player.
- The diff tool's resync ignores GD's on-slope flag in the air (it stays set).

Still open in Tartarus, each needing a recorded test (NEEDS.md, "Tartarus tests"): wave, ball and UFO
on slopes; wave into mode portals (wave -> UFO gave yVel 0, wave -> cube -2.0); two gravity
portals on one step (no change at all, the sim halves twice); a blue pad turned sideways; a cube
rising into a slope's open side; a turned teleport portal. Also open: mini ship deaths on slope
sides at 3x (no object in the D row), a mini UFO dying on a block corner, player 2 at the dual
band's ceiling.

## The Hallucination (81139702, 2026-11-15)

19,237 gameplay objects (9,939 slopes), 554 move / toggle triggers, every mode but the spider at
all speeds; three traces (recording with practice, a full playback, a short run). The playback trace
went from 48,477 to 56,620 matched steps; the same fixes gave +25,300 over the older traces (none lower).

- **Hitbox offsets turn with the object** (centre = position + the offset turned by the object's
  rotation): a teleport portal turned 305 deg, offset 10.8, was touched a step early without it.
- **Orbs in wave mode**: only the gravity orbs act (blue 27 uses, green 5; yellow touched 40 times,
  never used). Gravity flips and yVel is the cube's orb value (blue 4.492 at 4x, 4.568 at 2x, mini
  3.5935; green -11.23); the step's move keeps the old direction. Yellow, pink, red, black: nothing.
  Toggle orbs still stop the simulator (their group toggling isn't simulated).
- **Every pad**, not just the blue one, keeps the one step of gravity GD applies to a player
  standing on a block (yellow pad at 0.5x: 255 -> 254.9523).
- **Catch-up of moves under way** (tracediff resyncs): it used what was left of the 2-step start
  wait (0 once a move had started), putting every running move 2 steps ahead; it now uses the
  original wait less the fire step (eased: 1), which puts a moving platform exactly on GD's.
- tracediff, attempts that start at a checkpoint: moves the player passed before the attempt are
  timed from the furthest attempt from the start (it used to restart them at the checkpoint), and the
  band comes from the band portals any attempt touched by that tick (a trigger moves the right one).

Open: wave deaths at blocks and slopes (D rows without an object, 7), the ball, UFO and wave on
slopes (NEEDS.md, Tartarus tests), a rotated gravity portal touched 3 steps later than the sim right
after a UFO -> wave switch (the UFO's angle at the switch), toggle orbs.

## AKIRA pass (2026-11-16)

Two AKIRA traces (88421468: a 137-attempt practice session, and the recording plus two full
playbacks made with the rotation track; options off, cube / ship / UFO / ball / wave / robot at 0.5x
to 4x). AKIRA 27,120 -> 31,306 and 40,708 -> 44,084 matched steps; over all 34 regression traces
about +27,000, none lower except Duelo (-4).

- **UFO rotation**: each step the angle moves 0.0175 of the way to 0.4 x +atan2(dy, dx) of the
  step's move (the other way from the ship), with that target capped at 0.1 rad (5.7296 deg) on the
  gravity side; rising it isn't capped (up to 18 deg seen). Normal and mini, both gravities: exact
  to 1e-4 on every UFO step of the one-step-per-frame trace apart from dashes. (Fitting it on trace
  x is misleading: on the second step of a two-step frame the logged x and y repeat the first's.)
- **Turned dash orbs** fly along the orb's angle: y += xVel x 0.25 x tan(-angle) per step (290 deg:
  +6.5939 per 2.4 of x, exact), yVel reads 0; the player shows the orb's angle (-70, -24, 0) for
  the whole dash, in cube mode too. When it ends the flying modes turn on from the dash angle in the
  same step (with that step's dash move); the cube gets back an angle the dash hid (122, 110: not
  measured, the sim keeps spinning it underneath). Upside-down or flipped turned dashes: unsupported.
- **The dash uses the press** (no UFO jump after it), and **a pad ends a dash** (3 pink pads under
  -70 deg UFO dashes: yVel 6.4 on that step).
- **Gravity portals act on their first touch only**, even when that touch changed nothing (a UFO
  already upside-down touched a yellow portal, a blue one flipped it back, the yellow one touched
  again did nothing; the sim had flipped twice). Also fixes ChopStep 2's yVel/4 stops.
- **Growing on a block**: a normal-size portal while standing mini on a block puts the player on the
  block at once (upside-down 771 -> 765); on the floor line it still waits a step.
- **The wave dies on any solid it touches, slopes too, unless it touches a D block (1755)** (the
  user). Inside D blocks it slides on block faces met from straight above or below, with its 10x10
  box (mini 6x6): a mini wave rising into undersides at 690 stood at 687 for 16 steps, ground flag
  set (AKIRA). Big gains in Orochi, ChopStep, SubSonic. Wave on slopes inside D blocks: not measured
  (stops).
- **Wave slope deaths**: an unturned 7.4 box (mini 4.44) against the slope's triangle. All 33
  normal-size slope deaths in Tartarus, Sonic Wave 2 and SubSonic fit to 0.1 (the box turned by the
  wave's rotation doesn't fit); mini 4.44 is the same ratio, 10 of 15 mini deaths fit and the rest
  touched no slope. Tartarus: all 22 wave slope stops gone; +3,200 steps over the regression.
  (The true death step is the first row that repeats the previous tick, not the row before it.)
- Toggle orbs with no target group (key 51 = 0) do nothing but use the press.
- Checked and kept: the player's box turned by its rotation. One ball touch of a turned portal
  (AKIRA, 17 deg) fits the unturned box better, but turning it off for the ball loses steps overall.

Open in AKIRA: ship deaths at hazards moved by move triggers (458, 216: the sim dies, the game
doesn't), 19 slope stops (1339), RotateCom-moved hazards, a blue pad in wave mode, saws against
the turned ship (still one step early).

## Ball and UFO on slopes (2026-11-16)

Built from the existing traces (~10,000 ball/UFO steps on slopes). Regression +12,195 steps, none
lower (DoubleDash +2,645, Orochi +2,006, Night Rider 2 +1,807, SubSonic +1,479, josh +1,105).
Ball/UFO slope stops 265 -> 153, now ordinary differences rather than "not implemented".

- **Ball**: the cube's slope code (sits half its size from the line at right angles, capped past
  the top; ~4,600 steps exact for ball and UFO). Carried off a slope's top it takes the ship's
  launch (L[k] x xVel x steps/24 in [0.4, 1]); that step still moves with one step of gravity
  (291 -> 291.029 upside down).
- **Ball switch on a slope** that carries it up: the jump value gains a quarter of the ship's full
  launch, rounded to 0.001, before the 0.3 switch factor: round(jump + 0.25 x L[k] x xVel, 3) x 0.3
  (8.984 + 2.086 -> 3.321000132, float-exact; ~70 switches, 1x-3x, normal and mini, 1:2 / 45 /
  2:1); not by the time on the slope. On a falling slope: the flat value. It switches on the press
  step. (Orochi has a few 3.84s the rule puts at 3.707: open.)
- **Ball pushed by a slope on the side away from gravity** (switched under a falling ceiling):
  it rides that line while yVel keeps building up, like the ship's other-side slopes.
- **The UFO on slopes is the ship** (`_ship_slopes`): the held button counts as thrust (riding a
  rising floor held, yVel reads 2.0, ground flag off; under a slope it's pushed), the same launch.
  Against the cube's code for the UFO: +3,400 steps.
- **A slope falling away ahead** (a peak: rising slope then a falling one) doesn't hold the player
  until its centre gets past the falling slope's top end (all modes using the cube code: +2,175,
  Night Rider 2 +1,622).
- Open: ball/UFO leaving slopes (yVel at the launch, 23 + 18 stops), landings onto slopes (50),
  the Orochi 3.84 switches, a press already buffered when landing on a slope.

## Sailent Clubstar (89054024, 2026-11-16)

740 practice attempts, mostly mini cube at 0.5x. 85,133 steps matched.
- **No landing snap at 0.5x, 3x or 4x**: 846 block-to-block landings over 27 traces (535 at 0.5x
  here, every layout seen) and none snapped. The old default ("snap everywhere") is gone. Only 1x
  and 2x snap, on their measured layouts. Snap logging: `SNAP_LOG=1` makes tracediff print a
  `SNAPLOG` line per candidate landing (speed, layout, snap/keep). `SNAP_ORACLE=1` also takes the
  game's choice so the run continues.
- **Upside-down spike (ID 8)**: the 0.2 is inset from its flat side only, and the tip stays put. An
  upside-down mini cube passed 0.01 under the tip of downward spikes and lived 19 times, but the
  old "whole box 0.2 lower" killed it. The original 12 flat-side survivals still fit.
- Both changes together: +30,071 matched steps on the other 26 traces, none lower.
- **The jump at 47% (x 25641) is impossible at 240 steps/s.** The mini cube must jump from the
  floor at y 1389 to clear spike 1 (x 25665.5) and spike 3 (x 25696.5). Steps fall at
  x = 25639.3965 + k x 1.04688, and every attempt lies on this grid:
  - Jumping at x 25639.40 clears spike 1 by 0.75, then touches spike 3 by 0.0098 in x.
  - Jumping one step later, at x 25640.44, hits spike 1 by 0.49.
  - The window of jump positions that works is about 0.6 units wide, between two steps.
  - No snap moves x here.
  - The sim gives the same deaths on the same steps for all ~150 attempts.
- Open: on its first step over a square made of two 45-degree slopes at x 25650 (the hanging one's
  flat top is 0.5 above the floor blocks), a standing mini cube is lifted 0.5 (46 times). Landing
  cubes on a hanging slope's flat top, like on a block top, fixes Sailent (+598). It costs the slope
  test levels and Night Rider 2 (-500) even when limited to standing step-ups, so it isn't wired in.

## Aeternus (102647436, 2026-11-16) and negative scale

561 attempts (bot), 4x start; 61,658 steps matched (58,588 before this pass).
- **Negative scale with the legacy fixNegativeScale off** (the user: "the hitbox gets really small
  and goes way off centre"):
  - What GD stores as the object's rect is a **0x0 point at (x - w*sx/2, y - h*sy/2)**, using the
    signed scales. A scale of -1 on both axes puts it at the top-right corner. This comes straight
    from GD's own orb rects in the Lost Love trace:
    - 33 orbs at -1, -0.6 and -1.4 give +18, +10.8 and +25.2;
    - flipping the orb doesn't move the point.
  - For a quarter-turned object (Aeternus's 329 slabs), the point uses the turned width and
    height, and the offset is not turned. Turning the offset put the point where the cube touched
    the slab and lived.
  - **Saws** (negative radius) never kill. Aeternus: the cube passed 9.7-17.3 from the centre of 3
    negatively scaled 184 saws (radius 17.3-23.3) and lived. The same saws with a positive scale
    killed at 16.5-19.9.
  - The converter writes the point as `neg: [x, y]`; levels converted earlier don't have it.
  - Results:
    - Aeternus: death mismatches 103 -> 55.
    - Lost Love startpos 2: 14,968 -> 15,821. Reconverted with the same 4,666 objects and 117
      triggers.
    - La Llorona 2 (17 such objects) never reaches them.
- Snaps: 91 candidate landings at 1x-4x, no snap off the measured layouts.
- Open: a mini UFO dying on a spike and touching a turned blue pad (334 deg) on the same step. The
  game flipped it on that step, but the sim's turned 18x18 box (8.7 deg) doesn't reach the pad. A
  ~20-21 box would hit on exactly that step. A fit over all turned contacts mixes portals'
  own timing and isn't consistent yet. This is about 40 of the "yVel + upsideDown" stops.

## DB test 1 (own test level, tools/testlevel.py; 2026-11-17)

10 attempts, 3 to the end. What it settled:
- **Hanging slope flat tops** (solid away from gravity) hold the cube like a block top.
  - A standing cube steps up onto one on its first overlapping step: the 45 and 2:1 squares 0.5
    above the ground were stepped up every time, and it falls off past the end like a ledge.
  - A jump lands on a lone one (y 167 on tops at 152).
  - Two rules come from Night Rider 2 x 41707. Landing from the air, a block wins over a flat top
    (1111.0 kept over 1111.5). And a flat top doesn't lift a cube that was already inside its box
    on the previous step.
  - Cube only. Sailent +598, Night Rider 2b +13, the slope test levels unchanged.
- **Cube into a hanging slope's underside or tip**: it dies once its box is more than 7.47 past the
  line, measured along y at the box's deepest point. It lived at 7.36 and died at 7.58, over 6
  deaths at 45 and 2:1, rising and falling (`C.SLOPE_UNDERSIDE_KILL`, normal size only). **Not
  wired in** (env `SLOPE_UNDERSIDE=1`). Artifice x 54725, an upside-down cube at 2x, lived at
  8.34 and died one step later. A square box fits neither level (DB: half in 8.56-9.95; Artifice:
  10.19-10.83). The cube's rotation (5-20 deg off square in DB) is the next suspect.
- **Blue pad turned 90 deg**: no effect on an upside-down cube, 3 of 3 (it isn't even logged as
  used). Other turns and gravities aren't measured yet.
- **Flip + normal gravity portals at one x**: both fire, flip first. It ends in normal gravity with
  yVel x 0.25. A standing cube loses the ground flag for one step.
- **Negative scale turned 30/45/60 deg**: the normal turned hitbox (GD rects 49.2 / 50.9 wide,
  centred). The 0x0 point is only for unturned or quarter-turned objects; the converter now leaves
  turned ones alone.
- **Turned blue pad (334 deg) against a mini UFO on the floor** (rotation -3.2): it fires at x
  5674.89, not at 5673.59. Only an 18 box turned by +3.2 (the opposite of the trace's sign) fits.
  The Aeternus case (rotation +8.7) misses by 0.004 with the sim's current sign. Not settled: the
  turned player box needs a test with larger tilts.
- UFO jumps on slopes: the game gives 8.0 / 7.355 where the sim gives 6.871 (x 1716, 1914, 2879).
  Not fitted yet.

## Cosmic Salad (78676189, 2026-11-17)

Three traces: 1794938197 (198 attempts), 1794938575 (115), 1794938826 (560, 114 MB). All
legacy options are off, including fixRadiusCollision. The level has 1,062 move triggers acting on
8,220 objects. Matched 48,014 + 25,008 + 525,447 steps (before the snap change below). The modes
covered: wave 4x, cube 1x-4x normal and mini, UFO 4x, ball, mini ship, a little dual.

- **Landing snap only after a jump** (all 32 traces + Cosmic Salad, 3,374 logged landings, with
  how the player left the ground):
  - 1x: jump 70 of 211 snapped; fall 0 of 214, orb 0 of 229, pad 0 of 170.
  - 0.5x: jump 3 of 63, pad 1 of 72 (the pad case isn't checked yet).
  - 2x and 3x: no snaps at all (2x (150, 30): 9 jump landings, none snapped). That contradicts the
    old 2x (150, 30) entry from the 3-landing staircase test.
  - 4x (150, -30): 12 snapped after a pad and 2 after a fall; the sim doesn't snap at 4x. Not
    understood: moving blocks?
  - 0.5x jump snaps: (60, 60) twice, (90, 30) once, (120, -30) once. That's the 1x list shifted
    30 to the left.
  - Mixed even after a jump at 1x: (90, 30) snapped 12 of 28, (120, 30) 20 of 29, (90, 60) 27 of
    27, (150, -30) 5 of 5. (90, 30) is not in the sim's list. One more factor is missing. The same
    blocks, layout and distance snapped 6 times and stayed once (ids 1 > 207, d = -29.4). A
    buffered jump vs a fresh one, or where on the reference block it jumped from, are guesses.
  - **In the code and regression-checked (2026-11-17)**: `Sim._snaps` returns False unless
    `p.launch == "jump"` (`SNAP_ANY_LAUNCH=1` restores the old rule), and SNAP_PATTERNS["0.5x"] =
    (60, 60), (90, 30), (120, -30). Lost Love +506, part 14 +256, part 11 +117 (+879), no
    trace lower.
  - Tools: `p.launch` (jump/pad/orb/fall) in physics. SNAPLOG lines now end with the raw distance
    to the predicted spot and the launch kind.
- **Saws with fixRadiusCollision off**: circle vs the player's unturned box with radius = table
  radius x scale (the current model) is still the best fit. Over 177,856 steps near static saws, it
  separates the wave and mini ship exactly. Worse fits: radius x scale^2, unscaled radius,
  centre-to-centre, and the turned box (either direction). The leftovers are a few specific saws
  (741 at 8319/417 and 9005/433, 188 at 16033/18293, 678 at 10041). There the cube or UFO lived
  up to 7-11 inside the circle, which looks like saws that are really elsewhere (moved or toggled)
  rather than a rule. 50 false sim deaths at 741 (9005, 433): the cube lived 0.21 inside.
- **Mode and size portals the sim misses**:
  - The ball portal 47 at (4785, 225), group 1, fired while the cube was at y 1059. The mod logs
    the portal's live position (getPositionY), and it said y 225, rect y 182-268. Group 1 has 699
    objects, and no kept trigger targets it. Not understood.
  - Mini + ship portals at (3875, 1095) turned 53 deg: the game used them (cube at y 1117), the
    sim didn't. This is the turned-portal check.
  - The cube portal at (16815, 555) turned 315 deg: the sim switched the UFO to cube, the game
    didn't (28 stops).
- **UFO 4x on slopes** (about 430 stops at x 14500-16750, mostly upside down): most are y off by
  ~0.0004, and the UFO holds yVel -2.0 on ceiling slopes. One snapped 8.5 units onto a slope
  (509.35, while the sim had 517.81). That's the open UFO-slope area.
- Remaining stops: 66 solids and 64 hazards moved by move triggers that something not simulated
  starts, 46 hazards turned by a RotateCom at x -29 (from the start), dual p2.x (24), and the
  first stops at x 1500-1840 (x off by 1 at 1x: snaps).

## Regression speed (2026-11-17)

- Profile (Sailent, 738 attempts): 169 s, of which 152 s was `Sim.__init__` per attempt (copying
  ~20,000 objects with dataclasses.replace and rebuilding the grid). The physics took 14.5 s and
  parsing the CSV 0.5 s, so a parse cache isn't worth it.
- Now the objects and the grid are built once per level (`level._sim_template`) and shared. An
  object is copied only when a run changes it (`Sim.own`: triggers, toggle orbs, breakables,
  undo). Sailent 169 s -> 10 s, with identical results on all 34 traces.
- `./run.sh tools.regress` runs the set in `tools/regress_set.txt` on half the cores at
  below-normal priority, biggest first. It compares with `tools/regress_baseline.txt`
  (`--save` updates it) and writes full output to `.regress/<name>.txt`. The full set takes 3 min
  12 s (it took ~15 min with the old shell script). The slowest is Cosmic Salad A (192 s, one
  process: attempts can't be split, because practice checkpoints restore the snap reference from
  earlier attempts).
- PyPy 8.0.1 (pypy3.12-v8.0.1-win64.zip from downloads.python.org, 35.6 MB, SHA-256 matches
  pypy.org's checksums) is unzipped at %LOCALAPPDATA%/pypy-download. `run.sh` uses it when it's
  there (`PY=python ./run.sh ...` forces CPython). Output is identical: Sailent 10 s -> 6.9 s,
  Cosmic Salad A 192 s -> 61 s, and the full regression 3 min 12 s -> **76 s**, every trace at
  baseline.
