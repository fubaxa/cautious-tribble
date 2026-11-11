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
- **Wave boxes** (all centred on the player; 12 deaths in the wave test run, all on the exact step):
  - Blocks: 7.2x7.2 at **both** sizes; any contact kills, from any side (8 deaths: undersides, a
    front side, corners; the fits are 7.09-7.37 together). D blocks not tested.
  - Hazards: 12x12, mini 7.2x7.2 (4 spike deaths: normal 11.75-13.31, mini 7.03-9.62). In a level
    with the 2.2 physics options off the mini wave uses 12x12 (Sonic Wave 2: one spike, two saws).
    That split is a guess from two levels.
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
