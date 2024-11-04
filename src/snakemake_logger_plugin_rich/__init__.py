from snakemake_interface_logger_plugins.base import LoggerPluginBase
from snakemake_logger_plugin_rich.handler import RichLogHandler
from logging import Handler, Formatter


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
        Creates and returns an instance of RichLogHandler, configured with plugin settings.
        """
        # Initialize RichLogHandler with plugin settings
        handler = RichLogHandler(
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
            show_path=False,
            markup=False,
        )
        FORMAT = Formatter("%(message)s")
        handler.setFormatter(FORMAT)
        return handler
