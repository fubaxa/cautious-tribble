"""Load a level's objects from the player's own CCLocalLevels.dat (levels they made or saved).

Level-string y is 90 lower than in-game y (the floor's top is y=90 in game, y=0 in the editor).
"""
import base64
import os
import zlib

from . import objects

EDITOR_Y_OFFSET = 90.0


def _unz(data: bytes) -> bytes:
    return zlib.decompress(data, 15 | 32)


def default_save_path() -> str:
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "GeometryDash", "CCLocalLevels.dat")


def level_string(name: str, path: str | None = None) -> str:
    raw = open(path or default_save_path(), "rb").read()
    xml = _unz(base64.urlsafe_b64decode(bytes(c ^ 11 for c in raw).rstrip(b"\0") + b"==")).decode("utf-8", "replace")
    i = xml.find(f"<k>k2</k><s>{name}</s>")
    if i < 0:
        raise KeyError(f"level {name!r} not found in {path or default_save_path()}")
    j = xml.find("<k>k4</k><s>", i)
    end = xml.find("</s>", j)
    data = xml[j + len("<k>k4</k><s>"):end]
    return _unz(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("utf-8", "replace")


class Level:
    def __init__(self, start: dict, objs: list):
        self.start = start
        self.objects = objs

    @classmethod
    def parse(cls, s: str) -> "Level":
        parts = s.split(";")
        head = parts[0].split(",")
        start = dict(zip(head[0::2], head[1::2]))
        objs = []
        for p in parts[1:]:
            if not p:
                continue
            a = p.split(",")
            d = dict(zip(a[0::2], a[1::2]))
            objs.append(objects.make(int(d.get("1", 0)), float(d.get("2", 0)),
                                     float(d.get("3", 0)) + EDITOR_Y_OFFSET, float(d.get("6", 0))))
        return cls(start, objs)

    @classmethod
    def load_local(cls, name: str, path: str | None = None) -> "Level":
        return cls.parse(level_string(name, path))
