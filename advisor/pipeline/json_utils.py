import json as _json
from typing import Any


def _json_dumps_stable(obj: Any) -> str:
    return _json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _json_loads(text: str) -> Any:
    return _json.loads(text)
