import logging
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.console import Console
from typing import Optional
from snakemake_interface_executor_plugins.settings import ExecMode


class RichLogHandler(RichHandler):
    """
    A custom Rich handler for Snakemake logging with a persistent progress bar at the bottom.
    """

    def __init__(
        self,
        quiet=None,
        printshellcmds: Optional[bool] = None,
        printreason: Optional[bool] = None,
        debug_dag: Optional[bool] = None,
        nocolor: Optional[bool] = None,
        stdout: Optional[bool] = None,
        debug: Optional[bool] = None,
        mode=None,
        show_failed_logs: Optional[bool] = None,
        dryrun: Optional[bool] = None,
        *args,
        **kwargs,
    ):
        console = Console(stderr=not stdout)
        super().__init__(*args, **kwargs, console=console)

        # Store additional configurations
        self.quiet = quiet
        self.printshellcmds = printshellcmds
        self.printreason = printreason
        self.debug_dag = debug_dag
        self.nocolor = nocolor
        self.stdout = stdout
        self.debug = debug
        self.mode = mode
        self.show_failed_logs = show_failed_logs
        self.dryrun = dryrun
        self.stream = True

        # Initialize the progress bar only if mode is not SUBPROCESS and not dryrun
        if self.mode != ExecMode.SUBPROCESS and not self.dryrun:
            self.progress = Progress(
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                BarColumn(),
                MofNCompleteColumn(),
                TextColumn("•"),
                TimeElapsedColumn(),
                TextColumn("•"),
                TimeRemainingColumn(),
                console=console,
                auto_refresh=True,
            )
            self.progress_task = None
            self.total_steps = 1  # To avoid division errors if not set
        else:
            self.progress = None
            self.progress_task = None

    def start_progress_bar(self, total_steps):
        """
        Initialize and start the progress bar for a Snakemake job if progress is enabled.
        """
        if self.progress:
            self.total_steps = total_steps
            self.progress_task = self.progress.add_task(
                "Processing...", total=total_steps
            )

    def get_level(self, record: logging.LogRecord) -> str:
        """
        Gets snakemake log level from a log record. If there is no snakemake log level,
        returns the log record's level name.

        Args:
            record (logging.LogRecord)
        Returns:
            str: The log level

        """
        level = record.__dict__.get("level", None)

        if level is None:
            level = record.levelname

        return level.lower()

    def update_progress(self, done_steps):
        """
        Update the progress bar with the number of completed steps.
        """
        if self.progress and self.progress_task is not None:
            self.progress.update(self.progress_task, completed=done_steps)

    def emit(self, record):
        """
        Emit log messages with Rich formatting and update the progress bar if necessary.
        """
        message = self.format(record)
        level = self.get_level(record)

        if level == "progress" and self.progress:
            done_steps = getattr(record, "done", 0)
            total_steps = getattr(record, "total", self.total_steps)
            if self.progress_task is None:
                # Start progress bar if this is the first progress log
                self.total_steps = total_steps
                self.progress_task = self.progress.add_task(
                    "Processing...", total=total_steps
                )
                self.progress.start()
            # Update the progress bar
            self.progress.update(self.progress_task, completed=done_steps)
        if level == "run_info":
            record.message.replace("\n", "")
        else:
            super().emit(record)

    def close(self):
        """
        Ensure progress bar is stopped and cleaned up on handler close.
        """
        if self.progress:
            self.progress.stop()
            if self.progress_task is not None:
                self.progress.remove_task(self.progress_task)
                self.progress_task = None
        super().close()
