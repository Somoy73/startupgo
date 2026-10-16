"""Writes startup entries as JSON files plus an index."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .record import StartupRecord


class RecordStore:
    def __init__(self, root: Path):
        self.root = root
        self.entries = root / "startups"
        self.index_path = root / "index.json"

    def save(self, record: StartupRecord, *, weights: dict[str, float]) -> tuple[Path, dict[str, Any]]:
        """Write the entry (scores recomputed with ``weights``); returns its path and content."""
        data = record.to_dict(weights=weights)
        self.entries.mkdir(parents=True, exist_ok=True)
        path = self.entries / f"{record.id}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._update_index(data, path)
        return path, data

    def load(self, path: Path) -> StartupRecord:
        return StartupRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _update_index(self, data: dict[str, Any], path: Path) -> None:
        try:
            index = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            index = []
        scores = data["scores"]
        entry = {
            "id": data["id"],
            "name": data["name"],
            "website": data["website"],
            "file": str(path.relative_to(self.root)),
            "generated_at": data["generated_at"],
            "trl": scores["trl"]["level"],
            "brl": scores["brl"]["level"],
            "ocean_impact_readiness": scores["ocean_impact_readiness"]["level"],
            "investment_score": scores["investment_score"],
            "overall_confidence": scores["overall_confidence"],
        }
        index = sorted([e for e in index if e.get("id") != entry["id"]] + [entry], key=lambda e: e["name"].casefold())
        self.index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
