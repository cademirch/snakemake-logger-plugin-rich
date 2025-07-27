import logging
import re
from typing import Dict, Type, Optional, List
from rich.logging import RichHandler
#from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.console import Console, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import box
from rich.layout import Layout
from rich.text import Text
from pydantic import BaseModel
from snakemake_interface_logger_plugins.settings import OutputSettingsLoggerInterface
from snakemake_interface_logger_plugins.common import LogEvent


from snakemake_logger_plugin_rich.parsers import (
    WorkflowStarted,
    JobInfo,
    JobStarted,
    JobFinished,
    ShellCmd,
    JobError,
    GroupInfo,
    GroupError,
    ResourcesInfo,
    DebugDag,
    Progress as ProgressModel,
    RuleGraph,
    RunInfo,
)

class RichLogHandler(RichHandler):
    """
    A Snakemake logger that displays job information and
    shows progress bars for rules.
    """

    def __init__(
        self,
        console: Console,
        settings: OutputSettingsLoggerInterface,
        *args,
        **kwargs,
    ):
        
        kwargs["console"] = console
        kwargs["show_path"] = False
        kwargs["show_time"] = True
        kwargs["omit_repeated_times"] = False
        kwargs["rich_tracebacks"] = True
        kwargs["tracebacks_width"] = 100
        kwargs["tracebacks_show_locals"] = False
        super().__init__(*args, **kwargs)

        
        self.console = Console(stderr=True, log_path=False)
        self.settings = settings

        
        self.jobs_info = {}  

        
        self.progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(complete_style="green", finished_style="dim green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
            transient = True,
            auto_refresh = True,
        )

        
        self.rule_tasks = {}  
        self.total_jobs = {}  
        self.done_jobs = {}  

        
        self.log_messages: List[RenderableType] = []

        self.max_log_messages = 15  

        
        #self.logs_panel = Panel(Text(""), title="Logs", border_style="none")
        self.progress_panel = Panel(
            self.progress, title="Progress", border_style="dim"
        )
#
        #self.layout = Layout()
        #self.layout.split_column(
        #    Layout(self.logs_panel, name="logs", size=15),  
        #    Layout(self.progress_panel, name="progress"),  
        #)

        
        self.live = Live(
            self.progress_panel,
            console=self.console,
            refresh_per_second=8,
            auto_refresh=True,
            vertical_overflow="crop",
        )
        self.live.start()

        
        self.parsers: Dict[LogEvent, Type[BaseModel]] = {
            LogEvent.WORKFLOW_STARTED: WorkflowStarted,
            LogEvent.JOB_INFO: JobInfo,
            LogEvent.JOB_STARTED: JobStarted,
            LogEvent.JOB_FINISHED: JobFinished,
            LogEvent.JOB_ERROR: JobError,
            LogEvent.SHELLCMD: ShellCmd,
            LogEvent.GROUP_INFO: GroupInfo,
            LogEvent.GROUP_ERROR: GroupError,
            LogEvent.RESOURCES_INFO: ResourcesInfo,
            LogEvent.DEBUG_DAG: DebugDag,
            LogEvent.PROGRESS: ProgressModel,
            LogEvent.RULEGRAPH: RuleGraph,
            LogEvent.RUN_INFO: RunInfo,
        }

    def get_event_type(self, record: logging.LogRecord) -> Optional[LogEvent]:
        """Get event type from log record."""
        if hasattr(record, "event") and isinstance(record.event, LogEvent):
            return record.event
        return None

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
            "^Building DAG of jobs."
        ]

        for pattern in skip_patterns:
            if re.search(pattern, message):
                return False

        return True

    def format_wildcards(self, wildcards):
        """Format wildcards into a string representation."""
        if not wildcards:
            return None

        wc_table = Table(show_header=False,pad_edge=False, show_edge=False, padding = (0,0), box=box.SIMPLE)
        wc_table.add_column("wildcard", justify="left", no_wrap=True)
        wc_table.add_column("value", justify="left")
        for k,v in wildcards.items():
            wc_table.add_row(f"[italic]{k}[/] : ", v)
        return wc_table
        #TODO remove deprecated
        #return ", ".join(f"[italic]{k}[/]: {v}" for k, v in wildcards.items())

    def truncate_message(self, message, max_length=100):
        """Truncate message to fit within max_length characters."""
        #TODO FLAGGED FOR REMOVAL SINCE CONSOLE HANDLES THIS
        if len(message) <= max_length:
            return message
        return message[: max_length - 3] + "..."

    def create_custom_message(self, record, event_type):
        """Create custom formatted messages for specific event types."""
        if event_type == LogEvent.JOB_INFO:
            try:

                parser = self.parsers[event_type]
                job_info = parser.from_record(record)

                self.jobs_info[job_info.jobid] = {
                    "rule": job_info.rule_name,
                    "wildcards": job_info.wildcards
                }
                # reveal progress bar for this rule if it's not already
                self.progress.update(self.rule_tasks[job_info.rule_name], visible=True)

                table = Table(show_header=False,pad_edge=False, show_edge=False, padding = (0,0), box=box.SIMPLE)
                table.add_column("detail", justify="left", style="light_steel_blue", no_wrap=True)
                table.add_column("value", justify="left")
                table.add_row("Submitted: ", job_info.rule_name + f" [dim](id: {job_info.jobid})[/]")
                _wc = self.format_wildcards(job_info.wildcards)
                if _wc:
                    table.add_row("Wildcards: ", _wc)

                return table

            except Exception as e:
                return f"Error parsing job info: {str(e)}"

        elif event_type == LogEvent.JOB_FINISHED:
            try:

                parser = self.parsers[event_type]
                job_finished = parser.from_record(record)
                table = Table(show_header=False,pad_edge=False, show_edge=False, padding = (0,0), box=box.SIMPLE)
                table.add_column("detail", justify="left", style="green", no_wrap=True)
                table.add_column("value", justify="left")

                job_id = job_finished.job_id
                if job_id in self.jobs_info:
                    info = self.jobs_info[job_id]
                    _name = info["rule"]
                    _wc = self.format_wildcards(info["wildcards"])
                    table.add_row("Finished: ", _name + f" [dim](id: {job_id})[/]")
                    if _wc:
                        table.add_row("Wildcards: ", _wc)
                else:
                    table.add_row("Finished: ", f"job {job_id}[/]")

                return table


            except Exception as e:
                return f"Error creating job finished message: {str(e)}"

        elif event_type == LogEvent.SHELLCMD:
            parser = self.parsers[event_type]
            shellcmd = parser.from_record(record)
            format_cmd = re.sub('^\n', '', re.sub(r' +', ' ', shellcmd.shellcmd)).rstrip()
            return Syntax(format_cmd, lexer = "bash", padding=1)

        elif event_type == LogEvent.JOB_ERROR:
            try:
                
                parser = self.parsers[event_type]
                job_error = parser.from_record(record)

                
                return (
                    f"[bold red]ERROR[/bold red] in job {job_error.jobid}: Job failed"
                )

            except Exception as e:
                return f"Error parsing job error: {str(e)}"

        elif event_type == LogEvent.RUN_INFO:
            try:
                
                parser = self.parsers[event_type]
                run_info = parser.from_record(record)
                total = run_info.stats['total']
                self.total_progress = self.progress.add_task("Total", total = total)
                return f"Workflow: {run_info.stats['total']} jobs"

            except Exception as e:
                return f"Error parsing run info: {str(e)}"

        
        return None

    #def add_to_log_display(self, message, style=None):
    #    """Add a message to the log display panel."""
    #    
    #    if isinstance(message, str):
    #        if style:
    #            message = Text(message, style=style)
    #        else:
    #            message = Text(message)
#
    #    
    #    elif (
    #        isinstance(message, dict) and "message" in message and "command" in message
    #    ):
    #        
    #        #self.log_messages.append(Text(message["message"]))
    #        self.console.log(message["message"])
#
#
    #        #cmd_text = Markdown(f"""```bash\n{message["command"]}\n```""")
    #        cmd_text = Text("    " + message["command"], style="yellow")
    #        #self.log_messages.append(cmd_text)
    #        self.console.log(cmd_text)
    #        #self.update_log_panel()
    #        return
#
    #    
    #    self.log_messages.append(message)
#
    #    
    #    self.log_messages = self.log_messages[-self.max_log_messages :]
#
    #    
    #    self.update_log_panel()

    def update_log_panel(self):
        """Update the log panel with the current log messages."""
        if not self.log_messages:
            return

        
        log_text = Text("\n").join(self.log_messages)
                
        self.console.log(log_text)

        
        self.live.refresh()

    def emit(self, record):
        """Process log records and update progress bars."""
        try:
            
            event_type = self.get_event_type(record)

            
            message = self.format(record)

            
            if not self.should_log_message(record, message):
                pass
            else:
                
                if record.levelno >= logging.ERROR and not event_type:
                    
                    self.console.log(message, style="bold red")
                
                elif event_type:
                    custom_message = self.create_custom_message(record, event_type)
                    if event_type == LogEvent.RUN_INFO:
                        self.console.rule(custom_message, style= "dim green")
                        return
                    if custom_message is False:
                        
                        pass
                    elif custom_message is not None:
                        
                        self.console.log(custom_message)

                    else:
                        self.console.log(message)
                else:
                    self.console.log(message)

            
            if event_type == LogEvent.RUN_INFO:
                self.handle_run_info(record)
            elif event_type == LogEvent.JOB_INFO:
                self.handle_job_info(record)
            elif event_type == LogEvent.JOB_FINISHED:
                self.handle_job_finished(record)
            elif event_type == LogEvent.JOB_ERROR:
                self.handle_job_error(record)

        except Exception as e:
            
            self.console.log(
                f"Error in logging handler: {str(e)}", style="bold red"
            )

    def handle_run_info(self, record):
        """Handle RUN_INFO events to set up progress bars."""
        try:
            parser = self.parsers[LogEvent.RUN_INFO]
            run_info = parser.from_record(record)

            stats = run_info.stats
            if stats:
                for rule, count in stats.items():
                    if rule != "total" and count > 0:
                        if rule not in self.rule_tasks:
                            task_id = self.progress.add_task(
                                f"{rule}", total=count,
                                visible= False
                            )
                            self.rule_tasks[rule] = task_id
                            self.total_jobs[rule] = count
                            self.done_jobs[rule] = 0
        except Exception as e:
            self.console.log(
                f"Error parsing run info: {str(e)}", style="bold red"
            )

    def handle_job_info(self, record):
        """Handle JOB_INFO events for progress tracking."""
        try:
            parser = self.parsers[LogEvent.JOB_INFO]
            job_info = parser.from_record(record)

            
            rule_name = job_info.rule_name
            self.console.log(job_info)

            if rule_name not in self.rule_tasks:
                task_id = self.progress.add_task(f"{rule_name}", total=1)
                self.rule_tasks[rule_name] = task_id
                self.total_jobs[rule_name] = 1
                self.done_jobs[rule_name] = 0
        except Exception as e:
            self.console.log(
                f"Error parsing job info: {str(e)}", style="bold red"
            )

    def handle_job_finished(self, record):
        """Handle JOB_FINISHED events to update progress."""
        try:
            parser = self.parsers[LogEvent.JOB_FINISHED]
            job_finished = parser.from_record(record)

            
            job_id = job_finished.job_id

            if job_id in self.jobs_info:
                rule_name = self.jobs_info[job_id]["rule"]

                if rule_name in self.rule_tasks:
                    self.done_jobs[rule_name] = self.done_jobs.get(rule_name, 0) + 1

                    
                    task_id = self.rule_tasks[rule_name]
                    done = self.done_jobs[rule_name]
                    total = self.total_jobs[rule_name]

                    
                    if done >= total:
                        self.progress.update(
                            task_id,
                            completed=total,
                            description=f"[dim green]✓[/] [dim default]{rule_name}[/]",
                        )
                    else:
                        self.progress.update(task_id, completed=done)

                    self.progress.update(self.total_progress, advance=1)

        except Exception as e:
            self.console.log(
                f"Error parsing job finished: {str(e)}", style="bold red"
            )

    def handle_job_error(self, record):
        """Handle JOB_ERROR events to update progress bars with error state."""
        try:
            parser = self.parsers[LogEvent.JOB_ERROR]
            job_error = parser.from_record(record)

            
            job_id = job_error.jobid

            
            if job_id in self.jobs_info:
                rule_name = self.jobs_info[job_id]["rule_name"]

                if rule_name in self.rule_tasks:
                    task_id = self.rule_tasks[rule_name]
                    
                    self.progress.update(
                        task_id,
                        description=f"[red]✗[/] Rule: {rule_name} [red](failed)[/]",
                    )
        except Exception as e:
            self.console.log(
                f"Error handling job error: {str(e)}", style="bold red"
            )

    def close(self):
        """Clean up resources."""
        if hasattr(self, "live"):
            self.live.stop()
        super().close()
