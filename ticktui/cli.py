"""TickTUI CLI.

Implements the command surface described in README.md.

Notes / assumptions:
- TickTick "lists" map to TickTick "projects" via the Open API.
- "folders" map to TickTick "groups"; the Open API coverage is limited here.
- "tags" support isn't clearly available in the Open API; we provide best-effort
  behavior with clear errors when unsupported.

The CLI intentionally keeps dependencies minimal (stdlib argparse).
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional

from ticktui.api import Task, TickTickAuth, TickTickClient, TokenStorage


@dataclass(frozen=True)
class ExitCode:
    OK: int = 0
    ERROR: int = 1


def _parse_date_or_datetime(value: str) -> datetime:
    """Parse a date or datetime.

    Supported inputs:
    - YYYY-MM-DD           -> treated as all-day due date at 00:00 local
    - ISO-8601 datetime    -> passed to datetime.fromisoformat

    Returns timezone-aware datetime when possible.
    """

    value = value.strip()

    # Date-only
    try:
        d = date.fromisoformat(value)
    except ValueError:
        d = None

    if d is not None:
        # Use midnight local time (naive) — TickTick accepts ISO strings.
        return datetime.combine(d, time.min)

    # Datetime
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            "Invalid date/datetime. Use YYYY-MM-DD or ISO-8601 datetime."
        ) from e

    # If user provided a naive datetime, keep it naive.
    return dt


async def _build_client_from_tokens() -> TickTickClient:
    storage = TokenStorage()
    tokens = storage.load()
    access_token = tokens.get("access_token")
    if not access_token:
        raise RuntimeError(
            "Not logged in. Run the TUI once to authenticate, or store an access_token in ~/.config/ticktui/tokens.json"
        )

    # For the Open API calls we only need an access token.
    auth = TickTickAuth(client_id="", client_secret="")
    auth.access_token = access_token
    return TickTickClient(auth)


async def cmd_tasks_list(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        tasks = await client.get_all_tasks()

        if not args.show_completed:
            tasks = [t for t in tasks if not t.is_completed]

        if args.list_name:
            project = await client.resolve_project_by_name(args.list_name)
            tasks = [t for t in tasks if t.project_id == project.id]

        folder = args.folder
        if folder:
            # Folder support is group-based; best-effort filter by group name.
            tasks = await client.filter_tasks_by_folder_name(tasks, folder_name=folder)

        for t in tasks:
            due = t.due_date.isoformat() if t.due_date else ""
            status = "x" if t.is_completed else " "
            print(f"[{status}] {t.id}  {t.title}  {due}")
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_tasks_add(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        project = await client.resolve_project_by_name(args.list)
        due_dt = _parse_date_or_datetime(args.date) if args.date else None

        task = Task(id="", title=args.task_title, project_id=project.id, due_date=due_dt)
        created = await client.create_task(task)
        print(created.id)
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_tasks_edit(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        task = await client.get_task_any_project(args.task_id)
        if args.title:
            task.title = args.title
        if args.date is not None:
            task.due_date = _parse_date_or_datetime(args.date)
        updated = await client.update_task(task)
        print(updated.id)
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_tasks_delete(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        task = await client.get_task_any_project(args.task_id)
        await client.delete_task(task.project_id, task.id)
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_tasks_complete(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        task = await client.get_task_any_project(args.task_id)
        await client.complete_task(task.project_id, task.id)
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_today_list(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        tasks = await client.get_tasks_for_today(include_completed=args.show_completed)
        for t in tasks:
            due = t.due_date.isoformat() if t.due_date else ""
            status = "x" if t.is_completed else " "
            print(f"[{status}] {t.id}  {t.title}  {due}")
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_today_add(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        project = await client.resolve_project_by_name(args.list)
        due_dt = datetime.now()  # today
        task = Task(id="", title=args.task_title, project_id=project.id, due_date=due_dt)
        created = await client.create_task(task)
        print(created.id)
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_inbox_list(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        inbox = await client.resolve_inbox_project()
        tasks = await client.get_project_tasks(inbox.id)

        if not args.show_completed:
            tasks = [t for t in tasks if not t.is_completed]

        for t in tasks:
            due = t.due_date.isoformat() if t.due_date else ""
            status = "x" if t.is_completed else " "
            print(f"[{status}] {t.id}  {t.title}  {due}")
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_inbox_add(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        inbox = await client.resolve_inbox_project()
        due_dt = _parse_date_or_datetime(args.date) if args.date else None
        task = Task(id="", title=args.task_title, project_id=inbox.id, due_date=due_dt)
        created = await client.create_task(task)
        print(created.id)
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_lists_list(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        projects = await client.get_projects()
        for p in projects:
            print(f"{p.id}  {p.name}")
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_lists_add(args: argparse.Namespace) -> int:
    # Not in Open API; provide a clear message.
    raise RuntimeError("Creating lists/projects is not supported by TickTick Open API.")


async def cmd_lists_rename(args: argparse.Namespace) -> int:
    raise RuntimeError("Renaming lists/projects is not supported by TickTick Open API.")


async def cmd_lists_delete(args: argparse.Namespace) -> int:
    raise RuntimeError("Deleting lists/projects is not supported by TickTick Open API.")


async def cmd_folder_list(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        groups = await client.get_groups()
        for g in groups:
            print(f"{g['id']}  {g.get('name','')}")
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_folder_add(args: argparse.Namespace) -> int:
    raise RuntimeError("Creating folders/groups is not supported by TickTick Open API.")


async def cmd_folder_rename(args: argparse.Namespace) -> int:
    raise RuntimeError("Renaming folders/groups is not supported by TickTick Open API.")


async def cmd_folder_delete(args: argparse.Namespace) -> int:
    raise RuntimeError("Deleting folders/groups is not supported by TickTick Open API.")


async def cmd_tags_list(args: argparse.Namespace) -> int:
    client = await _build_client_from_tokens()
    try:
        tags = await client.get_tags()
        for tag in tags:
            print(tag)
        return ExitCode.OK
    finally:
        await client.close()


async def cmd_tags_add(args: argparse.Namespace) -> int:
    raise RuntimeError("Tag management is not supported by TickTick Open API.")


async def cmd_tags_rename(args: argparse.Namespace) -> int:
    raise RuntimeError("Tag management is not supported by TickTick Open API.")


async def cmd_tags_delete(args: argparse.Namespace) -> int:
    raise RuntimeError("Tag management is not supported by TickTick Open API.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ticktui")

    sub = parser.add_subparsers(dest="command", required=True)

    # tasks
    tasks = sub.add_parser("tasks")
    tasks_sub = tasks.add_subparsers(dest="tasks_command", required=True)

    tasks_list = tasks_sub.add_parser("list")
    tasks_list.add_argument(
        "--list",
        dest="list_name",
        default=None,
        help="Only show tasks from this list/project (by name)",
    )
    tasks_list.add_argument(
        "--folder",
        dest="folder",
        default=None,
        help="Only show tasks from this folder (group) (by name)",
    )
    tasks_list.add_argument(
        "--show-completed",
        dest="show_completed",
        action="store_true",
        help="Include completed tasks in output",
    )
    tasks_list.set_defaults(func=cmd_tasks_list)

    tasks_add = tasks_sub.add_parser("add")
    tasks_add.add_argument("task_title")
    tasks_add.add_argument("--date", dest="date", default=None)
    tasks_add.add_argument("--list", dest="list", required=True)
    tasks_add.set_defaults(func=cmd_tasks_add)

    tasks_edit = tasks_sub.add_parser("edit")
    tasks_edit.add_argument("task_id")
    tasks_edit.add_argument("--title", dest="title", default=None)
    tasks_edit.add_argument("--date", dest="date", default=None)
    tasks_edit.set_defaults(func=cmd_tasks_edit)

    tasks_delete = tasks_sub.add_parser("delete")
    tasks_delete.add_argument("task_id")
    tasks_delete.set_defaults(func=cmd_tasks_delete)

    tasks_complete = tasks_sub.add_parser("complete")
    tasks_complete.add_argument("task_id")
    tasks_complete.set_defaults(func=cmd_tasks_complete)

    # today
    today = sub.add_parser("today")
    today_sub = today.add_subparsers(dest="today_command", required=True)

    today_list = today_sub.add_parser("list")
    today_list.add_argument(
        "--show-completed",
        dest="show_completed",
        action="store_true",
        help="Include completed tasks in output",
    )
    today_list.set_defaults(func=cmd_today_list)

    today_add = today_sub.add_parser("add")
    today_add.add_argument("task_title")
    today_add.add_argument("--list", dest="list", required=True)
    today_add.set_defaults(func=cmd_today_add)

    # inbox
    inbox = sub.add_parser("inbox")
    inbox_sub = inbox.add_subparsers(dest="inbox_command", required=True)

    inbox_list = inbox_sub.add_parser("list")
    inbox_list.add_argument(
        "--show-completed",
        dest="show_completed",
        action="store_true",
        help="Include completed tasks in output",
    )
    inbox_list.set_defaults(func=cmd_inbox_list)

    inbox_add = inbox_sub.add_parser("add")
    inbox_add.add_argument("task_title")
    inbox_add.add_argument("--date", dest="date", default=None)
    inbox_add.set_defaults(func=cmd_inbox_add)

    # lists
    lists = sub.add_parser("lists")
    lists_sub = lists.add_subparsers(dest="lists_command", required=True)

    lists_list = lists_sub.add_parser("list")
    lists_list.set_defaults(func=cmd_lists_list)

    lists_add = lists_sub.add_parser("add")
    lists_add.add_argument("tag_name")
    lists_add.set_defaults(func=cmd_lists_add)

    lists_rename = lists_sub.add_parser("rename")
    lists_rename.add_argument("old_list_name")
    lists_rename.add_argument("new_list_name")
    lists_rename.set_defaults(func=cmd_lists_rename)

    lists_delete = lists_sub.add_parser("delete")
    lists_delete.add_argument("tag_name")
    lists_delete.set_defaults(func=cmd_lists_delete)

    # folder
    folder = sub.add_parser("folder")
    folder_sub = folder.add_subparsers(dest="folder_command", required=True)

    folder_list = folder_sub.add_parser("list")
    folder_list.set_defaults(func=cmd_folder_list)

    folder_add = folder_sub.add_parser("add")
    folder_add.add_argument("tag_name")
    folder_add.set_defaults(func=cmd_folder_add)

    folder_rename = folder_sub.add_parser("rename")
    folder_rename.add_argument("old_folder_name")
    folder_rename.add_argument("new_folder_name")
    folder_rename.set_defaults(func=cmd_folder_rename)

    folder_delete = folder_sub.add_parser("delete")
    folder_delete.add_argument("tag_name")
    folder_delete.set_defaults(func=cmd_folder_delete)

    # tags
    tags = sub.add_parser("tags")
    tags_sub = tags.add_subparsers(dest="tags_command", required=True)

    tags_list = tags_sub.add_parser("list")
    tags_list.set_defaults(func=cmd_tags_list)

    tags_add = tags_sub.add_parser("add")
    tags_add.add_argument("tag_name")
    tags_add.set_defaults(func=cmd_tags_add)

    tags_rename = tags_sub.add_parser("rename")
    tags_rename.add_argument("old_tag_name")
    tags_rename.add_argument("new_tag_name")
    tags_rename.set_defaults(func=cmd_tags_rename)

    tags_delete = tags_sub.add_parser("delete")
    tags_delete.add_argument("tag_name")
    tags_delete.set_defaults(func=cmd_tags_delete)

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    async def _runner() -> int:
        try:
            return await args.func(args)
        except Exception as e:  # noqa: BLE001
            print(f"Error: {e}")
            return ExitCode.ERROR

    raise SystemExit(asyncio.run(_runner()))
