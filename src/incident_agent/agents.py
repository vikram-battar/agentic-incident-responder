"""The three agents. Each one: gather evidence with tools, reason via the
provider, write the result to memory.

The reasoning itself is provider-pluggable - MockProvider does it with
deterministic rules (offline, testable), OpenAICompatibleProvider does it
with a real model. The agent loop (tools -> reason -> memory) is the same
either way.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .memory import IncidentMemory
from .providers import Provider
from .tools import AlertEnrichment, LogSearch, MetricsLookup, RunbookRetrieval


@dataclass
class TriageResult:
    severity: str
    category: str
    confidence: float
    rationale: str


@dataclass
class DiagnosisResult:
    root_cause: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    contributing_factors: list[str] = field(default_factory=list)


@dataclass
class RemediationPlan:
    steps: list[str] = field(default_factory=list)
    risk: str = "low"
    requires_approval: bool = False
    rollback_plan: str = ""


class TriageAgent:
    def __init__(self, provider: Provider, logs: LogSearch, metrics: MetricsLookup,
                 enrich: AlertEnrichment):
        self.provider = provider
        self.logs = logs
        self.metrics = metrics
        self.enrich = enrich

    def triage(self, service: str, alert: str, memory: IncidentMemory) -> TriageResult:
        meta = self.enrich.enrich(service, alert)
        metrics = self.metrics.get(service)
        log_lines = self.logs.search(service, keywords=alert.split()[:6], limit=8)
        out = self.provider.reason("triage", {
            "alert": alert, "service": service,
            "metrics": metrics, "logs": log_lines,
            "recent_deploy": meta["recent_deploy"],
        })
        result = TriageResult(out["severity"], out["category"],
                              float(out["confidence"]), out["rationale"])
        memory.update("triage", out)
        memory.update("enrichment", meta)
        memory.log_turn("triage", "severity_assigned",
                        f"{result.severity}/{result.category}")
        return result


class DiagnosisAgent:
    def __init__(self, provider: Provider, logs: LogSearch, metrics: MetricsLookup,
                 runbooks: RunbookRetrieval):
        self.provider = provider
        self.logs = logs
        self.metrics = metrics
        self.runbooks = runbooks

    def diagnose(self, service: str, alert: str, memory: IncidentMemory) -> DiagnosisResult:
        metrics = self.metrics.get(service)
        log_lines = self.logs.search(service, keywords=alert.split()[:8], limit=12)
        candidates = self.runbooks.retrieve(alert + " " + " ".join(log_lines[:3]))
        out = self.provider.reason("diagnose", {
            "alert": alert, "service": service,
            "metrics": metrics, "logs": log_lines,
            "recent_deploy": bool(memory.get("enrichment", {}).get("recent_deploy")),
            "runbook_candidates": [c["name"] for c in candidates],
        })
        result = DiagnosisResult(
            out["root_cause"], float(out["confidence"]),
            list(out.get("evidence", [])), list(out.get("contributing_factors", [])))
        memory.update("diagnosis", out)
        memory.update("runbook_candidates", candidates)
        memory.log_turn("diagnosis", "root_cause_hypothesis", result.root_cause[:80])
        return result


class RemediationAgent:
    def __init__(self, provider: Provider, runbooks: RunbookRetrieval):
        self.provider = provider
        self.runbooks = runbooks

    def plan(self, service: str, diagnosis: DiagnosisResult,
             memory: IncidentMemory) -> RemediationPlan:
        candidates = memory.get("runbook_candidates", [])
        steps: list[str] = []
        for cand in candidates[:1]:
            try:
                steps = self.runbooks.get(cand["name"])["steps"]
            except Exception:
                steps = []
        out = self.provider.reason("plan", {
            "service": service,
            "diagnosis": {"root_cause": diagnosis.root_cause,
                          "confidence": diagnosis.confidence},
            "runbook_steps": steps,
        })
        plan = RemediationPlan(list(out.get("steps", [])), out.get("risk", "low"),
                               bool(out.get("requires_approval", False)),
                               out.get("rollback_plan", ""))
        memory.update("plan", out)
        memory.log_turn("remediation", "plan_proposed",
                        f"risk={plan.risk} approval={plan.requires_approval}")
        return plan
