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
from rich.text import Text


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
        console = Console(
            stderr=not stdout,
        )
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

    def get_level_text(self, record: logging.LogRecord) -> Text:
        """Get the level name with a custom color style for the record.

        Args:
            record (logging.LogRecord): LogRecord instance.

        Returns:
            Text: Styled text for the level name.
        """
        level_name = record.levelname

        # Define custom styles for specific "pseudo" levels
        custom_styles = {
            "JOB INFO": "dark_cyan",
            "SHELL CMD": "green",
            "HOST": "medium_purple",
            "RESOURCES INFO": "royal_blue1",
            "RUN INFO": "yellow3",
            "INFO": "pale_green1",
        }

        # Apply custom style if it's a custom level, otherwise use default Rich style
        style = custom_styles.get(level_name, f"logging.level.{level_name.lower()}")

        # Return the level name styled with the selected color
        return Text.styled(f"[{level_name}]".ljust(1), style=style)
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

class RichFormatter(logging.Formatter):
    def __init__(self, printshellcmds: bool):
        super().__init__()
        self.printshellcmds = printshellcmds

    def format(self, record):
        # Format specific message types based on extra data
        if hasattr(record, "level"):
            record.levelname = record.level.upper().replace("_", " ")
            if record.level == "job_info":
                # Format job info as a single line

                job_id = getattr(record, "jobid", "N/A")
                rule_name = getattr(record, "rule_name", "N/A")
                shell_cmd = getattr(record, "shellcmd")

                if shell_cmd and self.printshellcmds:
                    return f"Executing job: {job_id} | rule: {rule_name} | shell: {shell_cmd}"
                else:
                    return f"Executing job: {job_id} | rule: {rule_name}"

        # Default format for other messages
        return f"{record.getMessage()}"


class RichFilter(logging.Filter):
    def filter(self, record):
        # Suppress repetitive "Select jobs to execute..." log entries
        level = getattr(record, "level", False)

        if level == "shellcmd":
            return False
        elif level == "progress":
            return True
        elif record.getMessage() == "Select jobs to execute...":
            return False
        elif record.getMessage().startswith("Execute"):
            return False

        # Suppress empty log entries
        if not record.getMessage().strip():
            return False

        return True