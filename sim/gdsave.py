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


def write_save(path: str, xml: str) -> None:
    """The inverse of read_save: gzip + URL-safe base64 + XOR 11."""
    import gzip
    data = base64.urlsafe_b64encode(gzip.compress(xml.encode("utf-8"))).translate(_XOR11)
    with open(path, "wb") as f:
        f.write(data)


def encode_level_string(level: str) -> str:
    import gzip
    return base64.urlsafe_b64encode(gzip.compress(level.encode("utf-8"))).decode("ascii")


def add_local_level(name: str, level: str, path: str | None = None, creator: str = "") -> str:
    """Put a level at the top of the player's created levels (k_0; the others move down one).
    A level with the same name is replaced. GD must be closed: it rewrites the file on exit.
    Returns the path of the backup made first."""
    import re
    import shutil
    import time
    path = path or os.path.join(save_dir(), "CCLocalLevels.dat")
    backup = f"{path}.backup-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copyfile(path, backup)
    xml = read_save(path)
    head = "<k>LLM_01</k><d><k>_isArr</k><t />"
    i = xml.find(head)
    if i < 0:
        raise ValueError("unexpected save layout (no LLM_01 list)")
    # drop an older copy with the same name
    m = re.search(r"<k>k_\d+</k><d><k>kCEK</k>(?:(?!<k>k_\d+</k><d><k>kCEK</k>).)*?<k>k2</k><s>"
                  + re.escape(name) + r"</s>.*?(?=<k>k_\d+</k><d><k>kCEK</k>|</d><k>LLM_02</k>)", xml, re.S)
    if m:
        xml = xml[:m.start()] + xml[m.end():]
    n = [0]

    def renum(_):
        n[0] += 1
        return f"<k>k_{n[0]}</k><d><k>kCEK</k>"
    body = re.sub(r"<k>k_\d+</k><d><k>kCEK</k>", renum, xml[i + len(head):])
    count = level.count(";") - 1
    entry = (f"<k>k_0</k><d><k>kCEK</k><i>4</i><k>k2</k><s>{name}</s><k>k4</k><s>{encode_level_string(level)}</s>"
             f"<k>k5</k><s>{creator}</s><k>k13</k><t /><k>k21</k><i>2</i><k>k16</k><i>1</i>"
             f"<k>k50</k><i>51</i><k>k47</k><t /><k>k48</k><i>{count}</i></d>")
    write_save(path, xml[:i + len(head)] + entry + body)
    return backup
