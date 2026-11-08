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

### Track B — Real-game bridge (evaluation + calibration)
- Use a client mod (e.g. via the Geode modding SDK) that exposes, over a local
  socket: player state (x, y, velocity, mode, gravity, speed), nearby object
  list, death/completion events, and accepts press/release inputs per tick.
- Support practice-mode checkpoints / savestates and speedhack for faster
  evaluation runs.
- Fallback (no mod): screen capture + simulated key presses. Much slower and
  noisier; only for final demos.

**Sim-to-real gap** is the main risk; mitigate with calibration (A.4),
domain randomization (small physics/timing jitter), and fine-tuning on the
real game through the bridge.

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
| 1–2 | Cube + ship physics simulator, level JSON format, Gym API, rendering for debugging |
| 3 | Search solver beats simple levels (T0); demonstration generation |
| 4 | Behavior-cloning policy beats training levels (T1, cube/ship) |
| 5–6 | PPO fine-tuning with checkpoint resets; add ball/UFO/wave |
| 7–8 | Procedural level generator + held-out benchmark; T2 evaluation |
| 9–10 | Real-game bridge mod, physics calibration, sim-to-real evaluation |
| 11+ | Remaining modes (robot, spider, swing, dual), harder levels, T3 |

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

1. Decide on the simulator language (start Python + NumPy, profile, port hot
   loop if < 50k steps/sec).
2. Define the level JSON schema and hand-build 5 tiny cube test levels.
3. Implement cube physics + spikes/blocks collision and a debug renderer.
4. Implement the search solver and verify it beats all 5 test levels.
5. Set up repo structure:
   ```
   sim/        # physics, objects, level loader, gym env
   solver/     # search-based expert
   agents/     # BC, PPO, models
   levels/     # json levels + procedural generator
   bridge/     # real-game mod + python client
   eval/       # benchmarks, heatmaps, videos
   ```
