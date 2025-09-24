import logging
from rich.logging import RichHandler
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    SpinnerColumn,
)
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from snakemake_interface_logger_plugins.settings import OutputSettingsLoggerInterface
from snakemake_logger_plugin_rich.event_handler import EventHandler


class RichLogHandler(RichHandler):
    """
    A Snakemake logger that displays job information and
    shows progress bars for rules.
    """

    def __init__(
        self,
        settings: OutputSettingsLoggerInterface,
        *args,
        **kwargs,
    ):
        self.settings = settings
        self.console = Console(log_path=False, stderr=True)
        self.progress = Progress(
            SpinnerColumn(
                spinner_name="dots", style="default", finished_text="[dim green]✓"
            ),
            TextColumn("{task.fields[active]}", style="default"),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(
                bar_width=None, complete_style="green", finished_style="dim green"
            ),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
            expand=True,
            auto_refresh=False,
            disable=True,
        )

        self.live_display = Live(
            Panel(
                self.progress,
                title="Workflow Progress",
                border_style="dim",
                padding=(0, 1, 0, 1),
            ),
            refresh_per_second=8,
            transient=True,
            console=self.console,
        )

        self.event_handler = EventHandler(
            console=self.console,
            progress=self.progress,
            live_display=self.live_display,
            dryrun=self.settings.dryrun,
            printshellcmds=self.settings.printshellcmds,
            show_failed_logs=settings.show_failed_logs,
            verbose=self.settings.verbose,
        )

        kwargs["console"] = self.console
        kwargs["show_time"] = True
        kwargs["omit_repeated_times"] = False
        kwargs["rich_tracebacks"] = True
        kwargs["tracebacks_width"] = 100
        kwargs["tracebacks_show_locals"] = False
        super().__init__(*args, **kwargs)

    def emit(self, record):
        """Process log records and delegate to event handler."""
        try:
            self.event_handler.handle(record)

        except Exception as e:
            self.handleError(
                logging.LogRecord(
                    name="RichLogHanlder",
                    level=logging.ERROR,
                    pathname="",
                    lineno=0,
                    msg=f"Error in logging handler: {str(e)}",
                    args=(),
                    exc_info=None,
                )
            )

    def close(self):
        """Clean up resources."""
        self.event_handler.close()
        super().close()
