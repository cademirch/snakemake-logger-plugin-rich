from rich.console import Console as RichConsole, RenderableType
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TaskID
from rich.layout import Layout
from rich.text import Text
from rich.live import Live
from typing import Dict, Optional


class Console:
    def __init__(
        self, rich_console: Optional[RichConsole] = None, dryrun: bool = False
    ):
        self.rich_console = rich_console or RichConsole()
        self.log_messages = []
        self.max_log_messages = 15

        self.rule_tasks: Dict[str, TaskID] = {}

        self.progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(complete_style="green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.rich_console,
            transient=False,
            auto_refresh=False,
        )

        self.logs_panel = Panel(Text(""), title="Logs", border_style="blue")
        self.progress_panel = Panel(
            self.progress, title="Rule Progress", border_style="green"
        )

        self.layout = Layout()
        self.layout.split_column(
            Layout(self.logs_panel, name="logs", size=15),
            Layout(self.progress_panel, name="progress", size=10),
        )

        self.live = Live(
            self.layout,
            console=self.rich_console,
            refresh_per_second=4,
            auto_refresh=False,
            vertical_overflow="crop",
        )
        self.live.start()

    def add_log(self, message: str, style: Optional[str] = None):
        """Add a message to the log panel."""
        text = Text(message, style=style) if style else Text(message)
        self.log_messages.append(text)
        self.log_messages = self.log_messages[-self.max_log_messages :]
        self._update_log_panel()

    def _update_log_panel(self):
        log_text = Text("\n").join(self.log_messages)
        self.logs_panel.renderable = log_text
        self.live.refresh()

    def add_or_update_progress(self, rule: str, completed: int, total: int):
        """Add or update a progress bar for a rule."""
        if rule not in self.rule_tasks:
            task_id = self.progress.add_task(description=rule, total=total)
            self.rule_tasks[rule] = task_id
        else:
            task_id = self.rule_tasks[rule]

        self.progress.update(task_id, completed=completed, total=total)
        self._update_progress_panel()

    def mark_rule_failed(self, rule: str):
        """Update progress bar for a failed rule."""
        if rule in self.rule_tasks:
            task_id = self.rule_tasks[rule]

            self.progress.update(task_id, description=f"[red]{rule} (failed)[/red]")
        self._update_progress_panel()

    def _update_progress_panel(self):
        self.progress_panel.renderable = self.progress
        self.live.refresh()

    def close(self):
        self.live.stop()
