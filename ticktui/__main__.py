"""Unified entrypoint.

Behavior:
- `ticktui` (no args) launches the Textual TUI.
- `ticktui <command> ...` launches the CLI.

This lets one executable serve both modes without extra scripts.
"""

from __future__ import annotations

import sys


def main() -> None:
    # No args should keep the quick path to the TUI.
    argv = sys.argv[1:]

    if not argv:
        from ticktui.app import main as tui_main

        tui_main()
        return

    # Any non-option first token means a CLI subcommand.
    if argv and not argv[0].startswith("-"):
        from ticktui.cli import main as cli_main

        cli_main(argv)
        return

    # Fallback: keep TUI behavior for option-only invocations.
    from ticktui.app import main as tui_main

    tui_main()


if __name__ == "__main__":
    main()
