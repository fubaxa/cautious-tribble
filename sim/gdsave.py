"""Read level strings from the player's own GD save files.

CCLocalLevels.dat holds levels made in the editor; CCGameManager.dat holds downloaded levels.
Both are XOR 11 + URL-safe base64 + gzip around a plist-like XML.
"""
import base64
import os
import zlib

_XOR11 = bytes(c ^ 11 for c in range(256))


def save_dir() -> str:
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "GeometryDash")


def _unz(data: bytes) -> bytes:
    return zlib.decompress(data, 15 | 32)


def read_save(path: str) -> str:
    raw = open(path, "rb").read().translate(_XOR11).rstrip(b"\0")
    return _unz(base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))).decode("utf-8", "replace")


def decode_level_string(data: str) -> str:
    """A stored level string: gzip + base64, or already plain (starts with the start object's keys)."""
    data = data.strip()
    if data.startswith("kS") or data.startswith("kA"):
        return data
    return _unz(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("utf-8", "replace")


def _level_at(xml: str, i: int) -> str:
    j = xml.find("<k>k4</k><s>", i)
    nxt = xml.find("<k>k2</k>", i + 10)
    if j < 0 or (0 <= nxt < j):
        raise KeyError("the save has no level data for this level (open it in GD once to download it)")
    end = xml.find("</s>", j)
    return decode_level_string(xml[j + len("<k>k4</k><s>"):end])


def local_level(name: str, path: str | None = None) -> str:
    xml = read_save(path or os.path.join(save_dir(), "CCLocalLevels.dat"))
    i = xml.find(f"<k>k2</k><s>{name}</s>")
    if i < 0:
        raise KeyError(f"no created level named {name!r}")
    return _level_at(xml, i)


def saved_level(name_or_id: str, path: str | None = None) -> str:
    xml = read_save(path or os.path.join(save_dir(), "CCGameManager.dat"))
    if str(name_or_id).isdigit():
        # each downloaded level: <k>ID</k><d><k>kCEK</k><i>4</i><k>k1</k><i>ID</i> ... <k>k2</k><s>name</s>
        i = xml.find(f"<k>{name_or_id}</k><d><k>kCEK</k>")
    else:
        i = xml.find(f"<k>k2</k><s>{name_or_id}</s>")
    if i < 0:
        raise KeyError(f"no downloaded level {name_or_id!r}")
    return _level_at(xml, xml.find("<k>k2</k>", i))
