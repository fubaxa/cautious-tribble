# Plan: Training an AI to Beat Geometry Dash Levels

## 1. Goal and scope

Build an agent that can complete Geometry Dash (GD) levels using only the
inputs a player has (press / release), and ideally **generalize** to levels it
has never seen.

Success targets, in increasing difficulty:

| Tier | Target |
|------|--------|
| T0 | Beat one specific easy level (memorization is fine) |
| T1 | Beat most official "Easy/Normal" levels seen in training |
| T2 | Beat **unseen** Easy/Normal levels zero-shot (≥ 50% completion rate) |
| T3 | Beat unseen Hard/Harder levels; handle all game modes (cube, ship, ball, UFO, wave, robot, spider, swing) |

Out of scope / ground rules: the bot is for research and offline play. Don't
submit bot runs to leaderboards or claim them as human completions, and don't
use online features in ways that break the game's terms of service.

### Target setup

- **Platform**: Windows
- **Game version**: Geometry Dash 2.2091
- **Mod loader**: Geode 6.0.0-alpha (SDK installed on the dev laptop)

Pin these versions for all experiments: memory layouts, object hitboxes and
physics constants are only guaranteed for this exact game version.

### Fidelity requirement: tick-exact

The goal is beating **real levels in the real game**, so the simulator must
reproduce the real game's per-tick player state exactly (same inputs → same
x, y, vy, mode, death tick). The real game is the ground truth from day one.

### Project boundaries

- **The simulator ("skeleton") is a separate, standalone project**: its own
  code, no dependency on the game or on any mod. Headless, optimized only for
  AI runs (no graphics, audio, decoration or UI).
- **DynamicButter** (`fubaxa/DynamicButters`, the user's Geode mod) is used
  **only as a measurement tool**: its findings (PLAN.md test results) and its
  logging (inputs with tick + position, per-step state, interactions, deaths).
  Nothing in this project changes how DynamicButter behaves; at most it gains
  extra log lines.

## 2. Key properties of the problem

- **Action space is tiny**: binary (held / not held) per physics tick. Timing
  is everything; a 1-tick error can mean death.
- **Mostly deterministic**: same inputs → same outcome (GD 2.2 runs physics at a
  fixed tick rate, 240 Hz by default). This makes search and savestates very
  powerful.
- **Sparse, harsh reward**: death resets the attempt. Progress (x-position) is
  a natural dense reward.
- **Long horizons**: a 90-second level ≈ 21,600 physics ticks.
- **Partial observability**: some triggers (move/alpha/pulse, invisible
  blocks, fake spikes) hide information; the agent may need memory.
- **Large mode/gimmick diversity**: gravity flips, speed portals, size
  portals, dual mode, orbs/pads, mirror portals.

## 3. Environment strategy (the most important decision)

Training against the real game at real-time speed is far too slow
(RL needs tens of millions of steps). Two tracks, used together:

### Track A — Custom simulator (primary training environment)
Write a headless, vectorized GD-style physics simulator in Python/NumPy (later
C++/Rust or JAX for speed):

1. Implement player physics per game mode (gravity, jump impulse, ship
   thrust, wave diagonal, etc.) and collision hitboxes.
2. Implement core objects: blocks, slabs, spikes, saws, orbs (yellow, pink,
   blue, green, dash, black), pads, portals (gravity, mode, speed, size,
   mirror, dual).
3. Load levels from **our own level format** (JSON list of objects). Add an
   importer for level strings the user owns / created themselves so personal
   test levels can be used.
4. Calibrate physics against the real game by recording player trajectories
   from it (Track B) and minimizing position error tick by tick.
5. Expose a Gymnasium API: `reset(level)`, `step(action)`, `save_state()`,
   `load_state()`; run 1000s of envs in parallel.

Use original graphics only (plain shapes are enough). The simulator exists for
training, not as a playable copy of the game.

### Track B — Ground truth from the real game (DynamicButter as a tool)
DynamicButter already provides, and has verified:

1. **Input logging**: every applied input with its tick, x, y and y-velocity
   (`log-inputs`), and `.gdr2` macros with per-input "Phys" snapshots.
2. **Frame-exact playback**: replays a macro with 0 drift (verified on
   Stereo Madness, 324 inputs), so the same input script can be run in the
   game and in the simulator.
3. **Exact per-step state** (`ExactState`): x, y, x/y velocity, size,
   speed, ground, gravity, gamemode, dash, jump buffer, ring jump, slope,
   held button, touched orbs; plus interaction hooks (orbs, pads, touch
   triggers, pickups) and death detection.

**Physics trace** (DynamicButter setting `physics-trace`, off by default,
logging only): one CSV per level session in `<save dir>/traces/`.
- Header: level ID/name, start settings, all legacy-physics flags (with
  their level-string keys), and the copies GD keeps on the player.
- `S` rows: player state at the end of every physics step (x, y, x/y
  velocity, rotation, size, speed, ground, gravity, mode, dash, jump
  buffer, ring jump, slope, held, dual, player hitbox).
- `I` inputs, `O` interactions (orb/pad/trigger/pickup with object ID,
  position and hitbox), `D` deaths (killing object + hitbox), `C`
  completion, `A` attempt starts.
- Floats with 9 and doubles with 17 significant digits, so values read
  back bit-exact. Nothing is written during scans or seeks.

Possible later addition: a hitbox dump per object ID (if the `O`/`D` rows
don't cover enough objects).

Findings from DynamicButter's testing that the simulator must reproduce:
- `m_currentProgress` counts half-steps (+2 per physics step, 240 steps/s);
  Click Between Steps must be off (it splits steps).
- Grouping of steps into rendered frames can change outcomes at the edge of
  a click window: the simulator (and AI) assume **1 step per frame at 240 FPS**.
- Speed portals trigger on **hitbox overlap** (incl. vertical), not the
  player's center.
- Grounded players usually keep a small non-zero y-velocity; the on-ground
  flag stays set on some steps where y changes.
- The first step after a spawn appears not to move the player.
- GD sends its own release 2 ticks after every respawn.
- Player 2 updates in the background outside dual mode (ignore it there).
- GD checkpoints round y / y-velocity in ship sections (not exact savestates),
  and some ball state is not captured yet.

### Physics constants
No reliable published values were found (only clones with their own tuned
numbers). Constants are therefore **measured from logs**:
- Run simple input scripts in purpose-built test levels (flat ground, single
  jump, held ship, each orb/pad/portal, each speed, mini/normal, flipped
  gravity), with DynamicButter logging every step.
- Fit gravity, jump impulse, terminal velocities, ship/wave/UFO/ball/robot/
  spider/swing parameters and per-speed x-velocity from the per-step deltas
  (values are float32; differences between steps give the constants
  directly).
- Each measured run becomes a golden trace and regression test.

### Calibration loop (golden traces)
- Record reference traces in the real game for each mechanic: flat jump,
  jump onto block, ship flight, each orb/pad/portal, speed changes, etc.
- Replay the same inputs in the simulator; find the **first diverging tick**;
  fix that; repeat. Every trace becomes an automated regression test.
- Fidelity details to watch: float32 arithmetic (match the game, not
  Python float64), order of update steps (move vs. collide), exact per-speed
  horizontal velocity, portal/orb activation timing.

### Converter fidelity
- Parse real level strings (compressed key/value object lists), keeping
  object ID, position, rotation, scale, flip and group IDs.
- Map object IDs → real hitboxes via the mod's dump.
- Support move/toggle/rotate triggers early: many real levels depend on them.
- Acceptance test: replay the same inputs on a level in the game and in the
  simulator; the death/completion tick must match.

### 3b. Legacy physics flags (2.2)
2.2 levels carry per-level compatibility toggles that switch between old and
new behavior. The simulator implements **both** behaviors for each flag, the
converter reads them from the level, and the AI receives them as input.

Candidates from the Geode bindings for 2.2091 (`LevelSettingsObject`, with
the level-string key in the level's start object):

| Field | Key | Likely affects |
|---|---|---|
| `m_fixGravityBug` | kA32 | gravity changes |
| `m_fixNegativeScale` | kA33 | hitboxes of negatively scaled objects |
| `m_fixRobotJump` | kA34 | robot jump |
| `m_fixRadiusCollision` | kA39 | round hitboxes (saws, etc.) |
| `m_enable22Changes` | kA40 | general 2.2 physics changes |
| `m_allowStaticRotate` | kA41 | rotation behavior |
| `m_reverseSync` | kA42 | reverse gameplay sync |
| `m_decreaseBoostSlide` | kA45 | boost/pad sliding |
| `m_enableImpulseFix` | kA48 | impulses (pads/orbs) |
| `m_enablePlayerSqueeze` | kA31 | player squeeze (maybe visual only) |
| `m_allowMultiRotation` | kA27 | rotation |
| `m_dynamicLevelHeight` | kA37 | level bounds |
| `m_sortGroups` | kA38 | group processing order |

The game copies some of these onto `PlayerObject` (`m_fixRobotJump`,
`m_enable22Changes`, `m_enableImpulseFix`), `GJBaseGameLayer` and
`PlayerCheckpoint`, i.e. they are read during physics.

**Defaults:** levels made before 2.2 have **all the new-physics options
off** (legacy behavior); new levels have them **on**. So a key missing from
an old level's start object means "off".

To do: confirm which of these the in-game level settings show (10–13) and
what each one changes. Each flag needs golden traces with it on and off.
Training levels must cover both settings so the AI doesn't assume one.
DynamicButter's physics trace writes each level's flags into the trace
header, so every trace records which physics it was measured under.

**Sim-to-real gap** is the main risk; mitigate with golden-trace calibration,
the converter acceptance test, and fine-tuning on the real game through the
bridge.

## 4. Observation design

Start with structured observations (fast, easy to learn), add pixels later
only if needed.

- **Player state**: y, vy, game mode (one-hot), gravity direction, speed
  multiplier, size (mini/normal), on-ground flag, dual state.
- **Level physics flags**: the level's legacy-physics toggles (Section 3b)
  as a fixed binary vector, constant for the whole level.
- **Object window**: the next N objects within ~X units ahead (and a little
  behind/above/below), each encoded as (type id, dx, dy, w, h, rotation,
  flags). Fed through an embedding + small Transformer / DeepSets encoder so
  the input is permutation-invariant and handles variable counts.
- **Alternative/rasterized**: a local occupancy grid (e.g. 64×32 cells,
  channels = solid / hazard / orb / pad / portal) processed by a small CNN.
  Easy to start with, and easy to compare against the object encoder.
- **Memory**: frame stacking (last 4 observations) or an LSTM/GRU core for
  hidden/visual triggers.

Action is taken every k ticks (action repeat k = 2–4 at 240 Hz) to shorten
the horizon, with k = 1 available for precise sections.

## 5. Learning approaches (phased)

### Phase 0 — Search baseline (no learning) → T0
Because the game is deterministic, beat a single level with
**savestate + search**: at each step try press/release, simulate ahead, prune
dead branches (beam search / DFS with backtracking from the last death).
This:
- proves the simulator works end to end,
- produces **perfect demonstration trajectories** for every training level for
  free (a huge dataset for Phase 1).

### Phase 1 — Behavior cloning (imitation) → T1
- Dataset: search-generated solutions + any human replays/macros of
  your own runs.
- Train the policy network (Section 4 encoder → press probability) with
  cross-entropy.
- Use DAgger-style correction: run the policy, at states where it drifts,
  query the search "expert" for the correct action, add to dataset, retrain.
  This fixes the compounding-error problem of pure cloning.

### Phase 2 — Reinforcement learning fine-tuning → T2
- Algorithm: **PPO** (stable, works well with massive vectorized envs);
  compare with a DQN-family method (e.g. Rainbow/R2D2-style with recurrence)
  given the discrete action space.
- Initialize from the BC policy.
- Reward:
  - `+Δx` progress per step (normalized by level length),
  - `−1` on death (episode ends),
  - `+large` bonus on completion,
  - small optional penalty for input spam (keeps inputs human-like).
- Exploration/efficiency tricks:
  - **Start from random checkpoints** along a level (reset into the middle
    using savestates/known-good trajectories) so the agent practices late
    sections without first beating early ones — the single most important
    trick for long levels.
  - Prioritize sections with high death rates (curriculum by failure).
- Curriculum over levels: cube-only → + orbs/pads → + ship → + other modes →
  speed changes → dual/mirror → Hard/Harder levels.

### Phase 3 — Generalization & robustness → T2/T3
- **Procedural level generator**: generate unlimited training levels from
  templates/grammars of gameplay chunks (jump patterns, ship corridors, wave
  tunnels, orb chains) with tunable difficulty. Validate each generated level
  is beatable using the Phase 0 search solver. This is what prevents
  overfitting to memorized levels.
- Hold out a test set of levels never seen in training (both generated and
  hand-made).
- Domain randomization: physics jitter, input latency of 0–2 ticks,
  object-position noise.
- Optional: a planning hybrid at test time (policy proposes, short-horizon
  lookahead in the simulator checks for death) — strong but only valid when
  you have a simulator model of the level.

### Phase 4 — Real game transfer
- The AI plays the level in the simulator and exports its run as a `.gdr2`
  macro; DynamicButter plays it back frame-exactly in the real game (physics
  correction **off**, so it tests the simulator honestly). No live link
  between the game and the AI is needed.
- Where the real run dies, DynamicButter's logs give the first diverging
  tick; fix the simulator there and re-run. Safe mode stays on, so these runs
  never save progress.

## 6. Model & infrastructure

- **Framework**: PyTorch (or JAX if the simulator is written in JAX for
  end-to-end GPU rollouts), Gymnasium API, CleanRL/Stable-Baselines3 or
  Sample Factory / EnvPool for high-throughput PPO.
- **Model size**: small — ~1–5M parameters (object-encoder Transformer with
  2–4 layers, 128-dim, + GRU + policy/value heads). Latency must fit within
  one physics tick (≈4 ms at 240 Hz) for real-time play.
- **Compute**: a single consumer GPU + 8–16 CPU cores is enough for T0–T2 if
  the simulator reaches ≥ 100k steps/sec.
- **Tracking**: Weights & Biases or TensorBoard; save replay videos of
  deaths for debugging.

## 7. Evaluation

- **Per level**: completion rate over 100 runs (with domain randomization),
  mean best % progress, attempts-to-first-completion (for in-training levels).
- **Generalization**: zero-shot completion rate on held-out level set,
  broken down by game mode and difficulty.
- **Sim-to-real**: completion rate of the same levels in sim vs. real game.
- **Death heatmaps**: where in each level the agent dies — directly guides the
  curriculum.

## 8. Milestones / timeline (rough)

| Week | Deliverable |
|------|-------------|
| 1 | Test levels + DynamicButter logging runs; trace file format; confirm the legacy flags |
| 2 | Measure cube + ship constants from logs; golden traces |
| 3–4 | Simulator cube + ship physics matching traces tick-exactly; Gym API; debug renderer |
| 5 | Level converter + death-tick acceptance test on real easy levels |
| 6 | Search solver beats a real easy level in sim, and the replayed solution beats it in the real game |
| 7 | Behavior-cloning policy (T1, cube/ship) |
| 8–9 | PPO fine-tuning with checkpoint resets; add ball/UFO/wave + triggers |
| 10–11 | Procedural generator + held-out benchmark; T2 evaluation in sim and real game |
| 12+ | Remaining modes (robot, spider, swing, dual), harder levels, T3 |

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Simulator physics doesn't match the real game | Tick-level calibration from recorded trajectories; fine-tune in real game |
| Long horizons make RL slow/unstable | Checkpoint resets, BC initialization, action repeat |
| Overfitting to memorized levels | Procedural generator, held-out test set, randomization |
| Hidden/visual-trick objects | Recurrent memory; mark as known limitation for T2 |
| A game update changes physics or object data | Pin GD 2.2091 / Geode 6.0.0-alpha; re-run golden traces after any update |
| Legacy physics flags behave differently than assumed | Golden traces with each flag on and off; flags as AI input |
| Pixel-based agent needed (no mod access) | Train a perception model to map frames → object list, reuse the same policy |

## 10. Immediate next steps

1. Define the trace file format (per-step player state) and input script
   format (GDR2 macros can serve as input scripts).
2. Confirm the 10 legacy physics options in the in-game level settings and
   map them to the fields in Section 3b.
3. Build small test levels (flat cube jumps, held ship) and log them with
   DynamicButter; extract per-step x, y, yVel.
4. Implement cube physics in the simulator (float32) and a trace-diff tool
   that reports the first diverging tick.
5. Set up repo structure:
   ```
   traces/     # golden traces + input scripts from the real game (via DynamicButter)
   sim/        # physics, objects, level loader, gym env
   converter/  # real level string -> simplified level
   solver/     # search-based expert
   agents/     # BC, PPO, models
   levels/     # converted levels + procedural generator
   eval/       # benchmarks, heatmaps, videos
   ```
