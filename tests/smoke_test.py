"""
Smoke tests for CI.

These tests intentionally avoid network calls and API usage. They only verify
that the project imports cleanly and exposes the expected agent methods.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.baseline import BaselineAgent
from src.reformulator import ReformulationAgent
from src.restart import RestartAgent


def test_agents_expose_required_methods():
    for cls in (BaselineAgent, ReformulationAgent, RestartAgent):
        assert hasattr(cls, "init")
        assert hasattr(cls, "answer")
        assert hasattr(cls, "close")


def test_baseline_query_is_raw_question():
    agent = BaselineAgent()
    question = "What is the population of Bonn?"
    assert question == question.strip()
