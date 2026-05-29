"""
CI checks for result summarization and repository safety.

These tests avoid network/API calls. They verify that report tooling works on a
small fixture and that sensitive local files are not tracked by Git.
"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_summary_script_outputs_expected_tables():
    fixture = ROOT / "tests" / "fixtures" / "sample_result.json"
    result = subprocess.run(
        [sys.executable, "scripts/summarize_results.py", str(fixture)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Aggregate Results" in result.stdout
    assert "Pairwise: RE-TRAC vs Reformulation" in result.stdout
    assert "Mid-trajectory reformulation | 2/2" in result.stdout
    assert "| 2 | 0 | 1 | 1 | 0 |" in result.stdout


def test_sensitive_files_are_not_tracked():
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    tracked = set(result.stdout.splitlines())

    assert ".env" not in tracked
    assert not any(path.startswith("results/") for path in tracked)
    assert not any(path.endswith(".dataless.bak") for path in tracked)
