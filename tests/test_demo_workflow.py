"""
Test the demo workflow using the rich logger plugin.

This test runs the demo Snakefile to ensure the rich logger plugin works correctly.
"""

import subprocess
import tempfile
from pathlib import Path
import pytest


def test_demo_workflow():
    """Test that a sample workflow runs successfully with the rich logger plugin."""

    project_root = Path(__file__).parent.parent
    test_snakefile = project_root / "tests" / "fixtures" / "Snakefile"

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "demo_output"
        output_dir.mkdir()

        cmd = [
            "snakemake",
            "-s",
            str(test_snakefile),
            "-d",
            str(output_dir),
            "--show-failed-logs",
            "--printshellcmds",
            "--logger",
            "rich",
            "--cores",
            "1",
            "output.txt",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            assert result.returncode == 0, (
                f"Snakemake failed with return code {result.returncode}.\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )

        except subprocess.TimeoutExpired:
            pytest.fail("Snakemake command timed out after 5 minutes")


def test_dryrun_mode():
    """Test that a dry run lists the jobs that would run, with their reasons.

    Nothing executes in a dry run, so there are no job-started/-finished events
    and no progress display. The logger should instead list each scheduled job
    (rule, wildcards, reason) and print snakemake's dry-run footer.
    """

    project_root = Path(__file__).parent.parent
    test_snakefile = project_root / "tests" / "fixtures" / "Snakefile"

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "demo_output"
        output_dir.mkdir()

        cmd = [
            "snakemake",
            "-n",
            "-s",
            str(test_snakefile),
            "-d",
            str(output_dir),
            "--logger",
            "rich",
            "--cores",
            "1",
            "output.txt",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            assert result.returncode == 0, (
                f"Dry-run snakemake failed with return code "
                f"{result.returncode}.\nSTDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )

            output = result.stdout + result.stderr
            # per-job listing with reasons, and the dry-run footer
            assert "Reason:" in output, (
                "The rich logger did not list job reasons in dry-run mode.\n"
                f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )
            assert "This was a dry-run" in output, (
                "The rich logger did not print the dry-run footer.\n"
                f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )
            assert "create_input" in output, (
                "The rich logger did not list the scheduled jobs in dry-run "
                f"mode.\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )

        except subprocess.TimeoutExpired:
            pytest.fail("Snakemake command timed out after 5 minutes")


def test_nothing_to_be_done():
    """Test that the "nothing to be done" message is displayed when up to date.

    Snakemake emits this as a plain info log (no LogEvent) once all requested
    files are present and up to date. The rich logger used to drop it silently,
    making an up-to-date run look like it ended without explanation.
    """

    project_root = Path(__file__).parent.parent
    test_snakefile = project_root / "tests" / "fixtures" / "Snakefile"

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "demo_output"
        output_dir.mkdir()

        cmd = [
            "snakemake",
            "-s",
            str(test_snakefile),
            "-d",
            str(output_dir),
            "--logger",
            "rich",
            "--cores",
            "1",
            "output.txt",
        ]

        try:
            # first run builds all outputs
            first = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            assert first.returncode == 0, (
                f"Initial snakemake run failed with return code "
                f"{first.returncode}.\nSTDOUT: {first.stdout}\n"
                f"STDERR: {first.stderr}"
            )

            # second run: everything is up to date
            second = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            assert second.returncode == 0, (
                f"Up-to-date snakemake run failed with return code "
                f"{second.returncode}.\nSTDOUT: {second.stdout}\n"
                f"STDERR: {second.stderr}"
            )

            output = second.stdout + second.stderr
            assert "Nothing to be done" in output, (
                "The rich logger did not display the 'Nothing to be done' "
                f"message on an up-to-date run.\nSTDOUT: {second.stdout}\n"
                f"STDERR: {second.stderr}"
            )

        except subprocess.TimeoutExpired:
            pytest.fail("Snakemake command timed out after 5 minutes")


def test_checkpoint_workflow():
    """Test that a workflow using checkpoints runs without breaking the logger.

    Checkpoints re-evaluate the DAG mid-run, so jobs are submitted for rules
    that were not part of the initial run_info event. This used to raise a
    KeyError inside the logging handler (which Snakemake swallows, leaving the
    return code at 0), so we explicitly assert the handler reported no error.
    """

    project_root = Path(__file__).parent.parent
    test_snakefile = project_root / "tests" / "fixtures" / "Snakefile_checkpoint"

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "checkpoint_output"
        output_dir.mkdir()

        cmd = [
            "snakemake",
            "-s",
            str(test_snakefile),
            "-d",
            str(output_dir),
            "--show-failed-logs",
            "--printshellcmds",
            "--logger",
            "rich",
            "--cores",
            "1",
            "aggregated.txt",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            assert result.returncode == 0, (
                f"Snakemake failed with return code {result.returncode}.\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )

            assert "Error in logging handler" not in result.stderr, (
                "The rich logger raised an error while handling checkpoint "
                f"events.\nSTDERR: {result.stderr}"
            )

        except subprocess.TimeoutExpired:
            pytest.fail("Snakemake command timed out after 5 minutes")
