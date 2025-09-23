from __future__ import annotations
import structlog
from typing import Any, Dict, Mapping

__all__ = [
    "to_redis",
]

log = structlog.get_logger()


def to_redis(d: Mapping[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in d.items():
        if isinstance(v, bool):
            out[k] = "1" if v else "0"
        elif v is None:
            out[k] = ""
        else:
            out[k] = str(v)
    return out
