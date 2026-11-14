"""Saving and restoring a simulator cheaply, for searches.

The player and the triggers' small bookkeeping lists are copied; objects and trigger positions are
restored from the undo log (Sim.journal), so a saved point costs a few microseconds even on a level
with 20,000 objects. Restoring is only valid backwards: to a point saved before any point already
restored over (the log is cut at the restored point).
"""
from __future__ import annotations

import dataclasses


def enable(sim):
    if sim.journal is None:
        sim.journal = []
        sim.journal_base = 0   # log entries already dropped by trim()


def save(sim):
    p = sim.player
    t = sim.triggers
    pc = dataclasses.replace(p)
    pc.used = set(p.used)
    pc.snap_dbg = None
    return (sim.journal_base + len(sim.journal), sim.tick, pc, t.next, t.unsorted, t.last,
            [list(m) for m in t.active], [list(q) for q in t.queue], [list(lk) for lk in t.locks],
            [list(m) for m in t.starting])


def restore(sim, snap):
    n, tick, pc, nxt, unsorted, last, active, queue, locks, starting = snap
    j = sim.journal
    n -= sim.journal_base
    if n < 0:
        raise ValueError("this saved point was dropped by trim()")
    objs, grid, trig = sim.objects, sim.grid, sim.triggers
    while len(j) > n:
        e = j.pop()
        k = e[0]
        if k == 0:
            o = objs[e[1]]
            moved = o.x != e[2] or o.y != e[3]
            o.x, o.y, o.moved_step, o.enabled, o.uncertain = e[2], e[3], e[4], e[5], e[6]
            if moved:
                grid.moved(e[1])
        elif k == 1:
            e[1]["x"], e[1]["y"] = e[2], e[3]
        elif k == 2:
            trig.fired.discard(e[1])
        else:
            trig.by_x[e[1]:] = e[2]
    p = dataclasses.replace(pc)
    p.used = set(pc.used)
    sim.player = p
    sim.tick = tick
    trig.next, trig.unsorted, trig.last = nxt, unsorted, last
    trig.active = [list(m) for m in active]
    trig.queue = [list(q) for q in queue]
    trig.locks = [list(lk) for lk in locks]
    trig.starting = [list(m) for m in starting]


def trim(sim, snap):
    """Drop the log before `snap`: points saved earlier can't be restored any more."""
    cut = snap[0] - sim.journal_base
    if cut > 0:
        del sim.journal[:cut]
        sim.journal_base += cut


def key(sim):
    """Everything that decides the future (with the world given by the tick): two runs with the
    same key at the same tick play the same from then on."""
    p = sim.player
    return (sim.tick, p.x, p.y, p.y_vel, p.speed, p.size, p.mode, p.on_ground, p.upside_down,
            p.holding, p.buffered, p.hold_blocked, p.dashing, p.area_bottom, p.on_slope,
            p.slope_capped, p.last_block, p.last_diff if p.last_block is not None else 0.0,
            p.last_block_x if p.last_block is not None else 0.0, frozenset(p.used),
            len(sim.triggers.fired))
