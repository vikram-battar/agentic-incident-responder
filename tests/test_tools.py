import pytest

from incident_agent.tools import (
    AlertEnrichment,
    LogSearch,
    MetricsLookup,
    RunbookRetrieval,
    ToolError,
)


def test_log_search_finds_oom_lines(incidents):
    tool = LogSearch(incidents)
    lines = tool.search("payments-api", ["oomkilled"])
    assert lines, "expected OOMKilled lines"
    assert any("OOMKilled" in l for l in lines)


def test_log_search_unknown_service_raises(incidents):
    tool = LogSearch(incidents)
    with pytest.raises(ToolError):
        tool.search("no-such-service", ["error"])


def test_metrics_lookup(incidents):
    tool = MetricsLookup(incidents)
    m = tool.get("checkout-web")
    assert m["error_rate_pct"] == 62


def test_metrics_lookup_unknown_raises(incidents):
    with pytest.raises(ToolError):
        MetricsLookup(incidents).get("nope")


def test_runbook_retrieval_ranks_relevant_first(runbook_dir):
    tool = RunbookRetrieval(runbook_dir)
    hits = tool.retrieve("OOMKilled CrashLoopBackOff memory cgroup out of memory")
    assert hits, "expected at least one hit"
    assert hits[0]["name"] == "crashloop-oom"
    assert any("memory limit" in s for s in hits[0]["steps"])


def test_runbook_retrieval_dns(runbook_dir):
    tool = RunbookRetrieval(runbook_dir)
    hits = tool.retrieve("no such host DNS lookup failed")
    assert hits[0]["name"] == "dns-failure"


def test_runbook_get(runbook_dir):
    tool = RunbookRetrieval(runbook_dir)
    doc = tool.get("db-connection-exhaustion")
    assert any("Failover" in s for s in doc["steps"])


def test_alert_enrichment(incidents):
    tool = AlertEnrichment(incidents)
    meta = tool.enrich("checkout-web", "5xx spike")
    assert meta["owner"] == "checkout-team"
    assert meta["recent_deploy"] is True
