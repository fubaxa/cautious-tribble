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
x, y, vy, mode, death tick). The real game is the ground truth from day one,
and the game mod (Section 3, Track B) is built **first**.

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

### Track B — Real-game mod (ground truth; built first)
A Geode mod (C++, Windows, GD 2.2091) with these features:

1. **Tick recorder**: logs player state at every physics tick (x, y, vy,
   mode, gravity, speed, size, on-ground, death/completion) to a trace file.
2. **Input replayer**: plays a fixed input script ("press @ tick 120,
   release @ tick 145") instead of a human, injected directly into the
   physics loop (not simulated keypresses).
3. **Hitbox/object dump**: exports the real hitbox (shape, size, offsets)
   for every object ID, so the simulator never guesses hitboxes.
4. **Bridge** (later): local socket exposing state + accepting per-tick
   inputs, with savestates and sped-up physics, for evaluation, for
   fine-tuning, and as a slow-but-exact fallback simulator.

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

**Sim-to-real gap** is the main risk; mitigate with golden-trace calibration,
the converter acceptance test, and fine-tuning on the real game through the
bridge.

## 4. Observation design

Start with structured observations (fast, easy to learn), add pixels later
only if needed.

- **Player state**: y, vy, game mode (one-hot), gravity direction, speed
  multiplier, size (mini/normal), on-ground flag, dual state.
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
- Run the trained policy through the Track B bridge on real levels.
- Fine-tune with a small amount of real-game RL / DAgger if the sim-to-real
  gap shows up (typically timing offsets in orbs and ship physics).

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
| 1 | Geode mod: tick recorder, input replayer, hitbox dump |
| 2 | Golden traces for cube + ship; trace file format |
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
| Real-game bridge breaks with game updates | Keep the bridge thin; pin the game/mod version for experiments |
| Pixel-based agent needed (no mod access) | Train a perception model to map frames → object list, reuse the same policy |

## 10. Immediate next steps

1. Define the trace file format (per-tick player state) and input script
   format; these are shared by the mod and the simulator.
2. Build the Geode mod's tick recorder (on the Windows dev laptop, against
   GD 2.2091 / Geode 6.0.0-alpha).
3. Add the input replayer and record the first golden traces (cube jumps on
   flat ground and onto blocks).
4. Implement cube physics in the simulator (float32) and a trace-diff tool
   that reports the first diverging tick.
5. Set up repo structure:
   ```
   mod/        # Geode mod (C++): recorder, replayer, hitbox dump, bridge
   traces/     # golden traces + input scripts from the real game
   sim/        # physics, objects, level loader, gym env
   converter/  # real level string -> simplified level
   solver/     # search-based expert
   agents/     # BC, PPO, models
   levels/     # converted levels + procedural generator
   eval/       # benchmarks, heatmaps, videos
   ```
