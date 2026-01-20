"""
Tools module for Supercoder - All tool implementations
"""
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
