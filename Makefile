.PHONY: test eval run demo lint

test:
	PYTHONPATH=src python -m pytest tests/ -q

eval:
	PYTHONPATH=src python -m incident_agent.cli eval

run:
	PYTHONPATH=src python -m incident_agent.cli run --service payments-api --alert "payments-api CrashLoopBackOff in prod-us-east, restart count 47 in 15m" --id INC-001

demo:
	PYTHONPATH=src python examples/demo.py
