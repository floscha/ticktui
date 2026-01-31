"""Main TUI application."""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Header,
    Footer,
    Static,
    ListView,
    ListItem,
    Label,
    Input,
    Button,
    TextArea,
)
from textual.binding import Binding
from textual.screen import Screen, ModalScreen
from textual import on

from .api import TickTickClient, TickTickAuth, Task, Project, TokenStorage
from .oauth import perform_oauth_flow

import asyncio


class ProjectItem(ListItem):
    """A list item representing a project."""
    
    def __init__(self, project: Project) -> None:
        super().__init__()
        self.project = project
    
    def compose(self) -> ComposeResult:
        yield Label(f"● {self.project.name}", classes="project-label")


class TaskItem(ListItem):
    """A list item representing a task."""
    
    def __init__(self, task_data: Task) -> None:
        super().__init__()
        self.task_data = task_data
    
    def compose(self) -> ComposeResult:
        # Priority indicator
        priority_colors = {0: "dim", 1: "blue", 3: "yellow", 5: "red"}
        priority_char = {0: " ", 1: "!", 3: "!!", 5: "!!!"}
        
        status_char = "✓" if self.task_data.is_completed else "○"
        priority = priority_char.get(self.task_data.priority, " ")
        
        text = f"[{priority_colors.get(self.task_data.priority, 'dim')}]{priority}[/] {status_char} {self.task_data.title}"
        yield Label(text, classes="task-label", markup=True)


class TaskDetail(Static):
    """Panel showing task details."""
    
    def __init__(self, current_task: Task = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_task = current_task
    
    def compose(self) -> ComposeResult:
        yield Static(self._render_content(), id="task-detail-content")
    
    def _render_content(self) -> str:
        if not self._current_task:
            return "[dim]No task selected[/]"
        
        lines = []
        lines.append(f"[bold]{self._current_task.title}[/bold]")
        lines.append("")
        lines.append(f"[cyan]Priority:[/] {self._current_task.priority_label}")
        lines.append(f"[cyan]Status:[/] {'Completed' if self._current_task.is_completed else 'Active'}")
        
        if self._current_task.due_date:
            lines.append(f"[cyan]Due:[/] {self._current_task.due_date.strftime('%Y-%m-%d %H:%M')}")
        
        if self._current_task.content:
            lines.append("")
            lines.append("[cyan]Description:[/]")
            lines.append(self._current_task.content)
        
        if self._current_task.tags:
            lines.append("")
            lines.append(f"[cyan]Tags:[/] {', '.join(self._current_task.tags)}")
        
        if self._current_task.items:
            lines.append("")
            lines.append("[cyan]Checklist:[/]")
            for item in self._current_task.items:
                status = "✓" if item.get("status", 0) == 1 else "○"
                lines.append(f"  {status} {item.get('title', '')}")
        
        return "\n".join(lines)
    
    def update_task(self, task: Task) -> None:
        """Update the displayed task."""
        self._current_task = task
        content = self.query_one("#task-detail-content", Static)
        content.update(self._render_content())


class HelpPanel(Static):
    """Panel showing keyboard shortcuts."""
    
    def compose(self) -> ComposeResult:
        help_text = """[bold cyan]Navigation[/]
[yellow]j/↓[/] Move down    [yellow]k/↑[/] Move up
[yellow]h/←[/] Projects     [yellow]l/→[/] Tasks
[yellow]Tab[/] Next panel   [yellow]S-Tab[/] Previous

[bold cyan]Actions[/]
[yellow]n[/] New task       [yellow]e[/] Edit task
[yellow]c[/] Complete       [yellow]d[/] Delete
[yellow]r[/] Refresh        [yellow]?[/] Help

[bold cyan]General[/]
[yellow]q[/] Quit           [yellow]Esc[/] Cancel"""
        yield Static(help_text, classes="help-content", markup=True)


class NewTaskModal(ModalScreen):
    """Modal for creating a new task."""
    
    CSS = """
    NewTaskModal {
        align: center middle;
    }
    
    NewTaskModal > Vertical {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    
    NewTaskModal Input {
        width: 100%;
        margin-bottom: 1;
    }
    
    NewTaskModal TextArea {
        height: 5;
        margin-bottom: 1;
    }
    
    NewTaskModal Horizontal {
        width: 100%;
        height: auto;
        align: right middle;
    }
    
    NewTaskModal Button {
        margin-left: 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, project_id: str) -> None:
        super().__init__()
        self.project_id = project_id
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]New Task[/bold]", markup=True)
            yield Input(placeholder="Task title", id="task-title")
            yield TextArea(id="task-content")
            with Horizontal():
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Create", variant="primary", id="create")
    
    def action_cancel(self) -> None:
        self.dismiss(None)
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
    
    @on(Button.Pressed, "#create")
    def on_create(self) -> None:
        title = self.query_one("#task-title", Input).value
        content = self.query_one("#task-content", TextArea).text
        
        if title.strip():
            task = Task(
                id="",
                title=title.strip(),
                project_id=self.project_id,
                content=content.strip(),
            )
            self.dismiss(task)
        else:
            self.notify("Task title is required", severity="error")


class EditTaskModal(ModalScreen):
    """Modal for editing an existing task."""
    
    CSS = """
    EditTaskModal {
        align: center middle;
    }
    
    EditTaskModal > Vertical {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    
    EditTaskModal Input {
        width: 100%;
        margin-bottom: 1;
    }
    
    EditTaskModal TextArea {
        height: 5;
        margin-bottom: 1;
    }
    
    EditTaskModal Horizontal {
        width: 100%;
        height: auto;
        align: right middle;
    }
    
    EditTaskModal Button {
        margin-left: 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, task: Task) -> None:
        super().__init__()
        self.task = task
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Edit Task[/bold]", markup=True)
            yield Input(value=self.task.title, placeholder="Task title", id="task-title")
            yield TextArea(self.task.content or "", id="task-content")
            with Horizontal():
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Save", variant="primary", id="save")
    
    def action_cancel(self) -> None:
        self.dismiss(None)
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
    
    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        title = self.query_one("#task-title", Input).value
        content = self.query_one("#task-content", TextArea).text
        
        if title.strip():
            self.task.title = title.strip()
            self.task.content = content.strip()
            self.dismiss(self.task)
        else:
            self.notify("Task title is required", severity="error")


class ConfirmModal(ModalScreen):
    """Modal for confirming actions."""
    
    CSS = """
    ConfirmModal {
        align: center middle;
    }
    
    ConfirmModal > Vertical {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }
    
    ConfirmModal Horizontal {
        width: 100%;
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    
    ConfirmModal Button {
        margin-left: 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
    ]
    
    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.message)
            with Horizontal():
                yield Button("No", variant="default", id="no")
                yield Button("Yes", variant="error", id="yes")
    
    def action_cancel(self) -> None:
        self.dismiss(False)
    
    def action_confirm(self) -> None:
        self.dismiss(True)
    
    @on(Button.Pressed, "#no")
    def on_no(self) -> None:
        self.dismiss(False)
    
    @on(Button.Pressed, "#yes")
    def on_yes(self) -> None:
        self.dismiss(True)


class LoginScreen(Screen):
    """Screen for handling login/authentication."""
    
    CSS = """
    LoginScreen {
        align: center middle;
    }
    
    LoginScreen > Vertical {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2 4;
    }
    
    LoginScreen Input {
        width: 100%;
        margin-bottom: 1;
    }
    
    LoginScreen Button {
        margin-top: 1;
        margin-right: 1;
    }
    
    LoginScreen .info-text {
        margin-bottom: 1;
        text-style: dim;
    }
    
    LoginScreen .status-text {
        margin-top: 1;
        text-style: italic;
    }
    
    LoginScreen .button-row {
        width: 100%;
        height: auto;
    }
    """
    
    BINDINGS = [
        Binding("escape", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold cyan]TickTUI - TickTick Terminal UI[/bold cyan]", markup=True)
            yield Label("")
            yield Label("Enter your TickTick API credentials:", classes="info-text")
            yield Label("(Get them from https://developer.ticktick.com/manage)", classes="info-text")
            yield Label("")
            yield Input(placeholder="Client ID", id="client-id")
            yield Input(placeholder="Client Secret", password=True, id="client-secret")
            yield Label("")
            yield Label("[dim]Or enter an existing access token:[/]", markup=True)
            yield Input(placeholder="Access Token (optional)", password=True, id="access-token")
            with Horizontal(classes="button-row"):
                yield Button("Login with OAuth", variant="primary", id="oauth-login")
                yield Button("Use Token", variant="default", id="token-login")
            yield Label("", id="status-label", classes="status-text")
    
    def action_quit(self) -> None:
        self.app.exit()
    
    @on(Button.Pressed, "#oauth-login")
    async def on_oauth_login(self) -> None:
        """Start OAuth authentication flow."""
        client_id = self.query_one("#client-id", Input).value.strip()
        client_secret = self.query_one("#client-secret", Input).value.strip()
        
        if not client_id or not client_secret:
            self.notify("Client ID and Client Secret are required for OAuth", severity="error")
            return
        
        status_label = self.query_one("#status-label", Label)
        status_label.update("[yellow]Starting OAuth flow... Check your browser![/]")
        try:
            access_token, refresh_token, error = await perform_oauth_flow(
                client_id,
                client_secret,
            )
            if error:
                status_label.update(f"[red]Error: {error}[/]")
                self.notify(f"OAuth failed: {error}", severity="error")
                return
            if access_token:
                status_label.update("[green]Authorization successful![/]")
                self.app.setup_client(client_id, client_secret, access_token, refresh_token)
                self.app.switch_screen("main")
            else:
                status_label.update("[red]No access token received[/]")
                self.notify("OAuth failed: No access token", severity="error")
        except Exception as e:
            status_label.update(f"[red]Error: {e}[/]")
            self.notify(f"OAuth failed: {e}", severity="error")
    
    @on(Button.Pressed, "#token-login")
    async def on_token_login(self) -> None:
        """Login using an existing access token."""
        access_token = self.query_one("#access-token", Input).value.strip()
        
        if not access_token:
            self.notify("Please enter an access token", severity="error")
            return
        
        client_id = self.query_one("#client-id", Input).value.strip() or "manual"
        client_secret = self.query_one("#client-secret", Input).value.strip() or "manual"
        
        self.app.setup_client(client_id, client_secret, access_token)
        self.app.switch_screen("main")


class MainScreen(Screen):
    """Main application screen with lazygit-inspired layout."""
    
    CSS = """
    MainScreen {
        layout: grid;
        grid-size: 3 1;
        grid-columns: 1fr 2fr 1fr;
    }
    
    .panel {
        border: solid $primary-darken-2;
        padding: 0 1;
        height: 100%;
    }
    
    .panel.focused {
        border: solid $primary;
    }
    
    .panel-title {
        dock: top;
        padding: 0 1;
        background: $primary-darken-3;
        color: $text;
        text-style: bold;
    }
    
    ListView {
        height: 100%;
        scrollbar-gutter: stable;
    }
    
    ListView:focus {
        border: none;
    }
    
    ListItem {
        padding: 0 1;
    }
    
    ListItem.--highlight {
        background: $primary-darken-2;
    }
    
    .project-label {
        width: 100%;
    }
    
    .task-label {
        width: 100%;
    }
    
    #projects-panel {
        column-span: 1;
    }
    
    #tasks-panel {
        column-span: 1;
    }
    
    #detail-panel {
        column-span: 1;
    }
    
    #help-panel {
        height: auto;
        dock: bottom;
        padding: 1;
        background: $surface-darken-1;
    }
    
    .loading {
        text-align: center;
        padding: 2;
        text-style: dim italic;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("j", "move_down", "Down", show=False),
        Binding("k", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("h", "focus_projects", "Projects", show=False),
        Binding("l", "focus_tasks", "Tasks", show=False),
        Binding("left", "focus_projects", "Projects", show=False),
        Binding("right", "focus_tasks", "Tasks", show=False),
        Binding("tab", "focus_next_panel", "Next Panel", show=False),
        Binding("shift+tab", "focus_prev_panel", "Prev Panel", show=False),
        Binding("n", "new_task", "New Task", show=True),
        Binding("e", "edit_task", "Edit Task", show=True),
        Binding("c", "complete_task", "Complete", show=True),
        Binding("d", "delete_task", "Delete", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.projects: list[Project] = []
        self.tasks: list[Task] = []
        self.current_project: Project | None = None
        self.current_task: Task | None = None
        self._panel_order = ["projects-list", "tasks-list"]
        self._current_panel_idx = 0
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Vertical(id="projects-panel", classes="panel"):
            yield Static("Projects", classes="panel-title")
            yield ListView(id="projects-list")
        
        with Vertical(id="tasks-panel", classes="panel"):
            yield Static("Tasks", classes="panel-title")
            yield ListView(id="tasks-list")
        
        with Vertical(id="detail-panel", classes="panel"):
            yield Static("Details", classes="panel-title")
            yield TaskDetail(id="task-detail")
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Load data when screen is mounted."""
        self.query_one("#projects-panel").add_class("focused")
        await self.load_projects()
        self.query_one("#projects-list", ListView).focus()
    
    async def load_projects(self) -> None:
        """Load projects from the API."""
        projects_list = self.query_one("#projects-list", ListView)
        projects_list.clear()
        projects_list.append(ListItem(Label("[dim]Loading...[/]", markup=True)))
        
        try:
            self.projects = await self.app.client.get_projects()
            projects_list.clear()
            
            for project in self.projects:
                projects_list.append(ProjectItem(project))
            
            # Select first project
            if self.projects:
                projects_list.index = 0
                self.current_project = self.projects[0]
                await self.load_tasks(self.current_project.id)
        except Exception as e:
            projects_list.clear()
            projects_list.append(ListItem(Label(f"[red]Error: {e}[/]", markup=True)))
            self.notify(f"Failed to load projects: {e}", severity="error")
    
    async def load_tasks(self, project_id: str) -> None:
        """Load tasks for a project."""
        tasks_list = self.query_one("#tasks-list", ListView)
        tasks_list.clear()
        tasks_list.append(ListItem(Label("[dim]Loading...[/]", markup=True)))
        
        try:
            self.tasks = await self.app.client.get_project_tasks(project_id)
            tasks_list.clear()
            
            # Sort tasks: incomplete first, then by priority (high to low)
            self.tasks.sort(key=lambda t: (t.is_completed, -t.priority))
            
            for task in self.tasks:
                tasks_list.append(TaskItem(task))
            
            if not self.tasks:
                tasks_list.append(ListItem(Label("[dim]No tasks[/]", markup=True)))
            else:
                tasks_list.index = 0
                self.current_task = self.tasks[0]
                self.update_task_detail()
        except Exception as e:
            tasks_list.clear()
            tasks_list.append(ListItem(Label(f"[red]Error: {e}[/]", markup=True)))
            self.notify(f"Failed to load tasks: {e}", severity="error")
    
    def update_task_detail(self) -> None:
        """Update the task detail panel."""
        detail = self.query_one("#task-detail", TaskDetail)
        detail.update_task(self.current_task)
    
    @on(ListView.Selected, "#projects-list")
    async def on_project_selected(self, event: ListView.Selected) -> None:
        """Handle project selection."""
        if isinstance(event.item, ProjectItem):
            self.current_project = event.item.project
            await self.load_tasks(self.current_project.id)
    
    @on(ListView.Highlighted, "#projects-list")
    async def on_project_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle project highlight change."""
        if isinstance(event.item, ProjectItem):
            self.current_project = event.item.project
            await self.load_tasks(self.current_project.id)
    
    @on(ListView.Selected, "#tasks-list")
    def on_task_selected(self, event: ListView.Selected) -> None:
        """Handle task selection."""
        if isinstance(event.item, TaskItem):
            self.current_task = event.item.task_data
            self.update_task_detail()
    
    @on(ListView.Highlighted, "#tasks-list")
    def on_task_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle task highlight change."""
        if isinstance(event.item, TaskItem):
            self.current_task = event.item.task_data
            self.update_task_detail()
    
    def action_quit(self) -> None:
        self.app.exit()
    
    def action_move_down(self) -> None:
        focused = self.app.focused
        if isinstance(focused, ListView):
            focused.action_cursor_down()
    
    def action_move_up(self) -> None:
        focused = self.app.focused
        if isinstance(focused, ListView):
            focused.action_cursor_up()
    
    def action_focus_projects(self) -> None:
        self._current_panel_idx = 0
        self._update_panel_focus()
        self.query_one("#projects-list", ListView).focus()
    
    def action_focus_tasks(self) -> None:
        self._current_panel_idx = 1
        self._update_panel_focus()
        self.query_one("#tasks-list", ListView).focus()
    
    def action_focus_next_panel(self) -> None:
        self._current_panel_idx = (self._current_panel_idx + 1) % len(self._panel_order)
        self._update_panel_focus()
        self.query_one(f"#{self._panel_order[self._current_panel_idx]}", ListView).focus()
    
    def action_focus_prev_panel(self) -> None:
        self._current_panel_idx = (self._current_panel_idx - 1) % len(self._panel_order)
        self._update_panel_focus()
        self.query_one(f"#{self._panel_order[self._current_panel_idx]}", ListView).focus()
    
    def _update_panel_focus(self) -> None:
        """Update visual focus indicators on panels."""
        self.query_one("#projects-panel").remove_class("focused")
        self.query_one("#tasks-panel").remove_class("focused")
        
        if self._current_panel_idx == 0:
            self.query_one("#projects-panel").add_class("focused")
        else:
            self.query_one("#tasks-panel").add_class("focused")
    
    async def action_new_task(self) -> None:
        """Open new task modal."""
        if not self.current_project:
            self.notify("Select a project first", severity="warning")
            return
        
        def handle_result(task: Task | None) -> None:
            if task:
                asyncio.create_task(self._create_task(task))
        
        await self.app.push_screen(NewTaskModal(self.current_project.id), handle_result)
    
    async def _create_task(self, task: Task) -> None:
        """Create a task via the API."""
        try:
            await self.app.client.create_task(task)
            self.notify(f"Created: {task.title}")
            await self.load_tasks(self.current_project.id)
        except Exception as e:
            self.notify(f"Failed to create task: {e}", severity="error")
    
    async def action_edit_task(self) -> None:
        """Open edit task modal."""
        if not self.current_task:
            self.notify("Select a task first", severity="warning")
            return
        
        def handle_result(task: Task | None) -> None:
            if task:
                asyncio.create_task(self._update_task(task))
        
        await self.app.push_screen(EditTaskModal(self.current_task), handle_result)
    
    async def _update_task(self, task: Task) -> None:
        """Update a task via the API."""
        try:
            await self.app.client.update_task(task)
            self.notify(f"Updated: {task.title}")
            await self.load_tasks(self.current_project.id)
        except Exception as e:
            self.notify(f"Failed to update task: {e}", severity="error")
    
    async def action_complete_task(self) -> None:
        """Mark current task as complete."""
        if not self.current_task:
            self.notify("Select a task first", severity="warning")
            return
        
        if self.current_task.is_completed:
            self.notify("Task already completed", severity="warning")
            return
        
        try:
            await self.app.client.complete_task(
                self.current_task.project_id,
                self.current_task.id
            )
            self.notify(f"Completed: {self.current_task.title}")
            await self.load_tasks(self.current_project.id)
        except Exception as e:
            self.notify(f"Failed to complete task: {e}", severity="error")
    
    async def action_delete_task(self) -> None:
        """Delete current task with confirmation."""
        if not self.current_task:
            self.notify("Select a task first", severity="warning")
            return
        
        def handle_confirm(confirmed: bool) -> None:
            if confirmed:
                asyncio.create_task(self._delete_task())
        
        await self.app.push_screen(
            ConfirmModal(f"Delete task '{self.current_task.title}'?"),
            handle_confirm
        )
    
    async def _delete_task(self) -> None:
        """Delete the current task via the API."""
        try:
            await self.app.client.delete_task(
                self.current_task.project_id,
                self.current_task.id
            )
            self.notify(f"Deleted: {self.current_task.title}")
            await self.load_tasks(self.current_project.id)
        except Exception as e:
            self.notify(f"Failed to delete task: {e}", severity="error")
    
    async def action_refresh(self) -> None:
        """Refresh the current view."""
        if self.current_project:
            await self.load_tasks(self.current_project.id)
        await self.load_projects()
        self.notify("Refreshed")
    
    def action_show_help(self) -> None:
        """Toggle help display."""
        self.notify("j/k: navigate | n: new | e: edit | c: complete | d: delete | r: refresh | q: quit")


class TickTUIApp(App):
    """Main TickTUI Application."""
    
    TITLE = "TickTUI"
    
    CSS = """
    Screen {
        background: $surface;
    }
    """
    
    SCREENS = {
        "login": LoginScreen,
        "main": MainScreen,
    }
    
    def __init__(self) -> None:
        super().__init__()
        self.client: TickTickClient | None = None
        self.auth: TickTickAuth | None = None
        self.token_storage = TokenStorage()
    
    async def on_mount(self) -> None:
        """Check for saved tokens and route to appropriate screen."""
        tokens = self.token_storage.load()
        
        if tokens.get("access_token"):
            # Try to use saved token
            self.setup_client("", "", tokens["access_token"])
            self.push_screen("main")
        else:
            self.push_screen("login")
    
    def setup_client(self, client_id: str, client_secret: str, access_token: str, refresh_token: str = None) -> None:
        """Set up the TickTick client with credentials."""
        self.auth = TickTickAuth(client_id, client_secret)
        self.auth.access_token = access_token
        self.client = TickTickClient(self.auth)
        
        # Save tokens for next time
        self.token_storage.save(access_token, refresh_token)
    
    async def on_unmount(self) -> None:
        """Clean up when app closes."""
        if self.client:
            await self.client.close()


def main():
    """Entry point for the application."""
    app = TickTUIApp()
    app.run()


if __name__ == "__main__":
    main()
