"""LLM provider interface.

The agents reason through a provider. Two implementations ship:

- MockProvider: deterministic, rule-based, works offline. This is what the
  tests and the eval harness use, so results are reproducible.
- OpenAICompatibleProvider: talks to any OpenAI-compatible chat API
  (OpenAI, Bedrock via proxy, Ollama, vLLM...). Set OPENAI_API_KEY and
  optionally OPENAI_BASE_URL / INCIDENT_AGENT_MODEL.

The agents don't care which one is plugged in.
"""
from __future__ import annotations

import json
import os
import urllib.request


class ProviderError(Exception):
    pass


class Provider:
    name = "base"

    def reason(self, task: str, evidence: dict) -> dict:
        """Return a structured reasoning result for one of the agent tasks:
        'triage', 'diagnose', 'plan'."""
        raise NotImplementedError

    def narrate(self, report: dict) -> str:
        """Turn a finished incident report into a short human-readable note."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Deterministic offline brain. Same interface as a real model, zero network.
# ---------------------------------------------------------------------------
class MockProvider(Provider):
    name = "mock"

    def reason(self, task: str, evidence: dict) -> dict:
        if task == "triage":
            return self._triage(evidence)
        if task == "diagnose":
            return self._diagnose(evidence)
        if task == "plan":
            return self._plan(evidence)
        raise ProviderError(f"unknown task: {task}")

    # -- triage ----------------------------------------------------------
    def _triage(self, ev: dict) -> dict:
        m = ev.get("metrics", {}) or {}
        err = float(m.get("error_rate_pct", 0) or 0)
        restarts = int(m.get("restarts_15m", 0) or 0)
        if err >= 20 or restarts >= 30:
            severity = "P1"
        elif err >= 5 or restarts >= 10:
            severity = "P2"
        elif err > 0 or restarts > 0:
            severity = "P3"
        else:
            severity = "P4"
        blob = " ".join([ev.get("alert", ""), *ev.get("logs", [])]).lower()
        category = "unknown"
        for name, keywords in _CATEGORY_PATTERNS:
            if any(k in blob for k in keywords):
                category = name
                break
        return {
            "severity": severity,
            "category": category,
            "confidence": 0.9 if category != "unknown" else 0.5,
            "rationale": f"error_rate={err}%, restarts_15m={restarts} -> {severity}; signals point at {category}",
        }

    # -- diagnose ---------------------------------------------------------
    def _diagnose(self, ev: dict) -> dict:
        blob = " ".join([ev.get("alert", ""), *ev.get("logs", [])]).lower()
        hits = []
        for name, keywords, cause in _DIAGNOSIS_PATTERNS:
            matched = [k for k in keywords if k in blob]
            if matched:
                hits.append((name, cause, matched))
        # a 5xx spike only means "bad deploy" if a deploy actually happened
        if not hits:
            return {
                "root_cause": "unknown - needs human investigation",
                "confidence": 0.4,
                "evidence": ev.get("logs", [])[:3],
                "contributing_factors": [],
            }
        # prefer the hit with the most matched keywords; break ties by order
        hits.sort(key=lambda h: len(h[2]), reverse=True)
        name, cause, matched = hits[0]
        if name == "Http5xx":
            if ev.get("recent_deploy"):
                cause = "Deploy regression: 5xx spike correlated with recent deploy"
            else:
                cause = "Upstream dependency returning 5xx (no recent deploy on this service)"
        return {
            "root_cause": cause,
            "confidence": 0.95 if len(matched) >= 2 else 0.8,
            "evidence": [l for l in ev.get("logs", []) if any(k in l.lower() for k in matched)][:4],
            "contributing_factors": [f"matched signals: {', '.join(matched)}"],
        }

    # -- plan -------------------------------------------------------------
    def _plan(self, ev: dict) -> dict:
        steps = list(ev.get("runbook_steps", []) or [])
        if not steps:
            steps = ["Gather more evidence and escalate to the service owner."]
        joined = " ".join(steps).lower()
        high_markers = ["failover", "drop", "delete production", "restart database", "promote replica"]
        med_markers = ["restart", "rollback", "scale", "renew", "increase", "drain", "cordon"]
        if any(m in joined for m in high_markers):
            risk = "high"
        elif any(m in joined for m in med_markers):
            risk = "medium"
        else:
            risk = "low"
        return {
            "steps": steps,
            "risk": risk,
            "requires_approval": risk == "high",
            "rollback_plan": "Revert to the previous known-good state (rollback deploy / restore config / fail back).",
        }

    def narrate(self, report: dict) -> str:
        d = report.get("diagnosis", {})
        p = report.get("plan", {})
        return (
            f"{report.get('service')} triaged as {report.get('severity')} "
            f"({report.get('category')}). Likely root cause: {d.get('root_cause')} "
            f"(confidence {d.get('confidence')}). Plan risk: {p.get('risk')}"
            + (" - waiting on human approval before acting." if p.get("requires_approval") else ".")
        )


_CATEGORY_PATTERNS = [
    ("resource-exhaustion", ["oomkilled", "out of memory", "cpu throttling", "throttled"]),
    ("deploy-regression", ["5xx", "http 500", "deploy", "rollout", "release"]),
    ("storage", ["no space left", "disk pressure", "evicted"]),
    ("network", ["no such host", "dns", "name resolution", "timeout", "connection refused"]),
    ("security", ["certificate", "tls", "x509"]),
    ("data-tier", ["too many connections", "pool exhausted", "replica lag"]),
    ("client-error", ["400", "bad request", "422"]),
    ("throughput", ["queue lag", "consumer lag", "backlog"]),
]

_DIAGNOSIS_PATTERNS = [
    ("OOMKilled", ["oomkilled", "memory cgroup out of memory", "out of memory"],
     "Container OOMKilled: memory limit too low for the workload"),
    ("DiskPressure", ["no space left on device", "disk pressure"],
     "Disk pressure: volume full, writes failing"),
    ("CertExpiry", ["certificate has expired", "x509: certificate has expired"],
     "TLS certificate expired on the serving endpoint"),
    ("DNSFailure", ["no such host", "name resolution", "dns lookup failed"],
     "DNS resolution failure for an upstream dependency"),
    ("DBConnExhaustion", ["too many connections", "pool exhausted", "connection refused"],
     "Database connection exhaustion: pool saturated"),
    ("ConfigInvalid", ["invalid configuration", "missing key", "config mismatch"],
     "Invalid configuration: required config key missing or malformed"),
    ("CPUThrottling", ["cpu throttling", "throttled"],
     "CPU throttling: CPU limit too low for current load"),
    ("CacheEvictions", ["evicted", "cache miss storm"],
     "Cache memory pressure: mass evictions degrading hit rate"),
    ("QueueLag", ["queue lag", "consumer lag", "backlog growing"],
     "Worker throughput below arrival rate: queue backlog growing"),
    ("UpstreamTimeout", ["upstream timed out", "gateway timeout", "deadline exceeded"],
     "Upstream dependency timeout: downstream calls exceeding deadline"),
    ("Http5xx", ["http 500", "5xx", "internal server error"],
     "Elevated 5xx rate on the service"),
    ("ClientErrors", ["http 400", "bad request", "422"],
     "Client-side bad requests: not a server fault"),
]


# ---------------------------------------------------------------------------
# Real model, OpenAI-compatible API. Dependency-free (urllib only).
# ---------------------------------------------------------------------------
class OpenAICompatibleProvider(Provider):
    name = "openai-compatible"

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL",
                         "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.environ.get("INCIDENT_AGENT_MODEL", "gpt-4o-mini")
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not set")

    def _chat(self, system: str, user: str) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
        except Exception as e:
            raise ProviderError(f"model call failed: {e}")
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise ProviderError(f"unexpected model response: {payload!r:.200}")

    def reason(self, task: str, evidence: dict) -> dict:
        schemas = {
            "triage": '{"severity": "P1|P2|P3|P4", "category": "...", "confidence": 0.0-1.0, "rationale": "..."}',
            "diagnose": '{"root_cause": "...", "confidence": 0.0-1.0, "evidence": ["..."], "contributing_factors": ["..."]}',
            "plan": '{"steps": ["..."], "risk": "low|medium|high", "requires_approval": true|false, "rollback_plan": "..."}',
        }
        if task not in schemas:
            raise ProviderError(f"unknown task: {task}")
        out = self._chat(
            "You are an SRE incident-response assistant. Reply with JSON only.",
            f"Task: {task}\nRespond with exactly this schema: {schemas[task]}\n"
            f"Evidence:\n{json.dumps(evidence, indent=2)[:6000]}",
        )
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            raise ProviderError(f"model did not return JSON: {out[:200]!r}")

    def narrate(self, report: dict) -> str:
        return self._chat(
            "You are an SRE writing a 2-3 sentence incident note. Plain language, no fluff.",
            f"Summarize this incident report:\n{json.dumps(report, indent=2)[:4000]}",
        )
