"""Working memory for an incident.

A plain JSON-serializable dict plus an append-only turn log, with
checkpoint/restore so a crashed or retried workflow can pick up where
it left off. Nothing fancy - that's the point: the orchestrator
checkpoints between every step.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


class IncidentMemory:
    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self.state: dict = {}
        self.turns: list[dict] = []

    def update(self, key: str, value) -> None:
        self.state[key] = value

    def get(self, key: str, default=None):
        return self.state.get(key, default)

    def log_turn(self, agent: str, action: str, detail: str = "") -> None:
        self.turns.append({
            "ts": time.time(),
            "agent": agent,
            "action": action,
            "detail": detail,
        })

    def to_dict(self) -> dict:
        return {"incident_id": self.incident_id, "state": self.state, "turns": self.turns}

    def checkpoint(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str))
        return path

    @classmethod
    def restore(cls, path: str | Path) -> "IncidentMemory":
        data = json.loads(Path(path).read_text())
        mem = cls(data["incident_id"])
        mem.state = data.get("state", {})
        mem.turns = data.get("turns", [])
        return mem
