from logging import LogRecord
from typing import Optional
from uuid import UUID

from snakemake_interface_logger_plugins.common import LogEvent

import snakemake_logger_plugin_rich.events as events
from snakemake_logger_plugin_rich.console import Console


def format_wildcards(wildcards):
    """Format wildcards into a string representation."""
    if not wildcards:
        return ""

    wildcards_str = ", ".join(f"{k}={v}" for k, v in wildcards.items())
    return f" | wildcards: {wildcards_str}"


class EventHandler:
    """Base class for processing Snakemake log events."""

    def __init__(
        self,
        console: Console,
        dryrun: bool = False,
    ):
        self.current_workflow_id: Optional[UUID] = None
        self.dryrun: bool = dryrun
        self.console = console
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
        self.console.add_log(f"Workflow started: {event_data.workflow_id}")

    def handle_job_info(self, event_data: events.JobInfo, **kwargs) -> None:
        """Handle job info event."""
        self.jobs_info[event_data.jobid] = {
            "rule_name": event_data.rule_name,
            "wildcards": event_data.wildcards,
        }
        wildcards_str = format_wildcards(event_data.wildcards)
        message = f"Submitted job {event_data.jobid} (Rule: {event_data.rule_name}{wildcards_str})"
        self.console.add_log(message)

    def handle_job_started(self, event_data: events.JobStarted, **kwargs) -> None:
        """Handle job started event."""
        pass

    def handle_job_finished(self, event_data: events.JobFinished, **kwargs) -> None:
        """Handle job finished event."""
        job_id = event_data.job_id

        if job_id in self.jobs_info:
            info = self.jobs_info[job_id]
            rule_name = info["rule_name"]

            if rule_name in self.rule_counts:
                self.rule_counts[rule_name]["completed"] += 1

            self.console.add_log(f"Finished job {job_id} (Rule: {rule_name})")
            self.console.add_or_update_progress(
                rule=f"Rule: {rule_name}",
                completed=self.rule_counts[rule_name]["completed"],
                total=self.rule_counts[rule_name]["total"],
            )

    def handle_shellcmd(self, event_data: events.ShellCmd, **kwargs) -> None:
        """Handle shell command event."""
        pass

    def handle_job_error(self, event_data: events.JobError, **kwargs) -> None:
        """Handle job error event."""
        self.console.add_log(
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
        """Handle run info event."""
        for rule, count in event_data.per_rule_job_counts.items():
            if count > 0:
                self.rule_counts[rule] = {"total": count, "completed": 0}
                self.console.add_or_update_progress(
                    rule=f"Rule: {rule}", completed=0, total=count
                )

    def handle_generic_event(
        self, event_type: LogEvent, record: LogRecord, **kwargs
    ) -> None:
        """Handle events that don't have a specific handler defined.

        Subclasses can override this method to provide custom handling for
        unusual or unrecognized event types.
        """
        pass

    def handle_generic_record(self, record: LogRecord, **kwargs) -> None:
        """Handle log records that don't have an event type.

        Subclasses can override this method to handle non-event log records.
        """
        pass
