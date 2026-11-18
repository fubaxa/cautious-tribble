"""Physics constants, all measured from DynamicButter physics traces (GD 2.2091, 240 steps/s).

Every value here has to be backed by a trace; anything not measured yet is left out so the simulator
fails loudly instead of guessing. Speeds are keyed by GD's player speed value (m_playerSpeed).
"""
import math

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
# every airborne cube step (all traces to Tartarus, 2026-11): 0.5x 0.21151-0.21174 (mini) /
# -0.21199, 1x 0.21551-0.21599, 2x 0.21526-0.21549, 3x and 4x 0.21601-0.21649 (3x off-grid
# steps: -0.6865 -> -0.470 and 0.1095 -> -0.107, Tartarus). 1x uses GD's 0.958199 x 0.225
# (= 0.21559), the others the middle of their range.
CUBE_GRAVITY = {"0.5x": 0.2116, "1x": 0.958199 * 0.225, "2x": 0.21537, "3x": 0.21625,
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
# half-height 3.924: a cube rising with its centre 3.923981 below a block died (twice, Every End
# 2 practice), at 3.924011 it survived (bot run; the two only differ in float32 rounding at
# different heights). Same in old and 2.2. Mini x 0.6 (assumed).
INNER_BOX = {1.0: (9.0, 7.848), 0.6: (5.4, 4.7088)}
# The cube's hazard box is its full 30x30 (mini 18x18), plain corners: deaths at corner overlaps
# (0.023 x 0.484), (0.523 x 0.034), (0.176 x 0.298), (0.516 x 0.110) in Every End 2.
# An upside-down spike (ID 8, flipped or turned 180) has its flat side (the top) inset by this much:
# 12 survivals at an overlap of 0.11 with one's flat side, while a normal spike killed at the same
# (0.516 x 0.110); 0.12-0.25 fit every run, 0.3 does not. Its tip end is NOT moved: an upside-down
# mini cube passing 0.01 from the tip lived (Sailent Clubstar; "the box 0.2 lower" killed it 19 times).
FLIPPED_SPIKE_SHIFT = 0.2
# The inner box against blocks touches inclusively, with square corners (as GD's hitbox viewer
# draws it): a death touching a side exactly (0.000 sideways, 0.55 vertical; Every End 2 x 95275,
# a solver macro). An earlier rounded-corner fit came from the 0.00003 difference above.
# A falling cube is only caught by a block whose top is more than this below its centre (after
# the step's move): caught at 3.12 (lowest of 1,394 landings), not caught at 2.748 (Every End 2,
# x 23355, practice: the same x landed from 3.97 above, 6 times).
LAND_MIN_ABOVE = 3.0

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
# 0.5x, 3x, 4x: no snap in 846 landings over 27 traces (Sailent Clubstar's 535 at 0.5x), any layout.
# 0.5x: the 1x layouts 30 shorter (4 jump landings, all snapped; Sailent's 535 were falls/orbs/pads
# or other layouts). Only landings after a jump snap (see Sim._snaps).
SNAP_PATTERNS = {"0.5x": {(60, 60), (90, 30), (120, -30)},
                 "1x": {(90, 60), (120, 30), (150, -30)}, "2x": {(150, 30)}}

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
# Slopes kill the wave (unless it touches a D block) when this unturned box reaches the slope's
# triangle: 7.4 fits all 33 normal-size slope deaths in Tartarus, Sonic Wave 2 and SubSonic, to
# 0.1 (the step before clear up to 7.4, the death step needing 7.3); mini 4.44 by the same ratio
# (fits 10 of 15 mini deaths, the rest touched no slope: not settled).
WAVE_SLOPE_BOX = {1.0: 7.4, 0.6: 4.44}
# A cube meeting a hanging slope (solid on the side away from gravity) from below or the side dies
# once its box reaches this far past the slope's line, measured along y at the box's deepest point
# (DB test 1: 6 deaths at 45 and 2:1, survived 7.36, died 7.58; normal size only). NOT WIRED IN:
# Shitty Artifice x 54725 (upside down, 2x) lived at 8.34 - the cube's rotation may matter.
SLOPE_UNDERSIDE_KILL = 7.47
# Wave floor and ceiling: set by the wave portal. Floor = portal y - 150 rounded down to a multiple
# of 30, at least the ground (90); the ceiling is 300 above it. The wave slides along them with its
# 20x20 box (mini 12x12). Measured with portals at y 135 (90-390), 555 (390-690) and 705 (floor 540).
WAVE_AREA_HEIGHT = 300.0

# Ship (levels with fixGravityBug off; 23,000 free-flight steps from the ship test level, BOTS phase
# 4 and VOLTSTORM, all speeds - the ship doesn't depend on speed). Per step yVel changes by
# SHIP_G x a factor, rounded to 3 decimals: holding +0.5 while "falling", +0.4 otherwise; released
# -0.32 while falling, -0.48 otherwise (gravity-relative). GD's "falling" compares the raw yVel
# with 2 x gravity (per speed, see ship_falling_yvel): yVel < it right side up, yVel > it upside
# down (not mirrored: the gravity bug; with fixGravityBug on it's mirrored). Mini: everything / 0.85. yVel is capped at +8 / -6.4 (gravity-relative; mini / 0.85).
# The ship flies in a 300-high band set by its portal like the wave's (floor 330 for a portal at
# y 495: it stopped at 615 = 630 - 15). Entering or leaving the ship halves yVel after the step's
# move with the old mode (cube -7.744 -> -3.98 = (-7.744 - 0.216) / 2; ball, cube the same way);
# between the wave and the ship it's a quarter, both ways (7.8 -> 1.95; ship -7.15 -> wave -1.7875).
SHIP_G = 0.958199 * 0.225


# GD's "falling" threshold for the ship: 2 x gravity at this speed (per-speed gravity / 0.225),
# normal and mini alike. Data (both sizes): 0.5x between 1.878 and 1.883, 1x 1.915-1.917, 2x
# 1.907-1.915, 3x above 1.921 (so 3x uses 4x's 0.21625, not the 0.2156 the cube table has - the
# cube's 3x steps round to -0.216 either way), 4x 1.922-1.923.
# 0.5x: at most 1.882 (a mini ship at 1.882 still accelerated as not falling); 2 x 0.21175 / 0.225
# = 1.88222 was too high
SHIP_FALLING_YVEL = {"0.5x": 1.8819, "1x": 2 * 0.958199, "2x": 2 * 0.21525 / Y_STEP,
                     "3x": 2 * 0.21625 / Y_STEP, "4x": 2 * 0.21625 / Y_STEP}


def ship_falling_yvel(speed: str) -> float:
    return SHIP_FALLING_YVEL[speed]
SHIP_HOLD = (0.5, 0.4)          # (falling, not falling)
SHIP_RELEASE = (0.32, 0.48)
SHIP_CAP_UP, SHIP_CAP_DOWN = 8.0, 6.4
# Faster than the caps (after an orb or a pad) the ship slows back instead of thrusting:
# gravity-relative, rising past +8: -0.32 holding / -0.48 released; falling past -6.4: +0.5 holding
# / +0.4 released (hundreds of steps, both orientations: ship test level, BOTS, josh layout). On the
# step after a yellow orb or pad it's put at the cap instead (16 -> 8; a red orb's isn't).
SHIP_ABOVE_CAP = (0.32, 0.48)   # (holding, released)
SHIP_BELOW_CAP = (0.5, 0.4)
SHIP_MINI = 1 / 0.85
WAVE_TO_SHIP_YVEL_FACTOR = 0.25
# Orbs in ship mode (gravity-relative yVel the orb sets; only what's been seen): yellow = the
# cube's value, red the same at normal size (11.18 at 1x, 13 uses; mini 12.578), green = 0.7 x
# yellow (it also flips gravity), pink 4.137 at 1x, blue flips gravity and sets the cube's fall,
# black -14 at both sizes. Dash orbs: not seen yet. (Ship test level, 1x, and BOTS phase 4.)
SHIP_ORB_YVEL = {("yellow", "1x", 1.0): 11.18, ("yellow", "3x", 1.0): 11.23,
                 ("yellow", "3x", 0.6): 8.984, ("yellow", "4x", 0.6): 8.984,
                 ("red", "0.5x", 1.0): 10.62, ("red", "1x", 1.0): 11.18, ("red", "3x", 1.0): 11.23,
                 ("red", "3x", 0.6): 12.578, ("red", "4x", 0.6): 12.578,
                 ("green", "0.5x", 1.0): 7.434, ("green", "1x", 1.0): 7.826, ("green", "3x", 1.0): 7.861,
                 ("green", "1x", 0.6): 6.261, ("green", "3x", 0.6): 6.289, ("green", "4x", 0.6): 6.289,
                 ("pink", "1x", 1.0): 4.137}
SHIP_BLUE_ORB_FALL = {("1x", 1.0): 4.472, ("3x", 1.0): 4.492, ("3x", 0.6): 3.594, ("0.5x", 0.6): 3.3985}
# Pads in ship mode: yellow = the cube's (16, mini 12.8), red 10.08 (half-ish of the cube's 20; at
# 0.5x and 1x alike). Pink: not seen yet.
SHIP_PAD_YVEL = {("yellow", 1.0): 16.0, ("yellow", 0.6): 12.8, ("red", 1.0): 10.08, ("pink", 1.0): 5.6,
                 ("pink", 0.6): 4.48, ("red", 0.6): 12.16}   # mini red: not 0.8 x (Artifice, 4 uses)
SHIP_BLACK_ORB_YVEL = -14.0
# Spider throws stop at hazards whose box comes within this of the player's x (3.998 stopped,
# 4.036 passed; ship tests 2026-11-14).
SPIDER_HAZARD_REACH = 4.0
# A spider throw up with nothing above ends here (out of bounds, killed 2 steps later).
SPIDER_TOP_Y = 3180.0

# Ship on slopes (ship slope test 2026-11-14, 3x and 1x, both gravities, 45 deg / 2:1 / 1:2).
# Leaving a slope where it keeps moving the way the ship goes (a rising floor's top, a falling
# ceiling's bottom) launches it at SHIP_SLOPE_LAUNCH[|k|] x xVel x f, f = steps on the slope / 24
# held between 0.4 and 1 (1 step: 0.4, 18: 0.75, 19-22: 19/24..22/24, 24 and more: 1).
# The 3x values are pinned by the rounded launches (e.g. 21/24 of 2:1 gives 10.356, 22/24 10.849).
SHIP_SLOPE_LAUNCH = {0.5: 4.50455 / 7.8000023138976102, 1.0: 8.34225 / 7.8000023138976102,
                     2.0: 11.83565 / 7.8000023138976102}
SLOPE_RAMP_STEPS = 24
SLOPE_LAUNCH_MIN = 0.4
BALL_SLOPE_SWITCH = 0.25    # ball switch on a rising slope: jump + this x SHIP_SLOPE_LAUNCH[|k|] x xVel
SHIP_SLOPE_AWAY_YVEL = 2.0   # pushed by a slope with the thrust away from it: at least this
SHIP_SLOPE_SNAP = 1.0        # a new contact catches the ship this far outside a surface not coming at it
                             # (0.98 caught, 1.13 not)


def wave_area_bottom(portal_y: float) -> float:
    import math
    return max(GROUND_Y, math.floor((portal_y - 150.0) / 30.0) * 30.0)
WAVE_HITBOX = {1.0: 10.0, 0.6: 6.0}
# Mini wave moves twice as steeply: y changes by xVel x 0.25 x 2 per step (63.43 degrees).
WAVE_MINI_SLOPE = 2.0


# Orbs in every mode (Shitty mix part 14, 1,000+ uses, plus the tables above): yVel = the cube's
# jump at that speed x a factor per (mode, orb), x 0.8 for mini, rounded to 3 decimals; the ball
# and the spider then x float32 0.7 (that gives GD's trailing digits exactly). Not the gravity
# ratio between modes: each mode has its own factors. Blue = the fall speed after the flip.
ORB_FACTOR = {
    "cube":   {"yellow": 1.0, "green": 1.0, "pink": 0.72, "red": 1.38, "blue": 0.4},
    "robot":  {"yellow": 0.9, "green": 1.0, "red": 1.28, "blue": 0.4},
    "ufo":    {"yellow": 1.0, "green": 1.0, "pink": 0.42, "red": 1.02, "blue": 0.4},
    "ship":   {"yellow": 1.0, "green": 0.7, "pink": 0.37, "red": 1.0, "blue": 0.4},
    "ball":   {"yellow": 1.0, "green": 1.0, "pink": 0.77, "red": 1.34, "blue": 0.4},
    "spider": {"yellow": 1.0, "green": 1.0, "pink": 0.72, "red": 1.34, "blue": 0.4},
}
ORB_AFTER = {"ball": 0.699999988079071, "spider": 0.699999988079071}   # float32 0.7
BLACK_ORB = {"cube": -15.0, "robot": -15.0, "ball": -15.0, "spider": -16.5, "ufo": -11.2, "ship": -14.0}


def orb_yvel(mode, orb, speed, size):
    """The orb's yVel (blue: the fall speed), or None when that orb isn't known in that mode.
    The measured tables win (a few mini values round differently); the formula fills the rest.
    Blue: round(jump x size x 0.8) halved by the flip (mini 3.3985 = 6.797 / 2)."""
    table = {"cube": ORB_YVEL, "ball": BALL_ORB_YVEL, "ship": SHIP_ORB_YVEL}.get(mode, {})
    blue = {"cube": BLUE_ORB_FALL, "ball": BALL_BLUE_ORB_FALL, "ship": SHIP_BLUE_ORB_FALL}.get(mode, {})
    if orb == "blue" and (speed, size) in blue:
        return blue[(speed, size)]
    if (orb, speed, size) in table:
        return table[(orb, speed, size)]
    f = ORB_FACTOR.get(mode, {}).get(orb)
    if f is None or (mode == "ship" and size != 1.0 and orb == "red"):
        return None
    jump = CUBE_JUMP[speed] * (MINI_JUMP_FACTOR if size != 1.0 else 1.0)
    v = round(jump * 0.8, 3) * 0.5 if orb == "blue" else round(jump * f, 3)
    return v * ORB_AFTER[mode] if mode in ORB_AFTER else v


# UFO (Shitty mix 11 / 14, Artifice, BOTS, VOLTSTORM, josh, cool challenge: ~60,000 steps). A press
# sets yVel on the next step to this, then that step's gravity (6.871 = 7.0 - 0.129), whatever
# yVel was, in the air or on the ground. Same at every speed.
UFO_JUMP = {1.0: 7.0, 0.6: 6.8}
# Gravity like the ship's: base 0.958199 x 0.225, x 0.6 while not falling and x 0.4 while falling
# (the ship's per-speed "falling" threshold), mini / 0.85, rounded to 0.001 each step.
UFO_GRAVITY = (0.4, 0.6)            # (falling, not falling)
UFO_FALL_CAP = {1.0: 6.4, 0.6: 7.529}
UFO_YELLOW_CLIP = 8.0               # the step after a yellow orb or pad (11.18 -> 8.0), as the ship

# Robot (same levels, ~40,000 steps): the cube's jump x 0.5 (mini x 0.8), then yVel held flat
# while the button stays held, for at most 67 more steps (seen at 0.5x, 1x, 3x and 4x), then
# gravity: 0.9 x the cube's, by speed (rounded as measured). Fall cap 15 as the cube.
ROBOT_JUMP_FACTOR = 0.5
ROBOT_BOOST_STEPS = 67
ROBOT_GRAVITY = {"0.5x": 0.19, "1x": 0.194, "2x": 0.194, "3x": 0.195, "4x": 0.195}

# Spider (~30,000 steps): gravity as the ball (0.129 at every speed and size), fall cap 15, box
# 0.9 x the cube's (27, mini 16.2). A press on the ground throws it like the spider orb (onto the
# nearest surface the other way, arriving with yVel 1, standing on the next step).
SPIDER_SIZE_FACTOR = 0.9
SPIDER_MAX_FALL = 15.0

# Pads by mode (all three levels): cube, robot and UFO use the cube's (the UFO's pink is 6.4),
# ball and spider the ball's; mini x 0.8 unless measured.
UFO_PAD_YVEL = {("yellow", 1.0): 16.0, ("pink", 1.0): 6.4, ("red", 1.0): 20.0,
                ("yellow", 0.6): 12.8, ("pink", 0.6): 5.12, ("red", 0.6): 16.0}
FLY_MODES = ("ship", "ufo", "wave")   # entering or leaving these changes yVel (see the portals)


def pad_yvel(mode, pad, size):
    if mode in ("ball", "spider"):
        t, blue = BALL_PAD_YVEL, BALL_BLUE_PAD_FALL
    elif mode == "ship":
        t, blue = SHIP_PAD_YVEL, BLUE_PAD_FALL
    elif mode == "ufo":
        t, blue = UFO_PAD_YVEL, BLUE_PAD_FALL
    else:
        t, blue = PAD_YVEL, BLUE_PAD_FALL
    if pad == "blue":
        v = blue.get(size)
        if v is None and size != 1.0 and 1.0 in blue:
            v = blue[1.0] * MINI_JUMP_FACTOR
        return v
    v = t.get((pad, size))
    if v is None and size != 1.0 and (pad, 1.0) in t:
        v = t[(pad, 1.0)] * MINI_JUMP_FACTOR
    return v


# --- Player rotation (fitted on every trace to Tartarus, 2026-11; the trace logs it each step) ---
# It matters for collisions with objects turned by an angle that isn't a multiple of 90: GD then
# turns the player's box by the player's rotation too (Tartarus: all 424 deaths at turned hazards and
# every turned-portal touch fit, with no false touches; the player's box unturned or the object
# turned the other way don't).
SPEED_VALUE = {"0.5x": 0.7, "1x": 0.9, "2x": 1.1, "3x": 1.3, "4x": 1.6}
CUBE_SPIN = {1.0: 22.5 / 13, 0.6: 2.25}   # degrees per airborne step (1.7307692 / 2.25)
CUBE_SETTLE = 0.13125     # on the ground: the angle left to the nearest 90 shrinks by 1 - this x speed
                          # per step (0.5x .9081, 1x .8819, 2x .8556, 3x .8294, 4x .79)
BALL_ROLL = 0.48143       # degrees per step per unit of xVel (x1.25 mini); after a switch in the air
BALL_AIR_SWITCH = 0.7084  # it turns the other way at 0.7084 of that
SHIP_TURN = 0.0375        # ship: each step the angle moves this part of the way to its direction of
WAVE_TURN = {1.0: 1 / 16, 0.6: 0.1}   # travel (-atan2(dy, dx) of the step's move); the wave faster
UFO_TURN = 0.0175         # UFO: the same, toward UFO_TILT x +atan2(dy, dx) (it tilts the other way),
UFO_TILT = 0.4            # at most UFO_FALL_TILT toward the gravity side (AKIRA: 20,000 UFO steps,
UFO_FALL_TILT = math.degrees(0.1)   # normal and mini, both gravities; exact to 1e-4 but in dashes)
