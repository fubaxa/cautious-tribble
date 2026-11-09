"""float32 helpers. GD stores positions as float32 and velocities as double; the simulator has to
round exactly where the game does, so every float32 value goes through f32()."""
import struct

_pack = struct.Struct("<f")


def f32(v: float) -> float:
    """Round a Python float (double) to the nearest float32, returned as a double."""
    return _pack.unpack(_pack.pack(v))[0]
