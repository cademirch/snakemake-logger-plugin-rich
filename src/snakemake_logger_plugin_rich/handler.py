import logging
from rich.logging import RichHandler
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.console import Console
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
        self.console = Console(log_path=False)
        self.progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(complete_style="green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
            auto_refresh=False,
            disable=True,
        )

        self.event_handler = EventHandler(
            console=self.console,
            progress=self.progress,
            dryrun=self.settings.dryrun,
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
