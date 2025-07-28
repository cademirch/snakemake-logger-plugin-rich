from logging import LogRecord
from typing import Optional
from uuid import UUID
from rich.console import Console
from rich.syntax import Syntax
from rich.progress import Progress, TaskID
from rich.table import Table
from rich import box
from typing import Dict
from snakemake_interface_logger_plugins.common import LogEvent
import snakemake_logger_plugin_rich.events as events
import re
import logging


def format_wildcards(wildcards):
    """Format wildcards into a string representation."""
    if not wildcards:
        return None

    wc_table = Table(
        show_header=False,
        pad_edge=False,
        show_edge=False,
        padding=(0, 0),
        box=box.SIMPLE,
    )
    wc_table.add_column("wildcard", justify="left", no_wrap=True)
    wc_table.add_column("value", justify="left")
    for k, v in wildcards.items():
        wc_table.add_row(f"[italic]{k}[/] : ", v)
    return wc_table


class ProgressDisplay:
    def __init__(self, progress: Progress):
        self.progress = progress
        self.rule_tasks: Dict[str, TaskID] = {}

    def add_or_update(
        self, rule: str, completed: int, total: int, visible: bool = True
    ):
        if rule not in self.rule_tasks:
            task_id = self.progress.add_task(
                description=rule, total=total, visible=visible
            )
            self.rule_tasks[rule] = task_id
        else:
            task_id = self.rule_tasks[rule]

        self.progress.update(task_id, completed=completed, total=total, refresh=True)
        return task_id

    def mark_rule_completed(self, rule: str):
        """Mark a rule as completed with checkmark."""
        if rule in self.rule_tasks:
            task_id = self.rule_tasks[rule]
            self.progress.update(
                task_id,
                description=f"[dim green]✓[/] [dim default]{rule}[/]",
                refresh=True,
            )

    def mark_rule_failed(self, rule: str):
        """Update progress bar for a failed rule."""
        if rule in self.rule_tasks:
            task_id = self.rule_tasks[rule]
            self.progress.update(
                task_id, description=f"[red]✗[/] {rule} [red](failed)[/]", refresh=True
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
        self.progress_display = ProgressDisplay(progress)
        self.jobs_info = {}
        self.rule_counts = {}  # {rule_name: {"total": n, "completed": m}}

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
        self.console.log(f"Workflow started: {event_data.workflow_id}")

    def handle_job_info(self, event_data: events.JobInfo, **kwargs) -> None:
        """Handle job info event with rich formatting."""

        self.jobs_info[event_data.jobid] = {
            "rule": event_data.rule_name,
            "wildcards": event_data.wildcards,
        }

        self.progress_display.set_visible(event_data.rule_name, True)

        # Create rich formatted output
        table = Table(
            show_header=False,
            pad_edge=False,
            show_edge=False,
            padding=(0, 2, 0, 0),
            box=box.SIMPLE,
        )
        table.add_column(
            "detail", justify="left", style="bold light_steel_blue", no_wrap=True
        )
        table.add_column("value", justify="left")

        table.add_row(
            "  Rule: ", event_data.rule_name + f" [dim](id: {event_data.jobid})[/]"
        )

        wc_table = format_wildcards(event_data.wildcards)
        if wc_table:
            table.add_row("  Wildcards: ", wc_table)

        if event_data.rule_msg:
            table.add_row("  Message: ", event_data.rule_msg)

        self.console.log("Submitted", style="bold light_steel_blue")
        self.console.log(table)

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

                if completed >= total:
                    self.progress_display.mark_rule_completed(rule_name)
                else:
                    self.progress_display.add_or_update(rule_name, completed, total)

                if self.total_progress:
                    self.progress_display.progress.update(
                        self.total_progress, advance=1
                    )

            table = Table(
                show_header=False,
                pad_edge=False,
                show_edge=False,
                padding=(0, 0),
                box=box.SIMPLE,
            )
            table.add_column("status", justify="left", style="bold green", no_wrap=True)
            table.add_column("detail", justify="left")
            table.add_column("value", justify="left")

            table.add_row("  Rule", info["rule"] + f" [dim](id: {job_id})[/]")
            wc_table = format_wildcards(info["wildcards"])
            if wc_table:
                table.add_row("  Wildcards: ", wc_table)

            self.console.log("Finished", style="bold green")
            self.console.log(table)

    def handle_shellcmd(self, event_data: events.ShellCmd, **kwargs) -> None:
        """Handle shell command event with syntax highlighting."""
        if event_data.shellcmd:
            format_cmd = re.sub(
                "^\n", "", re.sub(r" +", " ", event_data.shellcmd)
            ).rstrip()
            shell_table = Table(
                show_header=False,
                pad_edge=False,
                show_edge=False,
                padding=(0, 0),
                box=box.SIMPLE,
            )
            shell_table.add_column("detail", justify="left", style="light_steel_blue")
            shell_table.add_column("value", justify="left")
            shell_table.add_row(
                "  Shell: ",
                Syntax(format_cmd, lexer="bash", padding=1, theme="paraiso-dark"),
            )
            self.console.log(shell_table)

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
        total_jobs = event_data.total_job_count
        if total_jobs > 0:
            self.total_progress = self.progress_display.add_or_update(
                "Total", 0, total_jobs
            )
            self.console.rule(f"Workflow: {total_jobs} jobs", style="dim green")

        for rule, count in event_data.per_rule_job_counts.items():
            if count > 0:
                self.rule_counts[rule] = {"total": count, "completed": 0}
                self.progress_display.add_or_update(rule, 0, count, visible=False)

    def handle_generic_event(
        self, event_type: LogEvent, record: LogRecord, **kwargs
    ) -> None:
        """Handle events that don't have a specific handler defined.

        Subclasses can override this method to provide custom handling for
        unusual or unrecognized event types.
        """
        pass

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

    def handle_generic_record(self, record: LogRecord, **kwargs) -> None:
        """Handle log records that don't have an event type.

        Subclasses can override this method to handle non-event log records.
        """
        pass
