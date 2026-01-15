
import os
import re
import json
import subprocess
import hashlib
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
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

# --- Host Command Execution (runs on Windows host, not in Docker) ---
def run_on_host(command: str, timeout: int = 60) -> Dict[str, Any]:
    """
    Execute a command on the Windows host machine (not inside Docker).
    Useful for running GUI applications, opening files, etc.
    """
    import time as _time
    
    host_cmd_dir = os.environ.get("HOST_CMD_DIR")
    if not host_cmd_dir:
        return {'stdout': '', 'stderr': 'Host command execution not available (HOST_CMD_DIR not set)', 'returncode': -1}
    
    cmd_file = os.path.join(host_cmd_dir, "cmd.txt")
    result_file = os.path.join(host_cmd_dir, "result.txt")
    done_file = os.path.join(host_cmd_dir, "done.txt")
    
    # Get the Windows path for current directory
    host_pwd = os.environ.get("HOST_PWD", "C:\\")
    
    try:
        # Clean up any previous files
        for f in [result_file, done_file]:
            if os.path.exists(f):
                os.remove(f)
        
        # Write command file
        with open(cmd_file, 'w') as f:
            f.write(f"{command}\n{host_pwd}\n")
        
        # Wait for result
        start = _time.time()
        while _time.time() - start < timeout:
            if os.path.exists(done_file):
                # Read result
                if os.path.exists(result_file):
                    with open(result_file, 'r', encoding='utf-8', errors='replace') as f:
                        output = f.read()
                else:
                    output = ""
                
                # Clean up
                for f in [result_file, done_file]:
                    if os.path.exists(f):
                        os.remove(f)
                
                return {'stdout': output, 'stderr': '', 'returncode': 0}
            _time.sleep(0.1)
        
        return {'stdout': '', 'stderr': f'Timed out after {timeout}s', 'returncode': -1}
    
    except Exception as e:
        return {'stdout': '', 'stderr': str(e), 'returncode': -1}

# --- Shell Execution ---
def execute_pwsh(command: str, timeout: int = 60) -> Dict[str, Any]:
    """Execute a shell command"""
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
    try:
        # Non-blocking read
        import select
        output = ""
        if proc.stdout:
            # Try to read available output
            try:
                proc.stdout.flush()
                output = proc.stdout.read(10000) if proc.stdout.readable() else ""
            except:
                output = "(could not read output)"
        return {"output": output}
    except Exception as e:
        return {"error": str(e)}

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

def read_file(path: str) -> str:
    """Read a file's contents"""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

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
