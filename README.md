# Supercoder

**The FIRST AI coding assistant with visual UI analysis** 🚀

An autonomous AI coding agent that runs in your terminal. Give it a task, and it writes code, creates files, runs commands, and builds entire projects — all on its own.

**NEW:** Supercoder can now control browsers and "see" UIs like a human! Debug visual bugs, check accessibility, and perform visual regression testing automatically.

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
```

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/4lpine/Supercoder.git
cd Supercoder

# Install dependencies
pip install -r requirements.txt

# Run Supercoder
python main.py
```

Then just tell it what to build:
```
create a REST API with Express that has user authentication
```

Supercoder will autonomously:
1. Create project structure
2. Write all necessary files
3. Install dependencies
4. Test the code
5. Report completion

---

## 🌟 What Makes Supercoder Unique

Supercoder is the **ONLY** AI coding assistant with browser automation and visual UI analysis.

### Unique Features (ONLY in Supercoder)

| Feature | Supercoder | All Competitors |
|---------|------------|-----------------|
| **Browser Automation** | ✅ **11 tools** | ❌ None |
| **Visual UI Analysis** | ✅ **7 tools** | ❌ None |
| **Screenshot Debugging** | ✅ | ❌ |
| **Accessibility Checking** | ✅ | ❌ |
| **Visual Regression Testing** | ✅ | ❌ |
| **Local Vision Models** | ✅ **Free** | ❌ |
| **File Pinning** | ✅ | ❌ |
| **Undo System** | ✅ | ❌ |
| **Auto-Verification** | ✅ | ❌ |
| **Task Planning** | ✅ | ❌ |
| **350+ Models** | ✅ | ❌ |
| **Completely Free Tier** | ✅ | ❌ |

### Real-World Examples

**Debug Visual Bugs:**
```
User: "The login page looks broken at localhost:3000"

Supercoder:
→ Opens browser
→ Takes screenshot
→ Vision analysis: "Login button overlapping username field"
→ Fixes CSS
→ Verifies fix
→ Commits changes
```

**Accessibility Audits:**
```
User: "Check accessibility of the homepage"

Supercoder:
→ Takes screenshot
→ Analyzes: "Low contrast text (2.1:1, needs 4.5:1)"
→ Identifies: "Missing label on email input"
→ Suggests: "Increase text color to #666"
→ Fixes issues automatically
```

**Visual Regression Testing:**
```
User: "Did my CSS changes break anything?"

Supercoder:
→ Takes before/after screenshots
→ Compares visually
→ Reports: "Button color changed, text spacing increased"
→ Asks if changes are intentional
```

---

## 🎁 Complete Feature List

### 🤖 AI & Models
- **350+ AI Models** - GPT-4, Claude, Gemini, DeepSeek, Qwen, Llama, Mistral, and more
- **Free Models** - No API key required (qwen/qwen3-coder:free, mistralai/devstral-2512:free)
- **Model Switching** - Change models mid-conversation
- **Streaming Responses** - Real-time token streaming
- **Context Management** - Up to 200K tokens (model-dependent)
- **Autonomous Mode** - Continues working until task complete

### 🌐 Browser Automation (UNIQUE - 11 Tools)
- **Start/Control Browsers** - Chrome, Firefox, Edge
- **Navigate & Interact** - Click, type, scroll, wait for elements
- **Screenshot Capture** - Full page or element-specific screenshots
- **JavaScript Execution** - Run custom JS in browser context
- **Element Inspection** - Get properties, attributes, location, size
- **Session Management** - Multiple browser sessions simultaneously
- **Headless Mode** - Run browsers without GUI

### 👁️ Visual UI Analysis (UNIQUE - 7 Tools)
- **AI Vision Models** - Local Qwen3-VL (2B/4B/8B/32B) or OpenRouter API
- **UI Screenshot Analysis** - Analyze layout, elements, issues, suggestions
- **Visual Bug Detection** - Detect overlapping elements, misalignment, broken layouts
- **Element Finding** - Find UI elements by natural language ("blue login button")
- **Layout Verification** - Verify expected elements are present and positioned
- **Accessibility Checking** - Check contrast, text size, labels, color-only info
- **Visual Regression Testing** - Compare screenshots before/after changes
- **GPU Acceleration** - CUDA support for local vision models
- **Zero API Cost Option** - Run vision models locally for free

### 📁 File Operations (40+ Tools)
- Read, write, append, delete files
- Find & replace (single or multiple)
- Line operations (insert, remove, replace)
- File management (move, copy, backup)
- Directory operations (list, create, tree view)
- Undo system with transaction IDs
- Syntax highlighting in terminal

### 🧠 Code Intelligence (15+ Tools)
- Syntax checking with real-time diagnostics
- Auto-verification after edits
- Symbol extraction (functions, classes, variables)
- Reference finding across files
- Symbol renaming across multiple files
- Code formatting (Black, Prettier)
- Test generation (pytest, unittest)
- Stack trace analysis
- AST analysis for deep code understanding

### 🔍 Search & Discovery
- File search by name pattern (fuzzy matching)
- Content search with regex (ripgrep-like performance)
- In-file search with context lines
- Smart indexing for fast retrieval
- Symbol search across codebase

### 🔧 Git Integration
- Git status, diff, commit message generation
- Pull request creation via GitHub CLI
- Merge conflict resolution

### 💻 Shell & Process Management
- Command execution (PowerShell/Bash)
- Background processes (dev servers, watchers)
- Process monitoring and output capture
- Environment variables
- System info

### 📋 Task Management
- Project planning (requirements, design, tasks)
- Task lists with checkboxes
- Task execution (one by one or automatic)
- Progress tracking

### 🎯 Context Management
- File pinning (up to 8 files always in context)
- Smart context (automatically includes relevant files)
- Context caching for performance
- Real-time token counting

### 🌐 Web Integration
- Web search for programming help
- Stack Overflow search
- HTTP requests (GET, POST, PUT, DELETE)
- File downloads from URLs

### 🗄️ Database Integration
- Supabase support (query, insert, update, delete)
- Table listing and schema inspection
- Row counting with filters

---

## 💡 Installation

### Quick Install (Windows)

1. Download [`installer.bat`](https://github.com/4lpine/Supercoder/raw/main/bin/installer.bat)
2. Run it
3. Open a new terminal and type: `supercoder`

### Manual Install (All Platforms)

```bash
# Clone the repository
git clone https://github.com/4lpine/Supercoder.git
cd Supercoder

# Install dependencies
pip install -r requirements.txt

# Optional: Browser automation
pip install selenium webdriver-manager

# Optional: Local vision models (for UI analysis)
pip install torch transformers qwen-vl-utils accelerate

# For GPU support (recommended for vision):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Run Supercoder
python main.py
```

### Requirements

- **Python 3.8+**
- **Windows 10/11** (installer) or **Linux/macOS** (manual install)

---

## 🎮 Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `help` | Show all commands |
| `status` | Show session info (model, tokens, settings) |
| `model <name>` | Switch AI model |
| `models` | List 350+ available models |
| `tokens` | Add/manage API keys |
| `clear` | Clear conversation history |
| `quit` | Exit Supercoder |

### Browser & Vision Commands

| Command | Description |
|---------|-------------|
| `vision api` | Use OpenRouter API for vision (~$0.01-0.03/image) |
| `vision local 2b` | Use local Qwen3-VL 2B (4GB VRAM) |
| `vision local 4b` | Use local Qwen3-VL 4B (8GB VRAM) |
| `vision local 8b` | Use local Qwen3-VL 8B (16GB VRAM) |
| `vision local 32b` | Use local Qwen3-VL 32B (32GB+ VRAM) |
| `vision status` | Show current vision configuration |

### Task Management

| Command | Description |
|---------|-------------|
| `plan <description>` | Generate requirements, design, and tasks |
| `tasks` | List all tasks |
| `task next` | Execute next incomplete task |
| `task do <n>` | Execute specific task |
| `task done <n>` | Mark task complete |

### File Management

| Command | Description |
|---------|-------------|
| `pin <file>` | Pin file to always include in context |
| `unpin <file>` | Remove pinned file |
| `pins` | List pinned files |

### Settings

| Command | Description |
|---------|-------------|
| `auto` | Toggle autonomous mode |
| `auto cap 100` | Set max autonomous steps |
| `compact` | Toggle compact output |
| `verbose` | Toggle verbose output |
| `verify` | Set verification mode (py_compile, custom, off) |

---

## 🎨 Vision Model Options

### Option 1: API Mode (Easiest)

**No installation required!** Uses OpenRouter API.

```bash
vision api
```

**Cost:** ~$0.01-0.03 per screenshot  
**Models:** Qwen3-VL, GPT-4V, Claude Vision (automatic fallback)

### Option 2: Local Mode (Best for Heavy Use)

**Run vision models locally** - no API costs!

```bash
# Install dependencies
pip install torch transformers qwen-vl-utils accelerate

# For GPU support (recommended):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Configure
vision local 2b      # 4GB VRAM - fastest
vision local 4b      # 8GB VRAM - balanced
vision local 8b      # 16GB VRAM - better quality
vision local 32b     # 32GB+ VRAM - best quality
```

**Model downloads automatically on first use:**
- 2B: ~2GB download
- 4B: ~4GB download
- 8B: ~8GB download
- 32B: ~15GB download

---

## 📚 Example Workflows

### 1. Create a Full-Stack App

```
plan create a todo app with React frontend and FastAPI backend

# Supercoder generates:
# - Requirements document
# - Technical design
# - Task breakdown

task next    # Execute first task
task next    # Execute second task
# ... continues until complete
```

### 2. Debug Visual Bug

```
The login page at localhost:3000 looks broken

# Supercoder:
# 1. Opens browser
# 2. Takes screenshot
# 3. Analyzes: "Button overlapping input field"
# 4. Fixes CSS
# 5. Verifies fix
# 6. Commits changes
```

### 3. Add Feature to Existing Code

```
add JWT authentication to the user API

# Supercoder:
# 1. Reads existing code
# 2. Installs dependencies
# 3. Adds auth middleware
# 4. Updates routes
# 5. Writes tests
# 6. Verifies everything works
```

### 4. Accessibility Audit

```
check accessibility of all pages in my app

# Supercoder:
# 1. Opens each page
# 2. Takes screenshots
# 3. Analyzes contrast, labels, text size
# 4. Lists all issues
# 5. Suggests fixes
# 6. Optionally fixes automatically
```

---

## 🔧 Configuration

### API Keys

Supercoder works with OpenRouter for AI models:

1. Get a key from [openrouter.ai](https://openrouter.ai)
2. Run `tokens` command
3. Paste your key

Keys are saved globally in `~/.supercoder/tokens.txt`

### Free Models

Supercoder works without an API key using free models:
- `qwen/qwen3-coder:free` (default)
- `mistralai/devstral-2512:free`

### Project Settings

Project-specific files are stored in `.supercoder/`:
- `tasks.md` - Task list
- `requirements.md` - Requirements document
- `design.md` - Technical design
- `screenshots/` - Browser screenshots

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Machine                            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Supercoder (Python)                    │    │
│  │                                                     │    │
│  │  • main.py (UI & orchestration)                     │    │
│  │  • Agentic.py (AI interface)                        │    │
│  │  • tools.py (file/shell tools)                      │    │
│  │  • selenium_tools.py (browser automation)           │    │
│  │  • vision_tools.py (UI analysis)                    │    │
│  │                                                     │    │
│  │  Full access to your workspace                      │    │
│  │  PowerShell/Bash for command execution              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Python 3.8+ + dependencies                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │  OpenRouter API  │
                  │  350+ AI Models  │
                  └──────────────────┘
```

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a PR

---

## 📄 License

MIT License - do whatever you want with it.

---

## 🙏 Credits

Built with:
- [OpenRouter](https://openrouter.ai) - AI model access
- [Selenium](https://www.selenium.dev/) - Browser automation
- [Qwen3-VL](https://huggingface.co/Qwen) - Vision models
- [Python](https://python.org) - Everything else

---

## 🔗 Links

- **Website:** [cerebrix.dev](https://cerebrix.dev)
- **GitHub:** [github.com/4lpine/Supercoder](https://github.com/4lpine/Supercoder)
- **Issues:** [github.com/4lpine/Supercoder/issues](https://github.com/4lpine/Supercoder/issues)
- **Discord:** [discord.gg/GyS225bRJx](https://discord.gg/GyS225bRJx)

---

**Supercoder: The future of AI-assisted development is here.** 🚀
