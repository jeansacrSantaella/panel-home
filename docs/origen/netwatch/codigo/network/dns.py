"""Consulta DNS tipo A construida a mano y enviada por UDP."""
from __future__ import annotations

import random
import socket
import struct
import time
from typing import Optional, Tuple


def build_query(qid: int, name: str) -> bytes:
    packet = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)  # recursión activada, 1 pregunta
    packet += b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"
    return packet + struct.pack(">HH", 1, 1)  # tipo A, clase IN


def is_valid_answer(data: bytes, qid: int) -> bool:
    if len(data) < 8:
        return False
    rid, flags, _, answers = struct.unpack(">HHHH", data[:8])
    return rid == qid and (flags & 0xF) == 0 and answers > 0


def dns_query(server: str, name: str = "example.com", timeout: float = 2.0) -> Tuple[bool, Optional[float]]:
    qid = random.randint(0, 65535)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.sendto(build_query(qid, name), (server, 53))
        data, _ = s.recvfrom(512)
    except Exception:
        return False, None
    finally:
        s.close()
    ok = is_valid_answer(data, qid)
    return ok, (time.time() - t0) * 1000 if ok else None
