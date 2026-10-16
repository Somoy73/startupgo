"""File cache for raw pages and LLM outputs, so reruns are free and demos reproducible."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class JsonCache:
    def __init__(self, root: Path, *, read: bool = True):
        self.root = root
        self.read = read  # False = refresh: ignore cached entries but still write new ones

    def _path(self, namespace: str, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self.root / namespace / f"{digest}.json"

    def get(self, namespace: str, key: str) -> Any | None:
        if not self.read:
            return None
        path = self._path(namespace, key)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def put(self, namespace: str, key: str, value: Any) -> None:
        path = self._path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
