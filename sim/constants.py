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

# Cube: yVel change per airborne step (normal and mini are the same), by speed.
CUBE_GRAVITY = {"0.5x": 0.212, "1x": 0.216, "2x": 0.215, "3x": 0.216, "4x": 0.216}

# Cube: yVel on take-off, normal size, by speed. Mini = 0.8x (measured at 0.5x and 1x).
CUBE_JUMP = {"0.5x": 10.62, "1x": 11.18, "2x": 11.42, "3x": 11.23}  # 4x not measured yet
MINI_JUMP_FACTOR = 0.8

# Fastest cube fall seen (normal size). Not yet confirmed as a cap.
CUBE_MAX_FALL = -20.0

# Ground: top of the floor at y = 90 (player centre 105 at normal size).
GROUND_Y = 90.0

# Player hitbox (main, axis-aligned) side length by size.
PLAYER_SIZE = {1.0: 30.0, 0.6: 18.0}

# Gravity portals (with the 2.2 physics options on): the step moves with the old gravity, then the
# portal flips gravity and halves yVel (measured: 10.152 -> 5.076).
GRAVITY_FLIP_YVEL_FACTOR = 0.5
