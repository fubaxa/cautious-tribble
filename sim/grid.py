"""Spatial index over x: which objects can touch a given x range. Objects are filed under every
cell their hitbox (rotated bounds, saw circle) spans, and re-filed when a trigger moves them."""
import math

CELL = 60.0


def extent(o):
    """The x range an object's hitbox can reach."""
    x, y, w, h = o.rect
    if o.rotation % 360:
        a = math.radians(o.rotation)
        bw = w * abs(math.cos(a)) + h * abs(math.sin(a))
        x, w = x + w / 2 - bw / 2, bw
    if o.radius:
        cx = o.x + o.ox
        lo, hi = min(x, cx - o.radius), max(x + w, cx + o.radius)
        x, w = lo, hi - lo
    return x, x + w


class Grid:
    def __init__(self, objects):
        self.objects = objects
        self.cells = {}
        self.where = {}
        for i in range(len(objects)):
            self._add(i)

    def _span(self, i):
        x0, x1 = extent(self.objects[i])
        return range(math.floor(x0 / CELL), math.floor(x1 / CELL) + 1)

    def _add(self, i):
        span = self._span(i)
        self.where[i] = span
        for c in span:
            self.cells.setdefault(c, set()).add(i)

    def moved(self, i):
        for c in self.where.get(i, ()):
            self.cells[c].discard(i)
        self._add(i)

    def near(self, x0: float, x1: float):
        """Indices of objects whose hitbox x range may overlap [x0, x1], in level order."""
        out = set()
        for c in range(math.floor(x0 / CELL), math.floor(x1 / CELL) + 1):
            cell = self.cells.get(c)
            if cell:
                out |= cell
        return sorted(out)
