from incident_agent.agents import DiagnosisAgent, RemediationAgent, TriageAgent
from incident_agent.memory import IncidentMemory
from incident_agent.tools import AlertEnrichment, LogSearch, MetricsLookup, RunbookRetrieval


def _tools(incidents, runbook_dir):
    return (
        LogSearch(incidents),
        MetricsLookup(incidents),
        RunbookRetrieval(runbook_dir),
        AlertEnrichment(incidents),
    )


def test_triage_p1_oom(incidents, runbook_dir, provider):
    logs, metrics, runbooks, enrich = _tools(incidents, runbook_dir)
    agent = TriageAgent(provider, logs, metrics, enrich)
    mem = IncidentMemory("INC-001")
    out = agent.triage("payments-api",
                       "payments-api CrashLoopBackOff in prod-us-east, restart count 47 in 15m", mem)
    assert out.severity == "P1"
    assert out.confidence > 0.5
    assert mem.get("triage")["severity"] == "P1"


def test_triage_p3_client_errors(incidents, runbook_dir, provider):
    logs, metrics, runbooks, enrich = _tools(incidents, runbook_dir)
    agent = TriageAgent(provider, logs, metrics, enrich)
    mem = IncidentMemory("INC-008")
    out = agent.triage("notifications", "notifications HTTP 400 rate elevated at 2%", mem)
    assert out.severity == "P3"


def test_diagnose_oom(incidents, runbook_dir, provider):
    logs, metrics, runbooks, enrich = _tools(incidents, runbook_dir)
    agent = DiagnosisAgent(provider, logs, metrics, runbooks)
    mem = IncidentMemory("INC-001")
    mem.update("enrichment", {"recent_deploy": False})
    out = agent.diagnose("payments-api", "CrashLoopBackOff OOMKilled memory", mem)
    assert "oomkilled" in out.root_cause.lower()
    assert "memory limit" in out.root_cause.lower()
    assert out.evidence, "expected supporting log evidence"


def test_diagnose_bad_deploy_uses_deploy_context(incidents, runbook_dir, provider):
    logs, metrics, runbooks, enrich = _tools(incidents, runbook_dir)
    agent = DiagnosisAgent(provider, logs, metrics, runbooks)
    mem = IncidentMemory("INC-002")
    mem.update("enrichment", {"recent_deploy": True})
    out = agent.diagnose("checkout-web", "HTTP 500 rate spiked after deploy v2.14.3", mem)
    assert "deploy" in out.root_cause.lower()


def test_plan_medium_risk_no_approval(incidents, runbook_dir, provider):
    _, _, runbooks, _ = _tools(incidents, runbook_dir)
    agent = RemediationAgent(provider, runbooks)
    mem = IncidentMemory("INC-001")
    mem.update("runbook_candidates", [{"name": "crashloop-oom"}])

    class D:
        root_cause = "Container OOMKilled"
        confidence = 0.95

    plan = agent.plan("payments-api", D(), mem)
    assert plan.risk == "medium"
    assert plan.requires_approval is False
    assert any("memory limit" in s for s in plan.steps)


def test_plan_high_risk_requires_approval(incidents, runbook_dir, provider):
    _, _, runbooks, _ = _tools(incidents, runbook_dir)
    agent = RemediationAgent(provider, runbooks)
    mem = IncidentMemory("INC-007")
    mem.update("runbook_candidates", [{"name": "db-connection-exhaustion"}])

    class D:
        root_cause = "Database connection exhaustion"
        confidence = 0.9

    plan = agent.plan("orders-db", D(), mem)
    assert plan.risk == "high"
    assert plan.requires_approval is True
    assert plan.rollback_plan
