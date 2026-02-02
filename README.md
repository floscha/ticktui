# TickTUI

A CLI and terminal user interface for interacting with the TickTick task manager.

## Setup

### Installation

```bash
# Clone the repository
git clone https://github.com/floscha/ticktui.git
cd ticktui

# Install with uv
uv sync
```

### Register a TickTick App

1. Go to [TickTick Developer Portal](https://developer.ticktick.com/manage)
2. Log in with your TickTick account
3. Click "Create App" and give it a name
4. Set the **Redirect URI** to `http://localhost:8080/callback`
5. Note your **Client ID** and **Client Secret**

## TUI Usage

Start with `uv run ticktui`

### Keyboard Shortcuts

Navigation:

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `h` / `←` | Focus projects panel |
| `l` / `→` | Focus tasks panel |
| `Tab` | Next panel |
| `Shift+Tab` | Previous panel |

Actions:

| Key | Action |
|-----|--------|
| `n` | Create new task |
| `e` | Edit selected task |
| `c` | Complete selected task |
| `d` | Delete selected task |
| `r` | Refresh data |
| `?` | Show help |
| `q` | Quit |

## CLI Usage

### Tasks

```bash
ticktui tasks list
ticktui tasks list --list 
ticktui tasks add <task_title> --date <date_or_datetime> --list <list_name>
ticktui tasks edit <task_id> --title <new_title> --date <new_date_or_datetime>
ticktui tasks complete <task_id>
ticktui tasks delete <task_id>

# `today` is a shortcut to access tasks scheduled for today.
ticktui today list
ticktui today add <task_title> --list <list_name>

# `inbox` is a shortcut to access tasks in the built-in inbox list.
ticktui today list
ticktui today add <task_title> --date <date_or_datetime>
```

### Lists

```bash
ticktui lists list
ticktui lists add <tag_name>
ticktui lists rename <old_list_name> <new_list_name>
ticktui lists delete <tag_name>
```

### Folders

```bash
ticktui folder list
ticktui folder add <tag_name>
ticktui folder rename <old_folder_name> <new_folder_name>
ticktui folder delete <tag_name>
```

### Tags

```bash
ticktui tags list
ticktui tags add <tag_name>
ticktui tags rename <old_tag_name> <new_tag_name>
ticktui tags delete <tag_name>
```

### General Options

```bash
ticktui <command> --show-completed
```

## License

MIT License - See [LICENSE](LICENSE) for details.
