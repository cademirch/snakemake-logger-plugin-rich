from snakemake_interface_logger_plugins.base import LogHandlerBase
from snakemake_logger_plugin_rich.handler import (
    RichLogHandler,
    RichFormatter,
    RichFilter,
)
from rich.console import Console


class LogHandler(LogHandlerBase, RichLogHandler):
    def __post_init__(self) -> None:
        """
        Any additional setup after initialization.
        """
        console = Console(
            stderr=not self.common_settings.stdout,
        )
        RichLogHandler.__init__(self, console=console, settings=self.common_settings)
        self.setFormatter(RichFormatter(console, self.common_settings.printshellcmds))
        self.addFilter(RichFilter())

    @property
    def writes_to_stream(self) -> bool:
        """
        Whether this plugin writes to stderr/stdout
        """
        return True

    @property
    def writes_to_file(self) -> bool:
        """
        Whether this plugin writes to a file
        """
        return False

    @property
    def has_filter(self) -> bool:
        """
        Whether this plugin attaches its own filter
        """
        return True

    @property
    def has_formatter(self) -> bool:
        """
        Whether this plugin attaches its own formatter
        """
        return True