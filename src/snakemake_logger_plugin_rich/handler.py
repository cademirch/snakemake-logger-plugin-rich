import logging
from typing import Optional
from rich.logging import RichHandler
from snakemake_interface_logger_plugins.settings import OutputSettingsLoggerInterface
from snakemake_interface_logger_plugins.common import LogEvent
from snakemake_logger_plugin_rich.console import Console
from snakemake_logger_plugin_rich.event_handler import EventHandler


class RichLogHandler(RichHandler):
    """
    A Snakemake logger that displays job information and
    shows progress bars for rules.
    """

    def __init__(
        self,
        settings: Optional[OutputSettingsLoggerInterface] = None,
        *args,
        **kwargs,
    ):
        self.console = Console()
        self.event_handler = EventHandler(console=self.console)
        kwargs["console"] = self.console.rich_console
        kwargs["show_path"] = True
        kwargs["show_time"] = True
        kwargs["omit_repeated_times"] = False
        kwargs["rich_tracebacks"] = True
        kwargs["tracebacks_width"] = 100
        kwargs["tracebacks_show_locals"] = False
        super().__init__(*args, **kwargs)

        self.settings = settings

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
        super().close()