# GD editor guide (2.2) - simulator-relevant findings (running list)

## Ch.1-3 (pp. 6-42)
- Triggers fire when the player passes their x, or on touch ("Touch Trigger"), or when spawned.
- Blocks: hitting a block's side kills; landing on top is fine. Spikes kill on any touch.
- Gameplay objects work only the first time unless "Multi Activate".
- Spider (purple) pad: teleports vertically until an object is hit, like the spider.
- Dash orbs: move in the arrow's direction while held. On release the green dash keeps gravity and
  the pink dash switches it. Teleport orb: teleports to a target object. Trigger orb: toggles a
  group.
- Mode portals: some modes (ship...) have a floor/roof by default; "Free Mode" removes it.
- Gravity portals: blue = normal, yellow = upside down, green = toggle. Mirror: orange = going left,
  blue = going right.
- Mini is kept through mode changes until the green size portal.
- Speed changers act only on touching their hitbox; the same speed again does nothing.
- Checkpoint objects: platformer only.
- Letter objects:
  - D: the wave can touch blocks (have it, 1755).
  - J: a held click doesn't jump (after an orb); a new click on it still jumps.
  - S: a dash orb's dash stops at it.
  - H: the cube/robot hitting its head on it doesn't die (also upside down).
  - F: hitting your head on it flips gravity.
- Force objects (circle/square hitbox): apply a set force in the arrow's direction; force set in
  Edit Object.

## Ch.6 Edit Group (pp. 57-63)
- ORD (gameplay objects/triggers): the order in which objects activate. CH: channel (rotate
  gameplay).
- Extra options per object:
  - Dont Boost Y / Dont Boost X: stop the player being boosted by a moving object. So moving
    objects DO boost the player by default.
  - NoTouch: no interaction.
  - **Passable**: jump through a solid, land on it from the top.
  - Hide (visual only).
  - NonStickX/Y (platformer): no friction with moving objects.
  - **ExtraSticky**: a player standing on an object moving down too fast stops sticking; this
    raises the limit.
  - **Extended Collision**: objects scaled larger than 6 have inaccurate hitboxes; this makes them
    accurate.
  - IceBlock (platformer).
  - **GripSlope**: by default the player can't slide up steep slopes and slides down instead.
  - ScaleStick: the player's x moves with a scaling object it stands on.
  - **Single PTouch**: in dual, an orb used by both icons at once fires twice unless this is set.

## Ch.7 Triggers, part 1 (pp. 64-92)
- Start Pos: speed, mode, mini/dual/rotated gameplay; "Target Order / Target Channel" (activation
  order); Disable.
- **Move**:
  - Move X/Y in the editor: one block = 10 ("Small Step" makes one block = 30, for precision).
    Check the level-string units against the converter.
  - Easing types.
  - **Player X / Player Y**: the group follows the player's movement (= lock to player, have).
  - **Camera X / Y**: follows the screen's movement instead. NOT simulated (camera position needed).
  - Target Mode: move to a single-object target group, or to P1/P2; Center Group ID = the moved
    group's centre.
  - **Direction Mode**: move "Distance" toward a target (single object or P1/P2).
  - **Dynamic Mode**: target/direction re-checked as the target moves (otherwise only at
    activation).
  - Silent (platformer): blocks move instantly without carrying the player.
- **Stop / Pause / Resume**: stop triggers by group (permanent), pause (resumable), resume. "Use
  Control ID" limits it to remapped spawns.
- **Toggle**: disabled objects are invisible AND not interactable (have).
- **Spawn**:
  - delay;
  - **Spawn Ordered**: the triggers in the group fire left to right, the x distance between them =
    the delay;
  - Reset Remap; a remap page (group IDs remapped for the spawned triggers).
- **Rotate**:
  - target, center (0 = each object about its own centre);
  - degrees (positive = clockwise), x360;
  - **Aim Mode** (face a target/P1/P2, rot offset, limits), **Follow Mode** (copy a target's
    rotation), Dynamic Mode;
  - **Lock Obj Rotation**: positions rotate but the objects don't (hitboxes not turned).
- **Scale**: target, center (0 = own centre), duration, ScaleX/Y, Div by Value, Only Move (moves
  as if scaled, size kept), Relative Rotation, Relative Scale. Scaling changes hitboxes: not
  simulated.
- **Follow**: target group mimics a single-object follow group's movement times X/Y Mod, for Move
  Time.
- **Follow Player Y**:
  - target follows the player's y for Move Time;
  - Speed multiplier, Delay, Offset (10 = one block above);
  - **Max Speed: each step moves MaxSpeed/(MaxSpeed+1) of the remaining distance** (5 -> 5/6).
- **Advanced Follow** (3 modes: plain, accel/friction/near, steering), Edit/Re-Target Advanced
  Follow:
  - delays and variances (+-, random!);
  - MaxRange in units of 30 per block;
  - priorities / exclusive.
  - Random variance makes it non-deterministic: can't be simulated exactly.
- **Keyframe / Keyframe Animation**: movement along keyframes (Bezier curves optional, easing,
  CW/CCW, x360, spawn at keyframes, Time/Even/Dist durations, Close Loop). Mods for time, position,
  rotation and scale.

## Ch.7 Triggers, part 2 (pp. 92-120)
- **Area Move/Rotate/Scale/Fade/Tint**:
  - effects that depend on each object's distance from a centre: P1, P2, screen C/BL/CL/TL/BC/TC/
    BR/CR/TR, or a group;
  - Length, Offset X/Y (with a random +- variance!), Deadzone, ModFront/ModBack, direction
    shapes (Table 7.1), Ignore Linked / Ignore GParent / DEAP, easing in/out, Priority, Effect ID;
  - Area Move: MoveDist, MoveAngle (0 = up, 90 = right), Relative (away from the centre), RFade,
    XY Mode;
  - Area Rotate: degrees (positive = clockwise); Area Scale: ScaleX/Y;
  - Edit Area (by Effect ID) and Area Stop.
  Gameplay-relevant when the targets are solids or hazards. Player-relative: needs the player's
  path.
- **Touch trigger**: toggles (or spawns) a group on a click. Hold Mode: enabled while held,
  disabled on release. P1/P2 Only; Dual Mode (obsolete). In platformer, moving counts as a touch.
- **Count**: fires when an item ID reaches a number (checked continuously), Multi Activate.
  **Instant Count**: checked only when the trigger fires (==, >, <).
- **Pickup**: item ID +=, override, *, /. Division drops the decimals (integer truncation).
- **Time / Time Event / Time Control**: timers on item IDs (start/stop time, TimeMod, ignore
  TimeWarp, start paused, dont override).
- **Item Edit**: Target = op(op(I1, I2), Mod) with =, +, -, *, /. Rounding via NA (truncate,
  the default) / RND / FLR / CEI, plus neg/abs. **Item Compare**: ==, >, >=, <, <=, != with
  tolerance; spawns TrueID / FalseID.
- **Persistent Item**: kept on death, reset on exit.
- **Random / Advanced Random**: random choice of groups (chance %). Non-deterministic: can't be
  simulated exactly (the trace must tell which branch was taken).
- **Sequence**: each activation spawns the next group (counts per entry); MinInt (minimum time
  between steps); Reset time; modes Stop/Loop/Last; Reset Full/Step; Unique Remap.
- Spawn Particles (visual), Reset (collectables / checkpoint object come back).
- **Camera**: Zoom, Static Camera, Camera Offset (10 = one block), **Gameplay Offset** (player vs
  camera centre), Camera Rotation, Camera Edge. These matter only for camera-relative movement
  (Move "Camera" lock, area triggers on screen points, Follow Player...).

## Ch.7 Triggers, part 3 (pp. 120-142)
- **Camera Mode**: in Free Mode the borders (floor/ceiling band) of **Ship, Ball, UFO, Wave,
  Spider and Swing** are removed. So the ball has a band too: CHECK, the sim bands only
  ship/UFO/spider/wave.
- Camera Mode "Disable GridSnap": the camera centre normally snaps to the nearest grid space
  (relates to where the band is placed: the sim's `wave_area_bottom` floors to 30s).
- **Reverse** trigger: reverses the player's direction (classic).
- **Rotate Gameplay**: rotates gameplay (gravity direction) by the arrow. Edit Velocity / Override
  Velocity / VelModX/Y (scale or invert the velocity), Change Channel, Dont Slide (cancels Force
  Object forces), Instant Offset.
- **Event** trigger: spawns a group on player actions (e.g. "Normal Landing"), optionally only on a
  Material ID.
- **TimeWarp**: TimeMod scales time for everything, including player movement and trigger
  durations.
- **Collision / Instant Collision / Collision State / Collision Block**: groups spawned when
  collision blocks overlap (one "Dynamic"); P1/P2/PP = a player touching BlockB (or the players
  touching each other); Trigger On Exit. Collision State: spawns on entering/leaving its hitbox.
- **Toggle Block**: a click inside its hitbox toggles/spawns a group. **Claim Touch: the player
  won't jump and no ring spawns; the click can't be buffered.** Spawn Only; NO Multi Activate.
- **On Death**: toggles/spawns on death.
- **End** trigger: marks the level end and pulls the player toward it (Instant: teleports once
  it's on screen).
- **Player Control**: Stop Jump / Stop Move / Stop Rot / Stop Slide (P1/P2).
- **Options** trigger: Hide P1/P2, Disable P1/P2 Controls; **Unlink Dual Gravity: by default, when
  one dual icon switches gravity, the other switches too**; Edit Respawn Time; Boost Slide (force
  slide).
- **Gravity** trigger: multiplies gravity (<1 lighter, >1 heavier); P1/P2/PT (only the player
  touching it).
- **Teleport** trigger: to a single-object group; gravity after = normal / flipped / toggle; Save
  Offset (keeps the player's offset to the trigger centre); Ignore X/Y; Static Force / Force /
  Redirect Force with Min/Max and Mod (exit velocity = Mod x current speed).

## Ch.8-13 (pp. 156-205)
- Enter effects (and custom Move/Rotate/Scale/Fade/Tint Enter, Stop Enter): described as visual
  (objects move/scale/fade near the screen edges); one block = 30 in their settings. Nothing says
  they move hitboxes. Unconfirmed.
- **Channel system**: by default the player, every trigger and every gameplay object are on
  channel 0 and fire left to right. Rotate Gameplay "Change Channel" moves the player to another
  channel; objects with that CH then fire in the direction of the gameplay arrow (up: smaller y
  first, and so on). Speed changers should be on channels too in rotated/reversed gameplay.
- Keyframe system: details of Keyframe/Keyframe Animation (Time/Even/Dist, Curve, Ref Only, Dup
  Anim, Reverse Order, CW/CCW, closest direction by default, x360, SpawnID/Prox).
- Editor options: Show Hitboxes (blocks white, hazards red, gameplay objects green), Ignore Damage.
  Nothing else gameplay-relevant (auto-build, custom objects, sharing are editor-only).

## Against the simulator (2026-11-17)
Not modelled yet, and present in traced levels (object counts from levels/research):
- **J (1813)**: no jump from a held click on it. In Aeternus 119, Artifice 32, part 11 48,
  part 14 26, NR2 46, Aurorae 38, Llorona 32, AKIRA 30.
- **S (1829)**: ends a dash at it. Double Dash 48, Aeternus 45, part 11 44, Artifice 34, NR2 32,
  Orochi 28.
- **H (1859)**: no head-hit death for the cube/robot. Artifice 114, part 11 61, NR2 56, Double Dash
  51, Aeternus 46, Llorona 38.
- **F (2866)**: flips gravity on a head hit. None in the traced levels.
- **Force blocks (2069 square, 3645 circle)**: Aeternus 4, SubSonic 1, 126242564: 42.
- The **ball has a band** (Camera Mode lists ship, ball, UFO, wave, spider, swing). `_banded` covers
  ship/UFO/spider (the wave separately); dual cube/ball banding was tried and lost 5,000 steps.
  Check the non-dual ball portal band.
- Per-object flags: Passable, Dont Boost X/Y, ExtraSticky, Extended Collision (scale > 6
  hitboxes "inaccurate" without it), GripSlope, NoTouch (the converter drops 121; check the
  others' keys).
- Triggers that change the player: Gravity (multiplier), TimeWarp, Teleport (gravity/offset/
  force), Reverse, Rotate Gameplay (velocity mods), Player Control (stop jump/move/rot/slide),
  Options (unlink dual gravity: linked by default), End (pulls the player), Toggle Block (Claim
  Touch eats the click), Touch (hold mode), Spawn Ordered, Follow Player Y (MaxSpeed/(MaxSpeed+1)
  per step), Stop/Pause/Resume, Scale, Rotate aim/follow, Advanced Follow, Keyframes, Area
  triggers, Random (needs the branch from the trace), Count/Item/Time/Sequence, Collision
  triggers with P1/P2.
