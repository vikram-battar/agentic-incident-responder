"""End-to-end demo: run one incident through the full agent workflow."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from incident_agent.orchestrator import Orchestrator
from incident_agent.providers import MockProvider
from incident_agent.tools import load_incidents

incidents = load_incidents(ROOT / "data" / "incidents.json")
orch = Orchestrator(MockProvider(), incidents, ROOT / "data" / "runbooks",
                    checkpoint_dir=ROOT / "checkpoints")

report = orch.run("INC-007", "orders-db",
                  "orders-db rejecting writes: too many connections")
print(f"incident : {report.incident_id} ({report.service})")
print(f"severity : {report.severity} / {report.category}")
print(f"status   : {report.status}")
print(f"cause    : {report.diagnosis['root_cause']} "
      f"(confidence {report.diagnosis['confidence']})")
print("plan     :")
for s in report.plan["steps"]:
    print(f"  - {s}")
print(f"risk     : {report.plan['risk']} "
      f"(approval required: {report.plan['requires_approval']})")
print(f"note     : {report.note}")
