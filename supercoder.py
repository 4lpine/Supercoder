#!/usr/bin/env python3
"""
Supercoder - Production-ready AI-powered code generation and task execution

Features:
- Autonomous mode with configurable step limits
- Smart context management with retrieval-augmented generation
- Post-write verification (py_compile or custom commands)
- Multi-model support via OpenRouter API
- Multiline input support
- Session state persistence
"""
from __future__ import annotations

import os
import sys
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

import tools
from Agentic import Agent, execute_tool, MODEL_LIMITS, TokenManager

# ==============================================================================
# Constants & Configuration
# ==============================================================================

WORKING_DIR = Path(__file__).parent
AGENTS_DIR = WORKING_DIR / "Agents"
SUPERCODER_DIR = ".supercoder"

# File extensions for context
CODE_EXTENSIONS: Set[str] = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".h"}
DOC_EXTENSIONS: Set[str] = {".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".xml", ".html", ".css"}
ALL_EXTENSIONS: Set[str] = CODE_EXTENSIONS | DOC_EXTENSIONS

# Limits
MAX_FILE_SIZE = 200_000
MAX_PINNED_FILES = 8
MAX_RECENT_ITEMS = 10

# ==============================================================================
# Shell Compatibility (Windows PowerShell patch)
# ==============================================================================

@lru_cache(maxsize=1)
def _detect_shell() -> Tuple[Optional[str], str]:
    """Detect available shell. Cached for performance."""
    if os.name != "nt":
        return None, "posix shell"
    if shutil.which("pwsh"):
        return "pwsh", "PowerShell Core (pwsh)"
    if shutil.which("powershell"):
        return "powershell", "Windows PowerShell"
    return None, "cmd (fallback)"

_PS_EXE, _PS_LABEL = _detect_shell()

# Precompiled regex for command sanitization
_CMD_SEP_PATTERN = re.compile(r'\s*(?:&&|\|\|)\s*|\s&\s')

def _sanitize_cmd(command: str) -> str:
    """Sanitize command separators for PowerShell."""
    return _CMD_SEP_PATTERN.sub('; ', str(command).strip())

def _execute_pwsh_patched(command: str, timeout: int = 60) -> Dict[str, Any]:
    """Execute command via PowerShell on Windows."""
    if os.name == "nt" and _PS_EXE:
        args = [_PS_EXE, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _sanitize_cmd(command)]
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd())
            return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout.decode("utf-8", "ignore") if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = e.stderr.decode("utf-8", "ignore") if isinstance(e.stderr, bytes) else (e.stderr or "")
            return {"stdout": stdout, "stderr": f"{stderr}\nTimed out after {timeout}s", "returncode": -1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "returncode": 1}
    
    orig = getattr(tools, "_orig_execute_pwsh", None)
    if callable(orig):
        return orig(command, timeout=timeout)
    return {"stdout": "", "stderr": "execute_pwsh not available", "returncode": 1}

def _control_pwsh_patched(action: str, command: str = None, process_id: int = None, path: str = None) -> Dict[str, Any]:
    """Control background processes via PowerShell."""
    if os.name == "nt" and _PS_EXE:
        bg = getattr(tools, "_background_processes", {})
        try:
            if action == "start":
                if not command:
                    return {"error": "command required"}
                args = [_PS_EXE, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _sanitize_cmd(command)]
                proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=path or os.getcwd())
                pid = max(bg.keys(), default=0) + 1
                bg[pid] = proc
                tools._background_processes = bg
                return {"processId": pid, "status": "started"}
            if action == "stop":
                if process_id not in bg:
                    return {"error": f"Process {process_id} not found"}
                bg[process_id].terminate()
                del bg[process_id]
                return {"success": True}
            return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": str(e)}
    
    orig = getattr(tools, "_orig_control_pwsh", None)
    return orig(action, command=command, process_id=process_id, path=path) if callable(orig) else {"error": "not available"}

# Store originals and apply patches
tools._orig_execute_pwsh = getattr(tools, "execute_pwsh", None)
tools._orig_control_pwsh = getattr(tools, "control_pwsh_process", None)
tools.execute_pwsh = _execute_pwsh_patched
tools.control_pwsh_process = _control_pwsh_patched

# ==============================================================================
# ANSI Colors & Output
# ==============================================================================

class C:
    """ANSI color codes."""
    RST = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

def _s(text: str, color: str) -> str:
    """Apply color to text."""
    return f"{color}{text}{C.RST}"

_STATUS_STYLES = {
    "info": (C.BLUE, "[i]"),
    "success": (C.GREEN, "[✓]"),
    "warning": (C.YELLOW, "[!]"),
    "error": (C.RED, "[x]"),
    "context": (C.MAGENTA, "[~]"),
}

def status(msg: str, level: str = "info") -> None:
    """Print a status message."""
    color, prefix = _STATUS_STYLES.get(level, (C.BLUE, "[i]"))
    print(_s(f"  {prefix} {msg}", color))

def header() -> None:
    """Print application header."""
    print()
    print(_s("╭─────────────────────────────────────────────────────────────╮", C.CYAN))
    print(_s("│  > SUPERCODER - AI-Powered Code Generation                  │", C.CYAN))
    print(_s("╰─────────────────────────────────────────────────────────────╯", C.CYAN))
    print()

def divider() -> None:
    """Print a divider line."""
    print(_s("  " + "─" * 57, C.DIM))
    print()

# ==============================================================================
# Input Handling
# ==============================================================================

def get_input(prompt: str = "  > ") -> str:
    """Get user input with multiline support (<<< ... >>> or triple quotes)."""
    try:
        line = input(_s(prompt, C.YELLOW))
        stripped = line.strip()
        
        # Check for multiline markers
        if stripped == "<<<" or stripped.startswith('"""'):
            end = ">>>" if stripped == "<<<" else '"""'
            print(_s(f"  (multiline - end with {end})", C.DIM))
            
            lines = []
            if stripped.startswith('"""') and len(stripped) > 3:
                lines.append(stripped[3:])
            
            while True:
                ln = input(_s("  . ", C.DIM))
                if ln.strip() == end or (end == '"""' and ln.strip().endswith('"""')):
                    if end == '"""' and ln.strip().endswith('"""') and len(ln.strip()) > 3:
                        lines.append(ln.strip()[:-3])
                    break
                lines.append(ln)
            return "\n".join(lines)
        return line
    except (EOFError, KeyboardInterrupt):
        print()
        return "quit"

# ==============================================================================
# OpenRouter Model Management
# ==============================================================================

_model_cache: Dict[str, Dict[str, Any]] = {}
_cache_loaded: bool = False

def fetch_models() -> List[Dict[str, Any]]:
    """Fetch models from OpenRouter API."""
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
    """Get context limit for a model."""
    global _cache_loaded
    
    if model_id in _model_cache:
        return _model_cache[model_id].get("context_length", MODEL_LIMITS["default"])
    if model_id in MODEL_LIMITS:
        return MODEL_LIMITS[model_id]
    
    if not _cache_loaded:
        fetch_models()
        if model_id in _model_cache:
            return _model_cache[model_id].get("context_length", MODEL_LIMITS["default"])
    
    return MODEL_LIMITS["default"]

def model_exists(model_id: str) -> bool:
    """Check if model exists."""
    global _cache_loaded
    if model_id in _model_cache:
        return True
    if not _cache_loaded:
        fetch_models()
    return model_id in _model_cache

def display_models(models: List[Dict[str, Any]], filter_text: str = "") -> None:
    """Display models list."""
    if not models:
        status("No models available", "warning")
        return
    
    if filter_text:
        fl = filter_text.lower()
        models = [m for m in models if fl in m.get("id", "").lower() or fl in m.get("name", "").lower()]
    
    models = sorted(models, key=lambda m: m.get("id", ""))
    
    print()
    print(_s(f"  Available Models ({len(models)}):", C.BOLD))
    print(_s("  " + "─" * 60, C.DIM))
    
    for i, m in enumerate(models, 1):
        mid = m.get("id", "?")
        ctx = m.get("context_length", "?")
        pricing = m.get("pricing", {})
        print(_s(f"  {i:3}. ", C.DIM) + _s(mid, C.CYAN))
        print(_s(f"       Context: {ctx:,} | ${pricing.get('prompt', '?')}/{pricing.get('completion', '?')} per token", C.DIM))
    print()

# ==============================================================================
# Session State
# ==============================================================================

@dataclass
class State:
    """Session state container."""
    task: str = ""
    pinned: List[str] = field(default_factory=list)
    auto_mode: bool = True
    auto_cap: int = 50
    auto_steps: int = 0
    compact: bool = True
    verify_mode: str = "py_compile"  # py_compile | command | off
    verify_cmd: Optional[str] = None
    verify_summary: str = ""
    verify_detail: str = ""
    recent_reads: List[str] = field(default_factory=list)
    recent_writes: List[str] = field(default_factory=list)

    def reset_task(self) -> None:
        """Reset per-task state."""
        self.task = ""
        self.auto_steps = 0
        self.recent_reads.clear()
        self.recent_writes.clear()
        self.verify_summary = ""
        self.verify_detail = ""

def _push_unique(lst: List[str], item: str, cap: int = MAX_RECENT_ITEMS) -> None:
    """Add item to list, keeping it unique and capped."""
    if not item:
        return
    if item in lst:
        lst.remove(item)
    lst.append(item)
    while len(lst) > cap:
        lst.pop(0)

def _norm_path(p: str) -> str:
    """Normalize path to absolute."""
    try:
        return str(Path(p).resolve())
    except Exception:
        return p

def state_blurb(state: State) -> str:
    """Generate context blurb for model."""
    parts = []
    if state.task:
        parts.append(f"Goal: {state.task}")
    parts.append(f"Shell: {_PS_LABEL}. Use ';' as separator.")
    if state.recent_writes:
        parts.append(f"Recent writes: {', '.join(state.recent_writes[-5:])}")
    if state.verify_summary:
        parts.append(f"Verify: {state.verify_summary}")
        if "FAILED" in state.verify_summary and state.verify_detail:
            parts.append(f"Detail:\n{chr(10).join(state.verify_detail.splitlines()[:10])}")
    return "\n".join(parts)

# ==============================================================================
# Output Compression
# ==============================================================================

def _shorten(s: str, max_len: int = 280) -> str:
    """Shorten string with ellipsis."""
    s = " ".join((s or "").split())
    return s if len(s) <= max_len else s[:max_len - 3] + "..."

def _try_json(s: str) -> str:
    """Try to pretty-print JSON."""
    try:
        return json.dumps(json.loads(s), indent=2, ensure_ascii=False)
    except Exception:
        return s

def compress_console(text: str, max_chars: int = 2000) -> str:
    """Compress text for console display."""
    if not text:
        return ""
    text = _try_json(text)
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return f"{text[:half]}\n...\n{text[-half:]}"

def compress_model(tool: str, result: Any, limit: int = 9000) -> str:
    """Compress tool result for model context."""
    if result is None:
        return ""
    s = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
    
    # File reads get more space
    if tool in {"readCode", "readFile"}:
        return s if len(s) <= 20000 else s[:20000] + "\n...[truncated]..."
    
    # Shell output: extract key info
    if tool == "executePwsh":
        try:
            d = json.loads(s) if isinstance(result, str) else result
            if isinstance(d, dict):
                out = f"returncode={d.get('returncode')}\n"
                if d.get("stdout"):
                    out += f"STDOUT:\n{d['stdout']}\n"
                if d.get("stderr"):
                    out += f"STDERR:\n{d['stderr']}"
                s = out
        except Exception:
            pass
    
    if len(s) <= limit:
        return s
    
    lines = s.splitlines()
    if len(lines) <= 300:
        return s[:limit] + "\n...[truncated]..."
    return "\n".join(lines[:60]) + "\n...\n" + "\n".join(lines[-200:])

def print_tool(name: str, args: Dict[str, Any], result: str, compact: bool = True) -> None:
    """Print tool call and result."""
    args_str = _shorten(json.dumps(args, ensure_ascii=False), 160)
    print(_s(f"  [T] {name}", C.CYAN) + _s(" → ", C.DIM) + _s(args_str, C.GRAY))
    
    if result:
        out = compress_console(result, 1400 if compact else 4000)
        lines = out.splitlines()
        limit = 50 if compact else 200
        for line in lines[:limit]:
            print(_s("     │ ", C.DIM) + line)
        if len(lines) > limit:
            print(_s("     │ ...", C.DIM))

# ==============================================================================
# Verification
# ==============================================================================

def _quote_arg(arg: str) -> str:
    """Quote shell argument if needed."""
    if not arg:
        return '""'
    if any(c in arg for c in ' \t"()[]{}'):
        return '"' + arg.replace('"', '\\"') + '"'
    return arg

def run_py_compile(files: List[str]) -> Tuple[str, str]:
    """Run py_compile on changed Python files."""
    if not files:
        return "", ""
    
    unique = list(dict.fromkeys(_norm_path(f) for f in files if Path(f).exists()))
    if not unique:
        return "", ""
    
    cmd = f'{_quote_arg(sys.executable)} -m py_compile ' + ' '.join(_quote_arg(f) for f in unique)
    res = tools.execute_pwsh(cmd, timeout=30)
    
    rc = res.get("returncode", -1)
    if rc == 0:
        return f"py_compile OK ({len(unique)} file(s))", ""
    
    detail = (res.get("stderr") or res.get("stdout") or "").strip()[:2500]
    first_line = detail.splitlines()[0] if detail else ""
    return f"py_compile FAILED: {first_line}", detail

# ==============================================================================
# Prompt Loading
# ==============================================================================

@lru_cache(maxsize=8)
def load_prompt(name: str, fallback: str) -> str:
    """Load agent prompt from file (cached)."""
    try:
        text = (AGENTS_DIR / name).read_text(encoding="utf-8").strip()
        return text if text else fallback
    except Exception:
        return fallback

DEFAULT_EXECUTOR = """You are an autonomous coding agent.
Rules:
- Inspect before editing (listDirectory, fileSearch, grepSearch, readCode).
- Make small, reversible changes. Prefer strReplace for focused edits.
- Verify changes work (executePwsh, compile checks).
- Call finish only when verified complete.
"""

DEFAULT_REQUIREMENTS = "You are a requirements analyst. Write clear requirements in markdown."
DEFAULT_DESIGN = "You are a software architect. Produce a design doc in markdown."
DEFAULT_TASKS = "You are a tech lead. Produce an implementation task list in markdown."

# ==============================================================================
# Command Handlers
# ==============================================================================

COMMANDS = {}

def cmd(name: str, *aliases: str):
    """Decorator to register command handlers."""
    def decorator(fn):
        COMMANDS[name] = fn
        for alias in aliases:
            COMMANDS[alias] = fn
        return fn
    return decorator

@cmd("help", "?")
def cmd_help(state: State, executor: Agent, args: str) -> bool:
    print()
    print(_s("  Commands:", C.BOLD))
    cmds = [
        ("status", "Show session status"),
        ("plan [description]", "Generate requirements/design/tasks"),
        ("tasks", "List all tasks"),
        ("task do <n>", "Start working on task n"),
        ("task done <n>", "Mark task n as complete"),
        ("task next", "Start next incomplete task"),
        ("auto on|off", "Toggle autonomous mode"),
        ("auto cap N", "Set auto step limit"),
        ("temp <0.0-2.0>", "Set temperature"),
        ("model [name]", "Show/switch model"),
        ("models [filter]", "List OpenRouter models"),
        ("compact on|off", "Toggle compact output"),
        ("clear", "Clear conversation history"),
        ("pin/unpin/pins", "Manage pinned files"),
        ("verify off|py_compile|cmd", "Set verification"),
        ("index", "Rebuild retrieval index"),
        ("help", "Show this help"),
        ("quit", "Exit"),
    ]
    for c, desc in cmds:
        print(_s(f"    {c:<24}", C.YELLOW) + _s(f"─ {desc}", C.DIM))
    print()
    print(_s("  Shortcuts: tl=tasks, td=task do, tc=task done, tn=task next", C.DIM))
    print(_s("  Multiline: Start with <<< (end >>>) or \"\"\"", C.DIM))
    print()
    return True

@cmd("status")
def cmd_status(state: State, executor: Agent, args: str) -> bool:
    usage = executor.get_token_usage()
    cache = executor.get_cache_stats()
    print()
    print(_s("  Session Status", C.BOLD))
    print(_s("  " + "─" * 14, C.DIM))
    print(f"  Model: {_s(executor.model, C.CYAN)} ({executor.max_context:,} ctx)")
    print(f"  Temp: {executor.temperature} | Auto: {_s(str(state.auto_mode), C.GREEN if state.auto_mode else C.GRAY)} ({state.auto_steps}/{state.auto_cap})")
    print(f"  Verify: {state.verify_mode}" + (f" ({state.verify_cmd})" if state.verify_cmd else ""))
    print(f"  Tokens: {usage['used']:,} / {usage['max']:,} ({usage['percent']}%)")
    # Cache stats
    if cache["requests"] > 0:
        hit_rate = cache["cache_hit_rate"]
        cache_color = C.GREEN if hit_rate > 50 else C.YELLOW if hit_rate > 0 else C.GRAY
        cached = cache["cached_tokens"]
        total = cache["total_prompt_tokens"]
        print(f"  Cache: {_s(f'{hit_rate}%', cache_color)} hit rate ({cached:,}/{total:,} tokens)")
        if cache["total_cost"] > 0:
            print(f"  Cost: ${cache['total_cost']:.4f} ({cache['requests']} requests)")
    if state.pinned:
        print(f"  Pinned: {len(state.pinned)} file(s)")
    if state.task:
        print(f"  Task: {_shorten(state.task, 60)}")
    if state.recent_writes:
        print(f"  Writes: {', '.join(Path(p).name for p in state.recent_writes[-5:])}")
    print()
    return True

@cmd("quit", "exit", "q")
def cmd_quit(state: State, executor: Agent, args: str) -> bool:
    status("Goodbye!", "info")
    return False  # Signal to exit

@cmd("clear")
def cmd_clear(state: State, executor: Agent, args: str) -> bool:
    executor.clear_history(keep_system=True, keep_last=0)
    state.reset_task()
    status("History cleared", "success")
    return True

@cmd("index")
def cmd_index(state: State, executor: Agent, args: str) -> bool:
    status("Building index...", "info")
    try:
        executor.indexer.build(".")
        status("Index rebuilt", "success")
    except Exception as e:
        status(f"Index failed: {e}", "error")
    return True

@cmd("auto")
def cmd_auto(state: State, executor: Agent, args: str) -> bool:
    if args.startswith("cap "):
        try:
            n = int(args[4:].strip())
            state.auto_cap = max(1, min(500, n))
            state.auto_steps = 0
            status(f"Auto cap set to {state.auto_cap}", "context")
        except ValueError:
            status("Usage: auto cap <number>", "warning")
    elif args in {"on", "off"}:
        state.auto_mode = args == "on"
        state.auto_steps = 0
        status(f"Auto mode {'enabled' if state.auto_mode else 'disabled'}", "context")
    else:
        status("Usage: auto on|off|cap N", "warning")
    return True

@cmd("compact")
def cmd_compact(state: State, executor: Agent, args: str) -> bool:
    if args in {"on", "off"}:
        state.compact = args == "on"
        status(f"Compact {'enabled' if state.compact else 'disabled'}", "context")
    else:
        status("Usage: compact on|off", "warning")
    return True

@cmd("temp", "temperature")
def cmd_temp(state: State, executor: Agent, args: str) -> bool:
    if not args:
        status(f"Temperature: {executor.temperature} (0=focused, 1=creative)", "info")
        return True
    try:
        t = float(args)
        if 0.0 <= t <= 2.0:
            executor.temperature = t
            status(f"Temperature set to {t}", "success")
        else:
            status("Temperature must be between 0.0 and 2.0", "warning")
    except ValueError:
        status("Usage: temp <0.0-2.0>", "warning")
    return True

@cmd("pin")
def cmd_pin(state: State, executor: Agent, args: str) -> bool:
    path = args.strip().strip('"\'')
    if not path:
        status("Usage: pin <path>", "warning")
        return True
    p = _norm_path(path)
    if not Path(p).exists():
        status(f"Not found: {path}", "error")
    elif p not in state.pinned:
        state.pinned.append(p)
        status(f"Pinned: {Path(p).name}", "success")
    else:
        status("Already pinned", "info")
    return True

@cmd("unpin")
def cmd_unpin(state: State, executor: Agent, args: str) -> bool:
    p = _norm_path(args.strip().strip('"\''))
    if p in state.pinned:
        state.pinned.remove(p)
        status(f"Unpinned: {Path(p).name}", "success")
    else:
        status("Not pinned", "warning")
    return True

@cmd("pins")
def cmd_pins(state: State, executor: Agent, args: str) -> bool:
    print()
    if not state.pinned:
        status("No pinned files", "info")
    else:
        print(_s("  Pinned files:", C.BOLD))
        for p in state.pinned:
            print(_s("   - ", C.DIM) + p)
    print()
    return True

@cmd("verify")
def cmd_verify(state: State, executor: Agent, args: str) -> bool:
    if args == "off":
        state.verify_mode = "off"
        state.verify_cmd = None
        status("Verification disabled", "context")
    elif args == "py_compile":
        state.verify_mode = "py_compile"
        state.verify_cmd = None
        status("Verification: py_compile", "context")
    elif args.startswith("cmd "):
        state.verify_mode = "command"
        state.verify_cmd = args[4:].strip()
        status(f"Verification: {state.verify_cmd}", "context")
    else:
        status("Usage: verify off|py_compile|cmd <command>", "warning")
    return True

@cmd("models")
def cmd_models(state: State, executor: Agent, args: str) -> bool:
    status("Fetching models...", "info")
    models = fetch_models()
    display_models(models, args.strip())
    return True

@cmd("model")
def cmd_model(state: State, executor: Agent, args: str) -> bool:
    if not args:
        print()
        print(_s(f"  Model: {executor.model}", C.CYAN))
        print(_s(f"  Context: {executor.max_context:,} tokens", C.DIM))
        print()
        return True
    
    new_model = args.strip()
    if not model_exists(new_model):
        status(f"Model '{new_model}' not found. Use 'models' to list.", "error")
        return True
    
    old = executor.model
    executor.model = new_model
    executor.max_context = get_context_limit(new_model)
    status(f"Switched: {old} → {new_model}", "success")
    status(f"Context: {executor.max_context:,} tokens", "info")
    return True

# ==============================================================================
# Task Management
# ==============================================================================

TASKS_FILE = Path(SUPERCODER_DIR) / "tasks.md"

def _parse_tasks(content: str) -> List[Dict[str, Any]]:
    """Parse tasks from markdown content. Supports - [ ] and - [x] format."""
    tasks = []
    lines = content.splitlines()
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match task patterns: - [ ] task or - [x] task or * [ ] task
        if stripped.startswith(("- [ ]", "- [x]", "- [X]", "* [ ]", "* [x]", "* [X]")):
            done = "[x]" in stripped.lower()
            # Extract task text after the checkbox
            text = stripped[6:].strip()
            tasks.append({
                "index": len(tasks) + 1,
                "line": i,
                "done": done,
                "text": text,
                "raw": line
            })
    return tasks

def _update_task_status(content: str, line_num: int, done: bool) -> str:
    """Update a task's checkbox status."""
    lines = content.splitlines()
    if 0 <= line_num < len(lines):
        line = lines[line_num]
        if done:
            line = line.replace("[ ]", "[x]")
        else:
            line = line.replace("[x]", "[ ]").replace("[X]", "[ ]")
        lines[line_num] = line
    return "\n".join(lines)

@cmd("tasks", "task list", "tl")
def cmd_tasks(state: State, executor: Agent, args: str) -> bool:
    """List all tasks from tasks.md"""
    if not TASKS_FILE.exists():
        status(f"No tasks file found. Run 'plan' first or create {TASKS_FILE}", "warning")
        return True
    
    content = TASKS_FILE.read_text(encoding="utf-8")
    tasks = _parse_tasks(content)
    
    if not tasks:
        status("No tasks found in tasks.md", "warning")
        return True
    
    print()
    print(_s("  Tasks:", C.BOLD))
    print(_s("  " + "─" * 50, C.DIM))
    
    done_count = sum(1 for t in tasks if t["done"])
    
    for t in tasks:
        checkbox = _s("[✓]", C.GREEN) if t["done"] else _s("[ ]", C.GRAY)
        num = _s(f"{t['index']:2}.", C.DIM)
        text = _s(t["text"], C.GRAY if t["done"] else C.RST)
        print(f"  {num} {checkbox} {text}")
    
    print()
    print(_s(f"  Progress: {done_count}/{len(tasks)} complete", C.CYAN))
    print()
    return True

@cmd("task do", "td")
def cmd_task_do(state: State, executor: Agent, args: str):
    """Execute a specific task by number."""
    if not args:
        status("Usage: task do <number>", "warning")
        return True
    
    if not TASKS_FILE.exists():
        status("No tasks file found", "error")
        return True
    
    try:
        task_num = int(args.strip())
    except ValueError:
        status("Task number must be an integer", "error")
        return True
    
    content = TASKS_FILE.read_text(encoding="utf-8")
    tasks = _parse_tasks(content)
    
    if task_num < 1 or task_num > len(tasks):
        status(f"Task {task_num} not found. Use 'tasks' to list.", "error")
        return True
    
    task = tasks[task_num - 1]
    
    if task["done"]:
        status(f"Task {task_num} is already done", "warning")
        return True
    
    # Set this task as the current goal and return prompt to execute
    state.task = f"Task {task_num}: {task['text']}"
    status(f"Executing task {task_num}: {task['text']}", "context")
    
    # Return the task as a prompt to execute
    return f"Execute this task: {task['text']}. When complete, call finish."

@cmd("task done", "task check", "tc")
def cmd_task_done(state: State, executor: Agent, args: str) -> bool:
    """Mark a task as done."""
    if not args:
        status("Usage: task done <number>", "warning")
        return True
    
    if not TASKS_FILE.exists():
        status("No tasks file found", "error")
        return True
    
    try:
        task_num = int(args.strip())
    except ValueError:
        status("Task number must be an integer", "error")
        return True
    
    content = TASKS_FILE.read_text(encoding="utf-8")
    tasks = _parse_tasks(content)
    
    if task_num < 1 or task_num > len(tasks):
        status(f"Task {task_num} not found", "error")
        return True
    
    task = tasks[task_num - 1]
    
    if task["done"]:
        status(f"Task {task_num} already marked done", "info")
        return True
    
    # Update the file
    new_content = _update_task_status(content, task["line"], done=True)
    TASKS_FILE.write_text(new_content, encoding="utf-8")
    
    status(f"✓ Task {task_num} marked done: {task['text']}", "success")
    return True

@cmd("task undo", "task uncheck", "tu")
def cmd_task_undo(state: State, executor: Agent, args: str) -> bool:
    """Mark a task as not done."""
    if not args:
        status("Usage: task undo <number>", "warning")
        return True
    
    if not TASKS_FILE.exists():
        status("No tasks file found", "error")
        return True
    
    try:
        task_num = int(args.strip())
    except ValueError:
        status("Task number must be an integer", "error")
        return True
    
    content = TASKS_FILE.read_text(encoding="utf-8")
    tasks = _parse_tasks(content)
    
    if task_num < 1 or task_num > len(tasks):
        status(f"Task {task_num} not found", "error")
        return True
    
    task = tasks[task_num - 1]
    
    if not task["done"]:
        status(f"Task {task_num} is not marked done", "info")
        return True
    
    # Update the file
    new_content = _update_task_status(content, task["line"], done=False)
    TASKS_FILE.write_text(new_content, encoding="utf-8")
    
    status(f"Task {task_num} unmarked: {task['text']}", "success")
    return True

@cmd("task next", "tn")
def cmd_task_next(state: State, executor: Agent, args: str):
    """Start the next incomplete task."""
    if not TASKS_FILE.exists():
        status("No tasks file found. Run 'plan' to create one.", "warning")
        return True
    
    content = TASKS_FILE.read_text(encoding="utf-8")
    tasks = _parse_tasks(content)
    
    # Find first incomplete task
    for task in tasks:
        if not task["done"]:
            state.task = f"Task {task['index']}: {task['text']}"
            status(f"Executing task {task['index']}: {task['text']}", "context")
            # Return the task as a prompt to execute
            return f"Execute this task: {task['text']}. When complete, call finish."
    
    status("All tasks complete! 🎉", "success")
    return True

@cmd("plan")
def cmd_plan(state: State, executor: Agent, args: str) -> bool:
    """Generate requirements, design, and tasks for a project."""
    os.makedirs(SUPERCODER_DIR, exist_ok=True)
    
    if not args:
        print()
        status("Describe your project (or use: plan <description>)", "info")
        args = get_input("  Project: ").strip()
        if not args or args.lower() in {"quit", "exit", "cancel"}:
            status("Canceled", "warning")
            return True
    
    # Requirements
    status("Generating requirements...", "context")
    req_agent = Agent(initial_prompt=load_prompt("Requirements.md", DEFAULT_REQUIREMENTS))
    requirements = req_agent.Prompt(args, streaming=True)
    Path(SUPERCODER_DIR, "requirements.md").write_text(requirements, encoding="utf-8")
    status("Saved requirements.md", "success")
    divider()
    
    # Design
    status("Generating design...", "context")
    design_agent = Agent(initial_prompt=load_prompt("Design.md", DEFAULT_DESIGN))
    design_agent.add_context(str(Path(SUPERCODER_DIR, "requirements.md")))
    design = design_agent.Prompt("Create a design doc based on requirements.md", streaming=True)
    Path(SUPERCODER_DIR, "design.md").write_text(design, encoding="utf-8")
    status("Saved design.md", "success")
    divider()
    
    # Tasks
    status("Generating tasks...", "context")
    task_agent = Agent(initial_prompt=load_prompt("Tasks.md", DEFAULT_TASKS))
    task_agent.add_context([str(Path(SUPERCODER_DIR, "requirements.md")), str(Path(SUPERCODER_DIR, "design.md"))])
    tasks_content = task_agent.Prompt("Create implementation tasks based on requirements and design. Use markdown checkboxes: - [ ] task", streaming=True)
    Path(SUPERCODER_DIR, "tasks.md").write_text(tasks_content, encoding="utf-8")
    status("Saved tasks.md", "success")
    
    divider()
    status("Planning complete! Use 'tasks' to see task list, 'task next' to start.", "success")
    print()
    return True

# Legacy compatibility
@cmd("context add")
def cmd_context_add(state: State, executor: Agent, args: str) -> bool:
    cwd = Path(".")
    added = []
    for p in cwd.iterdir():
        if p.is_file() and p.suffix.lower() in ALL_EXTENSIONS:
            try:
                if p.stat().st_size <= MAX_FILE_SIZE:
                    np = _norm_path(str(p))
                    if np not in state.pinned:
                        state.pinned.append(np)
                        added.append(np)
            except Exception:
                pass
    status(f"Pinned {len(added)} file(s)", "success" if added else "warning")
    return True

@cmd("context clear", "context reset")
def cmd_context_clear(state: State, executor: Agent, args: str) -> bool:
    state.pinned.clear()
    status("Cleared pinned files", "success")
    return True

# ==============================================================================
# Main Execute Loop
# ==============================================================================

def run() -> None:
    """Main execution loop."""
    # Enable ANSI on Windows
    if sys.platform == "win32":
        os.system("")
    
    prompt = load_prompt("Executor.md", DEFAULT_EXECUTOR)
    
    header()
    status(f"Working directory: {os.getcwd()}", "info")
    status("Type 'help' for commands, 'plan' to start a new project", "info")
    divider()
    
    state = State()
    executor = Agent(initial_prompt=prompt)
    
    # Build index if missing
    idx_path = Path(SUPERCODER_DIR) / "index.json"
    if not idx_path.exists():
        status("Building retrieval index...", "info")
        try:
            executor.indexer.build(".")
            status("Index built", "success")
        except Exception as e:
            status(f"Index failed: {e}", "error")
    
    # Show tasks if they exist
    if TASKS_FILE.exists():
        content = TASKS_FILE.read_text(encoding="utf-8")
        tasks = _parse_tasks(content)
        if tasks:
            done = sum(1 for t in tasks if t["done"])
            status(f"Tasks: {done}/{len(tasks)} complete. Use 'tasks' to view, 'task next' to continue.", "info")
    
    user_input = get_input()
    
    while True:
        raw = user_input.strip()
        if not raw:
            user_input = get_input()
            continue
        
        # Parse command
        low = raw.lower()
        
        # Check for exact command match first
        handler = None
        cmd_args = ""
        
        for cmd_name in sorted(COMMANDS.keys(), key=len, reverse=True):
            if low == cmd_name or low.startswith(cmd_name + " "):
                handler = COMMANDS[cmd_name]
                cmd_args = raw[len(cmd_name):].strip()
                break
        
        if handler:
            result = handler(state, executor, cmd_args)
            if result is False:
                break  # quit command
            elif isinstance(result, str):
                # Handler returned a prompt to execute - fall through to execution
                raw = result
            else:
                # Normal command, get next input
                user_input = get_input()
                continue
        
        # Normal prompt handling (or task execution from above)
        if not state.task:
            state.task = raw
        
        # Token guard
        usage = executor.get_token_usage()
        if usage["percent"] >= 90:
            status("Context nearly full, trimming history...", "warning")
            executor.clear_history(keep_system=True, keep_last=8)
        
        # Add pinned context
        if state.pinned:
            executor.add_context(state.pinned[:MAX_PINNED_FILES])
        
        # Build model input
        blurb = state_blurb(state)
        model_input = f"{blurb}\n\nUser: {raw}" if blurb else raw
        
        # Call model
        try:
            content, tool_calls = executor.PromptWithTools(model_input, tools=None, streaming=False)
        except Exception as e:
            status(f"Model error: {e}", "error")
            user_input = get_input()
            continue
        
        # Display response
        if content:
            print()
            limit = 80 if state.compact else 200
            for line in content.splitlines()[:limit]:
                print(_s("  │ ", C.GREEN) + line)
            if len(content.splitlines()) > limit:
                print(_s("  │ ...", C.DIM))
            print()
        
        # Execute tools
        should_finish = False
        finish_summary = ""
        wrote_paths: List[str] = []
        changed_py: List[str] = []
        
        for tc in tool_calls or []:
            name = tc.get("name")
            args = tc.get("args") or {}
            
            # Track file operations
            if name in {"readFile", "readCode"}:
                if p := args.get("path"):
                    _push_unique(state.recent_reads, _norm_path(p))
            
            if name in {"fsWrite", "fsAppend", "strReplace", "deleteFile"}:
                if p := args.get("path"):
                    pn = _norm_path(p)
                    _push_unique(state.recent_writes, pn)
                    wrote_paths.append(pn)
                    if pn.lower().endswith(".py"):
                        changed_py.append(pn)
            
            # Handle finish
            if name == "finish":
                should_finish = True
                finish_summary = args.get("summary", "")
                print_tool(name, args, finish_summary, state.compact)
                continue
            
            # Execute tool
            try:
                result = execute_tool(tc)
                print_tool(name, args, str(result), state.compact)
                executor.AddToolResult(tc["id"], name, compress_model(name, result))
            except Exception as e:
                err = f"Error: {e}"
                status(f"Tool error ({name}): {err}", "error")
                executor.AddToolResult(tc["id"], name, err)
        
        # Post-write verification
        state.verify_summary = ""
        state.verify_detail = ""
        
        if wrote_paths and not should_finish and state.verify_mode != "off":
            if state.verify_mode == "py_compile" and changed_py:
                summary, detail = run_py_compile(changed_py)
                if summary:
                    state.verify_summary = summary
                    state.verify_detail = detail
                    status(summary, "error" if "FAILED" in summary else "success")
            elif state.verify_mode == "command" and state.verify_cmd:
                res = tools.execute_pwsh(state.verify_cmd, timeout=120)
                state.verify_summary = f"verify rc={res.get('returncode')}"
                state.verify_detail = compress_console(json.dumps(res), 2500)
                status(state.verify_summary, "info")
        
        # Handle completion
        if should_finish:
            divider()
            status("Task completed!", "success")
            if finish_summary:
                for line in finish_summary.splitlines()[:12]:
                    print(_s("  │ ", C.GREEN) + line)
            print()
            divider()
            state.reset_task()
            user_input = get_input("Next task: ")
            continue
        
        # Auto continuation
        if state.auto_mode:
            if state.auto_steps >= state.auto_cap:
                status("Auto cap reached", "warning")
                state.auto_steps = 0
                user_input = get_input()
            else:
                state.auto_steps += 1
                user_input = "Continue. Use tools. Call finish when verified complete."
        else:
            user_input = get_input()

# ==============================================================================
# Entry Point
# ==============================================================================

def main() -> None:
    """Main entry point."""
    run()


if __name__ == "__main__":
    main()
