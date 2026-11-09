"""Read DynamicButter physics traces (v5): one CSV per level session, see the file header."""
from dataclasses import dataclass, field

from .f32 import f32


@dataclass
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
    rect: tuple
    pos_x: float
    pos_y: float


@dataclass
class Attempt:
    number: int
    practice: bool
    steps: list = field(default_factory=list)
    inputs: list = field(default_factory=list)   # (tick, down, button, p2)
    events: list = field(default_factory=list)   # raw O/U/P/D/C rows
    death_tick: int | None = None
    complete_tick: int | None = None


@dataclass
class Trace:
    header: list
    attempts: list

    @property
    def version(self) -> int:
        for h in self.header:
            if "physics trace v" in h:
                return int(h.rsplit("v", 1)[1])
        return 0


def load(path: str) -> Trace:
    header, attempts = [], []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as f:
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
            elif k == "S" and len(r) >= 25:
                # float32 columns are printed with 9 digits: f32() gives back the exact value.
                cur.steps.append(Step(
                    tick=int(r[1]), step_in_frame=int(r[2]), x=f32(float(r[3])), y=f32(float(r[4])),
                    x_vel=float(r[5]), y_vel=float(r[6]), rotation=f32(float(r[7])), size=f32(float(r[8])),
                    speed=float(r[9]), on_ground=r[10] == "1", upside_down=r[11] == "1", mode=int(r[12]),
                    holding=r[17] == "1", jump_buffered=r[14] == "1", rect=tuple(f32(float(v)) for v in r[19:23]),
                    pos_x=f32(float(r[23])), pos_y=f32(float(r[24]))))
            elif k == "I":
                cur.inputs.append((int(r[1]), r[2] == "1", int(r[3]), r[4] == "1"))
            elif k in ("O", "U", "P", "D", "C"):
                cur.events.append(r)
                if k == "D" and r[-1] == "1" and cur.death_tick is None:
                    cur.death_tick = int(r[1])
                if k == "C":
                    cur.complete_tick = int(r[1])
    return Trace(header, attempts)
