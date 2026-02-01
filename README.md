# TickTUI

A CLI and terminal user interface for interacting with the TickTick task manager.

## Features

- 🎯 **Lazygit-inspired interface** - Three-panel layout with projects, tasks, and details
- ⌨️ **Vim-style navigation** - Use `j/k` or arrow keys to navigate
- ✅ **Full task management** - Create, edit, complete, and delete tasks
- 🔄 **Real-time sync** - Connects to TickTick's official REST API
- 🎨 **Rich display** - Priority indicators, completion status, and due dates

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

## Usage

### Keyboard Shortcuts

#### Navigation

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `h` / `←` | Focus projects panel |
| `l` / `→` | Focus tasks panel |
| `Tab` | Next panel |
| `Shift+Tab` | Previous panel |

#### Actions

| Key | Action |
|-----|--------|
| `n` | Create new task |
| `e` | Edit selected task |
| `c` | Complete selected task |
| `d` | Delete selected task |
| `r` | Refresh data |
| `?` | Show help |
| `q` | Quit |

## License

MIT License - See [LICENSE](LICENSE) for details.
