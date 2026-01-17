# SuperCoder

**The FIRST AI coding assistant with visual UI analysis** 🚀

An autonomous AI coding agent that runs in your terminal. Give it a task, and it writes code, creates files, runs commands, and builds entire projects — all on its own.

**NEW:** SuperCoder can now control browsers and "see" UIs like a human! Debug visual bugs, check accessibility, and perform visual regression testing automatically.

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
- 4lpine
```

---

## 🌟 What Makes SuperCoder Unique

SuperCoder is the **ONLY** AI coding assistant that can:

| Feature | Cursor | Claude Code | GitHub Copilot | Windsurf | SuperCoder |
|---------|--------|-------------|----------------|----------|------------|
| **Browser Automation** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Visual UI Analysis** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Screenshot Debugging** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Accessibility Checking** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Visual Regression Testing** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Local Vision Models** | ❌ | ❌ | ❌ | ❌ | ✅ |
| Price | $20/mo | $20-200/mo | $10-40/mo | $10/mo | **Free** or pay-per-use |
| Model choice | ~10 | Claude only | GPT only | GPT only | **350+** |
| Open source | ❌ | ❌ | ❌ | ❌ | ✅ |

### 🎯 Real-World Examples

**Debug Visual Bugs:**
```
User: "The login page looks broken at localhost:3000"

SuperCoder:
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

SuperCoder:
→ Takes screenshot
→ Analyzes: "Low contrast text (2.1:1, needs 4.5:1)"
→ Identifies: "Missing label on email input"
→ Suggests: "Increase text color to #666"
→ Fixes issues automatically
```

**Visual Regression Testing:**
```
User: "Did my CSS changes break anything?"

SuperCoder:
→ Takes before/after screenshots
→ Compares visually
→ Reports: "Button color changed, text spacing increased"
→ Asks if changes are intentional
```

---

## 🚀 Installation

### Quick Install (Windows)

1. **Download** [`installer.exe`](https://github.com/4lpine/Supercoder/raw/main/bin/installer.exe)
2. **Run it**
3. Open a new terminal and type: `supercoder`

### Manual Install (All Platforms)

```bash
# Clone the repository
git clone https://github.com/4lpine/Supercoder.git
cd Supercoder

# Install dependencies
pip install -r requirements.txt

# Optional: Browser automation
pip install -r requirements-selenium.txt

# Optional: Local vision models (for UI analysis)
pip install -r requirements-vision.txt

# Run SuperCoder
python main.py
```

### Requirements

- **Python 3.8+**
- **Windows 10/11** (installer) or **Linux/macOS** (manual install)

---

## 💡 Quick Start

### Basic Usage

```bash
python main.py

# In SuperCoder:
create a REST API with Express that has user authentication
```

SuperCoder will:
1. Create project structure
2. Write all necessary files
3. Install dependencies
4. Test the code
5. Report completion

### Browser Automation + Vision

```bash
python main.py

# Configure vision (choose one):
vision api           # Easiest - no install, ~$0.01-0.03/image
vision local 2b      # Local model - 4GB VRAM, free

# Test it:
Start Chrome, go to example.com, take a screenshot, analyze the UI
```

SuperCoder will:
1. Start browser
2. Navigate to URL
3. Take screenshot
4. Analyze UI with vision model
5. Report layout, elements, issues, and suggestions

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
| `quit` | Exit SuperCoder |

### Browser & Vision Commands

| Command | Description |
|---------|-------------|
| `vision api` | Use OpenRouter API for vision (~$0.01-0.03/image) |
| `vision local 2b` | Use local Qwen3-VL 2B (4GB VRAM) |
| `vision local 4b` | Use local Qwen3-VL 4B (8GB VRAM) |
| `vision local 8b` | Use local Qwen3-VL 8B (16GB VRAM) |
| `vision local 32b` | Use local Qwen3-VL 32B (32GB+ VRAM) |
| `vision status` | Show current vision configuration |
| `v` | Shortcut for vision command |

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
| `verbose` | Toggle verbose output (show full file contents) |
| `verify` | Set verification mode (py_compile, custom, off) |

---

## 🛠️ Tools & Capabilities

### Browser Automation (11 Tools)

- **seleniumStartBrowser** - Start Chrome/Firefox/Edge
- **seleniumNavigate** - Navigate to URLs
- **seleniumClick** - Click elements
- **seleniumType** - Type text into inputs
- **seleniumScreenshot** - Capture screenshots
- **seleniumExecuteScript** - Run JavaScript
- **seleniumWaitForElement** - Wait for elements
- **seleniumGetElement** - Get element properties
- **seleniumGetPageSource** - Get HTML source
- **seleniumListSessions** - List active browser sessions
- **seleniumCloseBrowser** - Close browser

### Vision Analysis (7 Tools)

- **visionAnalyzeUI** - Comprehensive UI analysis (layout, elements, issues, suggestions)
- **visionFindElement** - Find elements by description ("blue login button")
- **visionVerifyLayout** - Verify expected elements are present
- **visionAccessibilityCheck** - Check for accessibility issues
- **visionCompareScreenshots** - Visual regression testing
- **visionSetMode** - Configure local/API mode
- **visionGetStatus** - Check current configuration

### File Operations (20+ Tools)

- **readFile** - Read file contents
- **readCode** - Read code with AST analysis
- **fsWrite** - Create/overwrite files
- **fsAppend** - Append to files
- **strReplace** - Find and replace
- **deleteFile** - Delete files
- **listDirectory** - List folder contents
- **listDirectoryTree** - Recursive tree view
- **getFileInfo** - Get file metadata
- And more...

### Code Intelligence (10+ Tools)

- **grepSearch** - Search for patterns
- **fileSearch** - Find files by name
- **getDiagnostics** - Check for syntax errors
- **getSymbols** - Extract functions/classes
- **findReferences** - Find symbol usage
- **validateJson** - Validate JSON
- And more...

### Git Integration

- **gitStatus** - Check git status
- **gitDiff** - Show git diff
- **generateCommitMessage** - Auto-generate commit messages

### Shell & System

- **executePwsh** - Run shell commands
- **controlPwshProcess** - Start/stop background processes
- **systemInfo** - Get OS info
- **getEnvironmentVariable** - Read env vars

### Development

- **runTests** - Run pytest
- **formatCode** - Format code
- **httpRequest** - Make HTTP requests
- **webSearch** - Search the web

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
pip install -r requirements-vision.txt

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

# SuperCoder generates:
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

# SuperCoder:
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

# SuperCoder:
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

# SuperCoder:
# 1. Opens each page
# 2. Takes screenshots
# 3. Analyzes contrast, labels, text size
# 4. Lists all issues
# 5. Suggests fixes
# 6. Optionally fixes automatically
```

### 5. Visual Regression Testing

```
compare screenshots before and after my CSS changes

# SuperCoder:
# 1. Takes baseline screenshots
# 2. Applies changes
# 3. Takes new screenshots
# 4. Compares visually
# 5. Reports differences
```

---

## 🔧 Configuration

### API Keys

SuperCoder works with OpenRouter for AI models:

1. Get a key from [openrouter.ai](https://openrouter.ai)
2. Run `tokens` command
3. Paste your key

Keys are saved globally in `~/.supercoder/tokens.txt`

### Free Models

SuperCoder works without an API key using free models:
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
│  │              SuperCoder (Python)                    │    │
│  │                                                     │    │
│  │  • main.py (UI & orchestration)                    │    │
│  │  • Agentic.py (AI interface)                       │    │
│  │  • tools.py (file/shell tools)                     │    │
│  │  • selenium_tools.py (browser automation)          │    │
│  │  • vision_tools.py (UI analysis)                   │    │
│  │  • supabase_tools.py (database)                    │    │
│  │                                                     │    │
│  │  Full access to your workspace                     │    │
│  │  PowerShell/Bash for command execution             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Python 3.8+ + dependencies                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │   OpenRouter API  │
                  │   350+ AI Models  │
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

- **GitHub:** [github.com/4lpine/Supercoder](https://github.com/4lpine/Supercoder)
- **Issues:** [github.com/4lpine/Supercoder/issues](https://github.com/4lpine/Supercoder/issues)
- **OpenRouter:** [openrouter.ai](https://openrouter.ai)

---

## 📊 Stats

- **18 unique tools** for browser automation and vision analysis
- **350+ AI models** supported
- **100% open source**
- **First AI assistant** with visual UI analysis
- **Zero subscription fees** - pay only for what you use

---

**SuperCoder: The future of AI-assisted development is here.** 🚀
