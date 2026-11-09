"""A level as the simulator sees it: start settings plus gameplay objects (the converter's output)."""
import json

from . import gdsave, objects


class Level:
    def __init__(self, settings: dict, objs: list, triggers: list | None = None):
        self.settings = settings
        self.objects = objs
        self.triggers = triggers or []

    @classmethod
    def from_dict(cls, d: dict) -> "Level":
        objs = []
        for r in d["objects"]:
            objs.append(objects.Obj(
                id=r["id"], x=r["x"], y=r["y"], rotation=r.get("rot", 0.0), kind=r["kind"],
                w=r["w"], h=r["h"], extra=r.get("type"), flip_x=r.get("flip_x", False),
                flip_y=r.get("flip_y", False), groups=r.get("groups", []), multi=r.get("multi", False),
                radius=r.get("radius", 0.0), ox=r.get("ox", 0.0), oy=r.get("oy", 0.0)))
        return cls(d["settings"], objs, d.get("triggers", []))

    @classmethod
    def load(cls, path: str) -> "Level":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def load_local(cls, name: str, path: str | None = None) -> "Level":
        from converter.convert import convert
        return cls.from_dict(convert(gdsave.local_level(name, path), name, "local"))
