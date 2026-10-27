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
                check=False,
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


@pytest.mark.parametrize("verbose", [False, True])
def test_dryrun_mode(verbose):
    """Test the dry-run output.

    The job stats table is printed once, after the job listing. The listing
    of each job that would run (with wildcards and reason) is only shown with
    --verbose.
    """

    project_root = Path(__file__).parent.parent
    test_snakefile = project_root / "tests" / "fixtures" / "Snakefile"

    with tempfile.TemporaryDirectory() as temp_dir:
        cmd = [
            "snakemake",
            "-n",
            "-s",
            str(test_snakefile),
            "-d",
            temp_dir,
            "--logger",
            "rich",
            "--cores",
            "1",
            "output.txt",
        ]
        if verbose:
            cmd.append("--verbose")

        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=300
        )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "This was a dry-run" in output, output
    assert output.count("Job stats") == 1, output
    if verbose:
        assert "Reason:" in output, output
        assert output.index("Job stats") > output.rindex("Would run"), output
    else:
        assert "Would run" not in output, output


def test_dryrun_quiet():
    """With --quiet, snakemake sends the job stats only once."""

    snakefile = Path(__file__).parent / "fixtures" / "Snakefile"

    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            ["snakemake", "-n", "--quiet", "-s", str(snakefile), "-d", temp_dir]
            + ["--logger", "rich", "--cores", "1", "output.txt"],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert output.count("Job stats") == 1, output


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
            first = subprocess.run(
                cmd, check=False, capture_output=True, text=True, timeout=300
            )
            assert first.returncode == 0, (
                f"Initial snakemake run failed with return code "
                f"{first.returncode}.\nSTDOUT: {first.stdout}\n"
                f"STDERR: {first.stderr}"
            )

            # second run: everything is up to date
            second = subprocess.run(
                cmd, check=False, capture_output=True, text=True, timeout=300
            )
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
                check=False,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            assert result.returncode == 0, (
                f"Snakemake failed with return code {result.returncode}.\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )

            assert "--- Logging error ---" not in result.stderr, (
                "The rich logger raised an error while handling checkpoint "
                f"events.\nSTDERR: {result.stderr}"
            )

        except subprocess.TimeoutExpired:
            pytest.fail("Snakemake command timed out after 5 minutes")


@pytest.mark.parametrize("verbose", [False, True])
def test_errors_and_messages_are_printed(verbose):
    snakefile = Path(__file__).parent / "fixtures" / "Snakefile_error"

    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            ["snakemake", "-s", str(snakefile), "-d", temp_dir, "--logger", "rich"]
            + (["--verbose"] if verbose else []),
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Initializing workflow context" in output, output
    assert "CustomConfigError" in output, output
    assert "unknown step 'pdf'" in output, output
    assert "Internal debug details" not in output, output
