"""GDR2 macro files, read and written the way DynamicButter does (src/macro/Gdr2.cpp).

Layout (varint = LEB128; float/double = raw IEEE bytes, big-endian; bool = varint 0/1):
  "GDR" | version=2 | inputTag | author | description | duration (float, s)
  gameVersion | framerate (double) | seed | coins | ldm | platformer
  botName | botVersion | levelID | levelName
  replayExtension: varint size + bytes (DynamicButter's when botName == "DynamicButter")
  deaths: count + frames
  inputs: total, p1Count, records: varint (frameDelta << 1 | down) + "Phys" block

Ticks (m_currentProgress) count half-steps; file frames count physics steps: frame = tick / 2.
"""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field

BOT_NAME = "DynamicButter"
EXT_VERSION = 5


@dataclass
class Window:
    """Dynamic window: steps the input can move earlier / later and the run is still the same."""
    early: int = 0
    late: int = 0
    flags: int = 0
    early_exact: int = 0
    late_exact: int = 0


@dataclass
class Input:
    tick: int                 # GD tick at which the input is applied (even)
    down: bool
    player2: bool = False
    phys: tuple = (0.0, 0.0, 0.0, 0.0, 0.0)   # x, y, rotation, xVel, yVel before the input
    window: Window | None = None


@dataclass
class Macro:
    level_id: int = 0
    level_name: str = ""
    framerate: float = 240.0
    end_tick: int = 0
    author: str = ""
    bot_name: str = BOT_NAME
    recorded_at: int = 0
    inputs: list[Input] = field(default_factory=list)
    start_ticks: list[int] = field(default_factory=list)
    path: list[tuple[int, float]] = field(default_factory=list)   # (tick, x) corner points


class _W:
    def __init__(self):
        self.b = bytearray()

    def varint(self, v):
        v = int(v)
        while True:
            c = v & 0x7F
            v >>= 7
            self.b.append(c | (0x80 if v else 0))
            if not v:
                return

    def str(self, s):
        e = s.encode("utf-8")
        self.varint(len(e))
        self.b += e

    def f32(self, v):
        self.b += struct.pack(">f", v)

    def f64(self, v):
        self.b += struct.pack(">d", v)

    def block(self, other):
        self.varint(len(other.b))
        self.b += other.b


class _R:
    def __init__(self, data):
        self.d, self.p = data, 0

    def varint(self):
        v, s = 0, 0
        while True:
            c = self.d[self.p]
            self.p += 1
            v |= (c & 0x7F) << s
            s += 7
            if not c & 0x80:
                return v

    def str(self):
        n = self.varint()
        s = self.d[self.p:self.p + n].decode("utf-8", "replace")
        self.p += n
        return s

    def f32(self):
        v = struct.unpack(">f", self.d[self.p:self.p + 4])[0]
        self.p += 4
        return v

    def f64(self):
        v = struct.unpack(">d", self.d[self.p:self.p + 8])[0]
        self.p += 8
        return v

    def block(self):
        n = self.varint()
        r = _R(self.d[self.p:self.p + n])
        self.p += n
        return r


def write(m: Macro) -> bytes:
    w = _W()
    w.b += b"GDR"
    w.varint(2)
    w.str("Phys")
    w.str(m.author)
    w.str("")
    w.f32(m.end_tick / (2.0 * m.framerate))
    w.varint(22091)
    w.f64(m.framerate)
    w.varint(0)   # seed
    w.varint(0)   # coins
    w.varint(0)   # ldm
    w.varint(0)   # platformer
    w.str(BOT_NAME)
    w.varint(1)
    w.varint(m.level_id & 0xFFFFFFFF)
    w.str(m.level_name)
    ext = _W()
    ext.varint(EXT_VERSION)
    ext.varint(m.end_tick)
    ext.varint(m.recorded_at or int(time.time()))
    ext.varint(len(m.start_ticks))
    prev = 0
    for t in m.start_ticks:
        ext.varint(t - prev)
        prev = t
    ext.varint(len(m.path))
    prev = 0
    for t, x in m.path:
        ext.varint(t - prev)
        ext.f32(x)
        prev = t
    wins = [i for i in m.inputs if i.window is not None]
    ext.varint(len(wins))
    prev = 0
    for i in wins:
        ext.varint(i.tick - prev)
        ext.varint((2 if i.player2 else 0) | (1 if i.down else 0))
        for v in (i.window.early, i.window.late, i.window.flags, i.window.early_exact, i.window.late_exact):
            ext.varint(min(max(int(v), 0), 255))
        prev = i.tick
    w.block(ext)
    w.varint(0)   # deaths
    w.varint(len(m.inputs))
    w.varint(sum(1 for i in m.inputs if not i.player2))
    for p2 in (False, True):
        prev = 0
        for i in m.inputs:
            if i.player2 != p2:
                continue
            f = i.tick // 2
            w.varint(((f - prev) << 1) | (1 if i.down else 0))
            prev = f
            ph = _W()
            ph.f32(i.phys[0]); ph.f32(i.phys[1]); ph.f32(i.phys[2]); ph.f64(i.phys[3]); ph.f64(i.phys[4])
            w.block(ph)
    return bytes(w.b)


def read(data: bytes) -> Macro:
    r = _R(data)
    if r.d[:3] != b"GDR":
        raise ValueError("not a GDR file")
    r.p = 3
    if r.varint() != 2:
        raise ValueError("unsupported GDR version")
    tag = r.str()
    m = Macro()
    m.author = r.str()
    r.str()
    r.f32()
    r.varint()
    m.framerate = r.f64()
    r.varint(); r.varint(); r.varint()
    platformer = r.varint() != 0
    m.bot_name = r.str()
    r.varint()
    m.level_id = r.varint()
    m.level_name = r.str()
    ext = r.block()
    wins = []
    if m.bot_name == BOT_NAME:
        v = ext.varint()
        m.end_tick = ext.varint()
        m.recorded_at = ext.varint()
        if v >= 2:
            t = 0
            for _ in range(ext.varint()):
                t += ext.varint()
                m.start_ticks.append(t)
        if v >= 3:
            t = 0
            for _ in range(ext.varint()):
                t += ext.varint()
                m.path.append((t, ext.f32()))
        if v >= 4:
            t = 0
            for _ in range(ext.varint()):
                t += ext.varint()
                bits = ext.varint()
                win = Window(ext.varint(), ext.varint(), ext.varint())
                if v >= 5:
                    win.early_exact, win.late_exact = ext.varint(), ext.varint()
                wins.append((t, bits, win))
    for _ in range(r.varint()):
        r.varint()
    total, p1 = r.varint(), r.varint()
    scale = 2.0 * 240.0 / (m.framerate or 240.0)
    frame = 0
    for k in range(total):
        if k == p1:
            frame = 0
        packed = r.varint()
        frame += packed >> (3 if platformer else 1)
        i = Input(round(frame * scale), bool(packed & 1), k >= p1)
        if tag:
            e = r.block()
            if tag == "Phys":
                i.phys = (e.f32(), e.f32(), e.f32(), e.f64(), e.f64())
        if not platformer or (packed >> 1) & 3 == 1:
            m.inputs.append(i)
    m.inputs.sort(key=lambda i: i.tick)
    for t, bits, win in wins:
        for i in m.inputs:
            if i.tick == t and i.player2 == bool(bits & 2) and i.down == bool(bits & 1):
                i.window = win
                break
    return m


def load(path: str) -> Macro:
    with open(path, "rb") as f:
        return read(f.read())


def save(path: str, m: Macro) -> None:
    with open(path, "wb") as f:
        f.write(write(m))
