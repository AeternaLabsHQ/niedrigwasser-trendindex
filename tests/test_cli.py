import subprocess
import sys


def test_cli_lists_stages():
    result = subprocess.run(
        [sys.executable, "-m", "niedrigwasser", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "ingest" in result.stdout
    assert "screen" in result.stdout


def test_cli_unknown_stage_fails():
    result = subprocess.run(
        [sys.executable, "-m", "niedrigwasser", "nope"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_cli_uv_run_entry_point():
    result = subprocess.run(
        ["uv", "run", "niedrigwasser", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "ingest" in result.stdout
    assert "screen" in result.stdout
