# TickTUI

## Features

- 🎯 **Lazygit-inspired interface** - Three-panel layout with projects, tasks, and details
- ⌨️ **Vim-style navigation** - Use `j/k` or arrow keys to navigate
- ✅ **Full task management** - Create, edit, complete, and delete tasks
- 🔄 **Real-time sync** - Connects to TickTick's official REST API
- 🎨 **Rich display** - Priority indicators, completion status, and due dates

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/floscha/ticktui.git
cd ticktui

# Install with uv
uv sync
uv run ticktui
```

### Using pip

```bash
pip install ticktui
ticktui
```

## Setup

### 1. Register a TickTick App

1. Go to [TickTick Developer Portal](https://developer.ticktick.com/manage)
2. Log in with your TickTick account
3. Click "Create App" and give it a name
4. Set the **Redirect URI** to `http://localhost:8080/callback`
5. Note your **Client ID** and **Client Secret**

### 2. Run TickTUI

```bash
ticktui
```

### 3. Authenticate

TickTUI supports two authentication methods:

#### Option A: OAuth Flow (Recommended)

1. Enter your **Client ID** and **Client Secret**
2. Click **"Login with OAuth"**
3. A browser window will open for you to authorize the app
4. After authorizing, you'll be redirected back and automatically logged in
5. Your tokens are saved securely for future sessions

#### Option B: Manual Token

If you already have an access token:

1. Enter it in the **"Access Token"** field
2. Click **"Use Token"**

## Keyboard Shortcuts

### Navigation

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `h` / `←` | Focus projects panel |
| `l` / `→` | Focus tasks panel |
| `Tab` | Next panel |
| `Shift+Tab` | Previous panel |

### Actions

| Key | Action |
|-----|--------|
| `n` | Create new task |
| `e` | Edit selected task |
| `c` | Complete selected task |
| `d` | Delete selected task |
| `r` | Refresh data |
| `?` | Show help |
| `q` | Quit |

## Architecture

```
ticktui/
├── __init__.py       # Package initialization
├── api.py            # TickTick API client
└── app.py            # Textual TUI application
```

### API Client

The `api.py` module provides an async client for the TickTick REST API:

- `TickTickAuth` - OAuth2 authentication handler
- `TickTickClient` - Async HTTP client for API calls
- `Task` / `Project` - Data classes for API entities
- `TokenStorage` - Secure token persistence

### TUI Application

The `app.py` module implements the Textual-based interface:

- `MainScreen` - Three-panel layout (projects, tasks, details)
- `LoginScreen` - Authentication flow
- `NewTaskModal` / `EditTaskModal` - Task editing dialogs
- `ConfirmModal` - Deletion confirmations

## Development

```bash
# Install development dependencies
uv sync --dev

# Run the app
uv run ticktui

# Run with Textual console (for debugging)
uv run textual run --dev ticktui.app:TickTUIApp
```

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgements

- [Textual](https://textual.textualize.io/) - TUI framework
- [lazygit](https://github.com/jesseduffield/lazygit) - UI inspiration
- [TickTick](https://ticktick.com/) - Task management service
