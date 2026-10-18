"""Agentic incident responder: multi-agent triage, diagnosis, and remediation
planning with tool use, working memory, durable orchestration, and an
evaluation harness."""
from .agents import DiagnosisAgent, RemediationAgent, TriageAgent
from .eval_harness import evaluate, write_report
from .memory import IncidentMemory
from .orchestrator import IncidentReport, Orchestrator
from .providers import MockProvider, OpenAICompatibleProvider, ProviderError
from .tools import AlertEnrichment, LogSearch, MetricsLookup, RunbookRetrieval, ToolError

__all__ = [
    "TriageAgent", "DiagnosisAgent", "RemediationAgent",
    "IncidentMemory", "Orchestrator", "IncidentReport",
    "MockProvider", "OpenAICompatibleProvider", "ProviderError",
    "LogSearch", "MetricsLookup", "RunbookRetrieval", "AlertEnrichment", "ToolError",
    "evaluate", "write_report",
]

__version__ = "0.1.0"
