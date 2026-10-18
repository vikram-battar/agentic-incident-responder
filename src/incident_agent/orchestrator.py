"""Durable workflow: triage -> diagnose -> plan, with retries, checkpoints,
and a human-in-the-loop gate before anything risky.

Each step checkpoints memory to disk first, so a crash or a retry never
loses the work already done. Tool failures are retried with backoff;
if a step still fails, the run is marked failed with the error recorded.
High-risk remediation plans stop at the approval gate - the agent
proposes, a human disposes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from .agents import DiagnosisAgent, RemediationAgent, TriageAgent
from .memory import IncidentMemory
from .providers import Provider
from .tools import AlertEnrichment, LogSearch, MetricsLookup, RunbookRetrieval, ToolError


@dataclass
class StepTiming:
    step: str
    seconds: float
    attempts: int


@dataclass
class IncidentReport:
    incident_id: str
    service: str
    alert: str
    severity: str = ""
    category: str = ""
    diagnosis: dict = field(default_factory=dict)
    plan: dict = field(default_factory=dict)
    status: str = "pending"  # completed | awaiting_approval | failed
    note: str = ""
    timings: list[dict] = field(default_factory=list)
    error: str = ""


def _run_step(fn, step_name: str, max_retries: int, timings: list) -> tuple:
    attempts = 0
    start = time.time()
    while True:
        attempts += 1
        try:
            result = fn()
            timings.append({"step": step_name, "seconds": round(time.time() - start, 3),
                            "attempts": attempts})
            return result
        except ToolError as e:
            if attempts > max_retries + 1:
                timings.append({"step": step_name, "seconds": round(time.time() - start, 3),
                                "attempts": attempts})
                raise
            time.sleep(0.05 * attempts)  # tiny backoff; real impl would be longer


class Orchestrator:
    def __init__(self, provider: Provider, incidents: list[dict], runbook_dir: str | Path,
                 checkpoint_dir: str | Path | None = None, max_retries: int = 2):
        self.provider = provider
        self.logs = LogSearch(incidents)
        self.metrics = MetricsLookup(incidents)
        self.runbooks = RunbookRetrieval(runbook_dir)
        self.enrich = AlertEnrichment(incidents)
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        self.max_retries = max_retries

    def _checkpoint(self, memory: IncidentMemory, step: str) -> None:
        if self.checkpoint_dir:
            memory.checkpoint(self.checkpoint_dir / f"{memory.incident_id}.{step}.json")

    def run(self, incident_id: str, service: str, alert: str) -> IncidentReport:
        memory = IncidentMemory(incident_id)
        memory.update("alert", alert)
        report = IncidentReport(incident_id=incident_id, service=service, alert=alert)
        triage = TriageAgent(self.provider, self.logs, self.metrics, self.enrich)
        diagnosis = DiagnosisAgent(self.provider, self.logs, self.metrics, self.runbooks)
        remediation = RemediationAgent(self.provider, self.runbooks)
        try:
            t = _run_step(lambda: triage.triage(service, alert, memory),
                          "triage", self.max_retries, report.timings)
            self._checkpoint(memory, "triage")
            report.severity, report.category = t.severity, t.category

            d = _run_step(lambda: diagnosis.diagnose(service, alert, memory),
                          "diagnose", self.max_retries, report.timings)
            self._checkpoint(memory, "diagnose")
            report.diagnosis = {"root_cause": d.root_cause, "confidence": d.confidence,
                                "evidence": d.evidence,
                                "contributing_factors": d.contributing_factors}

            p = _run_step(lambda: remediation.plan(service, d, memory),
                          "plan", self.max_retries, report.timings)
            self._checkpoint(memory, "plan")
            report.plan = {"steps": p.steps, "risk": p.risk,
                           "requires_approval": p.requires_approval,
                           "rollback_plan": p.rollback_plan}

            if p.requires_approval:
                report.status = "awaiting_approval"
            else:
                report.status = "completed"
            report.note = self.provider.narrate({
                "service": service, "severity": report.severity,
                "category": report.category, "diagnosis": report.diagnosis,
                "plan": report.plan, "status": report.status,
            })
        except ToolError as e:
            report.status = "failed"
            report.error = str(e)
        return report
