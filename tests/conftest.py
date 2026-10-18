import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from incident_agent.providers import MockProvider
from incident_agent.tools import load_incidents


@pytest.fixture()
def incidents():
    return load_incidents(ROOT / "data" / "incidents.json")


@pytest.fixture()
def provider():
    return MockProvider()


@pytest.fixture()
def runbook_dir():
    return ROOT / "data" / "runbooks"
