"""Physics constants, all measured from DynamicButter physics traces (GD 2.2091, 240 steps/s).

Every value here has to be backed by a trace; anything not measured yet is left out so the simulator
fails loudly instead of guessing. Speeds are keyed by GD's player speed value (m_playerSpeed).
"""

# One physics step = 1/240 s. GD scales per-frame (60 fps) values by these factors per step.
X_STEP = 0.25    # x += xVel * 0.25 (xVel per speed below)
Y_STEP = 0.225   # y += yVel * 0.225, at every speed (measured at 0.5x..4x)

# Player speed (m_playerSpeed, float32 in the trace) -> portal name.
SPEEDS = {
    0.699999988: "0.5x",
    0.899999976: "1x",
    1.10000002: "2x",
    1.29999995: "3x",
    1.60000002: "4x",
}

# Horizontal velocity per speed (double, exactly as the trace prints it).
X_VEL = {
    "0.5x": 4.1860013287128206,
    "1x": 5.1930015618800667,
    "2x": 6.457002339951754,
    "3x": 7.8000023138976102,
    "4x": 9.6000033430511955,
}

# Speed portal object ID -> speed.
SPEED_PORTALS = {200: "0.5x", 201: "1x", 202: "2x", 203: "3x", 1334: "4x"}

# Player speed value (float32) each portal sets.
PLAYER_SPEED = {v: k for k, v in SPEEDS.items()}

# Cube: yVel change per airborne step (normal and mini are the same), by speed; yVel is then rounded
# to 3 decimals. The real values aren't multiples of 0.001: starting from an off-grid yVel (e.g. a
# mini blue orb's 3.3985) only a value inside these ranges gives GD's next yVel. Ranges that fit
# every airborne cube step: 0.5x 0.21150-0.21200, 1x 0.21550-0.21600, 2x 0.21500-0.21550,
# 3x 0.21550-0.21650, 4x 0.21600-0.21650. 1x and 3x use GD's 0.958199 x 0.225 (= 0.21559),
# the others the middle of their range.
CUBE_GRAVITY = {"0.5x": 0.21175, "1x": 0.958199 * 0.225, "2x": 0.21525, "3x": 0.958199 * 0.225,
                "4x": 0.21625}

# Cube: yVel on take-off, normal size, by speed. Mini = 0.8x (measured at 0.5x and 1x).
# 4x: from the yellow orb (11.23 at 4x), which equals the jump at every speed measured.
CUBE_JUMP = {"0.5x": 10.62, "1x": 11.18, "2x": 11.42, "3x": 11.23, "4x": 11.23}
MINI_JUMP_FACTOR = 0.8

# Cube fall cap: yVel stays at -15 (seen held for 6 steps at 1x before landing).
CUBE_MAX_FALL = 15.0

# Pads: yVel set on the touching step (after the move), by (pad, player size). Same at every speed.
PAD_YVEL = {("yellow", 1.0): 16.0, ("pink", 1.0): 10.4, ("red", 1.0): 20.0,
            ("yellow", 0.6): 12.8, ("pink", 0.6): 8.32, ("red", 0.6): 16.0}

# Blue pad: flips gravity and sets yVel to this speed in the new falling direction.
BLUE_PAD_FALL = {1.0: 6.4, 0.6: 5.12}

# Orbs: yVel set on the step they are used (after the move), by (orb, speed, size). Only the
# combinations seen in traces (same in 2.2 and older levels). The pattern: the cube's jump at that
# speed x 1 (yellow, green), 0.72 (pink), 1.38 (red), rounded to 3 decimals; mini x 0.8. Black is
# -15 at every speed and size (and in ball mode).
ORB_YVEL = {
    ("yellow", "0.5x", 1.0): 10.62, ("yellow", "1x", 1.0): 11.18, ("yellow", "2x", 1.0): 11.42,
    ("yellow", "4x", 1.0): 11.23, ("yellow", "0.5x", 0.6): 8.496, ("yellow", "4x", 0.6): 8.984,
    ("green", "0.5x", 1.0): 10.62, ("green", "1x", 1.0): 11.18, ("green", "2x", 1.0): 11.42,
    ("green", "4x", 1.0): 11.23, ("green", "0.5x", 0.6): 8.496, ("green", "4x", 0.6): 8.984,
    ("pink", "0.5x", 1.0): 7.646, ("pink", "1x", 1.0): 8.05, ("pink", "2x", 1.0): 8.222,
    ("pink", "0.5x", 0.6): 6.117,
    ("red", "0.5x", 1.0): 14.656, ("red", "1x", 1.0): 15.428, ("red", "2x", 1.0): 15.76,
    ("red", "4x", 1.0): 15.497, ("red", "0.5x", 0.6): 11.725, ("red", "4x", 0.6): 12.398,
}
BLACK_ORB_YVEL = -15.0

# Cube and ball inner hitbox: touching a block with it kills; the outer box may overlap a block's
# side or underside without effect (a slab moving down over the cube's top did nothing in Every
# End 2). Size: at most 7.5 (a 9x9 box overlapped blocks twice without a death, 7.5 never); the
# lower bound isn't measured yet (GD's blue box is drawn at about 30%). Mini x 0.6.
# (width, height). Side deaths: half-width 4.47-5.01 (4 in Sonic Wave 2, 2 in the test level);
# half-height 3.77-3.92 (a death in josh layout, a survival in Every End 2). Same in old and 2.2.
INNER_BOX = {1.0: (9.0, 7.8), 0.6: (5.4, 4.68)}
# The normal-size cube's hazard box is its full 30 wide (died at a sideways overlap of 0.109,
# Every End 2 start positions, twice) but a little short in height: vertical overlaps of 0.11
# survived 12 times. No death bounds the height yet. Mini cube: its full 18x18 box (9 deaths).
CUBE_HAZARD_TOLERANCE = 0.2   # fits the true death steps: 7.5-10 (3 block deaths)

# Ground: top of the floor at y = 90 (player centre 105 at normal size).
GROUND_Y = 90.0

# Player hitbox (main, axis-aligned) side length by size.
PLAYER_SIZE = {1.0: 30.0, 0.6: 18.0}

# Gravity portals (with the 2.2 physics options on): the step moves with the old gravity, then the
# portal flips gravity and halves yVel (measured: 10.152 -> 5.076).
GRAVITY_FLIP_YVEL_FACTOR = 0.5

# Snap between consecutive blocks: the most x can be moved on a landing (units), by speed.
# Measured: +1 at 1x, -2 at 2x; the other speeds are from the GD Creator School guide.
SNAP_SHIFT = {"0.5x": 1.0, "1x": 1.0, "2x": 2.0, "3x": 2.0, "4x": 1.0}

# Block layouts the snap happens between: (x distance, y distance up) from the previous block to the
# new one. 1x from Every End 2 (957 landings): (90, 60) and (120, 30) snap almost always; (60, -30),
# (90, -30), (120, 0), (150, 0), (120, 60) and most others never. Some layouts are mixed
# ((150, -30), (180, 30)): not worked out. 2x: (150, 30), the staircase in the test level.
SNAP_PATTERNS = {"1x": {(90, 60), (120, 30), (150, -30)}, "2x": {(150, 30)}}

# Blue orb: flips gravity and sets yVel to this speed in the new falling direction, whatever it
# was before (measured twice at 2x: 4.568 = 0.4 x the 2x jump).
BLUE_ORB_FALL = {("0.5x", 1.0): 4.248, ("1x", 1.0): 4.4719999999999995, ("2x", 1.0): 4.568,
                 ("0.5x", 0.6): 3.3985}

# Ball: pads and orbs give about 0.6 / 0.7 of the cube's value (float32 factors, hence the digits).
# Pads measured at 4x in an older level only; orbs at 2x (2.2) and 4x (older level).
BALL_PAD_YVEL = {("yellow", 1.0): 9.600000381469727, ("pink", 1.0): 6.720000267028809,
                 ("red", 1.0): 12.000000476837158}
BALL_BLUE_PAD_FALL = {1.0: 3.8400001525878906}
BALL_ORB_YVEL = {("green", "2x", 1.0): 7.993999863862991, ("green", "4x", 1.0): 7.860999866127968,
                 ("pink", "2x", 1.0): 6.155099895179271, ("pink", "4x", 1.0): 6.052899896919728,
                 ("red", "4x", 1.0): 10.533599820613862}
BALL_BLUE_ORB_FALL = {("2x", 1.0): 3.197599945545196, ("2x", 0.6): 2.5581499564349652}

# Ball (1x, 2x, 4x, both sizes). A click switches gravity and sets
# yVel to cube jump x 0.3 toward the new gravity (1x: 3.3540001332759855, mini 2.6832001066207884;
# the trailing digits are float32 0.3).
# The real gravity isn't a multiple of 0.001: yVel is rounded to 3 decimals after it is applied, so
# from most values the change is 0.129 and from some 0.130 (2.6832 -> 2.813). GD's gravity constant
# 0.958199 x 0.225 x 0.6 fits every ball step in the test run apart from the 1-ulp near misses.
BALL_GRAVITY = 0.958199 * 0.225 * 0.6
BALL_SWITCH_FACTOR = 0.30000001192092896

# Wave boxes (all centred on the player). Fitted to the TRUE death steps (the step that dies keeps
# the previous step's tick, see tools/tracediff.py): 12 deaths in the wave test.
#   floor: slides with a 20x20 box (mini 12x12): centre y 100 / 96
#   hazards: 10x10 (mini 6x6), the trace's player rect (fits 9.2-10.7 / 6.0-6.35)
#   blocks: an inner box of about 4x4 (mini 2.4x2.4) kills on any contact (fits 3.2-4.8 / 1.9-3.8)
#   portals, pads, orbs: 10x10 (mini 6x6)
WAVE_BODY = {1.0: 20.0, 0.6: 12.0}
WAVE_HAZARD_BOX = {1.0: 10.0, 0.6: 6.0}
WAVE_BLOCK_BOX = {1.0: 4.0, 0.6: 2.4}
# Wave floor and ceiling: set by the wave portal. Floor = portal y - 150 rounded down to a multiple
# of 30, at least the ground (90); the ceiling is 300 above it. The wave slides along them with its
# 20x20 box (mini 12x12). Measured with portals at y 135 (90-390), 555 (390-690) and 705 (floor 540).
WAVE_AREA_HEIGHT = 300.0


def wave_area_bottom(portal_y: float) -> float:
    import math
    return max(GROUND_Y, math.floor((portal_y - 150.0) / 30.0) * 30.0)
WAVE_HITBOX = {1.0: 10.0, 0.6: 6.0}
# Mini wave moves twice as steeply: y changes by xVel x 0.25 x 2 per step (63.43 degrees).
WAVE_MINI_SLOPE = 2.0
