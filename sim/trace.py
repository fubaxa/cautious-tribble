"""Read DynamicButter physics traces (v5): one CSV per level session, see the file header."""
from dataclasses import dataclass, field

from .f32 import f32


@dataclass(slots=True)   # millions of rows per big trace: no per-row __dict__ (about half the memory)
class Step:
    tick: int
    step_in_frame: int
    x: float
    y: float
    x_vel: float
    y_vel: float
    rotation: float
    size: float
    speed: float
    on_ground: bool
    upside_down: bool
    mode: int
    holding: bool
    jump_buffered: bool
    on_slope: bool
    rect: tuple
    pos_x: float
    pos_y: float
    dual: bool = False
    p2: object = None      # player 2's row for this step (v6 traces, while dual)


@dataclass
class Attempt:
    number: int
    practice: bool
    steps: list = field(default_factory=list)
    steps2: list = field(default_factory=list)   # player 2 while dual mode is on (v6 traces)
    inputs: list = field(default_factory=list)   # (tick, down, button, p2)
    input_pos: list = field(default_factory=list)   # (posX, posY, from a macro) right before each input (v5+), or None
    events: list = field(default_factory=list)   # raw O/U/P/D/C rows
    death_tick: int | None = None
    complete_tick: int | None = None


@dataclass
class Trace:
    header: list
    attempts: list
    path: str = ""

    @property
    def layout(self) -> str | None:
        """The level file DynamicButter saved with this trace (the layout it was played on), or None
        for traces recorded before it did that."""
        import os
        for h in self.header:
            if h.startswith("# layout "):
                return os.path.join(os.path.dirname(self.path), h[len("# layout "):].strip())
        return None

    @property
    def version(self) -> int:
        for h in self.header:
            if "physics trace v" in h:
                return int(h.rsplit("v", 1)[1])
        return 0


def _open(path: str):
    """A trace as text: `.csv`, or compressed `.csv.xz` (also found when the plain `.csv` is asked
    for but only the compressed file is there)."""
    import lzma
    import os
    if not path.endswith(".xz") and not os.path.exists(path) and os.path.exists(path + ".xz"):
        path += ".xz"
    if path.endswith(".xz"):
        return lzma.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, encoding="utf-8", errors="replace")


def load(path: str) -> Trace:
    header, attempts = [], []
    cur = None
    with _open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#"):
                header.append(line)
                continue
            r = line.split(",")
            k = r[0]
            if k == "A":
                cur = Attempt(int(r[1]), r[3] == "1")
                attempts.append(cur)
            elif cur is None:
                continue
            elif k in ("S", "S2") and len(r) >= 23:
                # float32 columns are printed with 9 digits: f32() gives back the exact value.
                row = (Step(
                    tick=int(r[1]), step_in_frame=int(r[2]), x=f32(float(r[3])), y=f32(float(r[4])),
                    x_vel=float(r[5]), y_vel=float(r[6]), rotation=f32(float(r[7])), size=f32(float(r[8])),
                    speed=float(r[9]), on_ground=r[10] == "1", upside_down=r[11] == "1", mode=int(r[12]),
                    holding=r[17] == "1", jump_buffered=r[14] == "1", on_slope=r[16] == "1", rect=tuple(f32(float(v)) for v in r[19:23]),
                    # v1-v4 have no posX/posY: use the hitbox centre (the same thing)
                    pos_x=f32(float(r[23]) if len(r) >= 25 else float(r[19]) + float(r[21]) / 2),
                    pos_y=f32(float(r[24]) if len(r) >= 25 else float(r[20]) + float(r[22]) / 2),
                    dual=r[18] == "1"))
                if k == "S":
                    cur.steps.append(row)
                else:
                    cur.steps2.append(row)
                    if cur.steps:
                        cur.steps[-1].p2 = row
            elif k == "I":
                cur.inputs.append((int(r[1]), r[2] == "1", int(r[3]), r[4] == "1"))
                cur.input_pos.append((float(r[6]), float(r[7]), r[5] == "1") if len(r) > 7 and r[6] else None)
            elif k in ("O", "U", "P", "D", "C"):
                cur.events.append(r)
                # v6 adds the player (1 or 2) after the dead flag
                if k == "D" and (r[9] if len(r) > 10 else r[-1]) == "1" and cur.death_tick is None:
                    cur.death_tick = int(r[1])
                if k == "C":
                    cur.complete_tick = int(r[1])
    return Trace(header, attempts, path)
