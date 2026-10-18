# agentic-incident-responder

Most incident response is the same loop: read the alert, pull logs and metrics, figure out what broke, decide what to do about it, and don't do anything stupid at 3 AM. I built the loop as code.

Three agents run it in sequence. A triage agent takes the alert, pulls metrics and logs, and assigns severity. A diagnosis agent searches logs, checks metrics, retrieves the relevant runbook, and proposes a root cause with a confidence score. A remediation agent turns that into a step-by-step plan with a risk rating. If the plan is high-risk — failover, dropping things, restarting a production database — it stops and waits for a human. The agent proposes; a human disposes.

This is a portfolio reference implementation I built from scratch. Not from any employer.

## the honest architecture part

The agent loop is real: tools -> reasoning -> working memory -> next step. What's swappable is the brain. Out of the box it runs on a deterministic rule-based provider, so the whole thing works offline and the eval numbers below are reproducible. Point it at any OpenAI-compatible API (`OPENAI_API_KEY`, optional `OPENAI_BASE_URL` / `INCIDENT_AGENT_MODEL`) and the same loop runs with a real model doing the reasoning. No code changes, just `--live-model`.

I'm not claiming the mock provider "does AI". It doesn't. It does the part that's actually valuable to demonstrate: the orchestration, the tool use, the memory, the retries, the approval gate, and the evaluation. The reasoning layer is behind an interface precisely so a model can do it.

## how it works

```
alert -> [enrich] -> triage -> diagnose -> plan -> (approval gate?) -> report
              |          |          |          |
              v          v          v          v
         checkpoint checkpoint checkpoint  checkpoint
```

- **tools** (`src/incident_agent/tools.py`): log search, metrics lookup, runbook retrieval (keyword-ranked, with a minimum-score cutoff so weak matches fall back to "escalate to the owner" instead of hallucinating a plan), alert enrichment.
- **memory** (`memory.py`): working memory per incident — state dict plus an append-only turn log, checkpointed to disk after every step so a crash or retry never loses work.
- **agents** (`agents.py`): triage (severity P1-P4 from error rate / restart velocity), diagnosis (root-cause hypothesis with evidence and confidence), remediation (steps, risk rating, rollback plan).
- **orchestrator** (`orchestrator.py`): runs the workflow with per-step retries and backoff. High-risk plans end at `awaiting_approval` instead of executing.
- **eval** (`eval_harness.py`): 12 labeled incidents, scored like you'd score a model — severity accuracy, root-cause keyword recall, remediation keyword recall, plus p50/p95 latency.

## try it (no API key needed)

```bash
# run the test suite
make test

# run one incident end to end
make run

# run the full eval suite (writes eval_report.md)
make eval

# use a real model instead of the mock
export OPENAI_API_KEY=...
PYTHONPATH=src python -m incident_agent.cli eval --live-model
```

## eval results (mock provider, reproducible)

| metric | value |
|---|---|
| severity accuracy | 1.0 |
| root-cause recall | 1.0 |
| remediation recall | 1.0 |
| **overall** | **1.0** |
| pass rate (>= 0.70) | 12/12 |
| latency p50 / p95 | <0.01s |

The eval set covers the greatest hits: OOMKilled crashloops, a bad deploy spiking 5xx, CPU throttling, disk pressure, DNS failure, expired TLS cert, DB connection exhaustion (this one correctly stops at the approval gate), client-side 400s (correctly falls back to "escalate to the owner" — no runbook applies), cache eviction storms, invalid config, upstream timeouts, and queue lag.

## layout

```
src/incident_agent/   providers, tools, memory, agents, orchestrator, eval, cli
data/incidents.json   12 labeled incidents (synthetic, realistic)
data/runbooks/        11 runbooks the retrieval tool searches
tests/                26 tests, all passing
examples/demo.py      one-command end-to-end run
```

## what i'd do next

Real log/metrics backends behind the tool interfaces (Elasticsearch, Prometheus), a vector store for runbook retrieval instead of keyword overlap, and the eval suite running against a real model on a schedule to catch regressions. The interfaces are already shaped for all three.
