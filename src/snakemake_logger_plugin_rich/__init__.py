from snakemake_interface_logger_plugins.base import LoggerPluginBase
from snakemake_logger_plugin_rich.handler import (
    RichLogHandler,
    RichFormatter,
    RichFilter,
)
from rich.console import Console
from logging import Handler


class LoggerPlugin(LoggerPluginBase):
    def __post__init(self) -> None:
        """
        Any additional setup after initialization.
        """

    def create_handler(
        self,
        quiet,
        printshellcmds: bool,
        printreason: bool,
        debug_dag: bool,
        nocolor: bool,
        stdout: bool,
        debug: bool,
        mode,
        show_failed_logs: bool,
        dryrun: bool,
    ) -> Handler:
        """
        Creates and returns an instance of RichLogHandler.
        """
        console = Console(
            stderr=not stdout,
        )
        handler = RichLogHandler(
            console,
            quiet=quiet,
            printshellcmds=printshellcmds,
            printreason=printreason,
            debug_dag=debug_dag,
            nocolor=nocolor,
            stdout=stdout,
            debug=debug,
            mode=mode,
            show_failed_logs=show_failed_logs,
            dryrun=dryrun,
            show_time=True,
            show_path=True,
            markup=True,
        )
        FORMAT = RichFormatter(console, printshellcmds=printshellcmds)
        filterer = RichFilter()
        handler.setFormatter(FORMAT)
        handler.addFilter(filterer)
        return handler
