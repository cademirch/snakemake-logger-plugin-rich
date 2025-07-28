from logging import LogRecord
from typing import Optional
from uuid import UUID
from rich.console import Console
from rich.syntax import Syntax
from rich.progress import Progress, TaskID
from rich.live import Live
from rich.markdown import Markdown
from rich.status import Status
from rich.panel import Panel
from rich.table import Table
from rich import box
from typing import Dict
from pathlib import Path
from snakemake_interface_logger_plugins.common import LogEvent
import snakemake_logger_plugin_rich.events as events
import re
import logging


def formatted_table(cols: int, left_col_style: str):
    """Convenience function that returns a table with standardized formatting"""
    _table = Table(
        show_header=False,
        pad_edge=False,
        show_edge=False,
        padding=(0,0),
        box=box.SIMPLE,
    )
    # the column name is irrelevant b/c headers won't be shown
    _table.add_column("detail", justify="left", style=left_col_style, no_wrap=True)
    for i in range(cols-1):
        _table.add_column(f"col_{i}", justify="left")
    return _table

def prettyprint_rule(rule: str) -> str:
    """Format the rule name to replace underscores with spaces and strip extra spaces"""
    return re.sub(" +", " ", rule.replace('_', ' ')).strip()


def format_wildcards(wildcards):
    """Format wildcards into a string representation."""
    if not wildcards:
        return None

    wc_table = formatted_table(2, "default")
    for k, v in wildcards.items():
        wc_table.add_row(f"[italic]{k}[/] : ", v)
    return wc_table


class ProgressDisplay:
    def __init__(self, progress: Progress, console: Console):

        self.progress = progress
        self.rule_tasks: Dict[str, TaskID] = {}
        self.live_display = Live(
            Panel(
                progress,
                title = "Workflow Progress",
                border_style="dim"
            ),
            refresh_per_second=4,
            transient=True,
            console= console
        )

    def add_or_update(
        self, rule: str, completed: int, total: int, visible: bool = True
    ):
        _rule = prettyprint_rule(rule)
        if rule not in self.rule_tasks:
            task_id = self.progress.add_task(
                description=_rule, total=total, visible=visible
            )
            self.rule_tasks[rule] = task_id
        else:
            task_id = self.rule_tasks[rule]

        self.progress.update(task_id, completed=completed, total=total, refresh=True)

        if completed >= total:
            self.progress.update(
                task_id,
                description=f"[dim green]✓[/] [dim default]{_rule}[/]",
                refresh=True
            )

        return task_id

    def mark_rule_failed(self, rule: str):
        """Update progress bar for a failed rule."""
        _rule = prettyprint_rule(rule)
        if rule in self.rule_tasks:
            task_id = self.rule_tasks[rule]
            self.progress.update(
                task_id, description=f"[red]✗[/] {_rule} [red](failed)[/]", refresh=True
            )

    def set_visible(self, rule: str, visible: bool = True):
        """Set visibility of a progress bar."""
        if rule in self.rule_tasks:
            task_id = self.rule_tasks[rule]
            self.progress.update(task_id, visible=visible, refresh=True)

    def has_tasks(self) -> bool:
        """Check if there are any active tasks."""
        return len(self.rule_tasks) > 0


class EventHandler:
    """Base class for processing Snakemake log events."""

    def __init__(
        self,
        console: Console,
        progress: Progress,
        dryrun: bool = False,
    ):
        self.current_workflow_id: Optional[UUID] = None
        self.dryrun: bool = dryrun
        self.console = console
        self.progress = progress
        self.progress_display = ProgressDisplay(progress, self.console)
        self.jobs_info = {}
        self.rule_counts = {}  # {rule_name: {"total": n, "completed": m}}
        self.total_jobs = 0
        self.completed = 0
        self.conda_statuses = {}  # {env_path: Status object}

    def handle(self, record: LogRecord, **kwargs) -> None:
        """Process a log record, routing to appropriate handler based on event type."""
        event_type = getattr(record, "event", None)

        if event_type:
            handler_map = {
                LogEvent.ERROR: (events.Error, self.handle_error),
                LogEvent.WORKFLOW_STARTED: (
                    events.WorkflowStarted,
                    self.handle_workflow_started,
                ),
                LogEvent.JOB_INFO: (events.JobInfo, self.handle_job_info),
                LogEvent.JOB_STARTED: (events.JobStarted, self.handle_job_started),
                LogEvent.JOB_FINISHED: (events.JobFinished, self.handle_job_finished),
                LogEvent.JOB_ERROR: (events.JobError, self.handle_job_error),
                LogEvent.SHELLCMD: (events.ShellCmd, self.handle_shellcmd),
                LogEvent.RULEGRAPH: (events.RuleGraph, self.handle_rule_graph),
                LogEvent.GROUP_INFO: (events.GroupInfo, self.handle_group_info),
                LogEvent.GROUP_ERROR: (events.GroupError, self.handle_group_error),
                LogEvent.RESOURCES_INFO: (
                    events.ResourcesInfo,
                    self.handle_resources_info,
                ),
                LogEvent.DEBUG_DAG: (events.DebugDag, self.handle_debug_dag),
                LogEvent.PROGRESS: (events.Progress, self.handle_progress),
                LogEvent.RUN_INFO: (events.RunInfo, self.handle_run_info),
            }

            handler_info = handler_map.get(event_type)
            if handler_info:
                event_class, handler_method = handler_info

                handler_method(event_class.from_record(record), **kwargs)
            else:
                self.handle_generic_event(event_type, record, **kwargs)
        else:
            self.handle_generic_record(record, **kwargs)



    def handle_error(self, event_data: events.Error, **kwargs) -> None:
        """Handle error event."""
        pass

    def handle_workflow_started(
        self, event_data: events.WorkflowStarted, **kwargs
    ) -> None:
        """Handle workflow started event."""
        self.console.rule(f"Workflow {event_data.workflow_id}", style = "green")

    def handle_job_info(self, event_data: events.JobInfo, **kwargs) -> None:
        """Handle job info event with rich formatting."""

        self.jobs_info[event_data.jobid] = {
            "rule": event_data.rule_name,
            "wildcards": event_data.wildcards,
        }

        self.progress_display.set_visible(event_data.rule_name, True)
        submission_text = f"[bold light_steel_blue]◯ Submitted[/] {event_data.rule_name} [dim](id: {event_data.jobid})[/]"

        table = formatted_table(2, "bold light_steel_blue")

        wc_table = format_wildcards(event_data.wildcards)
        if wc_table:
            table.add_row("    Wildcards:", wc_table)

        if event_data.rule_msg:
            table.add_row("    Message:", event_data.rule_msg)

        self.console.log(submission_text, table)

    def handle_job_started(self, event_data: events.JobStarted, **kwargs) -> None:
        """Handle job started event."""
        pass

    def handle_job_finished(self, event_data: events.JobFinished, **kwargs) -> None:
        """Handle job finished event with rich formatting."""
        job_id = event_data.job_id

        if job_id in self.jobs_info:
            info = self.jobs_info[job_id]
            rule_name = info["rule"]

            if rule_name in self.rule_counts:
                self.rule_counts[rule_name]["completed"] += 1
                completed = self.rule_counts[rule_name]["completed"]
                total = self.rule_counts[rule_name]["total"]

                self.progress_display.add_or_update(rule_name, completed, total)

            self.completed += 1
            self.progress_display.add_or_update(
                "Total Progress", self.completed, self.total_jobs
            )

            finished_text = "[bold green]◉ Finished[/] " + info["rule"] + f" [dim](id: {job_id})[/]"

            table = formatted_table(2, "bold green")
            wc_table = format_wildcards(info["wildcards"])
            if wc_table:
                table.add_row("    Wildcards: ", wc_table)

            self.console.log(finished_text, table)

    def handle_shellcmd(self, event_data: events.ShellCmd, **kwargs) -> None:
        """Handle shell command event with syntax highlighting."""
        if event_data.shellcmd:
            format_cmd = re.sub(r" +", " ", event_data.shellcmd).rstrip()
            format_cmd = re.sub("^\n", "", format_cmd)
            shell_table = formatted_table(2, "default")
            cmd = Syntax(
                format_cmd,
                dedent=True,
                lexer="bash",
                tab_size=2,
                word_wrap=True,
                padding=1
            )
            shell_table.add_row("     ", cmd)
            self.console.log("[light_steel_blue]    Shell Command:[/]", shell_table)

    def handle_job_error(self, event_data: events.JobError, **kwargs) -> None:
        """Handle job error event."""
        self.console.log(
            f"[bold red]ERROR[/bold red] in job {event_data.jobid}: Job failed"
        )

    def handle_group_info(self, event_data: events.GroupInfo, **kwargs) -> None:
        """Handle group info event."""
        pass

    def handle_group_error(self, event_data: events.GroupError, **kwargs) -> None:
        """Handle group error event."""
        pass

    def handle_resources_info(self, event_data: events.ResourcesInfo, **kwargs) -> None:
        """Handle resources info event."""
        pass

    def handle_debug_dag(self, event_data: events.DebugDag, **kwargs) -> None:
        """Handle debug DAG event."""
        pass

    def handle_progress(self, event_data: events.Progress, **kwargs) -> None:
        """Handle progress event."""
        pass

    def handle_rule_graph(self, event_data: events.RuleGraph, **kwargs) -> None:
        """Handle rule graph event."""
        pass

    def handle_run_info(self, event_data: events.RunInfo, **kwargs) -> None:
        """Handle run info event - sets up progress bars."""
        self.total_jobs = event_data.total_job_count

        if self.total_jobs > 0:
            self.total_progress_task = self.progress_display.add_or_update(
                "Total Progress", 0, self.total_jobs
            )
            self.console.log(f"Processing Workflow: {self.total_jobs} jobs", style="blue")
            self.progress.disable = False
            # end any existing conda statuses
            for status in self.conda_statuses.values():
                status.stop()
            self.conda_statuses.clear()
            self.progress_display.live_display.start()

        for rule, count in event_data.per_rule_job_counts.items():
            if count > 0:
                self.rule_counts[rule] = {"total": count, "completed": 0}
                self.progress_display.add_or_update(rule, 0, count, visible=False)

    def handle_generic_event(
        self, event_type: LogEvent, record: LogRecord, **kwargs
    ) -> None:
        """Handle events that don't have a specific handler defined."""
        pass

    def handle_generic_record(self, record: LogRecord, **kwargs) -> None:
        """Handle log records that don't have an event type."""
        message = record.getMessage()

        if not self.should_log_message(record, message):
            return
        conda_depwarn = "Your conda installation is not configured to use" in message
        if conda_depwarn:
            self.console.print(
                Panel(
                    Markdown("Adding `defaults` to the conda channel list implicitly is deprecated. To fix this, read [this guide](https://conda-forge.org/docs/user/tipsandtricks.html)."),
                    title = "Warning: conda channel configuration",
                    border_style="yellow"
                )
            )
            return

        # Check for conda environment creation start
        conda_create_match = re.search(
            r"Creating conda environment (.+?)\.\.\..*", message
        )
        if conda_create_match:
            env_path = conda_create_match.group(1)
            env_name = Path(env_path).name
            self._start_conda_status(env_name)
            return

        # Check for conda environment creation completion
        conda_done_match = re.search(
            r"Environment for (.+?) created \(location: (.+?)\)", message
        )
        if conda_done_match:
            env_path = conda_done_match.group(1)
            env_name = Path(env_path).name
            self._complete_conda_status(env_name)
            return

        if "Complete log" in message:
            self.console.rule("Workflow Finished", style="green")
            self.console.print("Complete Log:", message.split(":")[-1].strip(), soft_wrap=True)
            return

    def _start_conda_status(self, env_name: str):
        """Start a spinning status for conda environment creation."""
        status = Status(
            f"Creating conda environment [cyan]{env_name}[/cyan]...",
            console=self.console,
            spinner="dots",
        )
        status.start()
        self.conda_statuses[env_name] = status

    def _complete_conda_status(self, env_name: str):
        """Complete the conda environment creation status."""
        if env_name in self.conda_statuses:
            status = self.conda_statuses[env_name]
            self.console.log(
                f"[green]◉ Created[/] conda environment [cyan]{env_name}[/cyan]"
            )
            status.stop()
            del self.conda_statuses[env_name]

        else:
            self.console.log(
                f"[green]◉ Created[/] conda environment [cyan]{env_name}[/cyan]"
            )
            return

    def close(self):
        """Clean up any active statuses."""
        for status in self.conda_statuses.values():
            status.stop()
        self.conda_statuses.clear()
        self.progress_display.progress.stop()
        self.progress_display.live_display.stop()

    def should_log_message(self, record, message):
        """Determine if we should log this message based on content filtering."""

        if message == "None":
            return False

        if record.levelno >= logging.ERROR:
            return True

        skip_patterns = [
            "^Select jobs to execute",
            "^Assuming unrestricted shared filesystem",
            "^Using shell:",
            "^host:",
            "^Provided cores:",
            "^Rules claiming more threads will be",
            r"^Execute \d+ jobs.",
            "^Building DAG of jobs.",
            "^Activating conda env",
        ]

        for pattern in skip_patterns:
            if re.search(pattern, message):
                return False

        return True