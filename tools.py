"""
Tools module for Supercoder - All tool implementations
"""
import os
import re
import sys
import json
import subprocess
import shutil
import time
import hashlib
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# --- Undo System ---
@dataclass
class FileSnapshot:
    path: str
    content: Optional[str]
    existed: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

class UndoManager:
    def __init__(self, max_history: int = 100):
        self.history: List[List[FileSnapshot]] = []
        self.max_history = max_history
        self._lock = threading.Lock()
    
    def snapshot(self, paths: List[str]) -> int:
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

# --- Streaming Output Hook ---
_stream_handler = None

def set_stream_handler(handler) -> None:
    """Register a stream handler for interactive shell output."""
    global _stream_handler
    _stream_handler = handler

def _stream_event(event: str, text: Any = None) -> None:
    handler = _stream_handler
    if handler:
        try:
            handler(event, text)
            return
        except Exception:
            pass
    if event == "output":
        if text:
            print(text, end='', flush=True)
        return
    label = event.upper()
    msg = "" if text is None else str(text)
    print(f"[{label}] {msg}")

# --- Interactive Session Support ---
_INTERACTIVE_SESSIONS: Dict[int, Dict[str, Any]] = {}
_INTERACTIVE_SESSION_COUNTER = 0
_PROMPT_TOKEN_RE = re.compile(
    r'(?<!["(])(?P<label>[A-Za-z][^:\r\n]{0,60})(?P<punct>[:?>])\s*(?P<default>\([^\r\n]*?\))?'
)
_CMD_SEP_RE = re.compile(r'\s*(?:&&|\|\|)\s*|\s&\s')
_PROMPT_IDLE_TIMEOUT = 1.0

def _next_interactive_session_id() -> int:
    global _INTERACTIVE_SESSION_COUNTER
    _INTERACTIVE_SESSION_COUNTER += 1
    return _INTERACTIVE_SESSION_COUNTER

def _detect_ps_exe() -> Optional[str]:
    if os.name != "nt":
        return None
    if shutil.which("pwsh"):
        return "pwsh"
    if shutil.which("powershell"):
        return "powershell"
    return None

_PS_EXE = _detect_ps_exe()

def _sanitize_cmd(cmd: str) -> str:
    return _CMD_SEP_RE.sub("; ", str(cmd).strip())

def _build_shell_command(command: str, interactive: bool = False) -> str:
    if os.name == "nt":
        if _PS_EXE:
            sanitized = _sanitize_cmd(command)
            sanitized = sanitized.replace('"', '`"')
            flags = "-NoProfile -ExecutionPolicy Bypass"
            if not interactive:
                flags = f"{flags} -NonInteractive"
            return f'{_PS_EXE} {flags} -Command "{sanitized}"'
        return f'cmd.exe /c {command}'
    return command

def _normalize_key(label: str) -> str:
    return re.sub(r'\s+', ' ', label).strip().lower()

def _is_prompt_label(label: str) -> bool:
    if not label:
        return False
    trimmed = label.strip()
    if len(trimmed) < 2 or len(trimmed) > 40:
        return False
    lower = trimmed.lower()
    if re.match(r"^test\s*\d+$", lower) or lower.startswith("test "):
        return False
    if lower.startswith(("about to write to", "press ^c", "see `", "use `")):
        return False
    if "\\" in trimmed or "/" in trimmed:
        return False
    return True

def _clean_prompt_label(label: str, last_response: Optional[str]) -> str:
    cleaned = (label or "").strip()
    if last_response:
        if last_response in cleaned:
            cleaned = cleaned.split(last_response)[-1].strip()
    if "(" in cleaned:
        cleaned = cleaned.split("(", 1)[0].strip()
    if "  " in cleaned:
        cleaned = re.split(r"\s{2,}", cleaned)[-1].strip()
    if cleaned and len(cleaned) > 40:
        cleaned = cleaned[:40].strip()
    return cleaned

def _lookup_response(response_map: Optional[Dict[str, str]], prompt_key: str, prompt_line: str) -> Tuple[Optional[str], str]:
    if not response_map:
        return None, ""
    if prompt_key in response_map:
        return response_map[prompt_key], prompt_key
    if prompt_line:
        best_key = ""
        normalized_line = _normalize_key(prompt_line)
        for key in response_map.keys():
            if key in ("", "default", "*"):
                continue
            if key and key in normalized_line:
                if len(key) > len(best_key):
                    best_key = key
        if best_key:
            return response_map[best_key], best_key
    if "*" in response_map:
        return response_map["*"], "*"
    if "default" in response_map:
        return response_map["default"], "default"
    return None, ""

def _session_set_pending_prompt(session: Dict[str, Any], prompt_key: str, prompt_text: str) -> None:
    last_key = session.get("last_prompt_key", "")
    last_text = session.get("last_prompt_text", "")
    if prompt_key == last_key and prompt_text == last_text:
        session["repeat_count"] = session.get("repeat_count", 0) + 1
    else:
        session["repeat_count"] = 0
    session["pending_prompt"] = (prompt_key, prompt_text)
    session["pending_since"] = time.monotonic()
    session["last_prompt_key"] = prompt_key
    session["last_prompt_text"] = prompt_text
    session["saw_prompt"] = True
    session["awaiting_prompt"] = False

def _session_append_output(session: Dict[str, Any], text: Any) -> None:
    if not text:
        return
    if not isinstance(text, str):
        text = str(text)
    session["output_lines"].append(text)
    session["output_count"] = session.get("output_count", 0) + 1
    session["full_output"] += text
    _stream_event("output", text)
    session["scan_buffer"] += text
    session["last_output_time"] = time.monotonic()
    _session_scan_prompts(session)

def _session_scan_prompts(session: Dict[str, Any]) -> None:
    scan_buffer = session["scan_buffer"]
    scan_pos = session["scan_pos"]
    send_scan_pos = session.get("send_scan_pos", 0)
    if len(scan_buffer) > 8000:
        excess = len(scan_buffer) - 8000
        scan_buffer = scan_buffer[excess:]
        scan_pos = max(0, scan_pos - excess)
        send_scan_pos = max(0, send_scan_pos - excess)
    scan_start = max(0, scan_pos - 200)
    last_prompt = None
    for match in _PROMPT_TOKEN_RE.finditer(scan_buffer, scan_start):
        if match.end() <= scan_pos:
            continue
        if session.get("awaiting_prompt") and match.end() <= send_scan_pos:
            continue
        raw_label = match.group("label").strip()
        label = _clean_prompt_label(raw_label, session.get("last_response"))
        if not _is_prompt_label(label):
            continue
        key = _normalize_key(label)
        punct = match.group("punct")
        default = match.group("default") or ""
        prompt_text = f"{label}{punct} {default}".strip()
        last_prompt = (key, prompt_text)
    if last_prompt:
        _session_set_pending_prompt(session, last_prompt[0], last_prompt[1])
    session["scan_buffer"] = scan_buffer
    session["scan_pos"] = len(scan_buffer)
    session["send_scan_pos"] = send_scan_pos

# --- Shell Execution ---
def execute_pwsh(
    command: Optional[str] = None,
    timeout: int = 60,
    interactive_responses: Optional[Any] = None,
    session_id: Optional[int] = None,
    input_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a shell command with optional interactive response handling.

    If the command prompts for input, the tool returns status=need_input with
    a sessionId and prompt. Call execute_pwsh again with session_id + input_text.

    Args:
        command: Command to execute (required for new sessions)
        timeout: Timeout in seconds for this call
        interactive_responses: Optional list or map of responses for auto-reply
        session_id: Continue an interactive session
        input_text: One line of input to send to an existing session

    Returns:
        Dict with stdout, stderr, returncode, status, and optional sessionId/prompt
    """
    wexpect = None
    if os.name == "nt":
        try:
            import warnings
            warnings.filterwarnings(
                "ignore",
                message="pkg_resources is deprecated as an API.*",
                category=UserWarning,
            )
            import wexpect as _wexpect
            wexpect = _wexpect
        except ImportError:
            wexpect = None

    def _normalize_response_map(data: Dict[str, Any]) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        for key, val in data.items():
            if key is None:
                continue
            norm_key = _normalize_key(str(key))
            normalized[norm_key] = "" if val is None else str(val)
        return normalized

    def _apply_responses(session: Dict[str, Any], responses: Any) -> None:
        session["response_list"] = None
        session["response_map"] = None
        session["response_index"] = 0
        session["last_response"] = None
        session["repeat_count"] = 0
        if isinstance(responses, dict):
            session["response_map"] = _normalize_response_map(responses)
        elif isinstance(responses, (list, tuple)):
            session["response_list"] = ["" if r is None else str(r) for r in responses]

    def _send_input(session: Dict[str, Any], response: Optional[str]) -> None:
        text = "" if response is None else str(response)
        display = text if text else "<enter>"
        _stream_event("send", display)
        session["child"].sendline(text)
        now = time.monotonic()
        session["last_send_time"] = now
        session["last_output_time"] = now
        session["last_response"] = text
        session["awaiting_prompt"] = True
        session["send_output_count"] = session.get("output_count", 0)
        session["send_scan_pos"] = len(session.get("scan_buffer", ""))
        session["pending_prompt"] = None
        session["pending_since"] = None

    def _next_auto_response(session: Dict[str, Any], prompt_key: str, prompt_text: str) -> Optional[str]:
        response_map = session.get("response_map")
        if response_map:
            response, _ = _lookup_response(response_map, prompt_key, prompt_text)
            return response
        response_list = session.get("response_list")
        if response_list is None:
            return None
        repeat_count = session.get("repeat_count", 0)
        last_response = session.get("last_response")
        if repeat_count > 0 and last_response is not None and repeat_count <= 2:
            return last_response
        index = session.get("response_index", 0)
        if index >= len(response_list):
            return None
        session["response_index"] = index + 1
        return response_list[index]

    def _finish_session(session: Dict[str, Any], exit_code: int) -> Dict[str, Any]:
        try:
            session["child"].close()
        except Exception:
            pass
        _INTERACTIVE_SESSIONS.pop(session["id"], None)
        _stream_event("end", exit_code)
        return {
            "stdout": session.get("full_output", ""),
            "stderr": "",
            "returncode": exit_code,
            "status": "completed",
        }

    def _run_interactive(session: Dict[str, Any], timeout_sec: int) -> Dict[str, Any]:
        deadline = time.monotonic() + timeout_sec if timeout_sec and timeout_sec > 0 else None
        child = session["child"]
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                try:
                    child.close()
                except Exception:
                    pass
                _INTERACTIVE_SESSIONS.pop(session["id"], None)
                _stream_event("end", "timeout")
                return {
                    "stdout": session.get("full_output", ""),
                    "stderr": f"Command timed out after {timeout_sec}s",
                    "returncode": -1,
                    "status": "error",
                }
            try:
                index = child.expect([r"[\s\S]+", wexpect.EOF, wexpect.TIMEOUT], timeout=0.2)
            except wexpect.EOF:
                index = 1
            except wexpect.TIMEOUT:
                index = 2
            except Exception as e:
                try:
                    child.close()
                except Exception:
                    pass
                _INTERACTIVE_SESSIONS.pop(session["id"], None)
                _stream_event("end", "error")
                return {
                    "stdout": session.get("full_output", ""),
                    "stderr": f"Interactive command failed: {e}",
                    "returncode": -1,
                    "status": "error",
                }

            if index == 0:
                if child.before:
                    _session_append_output(session, child.before)
                if child.after:
                    _session_append_output(session, child.after)
                continue

            if index == 1:
                if child.before:
                    _session_append_output(session, child.before)
                exit_code = child.exitstatus if child.exitstatus is not None else 0
                return _finish_session(session, exit_code)

            pending = session.get("pending_prompt")
            if pending:
                prompt_key, prompt_text = pending
                response = _next_auto_response(session, prompt_key, prompt_text)
                if response is not None:
                    _send_input(session, response)
                    continue
                _stream_event("pause", prompt_text)
                return {
                    "stdout": session.get("full_output", ""),
                    "stderr": "",
                    "returncode": -1,
                    "status": "need_input",
                    "prompt": prompt_text,
                    "sessionId": session["id"],
                }

            idle_for = time.monotonic() - session.get("last_output_time", time.monotonic())
            post_send_idle = time.monotonic() - session.get("last_send_time", time.monotonic())
            if session.get("saw_prompt") and idle_for >= _PROMPT_IDLE_TIMEOUT and post_send_idle >= _PROMPT_IDLE_TIMEOUT:
                output_count = session.get("output_count", 0)
                send_output_count = session.get("send_output_count", 0)
                awaiting_prompt = session.get("awaiting_prompt", False)
                if awaiting_prompt and output_count <= send_output_count:
                    continue
                send_scan_pos = session.get("send_scan_pos", 0)
                tail = ""
                if session.get("scan_buffer"):
                    tail = session["scan_buffer"].splitlines()[-1].strip()
                prompt_text = ""
                if tail and (":" in tail or tail.endswith("?") or tail.endswith(">")):
                    prompt_text = tail
                scan_buffer = session.get("scan_buffer", "")
                last_prompt = None
                for match in _PROMPT_TOKEN_RE.finditer(scan_buffer):
                    if awaiting_prompt and match.end() <= send_scan_pos:
                        continue
                    raw_label = match.group("label").strip()
                    label = _clean_prompt_label(raw_label, session.get("last_response"))
                    if not _is_prompt_label(label):
                        continue
                    punct = match.group("punct")
                    default = match.group("default") or ""
                    prompt_text = f"{label}{punct} {default}".strip()
                    last_prompt = (label, prompt_text)
                if last_prompt:
                    label, prompt_text = last_prompt
                    prompt_key = _normalize_key(label)
                else:
                    if not prompt_text:
                        if awaiting_prompt:
                            continue
                        prompt_text = session.get("last_prompt_text", "input:")
                    label = re.split(r"[:?>]", prompt_text, 1)[0].strip()
                    prompt_key = _normalize_key(label) if label else ""
                _session_set_pending_prompt(session, prompt_key, prompt_text)
                _stream_event("pause", prompt_text)
                return {
                    "stdout": session.get("full_output", ""),
                    "stderr": "",
                    "returncode": -1,
                    "status": "need_input",
                    "prompt": prompt_text,
                    "sessionId": session["id"],
                }

            if hasattr(child, "isalive") and not child.isalive():
                exit_code = child.exitstatus if child.exitstatus is not None else 0
                return _finish_session(session, exit_code)

    if session_id is not None:
        session = _INTERACTIVE_SESSIONS.get(session_id)
        if not session:
            return {
                "stdout": "",
                "stderr": f"Interactive session {session_id} not found",
                "returncode": -1,
                "status": "error",
            }
        if wexpect is None:
            return {
                "stdout": "",
                "stderr": "Interactive mode requires wexpect on Windows. Install with: pip install wexpect",
                "returncode": -1,
                "status": "error",
            }
        _stream_event("start", session.get("command", ""))
        if interactive_responses is not None:
            _apply_responses(session, interactive_responses)
        if input_text is not None:
            _send_input(session, input_text)
        return _run_interactive(session, timeout)

    if not command:
        return {
            "stdout": "",
            "stderr": "Command required for execute_pwsh",
            "returncode": -1,
            "status": "error",
        }

    # Prefer interactive engine to detect prompts automatically (Windows + wexpect).
    if wexpect is None:
        if interactive_responses or input_text or session_id is not None:
            return {
                "stdout": "",
                "stderr": "Interactive mode requires wexpect on Windows. Install with: pip install wexpect",
                "returncode": -1,
                "status": "error",
            }
        try:
            shell_cmd = _build_shell_command(command, interactive=False)
            result = subprocess.run(
                shell_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "status": "completed",
            }
        except subprocess.TimeoutExpired as e:
            return {
                "stdout": e.stdout or "",
                "stderr": f"Command timed out after {timeout}s",
                "returncode": -1,
                "status": "error",
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "status": "error",
            }

    session_id = _next_interactive_session_id()
    shell_cmd = _build_shell_command(command, interactive=True)
    try:
        child = wexpect.spawn(shell_cmd, timeout=timeout, encoding="utf-8", codec_errors="ignore")
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Failed to start command: {e}",
            "returncode": -1,
            "status": "error",
        }

    session = {
        "id": session_id,
        "command": command,
        "child": child,
        "output_lines": [],
        "full_output": "",
        "scan_buffer": "",
        "scan_pos": 0,
        "pending_prompt": None,
        "pending_since": None,
        "last_output_time": time.monotonic(),
        "last_send_time": time.monotonic(),
        "response_list": None,
        "response_map": None,
        "response_index": 0,
        "last_prompt_key": "",
        "last_prompt_text": "",
        "saw_prompt": False,
        "awaiting_prompt": False,
        "output_count": 0,
        "send_output_count": 0,
        "send_scan_pos": 0,
        "repeat_count": 0,
        "last_response": None,
    }
    _INTERACTIVE_SESSIONS[session_id] = session
    _stream_event("start", command)
    if interactive_responses is not None:
        _apply_responses(session, interactive_responses)
        if isinstance(interactive_responses, dict):
            _stream_event("info", f"RESPONSES: {len(interactive_responses)} (map)")
        elif isinstance(interactive_responses, (list, tuple)):
            _stream_event("info", f"RESPONSES: {len(interactive_responses)} (list)")
    if input_text is not None:
        _send_input(session, input_text)
    return _run_interactive(session, timeout)


# --- Background Process Management ---
_background_processes: Dict[int, subprocess.Popen] = {}
_process_counter = 0

def control_pwsh_process(action: str, command: str = None, process_id: int = None, path: str = None) -> Dict[str, Any]:
    """Start or stop background processes"""
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

def list_processes() -> Dict[str, Any]:
    """List running background processes"""
    processes = []
    for pid, proc in _background_processes.items():
        status = "running" if proc.poll() is None else "stopped"
        processes.append({"processId": pid, "status": status})
    return {"processes": processes}

def get_process_output(process_id: int, lines: int = 100) -> Dict[str, Any]:
    """Get output from a background process"""
    if process_id not in _background_processes:
        return {"error": f"Process {process_id} not found"}
    
    proc = _background_processes[process_id]
    
    # Check if process is still running
    poll_result = proc.poll()
    status = "running" if poll_result is None else f"exited with code {poll_result}"
    
    # For now, return status without trying to read output
    # Reading stdout.read() blocks indefinitely on Windows when no data is available
    # TODO: Implement proper non-blocking read for Windows
    return {
        "output": f"Process status: {status}\n\nNote: Output reading is disabled to prevent hangs. Check the terminal where you started Supercoder to see the dev server output.",
        "status": status
    }

# --- File System ---
def list_directory(path: str = ".") -> Dict[str, Any]:
    """List directory contents"""
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

def read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    """
    Read a file's contents, optionally with line range.
    
    Args:
        path: Path to the file
        start_line: Starting line number (1-indexed, inclusive). If None, starts from beginning
        end_line: Ending line number (1-indexed, inclusive). If None, reads to end
    
    Returns:
        File contents as string, or just the specified line range
    """
    with open(path, 'r', encoding='utf-8') as f:
        if start_line is None and end_line is None:
            return f.read()
        
        lines = f.readlines()
        
        # Convert to 0-indexed
        start_idx = (start_line - 1) if start_line else 0
        end_idx = end_line if end_line else len(lines)
        
        # Clamp to valid range
        start_idx = max(0, min(start_idx, len(lines)))
        end_idx = max(0, min(end_idx, len(lines)))
        
        return ''.join(lines[start_idx:end_idx])

def read_multiple_files(paths: List[str]) -> Dict[str, Any]:
    """Read multiple files at once"""
    result = {}
    for p in paths:
        try:
            result[p] = read_file(p)
        except Exception as e:
            result[p] = {"error": str(e)}
    return result

def read_code(path: str, symbol: str = None, include_structure: bool = True) -> Dict[str, Any]:
    """
    Intelligently read code files with AST-based structure analysis and optional symbol search.
    
    Args:
        path: Path to the code file
        symbol: Optional symbol name to search for (function, class, variable)
        include_structure: Whether to include AST structure analysis (default True)
    
    Returns:
        Dict with content, structure analysis, and optionally symbol locations
    """
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
                        "decorators": [ast.unparse(d) if hasattr(ast, 'unparse') else str(d) for d in node.decorator_list]
                    })
                elif isinstance(node, ast.ClassDef):
                    methods = []
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            methods.append(item.name)
                    structure["classes"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "end_line": node.end_lineno,
                        "methods": methods,
                        "bases": [ast.unparse(b) if hasattr(ast, 'unparse') else str(b) for b in node.bases]
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        structure["imports"].append({"module": alias.name, "alias": alias.asname, "line": node.lineno})
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        structure["imports"].append({"module": f"{node.module}.{alias.name}", "alias": alias.asname, "line": node.lineno})
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            structure["global_vars"].append({"name": target.id, "line": node.lineno})
            
            result["structure"] = structure
        except SyntaxError as e:
            result["structure_error"] = f"Syntax error: {e}"
    
    # JavaScript/TypeScript basic structure (regex-based)
    elif p.suffix in (".js", ".ts", ".jsx", ".tsx") and include_structure:
        structure = {
            "functions": [],
            "classes": [],
            "imports": [],
            "exports": []
        }
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            # Functions
            func_match = re.match(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', line)
            if func_match:
                structure["functions"].append({"name": func_match.group(1), "line": i})
            # Arrow functions assigned to const/let/var
            arrow_match = re.match(r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', line)
            if arrow_match:
                structure["functions"].append({"name": arrow_match.group(1), "line": i})
            # Classes
            class_match = re.match(r'(?:export\s+)?class\s+(\w+)', line)
            if class_match:
                structure["classes"].append({"name": class_match.group(1), "line": i})
            # Imports
            if line.strip().startswith('import '):
                structure["imports"].append({"line": i, "statement": line.strip()[:100]})
            # Exports
            if line.strip().startswith('export '):
                structure["exports"].append({"line": i, "statement": line.strip()[:100]})
        
        result["structure"] = structure
    
    # Symbol search across the file
    if symbol:
        symbol_locations = []
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            if re.search(r'\b' + re.escape(symbol) + r'\b', line):
                symbol_locations.append({
                    "line": i,
                    "text": line.strip()[:150],
                    "is_definition": bool(re.match(rf'(?:def|class|function|const|let|var)\s+{re.escape(symbol)}\b', line.strip()))
                })
        result["symbol_search"] = {
            "symbol": symbol,
            "occurrences": len(symbol_locations),
            "locations": symbol_locations[:50]  # Cap at 50 results
        }
    
    return result

def file_search(pattern: str, path: str = ".") -> Dict[str, Any]:
    """Search for files by name pattern"""
    matches = []
    pattern_lower = pattern.lower()
    for root, dirs, files in os.walk(path):
        # Skip common ignore dirs
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.venv', 'venv'}]
        for f in files:
            if pattern_lower in f.lower():
                matches.append(os.path.join(root, f))
    return {"matches": matches[:100]}

def grep_search(pattern: str, path: str = ".") -> Dict[str, Any]:
    """Search for regex pattern in files"""
    # Handle non-string pattern
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
                            hits.append({"file": filepath, "line": i, "text": line.strip()[:200]})
                            if len(hits) >= 100:
                                return {"hits": hits, "truncated": True}
            except:
                continue
    return {"hits": hits}

def delete_file(path: str) -> Dict[str, Any]:
    """Delete a file"""
    undo_manager.snapshot([path])
    try:
        Path(path).unlink()
        return {"deleted": path}
    except FileNotFoundError:
        return {"error": f"File not found: {path}"}
    except Exception as e:
        return {"error": str(e)}

def fs_write(path: str, content: str) -> Dict[str, Any]:
    """Write content to a file"""
    undo_manager.snapshot([path])
    try:
        # Handle case where content is passed as dict/list instead of string
        if not isinstance(content, str):
            content = json.dumps(content, indent=2)
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"written": path, "bytes": len(content)}
    except Exception as e:
        return {"error": str(e)}

def fs_append(path: str, content: str) -> Dict[str, Any]:
    """Append content to a file"""
    undo_manager.snapshot([path])
    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(content)
        return {"appended": path, "bytes": len(content)}
    except Exception as e:
        return {"error": str(e)}

def str_replace(path: str, old: str, new: str) -> Dict[str, Any]:
    """Replace text in a file"""
    undo_manager.snapshot([path])
    try:
        # Handle case where old/new are passed as non-strings
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

# --- Diagnostics ---
def get_diagnostics(path: str) -> Dict[str, Any]:
    """Check for syntax/lint errors"""
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

# --- Property Coverage (placeholder) ---
def property_coverage(spec_path: str, code_path: str) -> Dict[str, Any]:
    """Analyze how well code covers spec requirements"""
    # Simple implementation - count requirements vs implementations
    try:
        spec = read_file(spec_path)
        code = read_file(code_path)
        
        # Count requirement markers
        req_count = len(re.findall(r'(?:MUST|SHALL|SHOULD|REQUIRED)', spec, re.IGNORECASE))
        
        # Count function/class definitions
        impl_count = len(re.findall(r'(?:def |class )', code))
        
        return {
            "requirements_found": req_count,
            "implementations_found": impl_count,
            "coverage_ratio": impl_count / max(req_count, 1)
        }
    except Exception as e:
        return {"error": str(e)}

# --- Additional Development Tools ---

def insert_lines(path: str, line_number: int, content: str) -> Dict[str, Any]:
    """Insert text at a specific line number"""
    undo_manager.snapshot([path])
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines(keepends=True)
        idx = max(0, line_number - 1)
        lines.insert(idx, content if content.endswith('\n') else content + '\n')
        Path(path).write_text(''.join(lines), encoding='utf-8')
        return {"inserted": path, "at_line": line_number}
    except Exception as e:
        return {"error": str(e)}

def remove_lines(path: str, start_line: int, end_line: int) -> Dict[str, Any]:
    """Remove lines from a file"""
    undo_manager.snapshot([path])
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines(keepends=True)
        del lines[start_line - 1:end_line]
        Path(path).write_text(''.join(lines), encoding='utf-8')
        return {"removed": f"lines {start_line}-{end_line}", "from": path}
    except Exception as e:
        return {"error": str(e)}

def move_file(source: str, destination: str) -> Dict[str, Any]:
    """Move or rename a file"""
    import shutil
    undo_manager.snapshot([source, destination])
    try:
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source, destination)
        return {"moved": source, "to": destination}
    except Exception as e:
        return {"error": str(e)}

def copy_file(source: str, destination: str) -> Dict[str, Any]:
    """Copy a file"""
    import shutil
    undo_manager.snapshot([destination])
    try:
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return {"copied": source, "to": destination}
    except Exception as e:
        return {"error": str(e)}

def create_directory(path: str) -> Dict[str, Any]:
    """Create a directory"""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return {"created": path}
    except Exception as e:
        return {"error": str(e)}

def undo(transaction_id: int = None) -> Dict[str, Any]:
    """Undo the last file operation"""
    return undo_manager.undo(transaction_id)

def get_symbols(path: str) -> Dict[str, Any]:
    """Extract functions, classes from Python file"""
    try:
        import ast
        tree = ast.parse(Path(path).read_text(encoding='utf-8'))
        symbols = {"functions": [], "classes": [], "imports": []}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols["functions"].append({"name": node.name, "line": node.lineno})
            elif isinstance(node, ast.ClassDef):
                symbols["classes"].append({"name": node.name, "line": node.lineno})
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    symbols["imports"].append(alias.name)
        return symbols
    except Exception as e:
        return {"error": str(e)}

def find_references(symbol: str, path: str = ".") -> Dict[str, Any]:
    """Find all references to a symbol"""
    results = []
    exts = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.go'}
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules'}]
        for f in files:
            if Path(f).suffix in exts:
                fp = os.path.join(root, f)
                try:
                    for i, line in enumerate(open(fp, encoding='utf-8'), 1):
                        if symbol in line:
                            results.append({"file": fp, "line": i, "text": line.strip()[:100]})
                except: pass
    return {"references": results[:50]}

def file_diff(path1: str, path2: str) -> Dict[str, Any]:
    """Compare two files"""
    import difflib
    try:
        c1 = Path(path1).read_text(encoding='utf-8').splitlines(keepends=True)
        c2 = Path(path2).read_text(encoding='utf-8').splitlines(keepends=True)
        diff = list(difflib.unified_diff(c1, c2, fromfile=path1, tofile=path2))
        return {"diff": ''.join(diff) or "Files identical"}
    except Exception as e:
        return {"error": str(e)}

def http_request(url: str, method: str = "GET", body: str = None) -> Dict[str, Any]:
    """Make HTTP request"""
    import urllib.request, urllib.error
    try:
        req = urllib.request.Request(url, method=method, data=body.encode() if body else None)
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"status": r.status, "body": r.read().decode()}
    except Exception as e:
        return {"error": str(e)}

def download_file(url: str, dest: str) -> Dict[str, Any]:
    """Download file from URL"""
    import urllib.request
    try:
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, dest)
        return {"downloaded": dest, "size": Path(dest).stat().st_size}
    except Exception as e:
        return {"error": str(e)}

def system_info() -> Dict[str, Any]:
    """Get system info"""
    import platform
    return {"os": platform.system(), "python": platform.python_version(), "cwd": os.getcwd()}

def run_tests(path: str = ".") -> Dict[str, Any]:
    """Run tests"""
    result = execute_pwsh(f'python -m pytest "{path}" -v', timeout=120)
    return {"stdout": result["stdout"], "stderr": result["stderr"], "passed": result["returncode"] == 0}

def format_code(path: str) -> Dict[str, Any]:
    """Format code file"""
    undo_manager.snapshot([path])
    if Path(path).suffix == ".py":
        result = execute_pwsh(f'python -m black "{path}" 2>&1', timeout=30)
    else:
        result = execute_pwsh(f'npx prettier --write "{path}" 2>&1', timeout=30)
    return {"formatted": path, "output": result["stdout"]}


# --- Web Search ---
def web_search(query: str, site: str = None, max_results: int = 5) -> Dict[str, Any]:
    """
    Search the web for programming help using DuckDuckGo.
    
    Args:
        query: Search query (e.g., "python async await example")
        site: Optional site to restrict search (e.g., "stackoverflow.com", "github.com")
        max_results: Maximum number of results to return (default 5)
    
    Returns:
        Dict with search results including titles, URLs, and snippets
    """
    import urllib.request
    import urllib.parse
    from html.parser import HTMLParser
    
    # Build search query
    search_query = query
    if site:
        search_query = f"site:{site} {query}"
    
    # URL encode the query
    encoded_query = urllib.parse.quote_plus(search_query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    try:
        # Make request with browser-like headers
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
        
        # Simple HTML parser to extract results
        class DDGParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results = []
                self.current_result = {}
                self.in_result = False
                self.in_title = False
                self.in_snippet = False
                self.current_text = ""
            
            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == 'a' and 'result__a' in attrs_dict.get('class', ''):
                    self.in_result = True
                    self.in_title = True
                    self.current_result = {'url': attrs_dict.get('href', ''), 'title': '', 'snippet': ''}
                elif tag == 'a' and 'result__snippet' in attrs_dict.get('class', ''):
                    self.in_snippet = True
            
            def handle_endtag(self, tag):
                if tag == 'a' and self.in_title:
                    self.current_result['title'] = self.current_text.strip()
                    self.current_text = ""
                    self.in_title = False
                elif tag == 'a' and self.in_snippet:
                    self.current_result['snippet'] = self.current_text.strip()
                    self.current_text = ""
                    self.in_snippet = False
                    if self.current_result.get('title'):
                        self.results.append(self.current_result)
                    self.current_result = {}
                    self.in_result = False
            
            def handle_data(self, data):
                if self.in_title or self.in_snippet:
                    self.current_text += data
        
        parser = DDGParser()
        parser.feed(html)
        
        results = parser.results[:max_results]
        
        if not results:
            return {"query": query, "results": [], "message": "No results found"}
        
        return {
            "query": query,
            "site_filter": site,
            "results": results
        }
        
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


def search_stackoverflow(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search Stack Overflow for programming help.
    
    Args:
        query: Search query (e.g., "python list comprehension filter")
        max_results: Maximum number of results to return
    
    Returns:
        Dict with Stack Overflow results
    """
    return web_search(query, site="stackoverflow.com", max_results=max_results)


# --- User Interaction ---
# This is a special marker tool - actual interaction is handled by Supercoder.py
def interact_with_user(message: str, interaction_type: str = "info") -> Dict[str, Any]:
    """
    Signal that the agent wants to interact with the user.
    This is a marker - actual interaction is handled by the execution loop.
    
    Args:
        message: The message to show the user
        interaction_type: One of "info" (task complete/status), "question" (needs input), "error" (problem encountered)
    
    Returns:
        Marker dict that the execution loop will intercept
    """
    return {
        "_interaction": True,
        "message": message,
        "type": interaction_type
    }


def request_user_command(command: str, reason: str, working_directory: str = None) -> Dict[str, Any]:
    """
    Request the user to run an interactive command manually in their terminal.
    Use this for commands that require user input (arrow keys, menus, prompts).
    
    Args:
        command: The command to ask the user to run (e.g., "supabase link")
        reason: Why this command needs to be run manually
        working_directory: Optional directory where command should be run
    
    Returns:
        Marker dict that the execution loop will intercept
    """
    return {
        "_user_command": True,
        "command": command,
        "reason": reason,
        "working_directory": working_directory
    }


# --- New Enhanced Tools ---

def get_file_info(path: str) -> Dict[str, Any]:
    """
    Get file metadata including size, modification time, permissions.
    
    Args:
        path: Path to the file or directory
    
    Returns:
        Dict with file information or error
    """
    try:
        p = Path(path)
        if not p.exists():
            return {"error": f"Path does not exist: {path}"}
        
        stat = p.stat()
        info = {
            "path": str(p),
            "exists": True,
            "is_file": p.is_file(),
            "is_dir": p.is_dir(),
            "size_bytes": stat.st_size,
            "size_human": _human_readable_size(stat.st_size),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }
        
        if p.is_file():
            info["extension"] = p.suffix
            info["name"] = p.name
            
        return info
    except Exception as e:
        return {"error": str(e)}


def _human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def list_directory_tree(path: str = ".", max_depth: int = 3, ignore_patterns: List[str] = None) -> Dict[str, Any]:
    """
    Get a recursive tree view of directory structure.
    
    Args:
        path: Root directory to start from
        max_depth: Maximum depth to recurse (default 3)
        ignore_patterns: List of patterns to ignore (e.g., ['.git', '__pycache__', 'node_modules'])
    
    Returns:
        Dict with tree structure
    """
    if ignore_patterns is None:
        ignore_patterns = ['.git', '__pycache__', 'node_modules', '.venv', 'venv', '.supercoder']
    
    def should_ignore(name: str) -> bool:
        return any(pattern in name for pattern in ignore_patterns)
    
    def build_tree(current_path: Path, current_depth: int) -> Dict[str, Any]:
        if current_depth > max_depth:
            return {"truncated": True}
        
        try:
            if not current_path.is_dir():
                return {"type": "file", "size": current_path.stat().st_size}
            
            children = {}
            for child in sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                if should_ignore(child.name):
                    continue
                children[child.name] = build_tree(child, current_depth + 1)
            
            return {"type": "directory", "children": children}
        except PermissionError:
            return {"error": "Permission denied"}
        except Exception as e:
            return {"error": str(e)}
    
    try:
        root = Path(path)
        if not root.exists():
            return {"error": f"Path does not exist: {path}"}
        
        tree = build_tree(root, 0)
        return {"path": str(root), "tree": tree}
    except Exception as e:
        return {"error": str(e)}


def replace_multiple(path: str, replacements: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Make multiple find/replace operations in one file.
    
    Args:
        path: Path to the file
        replacements: List of dicts with 'old' and 'new' keys
    
    Returns:
        Dict with results
    """
    undo_manager.snapshot([path])
    try:
        content = Path(path).read_text(encoding='utf-8')
        original_content = content
        
        results = []
        for i, repl in enumerate(replacements):
            old = repl.get('old', '')
            new = repl.get('new', '')
            
            if not old:
                results.append({"index": i, "error": "Missing 'old' value"})
                continue
            
            count = content.count(old)
            if count == 0:
                results.append({"index": i, "old": old[:50], "found": False})
            else:
                content = content.replace(old, new)
                results.append({"index": i, "old": old[:50], "new": new[:50], "count": count})
        
        if content != original_content:
            Path(path).write_text(content, encoding='utf-8')
            return {"path": path, "replacements": results, "modified": True}
        else:
            return {"path": path, "replacements": results, "modified": False}
    except Exception as e:
        return {"error": str(e)}


def git_status() -> Dict[str, Any]:
    """
    Get current git status - branch, modified files, etc.
    
    Returns:
        Dict with git status information
    """
    try:
        # Check if git is available
        result = execute_pwsh("git --version")
        if result["returncode"] != 0:
            return {"error": "Git is not installed or not in PATH"}
        
        # Get current branch
        branch_result = execute_pwsh("git branch --show-current")
        branch = branch_result["stdout"].strip() if branch_result["returncode"] == 0 else "unknown"
        
        # Get status
        status_result = execute_pwsh("git status --porcelain")
        
        if status_result["returncode"] != 0:
            return {"error": "Not a git repository or git error", "details": status_result["stderr"]}
        
        # Parse status
        lines = status_result["stdout"].strip().split('\n') if status_result["stdout"].strip() else []
        
        modified = []
        added = []
        deleted = []
        untracked = []
        
        for line in lines:
            if not line:
                continue
            status_code = line[:2]
            filepath = line[3:]
            
            if status_code.strip() == 'M' or 'M' in status_code:
                modified.append(filepath)
            elif status_code.strip() == 'A' or 'A' in status_code:
                added.append(filepath)
            elif status_code.strip() == 'D' or 'D' in status_code:
                deleted.append(filepath)
            elif status_code.strip() == '??':
                untracked.append(filepath)
        
        return {
            "branch": branch,
            "modified": modified,
            "added": added,
            "deleted": deleted,
            "untracked": untracked,
            "clean": len(lines) == 0
        }
    except Exception as e:
        return {"error": str(e)}


def git_diff(path: str = None, staged: bool = False) -> Dict[str, Any]:
    """
    Show git diff for a file or entire repo.
    
    Args:
        path: Optional path to specific file. If None, shows diff for entire repo
        staged: If True, shows staged changes (git diff --cached)
    
    Returns:
        Dict with diff output
    """
    try:
        cmd = "git diff"
        if staged:
            cmd += " --cached"
        if path:
            cmd += f' "{path}"'
        
        result = execute_pwsh(cmd)
        
        if result["returncode"] != 0:
            return {"error": "Git error", "details": result["stderr"]}
        
        return {
            "path": path or "all files",
            "staged": staged,
            "diff": result["stdout"],
            "has_changes": bool(result["stdout"].strip())
        }
    except Exception as e:
        return {"error": str(e)}


def find_in_file(path: str, pattern: str, context_lines: int = 2, case_sensitive: bool = False) -> Dict[str, Any]:
    """
    Search for pattern in a specific file with context lines.
    
    Args:
        path: Path to the file
        pattern: Text or regex pattern to search for
        context_lines: Number of lines to show before/after match (default 2)
        case_sensitive: Whether search is case sensitive (default False)
    
    Returns:
        Dict with matches and context
    """
    try:
        if not Path(path).exists():
            return {"error": f"File not found: {path}"}
        
        content = Path(path).read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Compile regex
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return {"error": f"Invalid regex pattern: {e}"}
        
        matches = []
        for i, line in enumerate(lines, 1):
            if regex.search(line):
                # Get context
                start = max(0, i - 1 - context_lines)
                end = min(len(lines), i + context_lines)
                
                context = []
                for j in range(start, end):
                    context.append({
                        "line_number": j + 1,
                        "content": lines[j],
                        "is_match": j + 1 == i
                    })
                
                matches.append({
                    "line_number": i,
                    "line": line,
                    "context": context
                })
        
        return {
            "path": path,
            "pattern": pattern,
            "matches": len(matches),
            "results": matches[:50]  # Limit to 50 matches
        }
    except Exception as e:
        return {"error": str(e)}


def get_environment_variable(name: str, default: str = None) -> Dict[str, Any]:
    """
    Get environment variable value.
    
    Args:
        name: Environment variable name
        default: Default value if not found
    
    Returns:
        Dict with variable value or error
    """
    try:
        value = os.environ.get(name, default)
        return {
            "name": name,
            "value": value,
            "exists": name in os.environ
        }
    except Exception as e:
        return {"error": str(e)}


def validate_json(path: str) -> Dict[str, Any]:
    """
    Validate JSON file and return any errors.
    
    Args:
        path: Path to JSON file
    
    Returns:
        Dict with validation results
    """
    try:
        if not Path(path).exists():
            return {"error": f"File not found: {path}"}
        
        content = Path(path).read_text(encoding='utf-8')
        
        try:
            data = json.loads(content)
            return {
                "path": path,
                "valid": True,
                "type": type(data).__name__,
                "keys": list(data.keys()) if isinstance(data, dict) else None,
                "length": len(data) if isinstance(data, (list, dict)) else None
            }
        except json.JSONDecodeError as e:
            return {
                "path": path,
                "valid": False,
                "error": str(e),
                "line": e.lineno,
                "column": e.colno,
                "message": e.msg
            }
    except Exception as e:
        return {"error": str(e)}


def count_lines(path: str) -> Dict[str, Any]:
    """
    Count lines, words, and characters in a file.
    
    Args:
        path: Path to the file
    
    Returns:
        Dict with counts
    """
    try:
        if not Path(path).exists():
            return {"error": f"File not found: {path}"}
        
        content = Path(path).read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Count non-empty lines
        non_empty_lines = sum(1 for line in lines if line.strip())
        
        # Count words
        words = len(content.split())
        
        # Count characters
        chars = len(content)
        chars_no_whitespace = len(content.replace(' ', '').replace('\n', '').replace('\t', ''))
        
        return {
            "path": path,
            "lines": len(lines),
            "non_empty_lines": non_empty_lines,
            "words": words,
            "characters": chars,
            "characters_no_whitespace": chars_no_whitespace,
            "size_bytes": Path(path).stat().st_size
        }
    except Exception as e:
        return {"error": str(e)}


def backup_file(path: str, backup_suffix: str = ".bak") -> Dict[str, Any]:
    """
    Create a backup copy of a file.
    
    Args:
        path: Path to the file to backup
        backup_suffix: Suffix for backup file (default .bak)
    
    Returns:
        Dict with backup information
    """
    try:
        if not Path(path).exists():
            return {"error": f"File not found: {path}"}
        
        if not Path(path).is_file():
            return {"error": f"Path is not a file: {path}"}
        
        # Create backup path
        backup_path = str(Path(path)) + backup_suffix
        
        # Copy file
        import shutil
        shutil.copy2(path, backup_path)
        
        return {
            "original": path,
            "backup": backup_path,
            "size": Path(backup_path).stat().st_size,
            "created": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


def finish(summary: str, status: str = "complete") -> Dict[str, Any]:
    """
    Signal that the agent has finished its current task and wants user review.
    
    Args:
        summary: A summary of what was accomplished
        status: One of "complete" (task done), "blocked" (needs user help), "partial" (some progress made)
    
    Returns:
        Marker dict that the execution loop will intercept to pause for user review
    """
    return {
        "_finish": True,
        "summary": summary,
        "status": status
    }


# --- Advanced Features: Test Generation, Debugging, Refactoring ---

def generate_tests(path: str, test_framework: str = "pytest", coverage: bool = True) -> Dict[str, Any]:
    """
    Generate unit tests for a Python file.
    
    Args:
        path: Path to the source file
        test_framework: Test framework to use (pytest, unittest)
        coverage: Whether to include coverage annotations
    
    Returns:
        Dict with generated test code
    """
    try:
        if not Path(path).exists():
            return {"error": f"File not found: {path}"}
        
        # Read the source file
        source_code = Path(path).read_text(encoding='utf-8')
        
        # Parse to find functions and classes
        import ast
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return {"error": f"Syntax error in source file: {e}"}
        
        functions = []
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Get function signature
                args = [arg.arg for arg in node.args.args]
                functions.append({
                    "name": node.name,
                    "args": args,
                    "line": node.lineno
                })
            elif isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append(item.name)
                classes.append({
                    "name": node.name,
                    "methods": methods,
                    "line": node.lineno
                })
        
        # Generate test file path
        test_path = Path(path).parent / f"test_{Path(path).name}"
        
        # Generate test template
        if test_framework == "pytest":
            test_code = f'''"""
Tests for {Path(path).name}
Auto-generated by SuperCoder
"""
import pytest
from {Path(path).stem} import *


'''
            # Generate test functions
            for func in functions:
                if not func["name"].startswith("_"):  # Skip private functions
                    test_code += f'''def test_{func["name"]}():
    """Test {func["name"]} function"""
    # TODO: Implement test
    # Example: result = {func["name"]}({", ".join(f"arg{i}" for i in range(len(func["args"])))})
    # assert result == expected_value
    pass


'''
            
            # Generate test classes
            for cls in classes:
                test_code += f'''class Test{cls["name"]}:
    """Tests for {cls["name"]} class"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.instance = {cls["name"]}()
    
'''
                for method in cls["methods"]:
                    if not method.startswith("_") and method != "__init__":
                        test_code += f'''    def test_{method}(self):
        """Test {method} method"""
        # TODO: Implement test
        pass
    
'''
        
        return {
            "source_file": path,
            "test_file": test_path,
            "test_code": test_code,
            "functions_found": len(functions),
            "classes_found": len(classes),
            "framework": test_framework
        }
    
    except Exception as e:
        return {"error": str(e)}


def analyze_test_coverage(path: str = ".") -> Dict[str, Any]:
    """
    Analyze test coverage for Python files.
    
    Args:
        path: Path to analyze (file or directory)
    
    Returns:
        Dict with coverage information
    """
    try:
        # Run pytest with coverage
        result = execute_pwsh(f'python -m pytest "{path}" --cov=. --cov-report=json --cov-report=term', timeout=120)
        
        if result["returncode"] != 0:
            return {
                "error": "Coverage analysis failed",
                "output": result["stderr"],
                "suggestion": "Make sure pytest-cov is installed: pip install pytest-cov"
            }
        
        # Try to read coverage.json if it exists
        coverage_file = Path(".coverage.json") if Path(".coverage.json").exists() else Path("coverage.json")
        
        if coverage_file.exists():
            coverage_data = json.loads(coverage_file.read_text())
            return {
                "coverage_file": str(coverage_file),
                "summary": coverage_data.get("totals", {}),
                "output": result["stdout"]
            }
        else:
            return {
                "output": result["stdout"],
                "message": "Coverage report generated (see terminal output)"
            }
    
    except Exception as e:
        return {"error": str(e)}


def set_breakpoint_trace(path: str, line_number: int, condition: str = None) -> Dict[str, Any]:
    """
    Insert a breakpoint/trace statement in code.
    
    Args:
        path: Path to the file
        line_number: Line number to insert breakpoint
        condition: Optional condition for conditional breakpoint
    
    Returns:
        Dict with result
    """
    undo_manager.snapshot([path])
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines(keepends=True)
        
        if line_number < 1 or line_number > len(lines):
            return {"error": f"Line number {line_number} out of range (1-{len(lines)})"}
        
        # Get indentation of target line
        target_line = lines[line_number - 1]
        indent = len(target_line) - len(target_line.lstrip())
        
        # Create breakpoint statement
        if condition:
            breakpoint_line = f"{' ' * indent}if {condition}: breakpoint()  # SuperCoder breakpoint\n"
        else:
            breakpoint_line = f"{' ' * indent}breakpoint()  # SuperCoder breakpoint\n"
        
        # Insert breakpoint
        lines.insert(line_number - 1, breakpoint_line)
        
        Path(path).write_text(''.join(lines), encoding='utf-8')
        
        return {
            "path": path,
            "line": line_number,
            "condition": condition,
            "message": f"Breakpoint inserted at line {line_number}"
        }
    
    except Exception as e:
        return {"error": str(e)}


def remove_breakpoints(path: str) -> Dict[str, Any]:
    """
    Remove all SuperCoder breakpoints from a file.
    
    Args:
        path: Path to the file
    
    Returns:
        Dict with result
    """
    undo_manager.snapshot([path])
    try:
        content = Path(path).read_text(encoding='utf-8')
        lines = content.splitlines(keepends=True)
        
        # Remove lines with SuperCoder breakpoints
        original_count = len(lines)
        lines = [line for line in lines if "# SuperCoder breakpoint" not in line]
        removed = original_count - len(lines)
        
        Path(path).write_text(''.join(lines), encoding='utf-8')
        
        return {
            "path": path,
            "removed": removed,
            "message": f"Removed {removed} breakpoint(s)"
        }
    
    except Exception as e:
        return {"error": str(e)}


def analyze_stack_trace(error_output: str) -> Dict[str, Any]:
    """
    Analyze a Python stack trace and extract useful information.
    
    Args:
        error_output: The error/stack trace text
    
    Returns:
        Dict with analyzed information
    """
    try:
        lines = error_output.strip().split('\n')
        
        # Find the actual error message (usually last line)
        error_message = lines[-1] if lines else ""
        
        # Extract error type
        error_type = error_message.split(':')[0] if ':' in error_message else "Unknown"
        
        # Find file references
        file_references = []
        for line in lines:
            if 'File "' in line:
                # Extract file path and line number
                import re
                match = re.search(r'File "([^"]+)", line (\d+)', line)
                if match:
                    file_references.append({
                        "file": match.group(1),
                        "line": int(match.group(2))
                    })
        
        # Get the last file reference (usually where error occurred)
        error_location = file_references[-1] if file_references else None
        
        return {
            "error_type": error_type,
            "error_message": error_message,
            "error_location": error_location,
            "stack_depth": len(file_references),
            "all_locations": file_references,
            "full_trace": error_output
        }
    
    except Exception as e:
        return {"error": f"Failed to analyze stack trace: {str(e)}"}


def rename_symbol(symbol: str, new_name: str, path: str = ".", file_pattern: str = "*.py") -> Dict[str, Any]:
    """
    Rename a symbol (function, class, variable) across multiple files.
    
    Args:
        symbol: Current symbol name
        new_name: New symbol name
        path: Root directory to search
        file_pattern: File pattern to match (default: *.py)
    
    Returns:
        Dict with renamed files
    """
    try:
        import glob
        
        # Find all matching files
        if Path(path).is_file():
            files = [path]
        else:
            pattern = str(Path(path) / "**" / file_pattern)
            files = glob.glob(pattern, recursive=True)
        
        # Backup all files first
        undo_manager.snapshot(files)
        
        modified_files = []
        total_replacements = 0
        
        for file_path in files:
            try:
                content = Path(file_path).read_text(encoding='utf-8')
                
                # Use word boundary regex to avoid partial matches
                import re
                pattern = r'\b' + re.escape(symbol) + r'\b'
                new_content, count = re.subn(pattern, new_name, content)
                
                if count > 0:
                    Path(file_path).write_text(new_content, encoding='utf-8')
                    modified_files.append({
                        "file": file_path,
                        "replacements": count
                    })
                    total_replacements += count
            
            except Exception as e:
                # Skip files that can't be read
                continue
        
        return {
            "symbol": symbol,
            "new_name": new_name,
            "files_modified": len(modified_files),
            "total_replacements": total_replacements,
            "details": modified_files
        }
    
    except Exception as e:
        return {"error": str(e)}


def generate_commit_message(staged: bool = True) -> Dict[str, Any]:
    """
    Generate a descriptive commit message based on git diff.
    
    Args:
        staged: Generate message for staged changes (default) or all changes
    
    Returns:
        Dict with generated commit message
    """
    try:
        # Get the diff
        diff_result = git_diff(staged=staged)
        
        if "error" in diff_result:
            return diff_result
        
        if not diff_result.get("has_changes"):
            return {"message": "No changes to commit"}
        
        diff_text = diff_result["diff"]
        
        # Analyze the diff
        lines = diff_text.split('\n')
        
        files_changed = []
        additions = 0
        deletions = 0
        
        current_file = None
        for line in lines:
            if line.startswith('diff --git'):
                # Extract filename
                parts = line.split()
                if len(parts) >= 4:
                    current_file = parts[3].replace('b/', '')
                    if current_file not in files_changed:
                        files_changed.append(current_file)
            elif line.startswith('+') and not line.startswith('+++'):
                additions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
        
        # Generate commit message
        if len(files_changed) == 1:
            subject = f"Update {files_changed[0]}"
        elif len(files_changed) <= 3:
            subject = f"Update {', '.join(files_changed)}"
        else:
            subject = f"Update {len(files_changed)} files"
        
        # Add details
        body_parts = []
        body_parts.append(f"Modified {len(files_changed)} file(s)")
        body_parts.append(f"+{additions} -{deletions} lines")
        
        if files_changed:
            body_parts.append("\nFiles changed:")
            for f in files_changed[:10]:  # Limit to 10 files
                body_parts.append(f"  - {f}")
        
        commit_message = f"{subject}\n\n" + "\n".join(body_parts)
        
        return {
            "message": commit_message,
            "subject": subject,
            "files_changed": len(files_changed),
            "additions": additions,
            "deletions": deletions
        }
    
    except Exception as e:
        return {"error": str(e)}


def create_pull_request(title: str, body: str = "", base: str = "main", head: str = None) -> Dict[str, Any]:
    """
    Create a pull request (requires gh CLI).
    
    Args:
        title: PR title
        body: PR description
        base: Base branch (default: main)
        head: Head branch (default: current branch)
    
    Returns:
        Dict with PR information
    """
    try:
        # Check if gh CLI is installed
        check_result = execute_pwsh("gh --version")
        if check_result["returncode"] != 0:
            return {
                "error": "GitHub CLI (gh) not installed",
                "install": "https://cli.github.com/"
            }
        
        # Get current branch if head not specified
        if not head:
            branch_result = execute_pwsh("git branch --show-current")
            head = branch_result["stdout"].strip()
        
        # Create PR
        cmd = f'gh pr create --title "{title}" --body "{body}" --base {base} --head {head}'
        result = execute_pwsh(cmd)
        
        if result["returncode"] == 0:
            return {
                "success": True,
                "title": title,
                "base": base,
                "head": head,
                "output": result["stdout"]
            }
        else:
            return {
                "error": "Failed to create PR",
                "details": result["stderr"]
            }
    
    except Exception as e:
        return {"error": str(e)}


def resolve_merge_conflict(path: str, strategy: str = "ours") -> Dict[str, Any]:
    """
    Attempt to resolve merge conflicts in a file.
    
    Args:
        path: Path to file with conflicts
        strategy: Resolution strategy - "ours", "theirs", or "both"
    
    Returns:
        Dict with resolution result
    """
    undo_manager.snapshot([path])
    try:
        content = Path(path).read_text(encoding='utf-8')
        
        if '<<<<<<<' not in content:
            return {"message": "No merge conflicts found in file"}
        
        lines = content.split('\n')
        resolved_lines = []
        in_conflict = False
        conflict_start = None
        ours_lines = []
        theirs_lines = []
        
        for i, line in enumerate(lines):
            if line.startswith('<<<<<<<'):
                in_conflict = True
                conflict_start = i
                ours_lines = []
                theirs_lines = []
            elif line.startswith('=======') and in_conflict:
                # Switch from ours to theirs
                pass
            elif line.startswith('>>>>>>>') and in_conflict:
                # End of conflict
                if strategy == "ours":
                    resolved_lines.extend(ours_lines)
                elif strategy == "theirs":
                    resolved_lines.extend(theirs_lines)
                elif strategy == "both":
                    resolved_lines.extend(ours_lines)
                    resolved_lines.append("# --- merged ---")
                    resolved_lines.extend(theirs_lines)
                
                in_conflict = False
            elif in_conflict:
                if conflict_start is not None and '=======' not in line:
                    if not any(line.startswith(m) for m in ['<<<<<<<', '=======']):
                        if len(theirs_lines) == 0 or '=======' in '\n'.join(lines[conflict_start:i]):
                            theirs_lines.append(line)
                        else:
                            ours_lines.append(line)
            else:
                resolved_lines.append(line)
        
        resolved_content = '\n'.join(resolved_lines)
        Path(path).write_text(resolved_content, encoding='utf-8')
        
        return {
            "path": path,
            "strategy": strategy,
            "message": "Merge conflicts resolved",
            "note": "Please review the changes carefully"
        }
    
    except Exception as e:
        return {"error": str(e)}


# --- Load Context Guide ---
def load_context_guide(guide_name: str) -> Dict[str, Any]:
    """
    Load additional context guides for specialized tasks.
    Use this when you recognize a task that needs specialized knowledge.
    
    Args:
        guide_name: Name of the guide to load (e.g., "web-apps")
    
    Available guides:
    - "web-apps": Complete guide for building web applications with Next.js + Supabase
    - "supabase-cli-guide": Comprehensive Supabase CLI usage guide
    - "postgres-guide": Comprehensive PostgreSQL database integration guide
    
    Returns:
        Guide content and metadata
    """
    try:
        # Get the Agents directory
        agents_dir = Path(__file__).parent / "Agents"
        guide_path = agents_dir / f"{guide_name}.md"
        
        if not guide_path.exists():
            return {
                "error": f"Guide '{guide_name}' not found",
                "available_guides": ["web-apps", "supabase-cli-guide", "postgres-guide"]
            }
        
        content = guide_path.read_text(encoding='utf-8')
        
        return {
            "guide_name": guide_name,
            "content": content,
            "path": str(guide_path),
            "message": f"Loaded {guide_name} guide - follow this for the current task"
        }
        
    except Exception as e:
        return {"error": str(e)}



# ==============================================================================
# PostgreSQL Database Integration
# ==============================================================================

_postgres_connections: Dict[str, Any] = {}

def postgres_connect(
    connection_name: str = "default",
    host: str = "localhost",
    port: int = 5432,
    database: str = None,
    user: str = None,
    password: str = None,
    connection_string: str = None
) -> Dict[str, Any]:
    """
    Connect to a PostgreSQL database.
    
    Args:
        connection_name: Name for this connection (default: "default")
        host: Database host (default: localhost)
        port: Database port (default: 5432)
        database: Database name
        user: Username
        password: Password
        connection_string: Full connection string (overrides other params)
            Format: postgresql://user:password@host:port/database
    
    Returns:
        Connection status and info
    """
    try:
        import psycopg2
        from psycopg2 import pool
    except ImportError:
        return {
            "error": "psycopg2 not installed. Install with: pip install psycopg2-binary"
        }
    
    try:
        if connection_string:
            conn = psycopg2.connect(connection_string)
        else:
            if not all([database, user, password]):
                return {
                    "error": "Missing required parameters: database, user, password (or provide connection_string)"
                }
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
        
        # Test connection
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        
        _postgres_connections[connection_name] = conn
        
        return {
            "connection_name": connection_name,
            "status": "connected",
            "database": database or "from connection string",
            "host": host,
            "port": port,
            "version": version
        }
    
    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}


def postgres_disconnect(connection_name: str = "default") -> Dict[str, Any]:
    """
    Disconnect from a PostgreSQL database.
    
    Args:
        connection_name: Name of the connection to close
    
    Returns:
        Disconnection status
    """
    if connection_name not in _postgres_connections:
        return {"error": f"Connection '{connection_name}' not found"}
    
    try:
        _postgres_connections[connection_name].close()
        del _postgres_connections[connection_name]
        return {
            "connection_name": connection_name,
            "status": "disconnected"
        }
    except Exception as e:
        return {"error": str(e)}


def postgres_list_connections() -> Dict[str, Any]:
    """
    List all active PostgreSQL connections.
    
    Returns:
        List of connection names and their status
    """
    connections = []
    for name, conn in _postgres_connections.items():
        try:
            # Check if connection is alive
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.close()
            status = "active"
        except:
            status = "closed"
        
        connections.append({
            "name": name,
            "status": status
        })
    
    return {"connections": connections}


def postgres_query(
    query: str,
    params: List[Any] = None,
    connection_name: str = "default",
    fetch_all: bool = True
) -> Dict[str, Any]:
    """
    Execute a SELECT query and return results.
    
    Args:
        query: SQL SELECT query
        params: Query parameters (for parameterized queries)
        connection_name: Name of the connection to use
        fetch_all: If True, fetch all rows; if False, fetch one row
    
    Returns:
        Query results with column names
    """
    if connection_name not in _postgres_connections:
        return {"error": f"Connection '{connection_name}' not found. Use postgres_connect first."}
    
    try:
        conn = _postgres_connections[connection_name]
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        # Get column names
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        # Fetch results
        if fetch_all:
            rows = cursor.fetchall()
        else:
            row = cursor.fetchone()
            rows = [row] if row else []
        
        cursor.close()
        
        # Convert to list of dicts
        results = []
        for row in rows:
            results.append(dict(zip(columns, row)))
        
        return {
            "query": query,
            "row_count": len(results),
            "columns": columns,
            "rows": results
        }
    
    except Exception as e:
        return {"error": f"Query failed: {str(e)}"}


def postgres_execute(
    query: str,
    params: List[Any] = None,
    connection_name: str = "default",
    commit: bool = True
) -> Dict[str, Any]:
    """
    Execute an INSERT, UPDATE, DELETE, or DDL query.
    
    Args:
        query: SQL query (INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, etc.)
        params: Query parameters (for parameterized queries)
        connection_name: Name of the connection to use
        commit: Whether to commit the transaction (default: True)
    
    Returns:
        Execution status and affected row count
    """
    if connection_name not in _postgres_connections:
        return {"error": f"Connection '{connection_name}' not found. Use postgres_connect first."}
    
    try:
        conn = _postgres_connections[connection_name]
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        affected_rows = cursor.rowcount
        
        if commit:
            conn.commit()
        
        cursor.close()
        
        return {
            "query": query,
            "affected_rows": affected_rows,
            "status": "success",
            "committed": commit
        }
    
    except Exception as e:
        conn.rollback()
        return {"error": f"Execution failed: {str(e)}"}


def postgres_list_tables(
    connection_name: str = "default",
    schema: str = "public"
) -> Dict[str, Any]:
    """
    List all tables in the database.
    
    Args:
        connection_name: Name of the connection to use
        schema: Schema name (default: public)
    
    Returns:
        List of table names
    """
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = %s 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """
    
    result = postgres_query(query, params=[schema], connection_name=connection_name)
    
    if "error" in result:
        return result
    
    tables = [row["table_name"] for row in result["rows"]]
    
    return {
        "schema": schema,
        "table_count": len(tables),
        "tables": tables
    }


def postgres_describe_table(
    table_name: str,
    connection_name: str = "default",
    schema: str = "public"
) -> Dict[str, Any]:
    """
    Get detailed information about a table's structure.
    
    Args:
        table_name: Name of the table
        connection_name: Name of the connection to use
        schema: Schema name (default: public)
    
    Returns:
        Table structure with columns, types, constraints
    """
    query = """
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position;
    """
    
    result = postgres_query(query, params=[schema, table_name], connection_name=connection_name)
    
    if "error" in result:
        return result
    
    # Get primary keys
    pk_query = """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = %s::regclass AND i.indisprimary;
    """
    
    pk_result = postgres_query(
        pk_query, 
        params=[f"{schema}.{table_name}"], 
        connection_name=connection_name
    )
    
    primary_keys = [row["attname"] for row in pk_result.get("rows", [])] if "rows" in pk_result else []
    
    return {
        "table_name": table_name,
        "schema": schema,
        "columns": result["rows"],
        "primary_keys": primary_keys,
        "column_count": len(result["rows"])
    }


def postgres_insert(
    table_name: str,
    data: Dict[str, Any],
    connection_name: str = "default",
    schema: str = "public",
    returning: str = None
) -> Dict[str, Any]:
    """
    Insert a row into a table.
    
    Args:
        table_name: Name of the table
        data: Dictionary of column:value pairs
        connection_name: Name of the connection to use
        schema: Schema name (default: public)
        returning: Column to return (e.g., "id" for auto-generated IDs)
    
    Returns:
        Insert status and optionally returned value
    """
    if not data:
        return {"error": "No data provided"}
    
    columns = list(data.keys())
    values = list(data.values())
    placeholders = ["%s"] * len(values)
    
    query = f"""
        INSERT INTO {schema}.{table_name} ({', '.join(columns)})
        VALUES ({', '.join(placeholders)})
    """
    
    if returning:
        query += f" RETURNING {returning}"
    
    if returning:
        result = postgres_query(query, params=values, connection_name=connection_name, fetch_all=False)
        if "error" in result:
            return result
        return {
            "status": "success",
            "table": table_name,
            "inserted": data,
            "returned": result["rows"][0] if result["rows"] else None
        }
    else:
        result = postgres_execute(query, params=values, connection_name=connection_name)
        if "error" in result:
            return result
        return {
            "status": "success",
            "table": table_name,
            "inserted": data,
            "affected_rows": result["affected_rows"]
        }


def postgres_update(
    table_name: str,
    data: Dict[str, Any],
    where: str,
    where_params: List[Any] = None,
    connection_name: str = "default",
    schema: str = "public"
) -> Dict[str, Any]:
    """
    Update rows in a table.
    
    Args:
        table_name: Name of the table
        data: Dictionary of column:value pairs to update
        where: WHERE clause (without the WHERE keyword)
        where_params: Parameters for the WHERE clause
        connection_name: Name of the connection to use
        schema: Schema name (default: public)
    
    Returns:
        Update status and affected row count
    """
    if not data:
        return {"error": "No data provided"}
    
    set_clauses = [f"{col} = %s" for col in data.keys()]
    values = list(data.values())
    
    if where_params:
        values.extend(where_params)
    
    query = f"""
        UPDATE {schema}.{table_name}
        SET {', '.join(set_clauses)}
        WHERE {where}
    """
    
    result = postgres_execute(query, params=values, connection_name=connection_name)
    
    if "error" in result:
        return result
    
    return {
        "status": "success",
        "table": table_name,
        "updated": data,
        "where": where,
        "affected_rows": result["affected_rows"]
    }


def postgres_delete(
    table_name: str,
    where: str,
    where_params: List[Any] = None,
    connection_name: str = "default",
    schema: str = "public"
) -> Dict[str, Any]:
    """
    Delete rows from a table.
    
    Args:
        table_name: Name of the table
        where: WHERE clause (without the WHERE keyword)
        where_params: Parameters for the WHERE clause
        connection_name: Name of the connection to use
        schema: Schema name (default: public)
    
    Returns:
        Delete status and affected row count
    """
    query = f"""
        DELETE FROM {schema}.{table_name}
        WHERE {where}
    """
    
    result = postgres_execute(query, params=where_params, connection_name=connection_name)
    
    if "error" in result:
        return result
    
    return {
        "status": "success",
        "table": table_name,
        "where": where,
        "affected_rows": result["affected_rows"]
    }


def postgres_transaction_begin(connection_name: str = "default") -> Dict[str, Any]:
    """
    Begin a transaction (for manual transaction control).
    
    Args:
        connection_name: Name of the connection to use
    
    Returns:
        Transaction status
    """
    if connection_name not in _postgres_connections:
        return {"error": f"Connection '{connection_name}' not found"}
    
    try:
        conn = _postgres_connections[connection_name]
        # PostgreSQL connections are always in a transaction, but we can mark it
        return {
            "status": "transaction_started",
            "connection_name": connection_name,
            "note": "Use postgres_execute with commit=False, then call postgres_transaction_commit or postgres_transaction_rollback"
        }
    except Exception as e:
        return {"error": str(e)}


def postgres_transaction_commit(connection_name: str = "default") -> Dict[str, Any]:
    """
    Commit the current transaction.
    
    Args:
        connection_name: Name of the connection to use
    
    Returns:
        Commit status
    """
    if connection_name not in _postgres_connections:
        return {"error": f"Connection '{connection_name}' not found"}
    
    try:
        conn = _postgres_connections[connection_name]
        conn.commit()
        return {
            "status": "committed",
            "connection_name": connection_name
        }
    except Exception as e:
        return {"error": str(e)}


def postgres_transaction_rollback(connection_name: str = "default") -> Dict[str, Any]:
    """
    Rollback the current transaction.
    
    Args:
        connection_name: Name of the connection to use
    
    Returns:
        Rollback status
    """
    if connection_name not in _postgres_connections:
        return {"error": f"Connection '{connection_name}' not found"}
    
    try:
        conn = _postgres_connections[connection_name]
        conn.rollback()
        return {
            "status": "rolled_back",
            "connection_name": connection_name
        }
    except Exception as e:
        return {"error": str(e)}


def postgres_count_rows(
    table_name: str,
    where: str = None,
    where_params: List[Any] = None,
    connection_name: str = "default",
    schema: str = "public"
) -> Dict[str, Any]:
    """
    Count rows in a table with optional filtering.
    
    Args:
        table_name: Name of the table
        where: Optional WHERE clause (without the WHERE keyword)
        where_params: Parameters for the WHERE clause
        connection_name: Name of the connection to use
        schema: Schema name (default: public)
    
    Returns:
        Row count
    """
    query = f"SELECT COUNT(*) as count FROM {schema}.{table_name}"
    
    if where:
        query += f" WHERE {where}"
    
    result = postgres_query(query, params=where_params, connection_name=connection_name, fetch_all=False)
    
    if "error" in result:
        return result
    
    count = result["rows"][0]["count"] if result["rows"] else 0
    
    return {
        "table": table_name,
        "count": count,
        "where": where
    }


# ==============================================================================
# Image Generation (OpenRouter)
# ==============================================================================

def image_generate(
    prompt: str,
    model: str = "google/gemini-2.5-flash-image",
    save_path: str = None,
    num_images: int = 1
) -> Dict[str, Any]:
    """
    Generate images from text prompts using OpenRouter image generation models.
    The AI model automatically determines the best aspect ratio and size based on your prompt.
    
    Args:
        prompt: Text description of the image to generate (be specific about what you want)
        model: Image generation model to use (default: google/gemini-2.5-flash-image)
        save_path: Optional path to save the image (auto-generates if not provided)
        num_images: Number of images to generate (default: 1)
    
    Returns:
        Dict with generated image paths and metadata
    """
    try:
        # Import required modules
        import requests
        import base64
        from datetime import datetime
        
        # Get API key
        try:
            from Agentic import TokenManager
            TokenManager.load_tokens()
            api_key = TokenManager.get_token()
        except Exception as e:
            return {"error": f"Failed to load API key: {e}"}
        
        # Build request payload - let the model decide aspect ratio and size
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "modalities": ["image", "text"]
        }
        
        # Make API request
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/4lpine/Supercoder",
                "X-Title": "Supercoder"
            },
            json=payload,
            timeout=120
        )
        
        # Check for errors
        if response.status_code != 200:
            error_detail = ""
            try:
                error_data = response.json()
                error_detail = error_data.get("error", {}).get("message", str(error_data))
            except:
                error_detail = response.text
            
            return {
                "error": f"API request failed with status {response.status_code}",
                "detail": error_detail,
                "model": model,
                "prompt": prompt
            }
        
        result = response.json()
        
        # Extract images from response
        if not result.get("choices"):
            return {"error": "No response from API", "result": result}
        
        message = result["choices"][0]["message"]
        
        if not message.get("images"):
            return {
                "error": "No images generated",
                "response": message.get("content", ""),
                "model": model,
                "prompt": prompt
            }
        
        # Process and save images
        saved_images = []
        
        for idx, image_data in enumerate(message["images"]):
            # Get base64 image data
            image_url = image_data["image_url"]["url"]
            
            # Extract base64 data (remove data:image/png;base64, prefix)
            if "base64," in image_url:
                base64_data = image_url.split("base64,")[1]
            else:
                base64_data = image_url
            
            # Decode base64 to bytes
            image_bytes = base64.b64decode(base64_data)
            
            # Generate save path if not provided
            if save_path:
                if num_images > 1:
                    # Add index to filename
                    path_obj = Path(save_path)
                    save_file = path_obj.parent / f"{path_obj.stem}_{idx+1}{path_obj.suffix}"
                else:
                    save_file = Path(save_path)
            else:
                # Auto-generate path in .supercoder/images/
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                images_dir = Path(".supercoder/images")
                images_dir.mkdir(parents=True, exist_ok=True)
                save_file = images_dir / f"generated_{timestamp}_{idx+1}.png"
            
            # Save image
            save_file.parent.mkdir(parents=True, exist_ok=True)
            save_file.write_bytes(image_bytes)
            
            saved_images.append({
                "path": str(save_file),
                "size_bytes": len(image_bytes),
                "index": idx + 1
            })
        
        return {
            "status": "success",
            "prompt": prompt,
            "model": model,
            "num_images": len(saved_images),
            "images": saved_images,
            "response_text": message.get("content", "")
        }
    
    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Image generation failed: {str(e)}"}


def image_generate_batch(
    prompts: List[str],
    model: str = "google/gemini-2.5-flash-image",
    save_dir: str = None
) -> Dict[str, Any]:
    """
    Generate multiple images from a list of prompts.
    The AI model automatically determines the best aspect ratio and size for each image.
    
    Args:
        prompts: List of text descriptions
        model: Image generation model to use
        save_dir: Directory to save images (default: .supercoder/images/)
    
    Returns:
        Dict with results for each prompt
    """
    if not prompts:
        return {"error": "No prompts provided"}
    
    results = []
    
    for idx, prompt in enumerate(prompts):
        # Generate save path
        if save_dir:
            save_path = Path(save_dir) / f"image_{idx+1}.png"
        else:
            save_path = None
        
        # Generate image
        result = image_generate(
            prompt=prompt,
            model=model,
            save_path=str(save_path) if save_path else None
        )
        
        results.append({
            "prompt": prompt,
            "result": result
        })
    
    # Count successes and failures
    successes = sum(1 for r in results if r["result"].get("status") == "success")
    failures = len(results) - successes
    
    return {
        "total": len(prompts),
        "successes": successes,
        "failures": failures,
        "results": results
    }


def image_list_models() -> Dict[str, Any]:
    """
    List available image generation models on OpenRouter.
    
    Returns:
        Dict with available models and their capabilities
    """
    models = [
        {
            "id": "google/gemini-2.5-flash-image",
            "name": "Gemini 2.5 Flash Image",
            "provider": "Google",
            "features": [
                "Fast generation",
                "Aspect ratio control",
                "Image size control",
                "High quality"
            ],
            "aspect_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
            "image_sizes": ["256x256", "512x512", "1024x1024", "2048x2048", "4K"],
            "recommended": True
        },
        {
            "id": "google/gemini-3-pro-image-preview",
            "name": "Gemini 3 Pro Image (Nano Banana Pro)",
            "provider": "Google",
            "features": [
                "Higher quality",
                "Aspect ratio control",
                "Image size control"
            ],
            "aspect_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
            "image_sizes": ["256x256", "512x512", "1024x1024", "2048x2048", "4K"],
            "recommended": False
        },
        {
            "id": "openai/gpt-5-image",
            "name": "GPT-5 Image",
            "provider": "OpenAI",
            "features": [
                "Superior instruction following",
                "Text rendering in images",
                "Detailed image editing"
            ],
            "aspect_ratios": [],
            "image_sizes": [],
            "recommended": False
        }
    ]
    
    return {
        "models": models,
        "default": "google/gemini-2.5-flash-image",
        "count": len(models)
    }


def image_edit(
    image_path: str,
    prompt: str,
    model: str = "google/gemini-2.5-flash-image",
    save_path: str = None
) -> Dict[str, Any]:
    """
    Edit an existing image based on a text prompt.
    
    Args:
        image_path: Path to the image to edit
        prompt: Description of how to edit the image
        model: Image generation model to use
        save_path: Optional path to save the edited image
    
    Returns:
        Dict with edited image path and metadata
    """
    try:
        import requests
        import base64
        from datetime import datetime
        
        # Read the image
        image_file = Path(image_path)
        if not image_file.exists():
            return {"error": f"Image not found: {image_path}"}
        
        # Encode image to base64
        image_bytes = image_file.read_bytes()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # Determine image type
        ext = image_file.suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(ext, 'image/png')
        
        # Get API key
        try:
            from Agentic import TokenManager
            TokenManager.load_tokens()
            api_key = TokenManager.get_token()
        except Exception as e:
            return {"error": f"Failed to load API key: {e}"}
        
        # Build request with image input
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        },
                        {
                            "type": "text",
                            "text": f"Edit this image: {prompt}"
                        }
                    ]
                }
            ],
            "modalities": ["image", "text"]
        }
        
        # Make API request
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=120
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Extract edited image
        if not result.get("choices"):
            return {"error": "No response from API"}
        
        message = result["choices"][0]["message"]
        
        if not message.get("images"):
            return {
                "error": "No edited image generated",
                "response": message.get("content", "")
            }
        
        # Get base64 image data
        image_url = message["images"][0]["image_url"]["url"]
        
        if "base64," in image_url:
            base64_data = image_url.split("base64,")[1]
        else:
            base64_data = image_url
        
        # Decode base64 to bytes
        edited_bytes = base64.b64decode(base64_data)
        
        # Generate save path if not provided
        if save_path:
            save_file = Path(save_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            images_dir = Path(".supercoder/images")
            images_dir.mkdir(parents=True, exist_ok=True)
            save_file = images_dir / f"edited_{timestamp}.png"
        
        # Save edited image
        save_file.parent.mkdir(parents=True, exist_ok=True)
        save_file.write_bytes(edited_bytes)
        
        return {
            "status": "success",
            "original_image": image_path,
            "edited_image": str(save_file),
            "prompt": prompt,
            "model": model,
            "size_bytes": len(edited_bytes)
        }
    
    except Exception as e:
        return {"error": f"Image editing failed: {str(e)}"}


def image_generate_for_project(
    project_type: str,
    descriptions: List[str] = None,
    save_dir: str = None
) -> Dict[str, Any]:
    """
    Generate a set of images for a specific project type (website, app, etc.).
    
    Args:
        project_type: Type of project (website, app, logo, icon, banner, etc.)
        descriptions: Optional list of specific image descriptions
        save_dir: Directory to save images (default: project-specific folder)
    
    Returns:
        Dict with generated images for the project
    """
    # Default descriptions based on project type
    default_descriptions = {
        "website": [
            "Modern hero section background with gradient",
            "Professional team photo placeholder",
            "Abstract technology background",
            "Call-to-action banner background"
        ],
        "app": [
            "App icon with modern design",
            "Splash screen background",
            "Onboarding illustration 1",
            "Onboarding illustration 2",
            "Empty state illustration"
        ],
        "logo": [
            "Professional company logo design",
            "Logo variation for dark background",
            "Favicon design"
        ],
        "banner": [
            "Website banner 1920x400",
            "Social media banner 1200x630",
            "Email header banner"
        ],
        "icon": [
            "Feature icon 1",
            "Feature icon 2",
            "Feature icon 3",
            "Feature icon 4"
        ]
    }
    
    # Use provided descriptions or defaults
    prompts = descriptions or default_descriptions.get(project_type, [f"{project_type} image"])
    
    # Set save directory
    if not save_dir:
        save_dir = Path(".supercoder/images") / project_type
    else:
        save_dir = Path(save_dir)
    
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate images
    results = []
    
    for idx, prompt in enumerate(prompts):
        save_path = save_dir / f"{project_type}_{idx+1}.png"
        
        result = image_generate(
            prompt=prompt,
            save_path=str(save_path)
        )
        
        results.append({
            "description": prompt,
            "result": result
        })
    
    successes = sum(1 for r in results if r["result"].get("status") == "success")
    
    return {
        "project_type": project_type,
        "save_dir": str(save_dir),
        "total": len(prompts),
        "successes": successes,
        "results": results
    }
