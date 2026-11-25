# What the simulator still needs

## In-game tests

Record with `physics-trace` on (DynamicButter saves the level with the trace).

1. **Mini spider band ceiling.** In the spider test levels (spider portal at y 135, then a mini
   portal) a mini spider thrown up arrives at 351.9 = ceiling 360, not the band's 390 (25 of 25).
   In part 11, josh and saddsa mini spiders stand at band + 300. Test: spider portals at y 135, 285
   and 435, normal and mini, throws up with nothing above; a mini portal before vs after the spider
   portal.
2. **Spider pad throwing a spider.** Arrives standing with yVel 0 in 3 normal-size cases, moving
   with yVel 1 in 3 mini ones. Test: spider pads up and down, normal and mini, standing on them and
   touched in the air.
3. **UFO press on a slope.** Normal size, normal gravity is settled (8.0). Open: mini (9.368 twice,
   Double Dash 3x/4x) and upside down at 4x (6.871 once, 2.0 once). Test: mini UFO on 45 deg and
   2:1 floor slopes at 1x and 3x, pressing after 1, 5 and 30 steps; the same upside down on ceiling
   slopes, also at 4x.
4. **UFO after an orb: when is yVel clipped to 8?** DB test 1 (1x, yellow): not clipped (11.051).
   BOTS and josh (3x/4x): clipped to 8 where the sim doesn't clip. Test: yellow, pink and red orbs
   in UFO mode at 1x and 3x, normal and upside down, held and released.
5. **Blue pad turned 90 deg against a normal-gravity cube** (270 is settled; 90 upside down does
   nothing). Also both turns in ball and UFO mode.
6. **Cube on the floor running into the side of a floor-level block** (no trace has one; the sim
   kills it with the inner box). A few runs at 1x and 3x, normal and mini.
7. **Standing mode switches on blocks** (on the floor y is kept that step; on blocks the traces are
   mixed): cube -> spider, cube -> wave, wave -> cube, spider -> robot on a block at 1x.
8. **Snaps:** 1x jumps onto (90, 30) and (120, 30) from different spots on the block, and falls
   onto the same layouts.
9. **Turned player box:** Aeternus (mini UFO +8.7 deg) fits the current turn direction, DB test 1
   (mini UFO -3.2 deg) the opposite. Test: pads and orbs turned 30-60 deg from each side, the player
   tilted 10-40 deg both ways, normal and mini, cube and UFO.
10. **Cube into a hanging slope's underside** at different rotations (dies at 7.47 past the line in
    DB test 1, Artifice's upside-down 2x cube lived at 8.34; `SLOPE_UNDERSIDE=1` is off).
11. **Cube jumping up into a slope's open side** (68 stops in the traces).
12. **Teleport portals turned ~45 and 90 deg**, cube and ball.
13. **Wave into each mode portal**, going up and down, normal and mini.
14. **Wave on slopes and blocks inside D blocks**; mini wave deaths at slopes (to settle the 4.44
    box).
15. **Ball and UFO on slopes**, at 1x and 3x, normal and mini, both gravities:
    - holding through the slope's end (UFO held; ball with a press buffered before landing);
    - short stays: touch a rising slope for 1, 3, 6, 12, 20 steps and leave (the launch ramp);
    - down a slope from its top and off its bottom: stick, drop or launch;
    - slope to slope (different steepness) and slope to block;
    - a ball press on the slope's last step, and at 4x.
16. **Ball band** (240 high, measured from one portal at y 285 and ceilings at portals 130/135): ball
    portals at y 165, 225, 345 and 525 with nothing near the band edges, normal and mini; roll on
    the floor edge and switch to stand under the ceiling edge; one Free Mode ball portal.
17. **Upside-down into the ground** in other modes: ball, robot and spider sent down into the floor
    (green orb, black orb) while upside down (the cube stops there with yVel 0).
18. **Each physics option on and off**: the same run with one option switched.
19. **Swing**: everything.

## Open in the existing traces

- **Snap at 1x**: (90, 30) snapped 14 / kept 16 and (120, 30) 20 / 9 after jumps; the missing factor
  isn't the press, the time in the air, the takeoff offset or the reference block. 2x (150, 30)
  never snapped in 9 jumps (drop it?). 4x snaps after pads (Cosmic Salad). A 0.5x pad snap case.
- **Ball 0.5 off**: 6 stops left in Sailent (y 1119.5 / 1161 / 1299.5) after the ball got the
  flat-top rule.
- **Sailent**: UFO yVel 3.2 vs 3.81 (ticks 18114-20558); ball gravity flips 0.03 off (ticks
  23938-24370).
- **Missed deaths in Tartarus**: ball 16, cube 7, ship/UFO 6. A rotated ship dies a step later than
  the sim at saws 1705/1734. Saw outliers in Cosmic Salad.
- **Robot rising into a block's underside** passes in the game where the sim stops it (Lost Love ~15,
  Duelo Maestro).
- **UFO on slopes**: leaving-slope yVel (41 stops), an 8.5 catch onto a slope (Cosmic Salad). The
  0.0004 drift on Cosmic Salad's moving slopes is the move trigger's rounding: try position = start
  + total x ease(t), rounded once.
- **Turned mode/size portals** (Cosmic Salad): 53 deg used by the game but not the sim, 315 deg the
  other way; a group-1 ball portal that fired 834 units away.
- **Objects moved by triggers something unsimulated starts**: Cosmic Salad (130 stops), AKIRA, Night
  Rider 2, The Hallucination.
- **Respawn catch-up**: NR2b -134 (respawn right after moves fired at x 29847-30117).
- The Follow Player Y lag (1/6 of the gap per step); the same-step
  order of a touch Toggle and the triggers it enables; Flamewall's ball yVel +0.083 a step after
  wave -> ball -> blue portals.
- **Dual**: 55 player-2 x stops; legacy-dual gravity portals; a player-2 UFO's falling rule after an
  upside-down ship.
- **Slope 1339**: 106 "not implemented" stops.
- **1-ulp noise** in yVel and y on ~5 % of airborne steps.

## Not implemented

- Swing, platformer, mirror physics.
- Spider on slopes; wave on slopes inside D blocks; cube jump on a falling slope; turned dash orbs
  upside down.
- Turned solids (angles other than multiples of 90) have no collision.
- Force blocks outside cube/ball, sideways force arrows; Gravity trigger for ship/UFO/wave; Stop
  trigger pause/resume.
- Follow, advanced follow, keyframe, area, collision, count, item, time, random, sequence, on-death,
  teleport, reverse, rotate-gameplay, time-warp, player-control and end triggers.
- F block (2866), ExtraSticky, Dont Boost, GripSlope, Extended Collision. Passable (key 134) is in
  but unvalidated.
