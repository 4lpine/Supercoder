# Supercoder: A Comprehensive Technical Documentation

## Executive Summary

Supercoder is a sophisticated autonomous AI coding assistant built in Python that provides an interactive command-line interface for AI-assisted software development. The system comprises three interconnected modules: `supercoder.py` (the main application and user interface), `Agentic.py` (the AI agent framework and API communication layer), and `tools.py` (the comprehensive toolset for file operations, code analysis, and system interactions).

This document provides an exhaustive analysis of the entire codebase, with primary focus on `supercoder.py` as the central orchestration layer.

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Supercoder.py - The Main Application](#supercoderpy---the-main-application)
3. [Agentic.py - The AI Agent Framework](#agenticpy---the-ai-agent-framework)
4. [Tools.py - The Tool Library](#toolspy---the-tool-library)
5. [Inter-Module Communication](#inter-module-communication)
6. [Configuration and Customization](#configuration-and-customization)
7. [Security Considerations](#security-considerations)
8. [Appendices](#appendices)

---

## System Architecture Overview

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│                            (supercoder.py)                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Command   │  │   Session   │  │   Output    │  │   Task Management   │ │
│  │   Parser    │  │    State    │  │  Formatter  │  │      System         │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AI AGENT LAYER                                  │
│                             (Agentic.py)                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │    Agent    │  │   Token     │  │    File     │  │   API Communication │ │
│  │    Class    │  │  Management │  │   Indexer   │  │       Layer         │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TOOL EXECUTION LAYER                            │
│                               (tools.py)                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │    File     │  │   Shell     │  │    Code     │  │   Web Search &      │ │
│  │ Operations  │  │  Execution  │  │  Analysis   │  │   HTTP Requests     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SERVICES                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │   OpenRouter API    │  │   Local Filesystem  │  │   DuckDuckGo Search │  │
│  │   (LLM Provider)    │  │                     │  │                     │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Module Dependencies

```
supercoder.py
    ├── imports from Agentic.py
    │   ├── Agent (class)
    │   ├── execute_tool (function)
    │   ├── MODEL_LIMITS (dict)
    │   └── TokenManager (class)
    │
    └── imports from tools.py (via Agentic.py)
        └── All tool functions (patched for Windows compatibility)
```

---

## Supercoder.py - The Main Application

### Overview

`supercoder.py` is the primary entry point and user interface for the Supercoder system. It weighs in at **1,172 lines of Python code** and serves as the orchestration layer that ties together the AI agent capabilities with user interaction.

### Core Constants and Configuration

```python
WORKING_DIR = Path(__file__).parent
AGENTS_DIR = WORKING_DIR / "Agents"
SUPERCODER_DIR = ".supercoder"
TASKS_FILE = Path(SUPERCODER_DIR) / "tasks.md"

CODE_EXTENSIONS: Set[str] = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".h"}
DOC_EXTENSIONS: Set[str] = {".md", ".txt", ".json", ".yml", ".yaml", ".toml"}
ALL_EXTENSIONS: Set[str] = CODE_EXTENSIONS | DOC_EXTENSIONS

MAX_FILE_SIZE = 200_000      # Maximum file size for processing (200KB)
MAX_PINNED_FILES = 8         # Maximum number of files that can be pinned
MAX_RECENT_ITEMS = 10        # Maximum recent items to track
```

### Windows PowerShell Compatibility Layer

One of the most critical features of supercoder.py is its Windows compatibility layer. The system automatically detects and patches shell execution for Windows environments:

```python
@lru_cache(maxsize=1)
def _detect_shell() -> Tuple[Optional[str], str]:
    """Detect available shell on the system."""
    if os.name != "nt":
        return None, "posix shell"
    if shutil.which("pwsh"):
        return "pwsh", "PowerShell Core"
    if shutil.which("powershell"):
        return "powershell", "Windows PowerShell"
    return None, "cmd"
```

The patching mechanism replaces the default shell execution functions:

```python
def _execute_pwsh_patched(command: str, timeout: int = 60) -> Dict[str, Any]:
    """Windows-compatible shell execution with PowerShell."""
    if os.name == "nt" and _PS_EXE:
        args = [_PS_EXE, "-NoProfile", "-NonInteractive", 
                "-ExecutionPolicy", "Bypass", "-Command", _sanitize_cmd(command)]
        # ... execution logic
```

**Key Features:**
- Automatic shell detection (PowerShell Core → Windows PowerShell → cmd)
- Command sanitization (converts `&&` and `||` to `;` for PowerShell)
- Timeout handling with graceful error recovery
- Background process management


### ANSI Color System and Terminal UI

Supercoder implements a sophisticated terminal UI with ANSI color codes:

```python
class C:
    """ANSI color codes for terminal output."""
    RST, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
    RED = "\033[31m"
    BRED = "\033[91m"           # Bright red
    PURPLE = "\033[35m"
    BPURPLE = "\033[95m"        # Bright purple
    YELLOW = "\033[33m"
    BYELLOW = "\033[93m"        # Bright yellow
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    # Aliases for semantic usage
    GREEN, BLUE, MAGENTA, CYAN = BRED, PURPLE, PURPLE, BPURPLE
    BGREEN, BBLUE, BMAGENTA, BCYAN = BRED, BPURPLE, BPURPLE, BRED
```

**Status Message System:**

```python
_STATUS = {
    "info": (C.PURPLE, "[i]"),
    "success": (C.BRED, "[✓]"),
    "warning": (C.BYELLOW, "[!]"),
    "error": (C.RED, "[x]"),
    "context": (C.BPURPLE, "[~]")
}

def status(msg: str, level: str = "info") -> None:
    """Display a status message with appropriate styling."""
    c, p = _STATUS.get(level, (C.BLUE, "[i]"))
    print(_s(f"  {p} {msg}", c))
```

**ASCII Art Banner:**

The system displays a distinctive ASCII art banner on startup using colorama:

```python
def header() -> None:
    from colorama import Fore
    Color1 = Fore.MAGENTA
    Color2 = Fore.RED
    Banner = f"""
    {Color2}  ██████  █    ██  ██▓███  ▓█████  ██▀███   ▄████▄   ...
    """
    print(Banner)
```

### Session State Management

The `State` dataclass maintains all session-level information:

```python
@dataclass
class State:
    task: str = ""                              # Current task description
    pinned: List[str] = field(default_factory=list)  # Pinned context files
    auto_mode: bool = True                      # Autonomous execution mode
    auto_cap: int = 50                          # Maximum auto steps
    auto_steps: int = 0                         # Current step counter
    compact: bool = False                       # Compact output mode
    verbose: bool = True                        # Verbose output mode
    verify_mode: str = "py_compile"             # Code verification mode
    verify_cmd: Optional[str] = None            # Custom verification command
    verify_summary: str = ""                    # Last verification summary
    verify_detail: str = ""                     # Detailed verification output
    recent_reads: List[str] = field(default_factory=list)   # Recently read files
    recent_writes: List[str] = field(default_factory=list)  # Recently written files
    current_task_num: int = 0                   # Current task number being executed

    def reset_task(self) -> None:
        """Reset task-related state for a new task."""
        self.task = ""
        self.auto_steps = 0
        self.recent_reads.clear()
        self.recent_writes.clear()
        self.verify_summary = ""
        self.verify_detail = ""
```

### Input Handling System

The input system supports both single-line and multi-line input modes:

```python
def get_input(prompt: str = None) -> str:
    """Get user input with support for multiline mode."""
    try:
        if prompt is None:
            prompt = _build_prompt()
            print(prompt, end="")
            line = input()
        else:
            line = input(_s(prompt, C.YELLOW))
        
        stripped = line.strip()
        # Multiline mode triggers
        if stripped == "<<<" or stripped.startswith('"""'):
            end = ">>>" if stripped == "<<<" else '"""'
            print(f"  {C.GRAY}╭─ multiline mode (end with {end}){C.RST}")
            lines = []
            while True:
                ln = input(f"  {C.BPURPLE}│{C.RST} ")
                if ln.strip() == end:
                    print(f"  {C.GRAY}╰─────────────────────────────{C.RST}")
                    break
                lines.append(ln)
            return "\n".join(lines)
        return line
    except EOFError:
        return "quit"
```

**Custom Prompt Builder:**

```python
def _build_prompt() -> str:
    """Build the interactive prompt with user and directory info."""
    import getpass
    user = getpass.getuser()
    cwd = Path.cwd().name or "~"
    line1 = f"{C.BPURPLE}┌──({C.BRED}{user}{C.BPURPLE}@{C.BRED}supercoder{C.BPURPLE})-[{C.BOLD}{C.WHITE}{cwd}{C.RST}{C.BPURPLE}]{C.RST}"
    line2 = f"{C.BPURPLE}└─{C.BRED}${C.RST} "
    return f"{line1}\n{line2}"
```

### Model Management System

Supercoder integrates with OpenRouter to provide access to multiple AI models:

```python
_model_cache: Dict[str, Dict[str, Any]] = {}
_cache_loaded: bool = False

def fetch_models() -> List[Dict[str, Any]]:
    """Fetch available models from OpenRouter API."""
    global _model_cache, _cache_loaded
    import requests
    try:
        TokenManager.load_tokens()
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {TokenManager.get_token()}"},
            timeout=15
        )
        resp.raise_for_status()
        models = resp.json().get("data", [])
        _model_cache = {m["id"]: m for m in models if m.get("id")}
        _cache_loaded = True
        return models
    except Exception as e:
        status(f"Failed to fetch models: {e}", "error")
        return []

def get_context_limit(model_id: str) -> int:
    """Get the context window size for a model."""
    global _cache_loaded
    if model_id in _model_cache:
        return _model_cache[model_id].get("context_length", MODEL_LIMITS["default"])
    if model_id in MODEL_LIMITS:
        return MODEL_LIMITS[model_id]
    if not _cache_loaded:
        fetch_models()
    return _model_cache.get(model_id, {}).get("context_length", MODEL_LIMITS["default"])
```


### Command Registry System

Supercoder uses a decorator-based command registration system:

```python
_COMMANDS: Dict[str, Tuple[callable, str]] = {}
_SHORTCUTS: Dict[str, str] = {}

def cmd(name: str, help_text: str, shortcuts: List[str] = None):
    """Decorator to register a command handler."""
    def decorator(func):
        _COMMANDS[name] = (func, help_text)
        if shortcuts:
            for s in shortcuts:
                _SHORTCUTS[s] = name
        return func
    return decorator
```

**Complete Command Reference:**

| Command | Shortcuts | Description |
|---------|-----------|-------------|
| `help` | - | Show help information |
| `status` | - | Show session status |
| `clear` | - | Clear conversation history |
| `auto` | - | Toggle autonomous mode (on/off/cap N) |
| `compact` | - | Toggle compact output mode |
| `verbose` | - | Toggle verbose output mode |
| `verify` | - | Set verification mode (off/py_compile/custom) |
| `pin` | - | Pin a file to always include in context |
| `unpin` | - | Unpin a file |
| `pins` | - | List pinned files |
| `model` | - | Show or switch AI model |
| `models` | - | List available OpenRouter models |
| `index` | - | Rebuild retrieval index |
| `tokens` | - | Add/manage API tokens |
| `quit` | `exit`, `q` | Exit supercoder |
| `tasks` | `tl` | List all tasks |
| `task do` | `td` | Execute a specific task |
| `task done` | `tc` | Mark a task as complete |
| `task undo` | `tu` | Mark a task as incomplete |
| `task next` | `tn` | Execute next incomplete task |
| `plan` | - | Generate requirements, design, and tasks |

### Task Management System

Supercoder includes a sophisticated task management system that parses markdown-style task lists:

```python
_TASK_RE = re.compile(r'^(\s*[-*]?\s*\[([xX ])\]\s*)(.+)$', re.MULTILINE)

def _parse_tasks() -> List[Tuple[int, bool, str]]:
    """Parse tasks from the tasks.md file."""
    if not TASKS_FILE.exists():
        return []
    content = TASKS_FILE.read_text(encoding='utf-8')
    tasks = []
    for i, match in enumerate(_TASK_RE.finditer(content), 1):
        done = match.group(2).lower() == 'x'
        text = match.group(3).strip()
        tasks.append((i, done, text))
    return tasks

def _update_task_status(task_num: int, done: bool) -> bool:
    """Update the completion status of a task."""
    if not TASKS_FILE.exists():
        return False
    content = TASKS_FILE.read_text(encoding='utf-8')
    matches = list(_TASK_RE.finditer(content))
    if task_num < 1 or task_num > len(matches):
        return False
    match = matches[task_num - 1]
    new_mark = "[x]" if done else "[ ]"
    # ... replacement logic
    TASKS_FILE.write_text(new_content, encoding='utf-8')
    return True
```

**Task File Format:**
```markdown
- [ ] **[1] : First task description**
- [ ] **[2] : Second task description**
- [x] **[3] : Completed task**
```

### Output Compression and Formatting

The system includes intelligent output compression to manage large outputs:

```python
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
_WHITESPACE_RE = re.compile(r'\s+')

def compress_console(text: str, max_len: int = 8000) -> str:
    """Compress text for console display."""
    if not text or len(text) <= max_len:
        return text
    text = _ANSI_RE.sub('', text)           # Remove ANSI codes
    text = _WHITESPACE_RE.sub(' ', text)    # Normalize whitespace
    if len(text) <= max_len:
        return text
    half = max_len // 2 - 20
    return f"{text[:half]}\n... [{len(text) - max_len} chars truncated] ...\n{text[-half:]}"

def compress_model(text: str, max_len: int = 12000) -> str:
    """Compress text for model context."""
    if not text or len(text) <= max_len:
        return text
    half = max_len // 2 - 20
    return f"{text[:half]}\n... [{len(text) - max_len} chars truncated] ...\n{text[-half:]}"
```

### Syntax Highlighting Integration

When Pygments is available, Supercoder provides syntax highlighting:

```python
try:
    from pygments import highlight
    from pygments.lexers import get_lexer_for_filename, get_lexer_by_name, TextLexer
    from pygments.formatters import Terminal256Formatter
    from pygments.util import ClassNotFound
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False

def _syntax_highlight(code: str, filename: str = "") -> str:
    """Apply syntax highlighting to code based on filename extension."""
    if not PYGMENTS_AVAILABLE or not code.strip():
        return code
    try:
        if filename:
            lexer = get_lexer_for_filename(filename, stripall=True)
        else:
            lexer = TextLexer()
        formatter = Terminal256Formatter(style='monokai')
        return highlight(code, lexer, formatter).rstrip()
    except ClassNotFound:
        return code
```

### Tool Output Display

The `print_tool` function provides formatted output for tool executions:

```python
def print_tool(name: str, args: Dict[str, Any], result: str, compact: bool = True, verbose: bool = False) -> None:
    """Display tool execution results with appropriate formatting."""
    arg_str = ", ".join(f"{k}={repr(v)[:60]}" for k, v in args.items())
    print(f"\n  {C.BPURPLE}▸{C.RST} {C.BRED}{name}{C.RST}{C.GRAY}({arg_str[:100]}){C.RST}")
    
    result = _to_str(result)
    
    if verbose:
        # Full verbose output with nice formatting (rounded corners)
        print(f"  {C.PURPLE}╭{'─' * 70}{C.RST}")
        
        if name in ("fsWrite", "fsAppend"):
            # Show full file content being written
            content = _to_str(args.get("text", args.get("content", "")), join_lists=True)
            path = args.get("path", "")
            print(f"  {C.PURPLE}│{C.RST} {C.BYELLOW}FILE:{C.RST} {path}")
            print(f"  {C.PURPLE}│{C.RST} {C.BYELLOW}CONTENT ({len(content)} chars):{C.RST}")
            _print_highlighted_lines(content, path)
        
        elif name == "strReplace":
            # Show diff-style output for replacements
            path = args.get("path", "")
            old = _to_str(args.get("oldStr", ""), join_lists=True)
            new = _to_str(args.get("newStr", ""), join_lists=True)
            print(f"  {C.PURPLE}│{C.RST} {C.RED}OLD ({len(old)} chars):{C.RST}")
            _print_highlighted_lines(old, path, prefix=f"{C.RED}-{C.RST} ", line_nums=False)
            print(f"  {C.PURPLE}│{C.RST} {C.GREEN}NEW ({len(new)} chars):{C.RST}")
            _print_highlighted_lines(new, path, prefix=f"{C.GREEN}+{C.RST} ", line_nums=False)
        
        print(f"  {C.PURPLE}╰{'─' * 70}{C.RST}")
```


### Code Verification System

Supercoder includes automatic code verification after file writes:

```python
def run_py_compile(path: str) -> Tuple[bool, str]:
    """Verify Python file syntax using py_compile."""
    if not path.endswith('.py'):
        return True, ""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr or result.stdout
    except Exception as e:
        return False, str(e)

def _verify_writes(state: State) -> None:
    """Verify recently written files based on verification mode."""
    if state.verify_mode == "off" or not state.recent_writes:
        return
    errors = []
    for path in state.recent_writes[-5:]:
        if state.verify_mode == "py_compile" and path.endswith('.py'):
            ok, err = run_py_compile(path)
            if not ok:
                errors.append(f"{path}: {err}")
        elif state.verify_mode == "custom" and state.verify_cmd:
            cmd = state.verify_cmd.replace("{file}", _quote_arg(path))
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                errors.append(f"{path}: {result.stderr or result.stdout}")
    
    if errors:
        state.verify_summary = f"{len(errors)} error(s)"
        state.verify_detail = "\n".join(errors)
        status(f"Verification: {state.verify_summary}", "warning")
    else:
        state.verify_summary = "OK"
        state.verify_detail = ""
```

### Prompt Loading System

Agent prompts are loaded from markdown files in the Agents directory:

```python
@lru_cache(maxsize=8)
def load_prompt(name: str) -> str:
    """Load a prompt template from the Agents directory."""
    path = AGENTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding='utf-8')
    return ""

DEFAULT_EXECUTOR = load_prompt("Executor") or "You are a helpful coding assistant."
```

### Continuation Prompt Builder

The system builds context-rich continuation prompts for the AI:

```python
def build_continue_prompt(state: State, last_tools: List[str], had_content: bool) -> str:
    """Build a context-rich continue prompt based on what just happened."""
    parts = []
    
    if state.task:
        parts.append(f"Original goal: {_shorten(state.task, 150)}")
    
    if last_tools:
        parts.append(f"You just used: {', '.join(last_tools[-5:])}")
    
    if state.recent_writes:
        recent = [Path(p).name for p in state.recent_writes[-3:]]
        parts.append(f"Recently modified: {', '.join(recent)}")
    
    if state.verify_summary and "error" in state.verify_summary.lower():
        parts.append(f"⚠️ Verification issue: {state.verify_summary}")
    
    context = "\n".join(parts)
    
    if had_content and not last_tools:
        return f"""Context:
{context}

You explained something but didn't take action. Either:
1. Use tools to make progress on the task
2. Call finish() if the task is complete
3. Call interactWithUser() if you need clarification

What's your next action?"""
    else:
        return f"""Context:
{context}

Continue working on the task. What's the next step? 
Remember: Call finish() with a summary when the task is complete."""
```

### Main Execution Loop

The heart of Supercoder is its main execution loop:

```python
def run(agent: Agent, state: State) -> None:
    """Main execution loop for Supercoder."""
    global _last_interrupt
    import time as _time
    
    header()
    cmd_help(state, agent, "")
    _check_and_prompt_tokens()
    
    status(f"Working directory: {os.getcwd()}", "info")
    divider()
    
    done, total = _get_task_progress()
    if total > 0:
        status(f"Tasks: {done}/{total} complete. Use 'tasks' to view, 'task next' to continue.", "info")
    
    pending_prompt: Optional[str] = None

    while True:
        try:
            if pending_prompt:
                user_input = pending_prompt
                pending_prompt = None
            else:
                user_input = get_input()
            
            if not user_input.strip():
                continue
            
            # Command parsing and execution
            cmd_line = user_input.strip()
            cmd_name = cmd_line.split()[0].lower() if cmd_line else ""
            cmd_args = cmd_line[len(cmd_name):].strip()
            
            if cmd_name in _SHORTCUTS:
                cmd_name = _SHORTCUTS[cmd_name]
            
            # Handle compound commands like "task do"
            if cmd_name == "task" and cmd_args:
                sub = cmd_args.split()[0].lower()
                full_cmd = f"task {sub}"
                if full_cmd in _COMMANDS:
                    cmd_name = full_cmd
                    cmd_args = cmd_args[len(sub):].strip()
            
            if cmd_name in _COMMANDS:
                handler, _ = _COMMANDS[cmd_name]
                result = handler(state, agent, cmd_args)
                if isinstance(result, str):
                    pending_prompt = result
                continue

            # AI interaction loop
            state.task = user_input if not state.task else state.task
            state.auto_steps = 0
            blurb = state_blurb(state)
            full_prompt = f"{blurb}\n\nUser request: {user_input}" if blurb else user_input

            while True:
                if state.auto_mode and state.auto_steps >= state.auto_cap:
                    status(f"Auto cap reached ({state.auto_cap} steps)", "warning")
                    break
                
                state.auto_steps += 1
                
                def on_chunk(chunk: str):
                    print(chunk, end='', flush=True)
                
                content, tool_calls = agent.PromptWithTools(full_prompt, streaming=True, on_chunk=on_chunk)
                had_content = bool(content)
                
                if content:
                    print()
                
                tools_used_this_turn = []
                
                if not tool_calls:
                    if state.auto_mode:
                        if had_content:
                            full_prompt = "You just explained your plan. Now execute it by using the appropriate tools."
                        else:
                            full_prompt = build_continue_prompt(state, tools_used_this_turn, had_content)
                        continue
                    else:
                        break
                
                should_stop = False
                for tc in tool_calls:
                    name = tc["name"]
                    args = tc["args"]
                    tc_id = tc["id"]
                    tools_used_this_turn.append(name)
                    
                    # Handle special tools
                    if name == "finish":
                        summary = args.get("summary", "Task complete")
                        _print_completion_box(summary, success=True)
                        if state.current_task_num > 0:
                            _update_task_status(state.current_task_num, True)
                            state.current_task_num = 0
                        should_stop = True
                        agent.AddToolResult(tc_id, name, "Acknowledged. Waiting for user.")
                        break
                    
                    if name == "interactWithUser":
                        msg = args.get("message", "")
                        itype = args.get("interactionType", "info")
                        if itype == "complete":
                            _print_completion_box(msg, success=True)
                            should_stop = True
                        elif itype == "error":
                            _print_completion_box(msg, success=False)
                            should_stop = True
                        else:
                            status(msg, "info")
                            answer = input(f"{C.BPURPLE}  ╰─▸ {C.RST}")
                            agent.AddToolResult(tc_id, name, f"User response: {answer}")
                            full_prompt = answer
                        continue
                    
                    # Execute regular tools
                    result = execute_tool(tc)
                    
                    # Track file operations
                    if name in ("fsWrite", "fsAppend", "strReplace"):
                        path = args.get("path", "")
                        if path:
                            _push_unique(state.recent_writes, _norm_path(path))
                    elif name in ("readFile", "readCode", "readMultipleFiles"):
                        paths = args.get("paths", [args.get("path", "")])
                        for p in paths:
                            if p:
                                _push_unique(state.recent_reads, _norm_path(p))
                    
                    print_tool(name, args, result, state.compact, state.verbose)
                    agent.AddToolResult(tc_id, name, compress_console(result))
                
                if should_stop:
                    break
                
                _verify_writes(state)
                
                if not state.auto_mode:
                    cont = input(f"{C.BPURPLE}  ╰─▸ {C.BYELLOW}continue?{C.RST} {C.GRAY}(y/n){C.RST} ")
                    if cont.lower() not in ('y', 'yes', ''):
                        break
                
                full_prompt = build_continue_prompt(state, tools_used_this_turn, had_content)
            
            state.recent_writes.clear()
            
        except KeyboardInterrupt:
            now = _time.time()
            if now - _last_interrupt < _INTERRUPT_WINDOW:
                print(f"\n\n  {C.BPURPLE}Goodbye!{C.RST}\n")
                sys.exit(0)
            else:
                _last_interrupt = now
                print(f"\n  {C.BYELLOW}[!] Interrupted. Press Ctrl+C again to exit.{C.RST}")
                state.reset_task()
                pending_prompt = None
                continue
```

### Entry Point

```python
def main():
    """Application entry point."""
    if sys.platform == "win32":
        try:
            os.system("")  # Enable ANSI escape codes on Windows
        except Exception:
            pass
    
    agent = Agent(
        initial_prompt=DEFAULT_EXECUTOR,
        model="qwen/qwen3-coder:free",
        streaming=True
    )
    state = State()
    run(agent, state)

if __name__ == "__main__":
    main()
```


---

## Agentic.py - The AI Agent Framework

### Overview

`Agentic.py` is the AI agent framework that powers Supercoder. At **730 lines**, it provides the core infrastructure for AI model communication, context management, and tool execution.

### Token Management System

The `TokenManager` class handles API key management with support for multiple tokens and automatic rotation:

```python
class TokenManager:
    """Manages API tokens with rotation support."""
    _tokens = None
    _current_index = 0
    _global_tokens_path = Path.home() / ".supercoder" / "tokens.txt"

    @classmethod
    def load_tokens(cls):
        """Load tokens from various locations with fallback."""
        if cls._tokens is None:
            paths = [
                cls._global_tokens_path,
                _get_agentic_base_path() / ".Information" / "tokens.txt",
                Path(".Information/tokens.txt"),
            ]
            for p in paths:
                if p.exists():
                    try:
                        cls._tokens = [line.strip() for line in p.read_text().splitlines() if line.strip()]
                        if cls._tokens:
                            print(f"[Loaded {len(cls._tokens)} API token(s) from {p}]")
                            return
                    except Exception as e:
                        print(f"[Warning: Could not read tokens from {p}: {e}]")
            raise FileNotFoundError("No API tokens found.")

    @classmethod
    def get_token(cls):
        """Get the current active token."""
        cls.load_tokens()
        return cls._tokens[cls._current_index]

    @classmethod
    def rotate_token(cls):
        """Rotate to the next available token."""
        if cls._tokens and len(cls._tokens) > 1:
            cls._current_index = (cls._current_index + 1) % len(cls._tokens)
            print(f"[Rotated to token {cls._current_index + 1}/{len(cls._tokens)}]")
```

### Token Counter

The `TokenCounter` class estimates token usage for context management:

```python
class TokenCounter:
    """Token counter with tiktoken support (dev) or character-based fallback."""

    def __init__(self):
        self._encoder = None
        # Skip tiktoken in bundled exe - use fallback only
        if getattr(sys, 'frozen', False):
            return
        try:
            import tiktoken
            self._encoder = tiktoken.get_encoding("cl100k_base")
        except:
            pass

    def count(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0
        if self._encoder:
            try:
                return len(self._encoder.encode(text))
            except Exception:
                pass
        return max(len(text) // 4, 1)  # Fallback: ~4 chars per token

    def count_messages(self, messages: List[dict]) -> int:
        """Count tokens in a message list."""
        total = 0
        for msg in messages:
            content = msg.get("content") or ""
            if isinstance(content, list):
                text_content = ""
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        text_content += part["text"]
                total += self.count(text_content) + 4
            else:
                total += self.count(content) + 4
        return total + 3
```

### Native Tool Definitions

Agentic.py defines all available tools in a standardized format:

```python
NATIVE_TOOLS = [
    {"type": "function", "function": {
        "name": "executePwsh",
        "description": "Execute a shell command",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)"}
            },
            "required": ["command"]
        }
    }},
    # ... 30+ more tool definitions
]
```

**Complete Tool List:**

| Category | Tools |
|----------|-------|
| Shell | `executePwsh`, `controlPwshProcess`, `listProcesses`, `getProcessOutput` |
| File System | `listDirectory`, `readFile`, `readMultipleFiles`, `readCode`, `fsWrite`, `fsAppend`, `deleteFile`, `moveFile`, `copyFile`, `createDirectory` |
| Code Editing | `strReplace`, `insertLines`, `removeLines` |
| Search | `fileSearch`, `grepSearch`, `findReferences` |
| Analysis | `getDiagnostics`, `getSymbols`, `propertyCoverage`, `fileDiff` |
| Code Quality | `formatCode`, `runTests` |
| Network | `httpRequest`, `downloadFile`, `webSearch`, `searchStackOverflow` |
| System | `systemInfo`, `undo` |
| Interaction | `interactWithUser`, `finish` |

### Model Context Limits

Pre-defined context limits for popular models:

```python
MODEL_LIMITS = {
    "anthropic/claude-opus-4.5": 200000,
    "anthropic/claude-sonnet-4": 200000,
    "qwen/qwen3-coder": 128000,
    "deepseek/deepseek-v3.2": 160000,
    "qwen/qwen3-235b-a22b": 128000,
    "anthropic/claude-3-opus": 200000,
    "anthropic/claude-3-sonnet": 200000,
    "openai/gpt-4-turbo": 128000,
    "default": 128000
}
```

### File Indexer

The `FileIndexer` class provides lightweight file indexing for context retrieval:

```python
class FileIndexer:
    """Lightweight file indexer for context retrieval."""
    
    def __init__(self, index_path: Path = None, max_file_bytes: int = 200_000):
        self.index_path = index_path or Path(".supercoder/index.json")
        self.max_file_bytes = max_file_bytes
        self.index: Dict[str, Any] = {"files": {}, "built_at": time.time()}
        self._stop = {"the","a","an","and","or","of","to","in","on","for","with",...}
        self._ignore_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".supercoder", ".Information"}
        self._ignore_exts = {".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib"}
        self.load()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for indexing."""
        tokens = []
        word = []
        for ch in text.lower():
            if ch.isalnum() or ch == '_':
                word.append(ch)
            else:
                if word:
                    tokens.append("".join(word))
                    word = []
        if word:
            tokens.append("".join(word))
        return [t for t in tokens if t and t not in self._stop and len(t) > 2]

    def build(self, root: str = ".") -> None:
        """Build the file index."""
        root_path = Path(root)
        files = {}
        for r, dirs, filenames in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in self._ignore_dirs]
            for fname in filenames:
                p = Path(r) / fname
                if p.suffix in self._ignore_exts:
                    continue
                tokens = self._file_tokens(p)
                if not tokens:
                    continue
                files[str(p)] = {
                    "mtime": p.stat().st_mtime,
                    "size": p.stat().st_size,
                    "tokens": tokens[:800]
                }
        self.index = {"files": files, "built_at": time.time()}
        self.save()

    def search(self, query: str, limit: int = 8) -> List[str]:
        """Search the index for relevant files."""
        if not query or not self.index.get("files"):
            return []
        q_tokens = set(self._tokenize(query))
        if not q_tokens:
            return []
        scored = []
        for path, meta in self.index["files"].items():
            file_tokens = meta.get("tokens", [])
            if not file_tokens:
                continue
            score = sum(1 for qt in q_tokens if qt in set(file_tokens))
            if score > 0:
                scored.append((score, meta.get("mtime", 0), path))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [p for _, _, p in scored[:limit]]
```


### The Agent Class

The `Agent` class is the core of the AI interaction system:

```python
class Agent:
    """AI Agent with context management and tool support."""
    
    def __init__(self, initial_prompt: str, model: str = "qwen/qwen3-coder:free", 
                 streaming: bool = False, embedding_model: str = None):
        self.model = model
        self.streaming = streaming
        self.messages = []
        self.context_files = []
        self.mandatory_files = []
        self._context_cache = {}
        self.indexer = FileIndexer()
        self.token_counter = TokenCounter()
        self.max_context = MODEL_LIMITS.get(model, MODEL_LIMITS["default"])
        self.reserved_output = 4096
        self.messages.append({"role": "system", "content": initial_prompt})
```

**Key Methods:**

#### Context Building

```python
def _build_context_string(self, hint_text: str = "") -> str:
    """Build context string from files with intelligent selection."""
    all_files = self.mandatory_files + [f for f in self.context_files if f not in self.mandatory_files]
    
    if not all_files:
        # Use retrieval to find relevant files
        retrieval_hits = self.indexer.search(hint_text, limit=8) if self.indexer else []
        all_files = retrieval_hits
        self.context_files = retrieval_hits
        if not all_files:
            return ""

    current_tokens = self.token_counter.count_messages(self.messages)
    available = self.max_context - self.reserved_output - current_tokens - 1000
    parts = ["## Context Files:\n"]
    used_tokens = self.token_counter.count(parts[0])
    included = 0
    skipped_files = []

    # Include mandatory files first
    for f in self.mandatory_files:
        try:
            file_content = Path(f).read_text(encoding='utf-8')
            file_block = f"### {f}\n```\n{file_content}\n```\n"
            file_tokens = self.token_counter.count(file_block)
            parts.append(file_block)
            used_tokens += file_tokens
            included += 1
        except Exception as e:
            print(f"[Warning: Could not read mandatory file {f}: {e}]")

    # Rank and include optional files
    optional_files = [f for f in self.context_files if f not in self.mandatory_files]
    if self.indexer:
        retrieved = self.indexer.search(hint_text, limit=12)
        for f in retrieved:
            if f not in optional_files and f not in self.mandatory_files:
                optional_files.append(f)

    if hint_text:
        ranked = sorted(optional_files, key=lambda p: (
            self._score_file(p, hint_text),
            Path(p).stat().st_mtime if Path(p).exists() else 0
        ), reverse=True)
    else:
        ranked = sorted(optional_files, key=lambda p: 
            Path(p).stat().st_mtime if Path(p).exists() else 0, reverse=True)

    for f in ranked:
        try:
            file_content = self._get_cached_content(f)
            file_block = f"### {f}\n```\n{file_content}\n```\n"
            file_tokens = self.token_counter.count(file_block)
            if used_tokens + file_tokens <= available:
                parts.append(file_block)
                used_tokens += file_tokens
                included += 1
            else:
                skipped_files.append(f)
        except Exception as e:
            print(f"[Warning: Could not read optional file {f}: {e}]")

    if skipped_files:
        print(f"[Context: {included} files, {len(skipped_files)} optional files skipped, ~{used_tokens} tokens]")
        parts.append("## Skipped files (not included, available via tools):\n")
        for f in skipped_files:
            parts.append(f"- {f}\n")
    
    return "\n".join(parts)
```

#### Prompting Methods

```python
def Prompt(self, user_input: str, streaming: bool = None) -> str:
    """Send a prompt and get a response (no tools)."""
    if streaming is None:
        streaming = self.streaming
    context = self._build_context_string(user_input)
    full_input = f"{context}\n\n{user_input}" if context else user_input
    self.messages.append({"role": "user", "content": full_input})
    response = self._call_api(streaming=streaming)
    self.messages.append({"role": "assistant", "content": response})
    self.context_files = []
    return response

def PromptWithTools(self, user_input: str, tools: List[dict] = None, 
                    streaming: bool = False, on_chunk=None) -> Tuple[str, List[dict]]:
    """Send a prompt with tool support."""
    if tools is None:
        tools = NATIVE_TOOLS
    context = self._build_context_string(user_input)
    current_messages = list(self.messages)
    full_input = f"{context}\n\n{user_input}" if context else user_input
    current_messages.append({"role": "user", "content": full_input})
    self.messages.append({"role": "user", "content": user_input})
    
    original_messages = self.messages
    self.messages = current_messages
    try:
        content, tool_calls = self._call_api_with_tools(tools, streaming=streaming, on_chunk=on_chunk)
    finally:
        self.messages = original_messages

    assistant_msg = {"role": "assistant", "content": content or None}
    if tool_calls:
        assistant_msg["tool_calls"] = [
            {"id": tc["id"], "type": "function", 
             "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
            for tc in tool_calls
        ]
    self.messages.append(assistant_msg)
    self.context_files = []
    return content, tool_calls
```

#### API Communication

```python
def _call_api_with_tools(self, tools: List[dict], streaming: bool = False, 
                         on_chunk=None) -> Tuple[str, List[dict]]:
    """Call the OpenRouter API with tool support."""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            token = TokenManager.get_token()
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": self.messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "stream": streaming
                },
                timeout=120,
                stream=streaming
            )
            resp.raise_for_status()
            
            if streaming:
                content = ""
                tool_calls_data = {}
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        line = line[6:]
                    if line == '[DONE]':
                        break
                    try:
                        data = json.loads(line)
                        delta = data['choices'][0].get('delta', {})
                        if 'content' in delta and delta['content']:
                            chunk = delta['content']
                            content += chunk
                            if on_chunk:
                                on_chunk(chunk)
                        if 'tool_calls' in delta:
                            for tc in delta['tool_calls']:
                                idx = tc.get('index', 0)
                                if idx not in tool_calls_data:
                                    tool_calls_data[idx] = {'id': '', 'name': '', 'arguments': ''}
                                if 'id' in tc:
                                    tool_calls_data[idx]['id'] = tc['id']
                                if 'function' in tc:
                                    if 'name' in tc['function']:
                                        tool_calls_data[idx]['name'] = tc['function']['name']
                                    if 'arguments' in tc['function']:
                                        tool_calls_data[idx]['arguments'] += tc['function']['arguments']
                    except:
                        pass
                
                parsed_calls = []
                for idx in sorted(tool_calls_data.keys()):
                    tc = tool_calls_data[idx]
                    try:
                        args = json.loads(tc['arguments']) if tc['arguments'] else {}
                    except:
                        args = {}
                    if tc['name']:
                        parsed_calls.append({"id": tc['id'], "name": tc['name'], "args": args})
                return content, parsed_calls
            else:
                # Non-streaming response handling
                data = resp.json()
                message = data["choices"][0]["message"]
                content = message.get("content") or ""
                raw_tool_calls = message.get("tool_calls", [])
                parsed_calls = []
                for tc in raw_tool_calls:
                    if tc.get("type") == "function":
                        try:
                            args = json.loads(tc["function"]["arguments"])
                        except:
                            args = {}
                        parsed_calls.append({
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "args": args
                        })
                return content, parsed_calls
                
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status in (401, 403, 429):
                TokenManager.rotate_token()
            time.sleep(2 ** attempt)
        except Exception as e:
            time.sleep(2 ** attempt)
    
    return "[Error: All API attempts failed]", []
```

### Tool Execution Function

The `execute_tool` function routes tool calls to their implementations:

```python
def execute_tool(tool_call: dict) -> str:
    """Execute a tool call and return result."""
    from tools import (
        execute_pwsh, control_pwsh_process, list_processes, get_process_output,
        list_directory, read_file, read_multiple_files, read_code, file_search, grep_search,
        delete_file, fs_write, fs_append, str_replace, get_diagnostics, property_coverage,
        insert_lines, remove_lines, move_file, copy_file, create_directory, undo,
        get_symbols, find_references, file_diff, http_request, download_file,
        system_info, run_tests, format_code, web_search, search_stackoverflow,
        interact_with_user, finish
    )

    name = tool_call["name"]
    args = tool_call.get("args", {})

    # Parameter validation
    REQUIRED_PARAMS = {
        "executePwsh": ["command"],
        "readFile": ["path"],
        "fsWrite": ["path", "content"],
        "fsAppend": ["path", "content"],
        "strReplace": ["path", "old", "new"],
        "deleteFile": ["path"],
        "getDiagnostics": ["path"],
        "fileSearch": ["pattern"],
        "grepSearch": ["pattern"],
        "getProcessOutput": ["processId"],
        "controlPwshProcess": ["action"],
        "interactWithUser": ["message", "interactionType"],
    }

    if name in REQUIRED_PARAMS:
        missing = [p for p in REQUIRED_PARAMS[name] if p not in args or args[p] is None]
        if missing:
            return f"ERROR: {name} requires parameters: {missing}."

    try:
        # Route to appropriate tool implementation
        if name == "executePwsh":
            result = execute_pwsh(args["command"], args.get("timeout", 60))
            return f"stdout: {result['stdout']}\nstderr: {result['stderr']}\nreturncode: {result['returncode']}"
        elif name == "readFile":
            return read_file(args["path"])
        # ... (30+ more tool handlers)
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error executing {name}: {e}"
```


---

## Tools.py - The Tool Library

### Overview

`tools.py` provides the actual implementations for all tools available to the AI agent. At approximately **600 lines**, it contains file operations, shell execution, code analysis, web search, and more.

### Undo System

The undo system provides transaction-based file operation rollback:

```python
@dataclass
class FileSnapshot:
    """Snapshot of a file's state for undo operations."""
    path: str
    content: Optional[str]
    existed: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

class UndoManager:
    """Manages file operation history for undo functionality."""
    
    def __init__(self, max_history: int = 100):
        self.history: List[List[FileSnapshot]] = []
        self.max_history = max_history
        self._lock = threading.Lock()
    
    def snapshot(self, paths: List[str]) -> int:
        """Create a snapshot of files before modification."""
        snapshots = []
        for path in paths:
            p = Path(path)
            if p.exists():
                try:
                    content = p.read_text(encoding='utf-8')
                    snapshots.append(FileSnapshot(path=path, content=content, existed=True))
                except:
                    snapshots.append(FileSnapshot(path=path, content=None, existed=True))
            else:
                snapshots.append(FileSnapshot(path=path, content=None, existed=False))
        
        with self._lock:
            self.history.append(snapshots)
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
            return len(self.history) - 1

    def undo(self, transaction_id: Optional[int] = None) -> Dict[str, Any]:
        """Undo a file operation transaction."""
        with self._lock:
            if not self.history:
                return {"error": "No history to undo"}
            
            if transaction_id is None:
                transaction_id = len(self.history) - 1
            
            if transaction_id < 0 or transaction_id >= len(self.history):
                return {"error": f"Invalid transaction ID: {transaction_id}"}
            
            snapshots = self.history[transaction_id]
            restored = []
            
            for snap in snapshots:
                try:
                    if snap.existed and snap.content is not None:
                        Path(snap.path).parent.mkdir(parents=True, exist_ok=True)
                        Path(snap.path).write_text(snap.content, encoding='utf-8')
                        restored.append(f"Restored: {snap.path}")
                    elif not snap.existed and Path(snap.path).exists():
                        Path(snap.path).unlink()
                        restored.append(f"Deleted (was new): {snap.path}")
                except Exception as e:
                    restored.append(f"Failed {snap.path}: {e}")
            
            self.history = self.history[:transaction_id]
            return {"restored": restored}

undo_manager = UndoManager()
```

### Shell Execution

```python
def execute_pwsh(command: str, timeout: int = 60) -> Dict[str, Any]:
    """Execute a shell command."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {'stdout': '', 'stderr': f'Timed out after {timeout}s', 'returncode': -1}
    except Exception as e:
        return {'stdout': '', 'stderr': str(e), 'returncode': -1}
```

### Background Process Management

```python
_background_processes: Dict[int, subprocess.Popen] = {}
_process_counter = 0

def control_pwsh_process(action: str, command: str = None, 
                         process_id: int = None, path: str = None) -> Dict[str, Any]:
    """Start or stop background processes."""
    global _process_counter
    
    if action == "start":
        if not command:
            return {"error": "command required for start"}
        try:
            cwd = path if path else os.getcwd()
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd
            )
            _process_counter += 1
            _background_processes[_process_counter] = proc
            return {"processId": _process_counter, "status": "started"}
        except Exception as e:
            return {"error": str(e)}
    
    elif action == "stop":
        if process_id is None:
            return {"error": "processId required for stop"}
        if process_id not in _background_processes:
            return {"error": f"Process {process_id} not found"}
        try:
            _background_processes[process_id].terminate()
            del _background_processes[process_id]
            return {"success": True, "message": f"Process {process_id} stopped"}
        except Exception as e:
            return {"error": str(e)}
    
    return {"error": f"Unknown action: {action}"}
```

### File System Operations

```python
def list_directory(path: str = ".") -> Dict[str, Any]:
    """List directory contents."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Path does not exist: {path}"}
    
    entries = []
    for child in p.iterdir():
        entries.append({
            "name": child.name,
            "is_dir": child.is_dir(),
            "size": child.stat().st_size if child.is_file() else None
        })
    return {"entries": sorted(entries, key=lambda x: (not x["is_dir"], x["name"]))}

def read_file(path: str) -> str:
    """Read a file's contents."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def fs_write(path: str, content: str) -> Dict[str, Any]:
    """Write content to a file."""
    undo_manager.snapshot([path])
    try:
        if not isinstance(content, str):
            content = json.dumps(content, indent=2)
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"written": path, "bytes": len(content)}
    except Exception as e:
        return {"error": str(e)}

def str_replace(path: str, old: str, new: str) -> Dict[str, Any]:
    """Replace text in a file."""
    undo_manager.snapshot([path])
    try:
        # Handle non-string inputs
        if not isinstance(old, str):
            if isinstance(old, list):
                old = '\n'.join(str(item) for item in old)
            else:
                old = str(old)
        if not isinstance(new, str):
            if isinstance(new, list):
                new = '\n'.join(str(item) for item in new)
            else:
                new = str(new)
        
        content = read_file(path)
        if old not in content:
            return {"error": f"Text not found in {path}"}
        new_content = content.replace(old, new, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return {"replaced": path, "occurrences": content.count(old)}
    except Exception as e:
        return {"error": str(e)}
```

### Code Analysis with AST

```python
def read_code(path: str, symbol: str = None, include_structure: bool = True) -> Dict[str, Any]:
    """Intelligently read code files with AST-based structure analysis."""
    import ast
    
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}
    
    try:
        content = p.read_text(encoding='utf-8')
    except Exception as e:
        return {"error": f"Could not read file: {e}"}
    
    result = {
        "path": path,
        "content": content,
        "lines": len(content.splitlines()),
        "size_bytes": len(content.encode('utf-8'))
    }
    
    # AST analysis for Python files
    if p.suffix == ".py" and include_structure:
        try:
            tree = ast.parse(content)
            structure = {
                "functions": [],
                "classes": [],
                "imports": [],
                "global_vars": []
            }
            
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    args = [arg.arg for arg in node.args.args]
                    structure["functions"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "end_line": node.end_lineno,
                        "args": args,
                        "decorators": [ast.unparse(d) for d in node.decorator_list]
                    })
                elif isinstance(node, ast.ClassDef):
                    methods = [item.name for item in node.body 
                              if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    structure["classes"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "end_line": node.end_lineno,
                        "methods": methods,
                        "bases": [ast.unparse(b) for b in node.bases]
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        structure["imports"].append({
                            "module": alias.name,
                            "alias": alias.asname,
                            "line": node.lineno
                        })
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        structure["imports"].append({
                            "module": f"{node.module}.{alias.name}",
                            "alias": alias.asname,
                            "line": node.lineno
                        })
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            structure["global_vars"].append({
                                "name": target.id,
                                "line": node.lineno
                            })
            
            result["structure"] = structure
        except SyntaxError as e:
            result["structure_error"] = f"Syntax error: {e}"
    
    # JavaScript/TypeScript basic structure (regex-based)
    elif p.suffix in (".js", ".ts", ".jsx", ".tsx") and include_structure:
        structure = {"functions": [], "classes": [], "imports": [], "exports": []}
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            func_match = re.match(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', line)
            if func_match:
                structure["functions"].append({"name": func_match.group(1), "line": i})
            # ... more patterns
        result["structure"] = structure
    
    # Symbol search
    if symbol:
        symbol_locations = []
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            if re.search(r'\b' + re.escape(symbol) + r'\b', line):
                symbol_locations.append({
                    "line": i,
                    "text": line.strip()[:150],
                    "is_definition": bool(re.match(
                        rf'(?:def|class|function|const|let|var)\s+{re.escape(symbol)}\b',
                        line.strip()
                    ))
                })
        result["symbol_search"] = {
            "symbol": symbol,
            "occurrences": len(symbol_locations),
            "locations": symbol_locations[:50]
        }
    
    return result
```


### Search Functions

```python
def file_search(pattern: str, path: str = ".") -> Dict[str, Any]:
    """Search for files by name pattern."""
    matches = []
    pattern_lower = pattern.lower()
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.venv', 'venv'}]
        for f in files:
            if pattern_lower in f.lower():
                matches.append(os.path.join(root, f))
    return {"matches": matches[:100]}

def grep_search(pattern: str, path: str = ".") -> Dict[str, Any]:
    """Search for regex pattern in files."""
    if not isinstance(pattern, str):
        pattern = str(pattern)
    
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return {"error": f"Invalid regex: {e}"}
    
    hits = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.venv', 'venv'}]
        for f in files:
            filepath = os.path.join(root, f)
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    for i, line in enumerate(file, 1):
                        if regex.search(line):
                            hits.append({
                                "file": filepath,
                                "line": i,
                                "text": line.strip()[:200]
                            })
                            if len(hits) >= 100:
                                return {"hits": hits, "truncated": True}
            except:
                continue
    return {"hits": hits}
```

### Web Search Integration

```python
def web_search(query: str, site: str = None, max_results: int = 5) -> Dict[str, Any]:
    """Search the web for programming help using DuckDuckGo."""
    import urllib.request
    import urllib.parse
    from html.parser import HTMLParser
    
    search_query = query
    if site:
        search_query = f"site:{site} {query}"
    
    encoded_query = urllib.parse.quote_plus(search_query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
        
        # Custom HTML parser for DuckDuckGo results
        class DDGParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results = []
                self.current_result = {}
                self.in_result = False
                self.in_title = False
                self.in_snippet = False
                self.current_text = ""
            
            # ... parsing logic
        
        parser = DDGParser()
        parser.feed(html)
        
        results = parser.results[:max_results]
        
        return {
            "query": query,
            "site_filter": site,
            "results": results
        }
        
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}

def search_stackoverflow(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search Stack Overflow specifically."""
    return web_search(query, site="stackoverflow.com", max_results=max_results)
```

### User Interaction Tools

```python
def interact_with_user(message: str, interaction_type: str = "info") -> Dict[str, Any]:
    """Signal that the agent wants to interact with the user."""
    return {
        "_interaction": True,
        "message": message,
        "type": interaction_type
    }

def finish(summary: str, status: str = "complete") -> Dict[str, Any]:
    """Signal that the agent has finished its current task."""
    return {
        "_finish": True,
        "summary": summary,
        "status": status
    }
```

### Additional Utility Tools

```python
def get_diagnostics(path: str) -> Dict[str, Any]:
    """Check for syntax/lint errors."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Path not found: {path}"}
    
    errors = []
    
    if p.suffix == ".py":
        result = execute_pwsh(f'python -m py_compile "{path}"')
        if result["returncode"] != 0:
            errors.append({"type": "syntax", "message": result["stderr"]})
    
    elif p.suffix == ".json":
        try:
            with open(path, 'r') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            errors.append({"type": "syntax", "message": str(e)})
    
    return {"path": path, "errors": errors, "valid": len(errors) == 0}

def format_code(path: str) -> Dict[str, Any]:
    """Format code file using black (Python) or prettier (JS/TS)."""
    undo_manager.snapshot([path])
    if Path(path).suffix == ".py":
        result = execute_pwsh(f'python -m black "{path}" 2>&1', timeout=30)
    else:
        result = execute_pwsh(f'npx prettier --write "{path}" 2>&1', timeout=30)
    return {"formatted": path, "output": result["stdout"]}

def run_tests(path: str = ".") -> Dict[str, Any]:
    """Run tests using pytest."""
    result = execute_pwsh(f'python -m pytest "{path}" -v', timeout=120)
    return {
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "passed": result["returncode"] == 0
    }

def system_info() -> Dict[str, Any]:
    """Get system information."""
    import platform
    return {
        "os": platform.system(),
        "python": platform.python_version(),
        "cwd": os.getcwd()
    }
```

---

## Inter-Module Communication

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER INPUT                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        supercoder.py                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. Parse command or natural language input                          │    │
│  │  2. Build state context (pinned files, recent operations)            │    │
│  │  3. Call agent.PromptWithTools()                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Agentic.py                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. Build context string from files                                  │    │
│  │  2. Manage conversation history                                      │    │
│  │  3. Call OpenRouter API with tools                                   │    │
│  │  4. Parse streaming response and tool calls                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenRouter API                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  AI Model (Claude, GPT-4, Qwen, etc.)                                │    │
│  │  Returns: content + tool_calls                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Agentic.py                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  execute_tool() - Routes tool calls to tools.py                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          tools.py                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Execute actual operations:                                          │    │
│  │  - File read/write/modify                                            │    │
│  │  - Shell commands                                                    │    │
│  │  - Code analysis                                                     │    │
│  │  - Web search                                                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        supercoder.py                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. Display tool results                                             │    │
│  │  2. Update state (recent_writes, recent_reads)                       │    │
│  │  3. Run verification if enabled                                      │    │
│  │  4. Build continuation prompt or wait for user                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```


---

## Configuration and Customization

### Directory Structure

```
project/
├── supercoder.py          # Main application
├── Agentic.py             # AI agent framework
├── tools.py               # Tool implementations
├── Agents/                # Agent prompt templates
│   ├── Design.md          # Design generation prompt
│   ├── Executor.md        # Main executor prompt
│   ├── Requirements.md    # Requirements generation prompt
│   └── Tasks.md           # Task generation prompt
├── .supercoder/           # Runtime data directory
│   ├── index.json         # File index for retrieval
│   ├── tasks.md           # Task list
│   ├── requirements.md    # Generated requirements
│   └── design.md          # Generated design
└── ~/.supercoder/         # Global configuration
    └── tokens.txt         # API tokens (one per line)
```

### API Token Configuration

Tokens can be stored in multiple locations (checked in order):
1. `~/.supercoder/tokens.txt` (global)
2. `.Information/tokens.txt` (project-local)
3. Bundled with PyInstaller executable

**Token File Format:**
```
sk-or-v1-your-first-token-here
sk-or-v1-your-second-token-here
```

### Agent Prompt Customization

Agent prompts are loaded from markdown files in the `Agents/` directory:

- **Executor.md**: Main system prompt for the AI assistant
- **Requirements.md**: Template for generating requirements documents
- **Design.md**: Template for generating technical designs
- **Tasks.md**: Template for generating task breakdowns

### Model Selection

Default model: `qwen/qwen3-coder:free`

Available models can be listed with the `models` command. Switch models with:
```
model anthropic/claude-sonnet-4
```

### Verification Modes

| Mode | Description |
|------|-------------|
| `off` | No verification |
| `py_compile` | Python syntax check (default) |
| `<custom>` | Custom command with `{file}` placeholder |

Example custom verification:
```
verify mypy {file}
verify eslint {file}
```

---

## Security Considerations

### API Key Security

- Tokens are stored in user's home directory (`~/.supercoder/tokens.txt`)
- File permissions should be restricted to owner-only
- Tokens are masked when displayed (`sk-or-v1-abc...xyz`)
- Automatic token rotation on 401/403/429 errors

### Shell Execution Safety

- Commands are sanitized for PowerShell compatibility
- Timeout limits prevent runaway processes
- Background processes are tracked and can be terminated

### File System Safety

- Undo system maintains snapshots before modifications
- Maximum 100 transactions in undo history
- Thread-safe operations with locking

### Input Validation

- Required parameters are validated before tool execution
- Non-string inputs are converted appropriately
- Regex patterns are validated before use

---

## Appendices

### Appendix A: Complete Tool Reference

| Tool | Parameters | Description |
|------|------------|-------------|
| `executePwsh` | command, timeout | Execute shell command |
| `controlPwshProcess` | action, command, processId, path | Manage background processes |
| `listProcesses` | - | List running processes |
| `getProcessOutput` | processId, lines | Get process output |
| `listDirectory` | path | List directory contents |
| `readFile` | path | Read file contents |
| `readMultipleFiles` | paths | Read multiple files |
| `readCode` | path, symbol, includeStructure | Read code with AST analysis |
| `fileSearch` | pattern, path | Search files by name |
| `grepSearch` | pattern, path | Search file contents |
| `deleteFile` | path | Delete a file |
| `fsWrite` | path, content | Write/create file |
| `fsAppend` | path, content | Append to file |
| `strReplace` | path, old, new | Replace text in file |
| `insertLines` | path, lineNumber, content | Insert at line |
| `removeLines` | path, startLine, endLine | Remove lines |
| `moveFile` | source, destination | Move/rename file |
| `copyFile` | source, destination | Copy file |
| `createDirectory` | path | Create directory |
| `undo` | transactionId | Undo file operation |
| `getDiagnostics` | path | Check for errors |
| `getSymbols` | path | Extract code symbols |
| `findReferences` | symbol, path | Find symbol references |
| `fileDiff` | path1, path2 | Compare files |
| `propertyCoverage` | specPath, codePath | Analyze coverage |
| `formatCode` | path | Format code file |
| `runTests` | path | Run tests |
| `httpRequest` | url, method, body | Make HTTP request |
| `downloadFile` | url, destination | Download file |
| `webSearch` | query, site, maxResults | Web search |
| `searchStackOverflow` | query, maxResults | Stack Overflow search |
| `systemInfo` | - | Get system info |
| `interactWithUser` | message, interactionType | User interaction |
| `finish` | summary, status | Signal completion |

### Appendix B: Keyboard Shortcuts

| Shortcut | Command |
|----------|---------|
| `q` | quit |
| `exit` | quit |
| `tl` | tasks |
| `td` | task do |
| `tc` | task done |
| `tu` | task undo |
| `tn` | task next |

### Appendix C: Multiline Input

Two methods for multiline input:

1. **Triple angle brackets:**
   ```
   <<<
   Your multiline
   content here
   >>>
   ```

2. **Triple quotes:**
   ```
   """
   Your multiline
   content here
   """
   ```

### Appendix D: Environment Variables

The system respects standard environment variables:
- `HOME` / `USERPROFILE`: User home directory
- `PATH`: For finding executables (pwsh, python, etc.)

### Appendix E: Supported File Types

**Code Files (AST Analysis):**
- Python: `.py`
- JavaScript/TypeScript: `.js`, `.ts`, `.jsx`, `.tsx`
- Other: `.java`, `.go`, `.rs`, `.c`, `.cpp`, `.h`

**Document Files:**
- Markdown: `.md`
- Text: `.txt`
- Data: `.json`, `.yml`, `.yaml`, `.toml`

---

## Conclusion

Supercoder represents a sophisticated implementation of an autonomous AI coding assistant. The three-module architecture provides clean separation of concerns:

- **supercoder.py** handles user interaction, session management, and orchestration
- **Agentic.py** manages AI communication, context building, and tool routing
- **tools.py** provides the actual implementations for all file and system operations

Key strengths of the system include:
- Robust Windows compatibility through PowerShell patching
- Intelligent context management with file indexing and retrieval
- Comprehensive undo system for safe file operations
- Flexible verification system for code quality
- Task management for structured development workflows
- Beautiful terminal UI with syntax highlighting

The modular design allows for easy extension and customization, making Supercoder a powerful foundation for AI-assisted software development.

---

*Document generated for Supercoder v1.0*
*Total codebase: ~2,500 lines of Python*
