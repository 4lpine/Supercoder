# SuperCoder

An autonomous AI coding agent that runs in your terminal. Give it a task, and it writes code, creates files, runs commands, and builds entire projects — all on its own.

```
      ██████  █    ██  ██▓███  ▓█████  ██▀███   ▄████▄   ▒█████  ▓█████▄ ▓█████  ██▀███
    ▒██    ▒  ██  ▓██▒▓██░  ██▒▓█   ▀ ▓██ ▒ ██▒▒██▀ ▀█  ▒██▒  ██▒▒██▀ ██▌▓█   ▀ ▓██ ▒ ██▒
    ░ ▓██▄   ▓██  ▒██░▓██░ ██▓▒▒███   ▓██ ░▄█ ▒▒▓█    ▄ ▒██░  ██▒░██   █▌▒███   ▓██ ░▄█ ▒
      ▒   ██▒▓▓█  ░██░▒██▄█▓▒ ▒▒▓█  ▄ ▒██▀▀█▄  ▒▓▓▄ ▄██▒▒██   ██░░▓█▄   ▌▒▓█  ▄ ▒██▀▀█▄
    ▒██████▒▒▒▒█████▓ ▒██▒ ░  ░░▒████▒░██▓ ▒██▒▒ ▓███▀ ░░ ████▓▒░░▒████▓ ░▒████▒░██▓ ▒██▒
    ▒ ▒▓▒ ▒ ░░▒▓▒ ▒ ▒ ▒▓▒░ ░  ░░░ ▒░ ░░ ▒▓ ░▒▓░░ ░▒ ▒  ░░ ▒░▒░▒░  ▒▒▓  ▒ ░░ ▒░ ░░ ▒▓ ░▒▓░
    ░ ░▒  ░ ░░░▒░ ░ ░ ░▒ ░      ░ ░  ░  ░▒ ░ ▒░  ░  ▒     ░ ▒ ▒░  ░ ▒  ▒  ░ ░  ░  ░▒ ░ ▒░
    ░  ░  ░   ░░░ ░ ░ ░░          ░     ░░   ░ ░        ░ ░ ░ ▒   ░ ░  ░    ░     ░░   ░
          ░     ░                 ░  ░   ░     ░ ░          ░ ░     ░       ░  ░   ░
                                               ░                  ░
- Alpine
```

---

## Installation

### One-Click Install (Windows)

1. **Download** [`installer.exe`](https://github.com/4lpine/Supercoder/raw/main/bin/installer.exe)
2. **Run it**

That's it. The installer handles everything:

- ✅ Checks if Docker Desktop is installed (offers to install it if not)
- ✅ Downloads SuperCoder from GitHub
- ✅ Builds the Docker image with all dependencies
- ✅ Creates the `supercoder` command
- ✅ Adds it to your PATH

After installation, open a **new terminal** and type:

```
supercoder
```

### Requirements

- **Windows 10/11**
- **Docker Desktop** (the installer will help you get this if you don't have it)

### Updating

Just run `installer.exe` again. It will download the latest version and rebuild everything.

### Uninstalling

1. Delete the install folder (default: `C:\Users\YourName\supercoder`)
2. Remove the `bin` folder from your PATH (System Properties → Environment Variables)
3. Optionally remove the Docker image: `docker rmi supercoder:latest`

---

## What is SuperCoder?

SuperCoder is an **autonomous AI coding agent** that lives in your terminal. Unlike chatbots that just give you code snippets to copy-paste, SuperCoder actually:

- **Reads your files** to understand your codebase
- **Writes and modifies code** directly
- **Creates new files and folders**
- **Runs shell commands** to test, build, and debug
- **Iterates on its own work** until the task is complete

You describe what you want in plain English, and SuperCoder figures out how to build it.

### Why SuperCoder?

| Feature | Cursor | Claude Code | SuperCoder |
|---------|--------|-------------|------------|
| Price | $20/month | $20-200/month | **Free** or pay-per-use |
| Free tier | ❌ | ❌ | ✅ via g4f |
| Model choice | ~10 models | Claude only | **350+ models** |
| Open source | ❌ | ❌ | ✅ |
| Task planning | ❌ | ❌ | ✅ `plan` command |
| Undo file changes | ❌ | ❌ | ✅ built-in |
| File pinning | ❌ | ❌ | ✅ always in context |
| Auto-verify code | ❌ | ❌ | ✅ syntax check after edits |

**What SuperCoder does that others don't:**
- **350+ models** — Use GPT-4, Claude, Llama, Mistral, Gemini, DeepSeek, Qwen, and more. Switch models mid-conversation with `model <name>`
- **Task planning** — Run `plan build a todo app` and SuperCoder generates requirements, design docs, and a task list. Then execute with `task next`
- **Undo system** — Every file change is tracked. Made a mistake? Undo it
- **File pinning** — Pin important files so they're always included in context, even across conversations
- **Auto-verification** — Automatically runs `py_compile` after Python edits to catch syntax errors immediately
- **Completely free** — Use g4f models with no API key, or pay-per-token with OpenRouter (often cheaper than subscriptions)

### How It Works

SuperCoder runs inside a **Docker container** with a full Linux environment. When you launch it from a Windows folder, that folder is mounted inside the container. This means:

1. SuperCoder can read and write files in your project
2. It runs in an isolated environment (can't mess up your system)
3. It has access to Linux tools (grep, sed, git, etc.)
4. Your API tokens and settings persist between sessions

---

## Usage

### Basic Workflow

```
C:\Projects\myapp> supercoder

┌──(root@supercoder)-[myapp]
└─$ create a REST API with Express that has user authentication

▸ fsWrite(path='package.json')
▸ fsWrite(path='src/index.js')
▸ fsWrite(path='src/routes/auth.js')
▸ executePwsh(command='npm install')
...

╭──────────────────────────────────────────────────────────────────────╮
│  ✓ COMPLETE                                                          │
├──────────────────────────────────────────────────────────────────────┤
│  Created Express API with JWT authentication, user registration,     │
│  and login endpoints.                                                │
╰──────────────────────────────────────────────────────────────────────╯
```

### Commands

| Command | Description |
|---------|-------------|
| `help` | Show all commands |
| `status` | Show session info (model, tokens used, settings) |
| `model <name>` | Switch AI model |
| `models` | List all available models |
| `freemodels` | List free models (no API key needed) |
| `tokens` | Add/manage API keys |
| `cd <path>` | Change directory |
| `clear` | Clear conversation history |
| `quit` | Exit SuperCoder |

### Autonomous Mode

By default, SuperCoder runs in **autonomous mode** — it keeps working until the task is complete (up to 50 steps). You can control this:

| Command | Description |
|---------|-------------|
| `auto` | Toggle autonomous mode on/off |
| `auto on` | Enable autonomous mode |
| `auto off` | Disable (asks before each step) |
| `auto cap 100` | Set max steps to 100 |

### Output Modes

| Command | Description |
|---------|-------------|
| `compact` | Minimal output (default) |
| `verbose` | Show full file contents when reading/writing |

### File Pinning

Pin important files so SuperCoder always has them in context:

| Command | Description |
|---------|-------------|
| `pin <file>` | Pin a file to context |
| `unpin <file>` | Remove a pinned file |
| `pins` | List pinned files |

### Task Management

SuperCoder can break down large projects into tasks:

| Command | Description |
|---------|-------------|
| `plan <description>` | Generate requirements, design, and tasks |
| `tasks` | List all tasks |
| `task next` | Execute the next incomplete task |
| `task do <n>` | Execute a specific task |
| `task done <n>` | Mark a task complete |
| `task undo <n>` | Mark a task incomplete |

---

## Models

SuperCoder supports multiple AI providers:

### Free Models (No API Key)

These work out of the box via g4f:

- `gpt-4o-mini` - Fast, good for simple tasks
- `claude-3-haiku` - Quick responses
- `llama-3.1-70b` - Open source, capable
- And many more... (run `freemodels` to see all)

### OpenRouter Models (API Key Required)

For better performance, add an OpenRouter API key:

1. Get a key from [openrouter.ai](https://openrouter.ai)
2. Run `tokens` command and paste your key
3. Switch models with `model <name>`

Popular choices:
- `anthropic/claude-sonnet-4` - Best for complex coding
- `openai/gpt-4o` - Great all-around
- `mistralai/devstral-2512:free` - Free, good for coding
- `google/gemini-2.0-flash-001` - Fast and capable

---

## Tools

SuperCoder has access to these tools:

### File Operations
- `readFile` - Read file contents
- `readCode` - Read code with AST analysis
- `fsWrite` - Create/overwrite files
- `fsAppend` - Append to files
- `strReplace` - Find and replace in files
- `deleteFile` - Delete files
- `listDirectory` - List folder contents

### Code Intelligence
- `grepSearch` - Search for patterns in files
- `fileSearch` - Find files by name
- `getDiagnostics` - Check for syntax errors
- `getSymbols` - Extract functions/classes from code
- `findReferences` - Find all uses of a symbol

### Shell & System
- `executePwsh` - Run shell commands
- `controlPwshProcess` - Start/stop background processes
- `systemInfo` - Get OS and environment info

### Development
- `runTests` - Run pytest
- `formatCode` - Format with black/prettier
- `httpRequest` - Make HTTP requests
- `webSearch` - Search the web for help

### Interaction
- `finish` - Signal task completion
- `interactWithUser` - Ask the user a question

---

## Keyboard Shortcuts

SuperCoder supports readline keybindings:

| Key | Action |
|-----|--------|
| `↑` / `↓` | Browse command history |
| `←` / `→` | Move cursor |
| `Ctrl+A` | Jump to start of line |
| `Ctrl+E` | Jump to end of line |
| `Ctrl+W` | Delete word backwards |
| `Ctrl+U` | Delete entire line |
| `Ctrl+K` | Delete to end of line |
| `Ctrl+L` | Clear screen |
| `Ctrl+Y` | Paste last deleted text |
| `Alt+B` | Move back one word |
| `Alt+F` | Move forward one word |
| `Alt+D` | Delete word forward |

Command history is saved between sessions in `~/.supercoder/history`.

---

## Configuration

Settings are stored in `~/.supercoder/`:

| File | Purpose |
|------|---------|
| `tokens.txt` | API keys (one per line) |
| `history` | Command history |

Project-specific tasks are stored in `.supercoder/tasks.md` in your project folder.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Windows Machine                    │
│                                                             │
│  C:\Projects\myapp\  ←──────────────────────┐               │
│                                             │               │
│  ┌─────────────────────────────────────────┐│               │
│  │           Docker Container              ││               │
│  │                                         ││               │
│  │  ┌─────────────────────────────────┐    ││               │
│  │  │         SuperCoder              │    ││  mounted as   │
│  │  │                                 │    ││  /workspace   │
│  │  │  • main.py (UI & orchestration) │    ││               │
│  │  │  • Agentic.py (AI interface)    │    │◄───────────────┘
│  │  │  • tools.py (file/shell tools)  │    │                │
│  │  │                                 │    │                │
│  │  └─────────────────────────────────┘    │                │
│  │                                         │                │
│  │  Python 3.12 + dependencies             │                │
│  │  Linux (Debian)                         │                │
│  └─────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### Components

- **main.py** - Terminal UI, command handling, prompt building
- **Agentic.py** - AI model interface (OpenRouter, g4f), tool calling
- **tools.py** - File operations, shell execution, code analysis
- **Agents/*.md** - System prompts for different agent modes

---

## Examples

### Create a new project
```
create a Python CLI tool that converts markdown to HTML
```

### Add features to existing code
```
add error handling and logging to the database module
```

### Debug issues
```
the tests in test_auth.py are failing, can you fix them?
```

### Refactor code
```
refactor the user service to use async/await
```

### Generate documentation
```
add docstrings to all functions in src/utils.py
```

### Complex multi-step tasks
```
plan create a full-stack todo app with React frontend and FastAPI backend
```
Then use `task next` to execute each step.

---

## Troubleshooting

### "Docker is not running"
Start Docker Desktop from the Start menu and wait for it to fully load (whale icon in system tray).

### "SuperCoder not installed"
Run `installer.exe` again to rebuild the Docker image.

### Slow first startup
The first run downloads the Python base image (~150MB). Subsequent runs are instant.

### Can't type after task completes
This was a bug that's been fixed. Run `installer.exe` to update.

### Commands not found after install
Open a **new** terminal window. The PATH update only affects new terminals.

---

## Contributing

1. Fork the repo
2. Make changes
3. Test locally: `docker build -t supercoder:latest .`
4. Submit a PR

---

## License

MIT License - do whatever you want with it.

---

## Credits

Built with:
- [OpenRouter](https://openrouter.ai) - AI model access
- [g4f](https://github.com/xtekky/gpt4free) - Free model access
- [Docker](https://docker.com) - Containerization
- [Python](https://python.org) - Everything else
