"""Tools the agents can call. Each one is a plain class over local data.

In production these would hit your logging, metrics, and docs backends.
Here they read the bundled dataset so everything runs offline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


class ToolError(Exception):
    pass


_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "by", "as", "at", "from", "that",
    "this", "it", "its", "into", "over", "after", "before", "per", "via",
    "has", "have", "had", "will", "would", "can", "could", "should",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower())
            if len(t) > 2 and t not in _STOPWORDS}


class LogSearch:
    """Keyword search over service logs."""

    def __init__(self, incidents: list[dict]):
        self._by_service: dict[str, list[str]] = {}
        for inc in incidents:
            self._by_service.setdefault(inc["service"], []).extend(inc.get("logs", []))

    def search(self, service: str, keywords: list[str], limit: int = 10) -> list[str]:
        logs = self._by_service.get(service)
        if logs is None:
            raise ToolError(f"no logs for service {service!r}")
        kw = [k.lower() for k in keywords]
        ranked = []
        for line in logs:
            low = line.lower()
            score = sum(1 for k in kw if k in low)
            if score:
                ranked.append((score, line))
        ranked.sort(key=lambda t: t[0], reverse=True)
        return [line for _, line in ranked[:limit]]


class MetricsLookup:
    """Point-in-time metrics snapshot per service."""

    def __init__(self, incidents: list[dict]):
        self._metrics = {inc["service"]: inc.get("metrics", {}) for inc in incidents}

    def get(self, service: str) -> dict:
        if service not in self._metrics:
            raise ToolError(f"no metrics for service {service!r}")
        return dict(self._metrics[service])


class RunbookRetrieval:
    """Naive keyword retrieval over markdown runbooks (TF overlap ranking)."""

    def __init__(self, runbook_dir: str | Path):
        self._docs: list[tuple[str, str, list[str]]] = []  # (name, full_text, steps)
        for path in sorted(Path(runbook_dir).glob("*.md")):
            text = path.read_text()
            steps = [l.strip()[3:].strip() for l in text.splitlines()
                     if l.strip().startswith("- [ ]") or l.strip().startswith("1.")]
            # also accept plain "- " steps under a ## Steps heading
            if not steps:
                in_steps = False
                for line in text.splitlines():
                    if line.strip().lower().startswith("## steps"):
                        in_steps = True
                        continue
                    if in_steps and line.strip().startswith("#"):
                        break
                    if in_steps and line.strip().startswith("- "):
                        steps.append(line.strip()[2:].strip())
            self._docs.append((path.stem, text, steps))
        if not self._docs:
            raise ToolError(f"no runbooks found in {runbook_dir}")

    def retrieve(self, query: str, top_k: int = 2, min_score: int = 4) -> list[dict]:
        qtok = _tokens(query)
        scored = []
        for name, text, steps in self._docs:
            overlap = len(qtok & _tokens(text))
            if overlap >= min_score:
                scored.append((overlap, name, text, steps))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [{"name": n, "steps": s, "score": sc}
                for sc, n, _, s in scored[:top_k]]

    def get(self, name: str) -> dict:
        for n, text, steps in self._docs:
            if n == name:
                return {"name": n, "steps": steps, "text": text}
        raise ToolError(f"runbook {name!r} not found")


class AlertEnrichment:
    """Joins an alert with service ownership and recent change data."""

    def __init__(self, incidents: list[dict]):
        self._meta = {inc["service"]: {
            "owner": inc.get("owner", "unknown"),
            "recent_deploy": bool(inc.get("recent_deploy", False)),
            "dashboard": inc.get("dashboard", ""),
        } for inc in incidents}

    def enrich(self, service: str, alert: str) -> dict:
        meta = self._meta.get(service)
        if meta is None:
            raise ToolError(f"unknown service {service!r}")
        return {"service": service, "alert": alert, **meta}


def load_incidents(path: str | Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)
