
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
from Agentic import Agent, execute_tool, MODEL_LIMITS, TokenManager, G4F_FREE_MODELS, G4F_AVAILABLE

# Syntax highlighting
try:
    from pygments import highlight
    from pygments.lexers import get_lexer_for_filename, get_lexer_by_name, TextLexer
    from pygments.formatters import Terminal256Formatter
    from pygments.util import ClassNotFound
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False

# ==============================================================================
# Constants
# ==============================================================================

WORKING_DIR = Path(__file__).parent
AGENTS_DIR = WORKING_DIR / "Agents"
SUPERCODER_DIR = ".supercoder"
TASKS_FILE = Path(SUPERCODER_DIR) / "tasks.md"

CODE_EXTENSIONS: Set[str] = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".h"}
DOC_EXTENSIONS: Set[str] = {".md", ".txt", ".json", ".yml", ".yaml", ".toml"}
ALL_EXTENSIONS: Set[str] = CODE_EXTENSIONS | DOC_EXTENSIONS

MAX_FILE_SIZE = 200_000
MAX_PINNED_FILES = 8
MAX_RECENT_ITEMS = 10

# ==============================================================================
# Shell Compatibility (Windows PowerShell patch)
# ==============================================================================

@lru_cache(maxsize=1)
def _detect_shell() -> Tuple[Optional[str], str]:
    if os.name != "nt":
        return None, "posix shell"
    if shutil.which("pwsh"):
        return "pwsh", "PowerShell Core"
    if shutil.which("powershell"):
        return "powershell", "Windows PowerShell"
    return None, "cmd"

_PS_EXE, _PS_LABEL = _detect_shell()
_CMD_SEP_RE = re.compile(r'\s*(?:&&|\|\|)\s*|\s&\s')

def _sanitize_cmd(cmd: str) -> str:
    return _CMD_SEP_RE.sub('; ', str(cmd).strip())

def _execute_pwsh_patched(command: str, timeout: int = 60) -> Dict[str, Any]:
    if os.name == "nt" and _PS_EXE:
        args = [_PS_EXE, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _sanitize_cmd(command)]
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd())
            return {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
        except subprocess.TimeoutExpired as e:
            return {"stdout": getattr(e, 'stdout', '') or '', "stderr": f"Timed out after {timeout}s", "returncode": -1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "returncode": 1}
    orig = getattr(tools, "_orig_execute_pwsh", None)
    return orig(command, timeout=timeout) if callable(orig) else {"stdout": "", "stderr": "not available", "returncode": 1}

def _control_pwsh_patched(action: str, command: str = None, process_id: int = None, path: str = None) -> Dict[str, Any]:
    if os.name == "nt" and _PS_EXE:
        bg = getattr(tools, "_background_processes", {})
        try:
            if action == "start" and command:
                args = [_PS_EXE, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _sanitize_cmd(command)]
                proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=path or os.getcwd())
                pid = max(bg.keys(), default=0) + 1
                bg[pid] = proc
                tools._background_processes = bg
                return {"processId": pid, "status": "started"}
            if action == "stop" and process_id in bg:
                bg[process_id].terminate()
                del bg[process_id]
                return {"success": True}
        except Exception as e:
            return {"error": str(e)}
    orig = getattr(tools, "_orig_control_pwsh", None)
    return orig(action, command=command, process_id=process_id, path=path) if callable(orig) else {"error": "not available"}

# Apply patches
tools._orig_execute_pwsh = getattr(tools, "execute_pwsh", None)
tools._orig_control_pwsh = getattr(tools, "control_pwsh_process", None)
tools.execute_pwsh = _execute_pwsh_patched
tools.control_pwsh_process = _control_pwsh_patched


# ==============================================================================
# ANSI Colors & Output (Your UI)
# ==============================================================================

class C:
    RST, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
    RED = "\033[31m"
    BRED = "\033[91m"
    PURPLE = "\033[35m"
    BPURPLE = "\033[95m"
    YELLOW = "\033[33m"
    BYELLOW = "\033[93m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    GREEN, BLUE, MAGENTA, CYAN = BRED, PURPLE, PURPLE, BPURPLE
    BGREEN, BBLUE, BMAGENTA, BCYAN = BRED, BPURPLE, BPURPLE, BRED

def _s(text: str, color: str) -> str:
    return f"{color}{text}{C.RST}"

_STATUS = {"info": (C.PURPLE, "[i]"), "success": (C.BRED, "[✓]"), "warning": (C.BYELLOW, "[!]"), "error": (C.RED, "[x]"), "context": (C.BPURPLE, "[~]")}

def status(msg: str, level: str = "info") -> None:
    c, p = _STATUS.get(level, (C.BLUE, "[i]"))
    print(_s(f"  {p} {msg}", c))

def header() -> None:
    from colorama import Fore
    print()
    Color1 = Fore.MAGENTA
    Color2 = Fore.RED
    Banner = f"""
    {Color2}  ██████  █    ██  ██▓███  ▓█████  ██▀███   ▄████▄   {Color1}▒{Color2}█████  ▓█████▄ ▓█████  ██▀███  
    {Color1}▒{Color2}██    {Color1}▒  {Color2}██  ▓██{Color1}▒{Color2}▓██{Color1}░  {Color2}██{Color1}▒{Color2}▓█   ▀ ▓██ {Color1}▒ {Color2}██{Color1}▒▒{Color2}██▀ ▀█  {Color1}▒{Color2}██{Color1}▒  {Color2}██{Color1}▒▒{Color2}██▀ ██▌▓█   ▀ ▓██ {Color1}▒ {Color2}██{Color1}▒
    {Color1}░ {Color2}▓██▄   ▓██  {Color1}▒{Color2}██{Color1}░{Color2}▓██{Color1}░ {Color2}██▓{Color1}▒▒{Color2}███   ▓██ {Color1}░{Color2}▄█ {Color1}▒▒{Color2}▓█    ▄ {Color1}▒{Color2}██{Color1}░  {Color2}██{Color1}▒░{Color2}██   {Color2}█▌{Color1}▒{Color2}███   ▓██ {Color1}░{Color2}▄█ {Color1}▒
    {Color1}  ▒   {Color2}██{Color1}▒{Color2}▓▓█  {Color1}░{Color2}██{Color1}░▒{Color2}██▄█▓{Color1}▒ ▒▒{Color2}▓█  ▄ {Color1}▒{Color2}██▀▀█▄  {Color1}▒{Color2}▓▓▄ ▄██{Color1}▒▒{Color2}██   ██{Color1}░░{Color2}▓█▄   ▌{Color1}▒{Color2}▓█  ▄ {Color1}▒{Color2}██▀▀█▄  
    {Color1}▒{Color2}██████{Color1}▒▒▒▒{Color2}█████▓{Color1} ▒{Color2}██{Color1}▒ ░  ░░▒{Color2}████{Color1}▒░{Color2}██▓{Color1} ▒{Color2}██{Color1}▒▒ {Color2}▓███▀{Color1} ░░ {Color2}████▓{Color1}▒░░▒{Color2}████▓{Color1} ░▒{Color2}████{Color1}▒░{Color2}██▓{Color1} ▒{Color2}██{Color1}▒
    {Color1}▒ ▒{Color2}▓{Color1}▒ ▒ ░░▒{Color2}▓{Color1}▒ ▒ ▒ ▒{Color2}▓{Color1}▒░ ░  ░░░ ▒░ ░░ ▒{Color2}▓ {Color1}░▒{Color2}▓{Color1}░░ ░▒ ▒  ░░ ▒░▒░▒░  ▒▒{Color2}▓{Color1}  ▒ ░░ ▒░ ░░ ▒{Color2}▓ {Color1}░▒{Color2}▓{Color1}░
    {Color1}░ ░▒  ░ ░░░▒░ ░ ░ ░▒ ░      ░ ░  ░  ░▒ ░ ▒░  ░  ▒     ░ ▒ ▒░  ░ ▒  ▒  ░ ░  ░  ░▒ ░ ▒░
    {Color1}░  ░  ░   ░░░ ░ ░ ░░          ░     ░░   ░ ░        ░ ░ ░ ▒   ░ ░  ░    ░     ░░   ░
    {Color1}      ░     ░                 ░  ░   ░     ░ ░          ░ ░     ░       ░  ░   ░
    {Color1}                                           ░                  ░                      
    {Fore.RESET}
    """
    print(Banner)
    print()

def divider() -> None:
    print(f"  {C.PURPLE}{'─' * 57}{C.RST}")
    print()


# ==============================================================================
# Input & Model Management
# ==============================================================================

def _build_prompt() -> str:
    import getpass
    user = getpass.getuser()
    cwd = Path.cwd().name or "~"
    line1 = f"{C.BPURPLE}┌──({C.BRED}{user}{C.BPURPLE}@{C.BRED}supercoder{C.BPURPLE})-[{C.BOLD}{C.WHITE}{cwd}{C.RST}{C.BPURPLE}]{C.RST}"
    line2 = f"{C.BPURPLE}└─{C.BRED}${C.RST} "
    return f"{line1}\n{line2}"

def get_input(prompt: str = None) -> str:
    try:
        if prompt is None:
            prompt = _build_prompt()
            print(prompt, end="")
            line = input()
        else:
            line = input(_s(prompt, C.YELLOW))
        stripped = line.strip()
        if stripped == "<<<" or stripped.startswith('"""'):
            end = ">>>" if stripped == "<<<" else '"""'
            print(f"  {C.GRAY}╭─ multiline mode (end with {end}){C.RST}")
            lines = [stripped[3:]] if stripped.startswith('"""') and len(stripped) > 3 else []
            while True:
                ln = input(f"  {C.BPURPLE}│{C.RST} ")
                if ln.strip() == end or (end == '"""' and ln.strip().endswith('"""')):
                    if end == '"""' and ln.strip().endswith('"""') and len(ln.strip()) > 3:
                        lines.append(ln.strip()[:-3])
                    print(f"  {C.GRAY}╰─────────────────────────────{C.RST}")
                    break
                lines.append(ln)
            return "\n".join(lines)
        return line
    except EOFError:
        print()
        return "quit"

_model_cache: Dict[str, Dict[str, Any]] = {}
_cache_loaded: bool = False

def fetch_models() -> List[Dict[str, Any]]:
    global _model_cache, _cache_loaded
    import requests
    try:
        TokenManager.load_tokens()
        resp = requests.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {TokenManager.get_token()}"}, timeout=15)
        resp.raise_for_status()
        models = resp.json().get("data", [])
        _model_cache = {m["id"]: m for m in models if m.get("id")}
        _cache_loaded = True
        return models
    except Exception as e:
        status(f"Failed to fetch models: {e}", "error")
        return []

def get_context_limit(model_id: str) -> int:
    global _cache_loaded
    if model_id in _model_cache:
        return _model_cache[model_id].get("context_length", MODEL_LIMITS["default"])
    if model_id in MODEL_LIMITS:
        return MODEL_LIMITS[model_id]
    if not _cache_loaded:
        fetch_models()
    return _model_cache.get(model_id, {}).get("context_length", MODEL_LIMITS["default"])

def model_exists(model_id: str) -> bool:
    global _cache_loaded
    if model_id in _model_cache:
        return True
    if not _cache_loaded:
        fetch_models()
    return model_id in _model_cache

def display_models(models: List[Dict[str, Any]], filter_text: str = "") -> Tuple[List, List]:
    """Separate models into free and paid, return both lists."""
    if filter_text:
        fl = filter_text.lower()
        models = [m for m in models if fl in m.get("id", "").lower() or fl in m.get("name", "").lower()]
    
    free_models = []
    paid_models = []
    
    for m in models:
        pricing = m.get("pricing", {})
        prompt_price = float(pricing.get("prompt", "1") or "1")
        completion_price = float(pricing.get("completion", "1") or "1")
        
        if prompt_price == 0 and completion_price == 0:
            free_models.append(m)
        else:
            paid_models.append(m)
    
    return sorted(free_models, key=lambda m: m.get("id", "")), sorted(paid_models, key=lambda m: m.get("id", ""))


# ==============================================================================
# Session State & Helpers
# ==============================================================================

@dataclass
class State:
    task: str = ""
    pinned: List[str] = field(default_factory=list)
    auto_mode: bool = True
    auto_cap: int = 50
    auto_steps: int = 0
    compact: bool = False
    verbose: bool = True
    verify_mode: str = "py_compile"
    verify_cmd: Optional[str] = None
    verify_summary: str = ""
    verify_detail: str = ""
    recent_reads: List[str] = field(default_factory=list)
    recent_writes: List[str] = field(default_factory=list)
    current_task_num: int = 0

    def reset_task(self) -> None:
        self.task = ""
        self.auto_steps = 0
        self.recent_reads.clear()
        self.recent_writes.clear()
        self.verify_summary = ""
        self.verify_detail = ""

def _push_unique(lst: List[str], item: str, cap: int = MAX_RECENT_ITEMS) -> None:
    if item and item in lst:
        lst.remove(item)
    if item:
        lst.append(item)
    while len(lst) > cap:
        lst.pop(0)

def _norm_path(p: str) -> str:
    try:
        return str(Path(p).resolve())
    except:
        return p

def _shorten(s: str, n: int = 280) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n-3] + "..."

def state_blurb(state: State) -> str:
    parts = []
    if state.task:
        parts.append(f"Goal: {state.task}")
    parts.append(f"Shell: {_PS_LABEL}. Use ';' as separator.")
    if state.recent_writes:
        parts.append(f"Recent writes: {', '.join(Path(p).name for p in state.recent_writes[-5:])}")
    if state.verify_summary:
        parts.append(f"Verify: {state.verify_summary}")
    return "\n".join(parts)

# ==============================================================================
# Output Compression
# ==============================================================================

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
_WHITESPACE_RE = re.compile(r'\s+')

def compress_console(text: str, max_len: int = 8000) -> str:
    if not text or len(text) <= max_len:
        return text
    text = _ANSI_RE.sub('', text)
    text = _WHITESPACE_RE.sub(' ', text)
    if len(text) <= max_len:
        return text
    half = max_len // 2 - 20
    return f"{text[:half]}\n... [{len(text) - max_len} chars truncated] ...\n{text[-half:]}"

def compress_model(text: str, max_len: int = 12000) -> str:
    if not text or len(text) <= max_len:
        return text
    half = max_len // 2 - 20
    return f"{text[:half]}\n... [{len(text) - max_len} chars truncated] ...\n{text[-half:]}"

def _to_str(val: Any, join_lists: bool = False) -> str:
    """Convert any value to string for display."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, list) and join_lists:
        # For content that should be a string but model passed as list, join it
        return "\n".join(str(item) for item in val)
    try:
        return json.dumps(val, indent=2, default=str)
    except:
        return str(val)

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
    except Exception:
        return code

def _print_highlighted_lines(content: str, filename: str, prefix: str = "", line_nums: bool = True, color_override: str = None) -> None:
    """Print content with syntax highlighting and optional line numbers."""
    if PYGMENTS_AVAILABLE and filename:
        highlighted = _syntax_highlight(content, filename)
        lines = highlighted.split('\n')
    else:
        lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if color_override:
            line = f"{color_override}{line}{C.RST}"
        if line_nums:
            print(f"  {C.PURPLE}│{C.RST} {prefix}{C.DIM}{i:4}{C.RST} {line}")
        else:
            print(f"  {C.PURPLE}│{C.RST} {prefix}{line}")

def print_tool(name: str, args: Dict[str, Any], result: str, compact: bool = True, verbose: bool = False) -> None:
    arg_str = ", ".join(f"{k}={repr(v)[:60]}" for k, v in args.items())
    print(f"\n  {C.BPURPLE}▸{C.RST} {C.BRED}{name}{C.RST}{C.GRAY}({arg_str[:100]}){C.RST}")
    
    # Convert result to string if needed
    result = _to_str(result)
    
    if verbose:
        # Full verbose output with nice formatting (rounded corners)
        print(f"  {C.PURPLE}╭{'─' * 70}{C.RST}")
        
        # Show full arguments for write operations
        if name in ("fsWrite", "fsAppend"):
            content = _to_str(args.get("text", args.get("content", "")), join_lists=True)
            path = args.get("path", "")
            print(f"  {C.PURPLE}│{C.RST} {C.BYELLOW}FILE:{C.RST} {path}")
            print(f"  {C.PURPLE}│{C.RST} {C.BYELLOW}CONTENT ({len(content)} chars):{C.RST}")
            print(f"  {C.PURPLE}├{'─' * 70}{C.RST}")
            _print_highlighted_lines(content, path)
            print(f"  {C.PURPLE}├{'─' * 70}{C.RST}")
        
        elif name == "strReplace":
            path = args.get("path", "")
            old = _to_str(args.get("oldStr", ""), join_lists=True)
            new = _to_str(args.get("newStr", ""), join_lists=True)
            print(f"  {C.PURPLE}│{C.RST} {C.BYELLOW}FILE:{C.RST} {path}")
            print(f"  {C.PURPLE}│{C.RST} {C.RED}OLD ({len(old)} chars):{C.RST}")
            print(f"  {C.PURPLE}├{'─' * 70}{C.RST}")
            _print_highlighted_lines(old, path, prefix=f"{C.RED}-{C.RST} ", line_nums=False)
            print(f"  {C.PURPLE}├{'─' * 70}{C.RST}")
            print(f"  {C.PURPLE}│{C.RST} {C.GREEN}NEW ({len(new)} chars):{C.RST}")
            print(f"  {C.PURPLE}├{'─' * 70}{C.RST}")
            _print_highlighted_lines(new, path, prefix=f"{C.GREEN}+{C.RST} ", line_nums=False)
            print(f"  {C.PURPLE}├{'─' * 70}{C.RST}")
        
        elif name in ("readFile", "readCode", "readMultipleFiles"):
            path = args.get("path", args.get("paths", [""])[0] if args.get("paths") else "")
            print(f"  {C.PURPLE}│{C.RST} {C.BYELLOW}CONTENT:{C.RST}")
            print(f"  {C.PURPLE}├{'─' * 70}{C.RST}")
            _print_highlighted_lines(result, path)
            print(f"  {C.PURPLE}├{'─' * 70}{C.RST}")
        
        else:
            # Generic verbose output
            if result:
                print(f"  {C.PURPLE}│{C.RST} {C.BYELLOW}RESULT:{C.RST}")
                for line in result.split('\n'):
                    print(f"  {C.PURPLE}│{C.RST} {line}")
        
        print(f"  {C.PURPLE}╰{'─' * 70}{C.RST}")
    
    elif not compact:
        # Non-compact but not verbose - show more but not everything
        if result:
            for line in result.split('\n')[:50]:
                print(f"    {C.GRAY}{line[:300]}{C.RST}")
            if len(result.split('\n')) > 50:
                print(f"    {C.GRAY}... ({len(result.split(chr(10))) - 50} more lines){C.RST}")
    
    else:
        # Compact mode - minimal output
        if result:
            display = compress_console(result, 2000)
            for line in display.split('\n')[:15]:
                print(f"    {C.GRAY}{line[:150]}{C.RST}")
            if len(display.split('\n')) > 15:
                print(f"    {C.GRAY}... ({len(display.split(chr(10))) - 15} more lines){C.RST}")
    sys.stdout.flush()

def _print_completion_box(summary: str, success: bool = True) -> None:
    """Print a nice completion box with the summary."""
    icon = "✓" if success else "✗"
    color = C.GREEN if success else C.RED
    border_color = C.BPURPLE
    
    # Word wrap the summary to fit in the box
    max_width = 66
    words = summary.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 <= max_width:
            current_line = f"{current_line} {word}".strip()
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    
    print()
    print(f"  {border_color}╭{'─' * 70}╮{C.RST}")
    print(f"  {border_color}│{C.RST}  {color}{icon} COMPLETE{C.RST}{' ' * 58}{border_color}│{C.RST}")
    print(f"  {border_color}├{'─' * 70}┤{C.RST}")
    for line in lines:
        padding = 68 - len(line)
        print(f"  {border_color}│{C.RST}  {line}{' ' * padding}{border_color}│{C.RST}")
    print(f"  {border_color}╰{'─' * 70}╯{C.RST}")
    print()
    sys.stdout.flush()

def build_continue_prompt(state: State, last_tools: List[str], had_content: bool) -> str:
    """Build a context-rich continue prompt based on what just happened."""
    parts = []
    
    # What was the original goal
    if state.task:
        parts.append(f"Original goal: {_shorten(state.task, 150)}")
    
    # What tools were just used
    if last_tools:
        parts.append(f"You just used: {', '.join(last_tools[-5:])}")
    
    # What files were recently modified
    if state.recent_writes:
        recent = [Path(p).name for p in state.recent_writes[-3:]]
        parts.append(f"Recently modified: {', '.join(recent)}")
    
    # Verification status
    if state.verify_summary and "error" in state.verify_summary.lower():
        parts.append(f"⚠️ Verification issue: {state.verify_summary}")
    
    # Build the prompt
    context = "\n".join(parts)
    
    if had_content and not last_tools:
        # Model talked but didn't use tools
        return f"""Context:
{context}

You explained something but didn't take action. Either:
1. Use tools to make progress on the task
2. Call finish() if the task is complete
3. Call interactWithUser() if you need clarification

What's your next action?"""
    else:
        # Normal continuation after tool use
        return f"""Context:
{context}

Continue working on the task. What's the next step? 
Remember: Call finish() with a summary when the task is complete."""


# ==============================================================================
# Verification Helpers
# ==============================================================================

def run_py_compile(path: str) -> Tuple[bool, str]:
    if not path.endswith('.py'):
        return True, ""
    try:
        result = subprocess.run([sys.executable, "-m", "py_compile", path], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True, ""
        return False, result.stderr or result.stdout
    except Exception as e:
        return False, str(e)

def _quote_arg(arg: str) -> str:
    if ' ' in arg or '"' in arg:
        return f'"{arg}"'
    return arg

# ==============================================================================
# Prompt Loading
# ==============================================================================

@lru_cache(maxsize=8)
def load_prompt(name: str) -> str:
    path = AGENTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding='utf-8')
    return ""

DEFAULT_EXECUTOR = load_prompt("Executor") or "You are a helpful coding assistant."

# ==============================================================================
# Task Management
# ==============================================================================

_TASK_RE = re.compile(r'^(\s*[-*]?\s*\[([xX ])\]\s*)(.+)$', re.MULTILINE)

def _parse_tasks() -> List[Tuple[int, bool, str]]:
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
    if not TASKS_FILE.exists():
        return False
    content = TASKS_FILE.read_text(encoding='utf-8')
    matches = list(_TASK_RE.finditer(content))
    if task_num < 1 or task_num > len(matches):
        return False
    match = matches[task_num - 1]
    new_mark = "[x]" if done else "[ ]"
    prefix = match.group(1)
    old_checkbox = "[x]" if match.group(2).lower() == 'x' else "[ ]"
    new_prefix = prefix.replace(old_checkbox, new_mark, 1)
    if old_checkbox not in prefix:
        new_prefix = prefix.replace(f"[{match.group(2)}]", new_mark, 1)
    new_line = new_prefix + match.group(3)
    new_content = content[:match.start()] + new_line + content[match.end():]
    TASKS_FILE.write_text(new_content, encoding='utf-8')
    return True

def _get_task_progress() -> Tuple[int, int]:
    tasks = _parse_tasks()
    if not tasks:
        return 0, 0
    done = sum(1 for _, d, _ in tasks if d)
    return done, len(tasks)


# ==============================================================================
# Command Registry
# ==============================================================================

_COMMANDS: Dict[str, Tuple[callable, str]] = {}
_SHORTCUTS: Dict[str, str] = {}

def cmd(name: str, help_text: str, shortcuts: List[str] = None):
    def decorator(func):
        _COMMANDS[name] = (func, help_text)
        if shortcuts:
            for s in shortcuts:
                _SHORTCUTS[s] = name
        return func
    return decorator

# ==============================================================================
# Command Handlers
# ==============================================================================

@cmd("help", "Show this help")
def cmd_help(state: State, agent: Agent, args: str) -> None:
    print()
    print(_s("  Commands:", C.BOLD))
    max_name = max(len(n) for n in _COMMANDS) + 2
    for name, (_, help_text) in sorted(_COMMANDS.items()):
        print(f"  {_s(name.ljust(max_name), C.CYAN)} ─ {help_text}")
    print()
    print(_s("  Shortcuts: ", C.DIM) + ", ".join(f"{s}={n}" for s, n in sorted(_SHORTCUTS.items())))
    print(_s("  Multiline: Start with <<< (end >>>) or \"\"\"", C.DIM))
    print()

@cmd("status", "Show session status")
def cmd_status(state: State, agent: Agent, args: str) -> None:
    usage = agent.get_token_usage()
    print()
    print(_s("  Session Status:", C.BOLD))
    print(f"  Model: {_s(agent.model, C.CYAN)}")
    print(f"  Context: {usage['used']:,}/{usage['max']:,} tokens ({usage['percent']}%)")
    print(f"  Auto mode: {_s('ON' if state.auto_mode else 'OFF', C.GREEN if state.auto_mode else C.RED)} (cap: {state.auto_cap})")
    print(f"  Output: {_s('VERBOSE' if state.verbose else ('COMPACT' if state.compact else 'NORMAL'), C.CYAN)}")
    print(f"  Verify: {state.verify_mode}")
    if state.pinned:
        print(f"  Pinned: {', '.join(Path(p).name for p in state.pinned)}")
    if state.task:
        print(f"  Goal: {_shorten(state.task, 60)}")
    print()

@cmd("clear", "Clear conversation history")
def cmd_clear(state: State, agent: Agent, args: str) -> None:
    agent.clear_history(keep_system=True)
    state.reset_task()
    status("Conversation cleared", "success")

@cmd("auto", "Toggle autonomous mode (auto on|off) or set cap (auto cap N)")
def cmd_auto(state: State, agent: Agent, args: str) -> None:
    parts = args.lower().split()
    if not parts:
        state.auto_mode = not state.auto_mode
        status(f"Auto mode {'ON' if state.auto_mode else 'OFF'}", "success")
    elif parts[0] == "on":
        state.auto_mode = True
        status("Auto mode ON", "success")
    elif parts[0] == "off":
        state.auto_mode = False
        status("Auto mode OFF", "success")
    elif parts[0] == "cap" and len(parts) > 1:
        try:
            state.auto_cap = max(1, int(parts[1]))
            status(f"Auto cap set to {state.auto_cap}", "success")
        except ValueError:
            status("Invalid cap value", "error")
    else:
        status("Usage: auto [on|off|cap N]", "warning")

@cmd("compact", "Toggle compact output (compact on|off)")
def cmd_compact(state: State, agent: Agent, args: str) -> None:
    if args.lower() == "on":
        state.compact = True
        state.verbose = False
    elif args.lower() == "off":
        state.compact = False
    else:
        state.compact = not state.compact
        if state.compact:
            state.verbose = False
    status(f"Compact mode {'ON' if state.compact else 'OFF'}", "success")

@cmd("verbose", "Toggle verbose output - show full file contents (verbose on|off)")
def cmd_verbose(state: State, agent: Agent, args: str) -> None:
    if args.lower() == "on":
        state.verbose = True
        state.compact = False
    elif args.lower() == "off":
        state.verbose = False
    else:
        state.verbose = not state.verbose
        if state.verbose:
            state.compact = False
    status(f"Verbose mode {'ON' if state.verbose else 'OFF'}", "success")

@cmd("verify", "Set verification mode (off|py_compile|<cmd>)")
def cmd_verify(state: State, agent: Agent, args: str) -> None:
    mode = args.strip().lower()
    if mode in ("off", "none"):
        state.verify_mode = "off"
        state.verify_cmd = None
        status("Verification disabled", "success")
    elif mode == "py_compile":
        state.verify_mode = "py_compile"
        state.verify_cmd = None
        status("Verification: py_compile", "success")
    elif mode:
        state.verify_mode = "custom"
        state.verify_cmd = args.strip()
        status(f"Verification: {state.verify_cmd}", "success")
    else:
        status(f"Current: {state.verify_mode}" + (f" ({state.verify_cmd})" if state.verify_cmd else ""), "info")


@cmd("pin", "Pin a file to always include in context")
def cmd_pin(state: State, agent: Agent, args: str) -> None:
    path = args.strip()
    if not path:
        status("Usage: pin <filepath>", "warning")
        return
    if not Path(path).exists():
        status(f"File not found: {path}", "error")
        return
    norm = _norm_path(path)
    if norm not in state.pinned:
        if len(state.pinned) >= MAX_PINNED_FILES:
            status(f"Max {MAX_PINNED_FILES} pinned files", "warning")
            return
        state.pinned.append(norm)
        agent.set_mandatory_files(state.pinned)
        status(f"Pinned: {path}", "success")
    else:
        status(f"Already pinned: {path}", "info")

@cmd("unpin", "Unpin a file")
def cmd_unpin(state: State, agent: Agent, args: str) -> None:
    path = args.strip()
    if not path:
        status("Usage: unpin <filepath>", "warning")
        return
    norm = _norm_path(path)
    if norm in state.pinned:
        state.pinned.remove(norm)
        agent.set_mandatory_files(state.pinned)
        status(f"Unpinned: {path}", "success")
    else:
        status(f"Not pinned: {path}", "warning")

@cmd("pins", "List pinned files")
def cmd_pins(state: State, agent: Agent, args: str) -> None:
    if state.pinned:
        print()
        print(_s("  Pinned files:", C.BOLD))
        for p in state.pinned:
            print(f"    {p}")
        print()
    else:
        status("No pinned files", "info")

@cmd("model", "Show or switch model")
def cmd_model(state: State, agent: Agent, args: str) -> None:
    new_model = args.strip()
    if not new_model:
        status(f"Current model: {agent.model}", "info")
        status(f"Context limit: {agent.max_context:,} tokens", "info")
        status(f"Provider: {'g4f (FREE)' if agent.use_g4f else 'OpenRouter'}", "info")
        return
    
    # Check if it's a g4f free model
    if new_model in G4F_FREE_MODELS:
        old = agent.model
        agent.model = new_model
        agent.use_g4f = True
        agent.max_context = G4F_FREE_MODELS[new_model].get("context", 128000)
        status(f"Switched from {old} to {new_model} (FREE via g4f)", "success")
        status(f"Context limit: {agent.max_context:,} tokens", "info")
        return
    
    # Check OpenRouter models
    if not model_exists(new_model):
        status(f"Model not found: {new_model}", "error")
        status("Use 'freemodels' to see free g4f models, or 'models' for OpenRouter", "info")
        return
    old = agent.model
    agent.model = new_model
    agent.use_g4f = False
    agent.max_context = get_context_limit(new_model)
    status(f"Switched from {old} to {new_model}", "success")
    status(f"Context limit: {agent.max_context:,} tokens", "info")

@cmd("freemodels", "List free g4f models (no API key needed)", shortcuts=["fm"])
def cmd_freemodels(state: State, agent: Agent, args: str) -> None:
    if not G4F_AVAILABLE:
        status("g4f not installed. Run: pip install g4f", "error")
        return
    print()
    print(_s("  Free Models (via g4f - no API key needed):", C.BOLD))
    print(_s("  " + "─" * 50, C.DIM))
    for name, info in sorted(G4F_FREE_MODELS.items()):
        current = " ← current" if name == agent.model else ""
        print(f"  {_s(name, C.CYAN)}: {info['description']}{_s(current, C.GREEN)}")
    print()
    print(_s("  Switch with: model <name>", C.DIM))
    print()

@cmd("models", "List all available models (free and paid)")
def cmd_models(state: State, agent: Agent, args: str) -> None:
    filter_text = args.strip().lower()
    
    print()
    print(_s("═" * 70, C.BPURPLE))
    print(_s("  ALL AVAILABLE MODELS", C.BOLD))
    print(_s("═" * 70, C.BPURPLE))
    
    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY 1: G4F FREE MODELS (No API Key Required)
    # ═══════════════════════════════════════════════════════════════════════
    g4f_models = list(G4F_FREE_MODELS.items())
    if filter_text:
        g4f_models = [(k, v) for k, v in g4f_models if filter_text in k.lower() or filter_text in v.get("description", "").lower()]
    g4f_models = sorted(g4f_models, key=lambda x: x[0])
    
    print()
    print(_s(f"  ┌─ [1] G4F FREE - No API Key Required ({len(g4f_models)} models) ─────────────┐", C.GREEN + C.BOLD))
    print()
    for name, info in g4f_models:
        current = " ← CURRENT" if name == agent.model else ""
        desc = info.get("description", "")
        print(f"    {_s(name, C.CYAN):35} {_s(desc, C.DIM)}{_s(current, C.GREEN + C.BOLD)}")
    print()
    
    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY 2 & 3: OpenRouter Models (Free and Paid)
    # ═══════════════════════════════════════════════════════════════════════
    print(_s("  Fetching OpenRouter models...", C.DIM))
    
    try:
        models = fetch_models()
        if models:
            or_free, or_paid = display_models(models, filter_text)
            
            # CATEGORY 2: OpenRouter FREE
            print()
            print(_s(f"  ┌─ [2] OPENROUTER FREE - Requires Free API Key ({len(or_free)} models) ──┐", C.GREEN + C.BOLD))
            print()
            for m in or_free:
                model_id = m.get("id", "?")
                ctx = m.get("context_length", 0)
                ctx_str = f"{ctx//1000}k" if ctx >= 1000 else str(ctx)
                current = " ← CURRENT" if model_id == agent.model else ""
                print(f"    {_s(model_id, C.CYAN):50} {_s(f'({ctx_str})', C.DIM)}{_s(current, C.GREEN + C.BOLD)}")
            print()
            
            # CATEGORY 3: OpenRouter PAID
            print()
            print(_s(f"  ┌─ [3] OPENROUTER PAID ({len(or_paid)} models) ─────────────────────────┐", C.YELLOW + C.BOLD))
            print()
            for m in or_paid:
                model_id = m.get("id", "?")
                ctx = m.get("context_length", 0)
                ctx_str = f"{ctx//1000}k" if ctx >= 1000 else str(ctx)
                pricing = m.get("pricing", {})
                price = float(pricing.get("prompt", "0") or "0") * 1000000
                price_str = f"${price:.2f}/M" if price > 0 else ""
                current = " ← CURRENT" if model_id == agent.model else ""
                print(f"    {_s(model_id, C.CYAN):50} {_s(f'({ctx_str}) {price_str}', C.DIM)}{_s(current, C.GREEN + C.BOLD)}")
            print()
            
    except Exception as e:
        status(f"Could not fetch OpenRouter models: {e}", "warning")
        print(_s("  Visit https://openrouter.ai/models to see OpenRouter models", C.DIM))
    
    print(_s("═" * 70, C.BPURPLE))
    print(_s("  Usage: model <name>  |  G4F models need no API key!", C.DIM))
    print(_s("═" * 70, C.BPURPLE))
    print()

@cmd("index", "Rebuild retrieval index")
def cmd_index(state: State, agent: Agent, args: str) -> None:
    status("Building index...", "context")
    agent.indexer.build(".")
    count = len(agent.indexer.index.get("files", {}))
    status(f"Indexed {count} files", "success")

@cmd("tokens", "Add/manage API tokens (saved globally)")
def cmd_tokens(state: State, agent: Agent, args: str) -> None:
    tokens_path = Path.home() / ".supercoder" / "tokens.txt"
    current_count = 0
    if tokens_path.exists():
        current_count = len([l for l in tokens_path.read_text().splitlines() if l.strip()])
    if args.strip().lower() == "show":
        if current_count == 0:
            status("No tokens configured", "warning")
        else:
            status(f"{current_count} token(s) configured at {tokens_path}", "info")
            for i, line in enumerate(tokens_path.read_text().splitlines(), 1):
                if line.strip():
                    masked = line.strip()[:8] + "..." + line.strip()[-4:] if len(line.strip()) > 12 else "****"
                    print(f"    {C.GRAY}{i}. {masked}{C.RST}")
        return
    if args.strip().lower() == "clear":
        if tokens_path.exists():
            tokens_path.unlink()
            TokenManager._tokens = None
            TokenManager._current_index = 0
        status("Tokens cleared", "success")
        return
    print(f"  {C.GRAY}╭─ Enter API tokens (one per line, empty line to finish){C.RST}")
    print(f"  {C.GRAY}│  Saves to: ~/.supercoder/tokens.txt{C.RST}")
    print(f"  {C.GRAY}│  Current: {current_count} token(s){C.RST}")
    new_tokens = []
    while True:
        line = input(f"  {C.BPURPLE}│{C.RST} ")
        if not line.strip():
            break
        new_tokens.append(line.strip())
    print(f"  {C.GRAY}╰─────────────────────────────{C.RST}")
    if not new_tokens:
        status("No tokens entered", "warning")
        return
    tokens_path.parent.mkdir(parents=True, exist_ok=True)
    tokens_path.write_text("\n".join(new_tokens) + "\n")
    TokenManager._tokens = None
    TokenManager._current_index = 0
    TokenManager.load_tokens()
    status(f"Saved {len(new_tokens)} token(s) globally", "success")

@cmd("quit", "Exit supercoder", shortcuts=["exit", "q"])
def cmd_quit(state: State, agent: Agent, args: str) -> None:
    print(f"\n  {C.BPURPLE}Goodbye!{C.RST}\n")
    sys.exit(0)


# ==============================================================================
# Task Commands
# ==============================================================================

@cmd("tasks", "List all tasks", shortcuts=["tl"])
def cmd_tasks(state: State, agent: Agent, args: str) -> None:
    tasks = _parse_tasks()
    if not tasks:
        status("No tasks found. Use 'plan' to create tasks.", "info")
        return
    print()
    print(_s("  Tasks:", C.BOLD))
    print(_s("  " + "─" * 50, C.DIM))
    for num, done, text in tasks:
        mark = _s("[x]", C.GREEN) if done else _s("[ ]", C.DIM)
        print(f"  {num}. {mark} {_s(text, C.DIM if done else C.RST)}")
    done_count = sum(1 for _, d, _ in tasks if d)
    print()
    print(_s(f"  Progress: {done_count}/{len(tasks)} complete", C.CYAN))
    print()

@cmd("task do", "Execute a specific task", shortcuts=["td"])
def cmd_task_do(state: State, agent: Agent, args: str) -> Optional[str]:
    try:
        num = int(args.strip())
    except ValueError:
        status("Usage: task do <number>", "warning")
        return None
    tasks = _parse_tasks()
    if num < 1 or num > len(tasks):
        status(f"Invalid task number (1-{len(tasks)})", "error")
        return None
    _, done, text = tasks[num - 1]
    if done:
        status(f"Task {num} already complete", "info")
        return None
    state.current_task_num = num
    status(f"Executing task {num}: {text}", "context")
    return f"Execute this task and mark it complete when done:\n\nTask {num}: {text}\n\nWhen finished, call the finish() tool with a summary."

@cmd("task done", "Mark a task as complete", shortcuts=["tc"])
def cmd_task_done(state: State, agent: Agent, args: str) -> None:
    try:
        num = int(args.strip())
    except ValueError:
        status("Usage: task done <number>", "warning")
        return
    if _update_task_status(num, True):
        status(f"Task {num} marked complete", "success")
    else:
        status(f"Could not update task {num}", "error")

@cmd("task undo", "Mark a task as incomplete", shortcuts=["tu"])
def cmd_task_undo(state: State, agent: Agent, args: str) -> None:
    try:
        num = int(args.strip())
    except ValueError:
        status("Usage: task undo <number>", "warning")
        return
    if _update_task_status(num, False):
        status(f"Task {num} marked incomplete", "success")
    else:
        status(f"Could not update task {num}", "error")

@cmd("task next", "Execute next incomplete task", shortcuts=["tn"])
def cmd_task_next(state: State, agent: Agent, args: str) -> Optional[str]:
    tasks = _parse_tasks()
    for num, done, text in tasks:
        if not done:
            state.current_task_num = num
            status(f"Executing task {num}: {text}", "context")
            return f"Execute this task and mark it complete when done:\n\nTask {num}: {text}\n\nWhen finished, call the finish() tool with a summary."
    status("All tasks complete!", "success")
    return None

# ==============================================================================
# Plan Command
# ==============================================================================

@cmd("plan", "Generate requirements, design, and tasks for a project")
def cmd_plan(state: State, agent: Agent, args: str) -> Optional[str]:
    description = args.strip()
    if not description:
        status("Usage: plan <project description>", "warning")
        return None
    req_prompt = load_prompt("Requirements") or "Generate requirements for the project."
    design_prompt = load_prompt("Design") or "Create a technical design."
    tasks_prompt = load_prompt("Tasks") or "Break down into tasks."
    Path(SUPERCODER_DIR).mkdir(exist_ok=True)
    status("Generating requirements...", "context")
    plan_prompt = f"""You are planning a software project. The user wants:

{description}

Please generate:
1. Requirements document (save to .supercoder/requirements.md)
2. Technical design (save to .supercoder/design.md)  
3. Task list with checkboxes (save to .supercoder/tasks.md)

Format tasks.md like:
- [ ] **[1] : Task description**
- [ ] **[2] : Another task**

Use the fsWrite tool to create each file. Start with requirements, then design, then tasks."""
    return plan_prompt


# ==============================================================================
# Main Execution Loop
# ==============================================================================

def _verify_writes(state: State) -> None:
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

_last_interrupt: float = 0.0
_INTERRUPT_WINDOW: float = 2.0

def _check_and_prompt_tokens(agent: Agent) -> None:
    """Check if API tokens exist, prompt user to input if missing."""
    # G4F models don't need API tokens
    if agent.use_g4f:
        if G4F_AVAILABLE:
            status(f"Using FREE model: {agent.model} (via g4f - no API key needed!)", "success")
        else:
            status("g4f not installed! Run: pip install g4f", "error")
        return
    
    # OpenRouter models need API key
    try:
        TokenManager.load_tokens()
        token = TokenManager.get_token()
        if token:
            status(f"Using model: {agent.model} (OpenRouter)", "success")
            return
    except:
        pass
    
    # No token found - prompt user
    print()
    status("OpenRouter API key required!", "warning")
    print()
    print(_s(f"  Model '{agent.model}' requires an OpenRouter API key.", C.WHITE))
    print(_s("  Get a FREE key at: https://openrouter.ai/keys", C.CYAN))
    print()
    print(_s("  Options:", C.BOLD))
    print(_s("  1. Enter your OpenRouter API key", C.WHITE))
    print(_s("  2. Press Enter to use g4f free models (no key needed)", C.GREEN))
    print()
    
    choice = input(_s("  Enter API key (or press Enter for free models): ", C.YELLOW)).strip()
    
    if not choice:
        # Switch to g4f free model
        agent.model = "kimi-k2"
        agent.use_g4f = True
        agent.max_context = G4F_FREE_MODELS["kimi-k2"]["context"]
        status("Switched to kimi-k2 (FREE g4f model - no API key needed!)", "success")
        return
    
    # Save the token
    tokens_path = Path.home() / ".supercoder" / "tokens.txt"
    tokens_path.parent.mkdir(parents=True, exist_ok=True)
    tokens_path.write_text(choice + "\n")
    
    TokenManager._tokens = None
    TokenManager._current_index = 0
    TokenManager.load_tokens()
    
    status(f"API token saved! Using {agent.model}", "success")
    print()

def run(agent: Agent, state: State) -> None:
    global _last_interrupt
    import time as _time
    header()
    
    # Show help on startup
    cmd_help(state, agent, "")
    
    # Check for API keys and prompt if missing (only for non-g4f models)
    _check_and_prompt_tokens(agent)
    
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
            cmd_line = user_input.strip()
            cmd_name = cmd_line.split()[0].lower() if cmd_line else ""
            cmd_args = cmd_line[len(cmd_name):].strip()
            if cmd_name in _SHORTCUTS:
                cmd_name = _SHORTCUTS[cmd_name]
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
                sys.stdout.flush()
                
                # Track tools used this turn
                tools_used_this_turn = []
                
                if not tool_calls:
                    # In auto mode, keep going until finish is called
                    if state.auto_mode:
                        # If model just talked without acting, give it a nudge to use tools
                        if had_content:
                            full_prompt = "You just explained your plan. Now execute it by using the appropriate tools. Don't explain again - just act."
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
                            print(f"{C.BPURPLE}  ╭─ {C.BRED}response needed{C.RST}")
                            answer = input(f"{C.BPURPLE}  ╰─▸ {C.RST}")
                            agent.AddToolResult(tc_id, name, f"User response: {answer}")
                            full_prompt = answer
                        continue
                    result = execute_tool(tc)
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


# ==============================================================================
# Entry Point
# ==============================================================================

def main():
    if sys.platform == "win32":
        try:
            os.system("")
        except Exception:
            pass
    agent = Agent(
        initial_prompt=DEFAULT_EXECUTOR,
        model="mistralai/devstral-2512:free",  # Free OpenRouter model for coding
        streaming=True
    )
    state = State()
    run(agent, state)

if __name__ == "__main__":
    main()
